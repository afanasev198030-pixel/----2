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
                "address": parsed.buyer.address if parsed.buyer else None,
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
                    "hs_code": item.hs_code or "",
                    "gross_weight": item.gross_weight,
                    "net_weight": item.net_weight,
                    "country_origin_code": item.country_origin,
                }
                for item in parsed.items
            ],
            "contract_number": parsed.contract_number,
            "country_origin": parsed.country_origin,
            "country_destination": parsed.country_destination,
            "total_gross_weight": parsed.total_gross_weight,
            "total_net_weight": parsed.total_net_weight,
            "total_packages": parsed.total_packages,
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

    # Few-shot примеры для DSPy — улучшают точность классификации
    _HS_DEMOS = None

    @staticmethod
    def _get_demos():
        if not _dspy_available:
            return []
        if HSCodeClassifier._HS_DEMOS is None:
            HSCodeClassifier._HS_DEMOS = [
                dspy.Example(
                    description="Motor 3115 900KV brushless motor for FPV drone",
                    rag_results="- 8501100009: Электродвигатели малой мощности (score: 0.85)",
                    hs_code="8501100009", name_ru="Электродвигатели малой мощности",
                    reasoning="Бесколлекторный мотор для дрона < 37.5W → группа 8501", confidence="0.95",
                ).with_inputs("description", "rag_results"),
                dspy.Example(
                    description="ESC 55A Electronic Speed Controller MR30 version",
                    rag_results="- 8504409000: Преобразователи статические прочие (score: 0.80)",
                    hs_code="8504409000", name_ru="Преобразователи статические прочие",
                    reasoning="ESC = регулятор оборотов = статический преобразователь → 8504", confidence="0.95",
                ).with_inputs("description", "rag_results"),
                dspy.Example(
                    description="Flight Controller FC F405 AIO stack for quadcopter",
                    rag_results="- 8537101009: Пульты, панели и щиты управления (score: 0.78)",
                    hs_code="8537101009", name_ru="Пульты, панели и щиты управления прочие",
                    reasoning="Полётный контроллер = устройство управления → группа 8537", confidence="0.93",
                ).with_inputs("description", "rag_results"),
                dspy.Example(
                    description="Пропеллер 5 дюймов карбоновый для FPV дрона",
                    rag_results="- 8803300000: Части летательных аппаратов (score: 0.70)",
                    hs_code="8803300000", name_ru="Части летательных аппаратов прочие",
                    reasoning="Пропеллер для дрона = часть летательного аппарата → 8803", confidence="0.90",
                ).with_inputs("description", "rag_results"),
                dspy.Example(
                    description="FPV Camera Caddx Ratel 2 1200TVL CMOS sensor",
                    rag_results="- 8525809000: Камеры телевизионные прочие (score: 0.82)",
                    hs_code="8525809000", name_ru="Камеры телевизионные прочие",
                    reasoning="FPV камера = телевизионная камера → 8525", confidence="0.92",
                ).with_inputs("description", "rag_results"),
            ]
        return HSCodeClassifier._HS_DEMOS

    def __init__(self):
        self._dspy_module = None
        if _dspy_available:
            demos = self._get_demos()
            self._dspy_module = dspy.Predict(HSCodeSignature, demos=demos)

    def classify(self, description: str, rag_results: list[dict], context: str = "") -> dict:
        rag_text = ""
        if rag_results:
            rag_text = "\n".join([
                f"- {r.get('code', '')}: {r.get('name_ru', '')} (score: {r.get('score', 0):.2f})"
                for r in rag_results[:10]
            ])

        # DSPy path (needs rag candidates)
        if self._dspy_module and rag_text:
            try:
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

        # LLM direct call (works even without RAG candidates)
        try:
            from app.config import get_settings
            settings = get_settings()
            if settings.has_llm:
                from app.services.llm_client import get_llm_client, get_model
                llm = get_llm_client()
                context_block = f"\n\nКонтекст декларации (другие позиции):\n{context}" if context else ""
                if rag_text:
                    user_msg = f"Товар: {description}{context_block}\n\nКандидаты из справочника:\n{rag_text}\n\nВыбери лучший 10-значный код. Если в кандидатах только 4-6 значные, дополни до 10 знаков нулями."
                else:
                    user_msg = f"Товар: {description}{context_block}\n\nОпредели 10-значный код ТН ВЭД ЕАЭС для этого товара. Учитывай материал, назначение и страну происхождения."
                resp = llm.chat.completions.create(
                    model=get_model(),
                    messages=[
                        {"role": "system", "content": "Ты эксперт по ТН ВЭД ЕАЭС. Определи точный 10-значный код ТН ВЭД для товара. Ответь ТОЛЬКО в формате JSON: {\"hs_code\":\"XXXXXXXXXX\",\"name_ru\":\"название по-русски\",\"reasoning\":\"обоснование\",\"confidence\":0.95}\n\nРаспространённые аббревиатуры электроники (НЕ путать с сельхозпродукцией):\n- ESC = Electronic Speed Controller (регулятор оборотов, группа 8504/8537)\n- FC = Flight Controller (полётный контроллер, группа 8537/8543)\n- VTX = Video Transmitter (видеопередатчик, группа 8525)\n- PDB = Power Distribution Board (плата распределения питания, группа 8536)\n- BEC = Battery Eliminator Circuit (стабилизатор напряжения, группа 8504)\n- FPV = First Person View (видеосистема для дронов, группа 8525/8528)"},
                        {"role": "user", "content": user_msg},
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
                source = "llm_rag" if rag_text else "llm_direct"
                logger.info("hs_classified_by_llm", code=code, description=description[:50], model=get_model(), source=source)
                return {
                    "hs_code": code[:10],
                    "name_ru": data.get("name_ru", ""),
                    "reasoning": data.get("reasoning", f"LLM classification ({get_model()})"),
                    "confidence": float(data.get("confidence", 0.85)),
                    "source": source,
                }
        except Exception as e:
            logger.warning("llm_hs_classify_failed", error=str(e))

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


def configure_dspy(api_key: str = None, model: str = None, base_url: str = None):
    """Настроить DSPy для использования LLM (DeepSeek, OpenAI, etc.)."""
    if not _dspy_available:
        return
    try:
        from app.config import get_settings
        settings = get_settings()
        key = api_key or settings.effective_api_key
        mdl = model or settings.effective_model
        url = base_url or settings.effective_base_url

        lm = dspy.LM(f"openai/{mdl}", api_key=key, api_base=url)
        dspy.configure(lm=lm)
        logger.info("dspy_configured", model=mdl, provider=settings.LLM_PROVIDER, base_url=url)
    except Exception as e:
        logger.error("dspy_configure_failed", error=str(e))
