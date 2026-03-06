"""
Track AI token usage and report to core-api for cost governance (Phase 4.3).
Pricing per 1M tokens (approximate, March 2026):
  gpt-4.1:      input $2.00, output $8.00
  gpt-4.1-mini: input $0.40, output $1.60
  gpt-4o:       input $2.50, output $10.00
  deepseek-chat: input $0.27, output $1.10
"""
import time
import httpx
import structlog
from typing import Optional

from app.middleware.tracing import get_correlation_id

logger = structlog.get_logger()

CORE_API_URL = "http://core-api:8001"

PRICING_PER_M = {
    "gpt-4.1":       {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini":  {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano":  {"input": 0.10, "output": 0.40},
    "gpt-4o":        {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":   {"input": 0.15, "output": 0.60},
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
}


def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING_PER_M.get(model, {"input": 2.00, "output": 8.00})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def track_usage(
    response,
    operation: str,
    model: str = "",
    provider: str = "",
    declaration_id: str = "",
    company_id: str = "",
    duration_ms: int = 0,
):
    """Extract token usage from OpenAI response and send to core-api."""
    try:
        usage = getattr(response, "usage", None)
        if not usage:
            return

        from app.config import get_settings
        settings = get_settings()
        model_name = model or settings.effective_model
        prov = provider or settings.LLM_PROVIDER

        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", 0) or (input_tokens + output_tokens)
        cost = calc_cost(model_name, input_tokens, output_tokens)

        logger.info("ai_usage",
                     operation=operation, model=model_name,
                     input_tokens=input_tokens, output_tokens=output_tokens,
                     cost_usd=round(cost, 6), duration_ms=duration_ms)

        headers = {}
        cid = get_correlation_id()
        if cid:
            headers["X-Request-ID"] = cid

        httpx.post(
            f"{CORE_API_URL}/api/v1/internal/ai-usage",
            json={
                "company_id": company_id,
                "declaration_id": declaration_id,
                "operation": operation,
                "model": model_name,
                "provider": prov,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost_usd": round(cost, 6),
                "duration_ms": duration_ms,
            },
            headers=headers,
            timeout=3,
        )
    except Exception as e:
        logger.debug("usage_track_failed", error=str(e)[:80])


class TrackedLLM:
    """Wrapper around OpenAI client that tracks token usage."""

    def __init__(self, client, operation: str = "chat", declaration_id: str = "", company_id: str = ""):
        self._client = client
        self._operation = operation
        self._declaration_id = declaration_id
        self._company_id = company_id

    def chat_complete(self, **kwargs):
        start = time.time()
        response = self._client.chat.completions.create(**kwargs)
        duration_ms = int((time.time() - start) * 1000)
        track_usage(
            response,
            operation=self._operation,
            model=kwargs.get("model", ""),
            declaration_id=self._declaration_id,
            company_id=self._company_id,
            duration_ms=duration_ms,
        )
        return response
