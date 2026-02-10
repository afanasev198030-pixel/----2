"""
DSPy модули для автооптимизации промптов парсинга и классификации.
Заменяет ручной prompt engineering.
Fallback на regex-парсеры при недоступности OpenAI.
"""
import json
from typing import Optional
import structlog

logger = structlog.get_logger()

_dspy_available = False
try:
    import dspy
    _dspy_available = True
except ImportError:
    logger.warning("dspy_not_available", msg="DSPy not installed")

# Fallback imports
from app.services.invoice_parser import parse as regex_parse_invoice
from app.services.contract_parser import parse as regex_parse_contract
from app.services.packing_parser import parse as regex_parse_packing
from app.services.ocr_service import extract_text


# --- DSPy Signatures ---

if _dspy_available:

    class InvoiceSignature(dspy.Signature):
        """Извлеки структурированные данные из текста инвойса (коммерческого счёта).
        Ты — эксперт по таможенному оформлению РФ."""
        document_text: str = dspy.InputField(desc="Полный текст инвойса")
        invoice_number: str = dspy.OutputField(desc="Номер инвойса")
        invoice_date: str = dspy.OutputField(desc="Дата инвойса (DD.MM.YYYY)")
        seller_name: str = dspy.OutputField(desc="Наименование продавца/поставщика")
        seller_country: str = dspy.OutputField(desc="Код страны продавца ISO 3166-1 alpha-2")
        seller_address: str = dspy.OutputField(desc="Адрес продавца")
        buyer_name: str = dspy.OutputField(desc="Наименование покупателя")
        buyer_country: str = dspy.OutputField(desc="Код страны покупателя ISO 3166-1 alpha-2")
        currency: str = dspy.OutputField(desc="Код валюты (USD, EUR, CNY и т.д.)")
        total_amount: str = dspy.OutputField(desc="Общая сумма инвойса (число)")
        incoterms: str = dspy.OutputField(desc="Условия поставки Incoterms (EXW, FOB, CIF и т.д.)")
        items_json: str = dspy.OutputField(desc='JSON массив позиций: [{"line_no":1,"description":"...","quantity":10,"unit":"pcs","unit_price":5.0,"line_total":50.0}]')
        contract_number: str = dspy.OutputField(desc="Номер контракта/договора")
        country_origin: str = dspy.OutputField(desc="Страна происхождения товара ISO alpha-2")

    class ContractSignature(dspy.Signature):
        """Извлеки данные из текста контракта/договора поставки."""
        document_text: str = dspy.InputField(desc="Полный текст контракта")
        contract_number: str = dspy.OutputField(desc="Номер контракта")
        contract_date: str = dspy.OutputField(desc="Дата контракта")
        seller_name: str = dspy.OutputField(desc="Наименование продавца")
        buyer_name: str = dspy.OutputField(desc="Наименование покупателя")
        total_amount: str = dspy.OutputField(desc="Общая сумма контракта")
        currency: str = dspy.OutputField(desc="Валюта")
        incoterms: str = dspy.OutputField(desc="Условия Incoterms")

    class PackingSignature(dspy.Signature):
        """Извлеки данные из упаковочного листа (packing list)."""
        document_text: str = dspy.InputField(desc="Полный текст упаковочного листа")
        total_packages: str = dspy.OutputField(desc="Общее количество мест/упаковок")
        package_type: str = dspy.OutputField(desc="Тип упаковки (Carton, Pallet и т.д.)")
        total_gross_weight: str = dspy.OutputField(desc="Общий вес брутто в кг")
        total_net_weight: str = dspy.OutputField(desc="Общий вес нетто в кг")

    class HSCodeSignature(dspy.Signature):
        """Определи 10-значный код ТН ВЭД ЕАЭС для товара.
        Используй результаты поиска по справочнику ТН ВЭД."""
        description: str = dspy.InputField(desc="Описание товара")
        rag_results: str = dspy.InputField(desc="Результаты поиска по справочнику ТН ВЭД (top-10 похожих кодов)")
        hs_code: str = dspy.OutputField(desc="10-значный код ТН ВЭД ЕАЭС")
        name_ru: str = dspy.OutputField(desc="Название кода ТН ВЭД на русском")
        reasoning: str = dspy.OutputField(desc="Обоснование выбора кода")
        confidence: str = dspy.OutputField(desc="Уверенность 0.0-1.0")

    class RiskSignature(dspy.Signature):
        """Оцени риски таможенной декларации на основе правил СУР."""
        declaration_data: str = dspy.InputField(desc="Данные декларации в JSON")
        relevant_rules: str = dspy.InputField(desc="Релевантные правила СУР из базы")
        risk_score: str = dspy.OutputField(desc="Общий балл риска 0-100")
        risks_json: str = dspy.OutputField(desc='JSON массив рисков: [{"rule_code":"...","severity":"high","message":"...","recommendation":"..."}]')


