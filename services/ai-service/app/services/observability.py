"""
Arize-Phoenix observability для LLM трейсинга.
Автоинструментация LlamaIndex + DSPy.
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

    # Instrument LlamaIndex
    try:
        from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
        LlamaIndexInstrumentor().instrument()
        logger.info("llamaindex_instrumented")
    except ImportError:
        logger.info("llamaindex_instrumentor_not_installed")
    except Exception as e:
        logger.warning("llamaindex_instrument_failed", error=str(e))

    # Instrument DSPy
    try:
        from openinference.instrumentation.dspy import DSPyInstrumentor
        DSPyInstrumentor().instrument()
        logger.info("dspy_instrumented")
    except ImportError:
        logger.info("dspy_instrumentor_not_installed")
    except Exception as e:
        logger.warning("dspy_instrument_failed", error=str(e))

    logger.info("observability_initialized")
