"""
CrewAI мультиагентная оркестрация.
Агенты: DocumentParser, HSClassifier, RiskAnalyzer, PrecedentLearner.
Fallback на линейный pipeline при недоступности CrewAI/OpenAI.
"""
import json
import re
from typing import Optional
import structlog

from app.services.llm_json import strip_code_fences

logger = structlog.get_logger()

_crewai_available = False
try:
    from crewai import Agent, Task, Crew, Process
    _crewai_available = True
    logger.info("crewai_available", msg="CrewAI dependency loaded")
except ImportError:
    logger.warning("crewai_not_available", msg="CrewAI not installed")

from app.services.dspy_modules import (
    InvoiceExtractor, ContractExtractor, PackingExtractor,
    HSCodeClassifier, RiskAnalyzer,
)
from app.services.index_manager import get_index_manager
from app.services.ocr_service import extract_text
from app.services.invoice_parser import _is_garbage_desc
from app.services.rules_engine import (
    EvidenceTracker, validate_declaration,
    build_graph_rules_prompt, get_source_priority_map,
    build_full_rules_for_llm, build_strategies_prompt,
)
from app.services.escalation_agents import ReconciliationAgent, ReviewerAgent


def _classify_invoice_content(text: str, filename: str = "") -> str:
    """
    Определяет тип инвойса по содержанию документа с балльной системой.

    Читает текст и подсчитывает сигналы двух категорий:
      - транспортные сигналы: фрахт, перевозка, airline, surcharge, AWB и т.д.
      - товарные сигналы: описание товаров, ТН ВЭД, кол-во, цена за единицу и т.д.

    Возвращает:
      "transport_invoice" — если транспортные сигналы значительно преобладают
      "invoice"           — если товарные сигналы преобладают или ничья
    """
    t = (text[:6000].lower()) if text else ""
    fn = filename.lower()

    # ── Транспортные сигналы (фраза → вес) ─────────────────────────────────
    _TRANSPORT: list[tuple[str, float]] = [
        # Очень сильные — прямое название транспортных услуг
        ("air freight charge",      12.0),
        ("air freight",             10.0),
        ("ocean freight",           10.0),
        ("sea freight",             10.0),
        ("freight charge",          9.0),
        ("freight cost",            9.0),
        ("airway bill",             9.0),
        ("air waybill",             9.0),
        ("авиафрахт",               10.0),
        ("стоимость перевозки",     9.0),
        ("за перевозку",            9.0),
        ("транспортные услуги",     9.0),
        ("транспортные расходы",    8.0),
        ("фрахт",                   9.0),
        # Средние — характерны для транспортных инвойсов
        ("handling charge",         7.0),
        ("fuel surcharge",          8.0),
        ("security surcharge",      7.0),
        ("terminal handling",       7.0),
        ("documentation fee",       6.0),
        ("customs clearance fee",   6.0),
        ("доставка груза",          7.0),
        ("перевозка груза",         8.0),
        ("airline",                 5.0),
        ("carrier",                 5.0),
        ("freight forwarder",       6.0),
        ("экспедитор",              5.0),
        ("перевозчик",              5.0),
        ("flight no",               6.0),
        ("flight number",           6.0),
        ("номер рейса",             6.0),
        ("surcharge",               4.0),
        ("shipping company",        4.0),
    ]

    # ── Товарные сигналы (фраза → вес) ──────────────────────────────────────
    _GOODS: list[tuple[str, float]] = [
        # Очень сильные — прямое описание товаров
        ("description of goods",    10.0),
        ("наименование товара",     10.0),
        ("goods description",       9.0),
        ("commodity description",   9.0),
        ("hs code",                 9.0),
        ("hs-code",                 9.0),
        ("тн вэд",                  9.0),
        ("country of origin",       7.0),
        ("страна происхождения",    7.0),
        ("unit price",              8.0),
        ("цена за единицу",         8.0),
        ("цена за шт",              7.0),
        # Средние — характерны для товарного инвойса
        ("quantity",                5.0),
        ("кол-во",                  5.0),
        ("количество",              4.0),
        ("pcs",                     4.0),
        ("pieces",                  4.0),
        ("шт",                      3.0),
        ("net weight",              4.0),
        ("gross weight",            4.0),
        ("incoterms",               5.0),
        ("инкотермс",               5.0),
        ("part number",             4.0),
        ("артикул",                 4.0),
        ("model",                   3.0),
        ("item no",                 4.0),
    ]

    transport_score: float = sum(w for kw, w in _TRANSPORT if kw in t)
    goods_score: float = sum(w for kw, w in _GOODS if kw in t)

    # AWB-номер по паттерну NNN-NNNNNNN в тексте — очень сильный транспортный сигнал
    if re.search(r'\b\d{3}[-]\d{7,8}\b', t):
        transport_score += 8.0
    # AWB-паттерн в начале имени файла
    fn_stripped = re.sub(r'\.(pdf|jpg|jpeg|png|tif|tiff)$', '', fn).strip()
    if re.search(r'^\d{3}[-_ ]?\d{7,8}', fn_stripped):
        transport_score += 10.0

    logger.debug(
        "invoice_content_score",
        filename=filename,
        transport_score=round(transport_score, 1),
        goods_score=round(goods_score, 1),
        decision="transport_invoice" if (
            transport_score >= 15
            or transport_score > goods_score
        ) else "invoice",
    )

    # Транспортный: балл ≥ 15 ИЛИ превышает товарный
    if transport_score >= 15 or transport_score > goods_score:
        return "transport_invoice"
    return "invoice"


def _detect_doc_type(filename: str, text: str) -> str:
    """Определить тип документа по имени файла и содержимому."""
    fn_lower = filename.lower()
    text_lower = (text[:3000].lower()) if text else ""

    if fn_lower.endswith(('.xlsx', '.xls')):
        return "packing_list"

    # Combined INV+PL
    if ("inv" in fn_lower and "pl" in fn_lower) or ("инвойс" in fn_lower and "упаков" in fn_lower):
        return "invoice"

    # --- Эталонная ГТД (reference GTD) ---
    if any(k in fn_lower for k in ["gtd", "гтд", "декларация на товары"]):
        return "reference_gtd"
    if re.search(r'\d{8}[_\-]\d{6}[_\-]\d{7}', fn_lower):
        return "reference_gtd"

    # --- Документ СВХ (склад временного хранения) ---
    if any(k in fn_lower for k in ["cbx", "свх", "свх_", "warehouse"]):
        return "svh_doc"

    # --- По имени файла: однозначные типы ---
    if any(k in fn_lower for k in ["contract", "договор", "контракт"]):
        return "contract"
    if any(k in fn_lower for k in ["packing", "упаков", "packing_list", "packing-list"]):
        return "packing_list"
    if re.search(r'\bpl\b', fn_lower) and "inv" not in fn_lower:
        return "packing_list"
    if any(k in fn_lower for k in ["awb", "waybill", "накладная", "cmr"]):
        return "transport_doc"
    if any(k in fn_lower for k in ["application", "заявка"]):
        return "application_statement"
    if any(k in fn_lower for k in ["spec", "спец"]):
        return "specification"
    if any(k in fn_lower for k in ["teh", "тех"]):
        return "tech_description"

    # --- Платёжное поручение (ПП) — до инвойса, чтобы не спутать ---
    if any(k in fn_lower for k in ["пп", "платеж", "платёж", "payment order"]):
        return "payment_order"
    if any(k in text_lower for k in [
        "платежное поручение", "платёжное поручение", "заявление на перевод",
        "payment order", "просим списать с", "банк получателя",
    ]):
        return "payment_order"

    # --- Транспортный инвойс по имени файла (раньше чем обычный invoice) ---
    _transport_invoice_name = any(k in fn_lower for k in [
        "invoice for transport", "transport invoice", "freight invoice",
        "инвойс за перевозку", "транспортный инвойс", "инвойс за фрахт",
    ])
    if _transport_invoice_name:
        return "transport_invoice"

    # --- Если это инвойс (по имени или содержимому) —
    #     используем балльную систему по содержанию ---
    is_invoice_by_name = any(k in fn_lower for k in [
        "invoice", "инвойс", "счёт", "счет", "inv-", "inv_",
    ])
    is_invoice_by_content = (
        ("invoice" in text_lower or "инвойс" in text_lower or "счёт" in text_lower)
        and ("total" in text_lower or "amount" in text_lower or "итого" in text_lower)
    )

    if is_invoice_by_name or is_invoice_by_content:
        return _classify_invoice_content(text, filename)

    # --- По содержимому (файлы без очевидного имени) ---

    # AWB по паттерну NNN-NNNNNNNN в имени
    fn_stripped = re.sub(r'\.(pdf|jpg|jpeg|png|tif|tiff)$', '', fn_lower).strip()
    if re.search(r'^\d{3}[-_ ]?\d{7,8}', fn_stripped):
        return "transport_doc"
    if "air waybill" in text_lower or re.search(r'\bawb\b', text_lower):
        return "transport_doc"

    # Контракт
    if any(k in text_lower for k in [
        "contract №", "contract no", "договор №", "контракт №",
        "предмет договора", "subject of contract",
    ]):
        return "contract"

    # Спецификация
    if any(k in text_lower for k in [
        "specification", "спецификация",
        "приложение к контракту", "приложение к договору",
    ]):
        return "specification"
    if any(k in text_lower for k in ["наименование товара", "кол-во", "цена за ед", "unit price"]) \
            and "total" in text_lower:
        return "specification"

    # Техописание
    if any(k in text_lower for k in [
        "технические характеристики", "техническое описание", "назначение изделия",
        "область применения", "technical specifications", "operating temperature",
        "рабочее напряжение", "материал корпуса", "габаритные размеры",
    ]):
        return "tech_description"

    # Packing list
    if "packing list" in text_lower or "gross weight" in text_lower:
        return "packing_list"

    # Заявка / Application (forwarding order / transport order)
    if any(k in text_lower for k in ["forwarding agent", "forwarding order", "заявка на перевозку",
                                      "заявка на экспедирование", "отправитель груза", "shipper details"]):
        return "application_statement"

    # Эталонная ГТД (по содержимому)
    if any(k in text_lower for k in [
        "декларация на товары", "грузовая таможенная",
        "графа 31", "графа 33", "графа 44",
    ]) and re.search(r'\d{8}/\d{6}/\d{7}', text_lower):
        return "reference_gtd"

    # Документ СВХ (по содержимому)
    if any(k in text_lower for k in [
        "склад временного хранения", "свидетельство о включении в реестр",
        "документ о принятии на хранение", "отчёт о принятии на хранение",
        "отчет о принятии на хранение", "до-1", "до1",
    ]):
        return "svh_doc"

    return "other"


def _detect_doc_type_debug(filename: str, text: str) -> dict:
    """Determine document type with debug info: reason, matched keywords, scores."""
    fn_lower = filename.lower()
    text_lower = (text[:3000].lower()) if text else ""

    def _result(doc_type: str, reason: str, scores: dict | None = None) -> dict:
        return {"detected": doc_type, "reason": reason, "scores": scores}

    if fn_lower.endswith(('.xlsx', '.xls')):
        return _result("packing_list", "file_extension: xlsx/xls")

    if ("inv" in fn_lower and "pl" in fn_lower) or ("инвойс" in fn_lower and "упаков" in fn_lower):
        return _result("invoice", "filename_combined: inv+pl")

    if any(k in fn_lower for k in ["gtd", "гтд", "декларация на товары"]):
        return _result("reference_gtd", f"filename_keyword: {[k for k in ['gtd','гтд','декларация на товары'] if k in fn_lower]}")
    if re.search(r'\d{8}[_\-]\d{6}[_\-]\d{7}', fn_lower):
        return _result("reference_gtd", "filename_pattern: GTD number")

    if any(k in fn_lower for k in ["cbx", "свх", "свх_", "warehouse"]):
        return _result("svh_doc", f"filename_keyword: {[k for k in ['cbx','свх','warehouse'] if k in fn_lower]}")

    _fn_checks = [
        (["contract", "договор", "контракт"], "contract"),
        (["packing", "упаков", "packing_list", "packing-list"], "packing_list"),
        (["awb", "waybill", "накладная", "cmr"], "transport_doc"),
        (["application", "заявка"], "application_statement"),
        (["spec", "спец"], "specification"),
        (["teh", "тех"], "tech_description"),
    ]
    for keywords, dtype in _fn_checks:
        matched = [k for k in keywords if k in fn_lower]
        if matched:
            return _result(dtype, f"filename_keyword: {matched}")

    if re.search(r'\bpl\b', fn_lower) and "inv" not in fn_lower:
        return _result("packing_list", "filename_keyword: 'pl' (word boundary)")

    if any(k in fn_lower for k in ["пп", "платеж", "платёж", "payment order"]):
        return _result("payment_order", "filename_keyword: payment")
    _pp_kw = ["платежное поручение", "платёжное поручение", "заявление на перевод",
              "payment order", "просим списать с", "банк получателя"]
    pp_matched = [k for k in _pp_kw if k in text_lower]
    if pp_matched:
        return _result("payment_order", f"content_keyword: {pp_matched[:2]}")

    _ti_kw = ["invoice for transport", "transport invoice", "freight invoice",
              "инвойс за перевозку", "транспортный инвойс", "инвойс за фрахт"]
    ti_matched = [k for k in _ti_kw if k in fn_lower]
    if ti_matched:
        return _result("transport_invoice", f"filename_keyword: {ti_matched}")

    is_invoice_by_name = any(k in fn_lower for k in ["invoice", "инвойс", "счёт", "счет", "inv-", "inv_"])
    is_invoice_by_content = (
        ("invoice" in text_lower or "инвойс" in text_lower or "счёт" in text_lower)
        and ("total" in text_lower or "amount" in text_lower or "итого" in text_lower)
    )
    if is_invoice_by_name or is_invoice_by_content:
        trigger = "filename" if is_invoice_by_name else "content"
        subtype = _classify_invoice_content(text, filename)
        t = (text[:6000].lower()) if text else ""
        _TRANSPORT_KW = [
            ("air freight charge", 12.0), ("air freight", 10.0), ("ocean freight", 10.0),
            ("freight charge", 9.0), ("airway bill", 9.0), ("фрахт", 9.0),
            ("fuel surcharge", 8.0), ("handling charge", 7.0), ("carrier", 5.0),
        ]
        _GOODS_KW = [
            ("description of goods", 10.0), ("hs code", 9.0), ("unit price", 8.0),
            ("country of origin", 7.0), ("quantity", 5.0), ("gross weight", 4.0),
        ]
        ts = round(sum(w for kw, w in _TRANSPORT_KW if kw in t), 1)
        gs = round(sum(w for kw, w in _GOODS_KW if kw in t), 1)
        return _result(subtype, f"invoice_detected_by_{trigger}, scoring -> {subtype}",
                       {"transport_score": ts, "goods_score": gs})

    fn_stripped = re.sub(r'\.(pdf|jpg|jpeg|png|tif|tiff)$', '', fn_lower).strip()
    if re.search(r'^\d{3}[-_ ]?\d{7,8}', fn_stripped):
        return _result("transport_doc", "filename_pattern: AWB number")
    if "air waybill" in text_lower or re.search(r'\bawb\b', text_lower):
        return _result("transport_doc", "content_keyword: air waybill / awb")

    _content_checks = [
        (["contract №", "contract no", "договор №", "контракт №", "предмет договора", "subject of contract"], "contract"),
        (["specification", "спецификация", "приложение к контракту", "приложение к договору"], "specification"),
        (["технические характеристики", "техническое описание", "назначение изделия",
          "technical specifications", "operating temperature"], "tech_description"),
        (["packing list", "gross weight"], "packing_list"),
        (["forwarding agent", "forwarding order", "заявка на перевозку",
          "заявка на экспедирование", "отправитель груза"], "application_statement"),
        (["склад временного хранения", "свидетельство о включении в реестр",
          "документ о принятии на хранение", "до-1", "до1"], "svh_doc"),
    ]
    for keywords, dtype in _content_checks:
        matched = [k for k in keywords if k in text_lower]
        if matched:
            return _result(dtype, f"content_keyword: {matched[:2]}")

    if any(k in text_lower for k in ["наименование товара", "кол-во", "цена за ед", "unit price"]) \
            and "total" in text_lower:
        return _result("specification", "content_keyword: table headers + total")

    if any(k in text_lower for k in ["декларация на товары", "грузовая таможенная"]) \
            and re.search(r'\d{8}/\d{6}/\d{7}', text_lower):
        return _result("reference_gtd", "content_keyword: ГТД + registration number pattern")

    return _result("other", "no_match")


def _parse_svh_doc(text: str, filename: str) -> dict:
    """Извлечь данные СВХ (склада временного хранения) из текста документа.

    Ищет номер документа СВХ (ДО-1 / отчёт), название склада,
    дату помещения и регистрационный номер.
    """
    result: dict = {
        "svh_number": None,
        "warehouse_name": None,
        "warehouse_license": None,
        "placement_date": None,
    }

    if not text:
        return result

    text_search = text[:5000]

    # Номер документа СВХ: CBX..., ДО-1 №..., рег.номер
    # CBX-формат: CBX + дата + порядковый номер
    cbx_m = re.search(r'(CBX\d{10,20})', text_search, re.IGNORECASE)
    if cbx_m:
        result["svh_number"] = cbx_m.group(1).upper()
    else:
        # ДО-1 / отчёт формат
        do_m = re.search(r'(?:ДО[-\s]?1|отчёт|отчет)[\s№#:]*\s*([A-ZА-Яа-я0-9/\-]{4,30})',
                         text_search, re.IGNORECASE)
        if do_m:
            result["svh_number"] = do_m.group(1).strip()

    # Fallback: из имени файла
    if not result["svh_number"]:
        fn_m = re.search(r'(CBX\d{10,20})', filename, re.IGNORECASE)
        if fn_m:
            result["svh_number"] = fn_m.group(1).upper()

    # Название СВХ
    wh_m = re.search(
        r'(?:склад\s+временного\s+хранения|СВХ)\s*[:\-«"]?\s*(.{5,100}?)(?:[»"\n]|,\s*расположен)',
        text_search, re.IGNORECASE,
    )
    if wh_m:
        result["warehouse_name"] = wh_m.group(1).strip().rstrip('.,;')

    # Лицензия / свидетельство СВХ
    lic_m = re.search(
        r'(?:свидетельство|лицензия|разрешение)[\s№#:]*\s*([A-ZА-Яа-я0-9/\-]{4,30})',
        text_search, re.IGNORECASE,
    )
    if lic_m:
        result["warehouse_license"] = lic_m.group(1).strip()

    # Дата помещения
    date_m = re.search(
        r'(?:дата\s+(?:помещения|принятия|поступления)|помещ[её]н|принят)\s*[:\-]?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})',
        text_search, re.IGNORECASE,
    )
    if date_m:
        result["placement_date"] = date_m.group(1).strip()

    logger.debug("svh_parse_result", filename=filename,
                 svh_number=result["svh_number"],
                 warehouse_name=result["warehouse_name"])

    return result


# Кэш парсинга по MD5 хэшу файла (in-memory, до перезапуска)
_parse_cache: dict = {}
_CACHE_MAX = 200


def _count_good_items(items: list) -> int:
    """Считает позиции с содержательным описанием (не 'Item N', не пустые)."""
    good = 0
    for item in (items or []):
        desc = (item.get("description") or item.get("commercial_name") or "").strip()
        if desc and not re.match(r'^item\s*\d+$', desc.strip(), re.I):
            good += 1
    return good


def _invoice_score(inv: dict) -> tuple:
    """
    Оценка качества инвойса для выбора лучшего из нескольких.
    Приоритеты (по убыванию важности):
      1. Количество позиций с нормальными описаниями (не «Item N»)
      2. Наличие seller и buyer (1 если оба, 0 если нет)
      3. Уверенность парсера (confidence)
      4. Общее количество позиций
    """
    items = inv.get("items") or []
    good = _count_good_items(items)
    has_parties = 1 if (inv.get("seller") and inv.get("buyer")) else 0
    conf = inv.get("confidence") or 0.0
    total = len(items)
    return (good, has_parties, conf, total)


_VISION_RETRY_FIELDS: dict[str, list[str]] = {
    "invoice": ["seller", "buyer", "invoice_number"],
    "contract": ["contract_number"],
    "specification": ["items"],
    "packing_list": ["items"],
    "transport_doc": ["transport_number"],
}


def _check_needs_vision_retry(doc_type: str, extracted: dict) -> list[str]:
    """Return list of critical fields that are empty after LLM extraction."""
    required = _VISION_RETRY_FIELDS.get(doc_type, [])
    missing = []
    for f in required:
        val = extracted.get(f)
        if not val:
            missing.append(f)
        elif isinstance(val, dict) and not any(val.values()):
            missing.append(f)
        elif isinstance(val, list) and len(val) == 0:
            missing.append(f)
    return missing


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("\xa0", " ").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _normalize_hs_code(raw) -> str:
    """Normalize HS code to 10 digits, validate first 2 digits are 01-97."""
    code = re.sub(r"\D", "", str(raw or ""))
    if len(code) < 6:
        return ""
    if len(code) < 10:
        code = code.ljust(10, "0")
    else:
        code = code[:10]
    try:
        first2 = int(code[:2])
        if first2 < 1 or first2 > 97:
            return ""
    except ValueError:
        return ""
    return code


# ---------------------------------------------------------------------------
# calc-service integration utilities
# ---------------------------------------------------------------------------

def _fetch_exchange_rates() -> dict:
    """Fetch latest CBR exchange rates from calc-service.
    Returns dict like {"USD": 92.54, "EUR": 100.12, "CNY": 12.87, ...}.
    """
    import httpx
    from app.config import get_settings
    url = f"{get_settings().CALC_SERVICE_URL}/api/v1/calc/exchange-rates/latest"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json().get("rates", {})
    except Exception as e:
        logger.warning("fetch_exchange_rates_failed", error=str(e)[:200])
        return {}


