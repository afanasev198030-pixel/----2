"""
Track AI token usage and report to core-api for cost governance (Phase 4.3).
Pricing per 1M tokens (approximate, March 2026):
  gpt-4.1:      input $2.00, output $8.00
  gpt-4.1-mini: input $0.40, output $1.60
  gpt-4o:       input $2.50, output $10.00
  deepseek-chat: input $0.27, output $1.10
"""
from contextvars import ContextVar
import time
from typing import Any

import httpx
import structlog

from app.middleware.tracing import get_correlation_id

logger = structlog.get_logger()

CORE_API_URL = "http://core-api:8001"

_declaration_ctx: ContextVar[str] = ContextVar("ai_usage_declaration_id", default="")
_company_ctx: ContextVar[str] = ContextVar("ai_usage_company_id", default="")
_operation_ctx: ContextVar[str] = ContextVar("ai_usage_operation", default="")

PRICING_PER_M = {
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "openai/gpt-oss-120b": {"input": 0.039, "output": 0.100},
}


def set_usage_context(declaration_id: str = "", company_id: str = "", operation: str = ""):
    """Set current declaration/company context for all nested LLM calls."""
    current_decl = _declaration_ctx.get()
    current_company = _company_ctx.get()
    current_operation = _operation_ctx.get()
    return (
        _declaration_ctx.set(declaration_id or current_decl),
        _company_ctx.set(company_id or current_company),
        _operation_ctx.set(operation or current_operation),
    )


def reset_usage_context(tokens) -> None:
    if not tokens:
        return
    decl_token, company_token, operation_token = tokens
    _declaration_ctx.reset(decl_token)
    _company_ctx.reset(company_token)
    _operation_ctx.reset(operation_token)


def get_usage_context() -> dict[str, str]:
    return {
        "declaration_id": _declaration_ctx.get(),
        "company_id": _company_ctx.get(),
        "operation": _operation_ctx.get(),
    }


def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING_PER_M.get(model, {"input": 2.00, "output": 8.00})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def _persist_usage(
    *,
    operation: str,
    model_name: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    declaration_id: str = "",
    company_id: str = "",
    duration_ms: int = 0,
) -> None:
    cost = calc_cost(model_name, input_tokens, output_tokens)

    logger.info(
        "ai_usage",
        operation=operation,
        model=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost, 6),
        declaration_id=declaration_id or None,
        duration_ms=duration_ms,
    )

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
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost, 6),
            "duration_ms": duration_ms,
        },
        headers=headers,
        timeout=3,
    )


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
        context = get_usage_context()
        model_name = model or settings.effective_model
        prov = provider or settings.LLM_PROVIDER
        declaration_id = declaration_id or context["declaration_id"]
        company_id = company_id or context["company_id"]
        operation = operation or context["operation"] or "chat"

        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", 0) or (input_tokens + output_tokens)
        _persist_usage(
            operation=operation,
            model_name=model_name,
            provider=prov,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            declaration_id=declaration_id,
            company_id=company_id,
            duration_ms=duration_ms,
        )
    except Exception as e:
        logger.debug("usage_track_failed", error=str(e)[:80])


class _TrackedChatCompletions:
    def __init__(self, completions, operation: str, declaration_id: str = "", company_id: str = ""):
        self._completions = completions
        self._operation = operation
        self._declaration_id = declaration_id
        self._company_id = company_id

    def create(self, *args, **kwargs):
        start = time.time()
        response = self._completions.create(*args, **kwargs)
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


class _TrackedChat:
    def __init__(self, chat, operation: str, declaration_id: str = "", company_id: str = ""):
        self._chat = chat
        self.completions = _TrackedChatCompletions(
            chat.completions,
            operation=operation,
            declaration_id=declaration_id,
            company_id=company_id,
        )

    def __getattr__(self, name):
        return getattr(self._chat, name)


class TrackedOpenAIClient:
    """OpenAI-compatible client proxy that auto-tracks all chat completions."""

    def __init__(self, client, operation: str = "chat", declaration_id: str = "", company_id: str = ""):
        self._client = client
        self.chat = _TrackedChat(
            client.chat,
            operation=operation,
            declaration_id=declaration_id,
            company_id=company_id,
        )

    def __getattr__(self, name):
        return getattr(self._client, name)


class DSPYUsageBridge:
    """DSPy-compatible usage tracker bridge."""

    def add_usage(self, lm: str, usage_entry: dict[str, Any]) -> None:
        try:
            context = get_usage_context()
            provider, model_name = (lm.split("/", 1) + ["unknown"])[:2] if "/" in lm else ("openai", lm)
            input_tokens = int(usage_entry.get("prompt_tokens") or usage_entry.get("input_tokens") or 0)
            output_tokens = int(usage_entry.get("completion_tokens") or usage_entry.get("output_tokens") or 0)
            total_tokens = int(usage_entry.get("total_tokens") or (input_tokens + output_tokens))
            operation = context["operation"] or "dspy_call"

            _persist_usage(
                operation=operation,
                model_name=model_name,
                provider=provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                declaration_id=context["declaration_id"],
                company_id=context["company_id"],
                duration_ms=0,
            )
        except Exception as e:
            logger.debug("dspy_usage_track_failed", error=str(e)[:80])
