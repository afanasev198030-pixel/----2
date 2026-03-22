"""
Smart Parser роутер — мультизагрузка PDF, CrewAI оркестрация.
POST /api/v1/ai/parse-smart — парсинг нескольких PDF → данные для декларации
POST /api/v1/ai/parse-smart-stream — SSE стрим с прогрессом
POST /api/v1/ai/classify-hs-rag — RAG классификация ТН ВЭД
POST /api/v1/ai/check-risks-rag — RAG проверка рисков
"""
import json
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import structlog

from app.services.agent_crew import DeclarationCrew
from app.services.index_manager import get_index_manager
from app.services.dspy_modules import HSCodeClassifier, RiskAnalyzer
from app.services.usage_tracker import set_usage_context, reset_usage_context

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/ai", tags=["smart-parser"])


# Global progress store (in-memory; replaced by Redis in worker mode)
_progress: dict = {}

# ARQ connection pool (lazy init)
_arq_pool = None


async def _get_arq_pool():
    """Lazy-init ARQ Redis connection pool."""
    global _arq_pool
    if _arq_pool is None:
        from arq.connections import create_pool, RedisSettings
        from app.config import get_settings
        settings = get_settings()
        _arq_pool = await create_pool(
            RedisSettings.from_dsn(settings.REDIS_BROKER_URL),
            default_queue_name=settings.ARQ_QUEUE_NAME,
        )
    return _arq_pool


def _send_event(request_id: str, step: str, detail: str, progress: int):
    """Store progress event."""
    _progress[request_id] = {
        "step": step,
        "detail": detail,
        "progress": progress,
    }


@router.get("/parse-progress/{request_id}")
async def get_parse_progress(request_id: str):
    """Получить текущий прогресс парсинга."""
    return _progress.get(request_id, {"step": "waiting", "detail": "Ожидание...", "progress": 0})


@router.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """Получить статус задачи в очереди ARQ."""
    from app.config import get_settings
    settings = get_settings()
    if not settings.TASK_QUEUE_ENABLED:
        raise HTTPException(status_code=404, detail="Task queue is disabled")

    try:
        pool = await _get_arq_pool()
        from arq.jobs import Job
        job = Job(task_id, pool)
        info = await job.info()
        if info is None:
            return {"task_id": task_id, "status": "not_found"}
        return {
            "task_id": task_id,
            "status": str(info.status),
            "enqueue_time": str(info.enqueue_time) if info.enqueue_time else None,
            "start_time": str(info.start_time) if info.start_time else None,
            "finish_time": str(info.finish_time) if info.finish_time else None,
            "success": info.success,
            "result": info.result if info.success else None,
        }
    except Exception as e:
        logger.warning("task_status_error", task_id=task_id, error=str(e))
        return {"task_id": task_id, "status": "unknown", "error": str(e)}


