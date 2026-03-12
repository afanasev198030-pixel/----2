"""
Offline eval для HS-классификации.

Запуск:
  python -m app.services.offline_eval --dataset app/ml_models/hs_offline_eval_dataset.jsonl --min-accuracy 0.85
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import structlog

from app.services.dspy_modules import HSCodeClassifier
from app.services.index_manager import get_index_manager
from app.services.training_dataset import DATASET_FILE

logger = structlog.get_logger()


def _safe_code(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) < 6:
        return ""
    return digits[:10].ljust(10, "0")


def _load_dataset(path: Path, limit: int) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            desc = str(obj.get("description") or "").strip()
            code = _safe_code(str(obj.get("actual_hs_code") or ""))
            if len(desc) < 3 or not code:
                continue
            rows.append(
                {
                    "description": desc,
                    "actual_hs_code": code,
                    "context": obj.get("context") if isinstance(obj.get("context"), dict) else {},
                }
            )
    if limit > 0 and len(rows) > limit:
        rows = rows[-limit:]
    return rows


def run_eval(dataset_path: Path, min_accuracy: float, limit: int) -> int:
    rows = _load_dataset(dataset_path, limit)
    if not rows:
        print(
            json.dumps(
                {
                    "status": "skipped",
                    "reason": "dataset_empty_or_missing",
                    "dataset": str(dataset_path),
                },
                ensure_ascii=False,
            )
        )
        return 0

    idx = get_index_manager()
    clf = HSCodeClassifier()

    top1_hits = 0
    top3_hits = 0
    total = len(rows)

    for row in rows:
        desc = row["description"]
        actual = row["actual_hs_code"]
        rag = idx.search_hs_codes(desc)
        result = clf.classify(desc, rag)
        pred1 = _safe_code(result.get("hs_code", ""))
        candidates = [_safe_code(c.get("hs_code", "")) for c in (result.get("candidates") or [])]
        candidates = [c for c in candidates if c]

        if pred1 == actual:
            top1_hits += 1
        top3_pool = [pred1] + candidates[:3]
        if actual in top3_pool:
            top3_hits += 1

    accuracy = top1_hits / total
    top3_accuracy = top3_hits / total
    precision = accuracy
    recall = accuracy

    payload = {
        "status": "ok",
        "dataset": str(dataset_path),
        "samples": total,
        "metrics": {
            "accuracy_top1": round(accuracy, 4),
            "accuracy_top3": round(top3_accuracy, 4),
            "precision_top1": round(precision, 4),
            "recall_top1": round(recall, 4),
        },
        "thresholds": {"min_accuracy_top1": min_accuracy},
    }
    print(json.dumps(payload, ensure_ascii=False))
    logger.info("offline_eval_completed", **payload["metrics"], samples=total)

    if accuracy < min_accuracy:
        logger.error("offline_eval_failed_threshold", accuracy=accuracy, min_accuracy=min_accuracy)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default=str(DATASET_FILE))
    parser.add_argument("--min-accuracy", type=float, default=0.85)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()
    return run_eval(Path(args.dataset), args.min_accuracy, args.limit)


if __name__ == "__main__":
    sys.exit(main())
