"""
AI-оркестрация парсинга документов и сборки таможенной декларации.

Pipeline: OCR → LLM classify+extract → LLM compile → post-process → validate → HS classify → risk.
"""
import json
import re
from typing import Optional
import structlog

from app.services.llm_json import strip_code_fences

logger = structlog.get_logger()

from app.services.dspy_modules import (
    HSCodeClassifier, RiskAnalyzer,
)
from app.services.index_manager import get_index_manager
from app.services.ocr_service import extract_text
from app.services.invoice_parser import _is_garbage_desc
from app.services.rules_engine import validate_declaration
from app.services.escalation_agents import ReconciliationAgent, ReviewerAgent
from app.services.parsing_utils import (
    safe_float as _safe_float,
    normalize_hs_code as _normalize_hs_code,
    invoice_score as _invoice_score,
    check_needs_vision_retry as _check_needs_vision_retry,
)

# ---------------------------------------------------------------------------
# calc-service integration utilities
# ---------------------------------------------------------------------------

from app.services.post_processing import _fetch_payments, post_process_compilation


class DeclarationCrew:
    """
    Оркестрация AI-парсинга документов и сборки таможенной декларации.

    Pipeline: OCR → LLM classify+extract → LLM compile → Python post-process
    → validate → HS classify (RAG+DSPy) → risk → precedents → escalation.
    """

    def __init__(self):
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
                f"[{i + 1}] name={tp.get('product_name', '') or tp.get('name', '')}  "
                f"manufacturer={tp.get('manufacturer', '')}  "
                f"brand={tp.get('brand', '')}  model={tp.get('model', '')}  "
                f"article={tp.get('article_number', '')}  serial={tp.get('serial_numbers', '')}  "
                f"purpose={tp.get('purpose', '')}  "
                f"materials={tp.get('materials', '')}  "
                f"specs={tp.get('technical_specs', '') or tp.get('specifications', '')}  "
                f"hs_desc={tp.get('suggested_hs_description', '')}\n"
                f"    full_description={tp.get('full_description', '')}"
                for i, tp in enumerate(tech_products)
            ])

            client = get_llm_client(operation="techop_item_match_llm")
            resp_messages = [
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
- description_ru: ПОЛНОЕ описание товара для дополнения к графе 31 ДТ на русском языке. \
КРИТИЧЕСКИ ВАЖНО: если в тех.описании есть full_description — используй его ПОЛНОСТЬЮ, дословно, БЕЗ каких-либо сокращений и обобщений. \
Если full_description отсутствует — собери описание из всех доступных полей тех.описания: \
наименование, назначение/область применения, основные материалы (материал корпуса, покрытия и т.д.), \
технические характеристики (мощность, напряжение, размеры, вес, частота, степень защиты и т.д.), \
марку, модель, артикул, товарный знак, производителя — если указаны. \
Описание должно быть МАКСИМАЛЬНО ПОЛНЫМ. НЕ сокращать. НЕ обобщать. НЕ опускать детали.
- manufacturer: производитель / изготовитель (на русском, из тех.описания, null если нет)
- brand: марка / торговая марка / бренд (на русском, из тех.описания, null если нет)
- model: модель / серия (на русском, из тех.описания, null если нет)
- article_number: артикул / part number (из тех.описания, null если нет)
- serial_numbers: серийные номера через запятую (из тех.описания, null если нет)
- hs_description: описание для классификации ТН ВЭД (из suggested_hs_description или составь сам — материал + назначение + тип)
- match_confidence: уверенность совпадения (0.0–1.0)

JSON: {{"matches": [...]}}"""},
            ]
            resp = client.chat.completions.create(
                model=get_model(),
                messages=resp_messages,
                temperature=0,
                max_tokens=8000,
            )

            raw_resp = resp.choices[0].message.content
            if resp.choices[0].finish_reason == "length":
                logger.warning("techop_match_truncated_retrying")
                resp = client.chat.completions.create(
                    model=get_model(),
                    messages=resp_messages,
                    temperature=0,
                    max_tokens=12000,
                )
                raw_resp = resp.choices[0].message.content

            text = strip_code_fences(raw_resp)
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
                for fld in ("manufacturer", "brand", "model", "article_number", "serial_numbers"):
                    val = (m.get(fld) or "").strip()
                    if val:
                        result[idx][fld] = val
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

    def _process_single_file(self, file_bytes: bytes, filename: str, settings) -> dict:
        """OCR + LLM classify+extract for one file. Thread-safe."""
        from app.services.llm_parser import classify_and_extract_with_correction as classify_and_extract

        text = extract_text(file_bytes, filename)
        ocr_method = "vision_ocr" if settings.has_vision_ocr else "legacy"
        logger.info("ocr_done", filename=filename, chars=len(text), ocr_method=ocr_method)

        result = classify_and_extract(text, filename)
        doc_type = result["doc_type"]
        extracted = result["extracted"]
        extracted["_filename"] = filename
        extracted["doc_type"] = doc_type
        extracted["doc_type_confidence"] = result.get("doc_type_confidence", 0.5)

        missing_fields = _check_needs_vision_retry(doc_type, extracted)
        if missing_fields and settings.has_vision_ocr:
            logger.info("vision_retry_triggered",
                        filename=filename, doc_type=doc_type, missing=missing_fields)
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
                        logger.info("vision_retry_no_new_data", filename=filename)
            except Exception as e:
                logger.warning("vision_retry_failed",
                               filename=filename, error=str(e)[:200])

        items_count = len(extracted.get("items", extracted.get("products", [])))
        llm_debug = result.get("llm_debug", {})
        logger.info(
            "classify_extract_done",
            filename=filename, doc_type=doc_type,
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

        return {"filename": filename, "doc_type": doc_type, "extracted": extracted, "result": result}

    @staticmethod
    def _route_to_parsed_docs(parsed_docs: dict, doc_type: str, extracted: dict, filename: str):
        """Route a single file result into parsed_docs dict by document type."""
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
                new_conf = float(extracted.get("doc_type_confidence") or 0)
                old_conf = float(prev_inv.get("doc_type_confidence") or 0)
                if old_conf >= 0.97 and new_conf < old_conf:
                    logger.info("invoice_kept_high_conf",
                                kept=prev_inv.get("_filename"), skipped=filename,
                                kept_conf=old_conf, skipped_conf=new_conf)
                else:
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

    def process_documents(self, files: list[tuple[bytes, str]]) -> dict:
        """LLM-based document processing pipeline.

        Steps:
          1+2. OCR + classify_and_extract() — parallel per file via ThreadPoolExecutor
          3. _compile_declaration_llm() — LLM fills all declaration fields
          4. _post_process_compilation() — Python: arithmetic, lookups, normalization
          5. validate_declaration()
          6. HS RAG + DSPy classification
          7. Risk assessment
          8. Precedent search
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        logger.info("crew_process_start", files_count=len(files), pipeline="llm_v3")
        total_files = len(files)

        from app.config import get_settings as _get_settings
        _settings = _get_settings()
        max_workers = min(total_files, getattr(_settings, "PARSE_PARALLEL_WORKERS", 4))

        # ── Steps 1+2: OCR + classify + extract (parallel) ──
        self._progress("processing", f"AI обработка {total_files} файлов (x{max_workers})...", 10)

        file_results: list[dict] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._process_single_file, fb, fn, _settings): fn
                for fb, fn in files
            }
            for future in as_completed(futures):
                fn = futures[future]
                try:
                    file_result = future.result()
                    file_results.append(file_result)
                except Exception as e:
                    logger.error("file_processing_failed", filename=fn, error=str(e)[:300])
                    file_results.append({
                        "filename": fn, "doc_type": "error",
                        "extracted": {"_filename": fn}, "error": str(e),
                    })
                done = len(file_results)
                pct = 10 + int(45 * done / total_files)
                self._progress("processing", f"[{done}/{total_files}] {fn}", pct)

        logger.info("parallel_processing_done",
                     total=total_files, ok=sum(1 for r in file_results if not r.get("error")),
                     failed=sum(1 for r in file_results if r.get("error")),
                     workers=max_workers)

        parsed_docs: dict = {}
        for fr in file_results:
            if fr.get("error"):
                continue
            self._route_to_parsed_docs(parsed_docs, fr["doc_type"], fr["extracted"], fr["filename"])

        # ── Step 3: LLM compile (semantic decisions) ──
        self._progress("compiling", "AI компилирует данные декларации...", 58)
        llm_result = self._compile_declaration_llm(parsed_docs)

        # ── Step 4: Python post-process (arithmetic, lookups) ──
        self._progress("compiling", "Python: расчёты, нормализация...", 65)
        try:
            result = self._post_process_compilation(llm_result, parsed_docs)
        except Exception as e:
            logger.error("post_process_failed", error=str(e), exc_info=True)
            result = dict(llm_result)
            result.setdefault("issues", []).append({
                "id": "post_process_failed", "severity": "error",
                "message": f"Ошибка пост-обработки: {e}",
            })

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
                try:
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
                except Exception as e:
                    logger.error("hs_classify_item_failed", item_no=j+1, error=str(e)[:200])
                    item["hs_code"] = ""
                    item["hs_needs_review"] = True
                    item["hs_review_message"] = f"Ошибка классификации: {str(e)[:100]}"
            else:
                item["hs_code"] = ""
                item["hs_needs_review"] = True
                item["hs_review_message"] = "Описание товара отсутствует."

        # ── Step 6b: Payments calculation (after HS codes are known) ──
        self._progress("payments", "Расчёт платежей (calc-service)...", 85)
        try:
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
        except Exception as e:
            logger.error("payments_failed", error=str(e), exc_info=True)
            result.setdefault("issues", []).append({
                "id": "payments_failed", "severity": "error",
                "message": f"Не удалось рассчитать платежи: {e}",
            })

        # ── Step 7: Risk assessment ──
        self._progress("risks", "Оценка рисков СУР...", 88)
        try:
            risk_rules = self.index_manager.search_risk_rules(
                json.dumps(result, ensure_ascii=False, default=str)[:3000]
            )
            risk_result = self.risk_analyzer.analyze(result, risk_rules)
            result["risk_score"] = risk_result.get("risk_score", 0)
            result["risk_flags"] = {"risks": risk_result.get("risks", []), "source": risk_result.get("source", "")}
        except Exception as e:
            logger.error("risk_assessment_failed", error=str(e), exc_info=True)
            result["risk_score"] = 0
            result["risk_flags"] = {"risks": [], "source": "error"}
            result.setdefault("issues", []).append({
                "id": "risk_failed", "severity": "error",
                "message": f"Не удалось оценить риски: {e}",
            })

        # ── Step 8: Precedent search ──
        self._progress("precedents", "Поиск прецедентов...", 93)
        try:
            for item in result.get("items", []):
                desc = item.get("description", "")
                if desc:
                    precedents = self.index_manager.search_precedents(desc)
                    if precedents:
                        item["precedents"] = precedents[:3]
        except Exception as e:
            logger.error("precedent_search_failed", error=str(e), exc_info=True)
            result.setdefault("issues", []).append({
                "id": "precedents_failed", "severity": "warning",
                "message": f"Поиск прецедентов не удался: {e}",
            })

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
        from app.services.parsing_utils import to_dict
        return to_dict(obj)

    def _compile_declaration_llm(self, parsed_docs: dict) -> dict:
        from app.services.declaration_compiler import compile_declaration
        return compile_declaration(parsed_docs)

    def _post_process_compilation(self, llm_result: dict, parsed_docs: dict) -> dict:
        return post_process_compilation(
            llm_result, parsed_docs,
            match_items_to_techop=self._match_items_to_techop,
        )