@router.post("/parse-smart")
async def parse_smart(
    files: list[UploadFile] = File(...),
    declaration_id: Optional[str] = Form(None),
):
    """
    Мультизагрузка PDF файлов → автопарсинг → данные для декларации.
    При TASK_QUEUE_ENABLED=true ставит задачу в ARQ и возвращает task_id.
    При TASK_QUEUE_ENABLED=false работает синхронно (обратная совместимость).
    """
    import uuid as _uuid
    request_id = str(_uuid.uuid4())[:8]

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Too many files (max 20)")

    filenames = [f.filename for f in files]
    logger.info("parse_smart_start", files_count=len(files), filenames=filenames, request_id=request_id)

    # Step 1: Reading files
    _send_event(request_id, "reading", f"Чтение {len(files)} файлов...", 5)
    file_data = []
    for i, f in enumerate(files):
        content = await f.read()
        if len(content) == 0:
            continue
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File {f.filename} exceeds 50MB limit")
        file_data.append((content, f.filename or "document.pdf"))
        _send_event(request_id, "reading", f"Прочитан: {f.filename}", 5 + int(10 * (i + 1) / len(files)))

    if not file_data:
        raise HTTPException(status_code=400, detail="No valid files to process")

    # ── Async mode: enqueue to ARQ worker, then poll for result ──
    from app.config import get_settings
    settings = get_settings()

    if settings.TASK_QUEUE_ENABLED:
        try:
            pool = await _get_arq_pool()
            job = await pool.enqueue_job(
                "process_declaration_task",
                declaration_id=declaration_id,
                file_data=file_data,
                request_id=request_id,
            )
            _send_event(request_id, "queued", "Задача поставлена в очередь...", 10)
            logger.info("task_enqueued", task_id=job.job_id, request_id=request_id)

            poll_timeout = 540
            poll_interval = 3
            import time as _poll_time
            deadline = _poll_time.time() + poll_timeout

            while _poll_time.time() < deadline:
                await asyncio.sleep(poll_interval)
                info = await job.info()
                if info is None:
                    continue
                if info.success is not None:
                    if info.success:
                        task_result = info.result or {}
                        result = task_result.get("result", {}) if isinstance(task_result, dict) else {}
                        result["request_id"] = request_id
                        _send_event(request_id, "complete", "Готово!", 100)
                        logger.info(
                            "task_poll_complete",
                            task_id=job.job_id,
                            items_count=len(result.get("items", [])),
                            request_id=request_id,
                        )
                        asyncio.get_event_loop().call_later(60, lambda: _progress.pop(request_id, None))
                        return result
                    else:
                        error_msg = ""
                        if isinstance(info.result, dict):
                            error_msg = info.result.get("error", "Unknown error")
                        else:
                            error_msg = str(info.result)[:300] if info.result else "Unknown error"
                        logger.error("task_poll_failed", task_id=job.job_id, error=error_msg, request_id=request_id)
                        raise HTTPException(status_code=500, detail=f"AI processing failed: {error_msg}")

            logger.warning("task_poll_timeout", task_id=job.job_id, request_id=request_id)
            raise HTTPException(status_code=504, detail="AI processing timeout — задача всё ещё обрабатывается. Попробуйте повторить позже.")

        except HTTPException:
            raise
        except Exception as eq_err:
            logger.warning("enqueue_failed_fallback_sync", error=str(eq_err), request_id=request_id)

    # ── Sync fallback (TASK_QUEUE_ENABLED=false or enqueue failed) ──
    context_tokens = set_usage_context(declaration_id=declaration_id or "", operation="parse_smart_dspy")
    try:
        _send_event(request_id, "parsing", "Распознавание документов (OCR)...", 15)

        crew = DeclarationCrew()
        crew._progress_callback = lambda step, detail, pct: _send_event(request_id, step, detail, pct)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, crew.process_documents, file_data)

        _send_event(request_id, "complete", "Готово!", 100)

        logger.info(
            "parse_smart_complete",
            items_count=len(result.get("items", [])),
            confidence=result.get("confidence", 0),
            risk_score=result.get("risk_score", 0),
            request_id=request_id,
        )

        import re as _re
        def _pad_hs(code: str) -> str:
            c = _re.sub(r"\D", "", str(code or ""))
            if len(c) < 6:
                return ""
            if len(c) < 10:
                c = c.ljust(10, "0")
            c = c[:10]
            try:
                g = int(c[:2])
                if g < 1 or g > 97:
                    return ""
            except ValueError:
                return ""
            return c

        for item in result.get("items", []):
            raw = item.get("hs_code", "")
            if raw:
                item["hs_code"] = _pad_hs(raw)
            for cand in item.get("hs_candidates", []):
                if cand.get("hs_code"):
                    cand["hs_code"] = _pad_hs(cand["hs_code"])

        result["request_id"] = request_id

        try:
            from app.main import _last_parse
            import time as _time
            _last_parse.clear()
            _last_parse.update({
                "request_id": request_id,
                "timestamp": _time.time(),
                "files": filenames,
                "items_count": len(result.get("items", [])),
                "confidence": result.get("confidence", 0),
                "risk_score": result.get("risk_score", 0),
                "status": "complete",
                "items_preview": [
                    {"desc": (it.get("description") or it.get("commercial_name") or "")[:60], "hs": it.get("hs_code", "")}
                    for it in (result.get("items") or [])[:5]
                ],
            })
        except Exception:
            pass

        asyncio.get_event_loop().call_later(60, lambda: _progress.pop(request_id, None))
        return result

    except HTTPException:
        raise
    except Exception as e:
        _send_event(request_id, "error", f"Ошибка: {str(e)}", -1)
        logger.error("parse_smart_failed", error=str(e), exc_info=True, request_id=request_id)
        raise HTTPException(status_code=500, detail=f"Failed to parse documents: {str(e)}")
    finally:
        reset_usage_context(context_tokens)


