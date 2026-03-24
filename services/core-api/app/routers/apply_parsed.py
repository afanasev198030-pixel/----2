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
from sqlalchemy import select, func, or_, delete
from sqlalchemy.orm import selectinload
import httpx
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import (
    Declaration, DeclarationStatus, ProcessingStatus, DeclarationItem,
    Counterparty, Document, DeclarationLog, User, Company, Classifier,
    CustomsPayment,
)
from app.models.declaration_item_document import DeclarationItemDocument
from app.schemas.declaration import DeclarationResponse
from app.services.declaration_state_service import (
    recalculate_declaration_state,
    reset_signature_if_needed,
    set_processing_status,
)
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
    """Normalise deal nature to 3-digit format required by ДТ (010, 020, 030...)."""
    digits = _normalize_digits(value)
    if not digits:
        return None
    if len(digits) >= 3:
        return digits[:3]
    if len(digits) == 2:
        return digits + "0"
    if len(digits) == 1:
        return "0" + digits + "0"
    return digits


_DOC_CODE_TO_TYPE = {
    "01401": "certificate_origin",
    "01402": "certificate_origin",
    "01404": "certificate_origin",
    "02011": "transport_doc",
    "02013": "transport_doc",
    "02015": "transport_doc",
    "03011": "contract",
    "03012": "contract",
    "03031": "payment_order",
    "04021": "invoice",
    "04024": "packing_list",
    "04025": "transport_invoice",
    "04031": "transport_invoice",
    "04033": "transport_doc",
    "04091": "specification",
    "04099": "other",
    "05011": "tech_description",
    "05999": "application_statement",
    "06011": "certificate_origin",
    "06012": "certificate_origin",
    "06013": "certificate_origin",
    "06019": "certificate_origin",
    "07011": "phytosanitary",
    "07012": "veterinary",
    "07013": "sanitary",
    "09013": "other",
    "09023": "other",
    "09034": "other",
    "09999": "application_statement",
    "01011": "license",
    "01999": "permit",
}

