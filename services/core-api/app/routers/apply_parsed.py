"""
Endpoint для применения распознанных данных из AI к декларации.
Маппинг OCR/LLM данных на графы ДТ.
"""
import uuid
import re
from typing import Optional
from decimal import Decimal
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
import httpx
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import (
    Declaration, DeclarationStatus, DeclarationItem,
    Counterparty, Document, DeclarationLog, User, Company, Classifier,
)
from app.schemas.declaration import DeclarationResponse
from app.utils.declaration_helpers import (
    merge_company_inn_kpp as _build_declarant_inn_kpp,
    normalize_digits as _normalize_digits,
    post_address_fallback as _post_address_fallback,
)

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
def _normalize_deal_nature_code(value: Optional[str]) -> Optional[str]:
    """Store deal nature in the current 2-digit app format (01, 02, 03...)."""
    digits = _normalize_digits(value)
    if not digits:
        return None
    if len(digits) >= 2:
        return digits[:2]
    return digits


_DOC_CODE_TO_TYPE = {
    "04021": "invoice",
    "03011": "contract",
    "04024": "packing_list",
    "02011": "transport_doc",
    "04025": "transport_invoice",
    "09999": "application_statement",
}


def _infer_doc_type_from_text(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip().lower()
    if not text:
        return None
    if "invoice" in text or "инвойс" in text:
        return "invoice" if "transport" not in text and "фрахт" not in text else "transport_invoice"
    if "contract" in text or "контракт" in text or "договор" in text:
        return "contract"
    if "packing" in text or "упаков" in text:
        return "packing_list"
    if "awb" in text or "waybill" in text or "накладн" in text or "cmr" in text:
        return "transport_doc"
    if "spec" in text or "спец" in text:
        return "specification"
    if "tech" in text or "тех" in text:
        return "tech_description"
    if "application" in text or "заявка" in text:
        return "application_statement"
    return None


def _normalize_doc_type(
    explicit_type: Optional[str],
    doc_code: Optional[str],
    doc_type_name: Optional[str],
    original_filename: Optional[str],
) -> str:
    raw = (explicit_type or "").strip().lower()
    aliases = {
        "packing": "packing_list",
        "packing_list": "packing_list",
        "transport": "transport_doc",
        "transport_doc": "transport_doc",
        "awb": "transport_doc",
    }
    if raw in aliases:
        return aliases[raw]
    if raw in {
        "invoice",
        "contract",
        "packing_list",
        "transport_doc",
        "transport_invoice",
        "application_statement",
        "specification",
        "tech_description",
        "certificate_origin",
        "license",
        "permit",
        "sanitary",
        "veterinary",
        "phytosanitary",
        "other",
    }:
        return raw
    if doc_code and doc_code in _DOC_CODE_TO_TYPE:
        return _DOC_CODE_TO_TYPE[doc_code]
    for candidate in (doc_type_name, original_filename):
        inferred = _infer_doc_type_from_text(candidate)
        if inferred:
            return inferred
    return "other"


def _parse_doc_date(value: Optional[str]) -> Optional[date]:
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def _default_doc_filename(doc_type: str, doc_number: Optional[str]) -> str:
    suffix = (doc_number or "без_номера").replace("/", "_").replace("\\", "_").strip()
    return f"{doc_type}_{suffix or 'без_номера'}.pdf"


def _is_placeholder_party(value: Optional[str]) -> bool:
    normalized = (value or "").strip().upper()
    return normalized in {"СМ. ГРАФУ 14 ДТ", "SEE GRAPH 14", "SEE BOX 14"}


_CURRENCY_ALIASES = {
    "RMB": "CNY",
    "YUAN": "CNY",
    "YUANS": "CNY",
    "CNH": "CNY",
    "RUR": "RUB",
    "RUBLE": "RUB",
    "RUBLES": "RUB",
    "РУБЛЬ": "RUB",
    "РУБЛИ": "RUB",
    "ЮАНЬ": "CNY",
    "ЮАНИ": "CNY",
}

_COUNTRY_ALIASES = {
    "РОССИЯ": "RU",
    "РФ": "RU",
    "RUSSIA": "RU",
    "RUSSIAN FEDERATION": "RU",
    "КИТАЙ": "CN",
    "КНР": "CN",
    "CHINA": "CN",
    "ГОНКОНГ": "HK",
    "HONG KONG": "HK",
    "HONG KONG SAR": "HK",
}


async def _normalize_classifier_code(
    db: AsyncSession,
    classifier_type: str,
    raw_value: Optional[str],
) -> Optional[str]:
    raw = (raw_value or "").strip()
    if not raw:
        return None

    compact = re.sub(r"\s+", " ", raw).strip()
    upper = compact.upper()
    code_len = 0

    if classifier_type == "currency":
        upper = _CURRENCY_ALIASES.get(upper, upper)
        code_len = 3
    elif classifier_type == "country":
        upper = _COUNTRY_ALIASES.get(upper, upper)
        code_len = 2

    if code_len and len(upper) <= code_len and upper:
        code_result = await db.execute(
            select(Classifier.code).where(
                Classifier.classifier_type == classifier_type,
                Classifier.code == upper[:code_len],
                Classifier.is_active == True,
            ).limit(1)
        )
        code = code_result.scalar_one_or_none()
        if code:
            if code != compact:
                logger.info(
                    "classifier_code_normalized",
                    classifier_type=classifier_type,
                    raw=compact,
                    normalized=code,
                )
            return code

    normalized_text = compact.lower()
    name_result = await db.execute(
        select(Classifier.code).where(
            Classifier.classifier_type == classifier_type,
            Classifier.is_active == True,
            or_(
                func.lower(Classifier.name_ru) == normalized_text,
                func.lower(Classifier.name_en) == normalized_text,
            ),
        ).limit(1)
    )
    code = name_result.scalar_one_or_none()
    if code:
        logger.info(
            "classifier_name_resolved",
            classifier_type=classifier_type,
            raw=compact,
            normalized=code,
        )
        return code

    fallback = upper[:code_len] if code_len else upper
    if fallback and fallback != compact:
        logger.warning(
            "classifier_code_fallback_used",
            classifier_type=classifier_type,
            raw=compact,
            fallback=fallback,
        )
    return fallback or None


_CURRENCY_ALIASES = {
    "RMB": "CNY",
    "YUAN": "CNY",
    "YUANS": "CNY",
    "CNH": "CNY",
    "RUR": "RUB",
    "RUBLE": "RUB",
    "RUBLES": "RUB",
    "РУБЛЬ": "RUB",
    "РУБЛИ": "RUB",
    "ЮАНЬ": "CNY",
    "ЮАНИ": "CNY",
}

_COUNTRY_ALIASES = {
    "РОССИЯ": "RU",
    "РФ": "RU",
    "RUSSIA": "RU",
    "RUSSIAN FEDERATION": "RU",
    "КИТАЙ": "CN",
    "КНР": "CN",
    "CHINA": "CN",
    "ГОНКОНГ": "HK",
    "HONG KONG": "HK",
    "HONG KONG SAR": "HK",
}


async def _normalize_classifier_code(
    db: AsyncSession,
    classifier_type: str,
    raw_value: Optional[str],
) -> Optional[str]:
    raw = (raw_value or "").strip()
    if not raw:
        return None

    compact = re.sub(r"\s+", " ", raw).strip()
    upper = compact.upper()
    code_len = 0

    if classifier_type == "currency":
        upper = _CURRENCY_ALIASES.get(upper, upper)
        code_len = 3
    elif classifier_type == "country":
        upper = _COUNTRY_ALIASES.get(upper, upper)
        code_len = 2

    if code_len and len(upper) <= code_len and upper:
        code_result = await db.execute(
            select(Classifier.code).where(
                Classifier.classifier_type == classifier_type,
                Classifier.code == upper[:code_len],
                Classifier.is_active == True,
            ).limit(1)
        )
        code = code_result.scalar_one_or_none()
        if code:
            if code != compact:
                logger.info(
                    "classifier_code_normalized",
                    classifier_type=classifier_type,
                    raw=compact,
                    normalized=code,
                )
            return code

    normalized_text = compact.lower()
    name_result = await db.execute(
        select(Classifier.code).where(
            Classifier.classifier_type == classifier_type,
            Classifier.is_active == True,
            or_(
                func.lower(Classifier.name_ru) == normalized_text,
                func.lower(Classifier.name_en) == normalized_text,
            ),
        ).limit(1)
    )
    code = name_result.scalar_one_or_none()
    if code:
        logger.info(
            "classifier_name_resolved",
            classifier_type=classifier_type,
            raw=compact,
            normalized=code,
        )
        return code

    fallback = upper[:code_len] if code_len else upper
    if fallback and fallback != compact:
        logger.warning(
            "classifier_code_fallback_used",
            classifier_type=classifier_type,
            raw=compact,
            fallback=fallback,
        )
    return fallback or None


# --- Pydantic schemas for parsed data ---

class ParsedCounterparty(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    country_code: Optional[str] = None
    tax_number: Optional[str] = None  # устаревшее, используется как fallback
    inn: Optional[str] = None         # ИНН или эквивалент (VAT, Tax ID)
    kpp: Optional[str] = None         # КПП (для РФ) или None
    ogrn: Optional[str] = None        # ОГРН или эквивалент (Company Reg. No.)
    type: str = "seller"  # seller, buyer, importer, declarant


class ParsedItem(BaseModel):
    line_no: int = 1
    description: Optional[str] = None
    commercial_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    invoice_currency: Optional[str] = None  # валюта инвойса (для гр. 42: сверка с валютой контракта)
    hs_code: Optional[str] = None
    hs_code_name: Optional[str] = None
    country_origin_code: Optional[str] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    package_count: Optional[int] = None
    package_type: Optional[str] = None


class ParsedDocumentRef(BaseModel):
    doc_code: Optional[str] = None
    doc_type: Optional[str] = None
    doc_type_name: Optional[str] = None
    doc_number: Optional[str] = None
    doc_date: Optional[str] = None
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

    # Из транспортных документов
    trading_partner_country: Optional[str] = None  # Гр. 11: ISO2 страна контрагента
    country_dispatch: Optional[str] = None          # Гр. 15: ISO2 страна отправления (может отличаться от origin)
    container: Optional[bool] = None                # Гр. 19: контейнер (true/false)

    # Из AWB / транспорта
    transport_doc_number: Optional[str] = None
    transport_type: Optional[str] = None  # 40=воздушный, 10=морской, 30=авто
    transport_id: Optional[str] = None   # Гр. 21: идентификатор ТС (номер рейса / рег. номер / судно)
    transport_country_code: Optional[str] = None  # Гр. 21 подраздел 2: страна регистрации ТС
    delivery_place: Optional[str] = None  # Гр. 20: место поставки по Инкотермс
    customs_office_code: Optional[str] = None  # Код таможенного поста (8 цифр)
    goods_location: Optional[str] = None

    # Товарные позиции
    items: list[ParsedItem] = []

    # Ссылки на загруженные документы
    documents: list[ParsedDocumentRef] = []

    # Графа 8: по умолчанию True → "СМ. ГРАФУ 14 ДТ"
    buyer_matches_declarant: Optional[bool] = True

    # Графа 9: лицо, ответственное за финансовое урегулирование
    responsible_person: Optional[ParsedCounterparty | str] = None
    responsible_person_matches_declarant: Optional[bool] = True

    # Общие
    deal_nature_code: Optional[str] = "01"  # купля-продажа (2-значный app-format код)
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


def _truncate_declaration_fields(
    declaration: Declaration,
    field_limits: list[tuple[str, int]],
) -> None:
    for field_name, max_len in field_limits:
        value = getattr(declaration, field_name, None)
        if value and len(str(value)) > max_len:
            setattr(declaration, field_name, str(value)[:max_len])
            logger.warning(
                "field_truncated",
                field=field_name,
                original=str(value)[:30],
                max_len=max_len,
            )


def _apply_item_totals_fallback(
    declaration: Declaration,
    items: list[ParsedItem],
) -> None:
    if not items:
        return

    gross_sum = Decimal("0")
    net_sum = Decimal("0")
    has_gross = False
    has_net = False
    for item_data in items:
        gross_value = _to_decimal(item_data.gross_weight)
        net_value = _to_decimal(item_data.net_weight)
        if gross_value is not None:
            gross_sum += gross_value
            has_gross = True
        if net_value is not None:
            net_sum += net_value
            has_net = True

    if declaration.total_gross_weight is None and has_gross:
        declaration.total_gross_weight = gross_sum
        logger.info("total_gross_from_items", value=float(gross_sum))
    if declaration.total_net_weight is None and has_net:
        declaration.total_net_weight = net_sum
        logger.info("total_net_from_items", value=float(net_sum))


async def _fill_goods_location_from_post(
    db: AsyncSession,
    declaration: Declaration,
) -> None:
    office_code = (declaration.customs_office_code or declaration.entry_customs_code or "")[:8] or None
    if declaration.goods_location or not office_code:
        return

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
        return

    fallback_addr = _post_address_fallback(office_code)
    if fallback_addr:
        declaration.goods_location = fallback_addr
        logger.info("goods_location_from_fallback", code=office_code, address=fallback_addr[:50])
    else:
        logger.warning("goods_location_post_not_found", code=office_code)


async def _apply_declaration_header_fields(
    db: AsyncSession,
    declaration: Declaration,
    data: ApplyParsedRequest,
) -> Decimal:
    exchange_rate = Decimal("1")
    normalized_currency = await _normalize_classifier_code(db, "currency", data.currency)
    currency = normalized_currency or ((declaration.currency_code or "").strip().upper() or None)
    if currency:
        declaration.currency_code = currency

    if currency and currency.upper() != "RUB":
        try:
            from app.middleware.logging_middleware import tracing_headers
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.get("http://calc-service:8005/api/v1/calc/exchange-rates/latest", headers=tracing_headers())
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
        logger.info(
            "currency_converted",
            currency=currency,
            amount=data.total_amount,
            rate=float(exchange_rate),
            rub=float(total_rub),
        )
    if data.incoterms:
        declaration.incoterms_code = (data.incoterms or "").strip().upper()[:3] or None

    normalized_country_origin = await _normalize_classifier_code(db, "country", data.country_origin)
    if normalized_country_origin:
        declaration.country_origin_code = normalized_country_origin
    normalized_country_dispatch = await _normalize_classifier_code(db, "country", data.country_dispatch)
    if normalized_country_dispatch:
        declaration.country_dispatch_code = normalized_country_dispatch
    normalized_trading_country = await _normalize_classifier_code(db, "country", data.trading_partner_country)
    if normalized_trading_country:
        declaration.trading_country_code = normalized_trading_country

    if data.container is not None:
        declaration.container_info = "1" if data.container else "0"

    normalized_country_destination = await _normalize_classifier_code(
        db,
        "country",
        data.country_destination or declaration.country_destination_code or "RU",
    )
    declaration.country_destination_code = normalized_country_destination or "RU"

    if data.total_packages is not None:
        declaration.total_packages_count = data.total_packages
    gross_dec = _to_decimal(data.total_gross_weight)
    net_dec = _to_decimal(data.total_net_weight)
    if gross_dec is not None:
        declaration.total_gross_weight = gross_dec
    if net_dec is not None:
        declaration.total_net_weight = net_dec

    declaration.deal_nature_code = (
        _normalize_deal_nature_code(data.deal_nature_code)
        or _normalize_deal_nature_code(declaration.deal_nature_code)
        or "01"
    )
    if data.type_code:
        declaration.type_code = data.type_code
    if data.transport_type:
        transport_map = {
            "air": "40",
            "sea": "10",
            "auto": "30",
            "rail": "20",
            "40": "40",
            "10": "10",
            "30": "30",
            "20": "20",
        }
        transport_type = transport_map.get(str(data.transport_type).lower().strip(), str(data.transport_type)[:2])
        declaration.transport_type_border = transport_type
        declaration.transport_type_inland = transport_type
    if data.transport_doc_number:
        declaration.transport_at_border = data.transport_doc_number
    if data.transport_id:
        declaration.transport_on_border_id = data.transport_id
    if data.delivery_place:
        declaration.delivery_place = data.delivery_place
    if data.customs_office_code:
        declaration.customs_office_code = _normalize_digits(data.customs_office_code)[:8] or None
    if data.goods_location and not declaration.goods_location:
        declaration.goods_location = data.goods_location.strip()

    freight_dec = _to_decimal(data.freight_amount)
    if freight_dec is not None:
        declaration.freight_amount = freight_dec
    if data.freight_currency:
        declaration.freight_currency = data.freight_currency

    declaration.total_items_count = len(data.items) if data.items else 0

    import math

    items_count = len(data.items) if data.items else 0
    declaration.forms_count = 1 + math.ceil((items_count - 1) / 3) if items_count > 1 else (1 if items_count == 1 else 0)

    _apply_item_totals_fallback(declaration, data.items)
    _truncate_declaration_fields(
        declaration,
        [
            ("country_dispatch_code", 2), ("country_origin_code", 2), ("country_destination_code", 2),
            ("trading_country_code", 2), ("transport_type_border", 2), ("transport_type_inland", 2),
            ("currency_code", 3), ("incoterms_code", 3), ("deal_nature_code", 2),
            ("freight_currency", 3), ("customs_office_code", 8), ("type_code", 10),
        ],
    )
    await _fill_goods_location_from_post(db, declaration)

    return exchange_rate


async def _create_declaration_items(
    db: AsyncSession,
    declaration: Declaration,
    data: ApplyParsedRequest,
    current_user: User,
    sender_id: Optional[uuid.UUID],
    exchange_rate: Decimal,
) -> int:
    from app.models.hs_code_history import HsCodeHistory
    from sqlalchemy import func as sa_func

    items_created = 0

    for item_data in data.items:
        hs_code = item_data.hs_code or ""
        hs_source = "ai"
        desc_norm = (item_data.description or "")[:300].strip().lower()
        item_country_origin_code = await _normalize_classifier_code(
            db,
            "country",
            item_data.country_origin_code or data.country_origin,
        )

        if not hs_code and desc_norm and current_user.company_id:
            try:
                hist = await db.execute(
                    select(HsCodeHistory)
                    .where(
                        HsCodeHistory.company_id == current_user.company_id,
                        sa_func.similarity(HsCodeHistory.description_trgm, desc_norm) > 0.3,
                    )
                    .order_by(
                        sa_func.similarity(HsCodeHistory.description_trgm, desc_norm).desc(),
                        HsCodeHistory.usage_count.desc(),
                    )
                    .limit(1)
                )
                match = hist.scalar_one_or_none()
                if match:
                    hs_code = match.hs_code
                    hs_source = "history"
                    logger.info(
                        "hs_code_from_history",
                        desc=desc_norm[:50],
                        hs_code=hs_code,
                        similarity="trgm",
                        usage_count=match.usage_count,
                    )
            except Exception as e:
                logger.debug("hs_history_lookup_failed", error=str(e)[:80])

        graph_42: Optional[Decimal] = None
        if item_data.line_total:
            graph_42 = _to_decimal(item_data.line_total)
        elif item_data.unit_price and item_data.quantity:
            graph_42 = _to_decimal(item_data.unit_price * item_data.quantity)
        elif item_data.unit_price:
            graph_42 = _to_decimal(item_data.unit_price)

        item = DeclarationItem(
            declaration_id=declaration.id,
            item_no=item_data.line_no,
            description=item_data.description,
            commercial_name=item_data.commercial_name or item_data.description,
            hs_code=hs_code,
            country_origin_code=item_country_origin_code,
            gross_weight=_to_decimal(item_data.gross_weight),
            net_weight=_to_decimal(item_data.net_weight),
            unit_price=graph_42,
            package_count=item_data.package_count,
            package_type=item_data.package_type,
            additional_unit=item_data.unit,
            additional_unit_qty=_to_decimal(item_data.quantity),
            mos_method_code="1",
            risk_score=data.risk_score or 0,
            risk_flags=data.risk_flags,
        )

        if graph_42:
            item.customs_value_rub = (graph_42 * exchange_rate).quantize(Decimal("0.01"))

        db.add(item)
        await db.flush()
        items_created += 1

        if hs_code and desc_norm and current_user.company_id:
            try:
                existing_hist = await db.execute(
                    select(HsCodeHistory).where(
                        HsCodeHistory.company_id == current_user.company_id,
                        HsCodeHistory.hs_code == hs_code,
                        HsCodeHistory.description_trgm == desc_norm,
                    )
                )
                hist_row = existing_hist.scalar_one_or_none()
                if hist_row:
                    hist_row.usage_count += 1
                    hist_row.declaration_id = declaration.id
                    hist_row.item_id = item.id
                else:
                    db.add(HsCodeHistory(
                        company_id=current_user.company_id,
                        counterparty_id=sender_id,
                        counterparty_name=(data.seller.name if data.seller else None),
                        description=item_data.description or "",
                        description_trgm=desc_norm,
                        hs_code=hs_code,
                        declaration_id=declaration.id,
                        item_id=item.id,
                        source=hs_source,
                    ))
            except Exception as e:
                logger.debug("hs_history_save_failed", error=str(e)[:80])

        if hs_code and item_data.description:
            try:
                import httpx as _httpx
                import os
                from app.middleware.logging_middleware import tracing_headers

                ai_url = os.environ.get("AI_SERVICE_URL", "http://ai-service:8003")
                _httpx.post(
                    f"{ai_url}/api/v1/ai/feedback",
                    json={
                        "declaration_id": str(declaration.id),
                        "item_id": str(item.id),
                        "feedback_type": "hs_auto_confirmed",
                        "predicted_value": hs_code,
                        "actual_value": hs_code,
                        "description": (item_data.description or "")[:300],
                        "company_id": str(current_user.company_id) if current_user.company_id else "",
                        "counterparty_name": (data.seller.name if data.seller else ""),
                    },
                    headers=tracing_headers(),
                    timeout=3,
                )
            except Exception as fb_err:
                logger.warning("ai_feedback_failed", error=str(fb_err), hs_code=item_data.hs_code)

    return items_created


def _attach_parsed_documents(
    db: AsyncSession,
    declaration: Declaration,
    documents: list[ParsedDocumentRef],
) -> int:
    documents_linked = 0

    for doc_data in documents:
        normalized_doc_type = _normalize_doc_type(
            doc_data.doc_type,
            doc_data.doc_code,
            doc_data.doc_type_name,
            doc_data.original_filename,
        )
        if normalized_doc_type != (doc_data.doc_type or "").strip().lower():
            logger.info(
                "document_type_normalized",
                original=doc_data.doc_type,
                normalized=normalized_doc_type,
                doc_code=doc_data.doc_code,
                filename=doc_data.original_filename,
            )
        doc = Document(
            declaration_id=declaration.id,
            doc_type=normalized_doc_type,
            file_key=doc_data.file_key,
            original_filename=doc_data.original_filename or _default_doc_filename(normalized_doc_type, doc_data.doc_number),
            mime_type=doc_data.mime_type or "application/pdf",
            file_size=doc_data.file_size,
            issued_at=_parse_doc_date(doc_data.doc_date),
            doc_number=doc_data.doc_number,
            parsed_data=doc_data.parsed_data,
        )
        db.add(doc)
        documents_linked += 1

    return documents_linked


def _build_apply_parsed_log_entry(
    declaration: Declaration,
    current_user: User,
    data: ApplyParsedRequest,
    counters: dict[str, int],
) -> tuple[DeclarationLog, list[dict]]:
    parsed_issues = data.issues or []
    error_issues = [issue for issue in parsed_issues if issue.get("severity") == "error"]
    warning_issues = [issue for issue in parsed_issues if issue.get("severity") == "warning"]

    return DeclarationLog(
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
    ), parsed_issues


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
        responsible_person_data = data.responsible_person
        if isinstance(responsible_person_data, str) and _is_placeholder_party(responsible_person_data):
            responsible_person_data = None
            data.responsible_person_matches_declarant = True

        # --- 0. Подтянуть ИНН/КПП из компании + адрес СВХ по коду поста ---
        company = await db.get(Company, current_user.company_id) if current_user.company_id else None
        merged_inn_kpp = _build_declarant_inn_kpp(company, data.declarant_inn_kpp or declaration.declarant_inn_kpp)
        if merged_inn_kpp:
            declaration.declarant_inn_kpp = merged_inn_kpp

        # --- 1. Создать/найти контрагентов ---
        sender_id = None
        receiver_id = None
        declarant_id = None

        if data.seller and data.seller.name:
            sender_id = await _find_or_create_counterparty(
                db, data.seller, "seller", current_user.company_id
            )
            counters["counterparties"] += 1

        # Графа 14: декларант — приоритет: Профиль компании > Контракт (buyer)
        # Каждое поле: если в профиле заполнено — берём из профиля, если пусто — из контракта
        c = company
        bp = data.buyer
        decl_name = (c.name if c else None) or (bp.name if bp else None)
        decl_address = (c.address if c else None) or (bp.address if bp else None)
        decl_country = (c.country_code if c else None) or (bp.country_code if bp else None) or "RU"
        decl_inn = (c.inn if c else None) or (bp.inn if bp else None)
        decl_kpp = (c.kpp if c else None) or (bp.kpp if bp else None)
        decl_ogrn = (c.ogrn if c else None) or (bp.ogrn if bp else None)

        if decl_name:
            declarant_cp = ParsedCounterparty(
                name=decl_name,
                address=decl_address,
                country_code=decl_country,
                inn=decl_inn,
                kpp=decl_kpp,
                ogrn=decl_ogrn,
                type="declarant",
            )
            declarant_id = await _find_or_create_counterparty(
                db, declarant_cp, "declarant", current_user.company_id
            )
            counters["counterparties"] += 1

        if declarant_id:
            declaration.declarant_counterparty_id = declarant_id
            declaration.declarant_ogrn = decl_ogrn
            if company and company.contact_phone:
                declaration.declarant_phone = company.contact_phone

        # Графа 8: по умолчанию «СМ. ГРАФУ 14 ДТ» (receiver = declarant)
        # Исключение: трёхсторонний договор — отдельный получатель
        if data.buyer_matches_declarant and declarant_id:
            receiver_id = declarant_id
        elif data.buyer and data.buyer.name:
            receiver_id = await _find_or_create_counterparty(
                db, data.buyer, "buyer", current_user.company_id
            )
            counters["counterparties"] += 1

        # Графа 9: по умолчанию «СМ. ГРАФУ 14 ДТ» (financial = declarant)
        # Исключение: трёхсторонний договор — отдельное ответственное лицо
        financial_id = None
        if data.responsible_person_matches_declarant and declarant_id:
            financial_id = declarant_id
        elif isinstance(responsible_person_data, ParsedCounterparty) and responsible_person_data.name:
            financial_id = await _find_or_create_counterparty(
                db, responsible_person_data, "financial", current_user.company_id
            )
            counters["counterparties"] += 1

        # --- 2. Обновить поля декларации ---
        if sender_id:
            declaration.sender_counterparty_id = sender_id
        if receiver_id:
            declaration.receiver_counterparty_id = receiver_id
        if financial_id:
            declaration.financial_counterparty_id = financial_id

        exchange_rate = await _apply_declaration_header_fields(db, declaration, data)

        # --- 3. Создать товарные позиции ---
        counters["items"] = await _create_declaration_items(
            db,
            declaration,
            data,
            current_user,
            sender_id,
            exchange_rate,
        )

        # --- 4. Привязать документы ---
        counters["documents"] = _attach_parsed_documents(db, declaration, data.documents)

        # --- 5. Логирование ---
        log_entry, parsed_issues = _build_apply_parsed_log_entry(
            declaration,
            current_user,
            data,
            counters,
        )
        db.add(log_entry)

        _truncate_declaration_fields(
            declaration,
            [
                ("country_dispatch_code", 2), ("country_origin_code", 2), ("country_destination_code", 2),
                ("trading_country_code", 2), ("transport_type_border", 2), ("transport_type_inland", 2),
                ("currency_code", 3), ("incoterms_code", 3), ("deal_nature_code", 2),
                ("customs_office_code", 8), ("type_code", 10),
            ],
        )

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
    """Найти существующего контрагента или создать нового.
    Приоритет поиска: tax_number > exact name > ilike name.
    Обновляет недостающие поля у найденного контрагента.
    """
    existing = None
    normalized_country_code = await _normalize_classifier_code(db, "country", parsed.country_code)

    if parsed.tax_number:
        result = await db.execute(
            select(Counterparty).where(
                Counterparty.tax_number == parsed.tax_number,
                Counterparty.company_id == company_id,
            )
        )
        existing = result.scalar_one_or_none()

    if not existing and parsed.name:
        result = await db.execute(
            select(Counterparty).where(
                Counterparty.name == parsed.name,
                Counterparty.type == cp_type,
                Counterparty.company_id == company_id,
            )
        )
        existing = result.scalar_one_or_none()

    if not existing and parsed.name:
        result = await db.execute(
            select(Counterparty).where(
                Counterparty.name.ilike(f"%{parsed.name[:30]}%"),
                Counterparty.type == cp_type,
                Counterparty.company_id == company_id,
            )
        )
        existing = result.scalars().first()

    if existing:
        updated = False
        if normalized_country_code and not existing.country_code:
            existing.country_code = normalized_country_code
            updated = True
        if parsed.tax_number and not existing.tax_number:
            existing.tax_number = parsed.tax_number
            updated = True
        if parsed.address and not existing.address:
            existing.address = parsed.address
            updated = True
        if updated:
            await db.flush()
            logger.info("counterparty_updated", id=str(existing.id), name=existing.name)
        return existing.id

    # Собрать tax_number: приоритет отдельным полям inn/kpp, затем tax_number fallback
    effective_inn = parsed.inn or parsed.tax_number
    if effective_inn and parsed.kpp:
        effective_tax = f"{effective_inn} / {parsed.kpp}"
    else:
        effective_tax = effective_inn or parsed.tax_number

    counterparty = Counterparty(
        type=cp_type,
        name=parsed.name,
        country_code=normalized_country_code,
        tax_number=effective_tax,
        registration_number=parsed.ogrn,
        address=parsed.address,
        company_id=company_id,
    )
    db.add(counterparty)
    await db.flush()

    logger.info(
        "counterparty_created",
        name=parsed.name,
        type=cp_type,
        country_code=normalized_country_code,
    )

    return counterparty.id
