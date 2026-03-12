"""XML export & validation endpoints for customs declarations."""

from __future__ import annotations

import uuid

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from app.config import get_settings
from app.services.xml_builder import build_declaration_xml
from app.services.xml_validator import validate_declaration_xml

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter(prefix="/api/v1/integration", tags=["xml-export"])


# ---------------------------------------------------------------------------
# Helpers — fetch data from core-api
# ---------------------------------------------------------------------------

async def _headers_from_request(request: Request) -> dict[str, str]:
    """Forward Authorization header (if present) to core-api calls."""
    headers: dict[str, str] = {}
    auth = request.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth
    return headers


async def _fetch_declaration(declaration_id: uuid.UUID, headers: dict[str, str]) -> dict:
    """GET /api/v1/declarations/{id} from core-api."""
    url = f"{settings.CORE_API_URL}/api/v1/declarations/{declaration_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Declaration not found")
    if resp.status_code == 401:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if resp.status_code == 403:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if resp.status_code != 200:
        logger.error("core_api_error", url=url, status=resp.status_code, body=resp.text[:500])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"core-api returned {resp.status_code}",
        )
    return resp.json()


async def _fetch_items(declaration_id: uuid.UUID, headers: dict[str, str]) -> list[dict]:
    """GET /api/v1/declarations/{id}/items/ from core-api."""
    url = f"{settings.CORE_API_URL}/api/v1/declarations/{declaration_id}/items"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code != 200:
        logger.warning("core_api_items_error", url=url, status=resp.status_code)
        return []
    return resp.json()


async def _fetch_counterparty(
    counterparty_id: str | None,
    headers: dict[str, str],
) -> dict | None:
    """GET /api/v1/counterparties/{id} from core-api.  Returns None on miss."""
    if not counterparty_id:
        return None
    url = f"{settings.CORE_API_URL}/api/v1/counterparties/{counterparty_id}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code != 200:
        logger.warning("counterparty_not_found", id=counterparty_id, status=resp.status_code)
        return None
    return resp.json()


async def _gather_data(declaration_id: uuid.UUID, request: Request):
    """Fetch declaration, items, sender and receiver from core-api."""
    headers = await _headers_from_request(request)

    decl = await _fetch_declaration(declaration_id, headers)
    items = await _fetch_items(declaration_id, headers)

    sender = await _fetch_counterparty(decl.get("sender_counterparty_id"), headers)
    receiver = await _fetch_counterparty(decl.get("receiver_counterparty_id"), headers)

    return decl, items, sender, receiver


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/export-xml/{declaration_id}")
async def export_xml(declaration_id: uuid.UUID, request: Request):
    """Build XML for a declaration and return it as a downloadable file."""
    decl, items, sender, receiver = await _gather_data(declaration_id, request)

    xml_string = build_declaration_xml(
        decl=decl,
        items=items,
        sender=sender,
        receiver=receiver,
        payments=[],
    )

    # Validate before returning
    validation = validate_declaration_xml(xml_string)
    if not validation["valid"]:
        logger.warning(
            "xml_export_validation_failed",
            declaration_id=str(declaration_id),
            errors=validation["errors"],
        )

    number = decl.get("number_internal") or str(declaration_id)[:8]
    filename = f"declaration_{number}.xml"

    logger.info(
        "xml_exported",
        declaration_id=str(declaration_id),
        valid=validation["valid"],
        errors_count=len(validation["errors"]),
    )

    return Response(
        content=xml_string,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/validate-xml/{declaration_id}")
async def validate_xml(declaration_id: uuid.UUID, request: Request):
    """Build XML for a declaration and validate it without downloading."""
    decl, items, sender, receiver = await _gather_data(declaration_id, request)

    xml_string = build_declaration_xml(
        decl=decl,
        items=items,
        sender=sender,
        receiver=receiver,
        payments=[],
    )

    result = validate_declaration_xml(xml_string)

    logger.info(
        "xml_validated",
        declaration_id=str(declaration_id),
        valid=result["valid"],
        errors_count=len(result["errors"]),
        warnings_count=len(result["warnings"]),
    )

    return result
