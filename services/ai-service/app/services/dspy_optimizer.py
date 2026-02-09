"""
DSPy авто-оптимизация промптов.
BootstrapFewShot для HSCodeClassifier и InvoiceExtractor.
"""
import json
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()

_dspy_available = False
try:
    import dspy
    from dspy.teleprompt import BootstrapFewShot
    _dspy_available = True
except ImportError:
    logger.info("dspy_optimizer_skipped", reason="DSPy not installed")

MODELS_DIR = Path(__file__).parent.parent / "ml_models"


def hs_code_match(example, prediction, trace=None) -> bool:
    """Метрика: совпадение предсказанного кода ТН ВЭД с реальным."""
    predicted = getattr(prediction, 'hs_code', '').strip()
    expected = getattr(example, 'hs_code', '').strip()
    if not predicted or not expected:
        return False
    # Точное совпадение или совпадение первых 4 цифр
    return predicted == expected or predicted[:4] == expected[:4]


def optimize_hs_classifier(examples: list[dict], model: str = "gpt-4o") -> Optional[str]:
    """Оптимизировать HSCodeClassifier на примерах.

    Args:
        examples: [{"description": "...", "hs_code": "8501200009", "rag_results": "..."}]
    Returns:
        Path к сохранённому модулю или None
    """
    if not _dspy_available or len(examples) < 10:
        logger.info("hs_optimizer_skip", reason="not enough examples" if _dspy_available else "DSPy not available", count=len(examples))
        return None

    try:
        from app.services.dspy_modules import HSCodeSignature

        trainset = []
        for ex in examples:
            trainset.append(dspy.Example(
                description=ex["description"],
                rag_results=ex.get("rag_results", ""),
                hs_code=ex["hs_code"],
                name_ru=ex.get("name_ru", ""),
                reasoning=ex.get("reasoning", ""),
                confidence=str(ex.get("confidence", 0.8)),
            ).with_inputs("description", "rag_results"))

        module = dspy.Predict(HSCodeSignature)
        optimizer = BootstrapFewShot(metric=hs_code_match, max_bootstrapped_demos=4, max_labeled_demos=8)
        optimized = optimizer.compile(module, trainset=trainset)

        # Save
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        save_path = str(MODELS_DIR / "hs_classifier_optimized.json")
        optimized.save(save_path)
        logger.info("hs_classifier_optimized", path=save_path, examples=len(examples))
        return save_path

    except Exception as e:
        logger.error("hs_optimizer_failed", error=str(e), exc_info=True)
        return None


def optimize_invoice_extractor(examples: list[dict], model: str = "gpt-4o") -> Optional[str]:
    """Оптимизировать InvoiceExtractor на примерах."""
    if not _dspy_available or len(examples) < 5:
        return None

    try:
        from app.services.dspy_modules import InvoiceSignature

        def invoice_match(example, prediction, trace=None) -> bool:
            return bool(getattr(prediction, 'invoice_number', '').strip())

        trainset = []
        for ex in examples:
            trainset.append(dspy.Example(
                document_text=ex["text"],
                invoice_number=ex.get("invoice_number", ""),
                seller_name=ex.get("seller_name", ""),
                currency=ex.get("currency", ""),
                total_amount=str(ex.get("total_amount", "")),
            ).with_inputs("document_text"))

        module = dspy.Predict(InvoiceSignature)
        optimizer = BootstrapFewShot(metric=invoice_match, max_bootstrapped_demos=3)
        optimized = optimizer.compile(module, trainset=trainset)

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        save_path = str(MODELS_DIR / "invoice_extractor_optimized.json")
        optimized.save(save_path)
        logger.info("invoice_extractor_optimized", path=save_path, examples=len(examples))
        return save_path

    except Exception as e:
        logger.error("invoice_optimizer_failed", error=str(e), exc_info=True)
        return None
