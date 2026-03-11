"""Build FTS-compliant XML for EEC GoodsDeclaration (R.055, album 5.27.0)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from lxml import etree

NS_GD = "urn:EEC:R:055:GoodsDeclaration:v1.1.0"
NS_CACDO = "urn:EEC:M:CA:ComplexDataObjects:v1.10.3"
NS_CASDO = "urn:EEC:M:CA:SimpleDataObjects:v1.10.3"
NS_CCDO = "urn:EEC:M:ComplexDataObjects:v0.4.16"
NS_CSDO = "urn:EEC:M:SimpleDataObjects:v0.4.16"

NSMAP = {
    None: NS_GD,
    "cacdo": NS_CACDO,
    "casdo": NS_CASDO,
    "ccdo": NS_CCDO,
    "csdo": NS_CSDO,
}


def _el(parent: etree._Element, ns: str, tag: str) -> etree._Element:
    """Create a sub-element in the given namespace."""
    return etree.SubElement(parent, f"{{{ns}}}{tag}")


def _text_el(
    parent: etree._Element, ns: str, tag: str, value: Any | None,
    attribs: dict[str, str] | None = None,
) -> etree._Element | None:
    """Create a text sub-element if value is non-empty, with optional attributes."""
    if value is None or str(value).strip() == "":
        return None
    el = etree.SubElement(parent, f"{{{ns}}}{tag}")
    el.text = str(value).strip()
    if attribs:
        for k, v in attribs.items():
            el.set(k, v)
    return el


def _amount_el(parent: etree._Element, ns: str, tag: str, value: Any | None,
               currency: str = "RUB", code_list: str = "2") -> etree._Element | None:
    """Create an amount element with required currency attributes."""
    return _text_el(parent, ns, tag, value,
                    {"currencyCode": _alpha_currency(currency), "currencyCodeListId": code_list} if value else None)


def _measure_el(parent: etree._Element, ns: str, tag: str, value: Any | None,
                unit: str = "166", code_list: str = "2") -> etree._Element | None:
    """Create a measure element with required unit attributes."""
    return _text_el(parent, ns, tag, value,
                    {"measurementUnitCode": unit, "measurementUnitCodeListId": code_list} if value else None)


def _code_el(parent: etree._Element, ns: str, tag: str, value: Any | None,
             code_list: str = "2") -> etree._Element | None:
    """Create a code element with required codeListId attribute."""
    return _text_el(parent, ns, tag, value,
                    {"codeListId": code_list} if value else None)


def _fmt_date(iso_str: str | None) -> str:
    if iso_str:
        try:
            dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


_CURRENCY_NUM_TO_ALPHA = {
    "643": "RUB", "840": "USD", "978": "EUR", "156": "CNY",
    "826": "GBP", "392": "JPY", "756": "CHF", "949": "TRY",
}


def _alpha_currency(code: str | None) -> str:
    """Convert numeric currency code to ISO alpha-3."""
    if not code:
        return "RUB"
    c = str(code).strip()
    return _CURRENCY_NUM_TO_ALPHA.get(c, c)


def _fmt_datetime(iso_str: str | None) -> str:
    if iso_str:
        try:
            dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except (ValueError, AttributeError):
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


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
    """Build XML conforming to EEC_GoodsDeclaration.xsd (R.055).

    Parameters
    ----------
    decl : dict            -- Declaration fields from core-api.
    items : list[dict]     -- Declaration items.
    declarant : dict|None  -- Declarant counterparty (графа 14).
    sender : dict|None     -- Consignor counterparty (графа 2).
    receiver : dict|None   -- Consignee counterparty (графа 8).
    financial : dict|None  -- Financial settlement subject (графа 9).
    payments : list[dict]  -- Customs payments, keyed by item_id.
    item_documents : dict  -- {item_id_str: [doc_dict, ...]} for графа 44.
    item_preceding_docs : dict  -- {item_id_str: [doc_dict, ...]} for графа 40.
    """
    root = etree.Element(f"{{{NS_GD}}}GoodsDeclaration", nsmap=NSMAP)

    _build_edoc_meta(root, decl)
    _build_declaration_id(root, decl)
    _build_declaration_header(root, decl, items)
    _build_declarant(root, declarant or decl)
    _build_goods_shipment(
        root, decl, items, sender, receiver, financial,
        payments or [], item_documents or {}, item_preceding_docs or {},
    )
    _build_signatory(root, decl)

    xml_bytes: bytes = etree.tostring(
        root, pretty_print=True, xml_declaration=True, encoding="UTF-8",
    )
    return xml_bytes.decode("UTF-8")


def _build_edoc_meta(root: etree._Element, decl: dict) -> None:
    _text_el(root, NS_CSDO, "EDocCode", "R.055")
    _text_el(root, NS_CSDO, "EDocId", str(decl.get("id") or uuid.uuid4()))
    _text_el(root, NS_CSDO, "EDocDateTime", _fmt_datetime(decl.get("created_at")))


def _build_declaration_id(root: etree._Element, decl: dict) -> None:
    customs_code = decl.get("customs_office_code")
    number = decl.get("number_internal")
    if not customs_code and not number:
        return
    cdi = _el(root, NS_CACDO, "CustomsDeclarationIdDetails")
    _text_el(cdi, NS_CSDO, "CustomsOfficeCode", customs_code)
    _text_el(cdi, NS_CSDO, "DocCreationDate",
             _fmt_date(decl.get("submitted_at") or decl.get("created_at")))
    _text_el(cdi, NS_CASDO, "CustomsDocumentId", number)


def _build_declaration_header(root: etree._Element, decl: dict, items: list[dict]) -> None:
    type_code = decl.get("type_code") or ""
    kind = "ИМ"
    if type_code.upper().startswith("EX"):
        kind = "ЭК"
    elif type_code.upper().startswith("TR"):
        kind = "ТР"

    _text_el(root, NS_CASDO, "DeclarationKindCode", kind)

    procedure_digits = "".join(ch for ch in type_code if ch.isdigit())
    _code_el(root, NS_CASDO, "CustomsProcedureCode", procedure_digits or "40")
    _text_el(root, NS_CASDO, "DeclarationFeatureCode", decl.get("special_ref_code"))
    _text_el(root, NS_CASDO, "EDocIndicatorCode", "ЭД")

    _text_el(root, NS_CSDO, "PageQuantity", decl.get("forms_count"))
    _text_el(root, NS_CASDO, "GoodsQuantity", decl.get("total_items_count") or len(items))
    _text_el(root, NS_CASDO, "CargoQuantity", decl.get("total_packages_count"))


def _build_subject(parent: etree._Element, data: dict) -> None:
    """Shared builder for organization-type subjects (declarant, consignor, consignee)."""
    country = data.get("country_code")
    _code_el(parent, NS_CSDO, "UnifiedCountryCode", country)
    _text_el(parent, NS_CSDO, "SubjectName", data.get("name"))

    inn = data.get("tax_number") or data.get("declarant_inn_kpp")
    ogrn = data.get("ogrn") or data.get("declarant_ogrn")
    kpp = data.get("kpp")
    if inn:
        parts = str(inn).split("/")
        _text_el(parent, NS_CSDO, "TaxpayerId", parts[0])
        if len(parts) > 1:
            _text_el(parent, NS_CSDO, "TaxRegistrationReasonCode", parts[1])
        elif kpp:
            _text_el(parent, NS_CSDO, "TaxRegistrationReasonCode", kpp)
    if ogrn:
        _text_el(parent, NS_CSDO, "BusinessEntityId", ogrn)

    city = data.get("city")
    street = data.get("street")
    address_text = data.get("address")
    if city or street or address_text:
        addr = _el(parent, NS_CCDO, "SubjectAddressDetails")
        _code_el(addr, NS_CSDO, "UnifiedCountryCode", country)
        if address_text and not city and not street:
            _text_el(addr, NS_CSDO, "TerritoryCode", str(address_text)[:17])
        _text_el(addr, NS_CSDO, "RegionName", data.get("region"))
        _text_el(addr, NS_CSDO, "CityName", city or (str(address_text)[:120] if address_text and not street else None))
        _text_el(addr, NS_CSDO, "StreetName", street)
        _text_el(addr, NS_CSDO, "BuildingNumberId", data.get("building"))
        _text_el(addr, NS_CSDO, "RoomNumberId", data.get("room"))
        _text_el(addr, NS_CSDO, "PostalCode", data.get("postal_code"))

    phone = data.get("phone") or data.get("declarant_phone")
    email = data.get("email")
    if phone or email:
        comm = _el(parent, NS_CCDO, "CommunicationDetails")
        _text_el(comm, NS_CSDO, "PhoneNumber", phone)
        _text_el(comm, NS_CSDO, "EmailAddress", email)


def _build_declarant(root: etree._Element, data: dict) -> None:
    decl_el = _el(root, NS_CACDO, "DeclarantDetails")
    _build_subject(decl_el, data)


def _build_goods_shipment(
    root: etree._Element,
    decl: dict,
    items: list[dict],
    sender: dict | None,
    receiver: dict | None,
    financial: dict | None,
    payments: list[dict],
    item_documents: dict[str, list[dict]],
    item_preceding_docs: dict[str, list[dict]],
) -> None:
    gs = _el(root, NS_CACDO, "GDGoodsShipmentDetails")

    _build_country(gs, NS_CACDO, "DepartureCountryDetails", decl.get("country_dispatch_code"))
    _build_country(gs, NS_CACDO, "DestinationCountryDetails", decl.get("country_destination_code"))
    _build_country(gs, NS_CACDO, "TradeCountryDetails",
                   decl.get("trading_country_code") or decl.get("country_dispatch_code"))

    _build_delivery_terms(gs, decl)
    currency = decl.get("currency_code") or "RUB"
    alpha_curr = _alpha_currency(currency)
    _amount_el(gs, NS_CASDO, "CAValueAmount", decl.get("total_invoice_value"), alpha_curr)
    _text_el(gs, NS_CASDO, "ExchangeRate", decl.get("exchange_rate"),
             {"currencyCode": alpha_curr, "currencyCodeListId": "2"} if decl.get("exchange_rate") else None)

    if sender:
        consignor = _el(gs, NS_CACDO, "ConsignorDetails")
        _build_subject(consignor, sender)

    if receiver:
        consignee = _el(gs, NS_CACDO, "ConsigneeDetails")
        _build_subject(consignee, receiver)

    if financial:
        fin = _el(gs, NS_CACDO, "FinancialSettlementSubjectDetails")
        _build_subject(fin, financial)

    _amount_el(gs, NS_CASDO, "CustomsValueAmount", decl.get("total_customs_value"), "RUB")

    _build_transaction_nature(gs, decl)
    _build_consignment(gs, decl)
    _build_goods_location(gs, decl)

    payments_by_item: dict[str, list[dict]] = {}
    for p in payments:
        iid = str(p.get("item_id") or "")
        payments_by_item.setdefault(iid, []).append(p)

    for item in items:
        item_id_str = str(item.get("id", ""))
        _build_goods_item(
            gs, item,
            item_documents.get(item_id_str, []),
            item_preceding_docs.get(item_id_str, []),
            payments_by_item.get(item_id_str, []),
        )

    for p in payments:
        if not p.get("item_id"):
            _build_fact_payment(gs, p)


def _build_country(parent: etree._Element, ns: str, tag: str, code: str | None) -> None:
    if not code:
        return
    el = _el(parent, ns, tag)
    _code_el(el, NS_CASDO, "CACountryCode", code)


def _build_delivery_terms(parent: etree._Element, decl: dict) -> None:
    code = decl.get("incoterms_code")
    place = decl.get("delivery_place") or decl.get("loading_place")
    if not code and not place:
        return
    dt = _el(parent, NS_CACDO, "DeliveryTermsDetails")
    _code_el(dt, NS_CASDO, "DeliveryTermsCode", code)
    _text_el(dt, NS_CASDO, "PlaceName", place)


def _build_transaction_nature(parent: etree._Element, decl: dict) -> None:
    code = decl.get("deal_nature_code")
    code2 = decl.get("deal_specifics_code")
    if not code and not code2:
        return
    tn = _el(parent, NS_CACDO, "TransactionNatureDetails")
    nature_val = str(code).zfill(3) if code else None
    _text_el(tn, NS_CASDO, "TransactionNatureCode", nature_val)
    _text_el(tn, NS_CASDO, "TransactionFeatureCode", code2)


def _build_consignment(parent: etree._Element, decl: dict) -> None:
    container = decl.get("container_info")
    tb = decl.get("transport_type_border")
    ti = decl.get("transport_type_inland")
    if not container and not tb and not ti:
        return

    cons = _el(parent, NS_CACDO, "GDConsignmentDetails")
    _text_el(cons, NS_CASDO, "ContainerIndicator", container)

    if tb:
        bt = _el(cons, NS_CACDO, "BorderTransportDetails")
        _code_el(bt, NS_CSDO, "UnifiedTransportModeCode", tb)
        reg_num = decl.get("transport_reg_number")
        nat_code = decl.get("transport_nationality_code")
        if reg_num:
            tmd = _el(bt, NS_CACDO, "TransportMeansDetails")
            _text_el(tmd, NS_CASDO, "TransportMeansRegId", reg_num)
            if nat_code:
                nat = _el(tmd, NS_CACDO, "TransportMeansNationalityDetails")
                _text_el(nat, NS_CSDO, "UnifiedCountryCode", nat_code)

    if ti:
        adt = _el(cons, NS_CACDO, "ArrivalDepartureTransportDetails")
        _code_el(adt, NS_CSDO, "UnifiedTransportModeCode", ti)

    entry_code = decl.get("entry_customs_code")
    if entry_code:
        bco = _el(cons, NS_CACDO, "BorderCustomsOfficeDetails")
        _text_el(bco, NS_CSDO, "CustomsOfficeCode", entry_code)


def _build_goods_location(parent: etree._Element, decl: dict) -> None:
    loc_code = decl.get("goods_location_code")
    loc_customs = decl.get("goods_location_customs_code")
    loc_text = decl.get("goods_location")
    if not loc_code and not loc_customs and not loc_text:
        return
    gl = _el(parent, NS_CACDO, "GoodsLocationDetails")
    _text_el(gl, NS_CASDO, "GoodsLocationCode", loc_code)
    _text_el(gl, NS_CSDO, "CustomsOfficeCode", loc_customs)
    if loc_text and not loc_code:
        _text_el(gl, NS_CASDO, "PlaceName", loc_text)
    _text_el(gl, NS_CASDO, "CustomsControlZoneId", decl.get("goods_location_zone_id"))


def _build_goods_item(
    parent: etree._Element,
    item: dict,
    docs: list[dict],
    prec_docs: list[dict],
    payments: list[dict],
) -> None:
    gi = _el(parent, NS_CACDO, "GDGoodsItemDetails")

    _text_el(gi, NS_CASDO, "ConsignmentItemOrdinal", item.get("item_no"))
    _text_el(gi, NS_CSDO, "CommodityCode", item.get("hs_code"))

    desc = item.get("description") or ""
    for i, chunk in enumerate(_split_description(desc)):
        _text_el(gi, NS_CASDO, "GoodsDescriptionText", chunk)

    _measure_el(gi, NS_CSDO, "UnifiedGrossMassMeasure", item.get("gross_weight"), "166", "2")
    _measure_el(gi, NS_CSDO, "UnifiedNetMassMeasure", item.get("net_weight"), "166", "2")

    unit_qty = item.get("additional_unit_qty")
    raw_unit = item.get("additional_unit_code") or item.get("additional_unit") or "796"
    unit_code = raw_unit if raw_unit.isdigit() else "796"
    if unit_qty:
        gmd = _el(gi, NS_CACDO, "GoodsMeasureDetails")
        _measure_el(gmd, NS_CASDO, "GoodsMeasure", unit_qty, unit_code, "2")

    pkg_count = item.get("package_count")
    pkg_code = item.get("package_type_code") or item.get("package_type")
    if pkg_count or pkg_code:
        cpp = _el(gi, NS_CACDO, "CargoPackagePalletDetails")
        _text_el(cpp, NS_CASDO, "CargoQuantity", pkg_count)
        if pkg_code:
            ppd = _el(cpp, NS_CACDO, "PackagePalletDetails")
            _code_el(ppd, NS_CSDO, "PackageKindCode", pkg_code)
            _text_el(ppd, NS_CASDO, "PackageMarkName", item.get("package_marks"))

    _build_country(gi, NS_CACDO, "OriginCountryDetails", item.get("country_origin_code"))

    pref = item.get("preference_code")
    pref_country = item.get("country_origin_pref_code")
    if pref_country:
        pco = _el(gi, NS_CACDO, "PrefOriginCountryDetails")
        _text_el(pco, NS_CSDO, "UnifiedCountryCode", pref_country)

    if pref:
        pd = _el(gi, NS_CACDO, "PreferenceDetails")
        _text_el(pd, NS_CASDO, "CustomsDutyPrefCode", pref)

    proc = item.get("procedure_code")
    if proc:
        cpd = _el(gi, NS_CACDO, "CustomsProcedureDetails")
        parts = str(proc).split("/") if "/" in str(proc) else [proc]
        _text_el(cpd, NS_CASDO, "CustomsModeCode", parts[0])
        if len(parts) > 1:
            _text_el(cpd, NS_CASDO, "PreviousCustomsModeCode", parts[1])

    _amount_el(gi, NS_CASDO, "CAValueAmount", item.get("unit_price"), "RUB")
    _amount_el(gi, NS_CASDO, "CustomsValueAmount", item.get("customs_value_rub"), "RUB")
    _amount_el(gi, NS_CASDO, "StatisticValueAmount", item.get("statistical_value_usd"), "USD")
    _code_el(gi, NS_CASDO, "ValuationMethodCode", item.get("mos_method_code"))

    for pd in prec_docs:
        _build_preceding_doc(gi, pd)

    for doc in docs:
        _build_presented_doc(gi, doc)

    for pay in payments:
        _build_customs_payment(gi, pay)


def _split_description(text: str, max_len: int = 250, max_parts: int = 4) -> list[str]:
    if not text:
        return []
    parts: list[str] = []
    while text and len(parts) < max_parts:
        parts.append(text[:max_len])
        text = text[max_len:]
    return parts


def _build_preceding_doc(parent: etree._Element, doc: dict) -> None:
    pd = _el(parent, NS_CACDO, "PrecedingDocDetails")
    _text_el(pd, NS_CASDO, "LineId", doc.get("line_id"))
    _text_el(pd, NS_CSDO, "DocKindCode", doc.get("doc_kind_code"))
    _text_el(pd, NS_CSDO, "DocName", doc.get("doc_name"))

    customs_code = doc.get("customs_office_code")
    customs_num = doc.get("customs_doc_number")
    if customs_code or customs_num:
        cdi = _el(pd, NS_CACDO, "CustomsDocIdDetails")
        _text_el(cdi, NS_CSDO, "CustomsOfficeCode", customs_code)
        _text_el(cdi, NS_CSDO, "DocCreationDate", _fmt_date(doc.get("doc_date")))
        _text_el(cdi, NS_CASDO, "CustomsDocumentId", customs_num)

    other_num = doc.get("other_doc_number")
    if other_num and not customs_code:
        _text_el(pd, NS_CSDO, "DocId", other_num)
        _text_el(pd, NS_CSDO, "DocCreationDate", _fmt_date(doc.get("other_doc_date")))

    _text_el(pd, NS_CASDO, "ConsignmentItemOrdinal", doc.get("goods_number"))


def _build_presented_doc(parent: etree._Element, doc: dict) -> None:
    pd = _el(parent, NS_CACDO, "PresentedDocDetails")
    _text_el(pd, NS_CSDO, "DocKindCode", doc.get("doc_kind_code"))
    _text_el(pd, NS_CSDO, "DocId", doc.get("doc_number"))
    _text_el(pd, NS_CSDO, "DocCreationDate", _fmt_date(doc.get("doc_date")) if doc.get("doc_date") else None)
    _text_el(pd, NS_CSDO, "DocValidityDate",
             _fmt_date(doc.get("doc_validity_date")) if doc.get("doc_validity_date") else None)
    _text_el(pd, NS_CSDO, "UnifiedCountryCode", doc.get("country_code"))
    _text_el(pd, NS_CSDO, "AuthorityName", doc.get("authority_name"))
    _text_el(pd, NS_CASDO, "LineId", doc.get("line_id"))


def _build_customs_payment(parent: etree._Element, pay: dict) -> None:
    cp = _el(parent, NS_CACDO, "CustomsPaymentDetails")
    _text_el(cp, NS_CASDO, "CustomsTaxModeCode", pay.get("payment_type_code"))
    _text_el(cp, NS_CASDO, "TaxBaseMeasure", pay.get("base_amount"))
    _text_el(cp, NS_CSDO, "UnifiedCurrencyN3Code", pay.get("tax_base_currency_code") or pay.get("currency_code"))
    _text_el(cp, NS_CSDO, "UnifiedMeasurementUnitCode", pay.get("tax_base_unit_code"))

    rate = pay.get("rate")
    rate_type = pay.get("rate_type_code")
    if rate is not None:
        erd = _el(cp, NS_CACDO, "EffectiveCustomsRateDetails")
        _text_el(erd, NS_CASDO, "DutyTaxFeeRateValue", rate)
        _text_el(erd, NS_CASDO, "RateTypeCode", rate_type)
        _text_el(erd, NS_CSDO, "UnifiedCurrencyN3Code", pay.get("rate_currency_code"))
        _text_el(erd, NS_CSDO, "UnifiedMeasurementUnitCode", pay.get("rate_unit_code"))
        _text_el(erd, NS_CASDO, "WeightingFactor", pay.get("weighting_factor"))

    _text_el(cp, NS_CASDO, "DutyTaxFeeRateDate",
             _fmt_date(pay.get("rate_use_date")) if pay.get("rate_use_date") else None)
    _text_el(cp, NS_CASDO, "CustomsTaxPaymentFeatureCode", pay.get("payment_specifics"))
    _text_el(cp, NS_CASDO, "CAPaymentNAmount", pay.get("amount"))


def _build_fact_payment(parent: etree._Element, pay: dict) -> None:
    fp = _el(parent, NS_CACDO, "GDFactPaymentDetails")
    _text_el(fp, NS_CASDO, "CustomsTaxModeCode", pay.get("payment_type_code"))
    _text_el(fp, NS_CASDO, "CAPaymentNAmount", pay.get("amount"))


def _build_signatory(root: etree._Element, decl: dict) -> None:
    broker_reg = decl.get("broker_registry_number")
    broker_contract = decl.get("broker_contract_number")
    if broker_reg or broker_contract:
        sr = _el(root, NS_CACDO, "SignatoryRepresentativeDetails")
        if broker_reg:
            brd = _el(sr, NS_CACDO, "BrokerRegistryDocDetails")
            _text_el(brd, NS_CASDO, "RegistrationNumberId", broker_reg)
        if broker_contract:
            rcd = _el(sr, NS_CACDO, "RepresentativeContractDetails")
            _text_el(rcd, NS_CSDO, "DocId", broker_contract)
            _text_el(rcd, NS_CSDO, "DocCreationDate",
                     _fmt_date(decl.get("broker_contract_date")) if decl.get("broker_contract_date") else None)

    signer_name = decl.get("signatory_name")
    if signer_name:
        sp = _el(root, NS_CACDO, "SignatoryPersonV2Details")
        sd = _el(sp, NS_CACDO, "SigningDetails")
        _text_el(sd, NS_CSDO, "FullNameDetails", signer_name)
        _text_el(sd, NS_CSDO, "PositionName", decl.get("signatory_position"))

        id_doc = decl.get("signatory_id_doc")
        if id_doc:
            sid = _el(sp, NS_CACDO, "SignatoryPersonIdentityDetails")
            _text_el(sid, NS_CSDO, "DocId", id_doc)

        _text_el(sp, NS_CASDO, "QualificationCertificate", decl.get("signatory_cert_number"))

        poa = decl.get("signatory_power_of_attorney")
        if poa:
            poad = _el(sp, NS_CACDO, "PowerOfAttorneyDetails")
            _text_el(poad, NS_CSDO, "DocId", poa)
