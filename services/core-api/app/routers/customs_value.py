"""CRUD + auto-generation for Customs Value Declaration (ДТС-1)."""
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog
import httpx
import os

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import (
    User,
    Declaration,
    DeclarationItem,
)
from app.models.customs_value_declaration import CustomsValueDeclaration
from app.models.customs_value_item import CustomsValueItem
from app.schemas.customs_value_declaration import (
    CustomsValueDeclarationResponse,
    CustomsValueDeclarationUpdate,
    CustomsValueItemUpdate,
    CustomsValueItemResponse,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/api/v1/declarations/{decl_id}/dts",
    tags=["customs-value-declaration"],
)

Q2 = Decimal("0.01")
CALC_SERVICE = os.environ.get("CALC_SERVICE_URL", "http://calc-service:8005")


def _d(val) -> Decimal:
    """Safely cast to Decimal, defaulting to 0."""
    if val is None:
        return Decimal(0)
    return Decimal(str(val))


def _recalc_item(item: CustomsValueItem) -> None:
    """Recompute derived fields for a single ДТС item (графы 12, 20, 24, 25)."""
    ipn = _d(item.invoice_price_national)
    ip = _d(item.indirect_payments)
    item.base_total = (ipn + ip).quantize(Q2, ROUND_HALF_UP)

    additions = (
        _d(item.broker_commission)
        + _d(item.packaging_cost)
        + _d(item.raw_materials)
        + _d(item.tools_molds)
        + _d(item.consumed_materials)
        + _d(item.design_engineering)
        + _d(item.license_payments)
        + _d(item.seller_income)
        + _d(item.transport_cost)
        + _d(item.loading_unloading)
        + _d(item.insurance_cost)
    )
    item.additions_total = additions.quantize(Q2, ROUND_HALF_UP)

    deductions = (
        _d(item.construction_after_import)
        + _d(item.inland_transport)
        + _d(item.duties_taxes)
    )
    item.deductions_total = deductions.quantize(Q2, ROUND_HALF_UP)

    item.customs_value_national = (
        _d(item.base_total) + _d(item.additions_total) - _d(item.deductions_total)
    ).quantize(Q2, ROUND_HALF_UP)