def _fetch_payments(items: list[dict], currency: str, exchange_rate: float) -> dict:
    """Call calc-service to calculate customs payments (duty, VAT, excise, fees).
    items: [{item_no, hs_code, customs_value_rub}, ...]
    Returns calc-service response with items + totals.
    """
    import httpx
    from app.config import get_settings
    url = f"{get_settings().CALC_SERVICE_URL}/api/v1/calc/payments/calculate"
    try:
        resp = httpx.post(url, json={
            "items": items,
            "currency": currency,
            "exchange_rate": exchange_rate,
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("fetch_payments_failed", error=str(e)[:200])
        return {}


def _determine_preference_code(
    cert_type: str | None,
    trade_agreement: str | None,
) -> str:
    """Determine 4-element preference code (gr. 36).
    Elements: customs_fee - duty - excise - VAT.
    Default: 'ОО' (no preference) or '-' (not established).
    """
    el1 = "ОО"  # customs fee always applies on import

    # Duty: tariff preference if origin certificate exists
    if cert_type in ("CT-1", "Form A", "EUR.1"):
        el2 = "ТП"
    else:
        el2 = "ОО"

    el3 = "-"   # excise: not established for most goods
    el4 = "ОО"  # VAT: always applies

    return f"{el1} {el2} {el3} {el4}"


_DESTINATION_TO_POST: dict[str, tuple[str, str, str]] = {
    "SVO":  ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
    "SVO2": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
    "UUEE": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
    "VKO":  ("10005030", "Т/П Аэропорт Внуково", "г. Москва, Внуковское шоссе, д. 4"),
    "UUWW": ("10005030", "Т/П Аэропорт Внуково", "г. Москва, Внуковское шоссе, д. 4"),
    "DME":  ("10009100", "Т/П Аэропорт Домодедово", "Московская обл., г.о. Домодедово, Аэропорт Домодедово"),
    "UUDD": ("10009100", "Т/П Аэропорт Домодедово", "Московская обл., г.о. Домодедово, Аэропорт Домодедово"),
    "ZIA":  ("10005040", "Т/П Аэропорт Жуковский", "Московская обл., г.о. Жуковский, Аэропорт Жуковский"),
    "UUBW": ("10005040", "Т/П Аэропорт Жуковский", "Московская обл., г.о. Жуковский, Аэропорт Жуковский"),
    "LED":  ("10206020", "Т/П Аэропорт Пулково", "г. Санкт-Петербург, Аэропорт Пулково, Пулковское ш."),
    "ULLI": ("10206020", "Т/П Аэропорт Пулково", "г. Санкт-Петербург, Аэропорт Пулково, Пулковское ш."),
    "SVX":  ("10502050", "Т/П Аэропорт Кольцово", "Свердловская обл., г. Екатеринбург, Аэропорт Кольцово"),
    "USSS": ("10502050", "Т/П Аэропорт Кольцово", "Свердловская обл., г. Екатеринбург, Аэропорт Кольцово"),
    "OVB":  ("10609040", "Т/П Аэропорт Толмачёво", "Новосибирская обл., г. Новосибирск, Аэропорт Толмачёво"),
    "UNNT": ("10609040", "Т/П Аэропорт Толмачёво", "Новосибирская обл., г. Новосибирск, Аэропорт Толмачёво"),
    "KJA":  ("10614040", "Т/П Аэропорт Красноярск (Емельяново)", "Красноярский край, г. Красноярск, Аэропорт Емельяново"),
    "UNKL": ("10614040", "Т/П Аэропорт Красноярск (Емельяново)", "Красноярский край, г. Красноярск, Аэропорт Емельяново"),
    "VVO":  ("10702030", "Т/П Аэропорт Владивосток", "Приморский край, г. Владивосток, Аэропорт Кневичи"),
    "UHWW": ("10702030", "Т/П Аэропорт Владивосток", "Приморский край, г. Владивосток, Аэропорт Кневичи"),
    "KHV":  ("10703040", "Т/П Аэропорт Хабаровск", "Хабаровский край, г. Хабаровск, Аэропорт Новый"),
    "UHHH": ("10703040", "Т/П Аэропорт Хабаровск", "Хабаровский край, г. Хабаровск, Аэропорт Новый"),
    "KZN":  ("10404080", "Т/П Аэропорт Казань", "Республика Татарстан, г. Казань, Аэропорт Казань"),
    "UWKD": ("10404080", "Т/П Аэропорт Казань", "Республика Татарстан, г. Казань, Аэропорт Казань"),
    "UFA":  ("10401060", "Т/П Аэропорт Уфа", "Республика Башкортостан, г. Уфа, Аэропорт Уфа"),
    "UWUU": ("10401060", "Т/П Аэропорт Уфа", "Республика Башкортостан, г. Уфа, Аэропорт Уфа"),
    "KUF":  ("10412030", "Т/П Аэропорт Самара (Курумоч)", "Самарская обл., г. Самара, Аэропорт Курумоч"),
    "UWWW": ("10412030", "Т/П Аэропорт Самара (Курумоч)", "Самарская обл., г. Самара, Аэропорт Курумоч"),
    "ROV":  ("10313110", "Т/П Аэропорт Ростов-на-Дону (Платов)", "Ростовская обл., г. Ростов-на-Дону, Аэропорт Платов"),
    "URRP": ("10313110", "Т/П Аэропорт Ростов-на-Дону (Платов)", "Ростовская обл., г. Ростов-на-Дону, Аэропорт Платов"),
    "KRR":  ("10309110", "Т/П Аэропорт Краснодар (Пашковский)", "Краснодарский край, г. Краснодар, Аэропорт Пашковский"),
    "URKK": ("10309110", "Т/П Аэропорт Краснодар (Пашковский)", "Краснодарский край, г. Краснодар, Аэропорт Пашковский"),
    "AER":  ("10317110", "Т/П Аэропорт Сочи", "Краснодарский край, г. Сочи, Аэропорт Адлер"),
    "URSS": ("10317110", "Т/П Аэропорт Сочи", "Краснодарский край, г. Сочи, Аэропорт Адлер"),
    "IKT":  ("10607040", "Т/П Аэропорт Иркутск", "Иркутская обл., г. Иркутск, Аэропорт Иркутск"),
    "UIII": ("10607040", "Т/П Аэропорт Иркутск", "Иркутская обл., г. Иркутск, Аэропорт Иркутск"),
    "OMS":  ("10610040", "Т/П Аэропорт Омск (Центральный)", "Омская обл., г. Омск, Аэропорт Центральный"),
    "UNOO": ("10610040", "Т/П Аэропорт Омск (Центральный)", "Омская обл., г. Омск, Аэропорт Центральный"),
    "TJM":  ("10503050", "Т/П Аэропорт Тюмень (Рощино)", "Тюменская обл., г. Тюмень, Аэропорт Рощино"),
    "USTR": ("10503050", "Т/П Аэропорт Тюмень (Рощино)", "Тюменская обл., г. Тюмень, Аэропорт Рощино"),
    "GOJ":  ("10408030", "Т/П Аэропорт Нижний Новгород (Стригино)", "Нижегородская обл., г. Нижний Новгород, Аэропорт Стригино"),
    "UWGG": ("10408030", "Т/П Аэропорт Нижний Новгород (Стригино)", "Нижегородская обл., г. Нижний Новгород, Аэропорт Стригино"),
    "PEE":  ("10411070", "Т/П Аэропорт Пермь (Большое Савино)", "Пермский край, г. Пермь, Аэропорт Большое Савино"),
    "USPP": ("10411070", "Т/П Аэропорт Пермь (Большое Савино)", "Пермский край, г. Пермь, Аэропорт Большое Савино"),
    "MRV":  ("10802050", "Т/П Аэропорт Минеральные Воды", "Ставропольский край, г. Минеральные Воды, Аэропорт Минеральные Воды"),
    "URMM": ("10802050", "Т/П Аэропорт Минеральные Воды", "Ставропольский край, г. Минеральные Воды, Аэропорт Минеральные Воды"),
    "KGD":  ("10012030", "Т/П Аэропорт Калининград (Храброво)", "Калининградская обл., г. Калининград, Аэропорт Храброво"),
    "UMKK": ("10012030", "Т/П Аэропорт Калининград (Храброво)", "Калининградская обл., г. Калининград, Аэропорт Храброво"),
    "MMK":  ("10207070", "Т/П Аэропорт Мурманск", "Мурманская обл., г. Мурманск, Аэропорт Мурманск"),
    "ULMM": ("10207070", "Т/П Аэропорт Мурманск", "Мурманская обл., г. Мурманск, Аэропорт Мурманск"),
    "YKS":  ("10704030", "Т/П Аэропорт Якутск", "Республика Саха (Якутия), г. Якутск, Аэропорт Якутск"),
    "UEEE": ("10704030", "Т/П Аэропорт Якутск", "Республика Саха (Якутия), г. Якутск, Аэропорт Якутск"),
    "GDX":  ("10706040", "Т/П Аэропорт Магадан (Сокол)", "Магаданская обл., г. Магадан, Аэропорт Сокол"),
    "UHMM": ("10706040", "Т/П Аэропорт Магадан (Сокол)", "Магаданская обл., г. Магадан, Аэропорт Сокол"),
    "PKC":  ("10705030", "Т/П Аэропорт Петропавловск-Камчатский", "Камчатский край, г. Петропавловск-Камчатский, Аэропорт Елизово"),
    "UHPP": ("10705030", "Т/П Аэропорт Петропавловск-Камчатский", "Камчатский край, г. Петропавловск-Камчатский, Аэропорт Елизово"),
    "UUS":  ("10707050", "Т/П Аэропорт Южно-Сахалинск", "Сахалинская обл., г. Южно-Сахалинск, Аэропорт Хомутово"),
    "UHSS": ("10707050", "Т/П Аэропорт Южно-Сахалинск", "Сахалинская обл., г. Южно-Сахалинск, Аэропорт Хомутово"),
    "CEK":  ("10504050", "Т/П Аэропорт Челябинск (Баландино)", "Челябинская обл., г. Челябинск, Аэропорт Баландино"),
    "USCC": ("10504050", "Т/П Аэропорт Челябинск (Баландино)", "Челябинская обл., г. Челябинск, Аэропорт Баландино"),
    "VOZ":  ("10104030", "Т/П Аэропорт Воронеж (Чертовицкое)", "Воронежская обл., г. Воронеж, Аэропорт Чертовицкое"),
    "UUOO": ("10104030", "Т/П Аэропорт Воронеж (Чертовицкое)", "Воронежская обл., г. Воронеж, Аэропорт Чертовицкое"),
}

_AWB_PREFIX_TO_POST: dict[str, tuple[str, str, str]] = {
    "999": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
    "784": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
    "555": ("10009100", "Т/П Аэропорт Домодедово", "Московская обл., г.о. Домодедово, Аэропорт Домодедово"),
    "880": ("10005030", "Т/П Аэропорт Внуково", "г. Москва, Внуковское шоссе, д. 4"),
    "176": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
    "074": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
    "172": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
    "580": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
    "728": ("10005030", "Т/П Аэропорт Внуково", "г. Москва, Внуковское шоссе, д. 4"),
}

_DEFAULT_POST: tuple[str, str, str] = (
    "10005020",
    "Т/П Аэропорт Шереметьево (Грузовой)",
    "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш.",
)


def _parse_transport_doc_llm(text: str, filename: str) -> dict:
    """Извлечь данные из транспортного документа (AWB / CMR / B/L).

    Извлекает:
    - vehicle_id: идентификатор для гр. 21
    - vehicle_type: тип ТС (air / road / sea / rail)
    - transport_country_code: ISO2 страна регистрации ТС
    - awb_number: номер AWB (только для авиа)
    - consignee_*: данные получателя для гр. 8
    """
    result: dict = {
        "vehicle_id": None,
        "vehicle_type": None,
        "transport_country_code": None,
        "awb_number": None,
        "shipper_name": None,
        "shipper_address": None,
        "destination_airport": None,
        "consignee_name": None,
        "consignee_address": None,
        "consignee_inn": None,
        "consignee_kpp": None,
        "consignee_ogrn": None,
    }
    if not text or len(text.strip()) < 20:
        return result
    try:
        from app.config import get_settings
        if not get_settings().has_llm:
            return result
        import json as _json
        from app.services.llm_client import get_llm_client, get_model, json_format_kwargs
        client = get_llm_client(operation="transport_match_llm")
        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": (
                    "Ты эксперт по таможенному оформлению РФ. "
                    "Извлеки данные из транспортного документа (AWB/CMR/B/L). Ответь ТОЛЬКО валидным JSON."
                )},
                {"role": "user", "content": f"""Извлеки из транспортного документа (AWB / CMR / B/L / ж/д накладная):

- doc_type: тип документа — "awb" (авиа), "cmr" (авто), "bill_of_lading" (море), "rail" (ж/д)
- vehicle_id: идентификатор транспортного средства:
    • AWB → номер рейса (flight number), например "CA836" или "SU100". НЕ номер AWB.
    • CMR → государственный регистрационный номер грузового автомобиля (тягача)
    • B/L → название судна (vessel name)
    • Ж/д → номер поезда или локомотива
- awb_number: номер авиационной накладной (только для AWB, формат NNN-NNNNNNNN)
- transport_country_code: ISO 3166-1 alpha-2 код страны регистрации конкретного транспортного средства.
    ВАЖНО: если регистрация конкретного ВС неизвестна (нет tail number / бортового знака) — вернуть "00".
    Для AWB: если известен только перевозчик, но не борт — "00".
- vehicle_count: количество транспортных средств (обычно 1)
- departure_airport: пункт отправления груза — город или IATA-код аэропорта/порта отправления.
    Искать в полях: "Airport of Departure", "Origin", "From", "Departure", "Аэропорт отправления", "Пункт погрузки".
    Примеры: "CAN" (Guangzhou), "PVG" (Shanghai), "HKG" (Hong Kong), "SHANGHAI", "QINGDAO".
    Для CMR/авто: город отправления (например "HANGZHOU", "YIWU", "NINGBO").
    Если не найдено — null.
- destination_airport: IATA-код аэропорта/порта назначения (графа 29 ДТ — таможня на границе).
    Искать в полях: "Airport of Destination", "Destination", "DEST", "To", "Аэропорт назначения".
    Примеры: "SVO", "SVO2", "DME", "VKO", "LED", "SVX", "OVB".
    Для CMR/авто: код пограничного перехода или города (например "МОСКВА", "БРЕСТ").
    Если не найдено — null.
- shipper_name: полное наименование ОТПРАВИТЕЛЯ груза (графа 2 ДТ).
    Искать в полях: "Shipper", "Shipper's Name", "Consignor", "Отправитель", "Грузоотправитель".
    Это компания, которая отправляет груз (НЕ перевозчик и НЕ агент).
- shipper_address: ПОЛНЫЙ адрес отправителя (графа 2 ДТ).
    Искать в полях: "Shipper's Address", "Address", "Адрес отправителя" — обычно сразу под именем отправителя.
    Включить: улицу, город, почтовый индекс, страну.
- consignee_name: наименование ПОЛУЧАТЕЛЯ груза (графа 8 ДТ) — ОБЯЗАТЕЛЬНО НА РУССКОМ ЯЗЫКЕ.
    Искать в полях: "Consignee", "Consignee's Name", "Получатель", "Грузополучатель".
    ВАЖНО: если в документе наименование только на иностранном языке (англ./кит.) —
    перевести/транслитерировать на русский (например "AG-Logistik LLC" → "ООО «АГ-ЛОГИСТИК»").
- consignee_address: ПОЛНЫЙ адрес получателя — ОБЯЗАТЕЛЬНО НА РУССКОМ ЯЗЫКЕ.
    Искать рядом с именем получателя. Включить: улицу, город, индекс, страну.
    Если адрес на иностранном языке — перевести на русский.
- consignee_inn: ИНН получателя (10 или 12 цифр). Искать: "ИНН", "INN", "Tax ID", "TIN".
- consignee_kpp: КПП получателя (9 цифр). Искать: "КПП", "KPP".
- consignee_ogrn: ОГРН/ОГРНИП получателя (13 или 15 цифр). Искать: "ОГРН", "OGRN".

ВАЖНО: shipper_name, shipper_address, destination_airport, consignee_name обязательны для граф 2, 8 и 29 ДТ.

Текст документа:
{text[:6000]}

JSON:"""},
            ],
            temperature=0,
            max_tokens=400,
            **json_format_kwargs(),
        )
        data = _json.loads(resp.choices[0].message.content.strip())
        result["vehicle_id"] = data.get("vehicle_id")
        result["vehicle_type"] = data.get("doc_type")
        result["transport_country_code"] = (data.get("transport_country_code") or "")[:2] or None
        result["awb_number"] = data.get("awb_number")
        result["vehicle_count"] = data.get("vehicle_count") or 1
        result["shipper_name"] = data.get("shipper_name")
        result["shipper_address"] = data.get("shipper_address")
        dep = (data.get("departure_airport") or "").strip().upper()
        result["departure_airport"] = dep or None
        dest = (data.get("destination_airport") or "").strip().upper()
        result["destination_airport"] = dest or None
        result["consignee_name"] = data.get("consignee_name")
        result["consignee_address"] = data.get("consignee_address")
        result["consignee_inn"] = (data.get("consignee_inn") or "").strip() or None
        result["consignee_kpp"] = (data.get("consignee_kpp") or "").strip() or None
        result["consignee_ogrn"] = (data.get("consignee_ogrn") or "").strip() or None
        logger.info("transport_doc_parsed", filename=filename,
                    vehicle_id=result["vehicle_id"], doc_type=result["vehicle_type"],
                    consignee_name=result["consignee_name"])
    except Exception as e:
        logger.warning("transport_doc_parse_failed", filename=filename, error=str(e))
    return result


