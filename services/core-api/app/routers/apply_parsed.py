"""
Endpoint для применения распознанных данных из AI к декларации.
Маппинг OCR/LLM данных на графы ДТ.
"""
import uuid
import re
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


def _to_decimal(value) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("\xa0", " ").replace(" ", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        logger.warning("decimal_parse_failed", raw=value)
        return None


def _normalize_digits(value: Optional[str]) -> str:
    return re.sub(r"\D", "", value or "")


def _parse_inn_kpp(raw_value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    raw = (raw_value or "").strip()
    if not raw:
        return None, None
    if "/" in raw:
        left, right = raw.split("/", 1)
        inn = _normalize_digits(left)
        kpp = _normalize_digits(right)
        return (inn or None), (kpp or None)
    digits = _normalize_digits(raw)
    # Collapsed INN+KPP formats without slash.
    if len(digits) == 19:  # 10 + 9
        return digits[:10], digits[10:]
    if len(digits) == 21:  # 12 + 9
        return digits[:12], digits[12:]
    if len(digits) in (10, 12):
        return digits, None
    return (digits or None), None


def _build_declarant_inn_kpp(company: Optional[Company], parsed_value: Optional[str]) -> Optional[str]:
    p_inn, p_kpp = _parse_inn_kpp(parsed_value)
    c_inn = _normalize_digits(company.inn) if company and company.inn else ""
    c_kpp = _normalize_digits(company.kpp) if company and company.kpp else ""
    # Declarant belongs to company: prefer company identifiers when available.
    inn = c_inn or (p_inn or "")
    kpp = c_kpp or (p_kpp or "")
    if inn and kpp:
        return f"{inn}/{kpp}"
    if inn:
        return inn
    return None


def _post_address_fallback(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    fallback = {
        "10005020": "г. Москва, аэропорт Внуково, Внуковское шоссе, д. 1",
        "10005030": "г. Москва, ул. Яузская, д. 8",
        "10002010": "Московская обл., г.о. Химки, аэропорт Шереметьево",
        "10002020": "Московская обл., г.о. Химки, аэропорт Шереметьево, Карго",
        "10009100": "Московская обл., г. Домодедово, аэропорт Домодедово",
        "10129060": "г. Санкт-Петербург, аэропорт Пулково",
        "10216120": "г. Санкт-Петербург, Гладкий остров",
        "10130090": "Приморский край, г. Находка, бухта Восточная",
        "10012020": "Новосибирская обл., аэропорт Толмачёво",
        "10009000": "Московская обл., г. Реутов, ул. Железнодорожная, д. 9",
    }
    return fallback.get(code[:8])


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
    declarant_inn_kpp: Optional[str] = None

    # Из упаковочного листа
    total_packages: Optional[int] = None
    package_type: Optional[str] = None
    total_gross_weight: Optional[float] = None
    total_net_weight: Optional[float] = None

    # Из AWB / транспорта
    transport_doc_number: Optional[str] = None
    transport_type: Optional[str] = None  # 40=воздушный, 10=морской, 30=авто
    customs_office_code: Optional[str] = None  # Код таможенного поста (8 цифр)
    goods_location: Optional[str] = None

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

    # Rules engine output
    evidence_map: Optional[dict] = None
    issues: Optional[list[dict]] = None


class ApplyParsedResponse(BaseModel):
    declaration_id: str
    status: str
    items_created: int
    counterparties_created: int
    documents_linked: int
    message: str
    issues: list[dict] = []
    evidence_map: Optional[dict] = None


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
        company = await db.get(Company, current_user.company_id) if current_user.company_id else None
        merged_inn_kpp = _build_declarant_inn_kpp(company, data.declarant_inn_kpp or declaration.declarant_inn_kpp)
        if merged_inn_kpp:
            declaration.declarant_inn_kpp = merged_inn_kpp

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

        # Всегда подтягивать курс ЦБ для не-рублёвых валют
        if currency and currency.upper() != "RUB":
            try:
                async with httpx.AsyncClient(timeout=10) as http:
                    resp = await http.get("http://calc-service:8005/api/v1/calc/exchange-rates/latest")
                    resp.raise_for_status()
                    rates = resp.json().get("rates", {})
                    rate_value = rates.get(currency.upper())
                    if rate_value and float(rate_value) > 0:
                        exchange_rate = Decimal(str(rate_value))
                    else:
                        logger.warning("currency_rate_not_found", currency=currency, available=list(rates.keys())[:10])
            except Exception as conv_err:
                logger.warning("calc_service_convert_failed", error=str(conv_err), currency=currency)

            declaration.exchange_rate = exchange_rate
            logger.info("exchange_rate_fetched", currency=currency, rate=float(exchange_rate))

        if data.total_amount is not None:
            declaration.total_invoice_value = Decimal(str(data.total_amount))
            if exchange_rate > 0 and exchange_rate != Decimal("1"):
                total_rub = Decimal(str(data.total_amount)) * exchange_rate
            else:
                total_rub = Decimal(str(data.total_amount))
            declaration.total_customs_value = total_rub.quantize(Decimal("0.01"))
            logger.info("currency_converted",
                currency=currency, amount=data.total_amount,
                rate=float(exchange_rate), rub=float(total_rub))
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
        gross_dec = _to_decimal(data.total_gross_weight)
        net_dec = _to_decimal(data.total_net_weight)
        if gross_dec is not None:
            declaration.total_gross_weight = gross_dec
        if net_dec is not None:
            declaration.total_net_weight = net_dec
        # deal_nature_code: всегда 01 (купля-продажа) если не указан
        declaration.deal_nature_code = data.deal_nature_code or declaration.deal_nature_code or "01"
        if data.type_code:
            declaration.type_code = data.type_code
        if data.transport_type:
            # Маппинг текстовых значений → коды (String(2))
            _TRANSPORT_MAP = {"air": "40", "sea": "10", "auto": "30", "rail": "20", "40": "40", "10": "10", "30": "30", "20": "20"}
            tt = _TRANSPORT_MAP.get(str(data.transport_type).lower().strip(), str(data.transport_type)[:2])
            declaration.transport_type_border = tt
        if data.transport_doc_number:
            declaration.transport_at_border = data.transport_doc_number
        if data.customs_office_code:
            declaration.customs_office_code = data.customs_office_code[:8]
        if data.goods_location and not declaration.goods_location:
            declaration.goods_location = data.goods_location.strip()
        freight_dec = _to_decimal(data.freight_amount)
        if freight_dec is not None:
            declaration.freight_amount = freight_dec
        if data.freight_currency:
            declaration.freight_currency = data.freight_currency

        declaration.total_items_count = len(data.items) if data.items else 0

        # Fallback totals from item rows if header totals are missing.
        if data.items:
            gross_sum = Decimal("0")
            net_sum = Decimal("0")
            has_gross = False
            has_net = False
            for item_data in data.items:
                g = _to_decimal(item_data.gross_weight)
                n = _to_decimal(item_data.net_weight)
                if g is not None:
                    gross_sum += g
                    has_gross = True
                if n is not None:
                    net_sum += n
                    has_net = True
            if declaration.total_gross_weight is None and has_gross:
                declaration.total_gross_weight = gross_sum
                logger.info("total_gross_from_items", value=float(gross_sum))
            if declaration.total_net_weight is None and has_net:
                declaration.total_net_weight = net_sum
                logger.info("total_net_from_items", value=float(net_sum))

        # Адрес СВХ (графа 30): по коду таможенного поста из справочника
        office_code = (declaration.customs_office_code or declaration.entry_customs_code or "")[:8] or None
        if not declaration.goods_location and office_code:
            from app.models import Classifier
            post_result = await db.execute(
                select(Classifier).where(
                    Classifier.classifier_type == "customs_post",
                    Classifier.code == office_code,
                    Classifier.is_active == True,
                )
            )
            post = post_result.scalar_one_or_none()
            if post and post.meta and post.meta.get("address"):
                declaration.goods_location = post.meta["address"]
                logger.info("goods_location_from_post", code=office_code, address=post.meta["address"][:50])
            else:
                fallback_addr = _post_address_fallback(office_code)
                if fallback_addr:
                    declaration.goods_location = fallback_addr
                    logger.info("goods_location_from_fallback", code=office_code, address=fallback_addr[:50])
                else:
                    logger.warning("goods_location_post_not_found", code=office_code)

        # --- 3. Создать товарные позиции ---
        for item_data in data.items:
            item = DeclarationItem(
                declaration_id=declaration.id,
                item_no=item_data.line_no,
                description=item_data.description,
                commercial_name=item_data.commercial_name or item_data.description,
                hs_code=item_data.hs_code,
                country_origin_code=(item_data.country_origin_code or data.country_origin or "")[:2] or None,
                gross_weight=_to_decimal(item_data.gross_weight),
                net_weight=_to_decimal(item_data.net_weight),
                unit_price=_to_decimal(item_data.unit_price),
                package_count=item_data.package_count,
                package_type=item_data.package_type,
                additional_unit=item_data.unit,
                additional_unit_qty=_to_decimal(item_data.quantity),
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

            # Автосохранение прецедента при высокой confidence
            if item_data.hs_code and item_data.description and data.confidence and data.confidence > 0.85:
                try:
                    import httpx as _httpx
                    import os
                    ai_url = os.environ.get("AI_SERVICE_URL", "http://ai-service:8003")
                    _httpx.post(f"{ai_url}/api/v1/ai/feedback", json={
                        "declaration_id": str(declaration.id),
                        "item_id": "",
                        "feedback_type": "hs_auto_confirmed",
                        "predicted_value": item_data.hs_code,
                        "actual_value": item_data.hs_code,
                        "description": (item_data.description or "")[:300],
                    }, timeout=3)
                except Exception:
                    pass

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
        parsed_issues = data.issues or []
        error_issues = [i for i in parsed_issues if i.get("severity") == "error"]
        warning_issues = [i for i in parsed_issues if i.get("severity") == "warning"]

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
                "rules_issues_errors": len(error_issues),
                "rules_issues_warnings": len(warning_issues),
                "evidence_map": data.evidence_map,
                "issues": parsed_issues,
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
            issues=parsed_issues,
            evidence_map=data.evidence_map,
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
