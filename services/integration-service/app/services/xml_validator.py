"""Validate a DeclarationOnGoods XML string against business rules."""

from __future__ import annotations

import re

from lxml import etree

NS = "urn:customs.ru:Information:CustomsDocuments:DeclarationOnGoods:5.24.0"
_NS = f"{{{NS}}}"


def _find(root: etree._Element, path: str) -> etree._Element | None:
    """Shortcut for ``root.find()`` with the default namespace."""
    return root.find(path, namespaces={"d": NS})


def _findall(root: etree._Element, path: str) -> list[etree._Element]:
    return root.findall(path, namespaces={"d": NS})


def _text(el: etree._Element | None) -> str | None:
    if el is None:
        return None
    return (el.text or "").strip() or None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_declaration_xml(xml_string: str) -> dict:
    """Validate the XML and return ``{valid, errors, warnings}``.

    Checks:
    - Required: DeclarationKind, at least one Item, each Item has HSCode
      (10 digits) and GoodsDescription, CurrencyCode, Consignor, Consignee,
      TotalInvoiceValue > 0.
    - Warnings: missing ExchangeRate, TotalGrossWeight, TotalNetWeight.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Parse XML ---
    try:
        root = etree.fromstring(xml_string.encode("UTF-8") if isinstance(xml_string, str) else xml_string)
    except etree.XMLSyntaxError as exc:
        return {"valid": False, "errors": [f"XML syntax error: {exc}"], "warnings": []}

    # --- DeclarationKind ---
    dk = _text(_find(root, "d:DeclarationKind"))
    if not dk:
        errors.append("DeclarationKind is missing or empty")

    # --- Consignor ---
    consignor = _find(root, "d:Consignor")
    if consignor is None:
        errors.append("Consignor (графа 2) is missing")

    # --- Consignee ---
    consignee = _find(root, "d:Consignee")
    if consignee is None:
        errors.append("Consignee (графа 8) is missing")

    # --- CurrencyCode ---
    currency_el = _find(root, "d:CurrencyInfo/d:CurrencyCode")
    if not _text(currency_el):
        errors.append("CurrencyCode is missing or empty")

    # --- TotalInvoiceValue > 0 ---
    tiv_el = _find(root, "d:CurrencyInfo/d:TotalInvoiceValue")
    tiv_text = _text(tiv_el)
    if not tiv_text:
        errors.append("TotalInvoiceValue is missing or empty")
    else:
        try:
            tiv_val = float(tiv_text)
            if tiv_val <= 0:
                errors.append(f"TotalInvoiceValue must be > 0, got {tiv_val}")
        except ValueError:
            errors.append(f"TotalInvoiceValue is not a valid number: {tiv_text}")

    # --- Items ---
    items_container = _find(root, "d:DeclarationItems")
    item_els = _findall(root, "d:DeclarationItems/d:Item") if items_container is not None else []

    if not item_els:
        errors.append("DeclarationItems must contain at least one Item")
    else:
        for idx, item_el in enumerate(item_els, start=1):
            item_num = item_el.get("itemNumber", str(idx))

            # HSCode — must be 10 digits
            hs = _text(item_el.find(f"{_NS}HSCode"))
            if not hs:
                errors.append(f"Item {item_num}: HSCode is missing")
            elif not re.fullmatch(r"\d{10}", hs):
                errors.append(f"Item {item_num}: HSCode must be exactly 10 digits, got '{hs}'")

            # GoodsDescription
            desc = _text(item_el.find(f"{_NS}GoodsDescription"))
            if not desc:
                errors.append(f"Item {item_num}: GoodsDescription is missing or empty")

    # --- ContainerIndicator (графа 19): must be "0" or "1" ---
    ci_el = _find(root, "d:TransportInfo/d:ContainerIndicator")
    ci_text = _text(ci_el)
    if ci_text and ci_text not in ("0", "1"):
        errors.append(f"ContainerIndicator (графа 19) must be '0' or '1', got '{ci_text}'")

    # --- DealNatureCode + DealSpecificsCode (графа 24) ---
    dnc = _text(_find(root, "d:FinancialRegulatory/d:DealNatureCode"))
    dsc = _text(_find(root, "d:FinancialRegulatory/d:DealSpecificsCode"))
    if dnc and not dsc:
        warnings.append("DealSpecificsCode (графа 24.2) is missing — should be filled alongside DealNatureCode")

    # --- Per-item: StatisticalValueUSD ---
    if item_els:
        for idx, item_el in enumerate(item_els, start=1):
            item_num = item_el.get("itemNumber", str(idx))
            sv = _text(item_el.find(f"{_NS}StatisticalValueUSD"))
            if not sv:
                warnings.append(f"Item {item_num}: StatisticalValueUSD (графа 46) is missing")
            elif sv:
                try:
                    sv_val = float(sv)
                    if sv_val <= 0:
                        warnings.append(f"Item {item_num}: StatisticalValueUSD should be > 0, got {sv_val}")
                except ValueError:
                    warnings.append(f"Item {item_num}: StatisticalValueUSD is not a valid number: {sv}")

    # --- Warnings for optional fields ---
    er_el = _find(root, "d:CurrencyInfo/d:ExchangeRate")
    if not _text(er_el):
        warnings.append("ExchangeRate is missing — will default to 1.0 at submission")

    gw_el = _find(root, "d:ConsignmentInfo/d:TotalGrossWeight")
    if not _text(gw_el):
        warnings.append("TotalGrossWeight is missing")

    nw_el = _find(root, "d:ConsignmentInfo/d:TotalNetWeight")
    if not _text(nw_el):
        warnings.append("TotalNetWeight is missing")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
