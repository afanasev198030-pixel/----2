"""Build ESADout_CU XML for Russian customs (FTS format, album 5.24.0).

Generates XML conforming to urn:customs.ru:Information:CustomsDocuments:ESADout_CU:5.24.0
(DocumentModeID 1006107E) — the standard accepted by FTS EAIS.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from lxml import etree

# ──────────────────────────────────────────────────────────────────────
# Namespaces
# ──────────────────────────────────────────────────────────────────────
NS_ESAD = "urn:customs.ru:Information:CustomsDocuments:ESADout_CU:5.24.0"
NS_CAT = "urn:customs.ru:CommonAggregateTypes:5.24.0"
NS_CLT = "urn:customs.ru:CommonLeafTypes:5.10.0"
NS_CATESAD = "urn:customs.ru:CUESADCommonAggregateTypesCust:5.24.0"
NS_RUSCAT = "urn:customs.ru:RUSCommonAggregateTypes:5.24.0"
NS_RUDECL = "urn:customs.ru:RUDeclCommonAggregateTypesCust:5.24.0"
NS_CLTESAD = "urn:customs.ru:CUESADCommonLeafTypes:5.17.0"
NS_RUSCLT = "urn:customs.ru:RUSCommonLeafTypes:5.21.0"

NSMAP = {
    None: NS_ESAD,
    "cat_ru": NS_CAT,
    "clt_ru": NS_CLT,
    "catESAD_cu": NS_CATESAD,
    "RUScat_ru": NS_RUSCAT,
    "RUDECLcat": NS_RUDECL,
    "cltESAD_cu": NS_CLTESAD,
    "RUSclt_ru": NS_RUSCLT,
}

DOCUMENT_MODE_ID = "1006107E"

# ──────────────────────────────────────────────────────────────────────
# Lookup dictionaries
# ──────────────────────────────────────────────────────────────────────
COUNTRY_NAMES: dict[str, str] = {
    "RU": "РОССИЯ", "CN": "КИТАЙ", "HK": "ГОНКОНГ", "US": "США",
    "DE": "ГЕРМАНИЯ", "TR": "ТУРЦИЯ", "KZ": "КАЗАХСТАН", "BY": "БЕЛАРУСЬ",
    "AM": "АРМЕНИЯ", "KG": "КЫРГЫЗСТАН", "UZ": "УЗБЕКИСТАН", "TJ": "ТАДЖИКИСТАН",
    "JP": "ЯПОНИЯ", "KR": "КОРЕЯ, РЕСПУБЛИКА", "GB": "ВЕЛИКОБРИТАНИЯ",
    "FR": "ФРАНЦИЯ", "IT": "ИТАЛИЯ", "IN": "ИНДИЯ", "TW": "ТАЙВАНЬ",
    "VN": "ВЬЕТНАМ", "TH": "ТАИЛАНД", "MY": "МАЛАЙЗИЯ", "SG": "СИНГАПУР",
    "AE": "ОАЭ", "SA": "САУДОВСКАЯ АРАВИЯ", "IL": "ИЗРАИЛЬ", "PL": "ПОЛЬША",
    "CZ": "ЧЕХИЯ", "NL": "НИДЕРЛАНДЫ", "BE": "БЕЛЬГИЯ", "ES": "ИСПАНИЯ",
    "PT": "ПОРТУГАЛИЯ", "AT": "АВСТРИЯ", "CH": "ШВЕЙЦАРИЯ", "SE": "ШВЕЦИЯ",
    "FI": "ФИНЛЯНДИЯ", "NO": "НОРВЕГИЯ", "DK": "ДАНИЯ", "IE": "ИРЛАНДИЯ",
    "BR": "БРАЗИЛИЯ", "MX": "МЕКСИКА", "CA": "КАНАДА", "AU": "АВСТРАЛИЯ",
}

COUNTRY_NUMERIC: dict[str, str] = {"RU": "643", "CN": "156", "HK": "344"}

UNIT_NAMES: dict[str, str] = {
    "796": "ШТ", "166": "КГ", "006": "М", "055": "М2", "113": "М3",
    "736": "Л", "116": "ПАРЫ", "625": "Л 100%", "778": "УПАК",
    "356": "КМ", "383": "Т",
}

_CURRENCY_NUM_TO_ALPHA: dict[str, str] = {
    "643": "RUB", "840": "USD", "978": "EUR", "156": "CNY",
    "826": "GBP", "392": "JPY", "756": "CHF", "949": "TRY",
}
_CURRENCY_ALPHA_TO_NUM: dict[str, str] = {v: k for k, v in _CURRENCY_NUM_TO_ALPHA.items()}

DOC_KIND_NAMES: dict[str, str] = {
    "01191": "СЕРТИФИКАТ", "01402": "ДС", "02011": "ТРАНСПОРТНАЯ НАКЛАДНАЯ",
    "02017": "АВИАНАКЛАДНАЯ", "02018": "КОНОСАМЕНТ",
    "03011": "ДОГОВОР (КОНТРАКТ)", "03012": "ДОПОЛНЕНИЕ К ДОГОВОРУ",
    "03031": "ДОКУМЕНТ ПО ВАЛЮТНОМУ КОНТРОЛЮ",
    "04021": "ИНВОЙС", "04024": "СПЕЦИФИКАЦИЯ", "04025": "УПАКОВОЧНЫЙ ЛИСТ",
    "04031": "СЧЕТ ЗА ПЕРЕВОЗКУ", "04033": "ДОГОВОР ПО ПЕРЕВОЗКЕ",
    "04091": "СЕРТИФИКАТ СООТВЕТСТВИЯ",
    "05011": "РАЗРЕШИТЕЛЬНЫЙ ДОКУМЕНТ", "05999": "ТЕХОПИСАНИЕ ОБЩЕЕ",
    "06011": "СЕРТИФИКАТ О ПРОИСХОЖДЕНИИ",
    "09023": "ИНОЙ ДОКУМЕНТ", "09034": "СВИДЕТЕЛЬСТВО ТП", "09999": "ПОЯСНЕНИЕ",
}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────
def _el(parent: etree._Element, ns: str | None, tag: str) -> etree._Element:
    if ns:
        return etree.SubElement(parent, f"{{{ns}}}{tag}")
    return etree.SubElement(parent, tag)


def _txt(
    parent: etree._Element, ns: str | None, tag: str, value: Any | None
) -> etree._Element | None:
    if value is None or str(value).strip() == "":
        return None
    if ns:
        el = etree.SubElement(parent, f"{{{ns}}}{tag}")
    else:
        el = etree.SubElement(parent, tag)
    el.text = str(value).strip()
    return el


def _fmt_date(iso_str: str | None) -> str | None:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return str(iso_str)[:10] if len(str(iso_str)) >= 10 else None


def _fmt_datetime_tz(iso_str: str | None) -> str | None:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%dT%H:%M:%S+03:00")
    except (ValueError, AttributeError):
        return None


def _fmt_amount(val: Any | None) -> str | None:
    if val is None:
        return None
    try:
        return f"{Decimal(str(val)):.2f}"
    except Exception:
        return str(val)


def _fmt_weight(val: Any | None) -> str | None:
    if val is None:
        return None
    try:
        return f"{Decimal(str(val)):.3f}"
    except Exception:
        return str(val)


def _alpha_currency(code: str | None) -> str:
    if not code:
        return "RUB"
    c = str(code).strip()
    return _CURRENCY_NUM_TO_ALPHA.get(c, c)


def _num_currency(code: str | None) -> str:
    if not code:
        return "643"
    c = str(code).strip()
    return _CURRENCY_ALPHA_TO_NUM.get(c, c)


def _country_name(code: str | None) -> str | None:
    if not code:
        return None
    return COUNTRY_NAMES.get(code.upper())


def _split_description(text: str, max_len: int = 250, max_parts: int = 4) -> list[str]:
    if not text:
        return []
    parts: list[str] = []
    while text and len(parts) < max_parts:
        parts.append(text[:max_len])
        text = text[max_len:]
    return parts


# ──────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────
def build_declaration_xml(
    decl: dict,
    items: list[dict],
    declarant: dict | None,
    sender: dict | None,
    receiver: dict | None,
    financial: dict | None = None,
    payments: list[dict] | None = None,
    item_documents: dict[str, list[dict]] | None = None,
    item_preceding_docs: dict[str, list[dict]] | None = None,
) -> str:
    """Build XML conforming to ESADout_CU 5.24.0 (DocumentModeID 1006107E).

    Parameters
    ----------
    decl : dict            -- Declaration fields from core-api.
    items : list[dict]     -- Declaration items.
    declarant : dict|None  -- Declarant counterparty.
    sender : dict|None     -- Consignor counterparty.
    receiver : dict|None   -- Consignee counterparty.
    financial : dict|None  -- Financial settlement subject.
    payments : list[dict]  -- Customs payments.
    item_documents : dict  -- {item_id_str: [doc_dict, ...]} for gr. 44.
    item_preceding_docs : dict  -- {item_id_str: [doc_dict, ...]} for gr. 40.
    """
    root = etree.Element(
        f"{{{NS_ESAD}}}ESADout_CU",
        nsmap=NSMAP,
        attrib={"DocumentModeID": DOCUMENT_MODE_ID},
    )

    _build_header(root, decl)
    _build_goods_shipment(
        root, decl, items, declarant, sender, receiver, financial,
        payments or [], item_documents or {}, item_preceding_docs or {},
    )
    _build_filled_person(root, decl)
    _build_customs_representative(root, decl)

    xml_bytes: bytes = etree.tostring(
        root, pretty_print=True, xml_declaration=True, encoding="UTF-8",
    )
    return xml_bytes.decode("UTF-8")


# ──────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────
def _build_header(root: etree._Element, decl: dict) -> None:
    _txt(root, NS_CAT, "DocumentID", str(decl.get("id") or uuid.uuid4()))

    hdr = _el(root, None, "EECEDocHeaderAddInfo")
    _txt(hdr, NS_RUSCAT, "EDocCode", "R.036")
    _txt(hdr, NS_RUSCAT, "EDocDateTime",
         _fmt_datetime_tz(decl.get("submitted_at") or decl.get("created_at")))

    type_code = decl.get("type_code") or ""
    kind = "ИМ"
    if type_code.upper().startswith("EX"):
        kind = "ЭК"
    elif type_code.upper().startswith("TR"):
        kind = "ТР"

    _txt(root, None, "CustomsProcedure", kind)

    procedure_digits = "".join(ch for ch in type_code if ch.isdigit())
    _txt(root, None, "CustomsModeCode", procedure_digits or "40")
    _txt(root, None, "ElectronicDocumentSign", "ЭД")
    _txt(root, None, "RecipientCountryCode",
         decl.get("country_destination_code") or "RU")


# ──────────────────────────────────────────────────────────────────────
# Goods Shipment
# ──────────────────────────────────────────────────────────────────────
def _build_goods_shipment(
    root: etree._Element,
    decl: dict,
    items: list[dict],
    declarant: dict | None,
    sender: dict | None,
    receiver: dict | None,
    financial: dict | None,
    payments: list[dict],
    item_documents: dict[str, list[dict]],
    item_preceding_docs: dict[str, list[dict]],
) -> None:
    gs = _el(root, None, "ESADout_CUGoodsShipment")

    origin_code = decl.get("country_dispatch_code")
    _txt(gs, NS_CATESAD, "OriginCountryName",
         decl.get("country_origin_name") or _country_name(origin_code))
    _txt(gs, NS_CATESAD, "OriginCountryCode", origin_code)
    _txt(gs, NS_CATESAD, "TotalGoodsNumber",
         decl.get("total_items_count") or len(items))
    _txt(gs, NS_CATESAD, "TotalPackageNumber", decl.get("total_packages_count"))
    _txt(gs, NS_CATESAD, "TotalSheetNumber", decl.get("forms_count"))
    _txt(gs, NS_CATESAD, "TotalCustCost", _fmt_amount(decl.get("total_customs_value")))
    _txt(gs, NS_CATESAD, "CustCostCurrencyCode",
         _alpha_currency(decl.get("currency_code")))

    _build_consignor(gs, sender)
    _build_consignee(gs, receiver, declarant)
    _build_financial(gs, financial, declarant)
    _build_declarant_section(gs, declarant or decl)
    _build_goods_location(gs, decl)
    _build_consignment(gs, decl)
    _build_contract_terms(gs, decl)

    payments_by_item: dict[str, list[dict]] = defaultdict(list)
    for p in payments:
        iid = str(p.get("item_id") or "")
        payments_by_item[iid].append(p)

    for item in items:
        item_id_str = str(item.get("id", ""))
        _build_goods_item(
            gs, item,
            item_documents.get(item_id_str, []),
            item_preceding_docs.get(item_id_str, []),
            payments_by_item.get(item_id_str, []),
        )

    _build_aggregate_payments(gs, payments, declarant or decl)


# ──────────────────────────────────────────────────────────────────────
# Subjects
# ──────────────────────────────────────────────────────────────────────
def _build_address(parent: etree._Element, data: dict) -> None:
    """Build RUScat_ru:SubjectAddressDetails."""
    postal = data.get("postal_code")
    country = data.get("country_code")
    region = data.get("region")
    city = data.get("city")
    street = data.get("street")
    address_text = data.get("address")

    if not any([postal, country, region, city, street, address_text]):
        return

    addr = _el(parent, NS_RUSCAT, "SubjectAddressDetails")
    _txt(addr, NS_RUSCAT, "PostalCode", postal)
    _txt(addr, NS_RUSCAT, "CountryCode", country)
    _txt(addr, NS_RUSCAT, "CounryName", _country_name(country))
    _txt(addr, NS_RUSCAT, "Region", region)

    if city:
        _txt(addr, NS_RUSCAT, "City", city)
    elif address_text and not street:
        _txt(addr, NS_RUSCAT, "City", str(address_text)[:120])

    if street:
        _txt(addr, NS_RUSCAT, "StreetHouse", street)


def _build_rf_org_features(parent: etree._Element, data: dict) -> None:
    """Build cat_ru:RFOrganizationFeatures for Russian organizations."""
    ogrn = data.get("ogrn") or data.get("declarant_ogrn")
    inn = data.get("tax_number") or data.get("declarant_inn_kpp")
    kpp = data.get("kpp")

    if inn and "/" in str(inn):
        parts = str(inn).split("/")
        inn = parts[0]
        if not kpp and len(parts) > 1:
            kpp = parts[1]

    if not any([ogrn, inn, kpp]):
        return

    rf = _el(parent, NS_CAT, "RFOrganizationFeatures")
    _txt(rf, NS_CAT, "OGRN", ogrn)
    _txt(rf, NS_CAT, "INN", inn)
    _txt(rf, NS_CAT, "KPP", kpp)


def _build_communication(parent: etree._Element, data: dict) -> None:
    phone = data.get("phone") or data.get("declarant_phone")
    email = data.get("email")
    if not phone and not email:
        return
    comm = _el(parent, NS_RUSCAT, "CommunicationDetails")
    _txt(comm, NS_CAT, "Phone", phone)
    _txt(comm, NS_CAT, "E_mail", email)


def _build_consignor(parent: etree._Element, sender: dict | None) -> None:
    if not sender:
        return
    el = _el(parent, None, "ESADout_CUConsignor")
    _txt(el, NS_CAT, "OrganizationName", sender.get("name"))
    _build_address(el, sender)


def _build_consignee(
    parent: etree._Element,
    receiver: dict | None,
    declarant: dict | None,
) -> None:
    el = _el(parent, None, "ESADout_CUConsignee")
    if _is_same_subject(receiver, declarant):
        _txt(el, NS_RUDECL, "EqualIndicator", "true")
    elif receiver:
        _txt(el, NS_CAT, "OrganizationName", receiver.get("name"))
        _build_rf_org_features(el, receiver)
        _build_address(el, receiver)
    else:
        _txt(el, NS_RUDECL, "EqualIndicator", "true")


def _build_financial(
    parent: etree._Element,
    financial: dict | None,
    declarant: dict | None,
) -> None:
    el = _el(parent, None, "ESADout_CUFinancialAdjustingResponsiblePerson")
    if _is_same_subject(financial, declarant):
        _txt(el, None, "DeclarantEqualFlag", "1")
    elif financial:
        _txt(el, NS_CAT, "OrganizationName", financial.get("name"))
        _build_rf_org_features(el, financial)
        _build_address(el, financial)
    else:
        _txt(el, None, "DeclarantEqualFlag", "1")


def _build_declarant_section(parent: etree._Element, data: dict) -> None:
    el = _el(parent, None, "ESADout_CUDeclarant")
    _txt(el, NS_CAT, "OrganizationName", data.get("name"))
    _build_rf_org_features(el, data)
    _build_address(el, data)
    _build_communication(el, data)


def _is_same_subject(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return True
    inn_a = a.get("tax_number") or ""
    inn_b = b.get("tax_number") or b.get("declarant_inn_kpp") or ""
    if inn_a and inn_b:
        return str(inn_a).split("/")[0] == str(inn_b).split("/")[0]
    return str(a.get("id", "1")) == str(b.get("id", "2"))


# ──────────────────────────────────────────────────────────────────────
# Goods Location (гр. 30)
# ──────────────────────────────────────────────────────────────────────
def _build_goods_location(parent: etree._Element, decl: dict) -> None:
    loc_code = decl.get("goods_location_info_type_code") or decl.get("goods_location_code")
    loc_customs = decl.get("goods_location_customs_code")
    loc_text = decl.get("goods_location")
    svh_doc = decl.get("goods_location_svh_doc_id")

    if not any([loc_code, loc_customs, loc_text, svh_doc]):
        return

    gl = _el(parent, None, "ESADout_CUGoodsLocation")
    _txt(gl, None, "InformationTypeCode", loc_code)
    _txt(gl, None, "CustomsOffice", loc_customs)
    _txt(gl, None, "CustomsCountryCode", "RU")

    if svh_doc:
        rd = _el(gl, None, "RegisterDocumentIdDetails")
        _txt(rd, NS_CATESAD, "DocId", svh_doc)

    loc_address = decl.get("goods_location_address")
    if loc_address or loc_text:
        addr_el = _el(gl, None, "Address")
        _txt(addr_el, NS_RUSCAT, "CountryCode", "RU")
        _txt(addr_el, NS_RUSCAT, "CounryName", "РОССИЯ")
        _txt(addr_el, NS_RUSCAT, "City", loc_address or loc_text)


# ──────────────────────────────────────────────────────────────────────
# Consignment / Transport (гр. 18, 21, 25, 26, 29)
# ──────────────────────────────────────────────────────────────────────
def _build_consignment(parent: etree._Element, decl: dict) -> None:
    container = decl.get("container_info")
    dispatch_code = decl.get("country_dispatch_code")
    dest_code = decl.get("country_destination_code")
    tb = decl.get("transport_type_border")
    entry_code = decl.get("entry_customs_code")

    if not any([container, dispatch_code, dest_code, tb, entry_code]):
        return

    cons = _el(parent, None, "ESADout_CUConsigment")
    _txt(cons, NS_CATESAD, "ContainerIndicator", container)
    _txt(cons, NS_CATESAD, "DispatchCountryCode", dispatch_code)
    _txt(cons, NS_CATESAD, "DispatchCountryName",
         decl.get("country_origin_name") or _country_name(dispatch_code))
    _txt(cons, NS_CATESAD, "DestinationCountryCode", dest_code)
    _txt(cons, NS_CATESAD, "DestinationCountryName", _country_name(dest_code))

    if entry_code:
        bco = _el(cons, NS_CATESAD, "BorderCustomsOffice")
        _txt(bco, NS_CAT, "Code", entry_code)
        _txt(bco, NS_CAT, "OfficeName", decl.get("border_customs_name"))
        _txt(bco, NS_CAT, "CustomsCountryCode",
             decl.get("border_customs_country_code") or "643")

    if tb:
        bt = _el(cons, None, "ESADout_CUBorderTransport")
        _txt(bt, NS_CAT, "TransportModeCode", tb)
        _txt(bt, NS_CAT, "TransportNationalityCode",
             decl.get("transport_nationality_code") or "00")
        _txt(bt, None, "TransportMeansQuantity",
             decl.get("transport_means_quantity") or "1")

        reg_num = decl.get("transport_reg_number")
        if reg_num:
            rtm = _el(bt, None, "RUTransportMeans")
            _txt(rtm, NS_CAT, "TransportKindCode",
                 decl.get("transport_kind_code") or f"{tb}0")
            _txt(rtm, NS_CAT, "TransportTypeName", decl.get("transport_type_name"))
            _txt(rtm, NS_CAT, "TransportIdentifier", reg_num)
            _txt(rtm, NS_CAT, "TransportMeansNationalityCode",
                 decl.get("transport_nationality_code") or "00")


# ──────────────────────────────────────────────────────────────────────
# Contract Terms (гр. 11, 20, 22, 24)
# ──────────────────────────────────────────────────────────────────────
def _build_contract_terms(parent: etree._Element, decl: dict) -> None:
    currency = decl.get("currency_code")
    total_inv = decl.get("total_invoice_value")
    trade_country = decl.get("trading_country_code") or decl.get("country_dispatch_code")
    deal_feature = decl.get("deal_specifics_code")
    deal_nature = decl.get("deal_nature_code")
    incoterms = decl.get("incoterms_code")
    delivery_place = decl.get("delivery_place") or decl.get("loading_place")

    if not any([currency, total_inv, trade_country, deal_nature, incoterms]):
        return

    ct = _el(parent, None, "ESADout_CUMainContractTerms")
    _txt(ct, NS_CATESAD, "ContractCurrencyCode", _alpha_currency(currency))
    _txt(ct, NS_CATESAD, "TotalInvoiceAmount", _fmt_amount(total_inv))
    _txt(ct, NS_CATESAD, "TradeCountryCode", trade_country)
    _txt(ct, NS_CATESAD, "DealFeatureCode", deal_feature)
    if deal_nature:
        _txt(ct, NS_CATESAD, "DealNatureCode", str(deal_nature).zfill(3))

    if incoterms or delivery_place:
        dt = _el(ct, NS_CATESAD, "CUESADDeliveryTerms")
        _txt(dt, NS_CAT, "DeliveryPlace", delivery_place)
        _txt(dt, NS_CAT, "DeliveryTermsStringCode", incoterms)


# ──────────────────────────────────────────────────────────────────────
# Goods Item (ESADout_CUGoods)
# ──────────────────────────────────────────────────────────────────────
def _build_goods_item(
    parent: etree._Element,
    item: dict,
    docs: list[dict],
    prec_docs: list[dict],
    payments: list[dict],
) -> None:
    gi = _el(parent, None, "ESADout_CUGoods")

    _txt(gi, NS_CATESAD, "GoodsNumeric", item.get("item_no"))

    desc = item.get("description") or ""
    short_desc = desc[:250] if desc else None
    _txt(gi, NS_CATESAD, "GoodsDescription", short_desc)

    _txt(gi, NS_CATESAD, "GrossWeightQuantity", _fmt_weight(item.get("gross_weight")))
    _txt(gi, NS_CATESAD, "NetWeightQuantity", _fmt_weight(item.get("net_weight")))
    _txt(gi, NS_CATESAD, "InvoicedCost", _fmt_amount(item.get("unit_price")))
    _txt(gi, NS_CATESAD, "CustomsCost", _fmt_amount(item.get("customs_value_rub")))
    _txt(gi, NS_CATESAD, "StatisticalCost", _fmt_amount(item.get("statistical_value_usd")))
    _txt(gi, NS_CATESAD, "GoodsTNVEDCode", item.get("hs_code"))
    _txt(gi, NS_CATESAD, "IntellectPropertySign",
         item.get("intellect_property_sign") or "N")
    _txt(gi, NS_CATESAD, "OriginCountryCode", item.get("country_origin_code"))
    _txt(gi, NS_CATESAD, "CustomsCostCorrectMethod", item.get("mos_method_code"))

    _build_goods_group_description(gi, item, desc)
    _build_preference(gi, item)

    for doc in docs:
        _build_presented_doc(gi, doc)

    for pay in payments:
        _build_payment_calc(gi, pay)

    _build_supplementary_qty(gi, item)
    _build_goods_packaging(gi, item)
    _build_customs_procedure(gi, item)


def _build_goods_group_description(
    parent: etree._Element, item: dict, full_desc: str
) -> None:
    manufacturer = item.get("manufacturer")
    trademark = item.get("trademark")
    model = item.get("model_name")
    qty = item.get("additional_unit_qty")
    unit_code = item.get("additional_unit_code") or item.get("additional_unit") or "796"
    if unit_code and not unit_code.isdigit():
        unit_code = "796"

    if not full_desc and not manufacturer:
        return

    ggd = _el(parent, NS_CATESAD, "GoodsGroupDescription")

    for chunk in _split_description(full_desc):
        _txt(ggd, NS_CATESAD, "GoodsDescription", chunk)

    ggi = _el(ggd, NS_CATESAD, "GoodsGroupInformation")
    _txt(ggi, NS_CATESAD, "Manufacturer", manufacturer or "НЕИЗВЕСТЕН")
    _txt(ggi, NS_CATESAD, "GoodsMark", trademark or "ОТСУТСТВУЕТ")
    _txt(ggi, NS_CATESAD, "GoodsModel", model)
    _txt(ggi, NS_CATESAD, "GoodsMarking",
         item.get("goods_marking") or "ОТСУТСТВУЕТ")
    _txt(ggi, NS_CATESAD, "SerialNumber",
         item.get("serial_number") or "ОТСУТСТВУЮТ")

    if qty:
        ggq = _el(ggi, NS_CATESAD, "GoodsGroupQuantity")
        _txt(ggq, NS_CATESAD, "GoodsQuantity", _fmt_amount(qty))
        _txt(ggq, NS_CATESAD, "MeasureUnitQualifierName",
             UNIT_NAMES.get(unit_code, "ШТ"))
        _txt(ggq, NS_CATESAD, "MeasureUnitQualifierCode", unit_code)

    _txt(ggi, NS_CATESAD, "LineNum", "1")
    _txt(ggi, NS_CATESAD, "InvoicedCost", _fmt_amount(item.get("unit_price")))

    _txt(ggd, NS_CATESAD, "GroupNum", "1")


def _build_preference(parent: etree._Element, item: dict) -> None:
    pref = item.get("preference_code") or ""
    if len(pref) >= 8:
        tax = pref[0:2]
        duty = pref[2:4]
        excise = pref[4:6].replace("--", "-")
        rate = pref[6:8]
    elif pref:
        tax = duty = rate = pref[:2] if len(pref) >= 2 else pref
        excise = "-"
    else:
        return

    pf = _el(parent, NS_CATESAD, "Preferencii")
    _txt(pf, NS_CATESAD, "CustomsTax", tax)
    _txt(pf, NS_CATESAD, "CustomsDuty", duty)
    _txt(pf, NS_CATESAD, "Excise", excise)
    _txt(pf, NS_CATESAD, "Rate", rate)


def _build_supplementary_qty(parent: etree._Element, item: dict) -> None:
    qty = item.get("additional_unit_qty")
    if not qty:
        return
    unit_code = item.get("additional_unit_code") or item.get("additional_unit") or "796"
    if unit_code and not unit_code.isdigit():
        unit_code = "796"

    sq = _el(parent, None, "SupplementaryGoodsQuantity")
    _txt(sq, NS_CAT, "GoodsQuantity", _fmt_amount(qty))
    _txt(sq, NS_CAT, "MeasureUnitQualifierName", UNIT_NAMES.get(unit_code, "ШТ"))
    _txt(sq, NS_CAT, "MeasureUnitQualifierCode", unit_code)


def _build_goods_packaging(parent: etree._Element, item: dict) -> None:
    pkg_count = item.get("package_count")
    pkg_code = item.get("package_type_code") or item.get("package_type")

    if not pkg_count and not pkg_code:
        return

    gp = _el(parent, None, "ESADGoodsPackaging")
    _txt(gp, NS_CATESAD, "PakageQuantity", pkg_count)
    _txt(gp, NS_CATESAD, "PakageTypeCode", "1")

    if pkg_code:
        ppi = _el(gp, NS_CATESAD, "PackagePalleteInformation")
        _txt(ppi, NS_CATESAD, "InfoKindCode", "0")
        _txt(ppi, NS_CATESAD, "PalleteCode", pkg_code if len(str(pkg_code)) <= 3 else "PK")
        _txt(ppi, NS_CATESAD, "PalleteQuantity", pkg_count)


def _build_customs_procedure(parent: etree._Element, item: dict) -> None:
    proc = item.get("procedure_code") or ""
    if not proc:
        return

    ep = _el(parent, None, "ESADCustomsProcedure")

    if "/" in proc:
        parts = proc.split("/")
        main_code = parts[0]
        prev_code = parts[1] if len(parts) > 1 else "00"
    elif len(proc) == 4:
        main_code = proc[:2]
        prev_code = proc[2:]
    else:
        main_code = proc
        prev_code = "00"

    _txt(ep, NS_CATESAD, "MainCustomsModeCode", main_code)
    _txt(ep, NS_CATESAD, "PrecedingCustomsModeCode", prev_code)
    _txt(ep, NS_CATESAD, "GoodsTransferFeature",
         item.get("goods_transfer_feature") or "000")


# ──────────────────────────────────────────────────────────────────────
# Presented Documents (гр. 44)
# ──────────────────────────────────────────────────────────────────────
def _build_presented_doc(parent: etree._Element, doc: dict) -> None:
    pd = _el(parent, None, "ESADout_CUPresentedDocument")

    kind_code = doc.get("doc_kind_code") or ""
    doc_name = doc.get("doc_name") or DOC_KIND_NAMES.get(kind_code, "")

    _txt(pd, NS_CAT, "PrDocumentName", doc_name)
    _txt(pd, NS_CAT, "PrDocumentNumber", doc.get("doc_number"))
    _txt(pd, NS_CAT, "PrDocumentDate", _fmt_date(doc.get("doc_date")))
    _txt(pd, NS_CATESAD, "PresentedDocumentModeCode", kind_code)

    begin_date = doc.get("doc_begin_date") or doc.get("doc_validity_date")
    if begin_date:
        _txt(pd, NS_CATESAD, "DocumentBeginActionsDate", _fmt_date(begin_date))

    record_id = doc.get("record_id")
    if record_id:
        _txt(pd, NS_CATESAD, "RecordID", record_id)

    edoc_id = doc.get("electronic_doc_id") or doc.get("archive_doc_id")
    earch_id = doc.get("electronic_arch_id")
    doc_mode_id = doc.get("document_mode_id")
    if edoc_id:
        rfg = _el(pd, NS_CATESAD, "RFG44PresentedDocId")
        _txt(rfg, NS_CATESAD, "ElectronicDocumentID", edoc_id)
        _txt(rfg, NS_CATESAD, "ElectronicArchID", earch_id)
        _txt(rfg, NS_CATESAD, "DocumentModeID", doc_mode_id)

    presenting_kind = doc.get("presenting_kind_code")
    pcustoms = doc.get("presenting_customs_code")
    preg_date = doc.get("presenting_reg_date")
    pgtd = doc.get("presenting_gtd_number")

    if presenting_kind is not None or pcustoms:
        dpd = _el(pd, NS_RUDECL, "DocumentPresentingDetails")
        _txt(dpd, NS_RUDECL, "DocPresentKindCode",
             presenting_kind if presenting_kind is not None else "0")

        if pcustoms or preg_date or pgtd:
            cdi = _el(dpd, NS_RUDECL, "CustomsDocIdDetails")
            _txt(cdi, NS_CAT, "CustomsCode", pcustoms)
            _txt(cdi, NS_CAT, "RegistrationDate", _fmt_date(preg_date))
            _txt(cdi, NS_CAT, "GTDNumber", pgtd)


# ──────────────────────────────────────────────────────────────────────
# Customs Payments
# ──────────────────────────────────────────────────────────────────────
def _build_payment_calc(parent: etree._Element, pay: dict) -> None:
    pc = _el(parent, None, "ESADout_CUCustomsPaymentCalculation")

    _txt(pc, NS_CATESAD, "PaymentModeCode", pay.get("payment_type_code"))
    _txt(pc, NS_CATESAD, "PaymentAmount", _fmt_amount(pay.get("amount")))
    _txt(pc, NS_CATESAD, "PaymentCurrencyCode",
         _num_currency(pay.get("currency_code")))

    base = pay.get("base_amount")
    if base:
        _txt(pc, NS_CATESAD, "TaxBase", _fmt_amount(base))
        _txt(pc, NS_CATESAD, "TaxBaseCurrencyCode",
             _num_currency(pay.get("tax_base_currency_code") or pay.get("currency_code")))

    rate = pay.get("rate")
    if rate is not None:
        _txt(pc, NS_CATESAD, "Rate", _fmt_amount(rate))
        _txt(pc, NS_CATESAD, "RateTypeCode", pay.get("rate_type_code"))

    _txt(pc, NS_CATESAD, "RateUseDate", _fmt_date(pay.get("rate_use_date")))
    _txt(pc, NS_CATESAD, "PaymentCode",
         pay.get("payment_specifics") or "ИУ")


def _build_aggregate_payments(
    parent: etree._Element,
    payments: list[dict],
    declarant: dict,
) -> None:
    item_payments = [p for p in payments if p.get("item_id")]
    if not item_payments:
        return

    aggregated: dict[str, Decimal] = defaultdict(Decimal)
    for p in item_payments:
        code = p.get("payment_type_code") or ""
        amt = p.get("amount")
        if code and amt:
            try:
                aggregated[code] += Decimal(str(amt))
            except Exception:
                pass

    if not aggregated:
        return

    inn = declarant.get("tax_number") or declarant.get("declarant_inn_kpp") or ""
    if "/" in str(inn):
        inn = str(inn).split("/")[0]

    ep = _el(parent, None, "ESADout_CUPayments")
    for code in sorted(aggregated.keys()):
        cp = _el(ep, None, "ESADout_CUCustomsPayment")
        _txt(cp, NS_CATESAD, "PaymentModeCode", code)
        _txt(cp, NS_CATESAD, "PaymentAmount", _fmt_amount(aggregated[code]))
        _txt(cp, NS_CATESAD, "PaymentCurrencyCode", "643")
        if inn:
            rf = _el(cp, None, "RFOrganizationFeatures")
            _txt(rf, NS_CAT, "INN", inn)


# ──────────────────────────────────────────────────────────────────────
# Signatory / Filled Person (гр. 54)
# ──────────────────────────────────────────────────────────────────────
def _build_filled_person(root: etree._Element, decl: dict) -> None:
    surname = decl.get("signatory_surname")
    first_name = decl.get("signatory_first_name")
    full_name = decl.get("signatory_name") or ""

    if not surname and full_name:
        parts = full_name.strip().split()
        surname = parts[0] if parts else None
        first_name = parts[1] if len(parts) > 1 else None

    if not surname:
        return

    fp = _el(root, None, "FilledPerson")

    sd = _el(fp, NS_RUDECL, "SigningDetails")
    _txt(sd, NS_CAT, "PersonSurname", surname)
    _txt(sd, NS_CAT, "PersonName", first_name)
    mid_name = decl.get("signatory_middle_name")
    if not mid_name and full_name:
        parts = full_name.strip().split()
        mid_name = parts[2] if len(parts) > 2 else None
    _txt(sd, NS_CAT, "PersonMiddleName", mid_name)
    _txt(sd, NS_CAT, "PersonPost", decl.get("signatory_position"))

    s_phone = decl.get("signatory_phone") or decl.get("declarant_phone")
    s_email = decl.get("signatory_email")
    if s_phone or s_email:
        sc = _el(sd, NS_RUSCAT, "CommunicationDetails")
        _txt(sc, NS_CAT, "Phone", s_phone)
        _txt(sc, NS_CAT, "E_mail", s_email)

    _txt(sd, NS_RUSCAT, "SigningDate",
         _fmt_datetime_tz(decl.get("signatory_signing_date") or decl.get("submitted_at")))

    id_code = decl.get("signatory_id_card_code")
    id_series = decl.get("signatory_id_card_series")
    id_number = decl.get("signatory_id_card_number")
    id_doc_text = decl.get("signatory_id_doc")

    if id_code or id_series or id_number or id_doc_text:
        sid = _el(fp, NS_RUDECL, "SignatoryPersonIdentityDetails")
        _txt(sid, NS_RUSCAT, "IdentityCardCode", id_code or "RU01001")
        if id_series:
            _txt(sid, NS_RUSCAT, "IdentityCardSeries", id_series)
        if id_number:
            _txt(sid, NS_RUSCAT, "IdentityCardNumber", id_number)
        elif id_doc_text:
            _txt(sid, NS_RUSCAT, "IdentityCardNumber", id_doc_text)
        _txt(sid, NS_RUSCAT, "IdentityCardDate",
             _fmt_date(decl.get("signatory_id_card_date")))
        _txt(sid, NS_RUSCAT, "OrganizationName", decl.get("signatory_id_card_org"))

    poa_num = decl.get("signatory_poa_number") or decl.get("signatory_power_of_attorney")
    poa_date = decl.get("signatory_poa_date")
    if poa_num:
        poa = _el(fp, NS_RUDECL, "PowerOfAttorneyDetails")
        _txt(poa, NS_CAT, "PrDocumentName", "ДОВЕРЕННОСТЬ")
        _txt(poa, NS_CAT, "PrDocumentNumber", poa_num)
        _txt(poa, NS_CAT, "PrDocumentDate", _fmt_date(poa_date))
        _txt(poa, NS_RUSCAT, "DocStartDate",
             _fmt_date(decl.get("signatory_poa_start_date") or poa_date))
        _txt(poa, NS_RUSCAT, "DocValidityDate",
             _fmt_date(decl.get("signatory_poa_end_date")))


# ──────────────────────────────────────────────────────────────────────
# Customs Representative (Таможенный представитель)
# ──────────────────────────────────────────────────────────────────────
def _build_customs_representative(root: etree._Element, decl: dict) -> None:
    broker_reg = decl.get("broker_registry_number")
    broker_contract = decl.get("broker_contract_number")
    if not broker_reg and not broker_contract:
        return

    cr = _el(root, None, "CUESADCustomsRepresentative")

    if broker_reg:
        brd = _el(cr, NS_RUDECL, "BrokerRegistryDocDetails")
        _txt(brd, NS_RUDECL, "DocKindCode",
             decl.get("broker_doc_kind_code") or "09034")
        _txt(brd, NS_RUDECL, "RegistrationNumberId", broker_reg)

    if broker_contract:
        rcd = _el(cr, NS_RUDECL, "RepresentativeContractDetails")
        _txt(rcd, NS_CAT, "PrDocumentNumber", broker_contract)
        _txt(rcd, NS_CAT, "PrDocumentDate",
             _fmt_date(decl.get("broker_contract_date")))
        doc_kind = decl.get("broker_contract_doc_kind_code")
        if doc_kind:
            _txt(rcd, NS_RUSCAT, "DocKindCode", doc_kind)