async def _fetch_usd_rate(currency_code: str, request_headers: dict | None = None) -> Decimal:
    """Get USD exchange rate from calc-service."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{CALC_SERVICE}/api/v1/calc/exchange-rate",
                params={"currency": "USD"},
            )
            if resp.status_code == 200:
                data = resp.json()
                rate = data.get("rate") or data.get("exchange_rate")
                if rate:
                    return Decimal(str(rate))
    except Exception as exc:
        logger.warning("dts_usd_rate_fetch_failed", error=str(exc))
    return Decimal("90.00")


async def _get_declaration(decl_id: uuid.UUID, db: AsyncSession) -> Declaration:
    result = await db.execute(
        select(Declaration)
        .options(selectinload(Declaration.items))
        .where(Declaration.id == decl_id)
    )
    decl = result.scalar_one_or_none()
    if not decl:
        raise HTTPException(status_code=404, detail="Declaration not found")
    return decl


async def _get_cvd(decl_id: uuid.UUID, db: AsyncSession) -> CustomsValueDeclaration:
    result = await db.execute(
        select(CustomsValueDeclaration)
        .options(selectinload(CustomsValueDeclaration.items))
        .where(CustomsValueDeclaration.declaration_id == decl_id)
    )
    cvd = result.scalar_one_or_none()
    if not cvd:
        raise HTTPException(status_code=404, detail="Customs value declaration not found")
    return cvd


# ───── GET ─────
@router.get("/", response_model=CustomsValueDeclarationResponse)
async def get_dts(
    decl_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _get_cvd(decl_id, db)


# ───── GENERATE ─────
@router.post(
    "/generate",
    response_model=CustomsValueDeclarationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_dts(
    decl_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-generate ДТС-1 from Declaration data."""
    existing = await db.execute(
        select(CustomsValueDeclaration).where(
            CustomsValueDeclaration.declaration_id == decl_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Customs value declaration already exists for this declaration",
        )

    decl = await _get_declaration(decl_id, db)
    exchange_rate = _d(decl.exchange_rate) if decl.exchange_rate else Decimal(1)
    usd_rate = await _fetch_usd_rate(decl.currency_code or "USD")
    usd_rate = _d(usd_rate)

    freight_rub = Decimal(0)
    if decl.freight_amount:
        if decl.freight_currency and decl.freight_currency != "RUB":
            freight_rub = _d(decl.freight_amount) * exchange_rate
        else:
            freight_rub = _d(decl.freight_amount)

    total_gross = sum(_d(it.gross_weight) for it in decl.items) or Decimal(1)

    cvd = CustomsValueDeclaration(
        declaration_id=decl_id,
        form_type="DTS1",
        filler_name=decl.signatory_name,
        filler_date=date.today(),
        filler_position=decl.signatory_position,
        filler_document=decl.signatory_id_doc,
        transport_carrier_name=decl.transport_at_border or decl.transport_on_border_id,
        transport_destination=decl.delivery_place,
        usd_exchange_rate=usd_rate,
    )
    db.add(cvd)
    await db.flush()

    items_sorted = sorted(decl.items, key=lambda i: i.item_no or 0)
    currency = decl.currency_code or "USD"

    for item in items_sorted:
        # Графа 11(а): unit_price уже хранит графу 42 ДТ (итого стоимость товара)
        if item.unit_price:
            item_price_foreign = _d(item.unit_price)
        elif len(items_sorted) == 1 and decl.total_invoice_value:
            item_price_foreign = _d(decl.total_invoice_value)
        else:
            item_price_foreign = Decimal(0)

        item_price_national = (item_price_foreign * exchange_rate).quantize(Q2, ROUND_HALF_UP)

        weight_share = _d(item.gross_weight) / total_gross if total_gross else Decimal(0)
        transport = (freight_rub * weight_share).quantize(Q2, ROUND_HALF_UP)

        # Пересчёт валют (раздел * ДТС-1)
        conversions: list[dict] = []
        if item_price_foreign > 0 and currency != "RUB":
            conversions.append({
                "item_no": item.item_no or 0,
                "graph": "11",
                "currency_code": currency,
                "amount_foreign": float(item_price_foreign.quantize(Q2, ROUND_HALF_UP)),
                "exchange_rate": float(exchange_rate),
            })
        if transport > 0 and decl.freight_amount and decl.freight_currency and decl.freight_currency != "RUB":
            freight_foreign_share = (_d(decl.freight_amount) * weight_share).quantize(Q2, ROUND_HALF_UP)
            conversions.append({
                "item_no": item.item_no or 0,
                "graph": "17",
                "currency_code": decl.freight_currency,
                "amount_foreign": float(freight_foreign_share),
                "exchange_rate": float(exchange_rate),
            })

        cvi = CustomsValueItem(
            customs_value_declaration_id=cvd.id,
            declaration_item_id=item.id,
            item_no=item.item_no or 0,
            hs_code=item.hs_code,
            invoice_price_foreign=item_price_foreign.quantize(Q2, ROUND_HALF_UP),
            invoice_price_national=item_price_national,
            indirect_payments=Decimal(0),
            transport_cost=transport,
            currency_conversions=conversions if conversions else None,
        )
        _recalc_item(cvi)

        if usd_rate and usd_rate > 0:
            cvi.customs_value_usd = (
                _d(cvi.customs_value_national) / usd_rate
            ).quantize(Q2, ROUND_HALF_UP)

        db.add(cvi)

    await db.commit()

    return await _get_cvd(decl_id, db)


# ───── UPDATE header ─────
@router.put("/", response_model=CustomsValueDeclarationResponse)
async def update_dts(
    decl_id: uuid.UUID,
    data: CustomsValueDeclarationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cvd = await _get_cvd(decl_id, db)
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(cvd, key, val)
    await db.commit()
    return await _get_cvd(decl_id, db)


# ───── UPDATE item ─────
@router.put("/items/{item_id}", response_model=CustomsValueItemResponse)
async def update_dts_item(
    decl_id: uuid.UUID,
    item_id: uuid.UUID,
    data: CustomsValueItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cvd = await _get_cvd(decl_id, db)
    result = await db.execute(
        select(CustomsValueItem).where(
            CustomsValueItem.id == item_id,
            CustomsValueItem.customs_value_declaration_id == cvd.id,
        )
    )
    cvi = result.scalar_one_or_none()
    if not cvi:
        raise HTTPException(status_code=404, detail="Customs value item not found")

    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(cvi, key, val)

    _recalc_item(cvi)

    usd_rate = _d(await _fetch_usd_rate("USD"))
    if usd_rate > 0:
        cvd.usd_exchange_rate = usd_rate
        cvi.customs_value_usd = (
            _d(cvi.customs_value_national) / usd_rate
        ).quantize(Q2, ROUND_HALF_UP)

    await db.commit()
    await db.refresh(cvi)
    return cvi


# ───── RECALCULATE all items ─────
@router.post("/recalculate", response_model=CustomsValueDeclarationResponse)
async def recalculate_dts(
    decl_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cvd = await _get_cvd(decl_id, db)
    usd_rate = await _fetch_usd_rate("USD")
    cvd.usd_exchange_rate = usd_rate

    for cvi in cvd.items:
        _recalc_item(cvi)
        if usd_rate and usd_rate > 0:
            cvi.customs_value_usd = (
                _d(cvi.customs_value_national) / usd_rate
            ).quantize(Q2, ROUND_HALF_UP)

    await db.commit()
    return await _get_cvd(decl_id, db)


# ───── DELETE ─────
@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dts(
    decl_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cvd = await _get_cvd(decl_id, db)
    await db.delete(cvd)
    await db.commit()