_DOC_TYPE_TO_CODE: dict[str, str] = {
    "invoice": "04021",
    "contract": "03011",
    "packing_list": "04024",
    "transport_doc": "02011",
    "transport_invoice": "04025",
    "specification": "04091",
    "tech_description": "05011",
    "application_statement": "05999",
    "certificate_origin": "06019",
    "payment_order": "03031",
    "license": "01011",
    "permit": "01999",
    "sanitary": "07013",
    "veterinary": "07012",
    "phytosanitary": "07011",
    "other": "09023",
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
    if "платёж" in text or "платеж" in text or "payment order" in text:
        return "payment_order"
    return None


async def _resolve_doc_kind_code(
    db: AsyncSession,
    doc_type: Optional[str],
    doc_code: Optional[str] = None,
) -> str:
    """Resolve document kind code for Графа 44 using classifier DB with fallback."""
    candidate = doc_code or _DOC_TYPE_TO_CODE.get(doc_type or "", "09023")
    result = await db.execute(
        select(Classifier.code).where(
            Classifier.classifier_type == "doc_type",
            Classifier.code == candidate,
            Classifier.is_active == True,
        ).limit(1)
    )
    if result.scalar_one_or_none():
        return candidate
    return _DOC_TYPE_TO_CODE.get(doc_type or "", candidate)


async def _get_exchange_rate(currency: str) -> Optional[Decimal]:
    """Получить курс ЦБ для валюты из calc-service. Возвращает None при ошибке."""
    if not currency or currency.upper() == "RUB":
        return Decimal("1")
    try:
        from app.middleware.logging_middleware import tracing_headers
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(
                "http://calc-service:8005/api/v1/calc/exchange-rates/latest",
                headers=tracing_headers(),
            )
            resp.raise_for_status()
            rates = resp.json().get("rates", {})
            rate_value = rates.get(currency.upper())
            if rate_value and float(rate_value) > 0:
                return Decimal(str(rate_value))
            logger.warning("currency_rate_not_found", currency=currency,
                           available=list(rates.keys())[:10])
    except Exception as e:
        logger.warning("calc_service_rate_failed", error=str(e), currency=currency)
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


def _has_cyrillic(text: Optional[str]) -> bool:
    """Проверяет, содержит ли текст кириллические символы."""
    if not text:
        return False
    return bool(re.search(r'[а-яА-ЯёЁ]', text))


def _prefer_russian(variant_a: Optional[str], variant_b: Optional[str]) -> Optional[str]:
    """Выбирает русский (кириллический) вариант, если доступен.

    Если variant_a — латиница, а variant_b — кириллица, берём variant_b.
    Иначе стандартный приоритет: variant_a > variant_b.
    """
    if variant_a and variant_b and not _has_cyrillic(variant_a) and _has_cyrillic(variant_b):
        return variant_b
    return variant_a or variant_b


def _is_placeholder_party(value: Optional[str]) -> bool:
    normalized = (value or "").strip().upper()
    return normalized in {"СМ. ГРАФУ 14 ДТ", "SEE GRAPH 14", "SEE BOX 14"}


_TRILATERAL_KEYWORDS = (
    "trilateral", "трёхсторонн", "трехсторонн", "three-party",
    "three_party", "трёхсторон", "трехсторон",
)


def _has_trilateral_contract(documents: list) -> bool:
    """Проверить наличие трёхстороннего договора среди загруженных документов."""
    for doc in documents:
        for text in (
            getattr(doc, "doc_type", None) or "",
            getattr(doc, "doc_type_name", None) or "",
            getattr(doc, "original_filename", None) or "",
        ):
            lower = text.lower()
            if any(kw in lower for kw in _TRILATERAL_KEYWORDS):
                return True
    return False


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
    transport_type_inland: Optional[str] = None  # Гр. 26: вид транспорта внутри страны (может отличаться от border)
    transport_id: Optional[str] = None   # Гр. 21: идентификатор ТС (номер рейса / рег. номер / судно)
    transport_country_code: Optional[str] = None  # Гр. 21 подраздел 2: страна регистрации ТС
    vehicle_reg_number: Optional[str] = None  # Гр. 18: бортовой/рег. номер ТС (не номер AWB!)
    vehicle_country_code: Optional[str] = None  # Гр. 18: код страны регистрации ТС
    delivery_place: Optional[str] = None  # Гр. 20: место поставки по Инкотермс
    customs_office_code: Optional[str] = None  # Код таможенного поста (8 цифр)
    goods_location: Optional[str] = None

    # Товарные позиции
    items: list[ParsedItem] = []

    # Ссылки на загруженные документы
    documents: list[ParsedDocumentRef] = []

    # Графа 8: получатель из транспортного документа (если отличается от декларанта)
    consignee: Optional[ParsedCounterparty] = None
    # True → "СМ. ГРАФУ 14 ДТ", False → использовать consignee
    buyer_matches_declarant: Optional[bool] = True

    # Графа 9: лицо, ответственное за финансовое урегулирование
    responsible_person: Optional[ParsedCounterparty | str] = None
    responsible_person_matches_declarant: Optional[bool] = True

    # Общие
    deal_nature_code: Optional[str] = "010"
    deal_specifics_code: Optional[str] = "00"
    type_code: Optional[str] = "IM40"

    # Транспортные расходы (графа 17 ДТС-1)
    freight_amount: Optional[float] = None
    freight_currency: Optional[str] = None

    # Дополнительные расходы для ДТС
    insurance_amount: Optional[float] = None
    insurance_currency: Optional[str] = None
    loading_cost: Optional[float] = None
    loading_currency: Optional[str] = None

    # Графа 54: подписант / таможенный представитель
    signatory_name: Optional[str] = None
    signatory_position: Optional[str] = None
    signatory_id_doc: Optional[str] = None
    signatory_cert_number: Optional[str] = None
    signatory_power_of_attorney: Optional[str] = None
    broker_registry_number: Optional[str] = None
    broker_contract_number: Optional[str] = None
    broker_contract_date: Optional[str] = None

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

    if data.country_origin:
        declaration.country_origin_name = (data.country_origin or "")[:60] or None
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
        or "010"
    )
    if not declaration.deal_specifics_code:
        declaration.deal_specifics_code = data.deal_specifics_code or "00"

    if data.type_code and not declaration.type_code:
        declaration.type_code = str(data.type_code)[:10]

    transport_map = {
        "air": "40", "sea": "10", "auto": "30", "rail": "20",
        "40": "40", "10": "10", "30": "30", "20": "20",
    }
    if data.transport_type:
        transport_type = transport_map.get(str(data.transport_type).lower().strip(), str(data.transport_type)[:2])
        declaration.transport_type_border = transport_type
    if data.transport_type_inland:
        inland = transport_map.get(str(data.transport_type_inland).lower().strip(), str(data.transport_type_inland)[:2])
        declaration.transport_type_inland = inland

    if data.vehicle_reg_number:
        declaration.transport_at_border = str(data.vehicle_reg_number)[:100]
        declaration.transport_reg_number = str(data.vehicle_reg_number)[:50]
    if data.vehicle_country_code:
        declaration.transport_nationality_code = str(data.vehicle_country_code)[:2]
    if data.transport_id:
        declaration.transport_on_border_id = str(data.transport_id)[:100]
    if data.delivery_place:
        declaration.delivery_place = str(data.delivery_place)[:200]
    if data.customs_office_code:
        declaration.customs_office_code = _normalize_digits(data.customs_office_code)[:8] or None
    if data.goods_location and not declaration.goods_location:
        declaration.goods_location = data.goods_location.strip()

    # Графа 54: signatory / broker
    if data.signatory_name:
        declaration.signatory_name = str(data.signatory_name)[:200]
    if data.signatory_position:
        declaration.signatory_position = str(data.signatory_position)[:200]
    if data.signatory_id_doc:
        declaration.signatory_id_doc = str(data.signatory_id_doc)[:200]
    if data.signatory_cert_number:
        declaration.signatory_cert_number = str(data.signatory_cert_number)[:20]
    if data.signatory_power_of_attorney:
        declaration.signatory_power_of_attorney = str(data.signatory_power_of_attorney)[:200]
    if data.broker_registry_number:
        declaration.broker_registry_number = str(data.broker_registry_number)[:30]
    if data.broker_contract_number:
        declaration.broker_contract_number = str(data.broker_contract_number)[:50]
    if data.broker_contract_date:
        parsed_bc_date = _parse_doc_date(data.broker_contract_date)
        if parsed_bc_date:
            declaration.broker_contract_date = datetime.combine(parsed_bc_date, datetime.min.time())

    # ДТС графы 4–5: инвойс и контракт
    if data.invoice_number:
        declaration.invoice_number = str(data.invoice_number)[:100]
    if data.invoice_date:
        inv_date = _parse_doc_date(data.invoice_date)
        if inv_date:
            declaration.invoice_date = inv_date
    if data.contract_number:
        declaration.contract_number = str(data.contract_number)[:100]
    if data.contract_date:
        cntr_date = _parse_doc_date(data.contract_date)
        if cntr_date:
            declaration.contract_date = cntr_date

    freight_dec = _to_decimal(data.freight_amount)
    if freight_dec is not None:
        declaration.freight_amount = freight_dec
    if data.freight_currency:
        declaration.freight_currency = str(data.freight_currency)[:3]

    declaration.total_items_count = len(data.items) if data.items else 0

    import math

    items_count = len(data.items) if data.items else 0
    declaration.forms_count = 1 + math.ceil((items_count - 1) / 3) if items_count > 1 else (1 if items_count == 1 else 0)

    _apply_item_totals_fallback(declaration, data.items)
    _truncate_declaration_fields(
        declaration,
        [
            ("country_dispatch_code", 2), ("country_destination_code", 2),
            ("trading_country_code", 2), ("transport_type_border", 2), ("transport_type_inland", 2),
            ("currency_code", 3), ("incoterms_code", 3), ("deal_nature_code", 3),
            ("deal_specifics_code", 2), ("freight_currency", 3),
            ("customs_office_code", 8), ("type_code", 10),
            ("country_origin_name", 60), ("transport_at_border", 100),
            ("transport_on_border_id", 100), ("delivery_place", 200),
            ("declarant_inn_kpp", 30), ("declarant_ogrn", 15), ("declarant_phone", 20),
            ("transport_reg_number", 50), ("transport_nationality_code", 2),
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
) -> tuple[int, list]:
    from app.models.hs_code_history import HsCodeHistory
    from sqlalchemy import func as sa_func

    items_created = 0
    created_items: list[DeclarationItem] = []

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

        type_code = (declaration.type_code or "IM40").upper()
        default_procedure = "4000" if "40" in type_code else "0000"

        item = DeclarationItem(
            declaration_id=declaration.id,
            item_no=item_data.line_no,
            description=item_data.description,
            commercial_name=((item_data.commercial_name or item_data.description) or "")[:500] or None,
            hs_code=(hs_code or "")[:10] or None,
            country_origin_code=(item_country_origin_code or "")[:2] or None,
            gross_weight=_to_decimal(item_data.gross_weight),
            net_weight=_to_decimal(item_data.net_weight),
            unit_price=graph_42,
            package_count=item_data.package_count,
            package_type=((item_data.package_type or "")[:50]) or None,
            additional_unit=((item_data.unit or "")[:20]) or None,
            additional_unit_qty=_to_decimal(item_data.quantity),
            procedure_code=default_procedure,
            preference_code="0000--00",
            mos_method_code="1",
            risk_score=data.risk_score or 0,
            risk_flags=data.risk_flags,
        )

        if graph_42:
            item.customs_value_rub = (graph_42 * exchange_rate).quantize(Decimal("0.01"))

        db.add(item)
        await db.flush()
        created_items.append(item)
        items_created += 1

        for doc_ref in data.documents:
            normalized_type = _normalize_doc_type(
                doc_ref.doc_type, doc_ref.doc_code,
                doc_ref.doc_type_name, doc_ref.original_filename,
            )
            doc_kind_code = await _resolve_doc_kind_code(db, normalized_type, doc_ref.doc_code)
            db.add(DeclarationItemDocument(
                declaration_item_id=item.id,
                doc_kind_code=doc_kind_code,
                doc_number=doc_ref.doc_number,
                doc_date=_parse_doc_date(doc_ref.doc_date),
                presenting_kind_code="1",
            ))

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

    return items_created, created_items


def _attach_parsed_documents(
    db: AsyncSession,
    declaration: Declaration,
    documents: list[ParsedDocumentRef],
) -> tuple[int, list[Document]]:
    """Create Document records and return (count, created_docs) for evidence linking."""
    created_docs: list[Document] = []

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
        created_docs.append(doc)

    return len(created_docs), created_docs


def _enrich_evidence_map_with_document_ids(
    evidence_map: dict | None,
    created_docs: list[Document],
) -> dict | None:
    """Link evidence_map entries to concrete Document IDs by matching source type to doc_type."""
    if not evidence_map or not created_docs:
        return evidence_map

    # doc_type → document_id lookup (first match wins)
    type_to_doc_id: dict[str, str] = {}
    for doc in created_docs:
        doc_type = str(doc.doc_type).lower().replace("documenttype.", "")
        if doc_type not in type_to_doc_id:
            type_to_doc_id[doc_type] = str(doc.id)

    # source values used by EvidenceTracker → document doc_type mapping
    source_to_doc_type = {
        "invoice": "invoice",
        "contract": "contract",
        "packing_list": "packing_list",
        "transport_doc": "transport_doc",
        "transport_invoice": "transport_invoice",
        "application_statement": "application_statement",
        "specification": "specification",
        "tech_description": "tech_description",
        "transport": "transport_doc",
        "packing": "packing_list",
    }

    enriched = dict(evidence_map)
    for field, info in enriched.items():
        if not isinstance(info, dict) or info.get("document_id"):
            continue
        source = info.get("source", "")
        mapped_type = source_to_doc_type.get(source, source)
        doc_id = type_to_doc_id.get(mapped_type)
        if doc_id:
            info["document_id"] = doc_id
    return enriched


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

    if declaration.status == DeclarationStatus.SENT.value:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot apply parsed data to a sent declaration",
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
            declaration.declarant_inn_kpp = str(merged_inn_kpp)[:30]

        # --- 1. Создать/найти контрагентов ---
        sender_id = None
        receiver_id = None
        declarant_id = None

        if data.seller and data.seller.name:
            sender_id = await _find_or_create_counterparty(
                db, data.seller, "seller", current_user.company_id
            )
            counters["counterparties"] += 1

        # Графа 14: декларант — ТОЛЬКО из контракта/инвойса.
        # AI-промпт обязан возвращать buyer.name и buyer.address на русском языке.
        # Профиль компании — fallback только для ИНН/КПП/ОГРН, если нет в контракте.
        bp = data.buyer   # данные из контракта/инвойса (AI извлекает на русском)
        c = company       # профиль компании (fallback только для реквизитов)
        decl_name = bp.name if bp else None
        decl_address = bp.address if bp else None
        decl_country = (bp.country_code if bp else None) or (c.country_code if c else None) or "RU"
        decl_inn = (bp.inn if bp else None) or (c.inn if c else None)
        decl_kpp = (bp.kpp if bp else None) or (c.kpp if c else None)
        decl_ogrn = (bp.ogrn if bp else None) or (c.ogrn if c else None)

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
            declaration.declarant_ogrn = str(decl_ogrn)[:15] if decl_ogrn else None
            if company and company.contact_phone:
                declaration.declarant_phone = str(company.contact_phone)[:20]

        if company and hasattr(company, "broker_license") and company.broker_license and not declaration.broker_registry_number:
            declaration.broker_registry_number = str(company.broker_license)[:30]

        # Графа 8: источник — транспортный документ (consignee).
        # Если consignee из transport_doc совпадает с декларантом по ИНН/КПП/ОГРН →
        # buyer_matches_declarant=True → receiver = declarant («СМ. ГРАФУ 14 ДТ»).
        # Если не совпадает → data.consignee содержит отдельного получателя.
        if (not data.buyer_matches_declarant
                and data.consignee
                and data.consignee.name
                and not _is_placeholder_party(data.consignee.name)):
            receiver_id = await _find_or_create_counterparty(
                db, data.consignee, "buyer", current_user.company_id
            )
            counters["counterparties"] += 1
            logger.info("graph_8_from_transport_doc", receiver_name=data.consignee.name)
        elif declarant_id:
            receiver_id = declarant_id

        # Графа 9: «СМ. ГРАФУ 14 ДТ» по умолчанию.
        # Отдельное фин. ответственное лицо — ТОЛЬКО при наличии трёхстороннего договора.
        has_trilateral = _has_trilateral_contract(data.documents)
        financial_id = None
        if has_trilateral and isinstance(responsible_person_data, ParsedCounterparty) and responsible_person_data.name:
            financial_id = await _find_or_create_counterparty(
                db, responsible_person_data, "financial", current_user.company_id
            )
            counters["counterparties"] += 1
            logger.info("graph_9_from_trilateral", financial_name=responsible_person_data.name)
        elif declarant_id:
            financial_id = declarant_id

        # --- 2. Обновить поля декларации ---
        if sender_id:
            declaration.sender_counterparty_id = sender_id
        if receiver_id:
            declaration.receiver_counterparty_id = receiver_id
        if financial_id:
            declaration.financial_counterparty_id = financial_id

        exchange_rate = await _apply_declaration_header_fields(db, declaration, data)

        # --- 3. Создать товарные позиции ---
        counters["items"], created_items = await _create_declaration_items(
            db,
            declaration,
            data,
            current_user,
            sender_id,
            exchange_rate,
        )

        usd_rate = await _get_exchange_rate("USD")

        # --- 3b. Распределить фрахт по позициям (Гр.45) и рассчитать Гр.46 ---
        freight_dec = _to_decimal(data.freight_amount)
        if freight_dec and freight_dec > 0 and created_items:
            freight_rate = Decimal("1")
            fc = (data.freight_currency or "").upper()
            dc = (declaration.currency_code or "").upper()
            if fc and fc != "RUB":
                if fc == dc and exchange_rate > 0:
                    freight_rate = exchange_rate
                else:
                    fr = await _get_exchange_rate(fc)
                    if fr:
                        freight_rate = fr
            freight_rub = (freight_dec * freight_rate).quantize(Decimal("0.01"))
            declaration.freight_amount = freight_dec
            declaration.freight_currency = data.freight_currency

            total_gross = declaration.total_gross_weight or Decimal("0")
            if total_gross > 0:
                for item in created_items:
                    item_gross = item.gross_weight or Decimal("0")
                    item_freight = (freight_rub * item_gross / total_gross).quantize(Decimal("0.01"))
                    item.customs_value_rub = (item.customs_value_rub or Decimal("0")) + item_freight
                logger.info("freight_distributed",
                            freight_rub=float(freight_rub), items=len(created_items),
                            freight_currency=data.freight_currency, freight_rate=float(freight_rate))

        # Гр.46: статистическая стоимость в USD
        for item in created_items:
            if item.customs_value_rub and usd_rate and usd_rate > 0:
                item.statistical_value_usd = (item.customs_value_rub / usd_rate).quantize(Decimal("0.01"))

        # Гр.12: общая таможенная стоимость = сумма Гр.45 по всем позициям
        if created_items:
            total_cv = sum(
                (it.customs_value_rub or Decimal("0")) for it in created_items
            )
            if total_cv > 0:
                declaration.total_customs_value = total_cv.quantize(Decimal("0.01"))
                logger.info("total_customs_value_calculated",
                            value=float(declaration.total_customs_value),
                            items=len(created_items))

        # --- 3b-dts. Обновить ДТС, если она уже существует ---
        try:
            from app.models.customs_value_declaration import CustomsValueDeclaration
            from app.models.customs_value_item import CustomsValueItem as CVItem
            cvd_result = await db.execute(
                select(CustomsValueDeclaration)
                .where(CustomsValueDeclaration.declaration_id == declaration.id)
            )
            cvd = cvd_result.scalar_one_or_none()
            if cvd and created_items:
                total_gross_dts = declaration.total_gross_weight or Decimal("0")
                insurance_dec = _to_decimal(data.insurance_amount)
                loading_dec = _to_decimal(data.loading_cost)

                for ci in created_items:
                    cvi_result = await db.execute(
                        select(CVItem).where(CVItem.declaration_item_id == ci.id)
                    )
                    cvi = cvi_result.scalar_one_or_none()
                    if not cvi:
                        continue

                    weight_share = (
                        Decimal(str(ci.gross_weight or 0)) / total_gross_dts
                        if total_gross_dts > 0 else Decimal(0)
                    )

                    if insurance_dec and insurance_dec > 0:
                        ins_rub = (insurance_dec * exchange_rate).quantize(Decimal("0.01"))
                        cvi.insurance_cost = (ins_rub * weight_share).quantize(Decimal("0.01"))
                    if loading_dec and loading_dec > 0:
                        load_rub = (loading_dec * exchange_rate).quantize(Decimal("0.01"))
                        cvi.loading_unloading = (load_rub * weight_share).quantize(Decimal("0.01"))

                    ipn = cvi.invoice_price_national or Decimal("0")
                    ip = cvi.indirect_payments or Decimal("0")
                    cvi.base_total = (ipn + ip).quantize(Decimal("0.01"))

                    additions = sum(
                        Decimal(str(getattr(cvi, f) or 0))
                        for f in [
                            "broker_commission", "packaging_cost", "raw_materials",
                            "tools_molds", "consumed_materials", "design_engineering",
                            "license_payments", "seller_income", "transport_cost",
                            "loading_unloading", "insurance_cost",
                        ]
                    )
                    cvi.additions_total = additions.quantize(Decimal("0.01"))
                    deductions = sum(
                        Decimal(str(getattr(cvi, f) or 0))
                        for f in ["construction_after_import", "inland_transport", "duties_taxes"]
                    )
                    cvi.deductions_total = deductions.quantize(Decimal("0.01"))
                    cvi.customs_value_national = (
                        cvi.base_total + cvi.additions_total - cvi.deductions_total
                    ).quantize(Decimal("0.01"))
                    if usd_rate and usd_rate > 0:
                        cvi.customs_value_usd = (cvi.customs_value_national / usd_rate).quantize(Decimal("0.01"))

                logger.info("dts_updated_from_parsed", declaration_id=str(declaration.id))
        except Exception as exc:
            logger.warning("dts_update_from_parsed_failed", error=str(exc))

        # --- 3c. Рассчитать и сохранить CustomsPayment (Гр. 47/B) ---
        await db.execute(
            delete(CustomsPayment).where(CustomsPayment.declaration_id == declaration.id)
        )
        if created_items:
            try:
                from app.middleware.logging_middleware import tracing_headers
                pay_items = []
                for ci in created_items:
                    pay_items.append({
                        "item_no": ci.item_no,
                        "hs_code": ci.hs_code or "",
                        "customs_value_rub": float(ci.customs_value_rub or 0),
                    })
                async with httpx.AsyncClient(timeout=10) as http:
                    pay_resp = await http.post(
                        "http://calc-service:8005/api/v1/calc/payments/calculate",
                        json={
                            "items": pay_items,
                            "currency": declaration.currency_code or "RUB",
                            "exchange_rate": float(exchange_rate),
                        },
                        headers=tracing_headers(),
                    )
                    pay_resp.raise_for_status()
                    pay_data = pay_resp.json()

                totals = pay_data.get("totals", {})
                _PAYMENT_MAP = [
                    ("customs_fee", "1010", "customs_fee"),
                    ("total_duty", "2010", "duty"),
                    ("total_vat", "5010", "vat"),
                ]
                for total_key, code, p_type in _PAYMENT_MAP:
                    amount = Decimal(str(totals.get(total_key, 0)))
                    if amount > 0:
                        db.add(CustomsPayment(
                            declaration_id=declaration.id,
                            payment_type=p_type,
                            payment_type_code=code,
                            payment_specifics="ИУ",
                            base_amount=declaration.total_customs_value,
                            amount=amount,
                            currency_code="643",
                        ))
                for pi in pay_data.get("items", []):
                    item_no = pi.get("item_no", 0)
                    matched = next((ci for ci in created_items if ci.item_no == item_no), None)
                    if not matched:
                        continue
                    duty_amt = Decimal(str(pi.get("duty", {}).get("amount", 0)))
                    vat_amt = Decimal(str(pi.get("vat", {}).get("amount", 0)))
                    duty_rate = Decimal(str(pi.get("duty", {}).get("rate", 0)))
                    vat_rate = Decimal(str(pi.get("vat", {}).get("rate", 0)))
                    if duty_amt > 0:
                        db.add(CustomsPayment(
                            declaration_id=declaration.id,
                            item_id=matched.id,
                            payment_type="duty",
                            payment_type_code="2010",
                            payment_specifics="ИУ",
                            base_amount=matched.customs_value_rub,
                            rate=duty_rate,
                            amount=duty_amt,
                            currency_code="643",
                        ))
                    if vat_amt > 0:
                        db.add(CustomsPayment(
                            declaration_id=declaration.id,
                            item_id=matched.id,
                            payment_type="vat",
                            payment_type_code="5010",
                            payment_specifics="ИУ",
                            base_amount=(matched.customs_value_rub or Decimal("0")) + duty_amt,
                            rate=vat_rate,
                            amount=vat_amt,
                            currency_code="643",
                        ))
                logger.info("customs_payments_created",
                            declaration_id=str(declaration.id),
                            customs_fee=float(totals.get("customs_fee", 0)),
                            total_duty=float(totals.get("total_duty", 0)),
                            total_vat=float(totals.get("total_vat", 0)))
            except Exception as pay_err:
                logger.warning("customs_payment_calc_failed", error=str(pay_err)[:200])

        # --- 4. Привязать документы ---
        doc_count, created_docs = _attach_parsed_documents(db, declaration, data.documents)
        counters["documents"] = doc_count

        # --- 5. Сохранить evidence_map и ai_confidence ---
        if data.evidence_map:
            declaration.evidence_map = _enrich_evidence_map_with_document_ids(
                data.evidence_map, created_docs,
            )
        if data.confidence is not None:
            declaration.ai_confidence = Decimal(str(data.confidence))
        if data.issues:
            declaration.ai_issues = data.issues

        # --- 6. Логирование ---
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
                ("country_dispatch_code", 2), ("country_destination_code", 2),
                ("trading_country_code", 2), ("transport_type_border", 2), ("transport_type_inland", 2),
                ("currency_code", 3), ("incoterms_code", 3), ("deal_nature_code", 3),
                ("deal_specifics_code", 2), ("customs_office_code", 8), ("type_code", 10),
                ("country_origin_name", 60), ("transport_at_border", 100),
                ("transport_on_border_id", 100), ("delivery_place", 200),
                ("declarant_inn_kpp", 30), ("declarant_ogrn", 15), ("declarant_phone", 20),
                ("freight_currency", 3),
                ("transport_reg_number", 50), ("transport_nationality_code", 2),
            ],
        )

        set_processing_status(
            declaration, ProcessingStatus.AUTO_FILLED, db,
            user_id=str(current_user.id),
        )
        reset_signature_if_needed(declaration, db, user_id=str(current_user.id))
        if declaration.status != DeclarationStatus.NEW.value:
            await recalculate_declaration_state(declaration, db, user_id=str(current_user.id))

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
        status=DeclarationStatus.NEW,
        processing_status=ProcessingStatus.NOT_STARTED.value,
        signature_status="unsigned",
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