def _run_parse_debug(file_data: list[tuple[bytes, str]]) -> dict:
    """Sync helper for parse-debug — runs in thread pool to avoid blocking event loop."""
    import time as _time
    t_start = _time.monotonic()

    from app.services.ocr_service import extract_text_debug
    from app.services.llm_parser import classify_and_extract_debug
    from app.services.rules_engine import validate_declaration

    documents = []
    parsed_docs: dict = {}

    for content, fname in file_data:
        doc_trace: dict = {"filename": fname, "stages": {}}

        ocr_result = extract_text_debug(content, fname)
        full_text = ocr_result["text"]
        ocr_stage: dict = {
            "method": ocr_result["method"],
            "chars": ocr_result["chars"],
            "pages": ocr_result.get("pages", 0),
            "duration_ms": ocr_result["duration_ms"],
            "text": full_text,
            "text_truncated": False,
        }
        if ocr_result.get("ocr_vision"):
            v = ocr_result["ocr_vision"]
            ocr_stage["ocr_vision"] = {
                "method": v.get("method"),
                "chars": v.get("chars"),
                "duration_ms": v.get("duration_ms"),
                "text": v.get("text", "")[:3000],
                "error": v.get("error"),
            }
        if ocr_result.get("ocr_legacy"):
            lg = ocr_result["ocr_legacy"]
            ocr_stage["ocr_legacy"] = {
                "method": lg.get("method"),
                "chars": lg.get("chars"),
                "pages": lg.get("pages", 0),
                "duration_ms": lg.get("duration_ms"),
                "text": lg.get("text", "")[:3000],
            }
        doc_trace["stages"]["ocr"] = ocr_stage

        ce_result = classify_and_extract_debug(full_text, fname)
        doc_type = ce_result["doc_type"]
        extracted = ce_result["extracted"]
        extracted["_filename"] = fname
        extracted["doc_type"] = doc_type

        vision_retry_info: dict = {}
        from app.services.agent_crew import _check_needs_vision_retry
        missing_fields = _check_needs_vision_retry(doc_type, extracted)
        if missing_fields:
            from app.config import get_settings as _get_settings
            _dbg_settings = _get_settings()
            if _dbg_settings.has_vision_ocr:
                logger.info("debug_vision_retry_triggered",
                            filename=fname, doc_type=doc_type,
                            missing=missing_fields)
                try:
                    from app.services.ocr_service import _extract_with_vision_ocr
                    from app.services.llm_parser import classify_and_extract_debug as _ce_debug
                    vision_text = _extract_with_vision_ocr(content, fname)
                    if vision_text and vision_text.strip():
                        vision_ce = _ce_debug(vision_text, fname)
                        vision_extracted = vision_ce.get("extracted", {})
                        merged = []
                        for field in missing_fields:
                            v = vision_extracted.get(field)
                            if v and not (isinstance(v, dict) and not any(v.values())):
                                extracted[field] = v
                                merged.append(field)
                        vision_retry_info = {
                            "triggered": True,
                            "missing_fields": missing_fields,
                            "merged_fields": merged,
                            "vision_doc_type": vision_ce.get("doc_type"),
                        }
                        if merged:
                            logger.info("debug_vision_retry_merged",
                                        filename=fname, merged_fields=merged)
                except Exception as e:
                    vision_retry_info = {
                        "triggered": True,
                        "missing_fields": missing_fields,
                        "error": str(e)[:200],
                    }
                    logger.warning("debug_vision_retry_failed",
                                   filename=fname, error=str(e)[:200])

        doc_trace["stages"]["classify_and_extract"] = {
            "doc_type": doc_type,
            "doc_type_confidence": ce_result.get("doc_type_confidence", 0),
            "extracted": extracted,
            "prompt_system": ce_result.get("llm_debug", {}).get("prompt_system", ""),
            "prompt_user": ce_result.get("llm_debug", {}).get("prompt_user", ""),
            "raw_response": ce_result.get("llm_debug", {}).get("raw_response", ""),
            "duration_ms": ce_result.get("llm_debug", {}).get("duration_ms", 0),
            "model": ce_result.get("llm_debug", {}).get("model", ""),
            "tokens": ce_result.get("llm_debug", {}).get("tokens", {}),
            "vision_retry": vision_retry_info or None,
        }

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
            parsed_docs["invoice"] = extracted
        else:
            parsed_docs[doc_type] = extracted

        documents.append(doc_trace)

    compilation: dict = {}
    try:
        if parsed_docs:
            crew = DeclarationCrew()

            t_llm = _time.monotonic()
            llm_result = crew._compile_declaration_llm(parsed_docs)
            llm_compile_ms = int((_time.monotonic() - t_llm) * 1000)

            t_pp = _time.monotonic()
            post_result = crew._post_process_compilation(llm_result, parsed_docs)
            post_process_ms = int((_time.monotonic() - t_pp) * 1000)

            evidence_map = post_result.get("evidence_map", {})
            issues = validate_declaration(post_result, evidence_map)
            post_result["evidence_map"] = evidence_map
            post_result["issues"] = issues

            calc_debug = post_result.pop("_calc_debug", {})
            compilation = {
                "llm_compile": {
                    "duration_ms": llm_compile_ms,
                    "fields": list(llm_result.keys()),
                    "items_count": len(llm_result.get("items", [])),
                    "result": {k: v for k, v in llm_result.items()
                               if k not in ("evidence_map", "issues", "items")},
                },
                "post_process": {
                    "duration_ms": post_process_ms,
                    "customs_office_code": post_result.get("customs_office_code"),
                    "customs_office_name": post_result.get("customs_office_name"),
                    "total_gross_weight": post_result.get("total_gross_weight"),
                    "total_net_weight": post_result.get("total_net_weight"),
                    "total_sheets": post_result.get("total_sheets"),
                    "total_items_count": post_result.get("total_items_count"),
                    "total_amount": post_result.get("total_amount"),
                    "exchange_rate": post_result.get("exchange_rate"),
                    "exchange_rate_currency": post_result.get("exchange_rate_currency"),
                    "total_customs_value": post_result.get("total_customs_value"),
                    "total_statistical_value": post_result.get("total_statistical_value"),
                    "preference_code": post_result.get("preference_code"),
                    "freight_distribution": calc_debug.get("freight_distribution"),
                    "items_preview": [
                        {
                            "description": (it.get("description") or "")[:100],
                            "hs_code": it.get("hs_code"),
                            "gross_weight": it.get("gross_weight"),
                            "net_weight": it.get("net_weight"),
                            "line_total": it.get("line_total"),
                            "customs_value_rub": it.get("customs_value_rub"),
                            "statistical_value_usd": it.get("statistical_value_usd"),
                            "country_origin_code": it.get("country_origin_code"),
                        }
                        for it in (post_result.get("items") or [])[:10]
                    ],
                },
                "validation": {
                    "issues": issues,
                    "issues_count": len(issues),
                },
                "evidence_map": evidence_map,
            }
    except Exception as e:
        compilation = {"error": str(e)[:500]}
        logger.error("parse_debug_compilation_failed", error=str(e), exc_info=True)

    total_ms = int((_time.monotonic() - t_start) * 1000)

    return {
        "documents": documents,
        "compilation": compilation,
        "total_duration_ms": total_ms,
    }


