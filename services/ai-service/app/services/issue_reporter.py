"""
Отправка проблем парсинга в core-api для персистентного хранения.
Используется для batch-тестирования: после 50+ деклараций агент выгружает все ошибки.
"""
import httpx
import structlog

from app.middleware.tracing import get_correlation_id

logger = structlog.get_logger()

CORE_API_URL = "http://core-api:8001"


def report_issue(
    stage: str,
    severity: str,
    message: str,
    details: dict = None,
    declaration_id: str = None,
):
    """
    Отправить проблему в core-api (синхронно, fire-and-forget).
    stage: ocr, regex, llm_enrich, hs_classify, apply_parsed, compile
    severity: error, warning, info
    """
    try:
        payload = {
            "stage": stage,
            "severity": severity,
            "message": message,
            "details": details,
            "declaration_id": declaration_id,
        }
        headers = {}
        cid = get_correlation_id()
        if cid:
            headers["X-Request-ID"] = cid
        httpx.post(
            f"{CORE_API_URL}/api/v1/internal/parse-issue",
            json=payload,
            headers=headers,
            timeout=5,
        )
        logger.debug("issue_reported", stage=stage, severity=severity, message=message[:80])
    except Exception as e:
        logger.warning("issue_report_failed", error=str(e)[:100])
