"""
ARQ tasks for async AI document processing.
Replaces the synchronous call in smart_parser.py to prevent timeouts and OOM.

Worker startup: arq app.workers.tasks.WorkerSettings
"""
import re
import time
from typing import Optional
import structlog
import httpx
from arq.connections import RedisSettings

from app.config import get_settings
from app.services.agent_crew import DeclarationCrew
from app.services.usage_tracker import set_usage_context, reset_usage_context

logger = structlog.get_logger()


def _pad_hs(code: str) -> str:
    """Normalize HS code to exactly 10 digits."""
    c = re.sub(r"\D", "", str(code or ""))
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


async def process_declaration_task(
    ctx: dict,
    declaration_id: Optional[str] = None,
    file_data: list = None,
    request_id: Optional[str] = None,
) -> dict:
    """Background task: OCR + LLM extraction + HS classification + risks."""
    settings = get_settings()

    if not file_data:
        logger.error("task_no_files", declaration_id=declaration_id)
        return {"status": "error", "error": "No files provided"}

    logger.info(
        "background_task_start",
        task="process_declaration",
        declaration_id=declaration_id,
        files_count=len(file_data),
        request_id=request_id,
    )

    started_at = time.time()
    context_tokens = set_usage_context(
        declaration_id=declaration_id or "",
        operation="parse_smart_background",
    )

    try:
        crew = DeclarationCrew()
        result = crew.process_documents(file_data)

        for item in result.get("items", []):
            raw = item.get("hs_code", "")
            if raw:
                item["hs_code"] = _pad_hs(raw)
            for cand in item.get("hs_candidates", []):
                if cand.get("hs_code"):
                    cand["hs_code"] = _pad_hs(cand["hs_code"])

        elapsed_ms = int((time.time() - started_at) * 1000)
        logger.info(
            "background_task_complete",
            declaration_id=declaration_id,
            items_count=len(result.get("items", [])),
            confidence=result.get("confidence", 0.0),
            elapsed_ms=elapsed_ms,
            request_id=request_id,
        )

        # Apply parsed result to declaration in core-api
        if declaration_id:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    apply_resp = await client.post(
                        f"{settings.CORE_API_URL}/api/v1/internal/apply-parsed/{declaration_id}",
                        json=result,
                    )
                    logger.info(
                        "apply_parsed_result",
                        declaration_id=declaration_id,
                        status_code=apply_resp.status_code,
                        request_id=request_id,
                    )
            except Exception as ap_err:
                logger.warning("apply_parsed_failed", error=str(ap_err)[:200])

            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    await client.post(
                        f"{settings.CORE_API_URL}/api/v1/internal/task-complete",
                        json={
                            "declaration_id": declaration_id,
                            "status": "success",
                            "request_id": request_id,
                        },
                    )
            except Exception as cb_err:
                logger.warning("task_callback_failed", error=str(cb_err))

        return {
            "status": "success",
            "declaration_id": declaration_id,
            "result": result,
            "request_id": request_id,
            "elapsed_ms": elapsed_ms,
        }

    except Exception as e:
        logger.exception(
            "background_task_failed",
            declaration_id=declaration_id,
            error=str(e),
            request_id=request_id,
        )
        return {
            "status": "error",
            "declaration_id": declaration_id,
            "error": str(e),
            "request_id": request_id,
        }
    finally:
        reset_usage_context(context_tokens)


_worker_cfg = get_settings()


async def _worker_startup(ctx: dict):
    """Fetch LLM config from core-api DB on worker start (mirrors ai-service startup)."""
    from app.utils.logging import setup_logging
    setup_logging()

    import os
    settings = get_settings()
    try:
        resp = httpx.get(
            f"{settings.CORE_API_URL}/api/v1/settings/internal/llm-config",
            timeout=10,
        )
        if resp.status_code == 200:
            db_cfg = resp.json()
            key = db_cfg.get("llm_api_key", "")
            if key and key != "sk-your-key-here":
                os.environ["LLM_API_KEY"] = key
                os.environ["OPENAI_API_KEY"] = key
                for env_key, cfg_key in [
                    ("LLM_PROVIDER", "llm_provider"),
                    ("LLM_BASE_URL", "llm_base_url"),
                    ("LLM_MODEL", "openai_model"),
                    ("LLM_PROJECT_ID", "llm_project_id"),
                ]:
                    val = db_cfg.get(cfg_key, "")
                    if val:
                        os.environ[env_key] = val
                get_settings.cache_clear()
                logger.info(
                    "worker_llm_config_loaded",
                    provider=db_cfg.get("llm_provider"),
                    model=db_cfg.get("openai_model"),
                    key_prefix=key[:8] + "...",
                )
            else:
                logger.info("worker_no_llm_key_in_db")
        else:
            logger.warning("worker_llm_config_non_200", status=resp.status_code)
    except Exception as e:
        logger.warning("worker_llm_config_failed", error=str(e)[:100])


class WorkerSettings:
    """ARQ worker configuration. Start with: arq app.workers.tasks.WorkerSettings"""

    redis_settings = RedisSettings.from_dsn(_worker_cfg.REDIS_BROKER_URL)
    functions = [process_declaration_task]
    cron_jobs = []
    queue_name = _worker_cfg.ARQ_QUEUE_NAME
    max_jobs = _worker_cfg.ARQ_MAX_JOBS
    job_timeout = _worker_cfg.ARQ_JOB_TIMEOUT_SECONDS
    on_startup = _worker_startup