# --- DSPy Modules ---

class InvoiceExtractor:
    """Извлечение данных из инвойса — DSPy + fallback на regex."""

    def __init__(self):
        self._dspy_module = None
        if _dspy_available:
            self._dspy_module = dspy.Predict(InvoiceSignature)

    def extract(self, file_bytes: bytes, filename: str) -> dict:
        """Извлечь данные из инвойса."""
        text = extract_text(file_bytes, filename)
        if not text:
            return {"error": "no_text_extracted", "confidence": 0.0}

        # Попытка через DSPy/LLM
        if self._dspy_module:
            try:
                result = self._dspy_module(document_text=text[:8000])
                items = _safe_json_parse(result.items_json, [])
                return {
                    "invoice_number": result.invoice_number,
                    "invoice_date": result.invoice_date,
                    "seller": {
                        "name": result.seller_name,
                        "country_code": result.seller_country,
                        "address": result.seller_address,
                    },
                    "buyer": {
                        "name": result.buyer_name,
                        "country_code": result.buyer_country,
                    },
                    "currency": result.currency,
                    "total_amount": _safe_float(result.total_amount),
                    "incoterms": result.incoterms,
                    "items": items,
                    "contract_number": result.contract_number,
                    "country_origin": result.country_origin,
                    "confidence": 0.9,
                    "source": "dspy_llm",
                    "raw_text": text,
                }
            except Exception as e:
                logger.warning("dspy_invoice_fallback", error=str(e))

        # Fallback на regex
        parsed = regex_parse_invoice(file_bytes, filename)
        return {
            "invoice_number": parsed.invoice_number,
            "invoice_date": parsed.invoice_date,
            "seller": {
                "name": parsed.seller.name if parsed.seller else None,
                "country_code": parsed.seller.country_code if parsed.seller else None,
                "address": parsed.seller.address if parsed.seller else None,
            } if parsed.seller else None,
            "buyer": {
                "name": parsed.buyer.name if parsed.buyer else None,
                "country_code": parsed.buyer.country_code if parsed.buyer else None,
            } if parsed.buyer else None,
            "currency": parsed.currency,
            "total_amount": parsed.total_amount,
            "incoterms": parsed.incoterms,
            "items": [
                {
                    "line_no": item.line_no,
                    "description": item.description_raw,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "unit_price": item.unit_price,
                    "line_total": item.line_total,
                }
                for item in parsed.items
            ],
            "contract_number": parsed.contract_number,
            "country_origin": parsed.country_origin,
            "confidence": parsed.confidence,
            "source": "regex",
            "raw_text": parsed.raw_text,
        }


