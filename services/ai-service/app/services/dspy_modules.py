"""
DSPy модули для автооптимизации промптов парсинга и классификации.
Заменяет ручной prompt engineering.
Fallback на regex-парсеры при недоступности OpenAI.
"""
import json
import re
from typing import Optional
import structlog

logger = structlog.get_logger()

# Лог классификации ТН ВЭД — in-memory ring buffer для дебаг-панели
_hs_classify_log: list[dict] = []
_HS_LOG_MAX = 50

def _log_classify(entry: dict):
    import time
    entry["ts"] = time.time()
    _hs_classify_log.append(entry)
    if len(_hs_classify_log) > _HS_LOG_MAX:
        _hs_classify_log.pop(0)

def get_hs_classify_log() -> list[dict]:
    return list(_hs_classify_log)


def _contains_any(text: str, words: list[str]) -> bool:
    t = f" {text.lower()} "
    for w in words:
        if f" {w.lower()} " in t or w.lower() in t:
            return True
    return False


def _detect_drone_product_kind(description: str) -> str:
    """
    Determine if description is:
    - complete_drone: ready UAV/quadcopter
    - component: electronics/mechanical part for drone
    - fpv_ambiguous: contains FPV but unclear
    - generic
    """
    text = (description or "").lower()
    if not text:
        return "generic"

    complete_drone_words = [
        "quadcopter", "квадрокоптер", "drone", "дрон", "uav", "бпла", "мультикоптер",
        "multicopter", "whoop", "cinewhoop", "fpv drone", "fpv quad", "racing drone",
    ]
    component_words = [
        "vtx", "video transmitter", "esc", "flight controller", "fc ", "fcf", "f4", "f7", "h7",
        "motor", "brushless", "antenna", "receiver", "camera", "propeller", "frame", "gimbal",
        "pdb", "bec", "gps module", "stack", "регулятор", "контроллер", "мотор", "антенн",
        "камера", "пропеллер", "рама", "передатчик", "приемник", "приёмник",
    ]

    has_complete = _contains_any(text, complete_drone_words)
    has_component = _contains_any(text, component_words)
    has_fpv = "fpv" in text

    if has_complete and not has_component:
        return "complete_drone"
    if has_component:
        return "component"
    if has_fpv:
        return "fpv_ambiguous"
    return "generic"


def _normalize_hs_code(raw: str, strict: bool = False) -> str:
    """Normalize HS code to exactly 10 digits. Min 6 digits input required."""
    code = re.sub(r"\D", "", str(raw or ""))
    if len(code) < 6:
        return ""
    if len(code) < 10:
        code = code.ljust(10, "0")
    else:
        code = code[:10]
    # Always validate group (01-97)
    try:
        first2 = int(code[:2])
        if first2 < 1 or first2 > 97:
            return ""
    except ValueError:
        return ""
    return code


def _build_candidates(selected: Optional[dict], rag_results: list[dict], keyword_suggestions: list[dict]) -> list[dict]:
    """
    Build de-duplicated candidate list:
    1) selected decision
    2) RAG top hits
    3) keyword fallback hints
    """
    merged: list[dict] = []
    if selected:
        code = _normalize_hs_code(selected.get("hs_code", ""), strict=True)
        if code:
            merged.append({
                "hs_code": code,
                "name_ru": selected.get("name_ru", ""),
                "confidence": float(selected.get("confidence", 0.0) or 0.0),
                "source": selected.get("source", "selected"),
            })

    for r in rag_results[:8]:
        code = _normalize_hs_code(r.get("code", ""), strict=False)
        if not code:
            continue
        conf = r.get("score", 0.0)
        try:
            conf_val = float(conf)
        except (ValueError, TypeError):
            conf_val = 0.0
        merged.append({
            "hs_code": code,
            "name_ru": r.get("name_ru", "") or "",
            "confidence": max(0.0, min(1.0, conf_val)),
            "source": "rag",
        })

    for s in keyword_suggestions[:5]:
        code = _normalize_hs_code(s.get("hs_code", ""), strict=True)
        if not code:
            continue
        merged.append({
            "hs_code": code,
            "name_ru": s.get("name_ru", "") or "",
            "confidence": float(s.get("confidence", 0.0) or 0.0),
            "source": "keyword",
        })

    by_code: dict[str, dict] = {}
    for c in merged:
        hs = c["hs_code"]
        if hs not in by_code or c.get("confidence", 0) > by_code[hs].get("confidence", 0):
            by_code[hs] = c
    result = list(by_code.values())
    result.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return result[:8]