# ──────────────────────────────────────────────────────────────
# Evidence map editing
# ──────────────────────────────────────────────────────────────

class EvidenceFieldPatch(BaseModel):
    """Patch for a single evidence_map entry."""
    source: Optional[str] = None
    document_id: Optional[str] = None
    confidence: Optional[float] = None
    value_preview: Optional[str] = None
    note: Optional[str] = None


class EvidencePatchRequest(BaseModel):
    """Partial update of evidence_map — only specified fields are changed."""
    fields: dict[str, EvidenceFieldPatch]


@router.patch(
    "/{declaration_id}/evidence",
    response_model=dict,
    summary="Update individual evidence_map entries",
)
async def patch_evidence_map(
    declaration_id: uuid.UUID,
    data: EvidencePatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Declaration).where(Declaration.id == declaration_id)
    )
    declaration = result.scalar_one_or_none()
    if not declaration:
        raise HTTPException(status_code=404, detail="Declaration not found")

    ev_map: dict = dict(declaration.evidence_map or {})
    old_values: dict = {}

    for field_name, patch in data.fields.items():
        old_values[field_name] = ev_map.get(field_name)
        existing = ev_map.get(field_name, {})
        if not isinstance(existing, dict):
            existing = {}
        updates = patch.model_dump(exclude_unset=True)
        existing.update(updates)
        ev_map[field_name] = existing

    declaration.evidence_map = ev_map
    await db.flush()

    log = DeclarationLog(
        declaration_id=declaration.id,
        user_id=current_user.id,
        action="evidence_map_edited",
        new_value={
            "fields_changed": list(data.fields.keys()),
            "old_values": old_values,
        },
    )
    db.add(log)
    await db.commit()

    logger.info(
        "evidence_map_patched",
        declaration_id=str(declaration_id),
        fields=list(data.fields.keys()),
        user_id=str(current_user.id),
    )

    return {"status": "ok", "fields_updated": list(data.fields.keys()), "evidence_map": ev_map}