class ContractExtractor:
    """Извлечение данных из контракта."""

    def __init__(self):
        self._dspy_module = None
        if _dspy_available:
            self._dspy_module = dspy.Predict(ContractSignature)

    def extract(self, file_bytes: bytes, filename: str) -> dict:
        text = extract_text(file_bytes, filename)
        if not text:
            return {"error": "no_text_extracted", "confidence": 0.0}

        if self._dspy_module:
            try:
                result = self._dspy_module(document_text=text[:8000])
                return {
                    "contract_number": result.contract_number,
                    "contract_date": result.contract_date,
                    "seller_name": result.seller_name,
                    "buyer_name": result.buyer_name,
                    "total_amount": _safe_float(result.total_amount),
                    "currency": result.currency,
                    "incoterms": result.incoterms,
                    "confidence": 0.85,
                    "source": "dspy_llm",
                    "raw_text": text,
                }
            except Exception as e:
                logger.warning("dspy_contract_fallback", error=str(e))

        parsed = regex_parse_contract(file_bytes, filename)
        return {
            "contract_number": parsed.contract_number,
            "contract_date": parsed.contract_date,
            "seller_name": parsed.seller_name,
            "buyer_name": parsed.buyer_name,
            "total_amount": parsed.total_amount,
            "currency": parsed.currency,
            "incoterms": parsed.incoterms,
            "confidence": parsed.confidence,
            "source": "regex",
            "raw_text": parsed.raw_text,
        }


class PackingExtractor:
    """Извлечение данных из упаковочного листа."""

    def __init__(self):
        self._dspy_module = None
        if _dspy_available:
            self._dspy_module = dspy.Predict(PackingSignature)

    def extract(self, file_bytes: bytes, filename: str) -> dict:
        text = extract_text(file_bytes, filename)
        if not text:
            return {"error": "no_text_extracted", "confidence": 0.0}

        if self._dspy_module:
            try:
                result = self._dspy_module(document_text=text[:8000])
                return {
                    "total_packages": _safe_int(result.total_packages),
                    "package_type": result.package_type,
                    "total_gross_weight": _safe_float(result.total_gross_weight),
                    "total_net_weight": _safe_float(result.total_net_weight),
                    "confidence": 0.85,
                    "source": "dspy_llm",
                    "raw_text": text,
                }
            except Exception as e:
                logger.warning("dspy_packing_fallback", error=str(e))

        parsed = regex_parse_packing(file_bytes, filename)
        return {
            "total_packages": parsed.total_packages,
            "package_type": parsed.package_type,
            "total_gross_weight": parsed.total_gross_weight,
            "total_net_weight": parsed.total_net_weight,
            "confidence": parsed.confidence,
            "source": "regex",
            "raw_text": parsed.raw_text,
        }


