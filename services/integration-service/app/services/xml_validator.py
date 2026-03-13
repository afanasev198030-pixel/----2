"""Two-level XML validation for ESADout_CU (FTS format 5.24.0).

L1 — XSD schema validation (structural correctness) — skipped until XSD available.
L2 — Business rules (logical checks on top of valid XML).
"""

from __future__ import annotations

import re
from typing import Optional

from lxml import etree
import structlog

logger = structlog.get_logger()

NS_ESAD = "urn:customs.ru:Information:CustomsDocuments:ESADout_CU:5.24.0"
NS_CAT = "urn:customs.ru:CommonAggregateTypes:5.24.0"
NS_CATESAD = "urn:customs.ru:CUESADCommonAggregateTypesCust:5.24.0"
NS_RUSCAT = "urn:customs.ru:RUSCommonAggregateTypes:5.24.0"
NS_RUDECL = "urn:customs.ru:RUDeclCommonAggregateTypesCust:5.24.0"

_NSMAP = {
    "esad": NS_ESAD,
    "cat_ru": NS_CAT,
    "catESAD_cu": NS_CATESAD,
    "RUScat_ru": NS_RUSCAT,
    "RUDECLcat": NS_RUDECL,
}


def _text(root: etree._Element, xpath: str) -> str | None:
    els = root.xpath(xpath, namespaces=_NSMAP)
    if not els:
        return None
    t = els[0].text if hasattr(els[0], "text") else str(els[0])
    return (t or "").strip() or None


def validate_declaration_xml(xml_string: str) -> dict:
    """Validate ESADout_CU XML and return ``{valid, errors, warnings, xsd_valid}``."""
    errors: list[str] = []
    warnings: list[str] = []
    xsd_valid: bool | None = None

    try:
        root = etree.fromstring(
            xml_string.encode("UTF-8") if isinstance(xml_string, str) else xml_string
        )
    except etree.XMLSyntaxError as exc:
        return {
            "valid": False,
            "errors": [f"XML syntax error: {exc}"],
            "warnings": [],
            "xsd_valid": False,
        }

    warnings.append("XSD schema for ESADout_CU not available — structural validation skipped")

    # --- L2: Business rules ---
    local_name = etree.QName(root).localname
    if local_name != "ESADout_CU":
        errors.append(f"Root element must be ESADout_CU, got '{local_name}'")

    procedure = _text(root, "esad:CustomsProcedure")
    if not procedure:
        errors.append("CustomsProcedure (ИМ/ЭК/ТР) is missing")

    mode = _text(root, "esad:CustomsModeCode")
    if not mode:
        errors.append("CustomsModeCode is missing")

    shipment = root.xpath("esad:ESADout_CUGoodsShipment", namespaces=_NSMAP)
    if not shipment:
        errors.append("ESADout_CUGoodsShipment is missing")
        return {"valid": False, "errors": errors, "warnings": warnings, "xsd_valid": xsd_valid}

    gs = shipment[0]

    declarant = gs.xpath("esad:ESADout_CUDeclarant", namespaces=_NSMAP)
    if not declarant:
        errors.append("ESADout_CUDeclarant (графа 14) is missing")
    else:
        org_name = _text(declarant[0], "cat_ru:OrganizationName")
        if not org_name:
            warnings.append("Declarant: OrganizationName is missing")
        inn = _text(declarant[0], ".//cat_ru:INN")
        if not inn:
            warnings.append("Declarant: INN is missing")

    items = gs.xpath("esad:ESADout_CUGoods", namespaces=_NSMAP)
    if not items:
        errors.append("At least one ESADout_CUGoods is required")
    else:
        for idx, item_el in enumerate(items, start=1):
            ordinal = _text(item_el, "catESAD_cu:GoodsNumeric") or str(idx)

            hs = _text(item_el, "catESAD_cu:GoodsTNVEDCode")
            if not hs:
                errors.append(f"Item {ordinal}: GoodsTNVEDCode (ТН ВЭД) is missing")
            elif not re.fullmatch(r"\d{10}", hs):
                errors.append(f"Item {ordinal}: GoodsTNVEDCode must be 10 digits, got '{hs}'")

            desc = _text(item_el, "catESAD_cu:GoodsDescription")
            if not desc:
                errors.append(f"Item {ordinal}: GoodsDescription is missing")

    container = _text(gs, ".//catESAD_cu:ContainerIndicator")
    if container and container not in ("0", "1"):
        errors.append(f"ContainerIndicator must be '0' or '1', got '{container}'")

    total_cost = _text(gs, "catESAD_cu:TotalCustCost")
    if total_cost:
        try:
            if float(total_cost) <= 0:
                errors.append(f"TotalCustCost must be > 0, got {total_cost}")
        except ValueError:
            errors.append(f"TotalCustCost is not a valid number: {total_cost}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "xsd_valid": xsd_valid,
    }
