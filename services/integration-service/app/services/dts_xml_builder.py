"""Build XML for Customs Value Declaration (ДТС-1) per EEC Decision 16.01.2018 No.4."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from lxml import etree

NS_DTS = "urn:EEC:R:CustomsValueDeclaration:v1.0.0"
NS_CACDO = "urn:EEC:M:CA:ComplexDataObjects:v1.10.3"
NS_CASDO = "urn:EEC:M:CA:SimpleDataObjects:v1.10.3"
NS_CCDO = "urn:EEC:M:ComplexDataObjects:v0.4.16"
NS_CSDO = "urn:EEC:M:SimpleDataObjects:v0.4.16"

NSMAP = {
    None: NS_DTS,
    "cacdo": NS_CACDO,
    "casdo": NS_CASDO,
    "ccdo": NS_CCDO,
    "csdo": NS_CSDO,
}


def _el(parent: etree._Element, ns: str, tag: str) -> etree._Element:
    return etree.SubElement(parent, f"{{{ns}}}{tag}")


def _text_el(
    parent: etree._Element, ns: str, tag: str, value: Any | None,
    attribs: dict[str, str] | None = None,
) -> etree._Element | None:
    if value is None or str(value).strip() == "":
        return None
    el = etree.SubElement(parent, f"{{{ns}}}{tag}")
    el.text = str(value).strip()
    if attribs:
        for k, v in attribs.items():
            el.set(k, v)
    return el


def _amount_el(parent: etree._Element, ns: str, tag: str, value: Any | None,
               currency: str = "RUB") -> etree._Element | None:
    return _text_el(parent, ns, tag, value,
                    {"currencyCode": currency, "currencyCodeListId": "2"} if value else None)


def _fmt_date(val: str | None) -> str:
    """ISO date for XML (YYYY-MM-DD)."""
    if val:
        try:
            dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            return str(val)[:10] if len(str(val)) >= 10 else str(val)
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _fmt_date_dd_mm_yy(val: str | datetime | None) -> str:
    """Формат для граф 4, 5, 10б: ДД.ММ.ГГ."""
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%d.%m.%y")
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%y")
    except (ValueError, AttributeError):
        s = str(val)
        return s[:10] if len(s) >= 10 else s


def _fmt_decimal(val: Any | None) -> str | None:
    if val is None:
        return None
    try:
        return f"{float(val):.2f}"
    except (ValueError, TypeError):
        return None


def _build_subject(parent: etree._Element, tag: str, cp: dict | None) -> None:
    """Build a SubjectDetails block (seller/buyer/declarant)."""
    if not cp:
        return
    subj = _el(parent, NS_DTS, tag)
    _text_el(subj, NS_CSDO, "SubjectName", cp.get("name"))
    _text_el(subj, NS_CSDO, "TaxpayerIdentifier", cp.get("tax_number") or cp.get("registration_number"))

    addr_fields = ["postal_code", "country_code", "region", "city", "street", "building", "room"]
    has_addr = any(cp.get(f) for f in addr_fields) or cp.get("address")
    if has_addr:
        addr = _el(subj, NS_CCDO, "SubjectAddressDetails")
        _text_el(addr, NS_CSDO, "CountryCode", cp.get("country_code"))
        _text_el(addr, NS_CSDO, "PostalCode", cp.get("postal_code"))
        _text_el(addr, NS_CSDO, "RegionName", cp.get("region"))
        _text_el(addr, NS_CSDO, "CityName", cp.get("city"))
        _text_el(addr, NS_CSDO, "StreetName", cp.get("street") or cp.get("address"))
        _text_el(addr, NS_CSDO, "BuildingNumberId", cp.get("building"))
        _text_el(addr, NS_CSDO, "RoomNumberId", cp.get("room"))


def build_dts_xml(
    decl: dict,
    dts: dict,
    sender: dict | None = None,
    receiver: dict | None = None,
    declarant: dict | None = None,
) -> str:
    """Build ДТС-1 XML from declaration + customs value declaration data."""

    root = etree.Element(f"{{{NS_DTS}}}CustomsValueDeclaration", nsmap=NSMAP)

    # EDocMeta
    meta = _el(root, NS_DTS, "EDocMeta")
    _text_el(meta, NS_CSDO, "EDocCode", "R.040")
    _text_el(meta, NS_CSDO, "EDocId", str(uuid.uuid4()))
    _text_el(meta, NS_CSDO, "EDocDateTime", datetime.now(timezone.utc).isoformat())

    # Declaration reference
    decl_ref = _el(root, NS_DTS, "CustomsDeclarationIdDetails")
    _text_el(decl_ref, NS_CASDO, "CustomsOfficeCode", decl.get("customs_office_code"))
    _text_el(decl_ref, NS_CASDO, "DocCreationDate", _fmt_date(decl.get("created_at")))
    _text_el(decl_ref, NS_CASDO, "CustomsDocumentId",
             decl.get("number_internal") or str(decl.get("id", ""))[:8])

    # Form type
    _text_el(root, NS_DTS, "FormTypeCode", dts.get("form_type", "DTS1"))
    _text_el(root, NS_DTS, "ValuationMethodCode", "1")

    # Sheet 1 — Subjects (graphs 1, 2a, 2b)
    _build_subject(root, "SellerDetails", sender)
    _build_subject(root, "BuyerDetails", receiver)
    _build_subject(root, "DeclarantDetails", declarant)

    # Graph 3 — Delivery terms (код + место, напр. EXW HONGKONG)
    if decl.get("incoterms_code"):
        terms = _el(root, NS_DTS, "DeliveryTermsDetails")
        _text_el(terms, NS_CASDO, "DeliveryTermsStringCode", decl.get("incoterms_code"))
        _text_el(terms, NS_CASDO, "DeliveryPlaceName", decl.get("delivery_place"))

    # Graph 4 — Invoice: номер и дата инвойса (не ДТ!)
    inv_num = decl.get("invoice_number")
    inv_date = decl.get("invoice_date")
    if inv_num or inv_date:
        inv_str = f"{inv_num or ''} ОТ {_fmt_date_dd_mm_yy(inv_date)}" if inv_date else (inv_num or "")
        _text_el(root, NS_DTS, "InvoiceDocumentId", inv_str.strip())
    elif decl.get("number_internal"):
        _text_el(root, NS_DTS, "InvoiceDocumentId", decl.get("number_internal"))

    # Graph 5 — Contract: номер и дата контракта
    cntr_num = decl.get("contract_number")
    cntr_date = decl.get("contract_date")
    if cntr_num or cntr_date:
        cntr_str = f"{cntr_num or ''} ОТ {_fmt_date_dd_mm_yy(cntr_date)}" if cntr_date else (cntr_num or "")
        _text_el(root, NS_DTS, "ContractDocumentId", cntr_str.strip())

    # Graphs 7–9 — Boolean flags
    flags = _el(root, NS_DTS, "TransactionCharacteristicsDetails")

    rel = _el(flags, NS_DTS, "RelatedPartyDetails")
    _text_el(rel, NS_DTS, "RelatedPartyIndicator", "1" if dts.get("related_parties") else "0")
    _text_el(rel, NS_DTS, "PriceInfluenceIndicator", "1" if dts.get("related_price_impact") else "0")
    _text_el(rel, NS_DTS, "VerificationIndicator", "1" if dts.get("related_verification") else "0")

    restr = _el(flags, NS_DTS, "RestrictionsDetails")
    _text_el(restr, NS_DTS, "RestrictionIndicator", "1" if dts.get("restrictions") else "0")
    _text_el(restr, NS_DTS, "ConditionIndicator", "1" if dts.get("price_conditions") else "0")

    ip_det = _el(flags, NS_DTS, "IntellectualPropertyDetails")
    _text_el(ip_det, NS_DTS, "LicensePaymentIndicator", "1" if dts.get("ip_license_payments") else "0")
    _text_el(ip_det, NS_DTS, "IncomeDependenceIndicator", "1" if dts.get("sale_depends_on_income") else "0")
    _text_el(ip_det, NS_DTS, "SellerIncomeIndicator", "1" if dts.get("income_to_seller") else "0")

    # Графа 17 — перевозчик и место «до» (общее для всех товаров)
    if dts.get("transport_carrier_name"):
        _text_el(root, NS_DTS, "TransportCarrierName", dts.get("transport_carrier_name"))
    if dts.get("transport_destination"):
        _text_el(root, NS_DTS, "TransportDestination", dts.get("transport_destination"))

    # Graph 6 — Additional docs
    if dts.get("additional_docs"):
        _text_el(root, NS_DTS, "AdditionalDocumentDetails", dts.get("additional_docs"))

    # Graph 10b — Filler (дата в дд.мм.гг для печати)
    filler = _el(root, NS_DTS, "FillerDetails")
    fd = dts.get("filler_date")
    _text_el(filler, NS_DTS, "FillerDate", _fmt_date_dd_mm_yy(fd) if fd else None)
    _text_el(filler, NS_DTS, "FillerName", dts.get("filler_name"))
    _text_el(filler, NS_DTS, "FillerDocument", dts.get("filler_document"))
    _text_el(filler, NS_DTS, "FillerContacts", dts.get("filler_contacts"))
    _text_el(filler, NS_DTS, "FillerPosition", dts.get("filler_position"))

    # Currency info (гр.11а курс инвойс→руб; гр.25б курс руб→USD)
    _text_el(root, NS_DTS, "CurrencyCode", decl.get("currency_code"))
    _text_el(root, NS_DTS, "ExchangeRate", _fmt_decimal(decl.get("exchange_rate")))
    _text_el(root, NS_DTS, "USDExchangeRate", _fmt_decimal(dts.get("usd_exchange_rate")))

    # Sheet 2 — Items (up to 3 per leaf). Графа 10а: добавочные листы = ceil(n/3)-1
    dts_items = dts.get("items", [])
    items_block = _el(root, NS_DTS, "CustomsValueGoodsDetails")
    add_sheets = max(0, (len(dts_items) + 2) // 3 - 1)
    _text_el(items_block, NS_DTS, "AdditionalSheetQuantity", str(add_sheets))

    for cvi in dts_items:
        item_el = _el(items_block, NS_DTS, "CustomsValueGoodsItemDetails")
        _text_el(item_el, NS_DTS, "ConsignmentItemOrdinal", str(cvi.get("item_no", 0)))
        _text_el(item_el, NS_DTS, "CommodityCode", cvi.get("hs_code"))

        # Graph 11a — price in foreign currency and national currency (с курсом)
        price = _el(item_el, NS_DTS, "TransactionPriceDetails")
        _amount_el(price, NS_DTS, "ForeignCurrencyAmount",
                   _fmt_decimal(cvi.get("invoice_price_foreign")),
                   decl.get("currency_code") or "USD")
        _amount_el(price, NS_DTS, "NationalCurrencyAmount",
                   _fmt_decimal(cvi.get("invoice_price_national")), "RUB")
        _text_el(price, NS_DTS, "ExchangeRate", _fmt_decimal(decl.get("exchange_rate")))

        # Graph 11b — indirect payments
        _amount_el(item_el, NS_DTS, "IndirectPaymentAmount",
                   _fmt_decimal(cvi.get("indirect_payments")), "RUB")

        # Graph 12 — base total
        _amount_el(item_el, NS_DTS, "BaseTotalAmount",
                   _fmt_decimal(cvi.get("base_total")), "RUB")

        # Graphs 13–19 — additions
        additions = _el(item_el, NS_DTS, "AdditionalChargeDetails")
        _amount_el(additions, NS_DTS, "BrokerCommissionAmount",
                   _fmt_decimal(cvi.get("broker_commission")), "RUB")
        _amount_el(additions, NS_DTS, "PackagingCostAmount",
                   _fmt_decimal(cvi.get("packaging_cost")), "RUB")
        _amount_el(additions, NS_DTS, "RawMaterialsAmount",
                   _fmt_decimal(cvi.get("raw_materials")), "RUB")
        _amount_el(additions, NS_DTS, "ToolsMoldsAmount",
                   _fmt_decimal(cvi.get("tools_molds")), "RUB")
        _amount_el(additions, NS_DTS, "ConsumedMaterialsAmount",
                   _fmt_decimal(cvi.get("consumed_materials")), "RUB")
        _amount_el(additions, NS_DTS, "DesignEngineeringAmount",
                   _fmt_decimal(cvi.get("design_engineering")), "RUB")
        _amount_el(additions, NS_DTS, "LicensePaymentAmount",
                   _fmt_decimal(cvi.get("license_payments")), "RUB")
        _amount_el(additions, NS_DTS, "SellerIncomeAmount",
                   _fmt_decimal(cvi.get("seller_income")), "RUB")
        _amount_el(additions, NS_DTS, "TransportCostAmount",
                   _fmt_decimal(cvi.get("transport_cost")), "RUB")
        _amount_el(additions, NS_DTS, "LoadingUnloadingAmount",
                   _fmt_decimal(cvi.get("loading_unloading")), "RUB")
        _amount_el(additions, NS_DTS, "InsuranceCostAmount",
                   _fmt_decimal(cvi.get("insurance_cost")), "RUB")

        # Graph 20 — total additions
        _amount_el(additions, NS_DTS, "AdditionsTotalAmount",
                   _fmt_decimal(cvi.get("additions_total")), "RUB")

        # Graphs 21–23 — deductions
        deductions = _el(item_el, NS_DTS, "DeductionDetails")
        _amount_el(deductions, NS_DTS, "ConstructionAfterImportAmount",
                   _fmt_decimal(cvi.get("construction_after_import")), "RUB")
        _amount_el(deductions, NS_DTS, "InlandTransportAmount",
                   _fmt_decimal(cvi.get("inland_transport")), "RUB")
        _amount_el(deductions, NS_DTS, "DutiesTaxesAmount",
                   _fmt_decimal(cvi.get("duties_taxes")), "RUB")

        # Graph 24 — total deductions
        _amount_el(deductions, NS_DTS, "DeductionsTotalAmount",
                   _fmt_decimal(cvi.get("deductions_total")), "RUB")

        # Graph 25 — customs value (25б с курсом USD)
        cv = _el(item_el, NS_DTS, "CustomsValueDetails")
        _amount_el(cv, NS_DTS, "CustomsValueNationalAmount",
                   _fmt_decimal(cvi.get("customs_value_national")), "RUB")
        _amount_el(cv, NS_DTS, "CustomsValueUSDAmount",
                   _fmt_decimal(cvi.get("customs_value_usd")), "USD")
        _text_el(cv, NS_DTS, "USDExchangeRate", _fmt_decimal(dts.get("usd_exchange_rate")))

        # Graph * — currency conversions
        conversions = cvi.get("currency_conversions")
        if conversions and isinstance(conversions, list):
            conv_block = _el(item_el, NS_DTS, "CurrencyConversionDetails")
            for conv in conversions:
                entry = _el(conv_block, NS_DTS, "CurrencyConversionEntry")
                _text_el(entry, NS_DTS, "ItemOrdinal", str(conv.get("item_no", "")))
                _text_el(entry, NS_DTS, "GraphNumber", str(conv.get("graph", "")))
                _text_el(entry, NS_DTS, "CurrencyCode", conv.get("currency_code"))
                _text_el(entry, NS_DTS, "ForeignAmount", _fmt_decimal(conv.get("amount_foreign")))
                _text_el(entry, NS_DTS, "ExchangeRate", _fmt_decimal(conv.get("exchange_rate")))

    # Additional data
    if dts.get("additional_data"):
        _text_el(root, NS_DTS, "AdditionalDataText", dts.get("additional_data"))

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True).decode("utf-8")
