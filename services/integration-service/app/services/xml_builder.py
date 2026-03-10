"""Build ФТС-compatible XML for a customs declaration (DeclarationOnGoods)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lxml import etree

NS = "urn:customs.ru:Information:CustomsDocuments:DeclarationOnGoods:5.24.0"
NSMAP = {None: NS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sub(parent: etree._Element, tag: str, text: Any | None) -> etree._Element | None:
    """Add a sub-element with *text* if the value is not None / empty."""
    if text is None or str(text).strip() == "":
        return None
    el = etree.SubElement(parent, tag)
    el.text = str(text)
    return el


def _fmt_date(iso_str: str | None) -> str:
    """Return date in YYYY-MM-DD from an ISO timestamp or today."""
    if iso_str:
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_declaration_xml(
    decl: dict,
    items: list[dict],
    sender: dict | None,
    receiver: dict | None,
    payments: list[dict] | None = None,
) -> str:
    """Return a UTF-8 XML string representing the declaration.

    Parameters
    ----------
    decl : dict
        Declaration data (flat dict from core-api ``GET /api/v1/declarations/{id}``).
    items : list[dict]
        Declaration items list.
    sender : dict | None
        Counterparty for графа 2 (consignor).
    receiver : dict | None
        Counterparty for графа 8 (consignee).
    payments : list[dict] | None
        Customs payments for графа 47 / B.
    """
    root = etree.Element("DeclarationOnGoods", nsmap=NSMAP)

    # --- Declaration kind (ИМ / ЭК) ---
    type_code = decl.get("type_code") or ""
    if type_code.upper().startswith("IM"):
        _sub(root, "DeclarationKind", "ИМ")
    elif type_code.upper().startswith("EX"):
        _sub(root, "DeclarationKind", "ЭК")
    else:
        _sub(root, "DeclarationKind", type_code)

    # Customs procedure (digits after IM/EX)
    procedure_digits = "".join(ch for ch in type_code if ch.isdigit())
    _sub(root, "CustomsProcedure", procedure_digits or "40")

    # --- Графа 7: особенности декларирования ---
    _sub(root, "SpecialReferenceCode", decl.get("special_ref_code"))

    # --- Declaration number block ---
    dn = etree.SubElement(root, "DeclarationNumber")
    _sub(dn, "CustomsOfficeCode", decl.get("customs_office_code"))
    _sub(dn, "RegistrationDate", _fmt_date(decl.get("submitted_at") or decl.get("created_at")))
    _sub(dn, "SerialNumber", decl.get("number_internal"))

    # --- Consignor (графа 2) ---
    if sender:
        cg = etree.SubElement(root, "Consignor")
        _sub(cg, "OrganizationName", sender.get("name"))
        _sub(cg, "Address", sender.get("address"))
        _sub(cg, "CountryCode", sender.get("country_code"))

    # --- Consignee (графа 8) ---
    if receiver:
        ce = etree.SubElement(root, "Consignee")
        _sub(ce, "OrganizationName", receiver.get("name"))
        _sub(ce, "Address", receiver.get("address"))
        _sub(ce, "CountryCode", receiver.get("country_code"))
        _sub(ce, "INN", receiver.get("tax_number"))

    # --- Financial / regulatory ---
    fr = etree.SubElement(root, "FinancialRegulatory")
    contract = decl.get("transport_at_border") or decl.get("number_internal")
    _sub(fr, "ContractNumber", contract)
    _sub(fr, "DealNatureCode", decl.get("deal_nature_code"))
    _sub(fr, "DealSpecificsCode", decl.get("deal_specifics_code"))

    # --- Transport info ---
    ti = etree.SubElement(root, "TransportInfo")
    _sub(ti, "BorderTransportMode", decl.get("transport_type_border"))
    _sub(ti, "InlandTransportMode", decl.get("transport_type_inland"))
    _sub(ti, "TransportDocument", decl.get("transport_at_border"))
    _sub(ti, "ContainerIndicator", decl.get("container_info"))

    # --- Countries ---
    trading_country = decl.get("trading_country_code") or decl.get("country_dispatch_code")
    _sub(root, "TradeCountry", trading_country)
    _sub(root, "DispatchCountry", decl.get("country_dispatch_code"))
    _sub(root, "DestinationCountry", decl.get("country_destination_code"))
    _sub(root, "OriginCountry", decl.get("country_origin_name"))

    # --- Delivery terms (Incoterms) ---
    dt_el = etree.SubElement(root, "DeliveryTerms")
    _sub(dt_el, "Code", decl.get("incoterms_code"))
    _sub(dt_el, "Place", decl.get("delivery_place") or decl.get("loading_place"))

    # --- Currency info ---
    ci = etree.SubElement(root, "CurrencyInfo")
    _sub(ci, "CurrencyCode", decl.get("currency_code"))
    _sub(ci, "TotalInvoiceValue", decl.get("total_invoice_value"))
    _sub(ci, "ExchangeRate", decl.get("exchange_rate"))

    # --- Consignment totals ---
    cs = etree.SubElement(root, "ConsignmentInfo")
    _sub(cs, "TotalItemsCount", decl.get("total_items_count"))
    _sub(cs, "TotalPackagesCount", decl.get("total_packages_count"))
    _sub(cs, "TotalGrossWeight", decl.get("total_gross_weight"))
    _sub(cs, "TotalNetWeight", decl.get("total_net_weight"))
    _sub(cs, "TotalCustomsValue", decl.get("total_customs_value"))

    # --- Declaration items ---
    di_root = etree.SubElement(root, "DeclarationItems")
    for item in items:
        item_el = etree.SubElement(di_root, "Item")
        item_el.set("itemNumber", str(item.get("item_no", "")))

        _sub(item_el, "GoodsDescription", item.get("description"))
        _sub(item_el, "CommercialName", item.get("commercial_name"))
        _sub(item_el, "HSCode", item.get("hs_code"))
        _sub(item_el, "HSCodeLetters", item.get("hs_code_letters"))
        _sub(item_el, "HSCodeExtra", item.get("hs_code_extra"))
        _sub(item_el, "OriginCountryCode", item.get("country_origin_code"))
        _sub(item_el, "OriginCountryPrefCode", item.get("country_origin_pref_code"))
        _sub(item_el, "GrossWeight", item.get("gross_weight"))
        _sub(item_el, "NetWeight", item.get("net_weight"))
        _sub(item_el, "PreferenceCode", item.get("preference_code"))
        _sub(item_el, "ProcedureCode", item.get("procedure_code"))
        _sub(item_el, "Quantity", item.get("additional_unit_qty"))
        _sub(item_el, "AdditionalUnit", item.get("additional_unit"))
        _sub(item_el, "UnitPrice", item.get("unit_price"))
        _sub(item_el, "CustomsValue", item.get("customs_value_rub"))
        _sub(item_el, "StatisticalValueUSD", item.get("statistical_value_usd"))
        _sub(item_el, "ValuationMethod", item.get("mos_method_code"))

    # --- Payments (графа 47) ---
    if payments:
        pay_root = etree.SubElement(root, "Payments")
        for pay in payments:
            pay_el = etree.SubElement(pay_root, "Payment")
            _sub(pay_el, "PaymentTypeCode", pay.get("payment_type_code"))
            _sub(pay_el, "PaymentType", pay.get("payment_type"))
            _sub(pay_el, "BaseAmount", pay.get("base_amount"))
            _sub(pay_el, "Rate", pay.get("rate"))
            _sub(pay_el, "Amount", pay.get("amount"))
            _sub(pay_el, "PaymentSpecifics", pay.get("payment_specifics"))

    # --- Графа 48: отсрочка платежей ---
    _sub(root, "PaymentDeferral", decl.get("payment_deferral"))

    # --- Графа 49: реквизиты склада ---
    _sub(root, "WarehouseRequisites", decl.get("warehouse_requisites"))

    # --- Графа 51: органы транзита ---
    _sub(root, "TransitOffices", decl.get("transit_offices"))

    # --- Графа 53: орган назначения ---
    _sub(root, "DestinationOffice", decl.get("destination_office_code"))

    # --- Customs office ---
    _sub(root, "CustomsOffice", decl.get("customs_office_code"))

    # --- Графа 54: место и дата ---
    _sub(root, "PlaceAndDate", decl.get("place_and_date"))

    # Serialize
    xml_bytes: bytes = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    )
    return xml_bytes.decode("UTF-8")
