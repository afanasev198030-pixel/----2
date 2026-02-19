"""
Arize-Phoenix observability для LLM трейсинга.
Подключается к удалённому Phoenix серверу (контейнер customs-phoenix:6006).
Автоинструментация OpenAI calls — каждый LLM запрос логируется.
"""
import os
import structlog

logger = structlog.get_logger()


def init_observability(phoenix_host: str = "", phoenix_port: int = 6006):
    """Подключение к Phoenix серверу для трейсинга LLM вызовов."""
    if not phoenix_host:
        logger.info("observability_skipped", reason="PHOENIX_HOST not set")
        return

    collector_endpoint = f"http://{phoenix_host}:{phoenix_port}"

    try:
        from phoenix.otel import register
        tracer_provider = register(
            project_name="customs-ai-service",
            endpoint=f"{collector_endpoint}/v1/traces",
        )
        logger.info("phoenix_connected", endpoint=collector_endpoint)
    except ImportError:
        logger.info("phoenix_not_installed", msg="pip install arize-phoenix")
        return
    except Exception as e:
        logger.warning("phoenix_connect_failed", error=str(e)[:100])
        os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", collector_endpoint)

    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor
        OpenAIInstrumentor().instrument()
        logger.info("openai_instrumented_for_phoenix")
    except ImportError:
        logger.debug("openai_instrumentor_not_installed", msg="pip install openinference-instrumentation-openai")
    except Exception as e:
        logger.warning("openai_instrument_failed", error=str(e)[:80])

    logger.info("observability_initialized", endpoint=collector_endpoint)
