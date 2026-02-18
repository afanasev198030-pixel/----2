"""
Smart Parser роутер — мультизагрузка PDF, CrewAI оркестрация.
POST /api/v1/ai/parse-smart — парсинг нескольких PDF → данные для декларации
POST /api/v1/ai/parse-smart-stream — SSE стрим с прогрессом
POST /api/v1/ai/classify-hs-rag — RAG классификация ТН ВЭД
POST /api/v1/ai/check-risks-rag — RAG проверка рисков
"""
import json
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import structlog

from app.services.agent_crew import DeclarationCrew
from app.services.index_manager import get_index_manager
from app.services.dspy_modules import HSCodeClassifier, RiskAnalyzer

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/ai", tags=["smart-parser"])


# Global progress store
_progress: dict = {}


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


@router.post("/parse-smart")
async def parse_smart(files: list[UploadFile] = File(...)):
    """
    Мультизагрузка PDF файлов → автопарсинг → данные для декларации.
    """
    import uuid as _uuid
    request_id = str(_uuid.uuid4())[:8]

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Too many files (max 20)")

    filenames = [f.filename for f in files]
    logger.info("parse_smart_start", files_count=len(files), filenames=filenames, request_id=request_id)

    try:
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

        # Step 2-5: Process through crew with progress callbacks
        _send_event(request_id, "parsing", "Распознавание документов (OCR)...", 15)

        crew = DeclarationCrew()
        crew._progress_callback = lambda step, detail, pct: _send_event(request_id, step, detail, pct)
        result = crew.process_documents(file_data)

        _send_event(request_id, "complete", "Готово!", 100)

        logger.info(
            "parse_smart_complete",
            items_count=len(result.get("items", [])),
            confidence=result.get("confidence", 0),
            risk_score=result.get("risk_score", 0),
            request_id=request_id,
        )

        # Normalize ALL HS codes to exactly 10 digits
        import re as _re
        def _pad_hs(code: str) -> str:
            c = _re.sub(r"\D", "", str(code or ""))
            if len(c) < 4:
                return ""
            if len(c) < 10:
                c = c.ljust(10, "0")
            return c[:10]

        for item in result.get("items", []):
            raw = item.get("hs_code", "")
            if raw:
                item["hs_code"] = _pad_hs(raw)
            for cand in item.get("hs_candidates", []):
                if cand.get("hs_code"):
                    cand["hs_code"] = _pad_hs(cand["hs_code"])

        # Include request_id in response for progress tracking
        result["request_id"] = request_id

        # Сохраняем last_parse для дебаг-панели
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

        # Clean up progress after 60s
        asyncio.get_event_loop().call_later(60, lambda: _progress.pop(request_id, None))

        return result

    except HTTPException:
        raise
    except Exception as e:
        _send_event(request_id, "error", f"Ошибка: {str(e)}", -1)
        logger.error("parse_smart_failed", error=str(e), exc_info=True, request_id=request_id)
        raise HTTPException(status_code=500, detail=f"Failed to parse documents: {str(e)}")


class ClassifyHSRequest(BaseModel):
    description: str
    country_origin: Optional[str] = None
    unit_price: Optional[float] = None


@router.post("/classify-hs-rag")
async def classify_hs_rag(request: ClassifyHSRequest):
    """
    RAG классификация ТН ВЭД.
    LlamaIndex → top-10 кодов → DSPy выбирает точный 10-значный код.
    """
    if not request.description:
        raise HTTPException(status_code=400, detail="Description is required")

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

        # Ensure 10-digit HS codes
        import re as _re
        def _pad10(code):
            c = _re.sub(r"\D", "", str(code or ""))
            if len(c) < 4: return ""
            return c.ljust(10, "0")[:10]
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
