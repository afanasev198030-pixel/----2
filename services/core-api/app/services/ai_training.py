"""
Автосбор обучающих примеров ТН ВЭД из утверждённых деклараций.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Declaration, DeclarationItem, Document, DeclarationStatus

logger = structlog.get_logger()


@dataclass
class TrainingSyncResult:
    scanned_declarations: int
    prepared_examples: int
    sent_examples: int
    dropped_examples: int


def _build_item_context(
    declaration: Declaration,
    item: DeclarationItem,
    documents: list[Document],
) -> dict[str, Any]:
    docs_compact: list[dict[str, Any]] = []
    for doc in documents:
        parsed_data = doc.parsed_data if isinstance(doc.parsed_data, dict) else {}
        docs_compact.append(
            {
                "doc_type": doc.doc_type,
                "filename": doc.original_filename,
                "doc_number": doc.doc_number,
                "parsed_data": parsed_data,
            }
        )

    return {
        "declaration": {
            "id": str(declaration.id),
            "status": declaration.status,
            "company_id": str(declaration.company_id),
            "currency_code": declaration.currency_code,
            "country_dispatch_code": declaration.country_dispatch_code,
            "country_destination_code": declaration.country_destination_code,
            "incoterms_code": declaration.incoterms_code,
            "total_invoice_value": float(declaration.total_invoice_value) if declaration.total_invoice_value is not None else None,
        },
        "item": {
            "id": str(item.id),
            "item_no": item.item_no,
            "description": item.description,
            "commercial_name": item.commercial_name,
            "country_origin_code": item.country_origin_code,
            "quantity": float(item.additional_unit_qty) if item.additional_unit_qty is not None else None,
            "unit": item.additional_unit,
            "unit_price": float(item.unit_price) if item.unit_price is not None else None,
        },
        "documents": docs_compact,
    }


async def collect_hs_training_examples(
    db: AsyncSession,
    limit_declarations: int = 200,
) -> tuple[list[dict[str, Any]], int]:
    """Собрать пары (контекст -> hs_code) из финальных деклараций."""
    result = await db.execute(
        select(Declaration)
        .where(
            Declaration.status == DeclarationStatus.SENT.value,
        )
        .options(
            selectinload(Declaration.items),
            selectinload(Declaration.documents),
        )
        .order_by(Declaration.updated_at.desc())
        .limit(limit_declarations)
    )
    declarations = result.scalars().all()

    examples: list[dict[str, Any]] = []
    dropped = 0
    seen_keys: set[tuple[str, str]] = set()

    for decl in declarations:
        docs = list(decl.documents or [])
        for item in decl.items or []:
            hs_code = (item.hs_code or "").strip()
            description = (item.description or item.commercial_name or "").strip()
            if not hs_code or len(hs_code) < 6 or not description:
                dropped += 1
                continue
            dedupe_key = (description.lower()[:300], hs_code[:10])
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            examples.append(
                {
                    "declaration_id": str(decl.id),
                    "item_id": str(item.id),
                    "company_id": str(decl.company_id),
                    "description": description[:500],
                    "actual_hs_code": hs_code[:10],
                    "context": _build_item_context(decl, item, docs),
                    "captured_at": datetime.utcnow().isoformat(),
                    "source": "approved_declaration",
                }
            )

    return examples, dropped


async def push_hs_training_examples(
    ai_service_url: str,
    examples: list[dict[str, Any]],
    timeout_s: int = 30,
) -> int:
    if not examples:
        return 0
    endpoint = f"{ai_service_url.rstrip('/')}/api/v1/ai/train-batch"
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response = await client.post(endpoint, json={"examples": examples})
        response.raise_for_status()
        payload = response.json() if response.content else {}
        return int(payload.get("accepted", len(examples)))


async def run_hs_training_sync(
    db: AsyncSession,
    ai_service_url: str,
    limit_declarations: int = 200,
) -> TrainingSyncResult:
    examples, dropped = await collect_hs_training_examples(
        db=db,
        limit_declarations=limit_declarations,
    )

    accepted = await push_hs_training_examples(
        ai_service_url=ai_service_url,
        examples=examples,
    )

    logger.info(
        "hs_training_sync_completed",
        scanned_declarations=limit_declarations,
        prepared_examples=len(examples),
        dropped_examples=dropped,
        accepted_examples=accepted,
    )
    return TrainingSyncResult(
        scanned_declarations=limit_declarations,
        prepared_examples=len(examples),
        sent_examples=accepted,
        dropped_examples=dropped,
    )
