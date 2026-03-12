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


def _parse_transport_doc_llm(text: str, filename: str) -> dict:
    """Извлечь идентификатор ТС из транспортного документа (AWB / CMR / B/L) — для графы 21.

    Определяет тип документа и извлекает:
    - vehicle_id: итоговый идентификатор для гр. 21 (номер рейса / рег. номер ТС / название судна)
    - vehicle_type: тип ТС (air / road / sea / rail)
    - transport_country_code: ISO2 страна регистрации ТС
    - awb_number: номер AWB (только для авиа)
    """
    result: dict = {
        "vehicle_id": None,
        "vehicle_type": None,
        "transport_country_code": None,
        "awb_number": None,
        "shipper_name": None,
        "shipper_address": None,
        "destination_airport": None,
    }
    if not text or len(text.strip()) < 20:
        return result
    try:
        from app.config import get_settings
        if not get_settings().has_llm:
            return result
        import json as _json
        from app.services.llm_client import get_llm_client, get_model
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

ВАЖНО: shipper_name, shipper_address и destination_airport обязательны для граф 2 и 29 ДТ.

Текст документа:
{text[:6000]}

JSON:"""},
            ],
            temperature=0,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        data = _json.loads(resp.choices[0].message.content.strip())
        result["vehicle_id"] = data.get("vehicle_id")
        result["vehicle_type"] = data.get("doc_type")
        result["transport_country_code"] = (data.get("transport_country_code") or "")[:2] or None
        result["awb_number"] = data.get("awb_number")
        result["vehicle_count"] = data.get("vehicle_count") or 1
        result["shipper_name"] = data.get("shipper_name")
        result["shipper_address"] = data.get("shipper_address")
        dest = (data.get("destination_airport") or "").strip().upper()
        result["destination_airport"] = dest or None
        logger.info("transport_doc_parsed", filename=filename,
                    vehicle_id=result["vehicle_id"], doc_type=result["vehicle_type"])
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
            from app.services.llm_client import get_llm_client, get_model

            def _first_filename(doc_type: str) -> str | None:
                for doc in docs:
                    if doc.get("doc_type") == doc_type:
                        return doc.get("filename")
                return None

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

            client = get_llm_client(operation="batch_secondary_parse_llm")
            resp = client.chat.completions.create(
                model=get_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""Из документов ниже извлеки:

contract: {{contract_number, contract_date, seller: {{name, country_code, address, inn, kpp, ogrn}}, buyer: {{name, country_code, address, inn, kpp, ogrn}}, is_trilateral: true/false, receiver: {{name, address, country_code, inn, kpp, ogrn}}, financial_responsible: {{name, address, country_code, inn, kpp, ogrn}}, currency, incoterms, payment_terms, delivery_place}}
  is_trilateral: true если договор трёхсторонний (между получателем, декларантом и лицом за фин. урегулирование)
  receiver: получатель груза (графа 8 ДТ) — ТОЛЬКО если отличается от buyer/declarant
  financial_responsible: лицо, ответственное за финансовое урегулирование (графа 9 ДТ) — ТОЛЬКО если отличается от buyer/declarant
specification: {{doc_number, doc_date, items_count, total_amount, currency, total_gross_weight, total_net_weight}}
  doc_number: номер спецификации / приложения к контракту
tech_description: {{doc_number, doc_date, products: [{{product_name, purpose, materials, technical_specs, suggested_hs_description}}]}}
transport_invoice: {{doc_number, doc_date, freight_amount, freight_currency, carrier_name, shipper_name, shipper_address, awb_number, transport_type}}
  doc_number: номер транспортного инвойса / счёта за перевозку
  shipper_name: отправитель груза — искать "Shipper", "Shipper's Name", "Отправитель", "Consignor"
  shipper_address: адрес отправителя — искать "Shipper's Address", "Адрес отправителя" (улица, город, индекс, страна)
application_statement: {{doc_number, doc_date, forwarding_agent: {{name, address, country_code, inn, kpp, ogrn}}, incoterms, delivery_place, shipper: {{name, address, country_code}}}}
  doc_number: номер заявки / поручения экспедитору
  shipper: отправитель груза — искать "Shipper", "Отправитель" и его адрес

Заполни только те разделы, для которых есть документы. Если документа нет — не включай раздел.
Для specification не извлекай все позиции целиком: нужен только items_count и totals для cross-check.

{combined_text[:16000]}

JSON:"""},
                ],
                temperature=0,
                max_tokens=2500,
                response_format={"type": "json_object"},
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
                cache_ok = True
                # Не использовать кеш инвойса, если в нём нет цен —
                # при предыдущем парсинге мог упасть LLM.
                if cached.get("_cache_type") == "invoice":
                    cached_items = cached.get("items", [])
                    has_any_price = any(
                        it.get("unit_price") or it.get("line_total")
                        for it in cached_items
                    ) if cached_items else False
                    if cached_items and not has_any_price:
                        cache_ok = False
                        logger.info("parse_cache_skip_no_prices",
                                    filename=filename, items=len(cached_items))
                if cache_ok:
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
                    prev_good, _, _, prev_total = prev_score
                    new_good, _, _, new_total = new_score
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
                # Парсим AWB/CMR/B/L LLM-ом для извлечения идентификатора ТС (гр. 21)
                transport_parsed = _parse_transport_doc_llm(text, filename)
                transport_parsed["raw_text"] = text
                transport_parsed["_filename"] = filename
                transport_parsed["doc_type"] = "transport_doc"
                parsed_docs["transport"] = transport_parsed
            elif doc_type in ("contract", "specification", "tech_description", "transport_invoice", "application_statement"):
                # Собираем для батч-парсинга одним LLM-вызовом
                secondary_texts.append({"doc_type": doc_type, "filename": filename, "text": text, "file_bytes": file_bytes})
            elif doc_type == "payment_order":
                parsed_docs.setdefault("payment_orders", []).append({"raw_text": text, "_filename": filename, "doc_type": doc_type})
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

        # Нормализация имён полей из _compile_by_rules → имена для ApplyParsedRequest
        if result.get("transport_country") and not result.get("transport_country_code"):
            result["transport_country_code"] = result["transport_country"]
        # Гр. 11: fallback — страна продавца (seller), НЕ страна происхождения товара
        if result.get("trading_partner_country") is None:
            seller_data = result.get("seller")
            if seller_data and isinstance(seller_data, dict) and seller_data.get("country_code"):
                result["trading_partner_country"] = seller_data["country_code"]

        # --- Шаг 2.5: CrewAI мультиагентная оркестрация (если доступна) ---
        # Отключено для оптимизации: дублирует логику шагов 3 и 4, тратит токены и время.
        logger.info(
            "crewai_stage_skipped",
            available=_crewai_available,
            reason="disabled_for_optimization",
        )
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

        # --- Шаг 5.5: Agent escalation layer (только для конфликтных кейсов) ---
        self._progress("escalation", "Проверка условий эскалации агентов...", 95)
        self._run_escalation(result)

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
        transport = parsed_docs.get("transport", {})
        application = parsed_docs.get("application_statement", {})

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

        # ── Графы 8 и 9: по умолчанию «СМ. ГРАФУ 14 ДТ» ──
        # Исключение: трёхсторонний договор с отдельными получателем / ответственным лицом
        is_trilateral = bool(contract.get("is_trilateral"))
        contract_receiver = contract.get("receiver") or contract.get("consignee")
        contract_financial = contract.get("financial_responsible") or contract.get("financial_party")

        buyer_matches_declarant = True
        responsible_person_matches_declarant = True
        responsible_person_data = None

        if is_trilateral and contract_receiver:
            receiver_party = _extract_party([contract_receiver], "buyer")
            if receiver_party and receiver_party.get("name"):
                buyer = receiver_party
                buyer_matches_declarant = False
                logger.info("trilateral_receiver_found",
                            name=receiver_party.get("name"),
                            msg="Графа 8: получатель из трёхстороннего договора")

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
        ev.record("buyer", buyer, buyer_src, confidence=0.85 if buyer_src == "contract" else 0.8, graph=8)
        ev.record("currency", currency, "contract", confidence=0.97 if currency else 0.3, graph=22)
        ev.record("total_amount", total_amount, "invoice", confidence=0.85, graph=22)
        # Графа 20: Инкотермс — 1) Заявка на перевозку, 2) Контракт.
        # Товарный инвойс НЕ является источником условий поставки.
        inco_val = application.get("incoterms") or contract.get("incoterms")
        delivery_place_val = application.get("delivery_place") or contract.get("delivery_place")
        inco_src = "application" if application.get("incoterms") else "contract"
        ev.record("incoterms", inco_val, inco_src, confidence=0.85, graph=20)

        # Предупреждение при расхождении условий поставки между документами
        app_inco = application.get("incoterms")
        app_place = application.get("delivery_place")
        inv_inco = inv.get("incoterms")
        contract_inco = contract.get("incoterms")
        if app_inco and inv_inco and app_inco.upper() != inv_inco.upper():
            logger.warning("incoterms_conflict_app_vs_invoice",
                           application=f"{app_inco} {app_place or ''}".strip(),
                           invoice=inv_inco,
                           msg=f"Графа 20: заявка ({app_inco} {app_place or ''}) ≠ инвойс ({inv_inco}). "
                               f"Используются условия из заявки на перевозку.")
        if app_inco and contract_inco and app_inco.upper() != contract_inco.upper():
            logger.warning("incoterms_conflict_app_vs_contract",
                           application=f"{app_inco} {app_place or ''}".strip(),
                           contract=contract_inco,
                           msg=f"Графа 20: заявка ({app_inco} {app_place or ''}) ≠ контракт ({contract_inco}). "
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
            "invoice": "04021",
            "contract": "03011",
            "packing": "04024",
            "packing_list": "04024",
            "specification": "04091",
            "transport_invoice": "04025",
            "transport": "02011",
            "transport_doc": "02011",
            "application_statement": "05999",
            "tech_description": "05011",
            "payment_order": "03031",
            "certificate_origin": "06019",
            "license": "01011",
            "permit": "01999",
            "sanitary": "07013",
            "veterinary": "07012",
            "phytosanitary": "07011",
            "other": "09023",
        }
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
        _append_doc(
            doc_type="transport_doc",
            doc_code="02011",
            doc_type_name="Транспортный документ",
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
        return docs

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
  "buyer": {{"name": "...", "country_code": "ISO2", "address": "...", "inn": "...", "kpp": "...", "ogrn": "..."}},
  "responsible_person": "гр.9: 'СМ. ГРАФУ 14 ДТ' по умолчанию. Заполнять данными ТОЛЬКО при трёхстороннем договоре (is_trilateral=true).",
  "trading_partner_country": "гр.11: ISO2 страна контрагента",
  "declarant_inn_kpp": "гр.14: ИНН/КПП декларанта",
  "country_dispatch": "гр.15: ISO2 страна отправления",
  "country_origin": "гр.16: ISO2 страна происхождения (или ЕВРОСОЮЗ/РАЗНЫЕ/НЕИЗВЕСТНО)",
  "country_destination": "гр.17: ISO2 страна назначения",
  "container": true/false (гр.19),
  "incoterms": "гр.20: код Инкотермс (3 буквы: EXW/FCA/FOB/CIF и т.д.)",
  "delivery_place": "гр.20: географический пункт поставки (город/порт, например Shanghai или Москва)",
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
            "seller", "buyer", "buyer_matches_declarant",
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
