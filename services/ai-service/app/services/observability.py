"""
Arize-Phoenix observability для LLM трейсинга.
Автоинструментация OpenAI calls.
"""
import structlog

logger = structlog.get_logger()


def init_observability(phoenix_host: str = "", phoenix_port: int = 6006):
    """Инициализация Phoenix observability. Вызывается при startup."""
    if not phoenix_host:
        logger.info("observability_skipped", reason="PHOENIX_HOST not set")
        return

    try:
        import phoenix as px
        px.launch_app()
        logger.info("phoenix_launched", host=phoenix_host, port=phoenix_port)
    except ImportError:
        logger.info("phoenix_not_installed", msg="pip install arize-phoenix")
        return
    except Exception as e:
        logger.warning("phoenix_launch_failed", error=str(e))

    # Instrument OpenAI calls
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor
        OpenAIInstrumentor().instrument()
        logger.info("openai_instrumented")
    except ImportError:
        logger.debug("openai_instrumentor_not_installed", msg="pip install openinference-instrumentation-openai")
    except Exception as e:
        logger.warning("openai_instrument_failed", error=str(e))

    logger.info("observability_initialized")
