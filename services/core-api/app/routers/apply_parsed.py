"""
Endpoint для применения распознанных данных из AI к декларации.
Маппинг OCR/LLM данных на графы ДТ.
"""
import uuid
from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import httpx
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import (
    Declaration, DeclarationStatus, DeclarationItem,
    Counterparty, Document, DeclarationLog, User, Company,
)
from app.schemas.declaration import DeclarationResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/declarations", tags=["apply-parsed"])


# --- Pydantic schemas for parsed data ---

class ParsedCounterparty(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    country_code: Optional[str] = None
    tax_number: Optional[str] = None
    type: str = "seller"  # seller, buyer, importer, declarant


class ParsedItem(BaseModel):
    line_no: int = 1
    description: Optional[str] = None
    commercial_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    hs_code: Optional[str] = None
    hs_code_name: Optional[str] = None
    country_origin_code: Optional[str] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    package_count: Optional[int] = None
    package_type: Optional[str] = None


class ParsedDocumentRef(BaseModel):
    doc_type: Optional[str] = None
    doc_number: Optional[str] = None
    file_key: Optional[str] = None
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    parsed_data: Optional[dict] = None


class ApplyParsedRequest(BaseModel):
    """Данные, распознанные AI из загруженных PDF."""
    # Из инвойса
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    seller: Optional[ParsedCounterparty] = None
    buyer: Optional[ParsedCounterparty] = None
    currency: Optional[str] = None
    total_amount: Optional[float] = None
    incoterms: Optional[str] = None
    country_origin: Optional[str] = None
    country_destination: Optional[str] = None

    # Из контракта
    contract_number: Optional[str] = None
    contract_date: Optional[str] = None

    # Из упаковочного листа
    total_packages: Optional[int] = None
    package_type: Optional[str] = None
    total_gross_weight: Optional[float] = None
    total_net_weight: Optional[float] = None

    # Из AWB / транспорта
    transport_doc_number: Optional[str] = None
    transport_type: Optional[str] = None  # 40=воздушный, 10=морской, 30=авто
    customs_office_code: Optional[str] = None  # Код таможенного поста (8 цифр)

    # Товарные позиции
    items: list[ParsedItem] = []

    # Ссылки на загруженные документы
    documents: list[ParsedDocumentRef] = []

    # Общие
    deal_nature_code: Optional[str] = "01"  # купля-продажа по умолчанию
    type_code: Optional[str] = "IM40"  # импорт по умолчанию

    # Транспортные расходы (графа 17)
    freight_amount: Optional[float] = None
    freight_currency: Optional[str] = None

    # Риски
    risk_score: Optional[int] = None
    risk_flags: Optional[dict] = None

    # Confidence
    confidence: Optional[float] = None


class ApplyParsedResponse(BaseModel):
    declaration_id: str
    status: str
    items_created: int
    counterparties_created: int
    documents_linked: int
    message: str


@router.post("/{declaration_id}/apply-parsed", response_model=ApplyParsedResponse)
async def apply_parsed_data(
    declaration_id: uuid.UUID,
    data: ApplyParsedRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Применить распознанные данные из AI к существующей декларации.
    Маппинг:
    - seller → графа 2 (отправитель)
    - buyer → графа 8 (получатель)
    - currency → графа 22 (валюта)
    - total_amount → графа 22 (сумма)
    - incoterms → графа 20
    - items[] → товарные позиции (графы 31-45)
    - transport → графы 18, 25, 26
    """
    # Найти декларацию
    result = await db.execute(
        select(Declaration).where(Declaration.id == declaration_id)
    )
    declaration = result.scalar_one_or_none()

    if not declaration:
        raise HTTPException(status_code=404, detail="Declaration not found")

    if declaration.status not in (DeclarationStatus.DRAFT, DeclarationStatus.CHECKING_LVL1):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot apply parsed data to declaration with status: {declaration.status}",
        )

    counters = {"counterparties": 0, "items": 0, "documents": 0}

    try:
        # --- 0. Подтянуть ИНН/КПП из компании + адрес СВХ по коду поста ---
        if current_user.company_id and not declaration.declarant_inn_kpp:
            company = await db.get(Company, current_user.company_id)
            if company:
                parts = [p for p in [company.inn, company.kpp] if p]
                if parts:
                    declaration.declarant_inn_kpp = "/".join(parts)

        # --- 1. Создать/найти контрагентов ---
        sender_id = None
        receiver_id = None

        if data.seller and data.seller.name:
            sender_id = await _find_or_create_counterparty(
                db, data.seller, "seller", current_user.company_id
            )
            counters["counterparties"] += 1

        if data.buyer and data.buyer.name:
            receiver_id = await _find_or_create_counterparty(
                db, data.buyer, "buyer", current_user.company_id
            )
            counters["counterparties"] += 1

        # --- 2. Обновить поля декларации ---
        if sender_id:
            declaration.sender_counterparty_id = sender_id
        if receiver_id:
            declaration.receiver_counterparty_id = receiver_id

        # Конвертация валюты через calc-service (курсы ЦБ)
        exchange_rate = Decimal("1")
        currency = data.currency or declaration.currency_code
        if data.currency:
            declaration.currency_code = data.currency
        if data.total_amount is not None:
            declaration.total_invoice_value = Decimal(str(data.total_amount))
            # Рассчитать таможенную стоимость в рублях
            if currency and currency.upper() != "RUB":
                try:
                    async with httpx.AsyncClient(timeout=10) as http:
                        resp = await http.get("http://calc-service:8005/api/v1/calc/exchange-rates/latest")
                        resp.raise_for_status()
                        rates = resp.json().get("rates", {})
                        rate_value = rates.get(currency.upper())
                        if rate_value and float(rate_value) > 0:
                            exchange_rate = Decimal(str(rate_value))
                            total_rub = Decimal(str(data.total_amount)) * exchange_rate
                        else:
                            logger.warning("currency_rate_not_found", currency=currency, available=list(rates.keys())[:10])
                            total_rub = Decimal(str(data.total_amount))
                except Exception as conv_err:
                    logger.warning("calc_service_convert_failed", error=str(conv_err), currency=currency)
                    total_rub = Decimal(str(data.total_amount))
                declaration.total_customs_value = total_rub.quantize(Decimal("0.01"))
                declaration.exchange_rate = exchange_rate
                logger.info("currency_converted",
                    currency=currency, amount=data.total_amount,
                    rate=float(exchange_rate), rub=float(total_rub))
            else:
                declaration.total_customs_value = Decimal(str(data.total_amount))
                exchange_rate = Decimal("1")
        if data.incoterms:
            declaration.incoterms_code = data.incoterms
        if data.country_origin:
            declaration.country_origin_code = (data.country_origin or "")[:2] or None
            declaration.country_dispatch_code = (data.country_origin or "")[:2] or None
            # Графа 11 — торговая страна = страна происхождения
            if not declaration.trading_country_code:
                declaration.trading_country_code = data.country_origin
        # country_destination: всегда RU если не указан
        declaration.country_destination_code = (data.country_destination or declaration.country_destination_code or "RU")[:2]
        if data.total_packages is not None:
            declaration.total_packages_count = data.total_packages
        if data.total_gross_weight is not None:
            declaration.total_gross_weight = Decimal(str(data.total_gross_weight))
        if data.total_net_weight is not None:
            declaration.total_net_weight = Decimal(str(data.total_net_weight))
        # deal_nature_code: всегда 01 (купля-продажа) если не указан
        declaration.deal_nature_code = data.deal_nature_code or declaration.deal_nature_code or "01"
        if data.type_code:
            declaration.type_code = data.type_code
        if data.transport_type:
            declaration.transport_type_border = data.transport_type
        if data.transport_doc_number:
            declaration.transport_at_border = data.transport_doc_number
        if data.customs_office_code and not declaration.customs_office_code:
            declaration.customs_office_code = data.customs_office_code[:8]
        if data.freight_amount is not None:
            declaration.freight_amount = Decimal(str(data.freight_amount))
        if data.freight_currency:
            declaration.freight_currency = data.freight_currency

        declaration.total_items_count = len(data.items) if data.items else 0

        # Адрес СВХ (графа 30): по коду таможенного поста из справочника
        if not declaration.goods_location and declaration.customs_office_code:
            from app.models import Classifier
            post_result = await db.execute(
                select(Classifier).where(
                    Classifier.classifier_type == "customs_post",
                    Classifier.code == declaration.customs_office_code,
                    Classifier.is_active == True,
                )
            )
            post = post_result.scalar_one_or_none()
            if post and post.meta and post.meta.get("address"):
                declaration.goods_location = post.meta["address"]
                logger.info("goods_location_from_post", code=declaration.customs_office_code, address=post.meta["address"][:50])

        # --- 3. Создать товарные позиции ---
        for item_data in data.items:
            item = DeclarationItem(
                declaration_id=declaration.id,
                item_no=item_data.line_no,
                description=item_data.description,
                commercial_name=item_data.commercial_name or item_data.description,
                hs_code=item_data.hs_code,
                country_origin_code=(item_data.country_origin_code or data.country_origin or "")[:2] or None,
                gross_weight=Decimal(str(item_data.gross_weight)) if item_data.gross_weight else None,
                net_weight=Decimal(str(item_data.net_weight)) if item_data.net_weight else None,
                unit_price=Decimal(str(item_data.unit_price)) if item_data.unit_price else None,
                package_count=item_data.package_count,
                package_type=item_data.package_type,
                additional_unit=item_data.unit,
                additional_unit_qty=Decimal(str(item_data.quantity)) if item_data.quantity else None,
                mos_method_code="01",  # Метод 1 по умолчанию (по стоимости сделки)
                risk_score=data.risk_score or 0,
                risk_flags=data.risk_flags,
            )

            # Рассчитать customs_value_rub через курс ЦБ
            if item_data.unit_price and item_data.quantity:
                line_val_currency = Decimal(str(item_data.unit_price * item_data.quantity))
                item.customs_value_rub = (line_val_currency * exchange_rate).quantize(Decimal("0.01"))

            db.add(item)
            counters["items"] += 1

        # --- 4. Привязать документы ---
        for doc_data in data.documents:
            doc = Document(
                declaration_id=declaration.id,
                doc_type=doc_data.doc_type or "other",
                file_key=doc_data.file_key,
                original_filename=doc_data.original_filename,
                mime_type=doc_data.mime_type or "application/pdf",
                file_size=doc_data.file_size,
                doc_number=doc_data.doc_number,
                parsed_data=doc_data.parsed_data,
            )
            db.add(doc)
            counters["documents"] += 1

        # --- 5. Логирование ---
        log_entry = DeclarationLog(
            declaration_id=declaration.id,
            user_id=current_user.id,
            action="apply_parsed",
            new_value={
                "source": "ai_parse_smart",
                "confidence": float(data.confidence) if data.confidence else 0.0,
                "items_created": counters["items"],
                "counterparties_created": counters["counterparties"],
                "documents_linked": counters["documents"],
                "invoice_number": data.invoice_number,
                "currency": data.currency,
                "total_amount": float(data.total_amount) if data.total_amount else None,
            },
        )
        db.add(log_entry)

        await db.commit()

        logger.info(
            "parsed_data_applied",
            declaration_id=str(declaration.id),
            user_id=str(current_user.id),
            items_created=counters["items"],
            counterparties_created=counters["counterparties"],
            documents_linked=counters["documents"],
            confidence=data.confidence,
        )

        return ApplyParsedResponse(
            declaration_id=str(declaration.id),
            status="applied",
            items_created=counters["items"],
            counterparties_created=counters["counterparties"],
            documents_linked=counters["documents"],
            message=f"Данные применены: {counters['items']} позиций, {counters['counterparties']} контрагентов",
        )

    except Exception as e:
        await db.rollback()
        logger.error(
            "apply_parsed_failed",
            declaration_id=str(declaration_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to apply parsed data: {str(e)}")


@router.post("/from-parsed", response_model=ApplyParsedResponse, status_code=201)
async def create_from_parsed(
    data: ApplyParsedRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Создать новую декларацию целиком из распознанных данных.
    Вызывается при нажатии "Создать декларацию из документов".
    """
    if not current_user.company_id:
        raise HTTPException(status_code=403, detail="User must be associated with a company")

    # Создать пустую декларацию
    declaration = Declaration(
        type_code=data.type_code or "IM40",
        company_id=current_user.company_id,
        status=DeclarationStatus.DRAFT,
        created_by=current_user.id,
    )
    db.add(declaration)
    await db.flush()

    logger.info(
        "declaration_created_from_parsed",
        declaration_id=str(declaration.id),
        user_id=str(current_user.id),
    )

    # Применить распознанные данные
    return await apply_parsed_data(declaration.id, data, db, current_user)


async def _find_or_create_counterparty(
    db: AsyncSession,
    parsed: ParsedCounterparty,
    cp_type: str,
    company_id: Optional[uuid.UUID],
) -> uuid.UUID:
    """Найти существующего контрагента или создать нового."""
    # Поиск по имени
    result = await db.execute(
        select(Counterparty).where(
            Counterparty.name == parsed.name,
            Counterparty.type == cp_type,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return existing.id

    # Создать нового
    counterparty = Counterparty(
        type=cp_type,
        name=parsed.name,
        country_code=parsed.country_code,
        tax_number=parsed.tax_number,
        address=parsed.address,
        company_id=company_id,
    )
    db.add(counterparty)
    await db.flush()

    logger.info(
        "counterparty_created",
        name=parsed.name,
        type=cp_type,
        country_code=parsed.country_code,
    )

    return counterparty.id