class HSCodeClassifier:
    """Классификация ТН ВЭД через DSPy + LlamaIndex RAG."""

    def __init__(self):
        self._dspy_module = None
        if _dspy_available:
            self._dspy_module = dspy.Predict(HSCodeSignature)

    def classify(self, description: str, rag_results: list[dict]) -> dict:
        if self._dspy_module and rag_results:
            try:
                rag_text = "\n".join([
                    f"- {r.get('code', '')}: {r.get('name_ru', '')} (score: {r.get('score', 0):.2f})"
                    for r in rag_results
                ])
                result = self._dspy_module(
                    description=description,
                    rag_results=rag_text,
                )
                return {
                    "hs_code": result.hs_code,
                    "name_ru": result.name_ru,
                    "reasoning": result.reasoning,
                    "confidence": _safe_float(result.confidence) or 0.8,
                    "source": "dspy_rag",
                }
            except Exception as e:
                logger.warning("dspy_hs_classify_fallback", error=str(e))

        # GPT-4o direct call (when DSPy unavailable but OpenAI configured)
        try:
            from app.config import get_settings
            settings = get_settings()
            if settings.has_openai and rag_results:
                import openai as _oai
                client = _oai.OpenAI(api_key=settings.OPENAI_API_KEY)
                rag_text = "\n".join([
                    f"- {r.get('code', '')}: {r.get('name_ru', '')} (score: {r.get('score', 0):.2f})"
                    for r in rag_results[:10]
                ])
                resp = client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Ты эксперт по ТН ВЭД ЕАЭС. Выбери точный 10-значный код ТН ВЭД для товара. Ответь ТОЛЬКО в формате JSON: {\"hs_code\":\"XXXXXXXXXX\",\"name_ru\":\"название\",\"reasoning\":\"обоснование\",\"confidence\":0.95}"},
                        {"role": "user", "content": f"Товар: {description}\n\nКандидаты из справочника:\n{rag_text}\n\nВыбери лучший 10-значный код. Если в кандидатах только 4-6 значные, дополни до 10 знаков нулями."},
                    ],
                    temperature=0,
                    max_tokens=300,
                )
                text = resp.choices[0].message.content.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                data = json.loads(text)
                code = data.get("hs_code", "").replace(".", "").replace(" ", "")
                if len(code) < 10:
                    code = code.ljust(10, "0")
                logger.info("hs_classified_by_gpt", code=code, description=description[:50])
                return {
                    "hs_code": code[:10],
                    "name_ru": data.get("name_ru", ""),
                    "reasoning": data.get("reasoning", "GPT-4o classification"),
                    "confidence": float(data.get("confidence", 0.85)),
                    "source": "gpt4o_rag",
                }
        except Exception as e:
            logger.warning("gpt4o_hs_classify_failed", error=str(e))

        # Fallback на keyword classifier
        from app.services.hs_classifier import classify as keyword_classify, _pad_hs_code
        suggestions = keyword_classify(description)
        if suggestions:
            return {
                "hs_code": _pad_hs_code(suggestions[0]["hs_code"]),
                "name_ru": suggestions[0]["name_ru"],
                "reasoning": "Keyword matching (fallback)",
                "confidence": suggestions[0]["confidence"],
                "source": "keyword",
            }
        return {"hs_code": "", "name_ru": "", "reasoning": "No match", "confidence": 0.0, "source": "none"}


class RiskAnalyzer:
    """Анализ рисков через DSPy + LlamaIndex RAG."""

    def __init__(self):
        self._dspy_module = None
        if _dspy_available:
            self._dspy_module = dspy.Predict(RiskSignature)

    def analyze(self, declaration_data: dict, relevant_rules: list[dict]) -> dict:
        if self._dspy_module and relevant_rules:
            try:
                result = self._dspy_module(
                    declaration_data=json.dumps(declaration_data, ensure_ascii=False, default=str),
                    relevant_rules=json.dumps(relevant_rules, ensure_ascii=False),
                )
                risks = _safe_json_parse(result.risks_json, [])
                return {
                    "risk_score": _safe_int(result.risk_score) or 0,
                    "risks": risks,
                    "source": "dspy_rag",
                }
            except Exception as e:
                logger.warning("dspy_risk_fallback", error=str(e))

        # Fallback на rule engine
        from app.services.risk_engine import assess
        items_dict = declaration_data.get("items", [])
        result = assess(
            items=items_dict,
            total_customs_value=declaration_data.get("total_customs_value"),
        )
        return {
            "risk_score": result.overall_risk_score,
            "risks": [r.model_dump() for r in result.risks],
            "source": "rule_engine",
        }


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        s = str(value).replace(",", ".").replace(" ", "").strip()
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(str(value).replace(",", ".").replace(" ", "").strip()))
    except (ValueError, TypeError):
        return None


def _safe_json_parse(text: str, default=None):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


def configure_dspy(openai_api_key: str, model: str = "gpt-4o"):
    """Настроить DSPy для использования OpenAI."""
    if not _dspy_available:
        return
    try:
        lm = dspy.LM(f"openai/{model}", api_key=openai_api_key)
        dspy.configure(lm=lm)
        logger.info("dspy_configured", model=model)
    except Exception as e:
        logger.error("dspy_configure_failed", error=str(e))
