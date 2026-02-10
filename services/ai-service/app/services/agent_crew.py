"""
CrewAI мультиагентная оркестрация.
Агенты: DocumentParser, HSClassifier, RiskAnalyzer, PrecedentLearner.
Fallback на линейный pipeline при недоступности CrewAI/OpenAI.
"""
import json
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

    # По имени файла
    if any(k in fn_lower for k in ["invoice", "инвойс", "счёт", "счет"]):
        return "invoice"
    if any(k in fn_lower for k in ["contract", "договор", "контракт"]):
        return "contract"
    if any(k in fn_lower for k in ["packing", "pl", "упаков"]):
        return "packing_list"
    if any(k in fn_lower for k in ["awb", "waybill", "накладная", "транспорт"]):
        return "transport_doc"
    if any(k in fn_lower for k in ["spec", "спец"]):
        return "specification"
    if any(k in fn_lower for k in ["teh", "тех"]):
        return "tech_description"

    # По содержимому
    text_lower = text[:2000].lower() if text else ""
    if "invoice" in text_lower and ("total" in text_lower or "amount" in text_lower):
        return "invoice"
    if "contract" in text_lower or "договор" in text_lower:
        return "contract"
    if "packing list" in text_lower or "gross weight" in text_lower:
        return "packing_list"
    if "air waybill" in text_lower or "awb" in text_lower:
        return "transport_doc"

    return "other"


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

    def process_documents(self, files: list[tuple[bytes, str]]) -> dict:
        """
        Обработать набор PDF файлов и вернуть данные для декларации.

        Args:
            files: список (file_bytes, filename)

        Returns:
            dict с данными для ApplyParsedRequest
        """
        logger.info("crew_process_start", files_count=len(files))
        total_files = len(files)

        # --- Шаг 1: Парсинг каждого документа ---
        parsed_docs = {}
        for i, (file_bytes, filename) in enumerate(files):
            pct = 15 + int(50 * i / total_files)
            self._progress("parsing", f"[{i+1}/{total_files}] Распознавание: {filename}", pct)

            text = extract_text(file_bytes, filename)
            doc_type = _detect_doc_type(filename, text)

            logger.info("document_detected", filename=filename, doc_type=doc_type)
            self._progress("parsing", f"[{i+1}/{total_files}] {filename} → {doc_type}", pct + 5)

            if doc_type == "invoice":
                self._progress("parsing", f"[{i+1}/{total_files}] AI извлекает данные из инвойса...", pct + 8)
                parsed_docs["invoice"] = self.invoice_extractor.extract(file_bytes, filename)
                parsed_docs["invoice"]["_filename"] = filename
            elif doc_type == "contract":
                self._progress("parsing", f"[{i+1}/{total_files}] AI извлекает данные из контракта...", pct + 8)
                parsed_docs["contract"] = self.contract_extractor.extract(file_bytes, filename)
                parsed_docs["contract"]["_filename"] = filename
            elif doc_type == "packing_list":
                self._progress("parsing", f"[{i+1}/{total_files}] AI извлекает данные из упаковочного листа...", pct + 8)
                parsed_docs["packing"] = self.packing_extractor.extract(file_bytes, filename)
                parsed_docs["packing"]["_filename"] = filename
            elif doc_type == "transport_doc":
                parsed_docs["transport"] = {"raw_text": text, "_filename": filename, "doc_type": "transport_doc"}
            elif doc_type == "specification":
                parsed_docs["specification"] = {"raw_text": text, "_filename": filename, "doc_type": "specification"}
            else:
                parsed_docs.setdefault("other", []).append({
                    "raw_text": text, "_filename": filename, "doc_type": doc_type,
                })

        # --- Шаг 2: Компиляция данных декларации ---
        self._progress("compiling", "Компиляция данных декларации...", 70)
        result = self._compile_declaration(parsed_docs)

        # --- Шаг 2.5: CrewAI мультиагентная оркестрация (если доступна) ---
        if _crewai_available:
            self._progress("crewai", "CrewAI агенты анализируют декларацию...", 72)
            result = self._run_crewai(parsed_docs, result)

        # --- Шаг 3: Классификация ТН ВЭД для КАЖДОЙ позиции ---
        items = result.get("items", [])
        for j, item in enumerate(items):
            desc = item.get("description", "") or item.get("commercial_name", "")
            self._progress("classifying", f"Классификация ТН ВЭД: позиция {j+1}/{len(items)} — {desc[:40]}", 75 + int(10 * j / max(len(items), 1)))

            if desc:
                # RAG поиск
                rag_results = self.index_manager.search_hs_codes(desc)
                # DSPy/keyword классификация
                hs_result = self.hs_classifier.classify(desc, rag_results)
                hs_code = hs_result.get("hs_code", "")

                # Гарантируем 10 знаков
                if hs_code and len(hs_code) < 10:
                    hs_code = hs_code.ljust(10, "0")

                item["hs_code"] = hs_code
                item["hs_code_name"] = hs_result.get("name_ru", "")
                item["hs_confidence"] = hs_result.get("confidence", 0.0)
                item["hs_reasoning"] = hs_result.get("reasoning", "")

                # Пометить если confidence низкий
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
        confidences = [
            parsed_docs.get("invoice", {}).get("confidence", 0),
            parsed_docs.get("contract", {}).get("confidence", 0),
            parsed_docs.get("packing", {}).get("confidence", 0),
        ]
        non_zero = [c for c in confidences if c > 0]
        result["confidence"] = sum(non_zero) / len(non_zero) if non_zero else 0.0

        logger.info(
            "crew_process_complete",
            items_count=len(result.get("items", [])),
            confidence=result["confidence"],
            risk_score=result.get("risk_score", 0),
        )

        return result

    def _compile_declaration(self, parsed_docs: dict) -> dict:
        """Собрать данные декларации из всех распознанных документов."""
        inv = parsed_docs.get("invoice", {})
        contract = parsed_docs.get("contract", {})
        packing = parsed_docs.get("packing", {})

        # Seller
        seller = None
        if inv.get("seller"):
            s = inv["seller"]
            seller = {
                "name": s.get("name"),
                "country_code": s.get("country_code"),
                "address": s.get("address"),
                "type": "seller",
            }

        # Buyer
        buyer = None
        if inv.get("buyer"):
            b = inv["buyer"]
            buyer = {
                "name": b.get("name"),
                "country_code": b.get("country_code"),
                "address": b.get("address") if isinstance(b, dict) else None,
                "type": "buyer",
            }

        # Items из инвойса
        origin_code = inv.get("country_origin") or (packing.get("items", [{}])[0].get("country_origin") if packing.get("items") else None)
        items = []
        for item_data in inv.get("items", []):
            items.append({
                "line_no": item_data.get("line_no", len(items) + 1),
                "description": item_data.get("description", item_data.get("description_raw", "")),
                "commercial_name": item_data.get("description", ""),
                "quantity": item_data.get("quantity"),
                "unit": item_data.get("unit"),
                "unit_price": item_data.get("unit_price"),
                "line_total": item_data.get("line_total"),
                "country_origin_code": origin_code,
                "gross_weight": None,  # будет заполнено из packing
                "net_weight": None,
            })

        # Обогащение из packing list
        if packing:
            total_gross = packing.get("total_gross_weight")
            total_net = packing.get("total_net_weight")
            # Распределить вес поровну по позициям (упрощение)
            if items and total_gross:
                per_item_gross = total_gross / len(items)
                per_item_net = (total_net / len(items)) if total_net else per_item_gross * 0.9
                for item in items:
                    item["gross_weight"] = round(per_item_gross, 3)
                    item["net_weight"] = round(per_item_net, 3)

        # Transport from AWB — extract AWB number
        import re as _re
        transport = parsed_docs.get("transport", {})
        awb_number = None
        awb_raw = transport.get("raw_text", "")
        if awb_raw:
            awb_match = _re.search(r'(\d{3})[- ]?(\d{8})', awb_raw)
            if awb_match:
                awb_number = f"{awb_match.group(1)}-{awb_match.group(2)}"

        result = {
            "invoice_number": inv.get("invoice_number"),
            "invoice_date": inv.get("invoice_date"),
            "seller": seller,
            "buyer": buyer,
            "currency": inv.get("currency"),
            "total_amount": inv.get("total_amount"),
            "incoterms": inv.get("incoterms") or contract.get("incoterms"),
            "country_origin": origin_code or inv.get("country_origin"),
            "country_destination": inv.get("country_destination", "RU"),
            "contract_number": inv.get("contract_number") or contract.get("contract_number"),
            "contract_date": contract.get("contract_date"),
            "total_packages": packing.get("total_packages"),
            "package_type": packing.get("package_type"),
            "total_gross_weight": packing.get("total_gross_weight"),
            "total_net_weight": packing.get("total_net_weight"),
            "transport_type": "40",  # Воздушный (по AWB)
            "transport_doc_number": awb_number,
            "deal_nature_code": "01",  # Купля-продажа
            "type_code": "IM40",  # Импорт
            "items": items,
            "documents": [],
        }

        return result
