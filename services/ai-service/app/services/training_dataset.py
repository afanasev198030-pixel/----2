"""
Хранилище train/eval датасета для HS-классификации.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

DATASET_DIR = Path(__file__).parent.parent / "ml_models"
DATASET_FILE = DATASET_DIR / "hs_offline_eval_dataset.jsonl"


def append_examples(examples: list[dict[str, Any]]) -> int:
    """Append JSONL examples for offline eval and return accepted count."""
    if not examples:
        return 0
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    accepted = 0
    with DATASET_FILE.open("a", encoding="utf-8") as fp:
        for ex in examples:
            description = str(ex.get("description") or "").strip()
            hs_code = str(ex.get("actual_hs_code") or "").strip()
            if len(description) < 3 or len(hs_code) < 6:
                continue
            payload = {
                "description": description[:500],
                "actual_hs_code": hs_code[:10],
                "context": ex.get("context") if isinstance(ex.get("context"), dict) else {},
                "source": ex.get("source") or "train_batch",
                "declaration_id": ex.get("declaration_id") or "",
                "item_id": ex.get("item_id") or "",
                "company_id": ex.get("company_id") or "",
                "captured_at": ex.get("captured_at") or "",
            }
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
            accepted += 1
    logger.info("hs_training_examples_appended", accepted=accepted, file=str(DATASET_FILE))
    return accepted


def dataset_path() -> str:
    return str(DATASET_FILE)
