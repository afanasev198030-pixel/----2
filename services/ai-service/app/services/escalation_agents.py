"""
Лёгкие агенты эскалации для конфликтных кейсов parse-smart.
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


class ReconciliationAgent:
    """Сверка сумм/весов/количества между шапкой и позициями."""

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        items = payload.get("items") or []
        issues: list[dict[str, Any]] = []
        evidence: dict[str, Any] = {}

        try:
            header_amount = float(payload.get("total_amount") or 0.0)
            items_amount = 0.0
            for it in items:
                qty = float(it.get("quantity") or it.get("additional_unit_qty") or 0.0)
                price = float(it.get("unit_price") or 0.0)
                line_total = it.get("line_total")
                if line_total is not None:
                    items_amount += float(line_total or 0.0)
                else:
                    items_amount += qty * price

            if header_amount > 0 and items_amount > 0:
                diff = abs(header_amount - items_amount)
                diff_pct = diff / max(header_amount, 0.01)
                evidence["invoice_amount_vs_items"] = {
                    "header_amount": round(header_amount, 2),
                    "items_amount": round(items_amount, 2),
                    "diff": round(diff, 2),
                    "diff_pct": round(diff_pct, 4),
                }
                if diff_pct > 0.1:
                    issues.append(
                        {
                            "code": "RECON_AMOUNT_MISMATCH",
                            "severity": "error",
                            "field": "total_amount",
                            "blocking": True,
                            "source": "reconciliation_agent",
                            "message": "Сумма в шапке декларации конфликтует с суммой по позициям (>10%).",
                        }
                    )
        except Exception as exc:
            logger.warning("reconciliation_agent_failed", error=str(exc)[:120])

        confidence = 0.86 if not issues else 0.62
        decision = "approve" if not issues else "needs_review"
        return {
            "agent": "ReconciliationAgent",
            "decision": decision,
            "confidence": confidence,
            "evidence": evidence,
            "issues": issues,
            "next_action": "continue_pipeline" if not issues else "request_human_review",
        }


class ReviewerAgent:
    """Финальная sanity-check перепроверка JSON-контракта."""

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        evidence: dict[str, Any] = {"fields_checked": []}

        required = ["currency", "total_amount", "items"]
        for field in required:
            evidence["fields_checked"].append(field)
            value = payload.get(field)
            if value in (None, "", []) and field != "items":
                issues.append(
                    {
                        "code": "REVIEWER_MISSING_FIELD",
                        "severity": "error",
                        "field": field,
                        "blocking": True,
                        "source": "reviewer_agent",
                        "message": f"Поле {field} не заполнено после компиляции.",
                    }
                )
        items = payload.get("items") or []
        if not items:
            issues.append(
                {
                    "code": "REVIEWER_EMPTY_ITEMS",
                    "severity": "error",
                    "field": "items",
                    "blocking": True,
                    "source": "reviewer_agent",
                    "message": "После парсинга нет товарных позиций.",
                }
            )

        confidence = 0.84 if not issues else 0.58
        decision = "approve" if not issues else "needs_review"
        return {
            "agent": "ReviewerAgent",
            "decision": decision,
            "confidence": confidence,
            "evidence": evidence,
            "issues": issues,
            "next_action": "continue_pipeline" if not issues else "request_human_review",
        }