@router.post("/parse-debug")
async def parse_debug(
    files: list[UploadFile] = File(...),
):
    """
    Debug endpoint: LLM-only pipeline trace.
    Stages per document: ocr -> classify_and_extract.
    Compilation: llm_compile -> post_process -> validation.
    Does NOT run HS classification, risks, or precedents.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Max 10 files for debug")

    file_data = []
    for f in files:
        content = await f.read()
        if not content:
            continue
        file_data.append((content, f.filename or "document.pdf"))

    if not file_data:
        raise HTTPException(status_code=400, detail="No valid files to process")

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_parse_debug, file_data)


class ClassifyHSRequest(BaseModel):
    description: str
    country_origin: Optional[str] = None
    unit_price: Optional[float] = None
    declaration_id: Optional[str] = None


@router.post("/classify-hs-rag")
async def classify_hs_rag(request: ClassifyHSRequest):
    """
    RAG классификация ТН ВЭД.
    LlamaIndex → top-10 кодов → DSPy выбирает точный 10-значный код.
    """
    if not request.description:
        raise HTTPException(status_code=400, detail="Description is required")

    context_tokens = set_usage_context(declaration_id=request.declaration_id or "", operation="hs_classify_dspy")
    try:
        # RAG поиск по ChromaDB
        index_manager = get_index_manager()
        rag_results = index_manager.search_hs_codes(request.description)

        # DSPy классификация
        classifier = HSCodeClassifier()
        result = classifier.classify(request.description, rag_results)

        logger.info(
            "hs_rag_classified",
            description=request.description[:50],
            hs_code=result.get("hs_code"),
            confidence=result.get("confidence"),
            source=result.get("source"),
        )

        # Ensure 10-digit HS codes (min 6 input, group 01-97)
        import re as _re
        def _pad10(code):
            c = _re.sub(r"\D", "", str(code or ""))
            if len(c) < 6: return ""
            c = c.ljust(10, "0")[:10]
            try:
                g = int(c[:2])
                if g < 1 or g > 97: return ""
            except ValueError: return ""
            return c
        if result.get("hs_code"):
            result["hs_code"] = _pad10(result["hs_code"])
        for c in result.get("candidates", []):
            if c.get("hs_code"):
                c["hs_code"] = _pad10(c["hs_code"])

        return {
            "suggestions": [result],
            "rag_candidates": rag_results[:5],
        }

    except Exception as e:
        logger.error("classify_hs_rag_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to classify HS code: {str(e)}")
    finally:
        reset_usage_context(context_tokens)


class RiskCheckRequest(BaseModel):
    items: list[dict] = []
    total_customs_value: Optional[float] = None
    country_origin: Optional[str] = None


@router.post("/check-risks-rag")
async def check_risks_rag(request: RiskCheckRequest):
    """
    RAG проверка рисков.
    LlamaIndex → релевантные правила СУР → DSPy анализирует.
    """
    try:
        declaration_data = {
            "items": request.items,
            "total_customs_value": request.total_customs_value,
            "country_origin": request.country_origin,
        }

        # RAG поиск правил
        index_manager = get_index_manager()
        declaration_text = str(declaration_data)[:3000]
        relevant_rules = index_manager.search_risk_rules(declaration_text)

        # DSPy анализ рисков
        analyzer = RiskAnalyzer()
        result = analyzer.analyze(declaration_data, relevant_rules)

        # Determine severity
        risk_score = result.get("risk_score", 0)
        if risk_score <= 25:
            severity = "low"
        elif risk_score <= 50:
            severity = "medium"
        elif risk_score <= 75:
            severity = "high"
        else:
            severity = "critical"

        logger.info(
            "risks_rag_checked",
            risk_score=risk_score,
            severity=severity,
            risks_count=len(result.get("risks", [])),
        )

        return {
            "overall_risk_score": risk_score,
            "overall_severity": severity,
            "risks": result.get("risks", []),
            "source": result.get("source", ""),
        }

    except Exception as e:
        logger.error("check_risks_rag_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check risks: {str(e)}")


# --- DSPy Feedback & Optimization ---

_feedback_store: list[dict] = []
_last_optimize_time: float = 0


class FeedbackRequest(BaseModel):
    declaration_id: Optional[str] = None
    item_id: Optional[str] = None
    feedback_type: str  # hs_code_corrected, hs_code_accepted, released
    predicted_value: Optional[str] = None
    actual_value: Optional[str] = None
    description: Optional[str] = None


class TrainBatchExample(BaseModel):
    declaration_id: Optional[str] = None
    item_id: Optional[str] = None
    company_id: Optional[str] = None
    description: str
    actual_hs_code: str
    context: Optional[dict] = None
    source: Optional[str] = None
    captured_at: Optional[str] = None


class TrainBatchRequest(BaseModel):
    examples: list[TrainBatchExample]


@router.post("/train-batch")
async def train_batch(data: TrainBatchRequest):
    """Принять батч обучающих примеров и сохранить в eval-датасет + прецеденты."""
    from app.services.index_manager import get_index_manager
    from app.services.training_dataset import append_examples, dataset_path

    idx = get_index_manager()
    raw_examples = [e.model_dump() for e in data.examples]
    accepted_dataset = append_examples(raw_examples)

    accepted_precedents = 0
    for ex in raw_examples:
        description = (ex.get("description") or "").strip()
        hs_code = (ex.get("actual_hs_code") or "").strip()
        if len(description) < 3 or len(hs_code) < 6:
            continue
        try:
            idx.add_precedent(
                description,
                hs_code[:10],
                metadata={
                    "source": ex.get("source") or "approved_declaration",
                    "declaration_id": ex.get("declaration_id") or "",
                    "item_id": ex.get("item_id") or "",
                    "company_id": ex.get("company_id") or "",
                },
            )
            accepted_precedents += 1
        except Exception as exc:
            logger.warning("train_batch_precedent_failed", error=str(exc)[:120])

    logger.info(
        "train_batch_completed",
        requested=len(raw_examples),
        accepted_dataset=accepted_dataset,
        accepted_precedents=accepted_precedents,
    )
    return {
        "status": "ok",
        "requested": len(raw_examples),
        "accepted": accepted_dataset,
        "precedents_added": accepted_precedents,
        "dataset_path": dataset_path(),
    }


@router.post("/feedback")
async def submit_feedback(data: FeedbackRequest):
    """Принять feedback для DSPy авто-оптимизации + сохранить прецедент."""
    _feedback_store.append(data.model_dump())
    logger.info("feedback_received", type=data.feedback_type, predicted=data.predicted_value, actual=data.actual_value, total=len(_feedback_store))

    # Сохранить как прецедент в ChromaDB (self-learning)
    if data.feedback_type in ("hs_confirmed", "hs_auto_confirmed") and data.description and data.actual_value:
        try:
            from app.services.index_manager import get_index_manager
            idx = get_index_manager()
            idx.add_precedent(data.description, data.actual_value, metadata={
                "declaration_id": data.declaration_id or "",
                "item_id": data.item_id or "",
                "source": "user_confirmed",
            })
            logger.info("precedent_saved", description=data.description[:50], hs_code=data.actual_value)
        except Exception as e:
            logger.warning("precedent_save_failed", error=str(e))

    # Авто-оптимизация при 10+ примеров
    import time
    global _last_optimize_time
    if len(_feedback_store) >= 10 and (time.time() - _last_optimize_time) > 3600:
        try:
            from app.services.dspy_optimizer import optimize_hs_classifier
            examples = [
                {"description": f["description"] or "", "hs_code": f["actual_value"] or f["predicted_value"] or ""}
                for f in _feedback_store if f.get("actual_value") or f.get("predicted_value")
            ]
            result = optimize_hs_classifier(examples)
            if result:
                _last_optimize_time = time.time()
                logger.info("auto_optimization_triggered", examples=len(examples), result=result)
        except Exception as e:
            logger.warning("auto_optimization_failed", error=str(e))

    return {"status": "received", "total_feedback": len(_feedback_store)}


@router.post("/optimize")
async def manual_optimize():
    """Ручной запуск DSPy оптимизации."""
    from app.services.index_manager import _log_event
    if len(_feedback_store) < 5:
        return {"status": "not_enough_data", "feedback_count": len(_feedback_store), "min_required": 5}

    try:
        from app.services.dspy_optimizer import optimize_hs_classifier
        examples = [
            {"description": f["description"] or "", "hs_code": f["actual_value"] or f["predicted_value"] or ""}
            for f in _feedback_store if f.get("actual_value") or f.get("predicted_value")
        ]
        _log_event("optimization_started", f"{len(examples)} examples")
        result = optimize_hs_classifier(examples)
        if result:
            import time
            global _last_optimize_time
            _last_optimize_time = time.time()
            _log_event("optimization_complete", f"Saved to {result}")
        else:
            _log_event("optimization_skipped", "Not enough data or DSPy unavailable", "warning")
        return {"status": "optimized" if result else "failed", "path": result, "examples": len(examples)}
    except Exception as e:
        logger.error("manual_optimization_failed", error=str(e))
        _log_event("optimization_failed", str(e), "error")
        raise HTTPException(500, f"Optimization failed: {str(e)}")


# --- Training Stats & HS Code Indexing ---

@router.get("/training-stats")
async def training_stats():
    """Статистика обучения: коллекции ChromaDB, feedback, лог."""
    from app.services.index_manager import get_index_manager, get_training_log
    from pathlib import Path

    idx = get_index_manager()
    stats = idx.get_stats()

    # Check for optimized model
    models_dir = Path(__file__).parent.parent / "ml_models"
    optimized_hs = (models_dir / "hs_classifier_optimized.json").exists()
    optimized_invoice = (models_dir / "invoice_extractor_optimized.json").exists()

    return {
        **stats,
        "feedback_count": len(_feedback_store),
        "last_optimize_time": _last_optimize_time or None,
        "optimized_models": {
            "hs_classifier": optimized_hs,
            "invoice_extractor": optimized_invoice,
        },
        "log": get_training_log()[-50:],  # last 50 events
    }


class IndexHSCodesRequest(BaseModel):
    codes: list[dict]  # [{"code": "8501200009", "name_ru": "...", "parent_code": "..."}]
    force: bool = False


@router.post("/index-hs-codes")
async def index_hs_codes(data: IndexHSCodesRequest):
    """Индексировать коды ТН ВЭД в ChromaDB."""
    from app.services.index_manager import get_index_manager, _log_event
    idx = get_index_manager()

    if not idx._initialized:
        # Try to init
        import json
        from pathlib import Path
        rules_path = Path(__file__).parent.parent / "rules" / "risk_rules.json"
        risk_rules = []
        if rules_path.exists():
            with open(rules_path) as f:
                risk_rules = json.load(f)
        idx.init_indices(risk_rules=risk_rules)

    if not idx._chroma_client:
        raise HTTPException(500, "ChromaDB not connected")

    _log_event("hs_index_request", f"{len(data.codes)} codes, force={data.force}")
    result = idx.index_hs_codes(data.codes, force=data.force)
    return result


# --- Cortex Memory: Precedents Management ---

@router.get("/precedents")
async def list_precedents(q: str = "", limit: int = 50):
    """Список прецедентов из ChromaDB с поиском."""
    from app.services.index_manager import get_index_manager
    idx = get_index_manager()
    if not idx._chroma_client:
        return {"precedents": [], "total": 0}

    try:
        col = idx._chroma_client.get_or_create_collection("precedents")
        if q:
            results = col.query(query_texts=[q], n_results=min(limit, 100))
            items = []
            for i, doc_id in enumerate(results["ids"][0]):
                meta = (results["metadatas"][0][i] if results["metadatas"] else {}) or {}
                dist = results["distances"][0][i] if results.get("distances") else 0
                items.append({
                    "id": doc_id,
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "hs_code": meta.get("hs_code", ""),
                    "description": meta.get("description", ""),
                    "source": meta.get("source", ""),
                    "score": round(1 - dist, 3) if dist else 0,
                })
        else:
            data = col.get(limit=limit, include=["documents", "metadatas"])
            items = []
            for i, doc_id in enumerate(data["ids"]):
                meta = (data["metadatas"][i] if data["metadatas"] else {}) or {}
                items.append({
                    "id": doc_id,
                    "text": data["documents"][i] if data["documents"] else "",
                    "hs_code": meta.get("hs_code", ""),
                    "description": meta.get("description", ""),
                    "source": meta.get("source", ""),
                })
        return {"precedents": items, "total": col.count()}
    except Exception as e:
        logger.warning("precedents_list_failed", error=str(e)[:100])
        return {"precedents": [], "total": 0, "error": str(e)[:200]}


@router.delete("/precedents/{precedent_id}")
async def delete_precedent(precedent_id: str):
    """Удалить неверный прецедент."""
    from app.services.index_manager import get_index_manager
    idx = get_index_manager()
    if not idx._chroma_client:
        raise HTTPException(500, "ChromaDB not connected")
    try:
        col = idx._chroma_client.get_or_create_collection("precedents")
        col.delete(ids=[precedent_id])
        logger.info("precedent_deleted", id=precedent_id)
        return {"status": "deleted", "id": precedent_id}
    except Exception as e:
        raise HTTPException(500, f"Delete failed: {str(e)}")


class ExtractFactsRequest(BaseModel):
    items: list[dict]

@router.post("/extract-facts")
async def extract_facts(data: ExtractFactsRequest):
    """Извлечь факты (description→hs_code) из подтверждённых позиций и сохранить как прецеденты."""
    from app.services.index_manager import get_index_manager
    idx = get_index_manager()
    saved = 0
    for item in data.items:
        desc = item.get("description", "")
        hs = item.get("hs_code", "")
        if desc and hs and len(hs) >= 6:
            try:
                idx.add_precedent(desc, hs, metadata={
                    "source": "extract_facts",
                    "quantity": item.get("quantity"),
                    "unit_price": item.get("unit_price"),
                })
                saved += 1
            except Exception as e:
                logger.warning("extract_fact_failed", desc=desc[:40], error=str(e)[:80])
    logger.info("facts_extracted", total=len(data.items), saved=saved)
    return {"status": "ok", "saved": saved, "total": len(data.items)}


@router.post("/train-from-gtd")
async def train_from_gtd(files: list[UploadFile] = File(...)):
    """Извлечь прецеденты из готовых ДТ (PDF) и добавить их в память (ChromaDB)."""
    from app.services.gtd_reference_extractor import extract_gtd_reference
    from app.services.index_manager import get_index_manager

    idx = get_index_manager()
    total_saved = 0
    total_files = len(files)

    for f in files:
        try:
            content = await f.read()
            reference = extract_gtd_reference(content, f.filename or "GTD.pdf")

            for it in reference.get("items", []):
                hs = (it.get("hs_code") or "").strip()
                desc = it.get("description", "").strip()
                if len(hs) >= 6 and desc:
                    idx.add_precedent(desc, hs[:10], metadata={
                        "source": "gtd_training",
                        "filename": f.filename
                    })
                    total_saved += 1
                    
        except Exception as e:
            logger.error("gtd_training_failed", filename=f.filename, error=str(e))
            
    return {"status": "ok", "files_processed": total_files, "precedents_saved": total_saved}


@router.post("/extract-gtd-reference")
async def extract_gtd_reference_endpoint(files: list[UploadFile] = File(...)):
    """Извлечь эталонные reference-данные из готовых GTD PDF без сохранения в память."""
    from app.services.gtd_reference_extractor import extract_gtd_reference

    references: list[dict] = []
    for f in files:
        try:
            content = await f.read()
            if not content:
                continue
            references.append(extract_gtd_reference(content, f.filename or "GTD.pdf"))
        except Exception as e:
            logger.error("gtd_reference_extract_failed", filename=f.filename, error=str(e))
            references.append({
                "filename": f.filename or "GTD.pdf",
                "header": {},
                "items": [],
                "error": str(e)[:200],
            })

    return {
        "status": "ok",
        "files_processed": len(references),
        "references": references,
    }
