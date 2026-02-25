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


def _detect_doc_type(filename: str, text: str) -> str:
    """Определить тип документа по имени файла и содержимому."""
    fn_lower = filename.lower()
    text_lower = (text[:3000].lower()) if text else ""

    if fn_lower.endswith(('.xlsx', '.xls')):
        return "packing_list"

    # Combined INV+PL
    if ("inv" in fn_lower and "pl" in fn_lower) or ("инвойс" in fn_lower and "упаков" in fn_lower):
        return "invoice"

    # --- По имени файла ---
    if any(k in fn_lower for k in ["invoice", "инвойс", "счёт", "счет", "inv-", "inv_"]):
        # Транспортный инвойс — отличаем от товарного
        if any(k in fn_lower for k in ["transport", "freight", "shipping", "доставк"]):
            return "transport_invoice"
        # Проверяем содержимое — если это инвойс за перевозку
        if any(k in text_lower for k in ["freight charge", "air freight", "shipping charge", "за перевозку", "транспортные услуги", "air waybill"]):
            return "transport_invoice"
        return "invoice"
    if any(k in fn_lower for k in ["contract", "договор", "контракт"]):
        return "contract"
    if any(k in fn_lower for k in ["packing", "упаков", "packing_list", "packing-list"]):
        return "packing_list"
    if re.search(r'\bpl\b', fn_lower) and "inv" not in fn_lower:
        return "packing_list"
    # AWB по паттерну NNN-NNNNNNNN или NNNNNNNNNNN (авианакладная)
    if re.search(r'^\d{3}[-_ ]?\d{8}', fn_lower.replace('.pdf', '').replace('.jpg', '').strip()):
        return "transport_doc"
    if any(k in fn_lower for k in ["awb", "waybill", "накладная"]):
        return "transport_doc"
    if any(k in fn_lower for k in ["spec", "спец"]):
        return "specification"
    if any(k in fn_lower for k in ["teh", "тех"]):
        return "tech_description"

    # --- По содержимому (для файлов без очевидного имени) ---

    # Транспортный инвойс
    if ("invoice" in text_lower or "счёт" in text_lower) and any(k in text_lower for k in [
        "freight", "shipping charge", "air freight", "за перевозку", "транспортные услуги"
    ]):
        return "transport_invoice"

    # Товарный инвойс
    if "invoice" in text_lower and ("total" in text_lower or "amount" in text_lower):
        return "invoice"

    # Контракт
    if any(k in text_lower for k in ["contract №", "contract no", "договор №", "контракт №", "предмет договора", "subject of"]):
        return "contract"

    # Спецификация — таблица с товарами, количеством, ценой
    if any(k in text_lower for k in ["specification", "спецификация", "приложение к контракту", "приложение к договору"]):
        return "specification"
    if any(k in text_lower for k in ["наименование товара", "кол-во", "цена за ед", "unit price"]) and "total" in text_lower:
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

    # AWB
    if "air waybill" in text_lower or re.search(r'\bawb\b', text_lower):
        return "transport_doc"

    return "other"


