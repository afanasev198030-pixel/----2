"""
CrewAI мультиагентная оркестрация.
Агенты: DocumentParser, HSClassifier, RiskAnalyzer, PrecedentLearner.
Fallback на линейный pipeline при недоступности CrewAI/OpenAI.
"""
import json
import re
from typing import Optional
import structlog

logger = structlog.get_logger()

_crewai_available = False
try:
    from crewai import Agent, Task, Crew, Process
    _crewai_available = True
except ImportError:
    logger.warning("crewai_not_available", msg="CrewAI not installed")

from app.services.dspy_modules import (
    InvoiceExtractor, ContractExtractor, PackingExtractor,
    HSCodeClassifier, RiskAnalyzer,
)
from app.services.index_manager import get_index_manager
from app.services.ocr_service import extract_text
from app.services.rules_engine import (
    EvidenceTracker, validate_declaration,
    build_graph_rules_prompt, get_source_priority_map,
    build_full_rules_for_llm, build_strategies_prompt,
)


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
            or (transport_score > goods_score and transport_score - goods_score >= 5)
        ) else "invoice",
    )

    # Транспортный: балл ≥ 15 ИЛИ превышает товарный на 5+ очков
    if transport_score >= 15 or (transport_score > goods_score and transport_score - goods_score >= 5):
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

    # --- По имени файла: однозначные типы ---
    if any(k in fn_lower for k in ["contract", "договор", "контракт"]):
        return "contract"
    if any(k in fn_lower for k in ["packing", "упаков", "packing_list", "packing-list"]):
        return "packing_list"
    if re.search(r'\bpl\b', fn_lower) and "inv" not in fn_lower:
        return "packing_list"
    if any(k in fn_lower for k in ["awb", "waybill", "накладная", "cmr"]):
        return "transport_doc"
    if any(k in fn_lower for k in ["spec", "спец"]):
        return "specification"
    if any(k in fn_lower for k in ["teh", "тех"]):
        return "tech_description"

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

    return "other"


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
      2. Общее количество позиций
      3. Уверенность парсера (confidence)
    """
    items = inv.get("items") or []
    good = _count_good_items(items)
    total = len(items)
    conf = inv.get("confidence") or 0.0
    return (good, total, conf)


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
        self._progress_callback = None

    def _progress(self, step: str, detail: str, pct: int):
        if self._progress_callback:
            try:
                self._progress_callback(step, detail, pct)
            except Exception:
                pass

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
                f"specs={tp.get('technical_specs', '')}  hs_desc={tp.get('suggested_hs_description', '')}"
                for i, tp in enumerate(tech_products)
            ])

            client = get_llm_client()
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
- description_ru: полное название товара для графы 31 ДТ (из тех.описания, на русском)
- hs_description: описание для классификации ТН ВЭД (из suggested_hs_description или составь сам — материал + назначение + тип)
- match_confidence: уверенность совпадения (0.0–1.0)

JSON: {{"matches": [...]}}"""},
                ],
                temperature=0,
                max_tokens=2000,
            )

            text = resp.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            matches = _json.loads(text).get("matches", [])

            result = [dict(it) for it in invoice_items]
            for m in matches:
                idx = (m.get("invoice_index") or 0) - 1
                if not (0 <= idx < len(result)):
                    continue
                desc_ru = (m.get("description_ru") or "").strip()
                hs_desc = (m.get("hs_description") or "").strip()
                conf = float(m.get("match_confidence") or 0.5)
                if desc_ru:
                    result[idx]["description_invoice"] = result[idx].get("description", "")
                    result[idx]["description"] = desc_ru
                    result[idx]["commercial_name"] = desc_ru
                    result[idx]["description_source"] = "tech_description"
                if hs_desc:
                    result[idx]["hs_description_for_classification"] = hs_desc
                result[idx]["techop_match_confidence"] = conf
                logger.info("techop_matched",
                            invoice_desc=(invoice_items[idx].get("description") or "")[:40],
                            tech_desc=desc_ru[:60], confidence=conf)
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
            from app.services.llm_client import get_llm_client, get_model

            # Собираем тексты для промпта
            doc_sections = []
            for d in docs:
                label = d["doc_type"].upper()
                text = d.get("text") or ""
                # For specification, items are often at the end. Take more text.
                if d["doc_type"] == "specification":
                    text_chunk = text[:8000]
                else:
                    text_chunk = text[:4000]
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

            client = get_llm_client()
            resp = client.chat.completions.create(
                model=get_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""Из документов ниже извлеки:

contract: {{contract_number, contract_date, seller: {{name, country_code, address, inn, kpp}}, buyer: {{name, country_code, address, inn, kpp}}, currency, incoterms, payment_terms}}
specification: {{items: [{{description, quantity, unit, unit_price, line_total, gross_weight, net_weight, country_origin, hs_code}}], total_amount, currency, total_gross_weight, total_net_weight}}
tech_description: {{products: [{{product_name, purpose, materials, technical_specs, suggested_hs_description}}]}}
transport_invoice: {{freight_amount, freight_currency, carrier_name, awb_number, transport_type}}

Заполни только те разделы, для которых есть документы. Если документа нет — не включай раздел.
CRITICAL: В specification.items.description пиши РЕАЛЬНОЕ название товара из текста, а не заглушки.

{combined_text[:16000]}

JSON:"""},
                ],
                temperature=0,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )

            text = resp.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = _json.loads(text)

            # Маппинг результата
            if data.get("contract"):
                c = data["contract"]
                # Создаём объект, совместимый с ContractParsed
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
                    )
                if c.get("buyer"):
                    b = c["buyer"]
                    buyer_party = ContractParty(
                        name=b.get("name"),
                        country_code=(b.get("country_code") or "")[:2] or None,
                        address=b.get("address"),
                        inn=b.get("inn"),
                        kpp=b.get("kpp"),
                    )
                parsed_docs["contract"] = ContractParsed(
                    contract_number=c.get("contract_number"), contract_date=c.get("contract_date"),
                    seller_name=c.get("seller", {}).get("name"), buyer_name=c.get("buyer", {}).get("name"),
                    seller=seller_party, buyer=buyer_party,
                    currency=c.get("currency"), incoterms=c.get("incoterms"),
                    payment_terms=c.get("payment_terms"), confidence=0.85,
                )

            if data.get("specification"):
                spec_raw = data["specification"] if isinstance(data["specification"], dict) else {}
                spec_items = []
                for idx, it in enumerate(spec_raw.get("items", []) if isinstance(spec_raw.get("items"), list) else []):
                    if not isinstance(it, dict):
                        continue
                    spec_items.append({
                        "line_no": it.get("line_no", idx + 1),
                        "description": it.get("description") or "",
                        "quantity": _safe_float(it.get("quantity")),
                        "unit": it.get("unit"),
                        "unit_price": _safe_float(it.get("unit_price")),
                        "line_total": _safe_float(it.get("line_total")),
                        "gross_weight": _safe_float(it.get("gross_weight")),
                        "net_weight": _safe_float(it.get("net_weight")),
                        "country_origin": it.get("country_origin"),
                        "hs_code": it.get("hs_code"),
                    })
                parsed_docs["specification"] = {
                    "items": spec_items,
                    "total_amount": _safe_float(spec_raw.get("total_amount")),
                    "currency": spec_raw.get("currency"),
                    "total_gross_weight": _safe_float(spec_raw.get("total_gross_weight")),
                    "total_net_weight": _safe_float(spec_raw.get("total_net_weight")),
                }
                logger.info(
                    "spec_batch_parsed",
                    items=len(spec_items),
                    total=parsed_docs["specification"]["total_amount"],
                    gross=parsed_docs["specification"]["total_gross_weight"],
                    net=parsed_docs["specification"]["total_net_weight"],
                )

            if data.get("tech_description"):
                parsed_docs.setdefault("tech_descriptions", []).append(data["tech_description"])

            if data.get("transport_invoice"):
                parsed_docs["transport_invoice"] = data["transport_invoice"]

            logger.info("batch_parse_complete", docs=len(docs), sections=list(data.keys()))

        except Exception as e:
            logger.warning("batch_parse_failed", error=str(e))
            # Fallback: парсим каждый документ отдельно
            for d in docs:
                try:
                    if d["doc_type"] == "contract":
                        parsed_docs["contract"] = self.contract_extractor.extract(d["file_bytes"], d["filename"])
                    elif d["doc_type"] == "specification":
                        from app.services.spec_parser import parse as parse_spec
                        parsed_docs["specification"] = parse_spec(d["file_bytes"], d["filename"])
                    elif d["doc_type"] == "tech_description":
                        from app.services.techop_parser import parse as parse_techop
                        parsed_docs.setdefault("tech_descriptions", []).append(parse_techop(d["file_bytes"], d["filename"]))
                    elif d["doc_type"] == "transport_invoice":
                        from app.services.transport_parser import parse as parse_transport
                        parsed_docs["transport_invoice"] = parse_transport(d["file_bytes"], d["filename"])
                except Exception as inner_e:
                    logger.warning("fallback_parse_failed", doc_type=d["doc_type"], error=str(inner_e)[:100])

        return parsed_docs

    def process_documents(self, files: list[tuple[bytes, str]]) -> dict:
        """
        Обработать набор PDF файлов и вернуть данные для декларации.

        Args:
            files: список (file_bytes, filename)

        Returns:
            dict с данными для ApplyParsedRequest
        """
        import hashlib as _hashlib
        logger.info("crew_process_start", files_count=len(files))
        total_files = len(files)

        # --- Шаг 1: OCR + детекция типов (быстро, без LLM) ---
        doc_texts = []  # [(file_bytes, filename, text, doc_type)]
        for i, (file_bytes, filename) in enumerate(files):
            pct = 10 + int(20 * i / total_files)
            self._progress("parsing", f"[{i+1}/{total_files}] OCR: {filename}", pct)
            text = extract_text(file_bytes, filename)
            doc_type = _detect_doc_type(filename, text)
            doc_texts.append((file_bytes, filename, text, doc_type))
            logger.info("document_detected", filename=filename, doc_type=doc_type)

        # --- Шаг 2: LLM-парсинг (invoice и packing — критичны, парсим отдельно; остальные — батчом) ---
        parsed_docs = {}
        secondary_texts = []  # Тексты для батч-парсинга одним LLM-вызовом

        for i, (file_bytes, filename, text, doc_type) in enumerate(doc_texts):
            pct = 30 + int(30 * i / total_files)

            # Кэш по хэшу файла
            file_hash = _hashlib.md5(file_bytes).hexdigest()[:12]
            cached = _parse_cache.get(file_hash)
            if cached:
                logger.info("parse_cache_hit", filename=filename, doc_type=doc_type)
                if cached.get("_cache_type") == "invoice":
                    parsed_docs["invoice"] = cached
                elif cached.get("_cache_type") == "packing":
                    parsed_docs["packing"] = cached
                continue

            if doc_type == "invoice":
                self._progress("parsing", f"[{i+1}/{total_files}] AI: инвойс...", pct)
                new_inv = self.invoice_extractor.extract(file_bytes, filename)
                new_inv["_filename"] = filename
                new_inv["_cache_type"] = "invoice"
                _parse_cache[file_hash] = new_inv
                # Если уже есть инвойс — выбираем лучший по качеству описаний, затем по кол-ву позиций
                prev_inv = parsed_docs.get("invoice")
                if prev_inv:
                    prev_score = _invoice_score(prev_inv)
                    new_score = _invoice_score(new_inv)
                    prev_good, prev_total, _ = prev_score
                    new_good, new_total, _ = new_score
                    if new_score > prev_score:
                        parsed_docs["invoice"] = new_inv
                        logger.info("invoice_replaced",
                                    prev=prev_inv.get("_filename"), new=filename,
                                    prev_good=prev_good, new_good=new_good,
                                    prev_items=prev_total, new_items=new_total)
                    else:
                        logger.info("invoice_kept",
                                    kept=prev_inv.get("_filename"), skipped=filename,
                                    kept_good=prev_good, skipped_good=new_good,
                                    kept_items=prev_total, skipped_items=new_total)
                else:
                    parsed_docs["invoice"] = new_inv
            elif doc_type == "packing_list":
                self._progress("parsing", f"[{i+1}/{total_files}] AI: упаковочный лист...", pct)
                parsed_docs["packing"] = self.packing_extractor.extract(file_bytes, filename)
                parsed_docs["packing"]["_filename"] = filename
                parsed_docs["packing"]["_cache_type"] = "packing"
                _parse_cache[file_hash] = parsed_docs["packing"]
            elif doc_type == "transport_doc":
                parsed_docs["transport"] = {"raw_text": text, "_filename": filename, "doc_type": "transport_doc"}
            elif doc_type in ("contract", "specification", "tech_description", "transport_invoice"):
                # Собираем для батч-парсинга одним LLM-вызовом
                secondary_texts.append({"doc_type": doc_type, "filename": filename, "text": text, "file_bytes": file_bytes})
            else:
                parsed_docs.setdefault("other", []).append({"raw_text": text, "_filename": filename, "doc_type": doc_type})

        # --- Шаг 3: Батч-парсинг второстепенных документов (один LLM-вызов) ---
        if secondary_texts:
            self._progress("parsing", f"AI: батч-парсинг {len(secondary_texts)} документов...", 60)
            parsed_docs = self._batch_parse_secondary(secondary_texts, parsed_docs)

        # --- Шаг 2: Компиляция данных декларации (хардкод-слияние) ---
        self._progress("compiling", "Компиляция данных декларации...", 70)
        result = self._compile_declaration(parsed_docs)

        # --- Шаг 2.1: LLM-компиляция по правилам граф ДТ из БД ---
        # Повторно вызывает LLM с полными правилами, перекрывает хардкод-значения
        self._progress("compiling", "AI применяет правила заполнения граф ДТ...", 73)
        result = self._compile_by_rules(parsed_docs, result)

        # --- Шаг 2.5: CrewAI мультиагентная оркестрация (если доступна) ---
        # Отключено для оптимизации: дублирует логику шагов 3 и 4, тратит токены и время.
        # if _crewai_available:
        #     self._progress("crewai", "CrewAI агенты анализируют декларацию...", 72)
        #     result = self._run_crewai(parsed_docs, result)

        # --- Шаг 3: Классификация ТН ВЭД для позиций БЕЗ кода ---
        items = result.get("items", [])
        all_descs = [it.get("description") or it.get("commercial_name") or "" for it in items if (it.get("description") or it.get("commercial_name"))]
        decl_context = "; ".join([d[:60] for d in all_descs]) if len(all_descs) > 1 else ""
        for j, item in enumerate(items):
            existing_hs = (item.get("hs_code") or "").strip()
            desc = item.get("description") or item.get("commercial_name") or ""
            self._progress("classifying", f"Классификация ТН ВЭД: позиция {j+1}/{len(items)} — {desc[:40]}", 75 + int(10 * j / max(len(items), 1)))

            # Skip if already have a good HS code from document parsing
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
                        logger.debug("hs_candidates_for_doc_code_skip", error=str(e)[:80])
                logger.info("hs_from_doc_kept", item_no=j+1, hs_code=item["hs_code"])
                continue

            if desc:
                # Для классификации ТН ВЭД: приоритет — hs_description из тех.описания,
                # так как оно специально сформулировано для таможенной классификации
                hs_classify_desc = item.get("hs_description_for_classification") or desc
                if hs_classify_desc != desc:
                    logger.info("hs_using_techop_desc", item_no=j+1,
                                invoice_desc=desc[:50], techop_desc=hs_classify_desc[:50])
                # RAG поиск
                rag_results = self.index_manager.search_hs_codes(hs_classify_desc)
                # DSPy/keyword классификация
                hs_result = self.hs_classifier.classify(hs_classify_desc, rag_results, context=decl_context)
                hs_code = hs_result.get("hs_code", "")

                # Гарантируем 10 знаков
                if hs_code and len(hs_code) < 10:
                    hs_code = hs_code.ljust(10, "0")

                item["hs_code"] = hs_code
                item["hs_code_name"] = hs_result.get("name_ru", "")
                item["hs_confidence"] = hs_result.get("confidence", 0.0)
                item["hs_reasoning"] = hs_result.get("reasoning", "")
                item["hs_candidates"] = hs_result.get("candidates", [])

                if hs_result.get("confidence", 0) < 0.5 or not hs_code:
                    item["hs_needs_review"] = True
                    item["hs_review_message"] = f"AI не уверен в коде ТН ВЭД для товара: {desc[:80]}. Пожалуйста, проверьте и укажите код вручную."
                else:
                    item["hs_needs_review"] = False

                logger.info("hs_classified", item_no=j+1, description=desc[:50], hs_code=hs_code, confidence=hs_result.get("confidence", 0))
            else:
                item["hs_code"] = ""
                item["hs_needs_review"] = True
                item["hs_review_message"] = "Описание товара отсутствует. Укажите описание и код ТН ВЭД вручную."

        # --- Шаг 4: Оценка рисков ---
        self._progress("risks", "Оценка рисков СУР...", 88)
        risk_rules = self.index_manager.search_risk_rules(
            json.dumps(result, ensure_ascii=False, default=str)[:3000]
        )
        risk_result = self.risk_analyzer.analyze(result, risk_rules)
        result["risk_score"] = risk_result.get("risk_score", 0)
        result["risk_flags"] = {"risks": risk_result.get("risks", []), "source": risk_result.get("source", "")}

        # --- Шаг 5: Поиск прецедентов ---
        self._progress("precedents", "Поиск прецедентов...", 93)
        for item in result.get("items", []):
            desc = item.get("description", "")
            if desc:
                precedents = self.index_manager.search_precedents(desc)
                if precedents:
                    item["precedents"] = precedents[:3]

        # Confidence — среднее по всем источникам
        def _get_conf(obj):
            if obj is None:
                return 0
            if isinstance(obj, dict):
                return obj.get("confidence", 0)
            return getattr(obj, "confidence", 0)
        confidences = [
            _get_conf(parsed_docs.get("invoice")),
            _get_conf(parsed_docs.get("contract")),
            _get_conf(parsed_docs.get("packing")),
        ]
        non_zero = [c for c in confidences if c > 0]
        result["confidence"] = sum(non_zero) / len(non_zero) if non_zero else 0.0

        items_count = len(result.get("items", []))
        logger.info(
            "crew_process_complete",
            items_count=items_count,
            confidence=result["confidence"],
            risk_score=result.get("risk_score", 0),
        )

        # Репорт проблем для batch-тестирования
        try:
            from app.services.issue_reporter import report_issue
            if items_count == 0:
                report_issue("compile", "warning", "No items after compilation",
                    {"files": [f for f, _ in files] if hasattr(files[0], '__len__') else [], "confidence": result.get("confidence")})
            for it in result.get("items", []):
                desc = it.get("description") or it.get("commercial_name") or ""
                if desc.lower().startswith("item ") or not desc:
                    report_issue("compile", "warning", f"Bad item description: '{desc[:60]}'",
                        {"description": desc, "hs_code": it.get("hs_code", "")})
                if not it.get("hs_code") or it.get("hs_code", "").startswith("0000"):
                    report_issue("hs_classify", "warning", f"No/bad HS code for: {desc[:60]}",
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

        # ── Seller/Buyer: контракт (приоритет, полные реквизиты) > инвойс ──
        def _extract_party(sources, party_type):
            for src in sources:
                if not src:
                    continue
                p = self._to_dict(src)
                name = p.get("name") or p.get("seller_name" if party_type == "seller" else "buyer_name")
                if name:
                    inn = (p.get("inn") or p.get("tax_number") or "").strip()
                    kpp = (p.get("kpp") or "").strip()
                    tax_number = f"{inn}/{kpp}" if inn and kpp else (inn or None)
                    return {
                        "name": name,
                        "country_code": (p.get("country_code") or "")[:2] or None,
                        "address": p.get("address"),
                        "tax_number": tax_number,
                        "type": party_type,
                    }
            return None

        seller = _extract_party([contract.get("seller"), inv.get("seller")], "seller")
        if not seller and contract.get("seller_name"):
            seller = {"name": contract["seller_name"], "country_code": None, "address": None, "type": "seller"}

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
        origin_code = inv.get("country_origin") or (packing.get("items", [{}])[0].get("country_origin") if packing.get("items") else None)

        # Источник items: ИНВОЙС НА ТОВАРЫ (приоритет) > Packing List.
        # Спецификация НЕ является источником позиций для декларации —
        # она содержит весь заказ, а на таможню едет только то, что в инвойсе/PL.
        # Спецификация используется только для перекрёстной сверки.
        inv_items = inv.get("items", [])
        packing_items = packing.get("items", []) if packing else []

        if inv_items:
            raw_items = inv_items
            items_source = "invoice"
        elif packing_items:
            raw_items = packing_items
            items_source = "packing_list"
        else:
            raw_items = []
            items_source = "none"
            logger.warning("no_items_found", msg="Нет позиций в инвойсе и PL — загрузите инвойс на товары")

        logger.info("items_source", source=items_source, count=len(raw_items))

        # Перекрёстная сверка со спецификацией (только предупреждение, не замена)
        spec_items = spec.get("items", [])
        if spec_items and inv_items:
            if len(spec_items) != len(inv_items):
                logger.info(
                    "spec_vs_invoice_count_mismatch",
                    spec_count=len(spec_items),
                    inv_count=len(inv_items),
                    msg="Количество позиций в спецификации и инвойсе различается — это нормально, "
                        "спецификация содержит весь заказ",
                )

        items = []
        for item_data in raw_items:
            desc = item_data.get("description", item_data.get("description_raw", ""))
            if _SKIP_ITEM.search(desc or ""):
                logger.info("skip_non_goods_item", description=desc[:60])
                continue
            hs_from_doc = _normalize_hs_code(item_data.get("hs_code"))
            if hs_from_doc and (not desc or str(desc).strip().lower().startswith("item ")):
                logger.info("drop_untrusted_doc_hs", hs_code=hs_from_doc, description=(desc or "")[:40])
                hs_from_doc = ""
            qty = _safe_float(item_data.get("quantity"))
            up = _safe_float(item_data.get("unit_price"))
            lt = _safe_float(item_data.get("line_total"))
            if not qty and lt and up and up > 0:
                qty = round(lt / up, 2)
            items.append({
                "line_no": item_data.get("line_no", len(items) + 1),
                "description": desc or "",
                "commercial_name": desc or "",
                "quantity": qty,
                "unit": item_data.get("unit"),
                "unit_price": up,
                "line_total": lt,
                "hs_code": hs_from_doc,
                "country_origin_code": ((item_data.get("country_origin_code") or item_data.get("country_origin") or origin_code) or "")[:2] or None,
                "gross_weight": _safe_float(item_data.get("gross_weight")),
                "net_weight": _safe_float(item_data.get("net_weight")),
            })

        # ── Обогащение из техописаний (ТехОп) через LLM-матчинг ──
        if tech_descs and items:
            all_tech_products = []
            for td in tech_descs:
                all_tech_products.extend(td.get("products", []))
            if all_tech_products:
                logger.info("techop_match_start", items=len(items), tech_products=len(all_tech_products))
                items = self._match_items_to_techop(items, all_tech_products)

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
        transport = parsed_docs.get("transport", {})
        awb_number = None
        awb_raw = transport.get("raw_text", "")
        if awb_raw:
            awb_match = _re.search(r'(\d{3})[- ]?(\d{8})', awb_raw)
            if awb_match:
                awb_number = f"{awb_match.group(1)}-{awb_match.group(2)}"

        # Transport type: определяем из AWB или транспортного инвойса
        transport_type = "40"  # default: воздушный
        if transport_inv.get("transport_type"):
            transport_type = str(transport_inv["transport_type"])

        # AWB номер: из транспортного документа или транспортного инвойса
        if not awb_number and transport_inv.get("awb_number"):
            awb_number = transport_inv["awb_number"]

        # Код таможенного поста: определяем по AWB prefix (airline code → аэропорт)
        customs_office_code = None
        _AWB_TO_POST = {
            "728": "10005020",  # Внуково
            "784": "10002020",  # Шереметьево
            "555": "10009100",  # Домодедово
            "880": "10005020",  # Внуково (DHL/UPS)
            "176": "10002020",  # Шереметьево (Emirates)
            "074": "10002020",  # Шереметьево (KLM)
            "172": "10005020",  # Внуково (прочие)
            "580": "10002020",  # Шереметьево (прочие)
        }
        if awb_number:
            awb_prefix = awb_number.split("-")[0] if "-" in awb_number else awb_number[:3]
            customs_office_code = _AWB_TO_POST.get(awb_prefix)

        _POST_ADDR = {
            "10005020": "г. Москва, аэропорт Внуково, Внуковское шоссе, д. 1",
            "10005030": "г. Москва, Внуковское шоссе, д. 1",
            "10002020": "Московская обл., г.о. Химки, аэропорт Шереметьево, Карго",
            "10009100": "Московская обл., г. Домодедово, аэропорт Домодедово",
        }

        # Default: если AWB есть но пост не определён — Внуково
        if awb_number and not customs_office_code:
            customs_office_code = "10005030"
            logger.info("customs_office_default", awb=awb_number, code=customs_office_code)
        # Если вообще нет AWB но transport_type=40 (воздушный) — Внуково
        if not customs_office_code and transport_type == "40":
            customs_office_code = "10005030"

        goods_location = _POST_ADDR.get(customs_office_code or "", "")
        # Fallback: если всё ещё пусто
        if not goods_location and customs_office_code:
            goods_location = f"Таможенный пост {customs_office_code}"

        # Гр. 22: валюта — ТОЛЬКО из контракта/договора купли-продажи (правило гр. 22).
        # Инвойс не является источником валюты для гр. 22.
        # Гр. 22: сумма = sum(гр. 42 по позициям); для сверки — итог инвойса на товары.
        currency = contract.get("currency")
        if not currency:
            logger.warning("currency_not_in_contract",
                           msg="Валюта не найдена в контракте — гр.22 требует проверки")
            currency = inv.get("currency")
        # Сумма — из инвойса на товары (спецификация не источник суммы)
        total_amount = inv.get("total_amount")

        # ── Evidence tracking ──
        seller_src = "contract" if contract.get("seller") or contract.get("seller_name") else "invoice"
        ev.record("seller", seller, seller_src, confidence=0.85 if seller_src == "contract" else 0.8, graph=2)
        buyer_src = "contract" if contract.get("buyer") or contract.get("buyer_name") else "invoice"
        ev.record("buyer", buyer, buyer_src, confidence=0.85 if buyer_src == "contract" else 0.8, graph=8)
        cur_src = "contract" if contract.get("currency") else "invoice"
        ev.record("currency", currency, cur_src, confidence=0.97 if cur_src == "contract" else 0.7, graph=22)
        ev.record("total_amount", total_amount, "invoice", confidence=0.85, graph=22)
        inco_val = inv.get("incoterms") or contract.get("incoterms")
        ev.record("incoterms", inco_val, "invoice" if inv.get("incoterms") else "contract", confidence=0.85, graph=20)
        origin_val = ((origin_code or inv.get("country_origin")) or "")[:2] or None
        ev.record("country_origin", origin_val, items_source, confidence=0.7, graph=16)
        ev.record("country_destination", "RU", "default", confidence=1.0, graph=17)
        ev.record("transport_type", transport_type,
                  "transport_invoice" if transport_inv.get("transport_type") else "default", confidence=0.8, graph=25)
        ev.record("transport_doc_number", awb_number, "transport_doc", confidence=0.9, graph=18)
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

        result = {
            "invoice_number": inv.get("invoice_number"),
            "invoice_date": inv.get("invoice_date"),
            "seller": seller,
            "buyer": buyer,
            "currency": currency,
            "total_amount": total_amount,
            "incoterms": inco_val,
            "country_origin": origin_val,
            "country_destination": inv.get("country_destination", "RU"),
            "contract_number": contract_num,
            "contract_date": contract.get("contract_date"),
            "total_packages": packing.get("total_packages") or inv.get("total_packages"),
            "package_type": packing.get("package_type"),
            "total_gross_weight": total_gross,
            "total_net_weight": total_net,
            "transport_type": transport_type,
            "transport_doc_number": awb_number,
            "customs_office_code": customs_office_code,
            "goods_location": goods_location,
            "deal_nature_code": "01",
            "type_code": "IM40",
            "declarant_inn_kpp": declarant_inn_kpp,
            "items": items,
            "documents": [],
            "freight_amount": transport_inv.get("freight_amount"),
            "freight_currency": transport_inv.get("freight_currency"),
        }

        evidence_map = ev.to_dict()
        issues = validate_declaration(result, evidence_map)
        result["evidence_map"] = evidence_map
        result["issues"] = issues

        return result

    def _compile_by_rules(self, parsed_docs: dict, base_result: dict) -> dict:
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
        if transport.get("raw_text"):
            docs_ctx["transport_doc_text"] = transport["raw_text"][:600]

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
  "seller": {{"name": "...", "country_code": "ISO2", "address": "..."}},
  "buyer": {{"name": "...", "country_code": "ISO2", "address": "...", "inn": "...", "kpp": "..."}},
  "responsible_person": "гр.9: лицо за фин. урегулирование или 'СМ. ГРАФУ 14 ДТ'",
  "trading_partner_country": "гр.11: ISO2 страна контрагента",
  "declarant_inn_kpp": "гр.14: ИНН/КПП декларанта",
  "country_dispatch": "гр.15: ISO2 страна отправления",
  "country_origin": "гр.16: ISO2 страна происхождения (или ЕВРОСОЮЗ/РАЗНЫЕ)",
  "country_destination": "гр.17: ISO2 страна назначения",
  "container": true/false (гр.19),
  "incoterms": "гр.20: код Инкотермс",
  "delivery_place": "гр.20: географический пункт поставки",
  "transport_id": "гр.21: номера/названия ТС через ;",
  "transport_country": "гр.21: ISO2 страна регистрации ТС или 00/99",
  "currency": "гр.22: ISO 4217 валюта",
  "total_amount": число (гр.22: общая фактурная стоимость),
  "deal_nature_code": "гр.24: код характера сделки",
  "contract_number": "гр.37: номер контракта",
  "contract_date": "гр.37: дата контракта ГГГГ-ММ-ДД",
  "customs_office_code": "гр.30: код таможенного поста",
  "special_features_code": "гр.7: код особенностей или null"
}}

JSON:"""

        try:
            client = get_llm_client()
            resp = client.chat.completions.create(
                model=get_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=2000,
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            llm_result = _json.loads(raw.strip())
            logger.info("compile_by_rules_ok", fields=list(llm_result.keys()))
        except Exception as e:
            logger.warning("compile_by_rules_llm_failed", error=str(e))
            return base_result

        # ── Мерж: LLM перекрывает хардкод там где вернул реальное значение ──
        merged = dict(base_result)
        flagged: list[str] = []

        for key, value in llm_result.items():
            if value is None or value == "":
                continue
            if isinstance(value, str) and value.upper() in ("NULL", "NONE", "N/A", "Н/Д"):
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