_dspy_available = False
_dspy_auth_failed = False
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
        """Извлечь данные из инвойса. DSPy → regex fallback."""
        text = extract_text(file_bytes, filename)
        if not text:
            logger.warning("invoice_no_text", filename=filename)
            return {"error": "no_text_extracted", "confidence": 0.0}

        # Regex + LLM enrichment (more reliable than DSPy for invoices)
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

        # Regex parser (contracts are batch-parsed by LLM in agent_crew, DSPy skipped)
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

        if False:  # DSPy disabled for packing — LLM packing parser is more reliable
            try:
                result = self._dspy_module(document_text=text[:8000])
                gross = _safe_float(result.total_gross_weight)
                net = _safe_float(result.total_net_weight)
                pkgs = _safe_int(result.total_packages)
                return {
                    "total_packages": pkgs,
                    "package_type": result.package_type,
                    "total_gross_weight": gross,
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
            "items": parsed.items,   # per-item weights for graphs 35/38
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
            module = dspy.Predict(HSCodeSignature)
            if demos:
                from dspy.teleprompt import LabeledFewShot
                optimizer = LabeledFewShot(k=len(demos))
                self._dspy_module = optimizer.compile(module, trainset=demos)
            else:
                self._dspy_module = module

    def classify(self, description: str, rag_results: list[dict], context: str = "") -> dict:
        from app.services.hs_classifier import classify as keyword_classify, _pad_hs_code
        keyword_suggestions = keyword_classify(description)

        def with_candidates(result_obj: dict) -> dict:
            selected = {
                "hs_code": result_obj.get("hs_code", ""),
                "name_ru": result_obj.get("name_ru", ""),
                "confidence": result_obj.get("confidence", 0.0),
                "source": result_obj.get("source", ""),
            }
            result_obj["candidates"] = _build_candidates(selected, rag_results or [], keyword_suggestions or [])
            return result_obj

        # ── Прецеденты: мгновенный ответ если есть точное совпадение ──
        try:
            from app.services.index_manager import get_index_manager
            idx = get_index_manager()
            precedents = idx.search_precedents(description, top_k=3)
            if precedents:
                best = precedents[0]
                score = best.get("score", 0)
                hs_code = _normalize_hs_code(best.get("metadata", {}).get("hs_code", ""), strict=True)
                if score > 0.9 and hs_code:
                    _log_classify({"description": description[:80], "method": "precedent", "hs_code": hs_code, "confidence": str(round(score, 2)), "reasoning": f"Прецедент (score={score:.2f})"})
                    logger.info("hs_from_precedent", description=description[:50], hs_code=hs_code, score=score)
                    return with_candidates({
                        "hs_code": hs_code[:10],
                        "name_ru": best.get("metadata", {}).get("description", "")[:100],
                        "reasoning": f"Прецедент из предыдущих деклараций (score={score:.2f})",
                        "confidence": min(0.98, score),
                        "source": "precedent",
                    })
        except Exception as e:
            logger.debug("precedent_search_skip", error=str(e)[:80])

        # ── Жёсткая эвристика: БПЛА и компоненты с известными кодами ──
        drone_kind = _detect_drone_product_kind(description)

        # Таблица эвристик для компонентов БПЛА/FPV
        # Коды верифицированы по ТН ВЭД ЕАЭС 2024
        _COMPONENT_HS_RULES = [
            # VTX — видеопередатчик (8525 60 — передающая аппаратура с встроенным приёмником)
            (["vtx", "video transmitter", "видеопередатчик", "передатчик видео", "5.8g transmitter"],
             "8525601000", "Аппаратура передающая с встроенным приёмным устройством (VTX)", 0.93),
            # ESC — регулятор оборотов (8504 40 — преобразователи статические)
            (["esc ", "esc-", "speed controller", "регулятор оборотов", "регулятор хода", "blheli", "simonk"],
             "8504409000", "Преобразователи статические прочие (ESC регулятор)", 0.93),
            # FC — полётный контроллер (8537 10 — пульты/панели управления ≤1000В)
            (["flight controller", "полетный контролер", "полётный контроллер", "fc f4", "fc f7", "fc h7",
              "aio stack", " fc ", "betaflight", "inav", "matek", "speedybee", "kakute"],
             "8537109100", "Пульты, панели и щиты управления прочие (FC контроллер)", 0.92),
            # Мотор бесколлекторный (8501 31 — DC моторы ≤750Вт, FPV моторы 100-600Вт)
            (["brushless motor", "bldc", "motor kv", "мотор kv", "350kv", "900kv", "1400kv", "2400kv", "2800kv",
              "motor 23", "motor 28", "motor 43", "motor 51"],
             "8501310000", "Электродвигатели постоянного тока мощностью ≤750 Вт", 0.93),
            # Камера FPV (8525 80 — камеры телевизионные прочие)
            (["fpv camera", "caddx", "runcam", "foxeer", "камера fpv", "tvl", "1200tvl", "cmos sensor"],
             "8525809000", "Камеры телевизионные прочие (FPV камера)", 0.92),
            # Пропеллер (8803 30 — части летательных аппаратов прочие)
            (["propeller", "пропеллер", "prop ", "hq prop", "gemfan", "2cw", "2ccw", "nazgul"],
             "8803300000", "Части летательных аппаратов прочие (пропеллер)", 0.91),
            # Рама дрона (8806 90 — части БПЛА)
            (["frame", "рама ", "frame kit", "drone frame", "рама дрон"],
             "8806909000", "Части БПЛА прочие (рама)", 0.91),
            # АКБ LiPo (8507 60 — аккумуляторы литий-ионные)
            (["lipo", "li-po", "аккумулятор lipo", "battery lipo", "battery pack", "mah ", "22000mah", "6s lipo", "4s lipo"],
             "8507600000", "Аккумуляторы литий-ионные (LiPo)", 0.93),
            # Антенна FPV/VTX (8517 71 — антенны для приёмо-передачи данных)
            (["antenna", "антенна", "lhcp", "rhcp", "sma connector", "pagoda", "клевер", "clover", "5.8g antenna"],
             "8517711900", "Антенны для приёмо-передачи данных (VTX, FPV, 5.8G)", 0.92),
            # Разъемы, коннекторы (8536 69 - штепсели и розетки)
            (["connector", "коннектор", "разъем", "разъём", "plug", "socket", "pin ", "pin connector"],
             "8536699008", "Штепсели и розетки", 0.85),
            # Приёмник (8526 92 — аппаратура дистанционного управления)
            (["receiver", "приемник", "приёмник", "elrs", "crossfire", "rxsr", "flysky", "frsky", "radiolink"],
             "8526920000", "Аппаратура дистанционного управления (приёмник RC)", 0.92),
        ]

        if drone_kind == "complete_drone":
            _log_classify({"description": description[:80], "method": "rule_complete_drone", "hs_code": "8806100000", "confidence": 0.9})
            return with_candidates({
                "hs_code": "8806100000",
                "name_ru": "Беспилотные летательные аппараты (БПЛА, дроны)",
                "reasoning": "Эвристика: готовый FPV/квадрокоптер (без признаков отдельного компонента)",
                "confidence": 0.9,
                "source": "rule_complete_drone",
            })

        if drone_kind == "component":
            desc_lower = description.lower()
            for keywords, hs_code, name_ru, conf in _COMPONENT_HS_RULES:
                if any(kw in desc_lower for kw in keywords):
                    logger.info("hs_component_rule", description=description[:60], hs_code=hs_code, keywords=[k for k in keywords if k in desc_lower])
                    _log_classify({"description": description[:80], "method": "rule_component", "hs_code": hs_code, "name_ru": name_ru, "confidence": conf})
                    return with_candidates({
                        "hs_code": hs_code,
                        "name_ru": name_ru,
                        "reasoning": f"Эвристика: компонент БПЛА ({name_ru})",
                        "confidence": conf,
                        "source": "rule_component",
                    })

        rag_text = ""
        if rag_results:
            rag_text = "\n".join([
                f"- {r.get('code', '')}: {r.get('name_ru', '')} (score: {r.get('score', 0):.2f})"
                for r in rag_results[:10]
            ])

        # DSPy path (needs rag candidates; skip if auth previously failed)
        global _dspy_auth_failed
        if self._dspy_module and rag_text and not _dspy_auth_failed:
            try:
                from app.services.usage_tracker import set_usage_context, reset_usage_context
                ctx_tokens = set_usage_context(operation="hs_classify_dspy")
                try:
                    dspy_result = self._dspy_module(
                        description=description,
                        rag_results=rag_text,
                    )
                finally:
                    reset_usage_context(ctx_tokens)
                code = _normalize_hs_code(dspy_result.hs_code, strict=True)
                conf = _safe_float(dspy_result.confidence) or 0.8
                if not code:
                    logger.warning("dspy_invalid_hs_code", raw=str(dspy_result.hs_code)[:40], description=description[:80])
                else:
                    chosen = {
                        "hs_code": code,
                        "name_ru": dspy_result.name_ru,
                        "reasoning": dspy_result.reasoning,
                        "confidence": conf,
                        "source": "dspy_rag",
                    }
                    _log_classify({
                        "description": description[:80],
                        "method": "dspy_rag",
                        "hs_code": chosen["hs_code"],
                        "name_ru": chosen["name_ru"],
                        "reasoning": chosen["reasoning"],
                        "confidence": str(chosen["confidence"]),
                        "rag_candidates": len(rag_results),
                        "context": context[:120] if context else "",
                        "decision_path": "dspy_rag",
                    })
                    return with_candidates(chosen)
            except Exception as e:
                err_str = str(e)
                logger.warning("dspy_hs_classify_fallback", error=err_str)
                if "Authentication Fails" in err_str or "api key" in err_str.lower():
                    _dspy_auth_failed = True
                    logger.warning("dspy_auth_disabled", msg="DSPy disabled due to auth failure, using LLM direct")

        # LLM direct call (works even without RAG candidates)
        try:
            from app.config import get_settings
            settings = get_settings()
            if settings.has_llm:
                from app.services.llm_client import get_llm_client, get_model
                llm = get_llm_client(operation="hs_classify_llm")
                context_block = f"\n\nКонтекст декларации (другие позиции):\n{context}" if context else ""
                kind_hint = {
                    "component": "Тип товара: компонент БПЛА/FPV (электронный модуль или часть).",
                    "fpv_ambiguous": "Тип товара: встречается FPV, но неясно — готовый БПЛА или компонент; выбирай консервативно и снижай confidence.",
                    "generic": "Тип товара: общий случай, классифицируй по назначению/материалу.",
                }.get(drone_kind, "Тип товара: общий случай.")
                if rag_text:
                    user_msg = (
                        f"Товар: {description}{context_block}\n\n{kind_hint}\n\n"
                        f"Кандидаты из справочника:\n{rag_text}\n\n"
                        "Выбери лучший 10-значный код. Если в кандидатах только 4-6 значные, дополни до 10 знаков нулями."
                    )
                else:
                    user_msg = (
                        f"Товар: {description}{context_block}\n\n{kind_hint}\n\n"
                        "Определи 10-значный код ТН ВЭД ЕАЭС для этого товара. Учитывай материал, назначение и страну происхождения."
                    )
                system_prompt = (
                    "Ты эксперт по ТН ВЭД ЕАЭС. Ответь ТОЛЬКО JSON: "
                    "{\"hs_code\":\"XXXXXXXXXX\",\"name_ru\":\"название\",\"reasoning\":\"обоснование\",\"confidence\":0.95}\n\n"
                    "Правила по товарам FPV/БПЛА:\n"
                    "1) Готовый летательный аппарат (drone/quadcopter/UAV/БПЛА) -> группа 8806.\n"
                    "2) Отдельные компоненты (VTX, ESC, FC, камера, мотор, антенна, приемник, PDB, BEC) -> НЕ 8806, а профильные группы 8501-8543/8517/8525.\n"
                    "3) Если описание неоднозначно (есть только 'FPV' без явного типа) — снижай confidence и указывай, что требуется ручная проверка."
                )
                resp = llm.chat.completions.create(
                    model=get_model(),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0,
                    max_tokens=300,
                    response_format={"type": "json_object"},
                )
                text = resp.choices[0].message.content.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                data = json.loads(text)
                code = _normalize_hs_code(data.get("hs_code", ""), strict=True)
                if not code:
                    raise ValueError(f"invalid_hs_code_from_llm: {str(data.get('hs_code', ''))[:30]}")
                source = "llm_rag" if rag_text else "llm_direct"

                # ── Этап 2: уточнение до точного 10-значного кода ──
                refined = _refine_hs_code(llm, code[:6], description, get_model())
                if refined:
                    code = refined["code"]
                    data["name_ru"] = refined.get("name_ru") or data.get("name_ru", "")
                    data["reasoning"] = (data.get("reasoning", "") + f" → уточнён до {code}").strip()
                    source = source + "_refined"

                # FPV-товары часто неоднозначны по описанию — не показываем излишнюю уверенность
                if "fpv" in (description or "").lower() and drone_kind != "complete_drone":
                    try:
                        data_conf = float(data.get("confidence", 0.85))
                    except (ValueError, TypeError):
                        data_conf = 0.85
                    if data_conf > 0.8:
                        data["confidence"] = 0.8
                    data["reasoning"] = (data.get("reasoning", "") + " | FPV-товар: проверьте код вручную перед выпуском.").strip()

                logger.info("hs_classified_by_llm", code=code, description=description[:50], model=get_model(), source=source)
                confidence_value = float(data.get("confidence", 0.85))
                _log_classify({
                    "description": description[:80],
                    "method": source,
                    "model": get_model(),
                    "prompt_system": system_prompt[:2000],
                    "prompt_user": user_msg[:2000],
                    "hs_code": code[:10],
                    "name_ru": data.get("name_ru", ""),
                    "reasoning": data.get("reasoning", ""),
                    "confidence": confidence_value,
                    "rag_candidates": len(rag_results),
                    "context": context[:120] if context else "",
                    "decision_path": source,
                })
                return with_candidates({
                    "hs_code": code[:10],
                    "name_ru": data.get("name_ru", ""),
                    "reasoning": data.get("reasoning", f"LLM classification ({get_model()})"),
                    "confidence": confidence_value,
                    "source": source,
                })
        except Exception as e:
            logger.warning("llm_hs_classify_failed", error=str(e))

        # Fallback на keyword classifier
        # Фильтруем коды с 6+ нулями на конце — они являются только заголовком раздела
        # (4-значный код, дополненный нулями), не пригодны как конкретный код ТН ВЭД
        valid_keyword_suggestions = [
            s for s in (keyword_suggestions or [])
            if not _pad_hs_code(s["hs_code"]).endswith("000000")
        ]
        if valid_keyword_suggestions:
            chosen = {
                "hs_code": _pad_hs_code(valid_keyword_suggestions[0]["hs_code"]),
                "name_ru": valid_keyword_suggestions[0]["name_ru"],
                "reasoning": "Keyword matching (fallback)",
                "confidence": valid_keyword_suggestions[0]["confidence"],
                "source": "keyword",
            }
            _log_classify({
                "description": description[:80],
                "method": "keyword",
                "hs_code": chosen["hs_code"],
                "name_ru": chosen["name_ru"],
                "reasoning": chosen["reasoning"],
                "confidence": chosen["confidence"],
                "decision_path": "keyword_fallback",
            })
            return with_candidates(chosen)
        _log_classify({"description": description[:80], "method": "none", "hs_code": "", "name_ru": "", "reasoning": "All methods failed"})
        try:
            from app.services.issue_reporter import report_issue
            report_issue("hs_classify", "error", f"All classify methods failed for: {description[:80]}",
                {"description": description[:200], "rag_candidates": len(rag_results), "context": context[:100] if context else ""})
        except Exception:
            pass
        return with_candidates({"hs_code": "", "name_ru": "", "reasoning": "No match", "confidence": 0.0, "source": "none"})


class RiskAnalyzer:
    """Анализ рисков через DSPy + LlamaIndex RAG."""

    def __init__(self):
        self._dspy_module = None
        if _dspy_available:
            self._dspy_module = dspy.Predict(RiskSignature)

    def analyze(self, declaration_data: dict, relevant_rules: list[dict]) -> dict:
        if self._dspy_module and relevant_rules and not _dspy_auth_failed:
            try:
                from app.services.usage_tracker import set_usage_context, reset_usage_context
                ctx_tokens = set_usage_context(operation="risk_analyze_dspy")
                try:
                    result = self._dspy_module(
                        declaration_data=json.dumps(declaration_data, ensure_ascii=False, default=str),
                        relevant_rules=json.dumps(relevant_rules, ensure_ascii=False),
                    )
                finally:
                    reset_usage_context(ctx_tokens)
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


def _refine_hs_code(llm_client, prefix_6: str, description: str, model: str) -> Optional[dict]:
    """Этап 2: уточнить 6-значный код до точного 10-значного из справочника."""
    if not prefix_6 or len(prefix_6) < 4:
        return None
    try:
        import httpx
        # Запрос подкодов из core-api (без auth — internal)
        resp = httpx.get(
            "http://core-api:8001/api/v1/classifiers/subcodes",
            params={"prefix": prefix_6[:6], "classifier_type": "hs_code"},
            timeout=5,
        )
        if resp.status_code != 200:
            return None
        subcodes = resp.json()
        if not subcodes or len(subcodes) < 2:
            return None

        # Формируем список для LLM
        options = "\n".join([f"- {c['code']}: {c['name_ru']}" for c in subcodes[:20]])

        refine_resp = llm_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Выбери ТОЧНЫЙ 10-значный код ТН ВЭД из списка. Ответь ТОЛЬКО JSON: {\"code\":\"XXXXXXXXXX\",\"name_ru\":\"название\"}"},
                {"role": "user", "content": f"Товар: {description}\n\nВарианты:\n{options}\n\nКакой код точнее всего?"},
            ],
            temperature=0,
            max_tokens=150,
        )
        text = refine_resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        code = (data.get("code") or "").replace(".", "").replace(" ", "")
        if code and len(code) == 10:
            logger.info("hs_refined", prefix=prefix_6, refined=code, description=description[:40])
            return {"code": code, "name_ru": data.get("name_ru", "")}
    except Exception as e:
        logger.debug("hs_refine_skip", error=str(e)[:80])
    return None


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

        from app.services.usage_tracker import DSPYUsageBridge

        lm = dspy.LM(f"openai/{mdl}", api_key=key, api_base=url)
        dspy.configure(lm=lm, usage_tracker=DSPYUsageBridge())
        logger.info("dspy_configured", model=mdl, provider=settings.LLM_PROVIDER, base_url=url)
    except Exception as e:
        logger.error("dspy_configure_failed", error=str(e))