# Кэш парсинга по MD5 хэшу файла (in-memory, до перезапуска)
_parse_cache: dict = {}
_CACHE_MAX = 200


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

            client = get_llm_client()
            resp = client.chat.completions.create(
                model=get_model(),
                messages=[
                    {"role": "system", "content": "Ты эксперт по таможенному оформлению. Извлеки данные из нескольких документов одного комплекта. Ответь ТОЛЬКО валидным JSON. ВАЖНО: description должен содержать ПОЛНОЕ наименование товара (марка, модель, артикул), ЗАПРЕЩЕНО писать 'Item 1', 'Товар 1'."},
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
                parsed_docs["invoice"] = self.invoice_extractor.extract(file_bytes, filename)
                parsed_docs["invoice"]["_filename"] = filename
                parsed_docs["invoice"]["_cache_type"] = "invoice"
                _parse_cache[file_hash] = parsed_docs["invoice"]
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

        # --- Шаг 2: Компиляция данных декларации ---
        self._progress("compiling", "Компиляция данных декларации...", 70)
        result = self._compile_declaration(parsed_docs)

        # --- Шаг 2.5: CrewAI мультиагентная оркестрация (если доступна) ---
        if _crewai_available:
            self._progress("crewai", "CrewAI агенты анализируют декларацию...", 72)
            result = self._run_crewai(parsed_docs, result)

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
                # RAG поиск
                rag_results = self.index_manager.search_hs_codes(desc)
                # DSPy/keyword классификация
                hs_result = self.hs_classifier.classify(desc, rag_results, context=decl_context)
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

        # Источник items: спецификация > инвойс
        spec_items = spec.get("items", [])
        inv_items = inv.get("items", [])
        
        # Check if spec items are placeholders
        spec_has_bad = any(
            not it.get("description") or str(it.get("description", "")).strip().lower().startswith("item ")
            for it in spec_items
        )
        if spec_has_bad and len(inv_items) > 0:
            logger.warning("spec_items_bad_fallback_to_invoice", spec_count=len(spec_items), inv_count=len(inv_items))
            raw_items = inv_items
            items_source = "invoice (fallback from spec)"
        else:
            raw_items = spec_items if spec_items else inv_items
            items_source = "specification" if spec_items else "invoice"
            
        logger.info("items_source", source=items_source, count=len(raw_items))

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

        # ── Обогащение из техописаний (ТехОп) ──
        if tech_descs and items:
            all_tech_products = []
            for td in tech_descs:
                all_tech_products.extend(td.get("products", []))
            if all_tech_products:
                for item in items:
                    item_desc_lower = (item.get("description") or "").lower()
                    for tp in all_tech_products:
                        tp_name = (tp.get("product_name") or "").lower()
                        # Fuzzy match: если название техописания содержится в описании товара или наоборот
                        if tp_name and (tp_name[:20] in item_desc_lower or item_desc_lower[:20] in tp_name):
                            # Обогащаем описание техническими характеристиками
                            enrichment = " | ".join(filter(None, [
                                tp.get("purpose"), tp.get("materials"), tp.get("technical_specs"),
                                tp.get("suggested_hs_description"),
                            ]))
                            if enrichment:
                                item["tech_description"] = enrichment
                                item["description"] = f"{item['description']} | {enrichment}"
                                logger.info("item_enriched_from_techop", desc=item["description"][:80])
                            break

        # Обогащение весами: packing list (приоритет) > спецификация > инвойс
        total_gross = _safe_float(
            packing.get("total_gross_weight") or spec.get("total_gross_weight") or
            inv.get("total_gross_weight") or inv.get("gross_weight")
        )
        total_net = _safe_float(
            packing.get("total_net_weight") or spec.get("total_net_weight") or
            inv.get("total_net_weight") or inv.get("net_weight")
        )
        logger.info("weights_sources", packing_gross=packing.get("total_gross_weight"), spec_gross=spec.get("total_gross_weight"), inv_gross=inv.get("total_gross_weight"), total_gross=total_gross)
        if items and total_gross:
            try:
                tg = float(total_gross)
                tn = float(total_net) if total_net else tg * 0.9
                per_item_gross = tg / len(items)
                per_item_net = tn / len(items)
                for item in items:
                    if not item.get("gross_weight"):
                        item["gross_weight"] = round(per_item_gross, 3)
                    if not item.get("net_weight"):
                        item["net_weight"] = round(per_item_net, 3)
            except (ValueError, TypeError):
                pass

        # Если общие веса не найдены, суммируем из позиций
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

        # Валюта: спецификация > инвойс > контракт
        currency = spec.get("currency") or inv.get("currency") or contract.get("currency")
        total_amount = spec.get("total_amount") or inv.get("total_amount")

        result = {
            "invoice_number": inv.get("invoice_number"),
            "invoice_date": inv.get("invoice_date"),
            "seller": seller,
            "buyer": buyer,
            "currency": currency,
            "total_amount": total_amount,
            "incoterms": inv.get("incoterms") or contract.get("incoterms"),
            "country_origin": ((origin_code or inv.get("country_origin")) or "")[:2] or None,
            "country_destination": inv.get("country_destination", "RU"),
            "contract_number": inv.get("contract_number") or contract.get("contract_number"),
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

        return result
