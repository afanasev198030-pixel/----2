"""XML export & validation endpoints for customs declarations (EEC R.055)."""

from __future__ import annotations

import uuid

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from app.config import get_settings
from app.services.xml_builder import build_declaration_xml
from app.services.xml_validator import validate_declaration_xml
from app.services.dts_xml_builder import build_dts_xml

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter(prefix="/api/v1/integration", tags=["xml-export"])


async def _headers_from_request(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    auth = request.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth
    return headers


async def _fetch_json(url: str, headers: dict[str, str], label: str = "resource") -> dict | list | None:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code == 404:
        return None
    if resp.status_code in (401, 403):
        raise HTTPException(status_code=resp.status_code, detail=f"Access denied fetching {label}")
    if resp.status_code != 200:
        logger.error("core_api_error", url=url, status=resp.status_code, body=resp.text[:500])
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"core-api returned {resp.status_code} for {label}")
    return resp.json()


async def _fetch_declaration(declaration_id: uuid.UUID, headers: dict[str, str]) -> dict:
    url = f"{settings.CORE_API_URL}/api/v1/declarations/{declaration_id}"
    result = await _fetch_json(url, headers, "declaration")
    if result is None:
        raise HTTPException(status_code=404, detail="Declaration not found")
    return result


async def _fetch_items(declaration_id: uuid.UUID, headers: dict[str, str]) -> list[dict]:
    url = f"{settings.CORE_API_URL}/api/v1/declarations/{declaration_id}/items"
    return await _fetch_json(url, headers, "items") or []


async def _fetch_counterparty(cp_id: str | None, headers: dict[str, str]) -> dict | None:
    if not cp_id:
        return None
    url = f"{settings.CORE_API_URL}/api/v1/counterparties/{cp_id}"
    return await _fetch_json(url, headers, "counterparty")


async def _fetch_payments(declaration_id: uuid.UUID, headers: dict[str, str]) -> list[dict]:
    url = f"{settings.CORE_API_URL}/api/v1/declarations/{declaration_id}/payments"
    result = await _fetch_json(url, headers, "payments")
    return result if isinstance(result, list) else []


async def _fetch_item_sub(
    declaration_id: uuid.UUID,
    items: list[dict],
    sub_path: str,
    headers: dict[str, str],
) -> dict[str, list[dict]]:
    """Fetch sub-resources (documents or preceding-docs) for each item, keyed by item_id."""
    result: dict[str, list[dict]] = {}
    for item in items:
        item_id = str(item.get("id", ""))
        if not item_id:
            continue
        url = (f"{settings.CORE_API_URL}/api/v1/declarations/{declaration_id}"
               f"/items/{item_id}/{sub_path}/")
        data = await _fetch_json(url, headers, sub_path)
        if isinstance(data, list) and data:
            result[item_id] = data
    return result


async def _gather_data(declaration_id: uuid.UUID, request: Request):
    headers = await _headers_from_request(request)

    decl = await _fetch_declaration(declaration_id, headers)
    items = await _fetch_items(declaration_id, headers)
    declarant = await _fetch_counterparty(decl.get("declarant_counterparty_id"), headers)
    sender = await _fetch_counterparty(decl.get("sender_counterparty_id"), headers)
    receiver = await _fetch_counterparty(decl.get("receiver_counterparty_id"), headers)
    financial = await _fetch_counterparty(decl.get("financial_counterparty_id"), headers)
    payments = await _fetch_payments(declaration_id, headers)
    item_documents = await _fetch_item_sub(declaration_id, items, "item-documents", headers)
    item_preceding_docs = await _fetch_item_sub(declaration_id, items, "preceding-docs", headers)

    return decl, items, declarant, sender, receiver, financial, payments, item_documents, item_preceding_docs


@router.get("/export-xml/{declaration_id}")
async def export_xml(declaration_id: uuid.UUID, request: Request):
    """Build EEC R.055 XML for a declaration and return it as a downloadable file."""
    (decl, items, declarant, sender, receiver,
     financial, payments, item_documents, item_preceding_docs) = await _gather_data(declaration_id, request)

    xml_string = build_declaration_xml(
        decl=decl,
        items=items,
        declarant=declarant,
        sender=sender,
        receiver=receiver,
        financial=financial,
        payments=payments,
        item_documents=item_documents,
        item_preceding_docs=item_preceding_docs,
    )

    validation = validate_declaration_xml(xml_string)
    if not validation["valid"]:
        logger.warning("xml_export_validation_failed",
                       declaration_id=str(declaration_id),
                       errors=validation["errors"])

    number = decl.get("number_internal") or str(declaration_id)[:8]
    filename = f"declaration_{number}.xml"

    logger.info("xml_exported",
                declaration_id=str(declaration_id),
                valid=validation["valid"],
                xsd_valid=validation.get("xsd_valid"),
                errors_count=len(validation["errors"]))

    return Response(
        content=xml_string,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/validate-xml/{declaration_id}")
async def validate_xml(declaration_id: uuid.UUID, request: Request):
    """Build XML and validate without downloading."""
    (decl, items, declarant, sender, receiver,
     financial, payments, item_documents, item_preceding_docs) = await _gather_data(declaration_id, request)

    xml_string = build_declaration_xml(
        decl=decl,
        items=items,
        declarant=declarant,
        sender=sender,
        receiver=receiver,
        financial=financial,
        payments=payments,
        item_documents=item_documents,
        item_preceding_docs=item_preceding_docs,
    )

    result = validate_declaration_xml(xml_string)

    logger.info("xml_validated",
                declaration_id=str(declaration_id),
                valid=result["valid"],
                xsd_valid=result.get("xsd_valid"),
                errors_count=len(result["errors"]),
                warnings_count=len(result["warnings"]))

    return result


# ───── ДТС XML export ─────

async def _fetch_dts(declaration_id: uuid.UUID, headers: dict[str, str]) -> dict | None:
    url = f"{settings.CORE_API_URL}/api/v1/declarations/{declaration_id}/dts/"
    return await _fetch_json(url, headers, "customs-value-declaration")


@router.get("/export-dts-xml/{declaration_id}")
async def export_dts_xml(declaration_id: uuid.UUID, request: Request):
    """Build ДТС-1 XML and return as downloadable file."""
    headers = await _headers_from_request(request)

    decl = await _fetch_declaration(declaration_id, headers)
    dts = await _fetch_dts(declaration_id, headers)
    if dts is None:
        raise HTTPException(status_code=404, detail="Customs value declaration not found. Generate DTS first.")

    sender = await _fetch_counterparty(decl.get("sender_counterparty_id"), headers)
    receiver = await _fetch_counterparty(decl.get("receiver_counterparty_id"), headers)
    declarant = await _fetch_counterparty(decl.get("declarant_counterparty_id"), headers)

    xml_string = build_dts_xml(
        decl=decl,
        dts=dts,
        sender=sender,
        receiver=receiver,
        declarant=declarant,
    )

    number = decl.get("number_internal") or str(declaration_id)[:8]
    filename = f"dts_{number}.xml"

    logger.info("dts_xml_exported", declaration_id=str(declaration_id))

    return Response(
        content=xml_string,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