class DeclarationCrew:
    """
    Мультиагентная оркестрация парсинга документов.
    Если CrewAI доступен — используются реальные Agent/Task/Crew.
    Иначе — линейный pipeline (fallback).
    """

    def __init__(self):
        self.invoice_extractor = InvoiceExtractor()
        self.contract_extractor = ContractExtractor()
        self.packing_extractor = PackingExtractor()
        self.hs_classifier = HSCodeClassifier()
        self.risk_analyzer = RiskAnalyzer()
        self.index_manager = get_index_manager()
        self.reconciliation_agent = ReconciliationAgent()
        self.reviewer_agent = ReviewerAgent()
        self._progress_callback = None

    def _progress(self, step: str, detail: str, pct: int):
        if self._progress_callback:
            try:
                self._progress_callback(step, detail, pct)
            except Exception:
                pass

    @staticmethod
    def _needs_escalation(result: dict) -> tuple[bool, list[str]]:
        confidence = float(result.get("confidence") or 0.0)
        issues = result.get("issues") or []
        has_blocking = any(
            bool(i.get("blocking")) or str(i.get("severity", "")).lower() == "error"
            for i in issues
            if isinstance(i, dict)
        )
        has_drift = any(
            bool(it.get("drift_status"))
            for it in (result.get("items") or [])
            if isinstance(it, dict)
        )

        reasons: list[str] = []
        if confidence < 0.8:
            reasons.append("low_confidence")
        if has_blocking:
            reasons.append("blocking_issues")
        if has_drift:
            reasons.append("drift_status")
        return bool(reasons), reasons

    def _run_escalation(self, result: dict) -> dict:
        """Запуск lightweight-агентов эскалации по triage-правилам."""
        should_run, reasons = self._needs_escalation(result)
        if not should_run:
            return {"enabled": False, "reasons": [], "runs": []}

        runs = [
            self.reconciliation_agent.run(result),
            self.reviewer_agent.run(result),
        ]

        merged_issues = list(result.get("issues") or [])
        for run in runs:
            for issue in run.get("issues", []):
                merged_issues.append(issue)
        result["issues"] = merged_issues
        result["agent_escalation"] = {"enabled": True, "reasons": reasons, "runs": runs}
        logger.info(
            "agent_escalation_completed",
            reasons=reasons,
            runs=len(runs),
            new_issues=sum(len(r.get("issues", [])) for r in runs),
        )
        return result["agent_escalation"]

    def _run_crewai(self, parsed_docs: dict, result: dict) -> dict:
        """Запустить CrewAI мультиагентную оркестрацию."""
        if not _crewai_available:
            return result

        try:
            from crewai import Agent, Task, Crew, Process

            # Агент 1: Классификатор ТН ВЭД
            hs_agent = Agent(
                role="Таможенный классификатор ТН ВЭД ЕАЭС",
                goal="Подобрать точный 10-значный код ТН ВЭД для каждого товара в декларации",
                backstory="Эксперт по классификации товаров с 20-летним опытом работы в таможне РФ. Знает все 97 групп ТН ВЭД и особенности классификации электроники, оборудования, БПЛА.",
                verbose=False,
                allow_delegation=False,
            )

            # Агент 2: Инспектор рисков
            risk_agent = Agent(
                role="Инспектор системы управления рисками (СУР)",
                goal="Оценить риски таможенной декларации и дать рекомендации по снижению рисков",
                backstory="Начальник отдела контроля таможенной стоимости. Специализируется на выявлении занижения стоимости, несоответствия весов и отсутствия документов.",
                verbose=False,
                allow_delegation=False,
            )

            # Задачи
            items = result.get("items", [])
            items_text = "\n".join([f"- {i.get('description','')} (qty: {i.get('quantity','')}, price: {i.get('unit_price','')})" for i in items])

            classify_task = Task(
                description=f"Определи 10-значные коды ТН ВЭД ЕАЭС для товаров:\n{items_text}\n\nДля каждого товара укажи: код ТН ВЭД, название, обоснование выбора.",
                agent=hs_agent,
                expected_output="Список товаров с кодами ТН ВЭД, названиями и обоснованиями",
            )

            risk_task = Task(
                description=f"Оцени риски декларации:\n- Валюта: {result.get('currency','')}\n- Сумма: {result.get('total_amount','')}\n- Страна: {result.get('country_origin','')}\n- Товары:\n{items_text}\n\nПроверь: занижение стоимости, соотношение весов, отсутствие документов.",
                agent=risk_agent,
                expected_output="Оценка рисков: балл 0-100, список рисков с severity и рекомендациями",
            )

            crew = Crew(
                agents=[hs_agent, risk_agent],
                tasks=[classify_task, risk_task],
                process=Process.sequential,
                verbose=False,
            )

            crew_result = crew.kickoff()
            logger.info("crewai_completed", result_length=len(str(crew_result)))

            # Результат CrewAI используется для обогащения
            result["crewai_analysis"] = str(crew_result)[:2000]

        except Exception as e:
            logger.warning("crewai_execution_failed", error=str(e))

        return result

    def _match_items_to_techop(self, invoice_items: list, tech_products: list) -> list:
        """LLM-матчинг: сопоставить позиции инвойса с товарами из тех.описания.

        Работает поверх языкового барьера (инвойс CN/EN, тех.описание RU/EN).
        Возвращает обогащённые позиции: description из тех.описания + hs_description для классификации.
        """
        if not tech_products or not invoice_items:
            return invoice_items

        try:
            from app.config import get_settings
            if not get_settings().has_llm:
                return invoice_items

            import json as _json
            from app.services.llm_client import get_llm_client, get_model

            inv_lines = "\n".join([
                f"[{i + 1}] desc={it.get('description', '') or '(пусто)'}  qty={it.get('quantity')}  price={it.get('unit_price')}"
                for i, it in enumerate(invoice_items)
            ])
            tech_lines = "\n".join([
                f"[{i + 1}] name={tp.get('product_name', '')}  purpose={tp.get('purpose', '')}  "
                f"materials={tp.get('materials', '')}  specs={tp.get('technical_specs', '')}  "
                f"hs_desc={tp.get('suggested_hs_description', '')}"
                for i, tp in enumerate(tech_products)
            ])

            client = get_llm_client(operation="techop_item_match_llm")
            resp = client.chat.completions.create(
                model=get_model(),
                messages=[
                    {"role": "system", "content": (
                        "Ты эксперт по таможенному оформлению РФ. "
                        "Сопоставь позиции инвойса с товарами из технических описаний — документы могут быть на разных языках (CN/EN/RU). "
                        "Ответь ТОЛЬКО валидным JSON."
                    )},
                    {"role": "user", "content": f"""Сопоставь позиции инвойса с техническими описаниями товаров.

ПОЗИЦИИ ИНВОЙСА:
{inv_lines}

ТОВАРЫ ИЗ ТЕХ. ОПИСАНИЯ:
{tech_lines}

Для каждой позиции инвойса верни:
- invoice_index: номер позиции инвойса (1-based)
- tech_index: номер из тех.описания (1-based, null если нет совпадения)
- commercial_name_ru: краткое коммерческое/фирменное наименование товара на русском (марка, модель, артикул)
- description_ru: ПОЛНОЕ описание товара для графы 31 ДТ на русском языке. \
Обязательно включить ВСЕ доступные сведения из тех.описания: \
наименование, назначение/область применения, основные материалы (материал корпуса, покрытия и т.д.), \
технические характеристики (мощность, напряжение, размеры, вес, частота, степень защиты и т.д.), \
марку, модель, артикул, товарный знак, производителя — если указаны. \
Формат: одно связное предложение или перечисление через запятую. НЕ сокращать, НЕ обобщать.
- hs_description: описание для классификации ТН ВЭД (из suggested_hs_description или составь сам — материал + назначение + тип)
- match_confidence: уверенность совпадения (0.0–1.0)

JSON: {{"matches": [...]}}"""},
                ],
                temperature=0,
                max_tokens=4000,
            )

            text = strip_code_fences(resp.choices[0].message.content)
            matches = _json.loads(text).get("matches", [])

            result = [dict(it) for it in invoice_items]
            for m in matches:
                idx = (m.get("invoice_index") or 0) - 1
                if not (0 <= idx < len(result)):
                    continue
                desc_ru = (m.get("description_ru") or "").strip()
                comm_name = (m.get("commercial_name_ru") or "").strip()
                hs_desc = (m.get("hs_description") or "").strip()
                conf = float(m.get("match_confidence") or 0.5)
                if desc_ru:
                    result[idx]["description_invoice"] = result[idx].get("description", "")
                    result[idx]["description"] = desc_ru
                    result[idx]["commercial_name"] = comm_name or desc_ru
                    result[idx]["description_source"] = "tech_description"
                if hs_desc:
                    result[idx]["hs_description_for_classification"] = hs_desc
                result[idx]["techop_match_confidence"] = conf
                logger.info("techop_matched",
                            invoice_desc=(invoice_items[idx].get("description") or "")[:40],
                            tech_desc=desc_ru[:80], confidence=conf)
            return result

        except Exception as e:
            logger.warning("techop_match_failed", error=str(e))
            return invoice_items

    def _batch_parse_secondary(self, docs: list[dict], parsed_docs: dict) -> dict:
        """Батч-парсинг контракта + спеки + ТехОп + транспорт одним LLM-вызовом."""
        try:
            from app.config import get_settings
            settings = get_settings()
            if not settings.has_llm:
                return parsed_docs

            import json as _json
            from app.services.llm_client import get_llm_client, get_model, json_format_kwargs

            def _first_filename(doc_type: str) -> str | None:
                for doc in docs:
                    if doc.get("doc_type") == doc_type:
                        return doc.get("filename")
                return None

            doc_sections = []
            for d in docs:
                label = d["doc_type"].upper()
                text = d.get("text") or ""
                if d["doc_type"] == "contract":
                    from app.services.contract_parser import _smart_slice_contract
                    text_chunk = _smart_slice_contract(text, max_chars=12000)
                elif d["doc_type"] == "specification":
                    text_chunk = text[:10000]
                else:
                    text_chunk = text[:6000]
                doc_sections.append(f"=== {label}: {d['filename']} ===\n{text_chunk}")

            combined_text = "\n\n".join(doc_sections)

            from app.config import get_settings as _get_settings
            _settings = _get_settings()
            _rules_hint = build_graph_rules_prompt(_settings.CORE_API_URL)
            _strategies_hint = build_strategies_prompt(_settings.CORE_API_URL)

            system_prompt = (
                "Ты эксперт по таможенному оформлению РФ. Извлеки данные из нескольких документов одного комплекта. "
                "Ответь ТОЛЬКО валидным JSON.\n\n"
                "Требования к форматам:\n"
                "- Страны: ISO 3166-1 alpha-2 (CN, RU, DE…)\n"
                "- Валюта: ISO 4217 (USD, EUR, CNY…)\n"
                "- Числа: убрать пробелы, запятые заменить на точки\n"
                "- ИНН: только цифры (10 или 12 знаков), КПП: 9 цифр\n"
                "- Если данных нет в документе — оставь null\n"
                "- При конфликте между документами: контракт > инвойс > packing list"
            )
            if _rules_hint:
                system_prompt += f"\n\n{_rules_hint}"
            if _strategies_hint:
                system_prompt += f"\n\n{_strategies_hint}"

            client = get_llm_client(operation="batch_secondary_parse_llm")
            resp = client.chat.completions.create(
                model=get_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""Из документов ниже извлеки:

contract: {{contract_number, contract_date, seller: {{name, country_code, address, inn, kpp, ogrn}}, buyer: {{name, country_code, address, inn, kpp, ogrn}}, is_trilateral: true/false, receiver: {{name, address, country_code, inn, kpp, ogrn}}, financial_responsible: {{name, address, country_code, inn, kpp, ogrn}}, currency, incoterms, payment_terms, delivery_place}}
  ВАЖНО: buyer.name и buyer.address ОБЯЗАТЕЛЬНО на русском языке! В контракте часто дублируется наименование на двух языках — всегда выбирай РУССКИЙ вариант (например «ООО «АГ-ЛОГИСТИК»» вместо «AG-Logistik LLC»).
  is_trilateral: true если договор трёхсторонний (между получателем, декларантом и лицом за фин. урегулирование)
  receiver: получатель груза (графа 8 ДТ) — ТОЛЬКО если отличается от buyer/declarant
  financial_responsible: лицо, ответственное за финансовое урегулирование (графа 9 ДТ) — ТОЛЬКО если отличается от buyer/declarant
specification: {{doc_number, doc_date, incoterms, delivery_place, items_count, total_amount, currency, total_gross_weight, total_net_weight}}
  doc_number: номер спецификации / приложения к контракту
  incoterms: условия поставки (EXW, FOB, CIF, FCA и т.д.) — если указаны в спецификации
  delivery_place: пункт/место поставки — если указан
tech_description: {{doc_number, doc_date, products: [{{product_name, purpose, materials, technical_specs, suggested_hs_description}}]}}
transport_invoice: {{doc_number, doc_date, freight_amount, freight_currency, shipper_name, shipper_address, shipper_contact, consignee_name, consignee_address, consignee_inn, contract_number, contract_date, awb_number, transport_type, route, flight_number, bank_details}}
  doc_number: номер транспортного инвойса / счёта за перевозку
  shipper_name: компания, выставившая инвойс (отправитель/перевозчик) — искать в шапке документа
  shipper_address: адрес компании-выставителя
  consignee_name: получатель услуги ("TO:" / "Покупатель") — наименование, ИНН
application_statement: {{doc_number, doc_date, forwarding_agent: {{name, address, country_code, inn, kpp, ogrn}}, incoterms, delivery_place, shipper: {{name, address, country_code}}}}
  doc_number: номер заявки / поручения экспедитору
  shipper: отправитель груза — искать "Shipper", "Отправитель" и его адрес

Заполни только те разделы, для которых есть документы. Если документа нет — не включай раздел.
Для specification не извлекай все позиции целиком: нужен только items_count и totals для cross-check.

{combined_text[:24000]}

JSON:"""},
                ],
                temperature=0,
                max_tokens=3000,
                **json_format_kwargs(),
            )

            text = strip_code_fences(resp.choices[0].message.content)
            data = _json.loads(text)

            # Маппинг результата
            contract_filename = _first_filename("contract")
            c = data.get("contract")
            if c or contract_filename:
                c = c if isinstance(c, dict) else {}
                from app.services.contract_parser import ContractParsed, ContractParty
                seller_party = None
                buyer_party = None
                if c.get("seller"):
                    s = c["seller"]
                    seller_party = ContractParty(
                        name=s.get("name"),
                        country_code=(s.get("country_code") or "")[:2] or None,
                        address=s.get("address"),
                        inn=s.get("inn"),
                        kpp=s.get("kpp"),
                        ogrn=s.get("ogrn"),
                    )
                if c.get("buyer"):
                    b = c["buyer"]
                    buyer_party = ContractParty(
                        name=b.get("name"),
                        country_code=(b.get("country_code") or "")[:2] or None,
                        address=b.get("address"),
                        inn=b.get("inn"),
                        kpp=b.get("kpp"),
                        ogrn=b.get("ogrn"),
                    )
                contract_payload = ContractParsed(
                    contract_number=c.get("contract_number"), contract_date=c.get("contract_date"),
                    seller_name=c.get("seller", {}).get("name"), buyer_name=c.get("buyer", {}).get("name"),
                    seller=seller_party, buyer=buyer_party,
                    currency=c.get("currency"), incoterms=c.get("incoterms"),
                    delivery_place=c.get("delivery_place"),
                    payment_terms=c.get("payment_terms"), confidence=0.85,
                ).model_dump()
                contract_payload["_filename"] = contract_filename
                parsed_docs["contract"] = contract_payload

            if data.get("specification"):
                spec_raw = data["specification"] if isinstance(data["specification"], dict) else {}
                spec_items_count = spec_raw.get("items_count")
                try:
                    spec_items_count = int(spec_items_count) if spec_items_count not in (None, "") else None
                except (TypeError, ValueError):
                    spec_items_count = None
                parsed_docs["specification"] = {
                    "items_count": spec_items_count,
                    "total_amount": _safe_float(spec_raw.get("total_amount")),
                    "currency": spec_raw.get("currency"),
                    "incoterms": spec_raw.get("incoterms"),
                    "delivery_place": spec_raw.get("delivery_place"),
                    "total_gross_weight": _safe_float(spec_raw.get("total_gross_weight")),
                    "total_net_weight": _safe_float(spec_raw.get("total_net_weight")),
                    "_filename": _first_filename("specification"),
                }
                logger.info(
                    "spec_batch_parsed",
                    items_count=spec_items_count,
                    total=parsed_docs["specification"]["total_amount"],
                    gross=parsed_docs["specification"]["total_gross_weight"],
                    net=parsed_docs["specification"]["total_net_weight"],
                )

            if data.get("tech_description"):
                tech_desc_payload = data["tech_description"] if isinstance(data["tech_description"], dict) else {}
                tech_desc_payload["_filename"] = _first_filename("tech_description")
                parsed_docs.setdefault("tech_descriptions", []).append(tech_desc_payload)

            if data.get("transport_invoice"):
                ti = data["transport_invoice"] if isinstance(data["transport_invoice"], dict) else {}
                ti["_filename"] = _first_filename("transport_invoice")
                parsed_docs["transport_invoice"] = ti

            if data.get("application_statement"):
                app_payload = data["application_statement"] if isinstance(data["application_statement"], dict) else {}
                app_payload["_filename"] = _first_filename("application_statement")
                parsed_docs["application_statement"] = app_payload
                logger.info("application_statement_parsed",
                            has_forwarder=bool(app_payload.get("forwarding_agent")),
                            has_shipper=bool(app_payload.get("shipper")))

            logger.info("batch_parse_complete", docs=len(docs), sections=list(data.keys()))

        except Exception as e:
            logger.warning("batch_parse_failed", error=str(e))
            # Fallback: парсим каждый документ отдельно
            for d in docs:
                try:
                    if d["doc_type"] == "contract":
                        contract_payload = self._to_dict(self.contract_extractor.extract(d["file_bytes"], d["filename"]))
                        contract_payload["_filename"] = d["filename"]
                        parsed_docs["contract"] = contract_payload
                    elif d["doc_type"] == "specification":
                        from app.services.spec_parser import parse as parse_spec
                        spec_payload = self._to_dict(parse_spec(d["file_bytes"], d["filename"]))
                        spec_payload["_filename"] = d["filename"]
                        parsed_docs["specification"] = spec_payload
                    elif d["doc_type"] == "tech_description":
                        from app.services.techop_parser import parse as parse_techop
                        tech_payload = self._to_dict(parse_techop(d["file_bytes"], d["filename"]))
                        tech_payload["_filename"] = d["filename"]
                        parsed_docs.setdefault("tech_descriptions", []).append(tech_payload)
                    elif d["doc_type"] == "transport_invoice":
                        from app.services.transport_parser import parse as parse_transport
                        transport_payload = self._to_dict(parse_transport(d["file_bytes"], d["filename"]))
                        transport_payload["_filename"] = d["filename"]
                        parsed_docs["transport_invoice"] = transport_payload
                except Exception as inner_e:
                    logger.warning("fallback_parse_failed", doc_type=d["doc_type"], error=str(inner_e)[:100])

        return parsed_docs

    def process_documents(self, files: list[tuple[bytes, str]]) -> dict:
        """LLM-based document processing pipeline.

        Steps:
          1. OCR all files
          2. classify_and_extract() — one LLM call per file (type + data)
          3. _compile_declaration_llm() — LLM fills all declaration fields
          4. _post_process_compilation() — Python: arithmetic, lookups, normalization
          5. validate_declaration()
          6. HS RAG + DSPy classification
          7. Risk assessment
          8. Precedent search
        """
        from app.services.llm_parser import classify_and_extract_with_correction as classify_and_extract

        logger.info("crew_process_start", files_count=len(files), pipeline="llm_v3")
        total_files = len(files)

        # ── Step 1: OCR ──
        from app.config import get_settings as _get_settings
        _settings = _get_settings()
        ocr_method = "vision_ocr" if _settings.has_vision_ocr else "legacy"

        doc_texts: list[tuple[bytes, str, str]] = []
        for i, (file_bytes, filename) in enumerate(files):
            pct = 10 + int(15 * i / max(total_files, 1))
            self._progress("ocr", f"[{i+1}/{total_files}] OCR: {filename}", pct)
            text = extract_text(file_bytes, filename)
            doc_texts.append((file_bytes, filename, text))
            logger.info("ocr_done", filename=filename, chars=len(text),
                        ocr_method=ocr_method)

        # ── Step 2: LLM classify + extract (one call per doc) ──
        parsed_docs: dict = {}
        for i, (file_bytes, filename, text) in enumerate(doc_texts):
            pct = 25 + int(30 * i / max(total_files, 1))
            self._progress("classify_extract", f"[{i+1}/{total_files}] AI: {filename}", pct)

            result = classify_and_extract(text, filename)
            doc_type = result["doc_type"]
            extracted = result["extracted"]
            extracted["_filename"] = filename
            extracted["doc_type"] = doc_type
            extracted["doc_type_confidence"] = result.get("doc_type_confidence", 0.5)

            # ── Vision OCR quality gate ──
            missing_fields = _check_needs_vision_retry(doc_type, extracted)
            if missing_fields and _settings.has_vision_ocr:
                logger.info("vision_retry_triggered",
                            filename=filename, doc_type=doc_type,
                            missing=missing_fields)
                try:
                    from app.services.ocr_service import _extract_with_vision_ocr
                    vision_text = _extract_with_vision_ocr(file_bytes, filename)
                    if vision_text and vision_text.strip():
                        vision_result = classify_and_extract(vision_text, filename)
                        vision_extracted = vision_result.get("extracted", {})
                        merged = []
                        for field in missing_fields:
                            v = vision_extracted.get(field)
                            if v and not (isinstance(v, dict) and not any(v.values())):
                                extracted[field] = v
                                merged.append(field)
                        if merged:
                            logger.info("vision_retry_merged",
                                        filename=filename, merged_fields=merged)
                        else:
                            logger.info("vision_retry_no_new_data",
                                        filename=filename)
                except Exception as e:
                    logger.warning("vision_retry_failed",
                                   filename=filename, error=str(e)[:200])

            _LIST_TYPES = {"tech_description", "payment_order", "conformity_declaration", "other"}
            if doc_type in _LIST_TYPES:
                list_key = {
                    "tech_description": "tech_descriptions",
                    "payment_order": "payment_orders",
                    "conformity_declaration": "conformity_declarations",
                    "other": "other",
                }[doc_type]
                parsed_docs.setdefault(list_key, []).append(extracted)
            elif doc_type == "packing_list":
                parsed_docs["packing"] = extracted
            elif doc_type == "transport_doc":
                parsed_docs["transport"] = extracted
            elif doc_type == "invoice":
                prev_inv = parsed_docs.get("invoice")
                if prev_inv:
                    new_score = _invoice_score(extracted)
                    old_score = _invoice_score(prev_inv)
                    if new_score > old_score:
                        parsed_docs["invoice"] = extracted
                        logger.info("invoice_replaced", prev=prev_inv.get("_filename"), new=filename)
                    else:
                        logger.info("invoice_kept", kept=prev_inv.get("_filename"), skipped=filename)
                else:
                    parsed_docs["invoice"] = extracted
            else:
                parsed_docs[doc_type] = extracted

            items_count = len(extracted.get("items", extracted.get("products", [])))
            llm_debug = result.get("llm_debug", {})
            logger.info(
                "classify_extract_done",
                filename=filename,
                doc_type=doc_type,
                confidence=result.get("doc_type_confidence"),
                reasoning=result.get("reasoning", "")[:150],
                correction_applied=result.get("correction_applied", False),
                validation_issues_count=len(result.get("validation_issues", [])),
                items_extracted=items_count,
                finish_reason=llm_debug.get("finish_reason"),
                tokens_prompt=llm_debug.get("tokens", {}).get("prompt", 0),
                tokens_completion=llm_debug.get("tokens", {}).get("completion", 0),
                duration_ms=llm_debug.get("duration_ms", 0),
                keys=list(extracted.keys()),
            )

        # ── Step 3: LLM compile (semantic decisions) ──
        self._progress("compiling", "AI компилирует данные декларации...", 58)
        llm_result = self._compile_declaration_llm(parsed_docs)

        # ── Step 4: Python post-process (arithmetic, lookups) ──
        self._progress("compiling", "Python: расчёты, нормализация...", 65)
        result = self._post_process_compilation(llm_result, parsed_docs)

        # Field normalization for ApplyParsedRequest compatibility
        if result.get("trading_partner_country") is None:
            seller_data = result.get("seller")
            if seller_data and isinstance(seller_data, dict) and seller_data.get("country_code"):
                result["trading_partner_country"] = seller_data["country_code"]
        if result.get("financial_responsible") and not result.get("responsible_person"):
            result["responsible_person"] = result["financial_responsible"]

        # ── Step 5: validate_declaration() ──
        self._progress("validating", "Валидация декларации...", 70)
        evidence_map = result.get("evidence_map", {})
        issues = validate_declaration(result, evidence_map)
        result["evidence_map"] = evidence_map
        result["issues"] = issues

        # ── Step 6: HS Classification ──
        items = result.get("items", [])
        all_descs = [it.get("description") or "" for it in items if it.get("description")]
        decl_context = "; ".join([d[:60] for d in all_descs]) if len(all_descs) > 1 else ""
        for j, item in enumerate(items):
            existing_hs = (item.get("hs_code") or "").strip()
            desc = item.get("description") or item.get("commercial_name") or ""
            self._progress("classifying", f"ТН ВЭД: {j+1}/{len(items)} — {desc[:40]}", 72 + int(12 * j / max(len(items), 1)))

            if existing_hs and len(existing_hs) >= 8 and not desc.strip().lower().startswith("item "):
                if len(existing_hs) < 10:
                    item["hs_code"] = existing_hs.ljust(10, "0")
                item.setdefault("hs_confidence", 0.9)
                item.setdefault("hs_reasoning", "Extracted from document")
                item["hs_needs_review"] = False
                if desc:
                    try:
                        rag_for_choice = self.index_manager.search_hs_codes(desc)
                        hs_candidates = []
                        for r in rag_for_choice[:8]:
                            code_raw = re.sub(r"\D", "", str(r.get("code", "")))
                            if len(code_raw) < 8:
                                continue
                            code = (code_raw[:10] if len(code_raw) >= 10 else code_raw.ljust(10, "0"))
                            hs_candidates.append({
                                "hs_code": code,
                                "name_ru": r.get("name_ru", "") or "",
                                "confidence": float(r.get("score", 0.0) or 0.0),
                                "source": "rag",
                            })
                        if hs_candidates:
                            item["hs_candidates"] = hs_candidates
                    except Exception as e:
                        logger.debug("hs_candidates_skip", error=str(e)[:80])
                logger.info("hs_from_doc_kept", item_no=j+1, hs_code=item["hs_code"])
                continue

            if desc:
                hs_classify_desc = item.get("hs_description_for_classification") or desc
                rag_results = self.index_manager.search_hs_codes(hs_classify_desc)
                hs_result = self.hs_classifier.classify(hs_classify_desc, rag_results, context=decl_context)
                hs_code = hs_result.get("hs_code", "")
                if hs_code and len(hs_code) < 10:
                    hs_code = hs_code.ljust(10, "0")
                item["hs_code"] = hs_code
                item["hs_code_name"] = hs_result.get("name_ru", "")
                item["hs_confidence"] = hs_result.get("confidence", 0.0)
                item["hs_reasoning"] = hs_result.get("reasoning", "")
                item["hs_candidates"] = hs_result.get("candidates", [])
                item["hs_needs_review"] = (hs_result.get("confidence", 0) < 0.5 or not hs_code)
                if item["hs_needs_review"]:
                    item["hs_review_message"] = f"AI не уверен в коде ТН ВЭД: {desc[:80]}"
                logger.info("hs_classified", item_no=j+1, description=desc[:50],
                            hs_code=hs_code, confidence=hs_result.get("confidence", 0))
            else:
                item["hs_code"] = ""
                item["hs_needs_review"] = True
                item["hs_review_message"] = "Описание товара отсутствует."

        # ── Step 6b: Payments calculation (after HS codes are known) ──
        self._progress("payments", "Расчёт платежей (calc-service)...", 85)
        exchange_rate = result.get("exchange_rate", 0.0)
        currency = (result.get("currency") or "USD").upper()
        items_with_hs = [it for it in items if it.get("hs_code")]

        if items_with_hs and exchange_rate > 0:
            pay_items = [{
                "item_no": it.get("line_no") or (i + 1),
                "hs_code": it["hs_code"],
                "customs_value_rub": _safe_float(it.get("customs_value_rub")) or 0.0,
            } for i, it in enumerate(items_with_hs)]

            payments_data = _fetch_payments(pay_items, currency, exchange_rate)
            if payments_data:
                result["payments"] = payments_data.get("totals", {})
                pay_items_resp = payments_data.get("items", [])
                for pay_item in pay_items_resp:
                    item_no = pay_item.get("item_no", 0)
                    for it in items:
                        if (it.get("line_no") or 0) == item_no or items.index(it) + 1 == item_no:
                            it["duty"] = pay_item.get("duty", {})
                            it["vat"] = pay_item.get("vat", {})
                            it["excise"] = pay_item.get("excise", 0)
                            break
                logger.info("payments_calculated",
                            total_duty=result["payments"].get("total_duty"),
                            total_vat=result["payments"].get("total_vat"),
                            customs_fee=result["payments"].get("customs_fee"))
        else:
            if not items_with_hs:
                logger.warning("payments_skipped", reason="no items with HS codes")
            elif exchange_rate <= 0:
                logger.warning("payments_skipped", reason="no exchange rate")

        # ── Step 7: Risk assessment ──
        self._progress("risks", "Оценка рисков СУР...", 88)
        risk_rules = self.index_manager.search_risk_rules(
            json.dumps(result, ensure_ascii=False, default=str)[:3000]
        )
        risk_result = self.risk_analyzer.analyze(result, risk_rules)
        result["risk_score"] = risk_result.get("risk_score", 0)
        result["risk_flags"] = {"risks": risk_result.get("risks", []), "source": risk_result.get("source", "")}

        # ── Step 8: Precedent search ──
        self._progress("precedents", "Поиск прецедентов...", 93)
        for item in result.get("items", []):
            desc = item.get("description", "")
            if desc:
                precedents = self.index_manager.search_precedents(desc)
                if precedents:
                    item["precedents"] = precedents[:3]

        # Confidence
        confidences = [
            (parsed_docs.get("invoice") or {}).get("doc_type_confidence", 0),
            (parsed_docs.get("contract") or {}).get("doc_type_confidence", 0),
            (parsed_docs.get("packing") or {}).get("doc_type_confidence", 0),
        ]
        non_zero = [c for c in confidences if c > 0]
        result["confidence"] = sum(non_zero) / len(non_zero) if non_zero else 0.0

        # ── Step 9: Agent escalation ──
        self._progress("escalation", "Проверка эскалации...", 95)
        self._run_escalation(result)

        items_count = len(result.get("items", []))
        logger.info("crew_process_complete", items_count=items_count,
                    confidence=result["confidence"], risk_score=result.get("risk_score", 0))

        try:
            from app.services.issue_reporter import report_issue
            if items_count == 0:
                report_issue("compile", "warning", "No items after compilation",
                    {"confidence": result.get("confidence")})
            for it in result.get("items", []):
                desc = it.get("description") or ""
                if desc.lower().startswith("item ") or not desc:
                    report_issue("compile", "warning", f"Bad item description: '{desc[:60]}'",
                        {"description": desc, "hs_code": it.get("hs_code", "")})
        except Exception:
            pass

        return result

    @staticmethod
    def _to_dict(obj) -> dict:
        """Pydantic model или dict → dict."""
        if obj is None:
            return {}
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        if isinstance(obj, dict):
            return obj
        return {}

    def _compile_declaration(self, parsed_docs: dict) -> dict:
        """Собрать данные декларации из всех распознанных документов."""
        ev = EvidenceTracker()

        inv = self._to_dict(parsed_docs.get("invoice"))
        contract = self._to_dict(parsed_docs.get("contract"))
        packing = self._to_dict(parsed_docs.get("packing"))
        spec = parsed_docs.get("specification", {})
        tech_descs = parsed_docs.get("tech_descriptions", [])
        transport_inv = parsed_docs.get("transport_invoice", {})
        transport = parsed_docs.get("transport", {})
        application = parsed_docs.get("application_statement", {})
        reference_gtd = parsed_docs.get("reference_gtd", {})
        svh_doc = parsed_docs.get("svh_doc", {})

        # ── Seller/Buyer: извлечение из источников с дополнением пробелов ──
        def _extract_party(sources, party_type):
            """Имя берём из первого источника (приоритет), недостающие
            address / country_code / inn / kpp / ogrn дополняем из остальных."""
            result = None
            for src in sources:
                if not src:
                    continue
                p = self._to_dict(src)
                name = p.get("name") or p.get("seller_name" if party_type == "seller" else "buyer_name")
                if not name:
                    continue
                if result is None:
                    inn = (p.get("inn") or p.get("tax_number") or "").strip()
                    kpp = (p.get("kpp") or "").strip()
                    ogrn = (p.get("ogrn") or "").strip()
                    tax_number = f"{inn}/{kpp}" if inn and kpp else (inn or None)
                    result = {
                        "name": name,
                        "country_code": (p.get("country_code") or "")[:2] or None,
                        "address": p.get("address"),
                        "tax_number": tax_number,
                        "inn": inn or None,
                        "kpp": kpp or None,
                        "ogrn": ogrn or None,
                        "type": party_type,
                    }
                else:
                    if not result.get("address") and p.get("address"):
                        result["address"] = p["address"]
                    if not result.get("country_code") and p.get("country_code"):
                        result["country_code"] = (p["country_code"] or "")[:2] or None
                    if not result.get("inn") and (p.get("inn") or p.get("tax_number")):
                        inn = (p.get("inn") or p.get("tax_number") or "").strip()
                        kpp = (p.get("kpp") or "").strip()
                        result["inn"] = inn or None
                        result["kpp"] = kpp or None
                        result["tax_number"] = f"{inn}/{kpp}" if inn and kpp else (inn or None)
                    if not result.get("ogrn") and p.get("ogrn"):
                        result["ogrn"] = p["ogrn"]
            return result

        # Графа 2 (Отправитель) — ТОЛЬКО транспортные источники:
        # 1. Транспортный документ (AWB/CMR/B/L) — Shipper/Consignor
        # 2. Заявка на ПЕРЕВОЗКУ (Application) — Отправитель/Shipper
        # 3. Транспортный инвойс — Shipper
        # Товарный инвойс (seller) и контракт (seller) НЕ используются —
        # это стороны сделки (Гр.11), а не физический грузоотправитель.
        transport_shipper = {"name": transport.get("shipper_name"),
                             "address": transport.get("shipper_address")} if transport.get("shipper_name") else None
        app_forwarder = application.get("forwarding_agent") or application.get("shipper")
        transp_inv_shipper = {"name": transport_inv.get("shipper_name"),
                              "address": transport_inv.get("shipper_address")} if transport_inv.get("shipper_name") else None

        sender = _extract_party([transport_shipper, app_forwarder, transp_inv_shipper], "seller")

        # Fallback: если ни один транспортный документ не дал отправителя —
        # берём продавца из товарного инвойса/контракта с предупреждением.
        # Это НЕ правильный источник для Гр.2, но лучше чем пустое поле.
        if not sender:
            sender = _extract_party([inv.get("seller"), contract.get("seller")], "seller")
            if sender:
                logger.warning("sender_fallback_to_invoice_seller",
                               name=sender.get("name"),
                               msg="Гр.2: отправитель не найден в транспортных документах. "
                                   "Использован продавец из инвойса/контракта — ТРЕБУЕТ ПРОВЕРКИ.")

        buyer = _extract_party([contract.get("buyer"), inv.get("buyer")], "buyer")
        if not buyer and contract.get("buyer_name"):
            buyer = {"name": contract["buyer_name"], "country_code": None, "address": None, "type": "buyer"}

        # ИНН/КПП декларанта: берём из buyer реквизитов контракта/инвойса
        def _extract_inn_kpp(src_obj: dict) -> Optional[str]:
            if not src_obj:
                return None
            p = self._to_dict(src_obj)
            inn = (p.get("inn") or p.get("tax_number") or "").strip()
            kpp = (p.get("kpp") or "").strip()
            if inn and kpp:
                return f"{inn}/{kpp}"
            return inn or None

        declarant_inn_kpp = _extract_inn_kpp(contract.get("buyer")) or _extract_inn_kpp(inv.get("buyer"))

        # ── Графа 8: получатель из транспортного документа ──
        # Источник — ТОЛЬКО transport_doc. Извлекаем consignee, сравниваем ИНН/КПП/ОГРН
        # с декларантом (гр.14). Совпадают → «СМ. ГРАФУ 14 ДТ», нет → данные из transport_doc.
        buyer_matches_declarant = True
        consignee_data = None

        transport_consignee_name = (transport.get("consignee_name") or "").strip()
        if transport_consignee_name:
            cons_inn = (transport.get("consignee_inn") or "").strip()
            cons_kpp = (transport.get("consignee_kpp") or "").strip()
            cons_ogrn = (transport.get("consignee_ogrn") or "").strip()

            decl_inn = (buyer.get("inn") or "").strip() if buyer else ""
            decl_kpp = (buyer.get("kpp") or "").strip() if buyer else ""
            decl_ogrn = (buyer.get("ogrn") or "").strip() if buyer else ""

            can_compare = bool(cons_inn or cons_ogrn)
            if can_compare:
                inn_ok = (cons_inn == decl_inn) if (cons_inn and decl_inn) else True
                kpp_ok = (cons_kpp == decl_kpp) if (cons_kpp and decl_kpp) else True
                ogrn_ok = (cons_ogrn == decl_ogrn) if (cons_ogrn and decl_ogrn) else True
                identifiers_match = inn_ok and kpp_ok and ogrn_ok
            else:
                identifiers_match = False

            if can_compare and identifiers_match:
                buyer_matches_declarant = True
                logger.info("graph_8_consignee_matches_declarant",
                            consignee_inn=cons_inn, declarant_inn=decl_inn,
                            msg="Графа 8: получатель совпадает с декларантом → «СМ. ГРАФУ 14 ДТ»")
            elif can_compare:
                buyer_matches_declarant = False
                consignee_data = _extract_party([{
                    "name": transport_consignee_name,
                    "address": transport.get("consignee_address"),
                    "country_code": "RU",
                    "inn": cons_inn or None,
                    "kpp": cons_kpp or None,
                    "ogrn": cons_ogrn or None,
                }], "buyer")
                logger.info("graph_8_consignee_from_transport_doc",
                            consignee_name=transport_consignee_name, consignee_inn=cons_inn,
                            msg="Графа 8: получатель отличается от декларанта")
            else:
                buyer_matches_declarant = True
                logger.warning("graph_8_consignee_no_identifiers",
                               consignee_name=transport_consignee_name,
                               msg="Графа 8: у получателя нет ИНН/ОГРН — нельзя сравнить с декларантом, «СМ. ГРАФУ 14 ДТ»")
        else:
            logger.info("graph_8_no_consignee_in_transport",
                        msg="Графа 8: получатель не найден в транспортном документе → «СМ. ГРАФУ 14 ДТ»")

        # ── Графа 9: по умолчанию «СМ. ГРАФУ 14 ДТ» ──
        # Отдельное фин. ответственное лицо — ТОЛЬКО при наличии трёхстороннего договора.
        is_trilateral = bool(contract.get("is_trilateral"))
        contract_financial = contract.get("financial_responsible") or contract.get("financial_party")
        responsible_person_matches_declarant = True
        responsible_person_data = None

        if is_trilateral and contract_financial:
            fin_party = _extract_party([contract_financial], "financial")
            if fin_party and fin_party.get("name"):
                responsible_person_data = fin_party
                responsible_person_matches_declarant = False
                logger.info("trilateral_financial_found",
                            name=fin_party.get("name"),
                            msg="Графа 9: ответственное лицо из трёхстороннего договора")

        # ── Items: спецификация (приоритет) > инвойс ──
        import re as _re
        _SKIP_ITEM = _re.compile(
            r'\b(freight|shipping|insurance|handling|delivery\s*fee|transport.*fee|'
            r'фрахт|доставка|страхов|транспортн)',
            _re.IGNORECASE,
        )
        def _normalize_hs_code(raw) -> str:
            code = _re.sub(r"\D", "", str(raw or ""))
            if len(code) < 6:
                return ""
            if len(code) < 10:
                code = code.ljust(10, "0")
            else:
                code = code[:10]
            try:
                first2 = int(code[:2])
                if first2 < 1 or first2 > 97:
                    return ""
            except ValueError:
                return ""
            return code
        # Графа 16 (header-level origin) вычисляется после сбора items (ниже)

        # Источник items: ТОЛЬКО инвойс на товары.
        # Packing List — источник весов/упаковки, но НЕ источник позиций (гр. 42).
        # Спецификация — только для перекрёстной сверки.
        inv_items = inv.get("items", [])
        packing_items = packing.get("items", []) if packing else []

        if inv_items:
            raw_items = inv_items
            items_source = "invoice"
        else:
            raw_items = []
            items_source = "none"
            logger.warning("no_items_found", msg="Нет позиций в инвойсе — загрузите инвойс на товары")

        logger.info("items_source", source=items_source, count=len(raw_items))

        # Перекрёстная сверка со спецификацией (только предупреждение, не замена)
        spec_items_count = spec.get("items_count")
        if spec_items_count is None:
            spec_items_count = len(spec.get("items", []) or [])
        if spec_items_count and inv_items:
            if int(spec_items_count) != len(inv_items):
                logger.info(
                    "spec_vs_invoice_count_mismatch",
                    spec_count=spec_items_count,
                    inv_count=len(inv_items),
                    msg="Количество позиций в спецификации и инвойсе различается — это нормально, "
                        "спецификация содержит весь заказ",
                )

        # Графа 34: per-item lookup для country_origin из PL (приоритет над инвойсом)
        _pl_origin_map: dict[int, str] = {}
        for pi, pl_it in enumerate(packing_items):
            co = (pl_it.get("country_origin") or "").strip()
            if co:
                _pl_origin_map[pi] = co[:2]

        items = []
        for idx, item_data in enumerate(raw_items):
            desc = item_data.get("description", item_data.get("description_raw", ""))
            if _SKIP_ITEM.search(desc or ""):
                logger.info("skip_non_goods_item", description=desc[:60])
                continue
            # Quality gate: drop descriptions that are clearly garbage —
            # service lines, header rows, payment conditions, raw codes, etc.
            if _is_garbage_desc(desc or ""):
                logger.warning("skip_garbage_item", description=(desc or "")[:80],
                               msg="Описание не похоже на товар — строка отфильтрована quality gate")
                continue
            hs_from_doc = _normalize_hs_code(item_data.get("hs_code"))
            if hs_from_doc and (not desc or _re.match(
                r'^(item|товар|product|goods?|позиция|pos)\s*\d*$',
                str(desc).strip(), _re.IGNORECASE,
            )):
                logger.info("drop_untrusted_doc_hs", hs_code=hs_from_doc, description=(desc or "")[:40])
                hs_from_doc = ""
            qty = _safe_float(item_data.get("quantity"))
            up = _safe_float(item_data.get("unit_price"))
            lt = _safe_float(item_data.get("line_total"))
            if not qty and lt and up and up > 0:
                qty = round(lt / up, 2)

            # Гр. 34: приоритет PL origin > invoice origin
            item_origin = (
                _pl_origin_map.get(idx)
                or (item_data.get("country_origin_code") or item_data.get("country_origin") or "").strip()[:2]
            ) or None

            items.append({
                "line_no": item_data.get("line_no", len(items) + 1),
                "description": desc or "",
                "commercial_name": desc or "",
                "quantity": qty,
                "unit": item_data.get("unit"),
                "unit_price": up,
                "line_total": lt,
                "invoice_currency": inv.get("currency"),
                "hs_code": hs_from_doc,
                "country_origin_code": item_origin,
                "gross_weight": _safe_float(item_data.get("gross_weight")),
                "net_weight": _safe_float(item_data.get("net_weight")),
                "package_count": None,
                "package_type": None,
                "description_source": "invoice",
            })

        # ── Обогащение из техописаний (ТехОп) через LLM-матчинг (гр. 31, пункт 1) ──
        # Техописание — приоритетный источник наименования товара для графы 31.
        # Без техописания — описание берётся из инвойса (менее предпочтительно).
        if tech_descs and items:
            all_tech_products = []
            for td in tech_descs:
                all_tech_products.extend(td.get("products", []))
            if all_tech_products:
                logger.info("techop_match_start", items=len(items), tech_products=len(all_tech_products))
                items = self._match_items_to_techop(items, all_tech_products)
                # Логируем позиции, для которых не нашлось совпадения с тех.описанием
                for item in items:
                    if item.get("description_source") != "tech_description":
                        logger.warning(
                            "techop_no_match_for_item",
                            description=item.get("description", "")[:60],
                            msg="Граф 31: наименование из инвойса (тех.описание не совпало) — требует проверки",
                        )
        else:
            if not tech_descs:
                logger.warning(
                    "techop_missing",
                    msg="Граф 31: документ «Техническое описание» не загружен — наименования берутся из инвойса",
                )

        # Веса (гр. 35/38): берём по каждой позиции из PL, не суммарные.
        # Спецификация НЕ источник весов.
        # Алгоритм:
        #   1. PL содержит per-item weights → матчим по описанию или позиции
        #   2. Если PL нет per-item — смотрим item-weights из инвойса
        #   3. Fallback: пропорционально по доле стоимости (НЕ поровну)
        #   4. Суммарные веса для декларации = sum(item weights)
        pl_items = packing.get("items") or []

        def _desc_key(desc: str) -> str:
            """Нормализованный ключ описания для матчинга."""
            return re.sub(r'[^a-zа-я0-9]', ' ', (desc or "").lower()).split()

        def _desc_similarity(a: str, b: str) -> float:
            """Доля общих слов между двумя описаниями (0..1)."""
            wa = set(_desc_key(a))
            wb = set(_desc_key(b))
            if not wa or not wb:
                return 0.0
            return len(wa & wb) / max(len(wa), len(wb))

        def _find_pl_item(inv_desc: str, pl_items: list, used: set) -> dict | None:
            """Найти PL-строку для инвойс-позиции по наилучшему совпадению описания."""
            best_score = 0.3       # минимальный порог сходства
            best_item = None
            for idx, pl_it in enumerate(pl_items):
                if idx in used:
                    continue
                sim = _desc_similarity(inv_desc, pl_it.get("description", ""))
                if sim > best_score:
                    best_score = sim
                    best_item = (idx, pl_it)
            return best_item

        # Шаг 1: Присвоить per-item веса из PL по матчингу
        pl_items_with_weights = [
            it for it in pl_items
            if _safe_float(it.get("gross_weight")) or _safe_float(it.get("net_weight"))
        ]
        weights_assigned = 0
        used_pl_indices: set = set()

        if pl_items_with_weights:
            if len(pl_items_with_weights) == len(items):
                # Одинаковое число позиций → матч по позиции (надёжнее описания)
                for j, item in enumerate(items):
                    pl_it = pl_items_with_weights[j]
                    pg = _safe_float(pl_it.get("gross_weight"))
                    pn = _safe_float(pl_it.get("net_weight"))
                    if pg and not item.get("gross_weight"):
                        item["gross_weight"] = round(pg, 3)
                    if pn and not item.get("net_weight"):
                        item["net_weight"] = round(pn, 3)
                    if pg or pn:
                        weights_assigned += 1
                        used_pl_indices.add(j)
                logger.info("weights_from_pl_by_position",
                            assigned=weights_assigned, pl_items=len(pl_items_with_weights))
            else:
                # Разное число → матч по описанию
                for item in items:
                    match = _find_pl_item(item.get("description", ""), pl_items_with_weights, used_pl_indices)
                    if match:
                        idx, pl_it = match
                        used_pl_indices.add(idx)
                        pg = _safe_float(pl_it.get("gross_weight"))
                        pn = _safe_float(pl_it.get("net_weight"))
                        if pg and not item.get("gross_weight"):
                            item["gross_weight"] = round(pg, 3)
                        if pn and not item.get("net_weight"):
                            item["net_weight"] = round(pn, 3)
                        if pg or pn:
                            weights_assigned += 1
                logger.info("weights_from_pl_by_desc",
                            assigned=weights_assigned, pl_items=len(pl_items_with_weights))

        # Шаг 2: Для позиций без веса — попробовать из инвойса (если есть item-level)
        for item in items:
            if not item.get("gross_weight") and not item.get("net_weight"):
                inv_items_src = inv.get("items") or []
                for inv_it in inv_items_src:
                    if _desc_similarity(item.get("description", ""),
                                        inv_it.get("description", "")) > 0.3:
                        ig = _safe_float(inv_it.get("gross_weight"))
                        in_ = _safe_float(inv_it.get("net_weight"))
                        if ig:
                            item["gross_weight"] = round(ig, 3)
                        if in_:
                            item["net_weight"] = round(in_, 3)
                        break

        # Шаг 3: Fallback — пропорционально по стоимости (НЕ поровну)
        # Применяется только если PL совсем не дал per-item весов
        total_gross = _safe_float(
            packing.get("total_gross_weight") or
            inv.get("total_gross_weight") or inv.get("gross_weight")
        )
        total_net = _safe_float(
            packing.get("total_net_weight") or
            inv.get("total_net_weight") or inv.get("net_weight")
        )
        items_missing_weight = [it for it in items if not it.get("gross_weight")]
        if items_missing_weight and total_gross:
            # Оставшийся вес = total - уже назначенные
            assigned_gross = sum((_safe_float(it.get("gross_weight")) or 0.0)
                                 for it in items if it.get("gross_weight"))
            assigned_net = sum((_safe_float(it.get("net_weight")) or 0.0)
                               for it in items if it.get("net_weight"))
            remaining_gross = max(0.0, (total_gross or 0.0) - assigned_gross)
            remaining_net = max(0.0, (total_net or 0.0) - assigned_net) if total_net else None

            # Пропорция по стоимости
            total_price = sum((_safe_float(it.get("line_total")) or 0.0) for it in items_missing_weight)
            for item in items_missing_weight:
                price = _safe_float(item.get("line_total")) or 0.0
                share = (price / total_price) if total_price > 0 else (1.0 / len(items_missing_weight))
                item["gross_weight"] = round(remaining_gross * share, 3)
                if remaining_net:
                    item["net_weight"] = round(remaining_net * share, 3)
                elif item.get("gross_weight"):
                    item["net_weight"] = round(item["gross_weight"] * 0.9, 3)
            logger.info("weights_fallback_proportional",
                        items=len(items_missing_weight),
                        remaining_gross=remaining_gross,
                        method="by_value_share")

        logger.info("weights_sources",
                    packing_gross=packing.get("total_gross_weight"),
                    inv_gross=inv.get("total_gross_weight"),
                    total_gross=total_gross,
                    pl_per_item_assigned=weights_assigned)

        # ── Грузовые места и упаковка (гр. 31): присваиваем из PL per-item ──
        # Алгоритм: если PL содержит per-item packages_count/package_type — матчим
        # по позиции или описанию (аналогично весам). Иначе оставляем None (заполнит пользователь).
        pl_items_for_pkg = [
            it for it in pl_items
            if it.get("packages_count") or it.get("package_type")
        ]
        pkg_assigned = 0
        if pl_items_for_pkg and items:
            if len(pl_items_for_pkg) == len(items):
                # Матч по позиции
                for j, item in enumerate(items):
                    pl_it = pl_items_for_pkg[j]
                    if not item.get("package_count"):
                        item["package_count"] = pl_it.get("packages_count")
                    if not item.get("package_type"):
                        item["package_type"] = pl_it.get("package_type") or packing.get("package_type")
                    pkg_assigned += 1
            else:
                # Матч по описанию
                used_pkg = set()
                for item in items:
                    match = _find_pl_item(item.get("description", ""), pl_items_for_pkg, used_pkg)
                    if match:
                        pkg_idx, pl_it = match
                        used_pkg.add(pkg_idx)
                        if not item.get("package_count"):
                            item["package_count"] = pl_it.get("packages_count")
                        if not item.get("package_type"):
                            item["package_type"] = pl_it.get("package_type") or packing.get("package_type")
                        pkg_assigned += 1

        # Если PL не дал per-item упаковку — проставить общий тип из PL (хотя бы тип)
        if pkg_assigned == 0 and packing.get("package_type"):
            for item in items:
                if not item.get("package_type"):
                    item["package_type"] = packing.get("package_type")

        logger.info("packaging_assigned", items_with_pkg=pkg_assigned, total_items=len(items))

        # ── Гр. 31: формируем полное описание (пункт 1 + пункт 2) ──
        # Пункт 1: наименование товара (уже в description — из тех.описания или инвойса)
        # Пункт 2: грузовые места и упаковка из PL
        for item in items:
            pkg_parts = []
            pc = item.get("package_count")
            pt = item.get("package_type")
            if pc:
                pkg_parts.append(f"{pc}")
            if pt:
                pkg_parts.append(pt)
            if pkg_parts:
                pkg_line = "2. Грузовые места: " + ", ".join(pkg_parts)
                desc = item.get("description") or ""
                if desc and pkg_line not in desc:
                    item["description"] = f"1. {desc}\n{pkg_line}"

        # Суммарные веса из позиций
        if items and (total_gross is None or total_net is None):
            gross_sum = sum((_safe_float(it.get("gross_weight")) or 0.0) for it in items)
            net_sum = sum((_safe_float(it.get("net_weight")) or 0.0) for it in items)
            if total_gross is None and gross_sum > 0:
                total_gross = round(gross_sum, 3)
            if total_net is None and net_sum > 0:
                total_net = round(net_sum, 3)
            logger.info("weights_from_items", total_gross=total_gross, total_net=total_net)

        # HS classification moved to process_documents() to avoid duplication

        # Transport from AWB — extract AWB number
        import re as _re
        # AWB номер: сначала из LLM-разбора транспортного документа, затем regex fallback
        awb_number = transport.get("awb_number")
        if not awb_number:
            awb_raw = transport.get("raw_text", "")
            if awb_raw:
                awb_match = _re.search(r'(\d{3})[- ]?(\d{8})', awb_raw)
                if awb_match:
                    awb_number = f"{awb_match.group(1)}-{awb_match.group(2)}"

        # Transport type (гр. 25): определяем из транспортного инвойса, документа или по типу документа
        transport_type = None
        if transport_inv.get("transport_type"):
            transport_type = str(transport_inv["transport_type"])
        elif transport.get("transport_type"):
            transport_type = str(transport["transport_type"])
        elif awb_number:
            transport_type = "40"  # AWB → воздушный
        if not transport_type:
            raw_transport = (transport.get("raw_text") or "").lower()
            if "cmr" in raw_transport or "consignment note" in raw_transport:
                transport_type = "30"  # авто
            elif "bill of lading" in raw_transport or "b/l" in raw_transport:
                transport_type = "10"  # морской
            elif "airway" in raw_transport or "awb" in raw_transport:
                transport_type = "40"  # воздушный
            else:
                transport_type = "40"
                logger.warning("transport_type_default", msg="Не удалось определить вид транспорта из документов, используется дефолт 40 (воздушный)")

        # AWB номер: из транспортного документа или транспортного инвойса
        if not awb_number and transport_inv.get("awb_number"):
            awb_number = transport_inv["awb_number"]

        # ── Гр. 29: Таможня на границе ──────────────────────────────────────────
        # Приоритет определения:
        #   1) IATA-код аэропорта назначения из транспортного документа (AWB/CMR/B/L)
        #   2) Regex-поиск "DEST:" в тексте транспортного документа
        #   3) Префикс AWB-номера (код авиакомпании)
        #   4) Дефолт для воздушного транспорта

        # Справочник: IATA-код аэропорта / ИКАО → (код таможенного органа, наименование, адрес места нахождения)
        _DESTINATION_TO_POST: dict[str, tuple[str, str, str]] = {
            # Москва — Шереметьево (Грузовой)
            "SVO":  ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
            "SVO2": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
            "UUEE": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),
            # Москва — Внуково
            "VKO":  ("10005030", "Т/П Аэропорт Внуково",                "г. Москва, Внуковское шоссе, д. 4"),
            "UUWW": ("10005030", "Т/П Аэропорт Внуково",                "г. Москва, Внуковское шоссе, д. 4"),
            # Москва — Домодедово
            "DME":  ("10009100", "Т/П Аэропорт Домодедово",             "Московская обл., г.о. Домодедово, Аэропорт Домодедово"),
            "UUDD": ("10009100", "Т/П Аэропорт Домодедово",             "Московская обл., г.о. Домодедово, Аэропорт Домодедово"),
            # Москва — Жуковский
            "ZIA":  ("10005040", "Т/П Аэропорт Жуковский",              "Московская обл., г.о. Жуковский, Аэропорт Жуковский"),
            "UUBW": ("10005040", "Т/П Аэропорт Жуковский",              "Московская обл., г.о. Жуковский, Аэропорт Жуковский"),
            # Санкт-Петербург — Пулково
            "LED":  ("10206020", "Т/П Аэропорт Пулково",                "г. Санкт-Петербург, Аэропорт Пулково, Пулковское ш."),
            "ULLI": ("10206020", "Т/П Аэропорт Пулково",                "г. Санкт-Петербург, Аэропорт Пулково, Пулковское ш."),
            # Екатеринбург — Кольцово
            "SVX":  ("10502050", "Т/П Аэропорт Кольцово",               "Свердловская обл., г. Екатеринбург, Аэропорт Кольцово"),
            "USSS": ("10502050", "Т/П Аэропорт Кольцово",               "Свердловская обл., г. Екатеринбург, Аэропорт Кольцово"),
            # Новосибирск — Толмачёво
            "OVB":  ("10609040", "Т/П Аэропорт Толмачёво",              "Новосибирская обл., г. Новосибирск, Аэропорт Толмачёво"),
            "UNNT": ("10609040", "Т/П Аэропорт Толмачёво",              "Новосибирская обл., г. Новосибирск, Аэропорт Толмачёво"),
            # Красноярск — Емельяново
            "KJA":  ("10614040", "Т/П Аэропорт Красноярск (Емельяново)", "Красноярский край, г. Красноярск, Аэропорт Емельяново"),
            "UNKL": ("10614040", "Т/П Аэропорт Красноярск (Емельяново)", "Красноярский край, г. Красноярск, Аэропорт Емельяново"),
            # Владивосток — Кневичи
            "VVO":  ("10702030", "Т/П Аэропорт Владивосток",            "Приморский край, г. Владивосток, Аэропорт Кневичи"),
            "UHWW": ("10702030", "Т/П Аэропорт Владивосток",            "Приморский край, г. Владивосток, Аэропорт Кневичи"),
            # Хабаровск — Новый
            "KHV":  ("10703040", "Т/П Аэропорт Хабаровск",             "Хабаровский край, г. Хабаровск, Аэропорт Новый"),
            "UHHH": ("10703040", "Т/П Аэропорт Хабаровск",             "Хабаровский край, г. Хабаровск, Аэропорт Новый"),
            # Казань
            "KZN":  ("10404080", "Т/П Аэропорт Казань",                 "Республика Татарстан, г. Казань, Аэропорт Казань"),
            "UWKD": ("10404080", "Т/П Аэропорт Казань",                 "Республика Татарстан, г. Казань, Аэропорт Казань"),
            # Уфа
            "UFA":  ("10401060", "Т/П Аэропорт Уфа",                    "Республика Башкортостан, г. Уфа, Аэропорт Уфа"),
            "UWUU": ("10401060", "Т/П Аэропорт Уфа",                    "Республика Башкортостан, г. Уфа, Аэропорт Уфа"),
            # Самара — Курумоч
            "KUF":  ("10412030", "Т/П Аэропорт Самара (Курумоч)",       "Самарская обл., г. Самара, Аэропорт Курумоч"),
            "UWWW": ("10412030", "Т/П Аэропорт Самара (Курумоч)",       "Самарская обл., г. Самара, Аэропорт Курумоч"),
            # Ростов-на-Дону — Платов
            "ROV":  ("10313110", "Т/П Аэропорт Ростов-на-Дону (Платов)", "Ростовская обл., г. Ростов-на-Дону, Аэропорт Платов"),
            "URRP": ("10313110", "Т/П Аэропорт Ростов-на-Дону (Платов)", "Ростовская обл., г. Ростов-на-Дону, Аэропорт Платов"),
            # Краснодар — Пашковский
            "KRR":  ("10309110", "Т/П Аэропорт Краснодар (Пашковский)", "Краснодарский край, г. Краснодар, Аэропорт Пашковский"),
            "URKK": ("10309110", "Т/П Аэропорт Краснодар (Пашковский)", "Краснодарский край, г. Краснодар, Аэропорт Пашковский"),
            # Сочи — Адлер
            "AER":  ("10317110", "Т/П Аэропорт Сочи",                   "Краснодарский край, г. Сочи, Аэропорт Адлер"),
            "URSS": ("10317110", "Т/П Аэропорт Сочи",                   "Краснодарский край, г. Сочи, Аэропорт Адлер"),
            # Иркутск
            "IKT":  ("10607040", "Т/П Аэропорт Иркутск",                "Иркутская обл., г. Иркутск, Аэропорт Иркутск"),
            "UIII": ("10607040", "Т/П Аэропорт Иркутск",                "Иркутская обл., г. Иркутск, Аэропорт Иркутск"),
            # Омск — Центральный
            "OMS":  ("10610040", "Т/П Аэропорт Омск (Центральный)",     "Омская обл., г. Омск, Аэропорт Центральный"),
            "UNOO": ("10610040", "Т/П Аэропорт Омск (Центральный)",     "Омская обл., г. Омск, Аэропорт Центральный"),
            # Тюмень — Рощино
            "TJM":  ("10503050", "Т/П Аэропорт Тюмень (Рощино)",        "Тюменская обл., г. Тюмень, Аэропорт Рощино"),
            "USTR": ("10503050", "Т/П Аэропорт Тюмень (Рощино)",        "Тюменская обл., г. Тюмень, Аэропорт Рощино"),
            # Нижний Новгород — Стригино
            "GOJ":  ("10408030", "Т/П Аэропорт Нижний Новгород (Стригино)", "Нижегородская обл., г. Нижний Новгород, Аэропорт Стригино"),
            "UWGG": ("10408030", "Т/П Аэропорт Нижний Новгород (Стригино)", "Нижегородская обл., г. Нижний Новгород, Аэропорт Стригино"),
            # Пермь — Большое Савино
            "PEE":  ("10411070", "Т/П Аэропорт Пермь (Большое Савино)", "Пермский край, г. Пермь, Аэропорт Большое Савино"),
            "USPP": ("10411070", "Т/П Аэропорт Пермь (Большое Савино)", "Пермский край, г. Пермь, Аэропорт Большое Савино"),
            # Минеральные Воды
            "MRV":  ("10802050", "Т/П Аэропорт Минеральные Воды",       "Ставропольский край, г. Минеральные Воды, Аэропорт Минеральные Воды"),
            "URMM": ("10802050", "Т/П Аэропорт Минеральные Воды",       "Ставропольский край, г. Минеральные Воды, Аэропорт Минеральные Воды"),
            # Калининград — Храброво
            "KGD":  ("10012030", "Т/П Аэропорт Калининград (Храброво)", "Калининградская обл., г. Калининград, Аэропорт Храброво"),
            "UMKK": ("10012030", "Т/П Аэропорт Калининград (Храброво)", "Калининградская обл., г. Калининград, Аэропорт Храброво"),
            # Мурманск
            "MMK":  ("10207070", "Т/П Аэропорт Мурманск",               "Мурманская обл., г. Мурманск, Аэропорт Мурманск"),
            "ULMM": ("10207070", "Т/П Аэропорт Мурманск",               "Мурманская обл., г. Мурманск, Аэропорт Мурманск"),
            # Якутск
            "YKS":  ("10704030", "Т/П Аэропорт Якутск",                 "Республика Саха (Якутия), г. Якутск, Аэропорт Якутск"),
            "UEEE": ("10704030", "Т/П Аэропорт Якутск",                 "Республика Саха (Якутия), г. Якутск, Аэропорт Якутск"),
            # Магадан — Сокол
            "GDX":  ("10706040", "Т/П Аэропорт Магадан (Сокол)",        "Магаданская обл., г. Магадан, Аэропорт Сокол"),
            "UHMM": ("10706040", "Т/П Аэропорт Магадан (Сокол)",        "Магаданская обл., г. Магадан, Аэропорт Сокол"),
            # Петропавловск-Камчатский — Елизово
            "PKC":  ("10705030", "Т/П Аэропорт Петропавловск-Камчатский", "Камчатский край, г. Петропавловск-Камчатский, Аэропорт Елизово"),
            "UHPP": ("10705030", "Т/П Аэропорт Петропавловск-Камчатский", "Камчатский край, г. Петропавловск-Камчатский, Аэропорт Елизово"),
            # Южно-Сахалинск — Хомутово
            "UUS":  ("10707050", "Т/П Аэропорт Южно-Сахалинск",         "Сахалинская обл., г. Южно-Сахалинск, Аэропорт Хомутово"),
            "UHSS": ("10707050", "Т/П Аэропорт Южно-Сахалинск",         "Сахалинская обл., г. Южно-Сахалинск, Аэропорт Хомутово"),
            # Челябинск — Баландино
            "CEK":  ("10504050", "Т/П Аэропорт Челябинск (Баландино)",  "Челябинская обл., г. Челябинск, Аэропорт Баландино"),
            "USCC": ("10504050", "Т/П Аэропорт Челябинск (Баландино)",  "Челябинская обл., г. Челябинск, Аэропорт Баландино"),
            # Воронеж — Чертовицкое
            "VOZ":  ("10104030", "Т/П Аэропорт Воронеж (Чертовицкое)",  "Воронежская обл., г. Воронеж, Аэропорт Чертовицкое"),
            "UUOO": ("10104030", "Т/П Аэропорт Воронеж (Чертовицкое)",  "Воронежская обл., г. Воронеж, Аэропорт Чертовицкое"),
        }

        # Fallback по префиксу AWB (IATA-код авиакомпании → аэропорт базирования для грузов в РФ)
        _AWB_PREFIX_TO_POST: dict[str, tuple[str, str, str]] = {
            "999": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),  # Air China Cargo
            "784": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),  # Aeroflot Cargo
            "555": ("10009100", "Т/П Аэропорт Домодедово",             "Московская обл., г.о. Домодедово, Аэропорт Домодедово"),                   # UPS
            "880": ("10005030", "Т/П Аэропорт Внуково",                "г. Москва, Внуковское шоссе, д. 4"),                                       # DHL
            "176": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),  # Emirates
            "074": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),  # KLM
            "172": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),  # Lufthansa Cargo
            "580": ("10005020", "Т/П Аэропорт Шереметьево (Грузовой)", "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш."),  # Turkish Airlines
            "728": ("10005030", "Т/П Аэропорт Внуково",                "г. Москва, Внуковское шоссе, д. 4"),                                       # UTair
        }

        _DEFAULT_POST: tuple[str, str, str] = (
            "10005020",
            "Т/П Аэропорт Шереметьево (Грузовой)",
            "Московская обл., г.о. Химки, Аэропорт Шереметьево, Шереметьевское ш.",
        )

        customs_office_code: Optional[str] = None
        customs_office_name: Optional[str] = None
        goods_location: Optional[str] = None

        # Priority 1: IATA-код назначения из LLM-разбора транспортного документа
        destination_airport = (transport.get("destination_airport") or "").upper().strip()

        # Priority 2 (regex fallback): "DEST: SVO2" в тексте AWB или транспортного инвойса
        if not destination_airport:
            for _raw_src in (transport.get("raw_text") or "", str(transport_inv)):
                _dest_m = re.search(r'\bDEST\s*[:\-]?\s*([A-Z]{3,4})\b', _raw_src, re.IGNORECASE)
                if _dest_m:
                    destination_airport = _dest_m.group(1).upper()
                    logger.info("destination_from_regex", destination=destination_airport)
                    break

        if destination_airport and destination_airport in _DESTINATION_TO_POST:
            customs_office_code, customs_office_name, goods_location = _DESTINATION_TO_POST[destination_airport]
            logger.info("customs_from_destination", destination=destination_airport,
                        code=customs_office_code, name=customs_office_name)

        # Priority 3: префикс AWB-номера
        if not customs_office_code and awb_number:
            awb_prefix = awb_number.split("-")[0] if "-" in awb_number else awb_number[:3]
            if awb_prefix in _AWB_PREFIX_TO_POST:
                customs_office_code, customs_office_name, goods_location = _AWB_PREFIX_TO_POST[awb_prefix]
                logger.info("customs_from_awb_prefix", prefix=awb_prefix,
                            code=customs_office_code, name=customs_office_name)

        # Priority 4: fallback — воздушный транспорт → Шереметьево (Грузовой)
        if not customs_office_code and transport_type == "40":
            customs_office_code, customs_office_name, goods_location = _DEFAULT_POST
            logger.warning("customs_office_fallback_default", code=customs_office_code,
                           reason="destination и AWB-prefix не определены")

        # Гр. 22: валюта — ТОЛЬКО из контракта (единственный источник по правилам).
        currency = contract.get("currency")
        if not currency:
            logger.warning("currency_not_in_contract",
                           msg="Валюта не найдена в контракте — гр.22 требует ручного ввода")
        # Сумма — из инвойса на товары (спецификация не источник суммы)
        total_amount = inv.get("total_amount")

        # Проверка расхождения валют инвойса и контракта (гр. 42)
        inv_currency = inv.get("currency")
        contract_currency = contract.get("currency")
        if inv_currency and contract_currency and inv_currency.upper() != contract_currency.upper():
            logger.warning(
                "currency_mismatch_invoice_vs_contract",
                invoice_currency=inv_currency,
                contract_currency=contract_currency,
                msg=(
                    f"Валюта инвойса ({inv_currency}) ≠ валюте контракта ({contract_currency}). "
                    f"Граф 42: стоимость позиций требует пересчёта по курсу ЦБ на дату инвойса."
                ),
            )

        # ── Evidence tracking ──
        sender_src = "transport_doc" if transport_shipper else ("application" if app_forwarder else "transport_invoice")
        ev.record("seller", sender, sender_src, confidence=0.9 if sender_src == "transport_doc" else 0.8, graph=2)
        buyer_src = "contract" if contract.get("buyer") or contract.get("buyer_name") else "invoice"
        ev.record("buyer", buyer, buyer_src, confidence=0.85 if buyer_src == "contract" else 0.8, graph=14)
        if consignee_data:
            ev.record("consignee", consignee_data, "transport_doc", confidence=0.9, graph=8)
        else:
            ev.record("consignee", "СМ. ГРАФУ 14 ДТ", "transport_doc", confidence=1.0, graph=8)
        ev.record("currency", currency, "contract", confidence=0.97 if currency else 0.3, graph=22)
        ev.record("total_amount", total_amount, "invoice", confidence=0.85, graph=22)
        # Графа 20: Инкотермс.
        # Приоритет источников: 1) Заявка, 2) Контракт, 3) Спецификация.
        # Инвойс НЕ является источником условий поставки.
        # Если delivery_place — только страна (не город), уточняем пунктом
        # отправления из транспортного документа.
        app_inco = application.get("incoterms")
        contract_inco = contract.get("incoterms")
        spec_inco = spec.get("incoterms")

        if app_inco:
            inco_val = app_inco
            inco_src = "application"
            inco_confidence = 0.90
        elif contract_inco:
            inco_val = contract_inco
            inco_src = "contract"
            inco_confidence = 0.85
        elif spec_inco:
            inco_val = spec_inco
            inco_src = "specification"
            inco_confidence = 0.80
        else:
            inco_val = None
            inco_src = "none"
            inco_confidence = 0.0

        delivery_place_val = (
            application.get("delivery_place")
            or contract.get("delivery_place")
            or spec.get("delivery_place")
        )

        _COUNTRY_ONLY_NAMES = {
            "china", "cn", "hong kong", "hk", "taiwan", "tw",
            "korea", "kr", "japan", "jp", "india", "in",
            "turkey", "tr", "germany", "de", "italy", "it",
            "usa", "us", "russia", "ru", "vietnam", "vn",
            "thailand", "th", "indonesia", "id", "malaysia", "my",
            "китай", "гонконг", "тайвань", "корея", "япония",
            "индия", "турция", "германия", "италия", "россия",
        }
        _DEST_CITIES_RU = {
            "moscow", "москва", "svo", "dme", "vko", "zia",
            "saint-petersburg", "санкт-петербург", "led", "пулково",
            "novosibirsk", "новосибирск", "ovb",
            "vladivostok", "владивосток", "vvo",
            "ekaterinburg", "екатеринбург", "svx",
            "kazan", "казань", "kzn",
            "krasnodar", "краснодар", "krr",
        }
        _SELLER_TERMS = {"EXW", "FCA", "FAS", "FOB"}

        _IATA_CITY = {
            "HKG": "HONG KONG", "SZX": "SHENZHEN", "PVG": "SHANGHAI",
            "SHA": "SHANGHAI", "CAN": "GUANGZHOU", "PEK": "BEIJING",
            "PKX": "BEIJING", "CTU": "CHENGDU", "CKG": "CHONGQING",
            "WUH": "WUHAN", "NKG": "NANJING", "HGH": "HANGZHOU",
            "XMN": "XIAMEN", "TAO": "QINGDAO", "DLC": "DALIAN",
            "TSN": "TIANJIN", "SJW": "SHIJIAZHUANG", "TNA": "JINAN",
            "ICN": "SEOUL", "NRT": "TOKYO", "TPE": "TAIPEI",
            "SGN": "HO CHI MINH", "BKK": "BANGKOK", "SIN": "SINGAPORE",
            "IST": "ISTANBUL", "FRA": "FRANKFURT", "DEL": "NEW DELHI",
        }

        transport_departure = transport.get("departure_airport") or transport.get("departure_point") or ""
        if transport_departure:
            transport_departure = _IATA_CITY.get(transport_departure.strip().upper(), transport_departure)
        _cur_inco = (inco_val or "").upper().strip()

        if delivery_place_val and delivery_place_val.strip().lower() in _COUNTRY_ONLY_NAMES:
            if transport_departure:
                logger.info("delivery_place_refined_by_transport",
                            original=delivery_place_val,
                            transport_departure=transport_departure,
                            msg=f"Графа 20: место поставки '{delivery_place_val}' — "
                                f"только страна, уточнено пунктом отправления "
                                f"из транспортного документа: '{transport_departure}'.")
                delivery_place_val = transport_departure
        elif (delivery_place_val and _cur_inco in _SELLER_TERMS
              and delivery_place_val.strip().lower() in _DEST_CITIES_RU):
            logger.warning("delivery_place_is_destination_city",
                           incoterms=_cur_inco, wrong_place=delivery_place_val,
                           transport_departure=transport_departure or None,
                           msg=f"Графа 20: для {_cur_inco} место поставки — город ПРОДАВЦА, "
                               f"а не назначения ('{delivery_place_val}')")
            if transport_departure:
                delivery_place_val = transport_departure
            else:
                delivery_place_val = None
        elif not delivery_place_val and transport_departure:
            delivery_place_val = transport_departure
            logger.info("delivery_place_from_transport",
                        transport_departure=transport_departure,
                        msg=f"Графа 20: место поставки не указано в заявке/контракте/"
                            f"спецификации, взято из транспортного документа: "
                            f"'{transport_departure}'.")

        ev.record("incoterms", inco_val, inco_src, confidence=inco_confidence, graph=20)

        app_place = application.get("delivery_place")
        if app_inco and contract_inco and app_inco.upper() != contract_inco.upper():
            logger.warning("incoterms_conflict_app_vs_contract",
                           application=f"{app_inco} {app_place or ''}".strip(),
                           contract=contract_inco,
                           msg=f"Графа 20: заявка ({app_inco} {app_place or ''}) ≠ контракт ({contract_inco}). "
                               f"Используются условия из заявки на перевозку.")
        if app_inco and spec_inco and app_inco.upper() != spec_inco.upper():
            logger.warning("incoterms_conflict_app_vs_spec",
                           application=f"{app_inco} {app_place or ''}".strip(),
                           specification=spec_inco,
                           msg=f"Графа 20: заявка ({app_inco} {app_place or ''}) ≠ спецификация ({spec_inco}). "
                               f"Используются условия из заявки на перевозку.")
        # Графа 16: агрегация страны происхождения из всех позиций
        _EU_COUNTRIES = {"AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU","IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE"}
        unique_origins = set()
        for it in items:
            co = (it.get("country_origin_code") or "").strip().upper()
            if co:
                unique_origins.add(co)
        if len(unique_origins) == 0:
            origin_val = None
        elif len(unique_origins) == 1:
            single = unique_origins.pop()
            origin_val = single
        elif unique_origins.issubset(_EU_COUNTRIES):
            origin_val = "EU"
        else:
            origin_val = "РАЗНЫЕ"
        ev.record("country_origin", origin_val, "aggregated_items", confidence=0.7, graph=16)
        ev.record("country_destination", "RU", "default", confidence=1.0, graph=17)
        ev.record("transport_type", transport_type,
                  "transport_invoice" if transport_inv.get("transport_type") else "default", confidence=0.8, graph=25)
        transport_id_val = transport.get("vehicle_id") or transport_inv.get("flight_number")
        ev.record("transport_id", transport_id_val, "transport_doc", confidence=0.9, graph=21)
        ev.record("transport_doc_number", awb_number, "transport_doc", confidence=0.9, graph=44)
        ev.record("customs_office_code", customs_office_code, "heuristic", confidence=0.7, graph=29)
        ev.record("goods_location", goods_location, "heuristic", confidence=0.6, graph=30)
        weight_src = "packing_list" if packing.get("total_gross_weight") else "invoice"
        ev.record("total_gross_weight", total_gross, weight_src, confidence=0.85, graph=35)
        ev.record("total_net_weight", total_net, weight_src, confidence=0.85, graph=38)
        ev.record("type_code", "IM40", "default", confidence=0.3, graph=1)
        ev.record("deal_nature_code", "01", "default", confidence=0.3, graph=24)
        ev.record("items", f"{len(items)} позиций", items_source, confidence=0.85, graph=31)
        contract_num = inv.get("contract_number") or contract.get("contract_number")
        ev.record("contract_number", contract_num,
                  "invoice" if inv.get("contract_number") else "contract", confidence=0.85)
        ev.record("declarant_inn_kpp", declarant_inn_kpp,
                  "contract" if contract.get("buyer") else "invoice", confidence=0.8, graph=14)

        # Гр. 11, 15, 19: страна контрагента, страна отправления, контейнер

        # Гр. 11: страна торгового партнёра = страна ПРОДАВЦА ПО КОНТРАКТУ.
        # НЕ путать с sender (отправитель из транспортного документа, Гр.2).
        # Пример: продавец ZED Group (HK) ≠ грузоотправитель HK SAN GENSHIN (CN).
        contract_seller = contract.get("seller") or {}
        contract_seller_cc = contract_seller.get("country_code") if isinstance(contract_seller, dict) else None
        trading_partner = (
            contract.get("seller_country")
            or contract_seller_cc
            or inv.get("seller_country")
        )

        # Гр. 15: страна отправления — откуда физически отправлен груз.
        # Источники: заявка на перевозку, транспортные документы, sender (Гр.2).
        sender_cc = sender.get("country_code") if sender and isinstance(sender, dict) else None
        country_dispatch_val = (
            application.get("country_dispatch")
            or sender_cc
        )

        # Гр. 19: контейнерная перевозка
        container_val = packing.get("container") if packing else None
        if container_val is None and transport_type:
            container_val = transport_type == "10"

        result = {
            "invoice_number": inv.get("invoice_number"),
            "invoice_date": inv.get("invoice_date"),
            "seller": sender,
            "buyer": buyer,
            "buyer_matches_declarant": buyer_matches_declarant,
            "consignee": consignee_data,
            "currency": currency,
            "total_amount": total_amount,
            "incoterms": inco_val,
            "trading_partner_country": trading_partner,
            "country_dispatch": (country_dispatch_val or "")[:2] or None,
            "country_origin": origin_val,
            "country_destination": inv.get("country_destination", "RU"),
            "container": container_val,
            "contract_number": contract_num,
            "contract_date": contract.get("contract_date"),
            "total_packages": packing.get("total_packages") or inv.get("total_packages"),
            "package_type": packing.get("package_type"),
            "total_gross_weight": total_gross,
            "total_net_weight": total_net,
            "transport_type": transport_type,
            "transport_doc_number": awb_number,
            "transport_id": transport.get("vehicle_id") or transport_inv.get("flight_number"),
            "transport_country_code": transport.get("transport_country_code"),
            "delivery_place": delivery_place_val,
            "customs_office_code": customs_office_code,
            "customs_office_name": customs_office_name,
            "goods_location": goods_location,
            "deal_nature_code": "01",
            "type_code": "IM40",
            "declarant_inn_kpp": declarant_inn_kpp,
            "responsible_person": responsible_person_data,
            "responsible_person_matches_declarant": responsible_person_matches_declarant,
            "items": items,
            "documents": self._build_documents_list(parsed_docs, inv, contract, awb_number),
            "freight_amount": transport_inv.get("freight_amount"),
            "freight_currency": transport_inv.get("freight_currency"),
            "insurance_amount": transport_inv.get("insurance_amount"),
            "insurance_currency": transport_inv.get("insurance_currency"),
            "loading_cost": transport_inv.get("loading_cost"),
            "loading_currency": transport_inv.get("loading_currency"),
        }

        # ── СВХ: данные склада временного хранения (гр. 30 / 49) ──
        if svh_doc:
            svh_number = svh_doc.get("svh_number")
            if svh_number:
                result["warehouse_requisites"] = svh_number
                result["goods_location_svh_doc_id"] = svh_number
                ev.record("warehouse_requisites", svh_number, "svh_doc", confidence=0.9, graph=49)
            wh_name = svh_doc.get("warehouse_name")
            if wh_name:
                result["warehouse_name"] = wh_name
                ev.record("warehouse_name", wh_name, "svh_doc", confidence=0.85, graph=30)
            logger.info("svh_integrated",
                        svh_number=svh_number, warehouse_name=wh_name)

        # ── Эталонная ГТД: reference data для перекрёстной проверки ──
        if reference_gtd:
            gtd_header = reference_gtd.get("header", {})
            gtd_items = reference_gtd.get("items", [])
            result["reference_gtd"] = {
                "filename": reference_gtd.get("filename"),
                "header": gtd_header,
                "items_count": len(gtd_items),
            }
            # Обогащение: если основные документы не дали HS-кодов — подтянуть из эталона
            if gtd_items and items:
                for item in items:
                    if item.get("hs_code"):
                        continue
                    desc = (item.get("description") or "").lower()
                    for g_item in gtd_items:
                        g_desc = (g_item.get("description") or "").lower()
                        if desc and g_desc and (desc[:30] in g_desc or g_desc[:30] in desc):
                            item["hs_code"] = g_item.get("hs_code", "")
                            item["hs_confidence"] = 0.75
                            item["hs_reasoning"] = f"Из эталонной ГТД: {reference_gtd.get('filename', '')}"
                            logger.info("hs_from_reference_gtd",
                                        description=desc[:50],
                                        hs_code=item["hs_code"])
                            break
            ev.record("reference_gtd", reference_gtd.get("filename"), "reference_gtd",
                      confidence=0.95, graph=0)

        buyer_src = "trilateral_contract" if (is_trilateral and not buyer_matches_declarant) else "default_see_graph_14"
        ev.record("buyer", buyer if not buyer_matches_declarant else "СМ. ГРАФУ 14 ДТ",
                  buyer_src, confidence=0.95, graph=8)
        rp_src = "trilateral_contract" if (is_trilateral and not responsible_person_matches_declarant) else "default_see_graph_14"
        ev.record("responsible_person",
                  responsible_person_data.get("name") if responsible_person_data else "СМ. ГРАФУ 14 ДТ",
                  rp_src, confidence=0.95, graph=9)
        tp_src = "contract" if (contract.get("seller_country") or contract_seller_cc) else "invoice"
        ev.record("trading_partner_country", trading_partner, tp_src, confidence=0.85, graph=11)
        cd_src = "application" if application.get("country_dispatch") else "sender"
        ev.record("country_dispatch", country_dispatch_val, cd_src, confidence=0.75, graph=15)
        ev.record("container", container_val, "transport_type" if transport_type else "unknown", confidence=0.6, graph=19)

        evidence_map = ev.to_dict()
        issues = validate_declaration(result, evidence_map)
        result["evidence_map"] = evidence_map
        result["issues"] = issues

        return result

    @staticmethod
    def _document_payload(obj) -> dict | None:
        """Подготовить лёгкий parsed_data для хранения в core-api Document."""
        data = DeclarationCrew._to_dict(obj)
        if not data:
            return None
        cleaned: dict = {}
        for key, value in data.items():
            if key in {"raw_text", "_cache_type"}:
                continue
            if isinstance(key, str) and key.startswith("_"):
                continue
            cleaned[key] = value
        return cleaned or None

    @staticmethod
    def _build_documents_list(parsed_docs: dict, inv: dict, contract: dict, awb_number: str | None) -> list[dict]:
        """Графа 44: перечень документов с кодами классификатора, номерами и датами."""
        import mimetypes

        _DOC_TYPE_CODES = {
            "invoice":               "04021",
            "contract":              "03011",
            "packing":               "04024",
            "packing_list":          "04024",
            "specification":         "04091",
            "transport_invoice":     "04025",
            "application_statement": "05999",
            "tech_description":      "05011",
            "insurance":             "03041",
            "payment_order":         "03031",
            "reference_gtd":         "09023",
            "svh_doc":               "09023",
            "certificate_origin":    "06019",
            "origin_certificate":    "06019",
            "license":               "01011",
            "permit":                "01999",
            "sanitary":              "07013",
            "veterinary":            "07012",
            "phytosanitary":         "07011",
            "conformity_declaration": "01191",
            "other":                 "09023",
        }
        _TRANSPORT_DOC_CODES = {
            "40": "02013",  # AWB
            "30": "02011",  # CMR
            "10": "02015",  # B/L
            "20": "02011",  # Railway
            "80": "02015",  # Inland waterway
        }
        _ORIGIN_CERT_CODES = {
            "CT-1":                  "06011",
            "Form A":                "06012",
            "EUR.1":                 "06013",
            "Declaration of Origin": "06021",
        }

        def _resolve_doc_code(doc_type: str, source_data) -> str:
            sd = DeclarationCrew._to_dict(source_data) if source_data else {}
            if doc_type in ("transport", "transport_doc"):
                tt = str(sd.get("transport_type", ""))
                return _TRANSPORT_DOC_CODES.get(tt, "02091")
            if doc_type in ("origin_certificate", "certificate_origin"):
                ct = str(sd.get("certificate_type", ""))
                return _ORIGIN_CERT_CODES.get(ct, "06019")
            return _DOC_TYPE_CODES.get(doc_type, "09023")
        docs: list[dict] = []

        def _append_doc(
            *,
            doc_type: str,
            doc_code: str,
            doc_type_name: str,
            parsed_source,
            doc_number: str | None = None,
            doc_date: str | None = None,
        ):
            source_dict = DeclarationCrew._to_dict(parsed_source)
            filename = source_dict.get("_filename")
            payload = DeclarationCrew._document_payload(source_dict)
            if not filename and not doc_number and not payload:
                return
            docs.append({
                "doc_type": doc_type,
                "doc_code": doc_code,
                "doc_number": doc_number,
                "doc_date": doc_date,
                "doc_type_name": doc_type_name,
                "original_filename": filename,
                "mime_type": mimetypes.guess_type(filename or "")[0] or "application/pdf",
                "parsed_data": payload,
            })

        _append_doc(
            doc_type="invoice",
            doc_code=_DOC_TYPE_CODES["invoice"],
            doc_type_name="Инвойс (счёт-фактура)",
            parsed_source=inv,
            doc_number=inv.get("invoice_number"),
            doc_date=inv.get("invoice_date"),
        )
        _append_doc(
            doc_type="contract",
            doc_code=_DOC_TYPE_CODES["contract"],
            doc_type_name="Контракт (договор)",
            parsed_source=contract,
            doc_number=contract.get("contract_number"),
            doc_date=contract.get("contract_date"),
        )

        transport_data = parsed_docs.get("transport") or {}
        _resolved_transport_code = _resolve_doc_code("transport_doc", transport_data)
        _TRANSPORT_DOC_NAMES = {
            "02013": "Авиационная накладная (AWB)",
            "02011": "Транспортная накладная (CMR)",
            "02015": "Коносамент (B/L)",
            "02091": "Транспортный документ",
        }
        _append_doc(
            doc_type="transport_doc",
            doc_code=_resolved_transport_code,
            doc_type_name=_TRANSPORT_DOC_NAMES.get(_resolved_transport_code, "Транспортный документ"),
            parsed_source=transport_data,
            doc_number=awb_number or transport_data.get("awb_number") or transport_data.get("vehicle_id"),
            doc_date=None,
        )

        packing_data = parsed_docs.get("packing") or {}
        _append_doc(
            doc_type="packing_list",
            doc_code=_DOC_TYPE_CODES["packing"],
            doc_type_name="Упаковочный лист",
            parsed_source=packing_data,
            doc_number=packing_data.get("packing_list_number") or packing_data.get("doc_number"),
            doc_date=packing_data.get("packing_list_date") or packing_data.get("doc_date"),
        )
        transport_inv_data = parsed_docs.get("transport_invoice") or {}
        _append_doc(
            doc_type="transport_invoice",
            doc_code=_DOC_TYPE_CODES["transport_invoice"],
            doc_type_name="Транспортный инвойс (фрахт)",
            parsed_source=transport_inv_data,
            doc_number=transport_inv_data.get("doc_number") or transport_inv_data.get("invoice_number"),
            doc_date=transport_inv_data.get("doc_date") or transport_inv_data.get("invoice_date"),
        )

        specification = parsed_docs.get("specification") or {}
        _append_doc(
            doc_type="specification",
            doc_code=_DOC_TYPE_CODES["specification"],
            doc_type_name="Спецификация",
            parsed_source=specification,
            doc_number=specification.get("doc_number"),
            doc_date=specification.get("doc_date"),
        )

        application_statement = parsed_docs.get("application_statement") or {}
        _append_doc(
            doc_type="application_statement",
            doc_code=_DOC_TYPE_CODES["application_statement"],
            doc_type_name="Заявка / поручение экспедитору",
            parsed_source=application_statement,
            doc_number=application_statement.get("doc_number"),
            doc_date=application_statement.get("doc_date"),
        )

        for tech_desc in parsed_docs.get("tech_descriptions") or []:
            _append_doc(
                doc_type="tech_description",
                doc_code=_DOC_TYPE_CODES["tech_description"],
                doc_type_name="Техническое описание",
                parsed_source=tech_desc,
                doc_number=tech_desc.get("doc_number"),
                doc_date=tech_desc.get("doc_date"),
            )

        for pay_order in parsed_docs.get("payment_orders") or []:
            _append_doc(
                doc_type="payment_order",
                doc_code=_DOC_TYPE_CODES["payment_order"],
                doc_type_name="Платёжное поручение",
                parsed_source=pay_order,
                doc_number=pay_order.get("doc_number"),
                doc_date=pay_order.get("doc_date"),
            )

        ref_gtd = parsed_docs.get("reference_gtd") or {}
        if ref_gtd:
            _append_doc(
                doc_type="reference_gtd",
                doc_code=_DOC_TYPE_CODES["reference_gtd"],
                doc_type_name="Эталонная ГТД (справочно)",
                parsed_source=ref_gtd,
                doc_number=ref_gtd.get("header", {}).get("customs_office_code"),
                doc_date=None,
            )

        svh = parsed_docs.get("svh_doc") or {}
        if svh:
            _append_doc(
                doc_type="svh_doc",
                doc_code=_DOC_TYPE_CODES["svh_doc"],
                doc_type_name="Документ СВХ",
                parsed_source=svh,
                doc_number=svh.get("svh_number"),
                doc_date=svh.get("placement_date"),
            )

        origin_cert = parsed_docs.get("origin_certificate") or {}
        if origin_cert:
            _cert_code = _resolve_doc_code("origin_certificate", origin_cert)
            _CERT_NAMES = {
                "06011": "Сертификат происхождения СТ-1",
                "06012": "Сертификат происхождения Form A",
                "06013": "Сертификат происхождения EUR.1",
                "06021": "Декларация о происхождении",
                "06019": "Сертификат происхождения",
            }
            _append_doc(
                doc_type="origin_certificate",
                doc_code=_cert_code,
                doc_type_name=_CERT_NAMES.get(_cert_code, "Сертификат происхождения"),
                parsed_source=origin_cert,
                doc_number=origin_cert.get("certificate_number"),
                doc_date=origin_cert.get("certificate_date"),
            )

        insurance_data = parsed_docs.get("insurance") or {}
        if insurance_data:
            _append_doc(
                doc_type="insurance",
                doc_code=_DOC_TYPE_CODES["insurance"],
                doc_type_name="Страховой полис / сертификат",
                parsed_source=insurance_data,
                doc_number=insurance_data.get("policy_number"),
                doc_date=insurance_data.get("issue_date"),
            )

        for conf_decl in parsed_docs.get("conformity_declarations") or []:
            _append_doc(
                doc_type="conformity_declaration",
                doc_code=_DOC_TYPE_CODES["conformity_declaration"],
                doc_type_name="Декларация о соответствии ЕАЭС",
                parsed_source=conf_decl,
                doc_number=conf_decl.get("declaration_number"),
                doc_date=conf_decl.get("registration_date"),
            )

        return docs

    # ------------------------------------------------------------------
    # NEW: LLM-only compilation pipeline (replaces _compile_declaration + _compile_by_rules)
    # ------------------------------------------------------------------

    def _compile_declaration_llm(self, parsed_docs: dict) -> dict:
        """LLM-based declaration compilation.

        Sends all extracted document data + filling rules to LLM.
        LLM handles semantic decisions: source priority, field selection,
        party identification, document type codes.
        Arithmetic, lookups and normalization are done in _post_process_compilation.
        """
        import json as _json
        from app.config import get_settings as _get_settings
        from app.services.llm_client import get_llm_client, get_model, json_format_kwargs
        from app.services.rules_engine import get_filling_rules_text

        settings = _get_settings()
        rules_text = build_full_rules_for_llm(section="header", core_api_url=settings.CORE_API_URL)
        filling_rules = get_filling_rules_text()

        docs_ctx = {}
        for doc_key, doc_data in parsed_docs.items():
            if doc_key.startswith("_"):
                continue
            data = self._to_dict(doc_data) if not isinstance(doc_data, list) else doc_data
            if not data:
                continue
            if isinstance(data, dict):
                cleaned = {k: v for k, v in data.items()
                           if v is not None and k not in ("raw_text", "_cache_type", "_filename")
                           and not (isinstance(k, str) and k.startswith("_"))}
                if doc_key == "specification" and cleaned:
                    cleaned.pop("items", None)
                    logger.info("spec_items_stripped_for_llm",
                                msg="Removed individual spec items from LLM context — "
                                    "only items_count/totals sent")
                if cleaned:
                    docs_ctx[doc_key] = cleaned
            elif isinstance(data, list):
                items_list = []
                for item in data:
                    if isinstance(item, dict):
                        c = {k: v for k, v in item.items()
                             if v is not None and k not in ("raw_text", "_cache_type", "_filename")}
                        if c:
                            items_list.append(c)
                if items_list:
                    docs_ctx[doc_key] = items_list

        docs_json = _json.dumps(docs_ctx, ensure_ascii=False, indent=2)

        from app.services.classifier_cache import get_cache
        _clf = get_cache()
        classifier_tables = (
            "СПРАВОЧНИК ВИДОВ ТРАНСПОРТА (гр.25/26): "
            + (_clf.format_for_prompt("transport_type") or "10—Морской|20—ЖД|30—Авто|40—Воздушный")
            + "\n"
            "СПРАВОЧНИК ХАРАКТЕРА СДЕЛКИ (гр.24, подраздел 1 — 2-значный код + '0'→3 цифры): "
            + (_clf.format_for_prompt("deal_nature") or "01—Купля-продажа|02—Бартер|03—Безвозмездная")
            + "\n"
            "СПРАВОЧНИК МОС (гр.43, подраздел 1): "
            + (_clf.format_for_prompt("mos_method") or "01—По цене сделки|02—Идентичные|03—Однородные")
            + "\n"
            "СПРАВОЧНИК ПРОЦЕДУР (гр.1/37): "
            + (_clf.format_for_prompt("procedure") or "IM40—Выпуск|IM51—Переработка")
            + "\n"
        )

        system_prompt = (
            "Ты опытный таможенный брокер РФ. Заполняешь таможенную декларацию ИМ40 (импорт).\n"
            "Тебе предоставлены извлечённые данные из документов и официальные правила.\n"
            "СТРОГО следуй правилам: приоритеты источников, форматы, специальные значения.\n"
            "Ответь ТОЛЬКО валидным JSON. Если данных нет — null. Не придумывай данные.\n"
            "НЕ делай арифметические расчёты (суммирование, распределение весов) — это сделает Python.\n\n"
            "ПРИОРИТЕТЫ ИСТОЧНИКОВ ПО ГРАФАМ (СТРОГО СОБЛЮДАЙ):\n"
            "- Графа 2 (seller / отправитель): ТОЛЬКО транспортные источники в порядке: "
            "1) transport (AWB/CMR/B/L) → shipper_name, "
            "2) application_statement → forwarding_agent или shipper, "
            "3) transport_invoice → shipper_name. "
            "Товарный инвойс (invoice.seller) и контракт (contract.seller) — это стороны СДЕЛКИ (гр.11), "
            "а НЕ грузоотправитель. Использовать их для seller ЗАПРЕЩЕНО.\n"
            "- Графа 14 (buyer / декларант): контракт > инвойс.\n"
            "- Графа 22 (currency / валюта): ТОЛЬКО из контракта.\n"
            "- Графа 11 (trading_partner_country): страна ПРОДАВЦА по контракту (contract.seller.country_code).\n\n"
            "ИСТОЧНИКИ ТОВАРНЫХ ПОЗИЦИЙ (items[]):\n"
            "- items[] формируются ТОЛЬКО из invoice (товарный инвойс). "
            "НЕ создавай позиции из specification, packing list или любого другого документа!\n"
            "- Specification (спецификация) — источник ТОЛЬКО для items_count (для сверки), "
            "incoterms и delivery_place. Спецификация НЕ источник товарных позиций!\n"
            "- Packing list — источник весов (gross_weight, net_weight) и упаковки, "
            "но НЕ источник товарных позиций.\n"
            "- Если один и тот же товар присутствует и в invoice, и в packing list — "
            "это ОДНА позиция, а не две. Бери описание/цену из invoice, веса из packing list.\n"
            "- Количество позиций в items[] должно СТРОГО совпадать с количеством товаров в инвойсе. "
            "Если в инвойсе 1 товар — в items[] должна быть 1 позиция, даже если в спецификации их больше.\n\n"
            "ОБРАБОТКА КОНФЛИКТОВ:\n"
            "- Если одно и то же поле содержит разные значения в разных документах, "
            "используй приоритеты источников для конкретной графы (см. выше). "
            "Для полей без специального приоритета: контракт > инвойс > упаковочный лист > транспортная накладная.\n"
            "- Добавь конфликт в issues[] с описанием: какие значения в каких документах.\n"
            "- Формат issue: {\"id\": \"conflict_<field>\", \"severity\": \"warning\", \"message\": \"описание\"}\n\n"
            "ГРАФА 20 (УСЛОВИЯ ПОСТАВКИ):\n"
            "- incoterms: ВСЕГДА указывай 3-буквенный код (EXW, FOB, CIF, FCA и т.д.)\n"
            "- delivery_place: город, написанный ПОСЛЕ кода Инкотермс в спецификации или контракте.\n"
            "  Для EXW/FCA/FOB/FAS — это город ПРОДАВЦА (отправления), НЕ город получателя.\n"
            "  Пример: если в спецификации написано 'EXW Hongkong', incoterms='EXW', delivery_place='Hongkong'."
        )

        user_prompt = f"""=== ИЗВЛЕЧЁННЫЕ ДАННЫЕ ИЗ ДОКУМЕНТОВ ===
{docs_json}

=== ПРАВИЛА ЗАПОЛНЕНИЯ ГРАФ ДТ (из БД) ===
{rules_text or ''}

=== ПРАВИЛА ЗАПОЛНЕНИЯ ГРАФ (полные) ===
{filling_rules or ''}

=== СПРАВОЧНИКИ КЛАССИФИКАТОРОВ (используй ТОЛЬКО коды из этих таблиц) ===
{classifier_tables}
=== ЗАДАЧА ===
На основе документов и правил заполни ВСЕ поля декларации, для которых есть данные.
Соблюдай приоритет источников для каждой графы.
Если между документами есть конфликтующие данные — выбери значение по приоритету и добавь issues[].

ФОРМАТ ОТВЕТА — JSON:
{{
  "type_code": "ИМ40 или другой код (гр.1)",
  "seller": {{"name": "...", "country_code": "ISO2", "address": "...", "inn": "...", "kpp": "...", "ogrn": "..."}},  // гр.2 ОТПРАВИТЕЛЬ: ТОЛЬКО из транспортных источников! 1) transport.shipper_name, 2) application_statement.forwarding_agent/shipper, 3) transport_invoice.shipper_name. НЕ из invoice.seller и НЕ из contract.seller!
  "buyer": {{"name": "...", "country_code": "ISO2", "address": "...", "inn": "...", "kpp": "...", "ogrn": "..."}},  // гр.14 ПОКУПАТЕЛЬ/ДЕКЛАРАНТ: name и address ОБЯЗАТЕЛЬНО на русском языке!
  "declarant": {{"name": "ТОЛЬКО НА РУССКОМ", "address": "ТОЛЬКО НА РУССКОМ", "inn": "...", "kpp": "...", "ogrn": "..."}},
  "buyer_matches_declarant": true,
  "consignee": null,
  "financial_responsible": null,
  "trading_partner_country": "ISO2 (гр.11)",
  "declarant_inn_kpp": "ИНН/КПП (гр.14)",
  "country_dispatch": "ISO2 (гр.15)",
  "country_origin": "ISO2 или РАЗНЫЕ/НЕИЗВЕСТНО/ЕВРОСОЮЗ (гр.16)",
  "country_destination": "ISO2 (гр.17, дефолт RU)",
  "departure_vehicle_info": "рег.номер/рейс/судно (гр.18)",
  "departure_vehicle_country": "ISO2 или 00/99 (гр.18)",
  "container": true/false,
  "incoterms": "3-буквенный код Инкотермс (гр.20): EXW/FCA/FOB/CIF и т.д.",
  "delivery_place": "город поставки из спецификации или контракта (гр.20)",
  "border_vehicle_info": "рейс/номер/судно (гр.21)",
  "border_vehicle_country": "ISO2 или 00/99 (гр.21)",
  "currency": "ISO4217 (гр.22) — ТОЛЬКО из контракта",
  "deal_nature_code": "3-значный код (гр.24, дефолт 010)",
  "deal_specifics_code": "2-значный код (гр.24, дефолт 01)",
  "transport_type": "10/20/30/40 (гр.25)",
  "transport_type_inland": "10/20/30/40 (гр.26)",
  "special_features_code": "код особенности или null (гр.7)",
  "contract_number": "номер контракта",
  "contract_date": "дата контракта",
  "invoice_number": "номер инвойса",
  "invoice_date": "дата инвойса",
  "transport_doc_number": "номер AWB/CMR/B-L",
  "destination_airport": "IATA код аэропорта назначения (для гр.29 lookup)",
  "total_packages": число (гр.6),
  "package_type": "тип упаковки",
  "freight_amount": число,
  "freight_currency": "ISO4217",
  "valuation_method": "1 (гр.43, дефолт)",
  "items": [
    {{
      "line_no": 1,
      "description": "наименование товара (из техописания если есть, иначе из инвойса)",
      "quantity": число,
      "unit": "единица измерения",
      "unit_price": число,
      "line_total": число,
      "country_origin_code": "ISO2 (гр.34)",
      "procedure_code": "4000 (гр.37)"
    }}
  ],
  "evidence_map": {{
    "seller": {{"source": "transport_doc", "confidence": 0.9, "graph": 2}},
    "buyer": {{"source": "contract", "confidence": 0.95, "graph": 14}},
    "currency": {{"source": "contract", "confidence": 0.97, "graph": 22}}
  }}
}}

JSON:"""

        try:
            client = get_llm_client(operation="compile_declaration_llm")
            resp = client.chat.completions.create(
                model=get_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=6000,
                **json_format_kwargs(),
            )
            raw = strip_code_fences(resp.choices[0].message.content)
            finish_reason = resp.choices[0].finish_reason

            if finish_reason == "length":
                logger.warning("compile_declaration_truncated_retrying")
                resp = client.chat.completions.create(
                    model=get_model(),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0,
                    max_tokens=10000,
                    **json_format_kwargs(),
                )
                raw = strip_code_fences(resp.choices[0].message.content)

            result = _json.loads(raw)
            logger.info("compile_declaration_llm_ok", fields=list(result.keys()),
                        items_count=len(result.get("items", [])))
            return result
        except Exception as e:
            logger.error("compile_declaration_llm_failed", error=str(e))
            return {"items": [], "evidence_map": {}, "issues": [
                {"id": "compile_llm_failed", "severity": "error", "message": f"LLM compilation failed: {e}"}
            ]}

    def _post_process_compilation(self, llm_result: dict, parsed_docs: dict) -> dict:
        """Deterministic post-processing after LLM compilation.

        Handles: IATA lookups, weight distribution, summing, normalization,
        item filtering, sheet count, description formatting.
        """
        import math
        result = dict(llm_result)

        # ── IATA -> customs office lookup (гр. 29, 30) ──
        destination_airport = (result.get("destination_airport") or "").upper().strip()
        if not destination_airport:
            awb = result.get("transport_doc_number") or ""
            for doc_key in ("transport", "transport_doc"):
                td = self._to_dict(parsed_docs.get(doc_key))
                if td:
                    destination_airport = (td.get("destination_airport") or "").upper().strip()
                    if destination_airport:
                        break

        customs_office_code = result.get("customs_office_code")
        customs_office_name = result.get("customs_office_name")
        goods_location = result.get("goods_location")

        if destination_airport and destination_airport in _DESTINATION_TO_POST:
            customs_office_code, customs_office_name, goods_location = _DESTINATION_TO_POST[destination_airport]

        awb_number = result.get("transport_doc_number") or ""
        if not customs_office_code and awb_number:
            prefix = awb_number.split("-")[0] if "-" in awb_number else awb_number[:3]
            if prefix in _AWB_PREFIX_TO_POST:
                customs_office_code, customs_office_name, goods_location = _AWB_PREFIX_TO_POST[prefix]

        transport_type = result.get("transport_type")
        if not customs_office_code and str(transport_type) == "40":
            customs_office_code, customs_office_name, goods_location = _DEFAULT_POST

        result["customs_office_code"] = customs_office_code
        result["customs_office_name"] = customs_office_name
        result["goods_location"] = goods_location

        # ── Transport vehicle info (гр. 18, 21, 44) from parsed docs ──
        td = self._to_dict(parsed_docs.get("transport")) or self._to_dict(parsed_docs.get("transport_doc"))
        if td:
            flight = td.get("flight_number") or td.get("flight_no") or ""
            awb = td.get("awb_number") or td.get("transport_doc_number") or ""
            vehicle_country = td.get("vehicle_country_code") or td.get("departure_country") or ""

            if flight and not result.get("departure_vehicle_info"):
                result["departure_vehicle_info"] = flight
            if flight and not result.get("border_vehicle_info"):
                result["border_vehicle_info"] = flight
            if awb and not result.get("transport_doc_number"):
                result["transport_doc_number"] = awb
            if vehicle_country and not result.get("departure_vehicle_country"):
                result["departure_vehicle_country"] = vehicle_country[:2].upper()
            if vehicle_country and not result.get("border_vehicle_country"):
                result["border_vehicle_country"] = vehicle_country[:2].upper()

        # ── Items processing ──
        items = result.get("items") or []
        inv_data = self._to_dict(parsed_docs.get("invoice"))
        packing_data = self._to_dict(parsed_docs.get("packing"))
        pl_items = (packing_data.get("items") or []) if packing_data else []

        inv_items = inv_data.get("items", []) if inv_data else []
        if inv_items and len(items) != len(inv_items):
            logger.warning(
                "items_count_mismatch_llm_vs_invoice",
                llm_count=len(items),
                invoice_count=len(inv_items),
                msg="LLM вернул другое количество позиций, чем в инвойсе — "
                    "принудительно используем позиции из инвойса",
            )
            items = list(inv_items)

        _SKIP_ITEM = re.compile(
            r'\b(freight|shipping|insurance|handling|delivery\s*fee|transport.*fee|'
            r'фрахт|доставка|страхов|транспортн)',
            re.IGNORECASE,
        )

        filtered_items = []
        for item in items:
            desc = item.get("description") or ""
            if _SKIP_ITEM.search(desc):
                continue
            if _is_garbage_desc(desc):
                continue
            item["hs_code"] = _normalize_hs_code(item.get("hs_code"))
            co = (item.get("country_origin_code") or "")
            if co:
                item["country_origin_code"] = co.strip().upper()[:2]
            filtered_items.append(item)
        items = filtered_items

        # ── Deduplication: LLM may create duplicates from invoice + packing list ──
        if len(items) > 1:
            def _dedup_key(it: dict) -> str:
                d = re.sub(r'[^a-zа-я0-9]', '', (it.get("description") or "").lower())
                return d

            seen_keys: dict[str, int] = {}
            deduplicated: list[dict] = []
            for item in items:
                key = _dedup_key(item)
                if not key:
                    deduplicated.append(item)
                    continue
                prev_idx = seen_keys.get(key)
                if prev_idx is not None:
                    prev = deduplicated[prev_idx]
                    prev_lt = _safe_float(prev.get("line_total")) or 0.0
                    cur_lt = _safe_float(item.get("line_total")) or 0.0
                    prev_up = _safe_float(prev.get("unit_price")) or 0.0
                    cur_up = _safe_float(item.get("unit_price")) or 0.0
                    if (prev_lt > 0 and cur_lt > 0 and abs(prev_lt - cur_lt) / max(prev_lt, cur_lt) < 0.05) or \
                       (prev_up > 0 and cur_up > 0 and abs(prev_up - cur_up) / max(prev_up, cur_up) < 0.05) or \
                       (prev_lt == 0 and cur_lt == 0):
                        for f in ("gross_weight", "net_weight", "package_count", "package_type"):
                            if item.get(f) and not prev.get(f):
                                prev[f] = item[f]
                        logger.warning("duplicate_item_removed",
                                       description=(item.get("description") or "")[:60],
                                       msg="Дубль позиции удалён (совпадение описания + цены)")
                        continue
                seen_keys[key] = len(deduplicated)
                deduplicated.append(item)

            if len(deduplicated) < len(items):
                logger.info("items_deduplicated",
                            before=len(items), after=len(deduplicated))
                items = deduplicated

        result["items"] = items

        # ── Weight distribution (гр. 35/38) ──
        items = self._distribute_weights(items, packing_data, inv_data)
        result["items"] = items

        # ── Sum totals ──
        total_gross = sum(_safe_float(it.get("gross_weight")) or 0.0 for it in items)
        total_net = sum(_safe_float(it.get("net_weight")) or 0.0 for it in items)
        if total_gross > 0:
            result["total_gross_weight"] = round(total_gross, 3)
        if total_net > 0:
            result["total_net_weight"] = round(total_net, 3)

        total_invoice = sum(_safe_float(it.get("line_total")) or 0.0 for it in items)
        invoice_total_amount = _safe_float(result.get("total_amount")) or 0.0

        if total_invoice > 0 and invoice_total_amount > 0:
            diff = abs(total_invoice - invoice_total_amount)
            threshold = max(invoice_total_amount, total_invoice) * 0.01
            if diff > threshold:
                logger.warning(
                    "graph22_vs_graph42_mismatch",
                    sum_items=round(total_invoice, 2),
                    invoice_total=round(invoice_total_amount, 2),
                    diff=round(diff, 2),
                    msg=(
                        f"Графа 22: сумма позиций (гр.42) = {round(total_invoice, 2)} "
                        f"≠ итогу инвойса = {round(invoice_total_amount, 2)}, "
                        f"расхождение {round(diff, 2)}"
                    ),
                )
                result.setdefault("issues", []).append({
                    "id": "graph22_vs_graph42_mismatch",
                    "severity": "warning",
                    "graph": 22,
                    "field": "total_amount",
                    "message": (
                        f"Графа 22: рассчитанная сумма позиций (∑ гр.42) = {round(total_invoice, 2)} "
                        f"не совпадает с итоговой суммой инвойса = {round(invoice_total_amount, 2)}. "
                        f"Расхождение: {round(diff, 2)}. Проверьте позиции и итог инвойса."
                    ),
                })
            result["total_amount"] = round(total_invoice, 2)
        elif total_invoice > 0:
            result["total_amount"] = round(total_invoice, 2)
            logger.info("graph22_from_items_sum", total=round(total_invoice, 2),
                        msg="Графа 22: итог инвойса отсутствует, сумма рассчитана из позиций")

        # ── Exchange rate (гр. 23) ──
        currency = (result.get("currency") or "").upper()
        exchange_rate = 0.0
        usd_rate = 0.0
        calc_debug = {}
        if currency and currency != "RUB":
            rates = _fetch_exchange_rates()
            exchange_rate = rates.get(currency, 0.0)
            usd_rate = rates.get("USD", 0.0)
            if exchange_rate > 0:
                result["exchange_rate"] = round(exchange_rate, 4)
                result["exchange_rate_currency"] = currency
                calc_debug["exchange_rate"] = exchange_rate
                calc_debug["usd_rate"] = usd_rate
                logger.info("exchange_rate_fetched", currency=currency, rate=exchange_rate)
            else:
                logger.warning("exchange_rate_not_found", currency=currency)
        elif currency == "RUB":
            exchange_rate = 1.0
            result["exchange_rate"] = 1.0
            result["exchange_rate_currency"] = "RUB"

        # ── Customs value (гр. 45) + freight distribution ──
        freight_amount = _safe_float(result.get("freight_amount")) or 0.0
        freight_currency = (result.get("freight_currency") or currency or "").upper()
        freight_rub = 0.0

        if freight_amount > 0 and exchange_rate > 0:
            if freight_currency == currency:
                freight_rub = freight_amount * exchange_rate
            elif freight_currency == "RUB":
                freight_rub = freight_amount
            else:
                rates = rates if 'rates' in dir() else _fetch_exchange_rates()
                fr_rate = rates.get(freight_currency, exchange_rate)
                freight_rub = freight_amount * fr_rate

        if exchange_rate > 0 and items:
            freight_distributed = []
            for item in items:
                line_total = _safe_float(item.get("line_total")) or 0.0
                item_value_rub = line_total * exchange_rate

                item_freight = 0.0
                if freight_rub > 0 and total_gross > 0:
                    item_gross = _safe_float(item.get("gross_weight")) or 0.0
                    item_freight = freight_rub * (item_gross / total_gross) if item_gross > 0 else 0.0
                    item_value_rub += item_freight

                if item_value_rub > 0:
                    item["customs_value_rub"] = round(item_value_rub, 2)
                    freight_distributed.append({
                        "description": (item.get("description") or "")[:60],
                        "line_total_fcy": line_total,
                        "line_total_rub": round(line_total * exchange_rate, 2),
                        "freight_share_rub": round(item_freight, 2),
                        "customs_value_rub": round(item_value_rub, 2),
                    })

            total_customs_value = sum(_safe_float(it.get("customs_value_rub")) or 0.0 for it in items)
            if total_customs_value > 0:
                result["total_customs_value"] = round(total_customs_value, 2)

            calc_debug["freight_rub"] = round(freight_rub, 2) if freight_rub > 0 else 0
            calc_debug["freight_distribution"] = freight_distributed
            calc_debug["total_customs_value"] = round(total_customs_value, 2)

            # ── Statistical value (гр. 46) ──
            if usd_rate <= 0 and currency != "USD":
                rates = _fetch_exchange_rates() if 'rates' not in dir() else rates
                usd_rate = rates.get("USD", 0.0)
            elif currency == "USD":
                usd_rate = exchange_rate

            if usd_rate > 0:
                for item in items:
                    cv = _safe_float(item.get("customs_value_rub")) or 0.0
                    if cv > 0:
                        item["statistical_value_usd"] = round(cv / usd_rate, 2)

                total_stat = sum(_safe_float(it.get("statistical_value_usd")) or 0.0 for it in items)
                if total_stat > 0:
                    result["total_statistical_value"] = round(total_stat, 2)
                calc_debug["total_statistical_value"] = round(total_stat, 2) if total_stat > 0 else 0

            logger.info("customs_values_calculated",
                        total_customs_value=result.get("total_customs_value"),
                        total_statistical_value=result.get("total_statistical_value"))

        # ── Preference code (гр. 36) ──
        origin_cert = parsed_docs.get("origin_certificate")
        cert_type = None
        trade_agreement = None
        if origin_cert and isinstance(origin_cert, dict):
            cert_type = origin_cert.get("certificate_type")
            trade_agreement = origin_cert.get("trade_agreement")

        preference_code = _determine_preference_code(cert_type, trade_agreement)
        result["preference_code"] = preference_code
        calc_debug["preference_code"] = preference_code
        calc_debug["origin_certificate_type"] = cert_type

        # ── Classifier validation (countries, currency, transport, procedure) ──
        from app.services.classifier_cache import get_cache as _get_clf_cache
        _clf = _get_clf_cache()
        issues = result.get("issues") or []

        _COUNTRY_FIELDS = (
            "country_dispatch", "country_destination", "country_origin",
            "trading_partner_country", "departure_vehicle_country",
            "border_vehicle_country",
        )
        for _cf in _COUNTRY_FIELDS:
            _cv = result.get(_cf)
            if _cv and isinstance(_cv, str) and _cv not in ("РАЗНЫЕ", "НЕИЗВЕСТНО", "ЕВРОСОЮЗ", "EU"):
                resolved = _clf.lookup_code("country", _cv)
                if resolved:
                    result[_cf] = resolved
                elif len(_cv) == 2 and _cv.upper().isalpha():
                    result[_cf] = _cv.upper()
                else:
                    issues.append({
                        "id": f"unknown_country_{_cf}",
                        "severity": "warning",
                        "message": f"Неизвестный код страны '{_cv}' в поле {_cf}",
                    })

        _cur = result.get("currency")
        if _cur and not _clf.validate_code("currency", _cur):
            resolved_cur = _clf.lookup_code("currency", _cur)
            if resolved_cur:
                result["currency"] = resolved_cur
            else:
                issues.append({
                    "id": "unknown_currency",
                    "severity": "warning",
                    "message": f"Неизвестный код валюты: {_cur}",
                })

        _tt = result.get("transport_type")
        if _tt and not _clf.validate_code("transport_type", str(_tt)):
            issues.append({
                "id": "unknown_transport_type",
                "severity": "warning",
                "message": f"Неизвестный код вида транспорта: {_tt}",
            })

        for _item in items:
            _ico = (_item.get("country_origin_code") or "").strip().upper()
            if _ico and len(_ico) == 2:
                _item["country_origin_code"] = _ico
            elif _ico:
                _resolved_co = _clf.lookup_code("country", _ico)
                if _resolved_co:
                    _item["country_origin_code"] = _resolved_co

        result["issues"] = issues

        # ── Инкотермс (гр. 20): детерминированная логика приоритетов ──
        # Приоритет: 1) заявка, 2) контракт, 3) спецификация.
        # Инвойс НЕ является источником. Если LLM уже вернул — перезаписываем
        # по строгому приоритету из extracted data, чтобы исключить ошибки LLM.
        application_d = self._to_dict(parsed_docs.get("application_statement"))
        contract_d = self._to_dict(parsed_docs.get("contract"))
        spec_d = self._to_dict(parsed_docs.get("specification"))
        transport_d = self._to_dict(parsed_docs.get("transport"))

        app_inco = application_d.get("incoterms") if application_d else None
        contract_inco = contract_d.get("incoterms") if contract_d else None
        spec_inco = spec_d.get("incoterms") if spec_d else None

        if app_inco:
            result["incoterms"] = app_inco
            inco_src = "application_statement"
        elif contract_inco:
            result["incoterms"] = contract_inco
            inco_src = "contract"
        elif spec_inco:
            result["incoterms"] = spec_inco
            inco_src = "specification"
        else:
            inco_src = "none"

        dp_val = (
            application_d.get("delivery_place") if application_d else None
        ) or (
            contract_d.get("delivery_place") if contract_d else None
        ) or (
            spec_d.get("delivery_place") if spec_d else None
        )

        _COUNTRY_ONLY = {
            "china", "cn", "hong kong", "hk", "taiwan", "tw",
            "korea", "kr", "japan", "jp", "india", "in",
            "turkey", "tr", "germany", "de", "italy", "it",
            "usa", "us", "russia", "ru", "vietnam", "vn",
            "thailand", "th", "indonesia", "id", "malaysia", "my",
            "китай", "гонконг", "тайвань", "корея", "япония",
            "индия", "турция", "германия", "италия", "россия",
        }

        _DESTINATION_CITIES_RU = {
            "moscow", "москва", "svo", "dme", "vko", "zia",
            "saint-petersburg", "санкт-петербург", "led", "пулково",
            "novosibirsk", "новосибирск", "ovb",
            "vladivostok", "владивосток", "vvo",
            "ekaterinburg", "екатеринбург", "svx",
            "kazan", "казань", "kzn",
            "krasnodar", "краснодар", "krr",
        }

        _SELLER_TERMS = {"EXW", "FCA", "FAS", "FOB"}

        _IATA_TO_CITY = {
            "HKG": "HONG KONG", "SZX": "SHENZHEN", "PVG": "SHANGHAI",
            "SHA": "SHANGHAI", "CAN": "GUANGZHOU", "PEK": "BEIJING",
            "PKX": "BEIJING", "CTU": "CHENGDU", "CKG": "CHONGQING",
            "WUH": "WUHAN", "NKG": "NANJING", "HGH": "HANGZHOU",
            "XMN": "XIAMEN", "TAO": "QINGDAO", "DLC": "DALIAN",
            "TSN": "TIANJIN", "SJW": "SHIJIAZHUANG", "TNA": "JINAN",
            "CGO": "ZHENGZHOU", "CSX": "CHANGSHA", "KMG": "KUNMING",
            "ICN": "SEOUL", "NRT": "TOKYO", "KIX": "OSAKA",
            "TPE": "TAIPEI", "SGN": "HO CHI MINH", "HAN": "HANOI",
            "BKK": "BANGKOK", "SIN": "SINGAPORE", "KUL": "KUALA LUMPUR",
            "CGK": "JAKARTA", "DEL": "NEW DELHI", "BOM": "MUMBAI",
            "IST": "ISTANBUL", "FRA": "FRANKFURT", "AMS": "AMSTERDAM",
            "MIL": "MILAN", "MXP": "MILAN", "CDG": "PARIS",
            "LHR": "LONDON", "MAD": "MADRID", "BCN": "BARCELONA",
        }

        def _resolve_iata(val: str) -> str:
            """Convert IATA code to city name if applicable."""
            upper = val.strip().upper()
            return _IATA_TO_CITY.get(upper, val)

        transport_departure = (
            (transport_d.get("departure_airport") if transport_d else None)
            or (transport_d.get("departure_point") if transport_d else None)
            or ""
        )
        if transport_departure:
            transport_departure = _resolve_iata(transport_departure)

        inco_code = (result.get("incoterms") or "").upper().strip()

        if dp_val and dp_val.strip().lower() in _COUNTRY_ONLY and transport_departure:
            logger.info("delivery_place_refined", original=dp_val, refined=transport_departure)
            dp_val = transport_departure
        elif dp_val and inco_code in _SELLER_TERMS and dp_val.strip().lower() in _DESTINATION_CITIES_RU:
            logger.warning("delivery_place_is_destination",
                           incoterms=inco_code, wrong_place=dp_val,
                           transport_departure=transport_departure or None,
                           msg=f"Графа 20: для {inco_code} место поставки должно быть "
                               f"городом ПРОДАВЦА, а не назначения ('{dp_val}')")
            if transport_departure:
                dp_val = transport_departure
            else:
                dp_val = None
        elif not dp_val and transport_departure:
            dp_val = transport_departure

        if dp_val:
            dp_val = _resolve_iata(dp_val)
            result["delivery_place"] = dp_val
        elif result.get("delivery_place") and inco_code in _SELLER_TERMS:
            llm_dp = result["delivery_place"].strip().lower()
            if llm_dp in _DESTINATION_CITIES_RU:
                logger.warning("delivery_place_llm_destination_removed",
                               incoterms=inco_code,
                               removed=result["delivery_place"],
                               msg=f"LLM указал '{result['delivery_place']}' как пункт поставки "
                                   f"для {inco_code} — это город назначения, удалён")
                result.pop("delivery_place", None)

        if result.get("incoterms"):
            logger.info("incoterms_postprocess",
                        incoterms=result["incoterms"],
                        delivery_place=result.get("delivery_place"),
                        source=inco_src)

        issues = result.get("issues") or []
        issues.append({
            "id": "preference_check",
            "severity": "warning",
            "graph": 36,
            "message": "Проверьте преференции (гр.36). Коды определены по умолчанию.",
        })
        result["issues"] = issues

        result["_calc_debug"] = calc_debug

        # ── Sheet count (гр. 3) ──
        n_items = len(items)
        if n_items > 0:
            total_sheets = 1 + math.ceil(max(0, n_items - 1) / 3) if n_items > 1 else 1
            result["total_sheets"] = total_sheets
            result["total_items_count"] = n_items

        # ── Description formatting (гр. 31) ──
        for item in items:
            desc = item.get("description") or ""
            pkg_parts = []
            pc = item.get("package_count") or item.get("packages_count")
            pt = item.get("package_type")
            if pc:
                pkg_parts.append(str(pc))
            if pt:
                pkg_parts.append(pt)
            if pkg_parts and desc:
                pkg_line = "2. Грузовые места: " + ", ".join(pkg_parts)
                if pkg_line not in desc:
                    item["description"] = f"1. {desc}\n{pkg_line}"

        # ── Country origin aggregation (гр. 16) ──
        _EU_COUNTRIES = {"AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR",
                         "HU","IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK",
                         "SI","ES","SE"}
        unique_origins = set()
        for it in items:
            co = (it.get("country_origin_code") or "").strip().upper()
            if co:
                unique_origins.add(co)
        if unique_origins:
            if len(unique_origins) == 1:
                result["country_origin"] = unique_origins.pop()
            elif unique_origins.issubset(_EU_COUNTRIES):
                result["country_origin"] = "EU"
            else:
                result["country_origin"] = "РАЗНЫЕ"

        # ── Documents list (гр. 44) ──
        if not result.get("documents"):
            result["documents"] = self._build_documents_list(
                parsed_docs,
                inv_data or {},
                self._to_dict(parsed_docs.get("contract")) or {},
                awb_number,
            )

        # ── Reference GTD enrichment ──
        ref_gtd = parsed_docs.get("reference_gtd")
        if ref_gtd and isinstance(ref_gtd, dict):
            gtd_items = ref_gtd.get("items", [])
            if gtd_items and items:
                for item in items:
                    if item.get("hs_code"):
                        continue
                    desc = (item.get("description") or "").lower()
                    for g_item in gtd_items:
                        g_desc = (g_item.get("description") or "").lower()
                        if desc and g_desc and (desc[:30] in g_desc or g_desc[:30] in desc):
                            item["hs_code"] = _normalize_hs_code(g_item.get("hs_code"))
                            item["hs_confidence"] = 0.75
                            item["hs_reasoning"] = f"Из эталонной ГТД"
                            break

        # ── SVH data (гр. 30/49) ──
        svh_doc = parsed_docs.get("svh_doc")
        if svh_doc and isinstance(svh_doc, dict):
            svh_number = svh_doc.get("svh_number")
            if svh_number:
                result["warehouse_requisites"] = svh_number
                result["goods_location_svh_doc_id"] = svh_number
            if svh_doc.get("warehouse_name"):
                result["warehouse_name"] = svh_doc["warehouse_name"]

        # ── Evidence map enrichment ──
        result = self._enrich_evidence_map(result, parsed_docs, inco_src)

        return result

    def _enrich_evidence_map(self, result: dict, parsed_docs: dict, inco_src: str) -> dict:
        """Fill gaps in evidence_map so every field with a value has a source."""
        ev = dict(result.get("evidence_map") or {})

        _KEY_RENAMES = {
            "transport_vehicle_border": "border_vehicle_info",
            "transport_vehicle_departure": "departure_vehicle_info",
            "transport_vehicle_border_country": "border_vehicle_country",
            "transport_vehicle_departure_country": "departure_vehicle_country",
            "transport_type_internal": "transport_type_inland",
        }
        for old_key, new_key in _KEY_RENAMES.items():
            if old_key in ev and new_key not in ev:
                ev[new_key] = ev.pop(old_key)
            elif old_key in ev:
                del ev[old_key]

        def _add(field: str, source: str, confidence: float,
                 graph: int | None = None, note: str = ""):
            if result.get(field) is None or field in ev:
                return
            entry: dict = {
                "value_preview": str(result[field])[:120],
                "source": source,
                "confidence": confidence,
            }
            if graph:
                entry["graph"] = graph
            if note:
                entry["note"] = note
            ev[field] = entry

        transport_d = self._to_dict(parsed_docs.get("transport"))

        _add("exchange_rate", "heuristic", 0.99, 23, "Курс ЦБ РФ")
        _add("total_customs_value", "aggregated_items", 0.95, 12, "Рассчитано из позиций")
        _add("total_gross_weight", "aggregated_items", 0.95, 35, "Сумма из позиций")
        _add("total_net_weight", "aggregated_items", 0.95, 38, "Сумма из позиций")
        _add("total_items_count", "heuristic", 1.0, 5, "Количество позиций")
        _add("total_sheets", "heuristic", 1.0, 3)
        _add("preference_code", "heuristic", 0.7, 36, "По умолчанию")
        _add("country_origin", "aggregated_items", 0.9, 16, "Из позиций")

        if result.get("incoterms") and "incoterms" not in ev:
            ev["incoterms"] = {
                "value_preview": str(result["incoterms"])[:120],
                "source": inco_src if inco_src != "none" else "heuristic",
                "confidence": 0.95 if inco_src != "none" else 0.5,
                "graph": 20,
            }
        if result.get("delivery_place") and "delivery_place" not in ev:
            dp_src = inco_src if inco_src != "none" else (
                "transport_doc" if transport_d else "heuristic"
            )
            ev["delivery_place"] = {
                "value_preview": str(result["delivery_place"])[:120],
                "source": dp_src,
                "confidence": 0.85,
                "graph": 20,
            }

        _add("customs_office_code", "heuristic", 0.9, 29, "Определён по IATA-коду")
        _add("goods_location", "heuristic", 0.9, 30, "Определён по IATA-коду")

        _add("invoice_number", "invoice", 0.95, 44)
        _add("invoice_date", "invoice", 0.95, 44)
        _add("contract_number", "contract", 0.95, 44)
        _add("contract_date", "contract", 0.95, 44)
        _add("total_amount", "invoice", 0.9, 22)
        _add("transport_doc_number", "transport_doc", 0.9, 44)
        _add("freight_amount", "transport_invoice", 0.9)
        _add("freight_currency", "transport_invoice", 0.9)
        _add("deal_nature_code", "contract", 0.85, 24)
        _add("deal_specifics_code", "contract", 0.8, 24)
        _add("type_code", "heuristic", 0.99, 1)

        _add("border_vehicle_info", "transport_doc", 0.9, 21)
        _add("departure_vehicle_info", "transport_doc", 0.9, 18)
        _add("border_vehicle_country", "transport_doc", 0.9, 21)
        _add("departure_vehicle_country", "transport_doc", 0.9, 18)
        _add("transport_type", "transport_doc", 0.9, 25)
        _add("transport_type_inland", "transport_doc", 0.8, 26)

        _add("country_dispatch", "transport_doc", 0.9, 15)
        _add("country_destination", "transport_doc", 0.9, 17)
        _add("trading_partner_country", "contract", 0.9, 11)

        # ── Item-level evidence (гр. 31-46) ──
        items = result.get("items") or []
        if items:
            inv_data = self._to_dict(parsed_docs.get("invoice"))
            packing_data = self._to_dict(parsed_docs.get("packing"))
            has_inv = bool(inv_data)
            has_pl = bool(packing_data)

            _ITEM_EV = {
                "description": ("invoice", 0.85, 31),
                "country_origin_code": ("conformity_declaration", 0.85, 34),
                "gross_weight": ("packing_list" if has_pl else "invoice", 0.9, 35),
                "net_weight": ("packing_list" if has_pl else "invoice", 0.85, 38),
                "additional_unit_qty": ("invoice", 0.85, 41),
                "unit_price": ("invoice", 0.9, 42),
                "customs_value_rub": ("heuristic", 0.95, 45),
                "statistical_value_usd": ("heuristic", 0.95, 46),
                "hs_code": ("heuristic", 0.8, 33),
                "procedure_code": ("heuristic", 0.9, 37),
                "preference_code": ("heuristic", 0.7, 36),
            }
            first_item = items[0] if items else {}
            for field, (src, conf, graph) in _ITEM_EV.items():
                if first_item.get(field) is not None and field not in ev:
                    note = ""
                    if src == "heuristic" and field == "customs_value_rub":
                        note = "Рассчитано: цена × курс + фрахт"
                    elif src == "heuristic" and field == "statistical_value_usd":
                        note = "Рассчитано: тамож. стоимость / курс USD"
                    entry: dict = {
                        "value_preview": str(first_item[field])[:120],
                        "source": src,
                        "confidence": conf,
                        "graph": graph,
                    }
                    if note:
                        entry["note"] = note
                    ev[field] = entry

        # ── Declarant / financial responsible (гр. 9, 14) ──
        contract_d = self._to_dict(parsed_docs.get("contract"))
        td_data = self._to_dict(parsed_docs.get("transport")) or self._to_dict(parsed_docs.get("transport_doc"))

        if result.get("declarant") and "declarant" not in ev:
            ev["declarant"] = {
                "value_preview": str(result["declarant"])[:120],
                "source": "contract" if contract_d else "transport_doc",
                "confidence": 0.9,
                "graph": 14,
            }
        if td_data and "declarant" not in ev:
            consignee = td_data.get("consignee_name") or td_data.get("consignee_inn")
            if consignee:
                ev["declarant"] = {
                    "value_preview": str(consignee)[:120],
                    "source": "transport_doc",
                    "confidence": 0.85,
                    "graph": 14,
                    "note": "Грузополучатель из AWB",
                }

        if "financial_responsible" not in ev and "responsible_person" not in ev:
            src = "contract" if contract_d else "transport_doc"
            ev["financial_responsible"] = {
                "value_preview": result.get("financial_responsible", result.get("buyer", {})
                    if isinstance(result.get("buyer"), dict) else ""),
                "source": src,
                "confidence": 0.85,
                "graph": 9,
            }

        result["evidence_map"] = ev
        logger.info("evidence_map_enriched", total_entries=len(ev),
                     keys=sorted(ev.keys()))
        return result

    def _distribute_weights(self, items: list, packing: dict | None, invoice: dict | None) -> list:
        """Distribute weights from PL to items, fallback to proportional by cost."""
        if not items:
            return items

        packing = packing or {}
        invoice = invoice or {}
        pl_items = packing.get("items") or []

        def _desc_similarity(a: str, b: str) -> float:
            wa = set(re.sub(r'[^a-zа-я0-9]', ' ', (a or "").lower()).split())
            wb = set(re.sub(r'[^a-zа-я0-9]', ' ', (b or "").lower()).split())
            if not wa or not wb:
                return 0.0
            return len(wa & wb) / max(len(wa), len(wb))

        pl_items_with_weights = [
            it for it in pl_items
            if _safe_float(it.get("gross_weight")) or _safe_float(it.get("net_weight"))
        ]

        weights_assigned = 0
        used_indices: set = set()

        if pl_items_with_weights:
            if len(pl_items_with_weights) == len(items):
                for j, item in enumerate(items):
                    pl_it = pl_items_with_weights[j]
                    pg = _safe_float(pl_it.get("gross_weight"))
                    pn = _safe_float(pl_it.get("net_weight"))
                    if pg and not item.get("gross_weight"):
                        item["gross_weight"] = round(pg, 3)
                    if pn and not item.get("net_weight"):
                        item["net_weight"] = round(pn, 3)
                    if pg or pn:
                        weights_assigned += 1
            else:
                for item in items:
                    best_score, best_match = 0.3, None
                    for idx, pl_it in enumerate(pl_items_with_weights):
                        if idx in used_indices:
                            continue
                        sim = _desc_similarity(item.get("description", ""), pl_it.get("description", ""))
                        if sim > best_score:
                            best_score = sim
                            best_match = (idx, pl_it)
                    if best_match:
                        idx, pl_it = best_match
                        used_indices.add(idx)
                        pg = _safe_float(pl_it.get("gross_weight"))
                        pn = _safe_float(pl_it.get("net_weight"))
                        if pg and not item.get("gross_weight"):
                            item["gross_weight"] = round(pg, 3)
                        if pn and not item.get("net_weight"):
                            item["net_weight"] = round(pn, 3)
                        if pg or pn:
                            weights_assigned += 1

        # Packaging from PL
        pl_pkg_items = [it for it in pl_items if it.get("packages_count") or it.get("package_type")]
        if pl_pkg_items and items:
            if len(pl_pkg_items) == len(items):
                for j, item in enumerate(items):
                    pl_it = pl_pkg_items[j]
                    if not item.get("package_count"):
                        item["package_count"] = pl_it.get("packages_count")
                    if not item.get("package_type"):
                        item["package_type"] = pl_it.get("package_type") or packing.get("package_type")
        if packing.get("package_type"):
            for item in items:
                if not item.get("package_type"):
                    item["package_type"] = packing["package_type"]

        # Fallback: proportional by cost
        total_gross = _safe_float(
            packing.get("total_gross_weight") or
            (invoice.get("total_gross_weight") if invoice else None)
        )
        total_net = _safe_float(
            packing.get("total_net_weight") or
            (invoice.get("total_net_weight") if invoice else None)
        )
        items_missing_weight = [it for it in items if not it.get("gross_weight")]
        if items_missing_weight and total_gross:
            assigned_gross = sum((_safe_float(it.get("gross_weight")) or 0.0) for it in items if it.get("gross_weight"))
            assigned_net = sum((_safe_float(it.get("net_weight")) or 0.0) for it in items if it.get("net_weight"))
            remaining_gross = max(0.0, (total_gross or 0.0) - assigned_gross)
            remaining_net = max(0.0, (total_net or 0.0) - assigned_net) if total_net else None

            total_price = sum((_safe_float(it.get("line_total")) or 0.0) for it in items_missing_weight)
            for item in items_missing_weight:
                price = _safe_float(item.get("line_total")) or 0.0
                share = (price / total_price) if total_price > 0 else (1.0 / len(items_missing_weight))
                item["gross_weight"] = round(remaining_gross * share, 3)
                if remaining_net:
                    item["net_weight"] = round(remaining_net * share, 3)
                elif item.get("gross_weight"):
                    item["net_weight"] = round(item["gross_weight"] * 0.9, 3)

        # Net weight fallback from gross
        for item in items:
            if item.get("gross_weight") and not item.get("net_weight"):
                item["net_weight"] = round(_safe_float(item["gross_weight"]) * 0.9, 3)

        return items

    # ------------------------------------------------------------------
    # LEGACY: _compile_by_rules (kept for reference, no longer called)
    # ------------------------------------------------------------------

    def _compile_by_rules_legacy(self, parsed_docs: dict, base_result: dict) -> dict:
        """Финальная LLM-компиляция декларации с полными правилами из БД.

        Берёт все извлечённые данные + полный текст правил для каждой графы
        и просит LLM заполнить поля декларации с соблюдением всех условий.
        Результат мержится поверх base_result (хардкод-компиляции).
        """
        import json as _json
        from app.config import get_settings as _get_settings
        from app.services.llm_client import get_llm_client, get_model

        settings = _get_settings()
        rules_text = build_full_rules_for_llm(section="header", core_api_url=settings.CORE_API_URL)
        if not rules_text:
            logger.warning("compile_by_rules_skipped", reason="no_rules_from_db")
            return base_result

        # ── Подготовка контекста документов ──────────────────────────────────
        inv = self._to_dict(parsed_docs.get("invoice"))
        contract = self._to_dict(parsed_docs.get("contract"))
        packing = self._to_dict(parsed_docs.get("packing"))
        spec = parsed_docs.get("specification") or {}
        transport_inv = parsed_docs.get("transport_invoice") or {}
        transport = parsed_docs.get("transport") or {}

        docs_ctx: dict = {}
        if inv:
            docs_ctx["invoice"] = {
                k: v for k, v in inv.items()
                if k not in ("items",) and v is not None
            }
        if contract:
            docs_ctx["contract"] = {
                k: v for k, v in contract.items()
                if v is not None
            }
        if packing:
            docs_ctx["packing_list"] = {
                k: v for k, v in packing.items()
                if k not in ("items",) and v is not None
            }
        if transport_inv:
            docs_ctx["transport_invoice"] = {
                k: v for k, v in transport_inv.items()
                if v is not None
            }
        if transport:
            transport_ctx: dict = {}
            if transport.get("shipper_name"):
                transport_ctx["shipper_name"] = transport["shipper_name"]
                transport_ctx["shipper_address"] = transport.get("shipper_address")
            if transport.get("vehicle_id"):
                transport_ctx["vehicle_id"] = transport["vehicle_id"]
            if transport.get("awb_number"):
                transport_ctx["awb_number"] = transport["awb_number"]
            if transport.get("transport_country_code"):
                transport_ctx["transport_country_code"] = transport["transport_country_code"]
            if transport_ctx:
                docs_ctx["transport_doc_parsed"] = transport_ctx
            if transport.get("raw_text"):
                docs_ctx["transport_doc_text"] = transport["raw_text"][:600]
        application_ctx = self._to_dict(parsed_docs.get("application_statement"))
        if application_ctx:
            docs_ctx["application_statement"] = {
                k: v for k, v in application_ctx.items() if v is not None
            }

        docs_json = _json.dumps(docs_ctx, ensure_ascii=False, indent=2)

        # ── Промпт ────────────────────────────────────────────────────────────
        system_prompt = (
            "Ты опытный таможенный брокер РФ. Заполняешь таможенную декларацию ИМ40 (импорт).\n"
            "Тебе предоставлены данные из документов и официальные правила заполнения каждой графы.\n"
            "ВАЖНО: строго следуй правилам — источникам, форматам, специальным значениям.\n"
            "Ответь ТОЛЬКО валидным JSON. Если данных нет — null. Не придумывай."
        )

        user_prompt = f"""=== ДАННЫЕ ИЗ ЗАГРУЖЕННЫХ ДОКУМЕНТОВ ===
{docs_json[:6000]}

=== ОФИЦИАЛЬНЫЕ ПРАВИЛА ЗАПОЛНЕНИЯ ГРАФ ДТ ===
{rules_text[:7000]}

=== ЗАДАЧА ===
На основе документов и правил заполни поля декларации.
Соблюдай: приоритет источников, специальные значения (СМ. ГРАФУ 14 ДТ, ЕВРОСОЮЗ, РАЗНЫЕ, 00, 99),
форматы (ISO 3166-1 alpha-2 для стран, ISO 4217 для валют, Инкотермс-коды).

Верни JSON со следующими полями (null если нет данных):
{{
  "type_code": "код типа декларации (гр.1), обычно ИМ 40",
  "seller": {{"name": "...", "country_code": "ISO2", "address": "...", "inn": "...", "kpp": "...", "ogrn": "..."}},  // гр.2 ОТПРАВИТЕЛЬ: ТОЛЬКО транспортные источники: 1) transport_doc.shipper, 2) application_statement.shipper, 3) transport_invoice.shipper. Товарный инвойс и контракт НЕ источники.
  "buyer": {{"name": "...", "country_code": "ISO2", "address": "...", "inn": "...", "kpp": "...", "ogrn": "..."}},  // гр.14 ПОКУПАТЕЛЬ/ДЕКЛАРАНТ: name и address ОБЯЗАТЕЛЬНО на русском языке! Если в контракте есть русский и английский вариант — выбирай РУССКИЙ.
  "responsible_person": "гр.9: 'СМ. ГРАФУ 14 ДТ' по умолчанию. Заполнять данными ТОЛЬКО при трёхстороннем договоре (is_trilateral=true).",
  "trading_partner_country": "гр.11: ISO2 страна контрагента",
  "declarant_inn_kpp": "гр.14: ИНН/КПП декларанта",
  "country_dispatch": "гр.15: ISO2 страна отправления",
  "country_origin": "гр.16: ISO2 страна происхождения (или ЕВРОСОЮЗ/РАЗНЫЕ/НЕИЗВЕСТНО)",
  "country_destination": "гр.17: ISO2 страна назначения",
  "container": true/false (гр.19),
  "incoterms": "гр.20: код Инкотермс (3 буквы: EXW/FCA/FOB/CIF и т.д.)",
  "delivery_place": "гр.20: город поставки из спецификации или контракта",
  "transport_id": "гр.21: номера/названия ТС через ;",
  "transport_country": "гр.21: ISO2 страна регистрации ТС или 00/99",
  "currency": "гр.22: ISO 4217 валюта",
  "total_amount": число (гр.22: общая фактурная стоимость),
  "deal_nature_code": "гр.24 подр.1: трёхзначный код характера сделки (010=купля-продажа, 020=бартер, 030=безвозмездная)",
  "contract_number": "гр.37: номер контракта",
  "contract_date": "гр.37: дата контракта ГГГГ-ММ-ДД",
  "special_features_code": "гр.7: код особенностей или null"
}}

JSON:"""

        try:
            client = get_llm_client(operation="compile_by_rules_llm")
            resp = client.chat.completions.create(
                model=get_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=2000,
            )
            raw = strip_code_fences(resp.choices[0].message.content)
            llm_result = _json.loads(raw)
            logger.info("compile_by_rules_ok", fields=list(llm_result.keys()))
        except Exception as e:
            logger.warning("compile_by_rules_llm_failed", error=str(e))
            return base_result

        # ── Мерж: LLM перекрывает хардкод там где вернул реальное значение ──
        # Поля, вычисленные в _compile_declaration со строгим приоритетом
        # источников, защищены от перезаписи LLM (если уже имеют значение).
        _PRIORITY_FIELDS = {
            "type_code", "deal_nature_code",
            "seller", "buyer", "buyer_matches_declarant", "consignee",
            "responsible_person", "responsible_person_matches_declarant",
            "transport_id", "transport_doc_number",
            "currency", "country_origin", "incoterms",
            "customs_office_code", "customs_office_name", "goods_location",
            "documents", "items", "evidence_map", "issues",
        }

        merged = dict(base_result)
        flagged: list[str] = []

        for key, value in llm_result.items():
            if value is None or value == "":
                continue
            if isinstance(value, str) and value.upper() in ("NULL", "NONE", "N/A", "Н/Д"):
                continue
            if key in _PRIORITY_FIELDS and base_result.get(key) is not None:
                continue
            merged[key] = value

        # Обновляем evidence_map: поля от compile_by_rules помечаем как источник "rules_llm"
        ev_map = merged.get("evidence_map") or {}
        for key in llm_result:
            if llm_result[key] is not None and key not in (
                "evidence_map", "issues", "items",
            ):
                if key not in ev_map:
                    ev_map[key] = {
                        "value_preview": str(llm_result[key])[:80],
                        "source": "rules_llm",
                        "confidence": 0.82,
                        "note": "Заполнено по правилам граф ДТ",
                    }
        merged["evidence_map"] = ev_map

        if flagged:
            existing_issues = merged.get("issues") or []
            for field in flagged:
                existing_issues.append({
                    "id": "rules_flag",
                    "severity": "info",
                    "field": field,
                    "graph": None,
                    "message": f"Поле «{field}» требует проверки пользователем",
                })
            merged["issues"] = existing_issues

        return merged
