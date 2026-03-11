"""Two-level XML validation for EEC GoodsDeclaration (R.055).

L1 — XSD schema validation (structural correctness).
L2 — Business rules (logical checks on top of valid XML).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from lxml import etree
import structlog

logger = structlog.get_logger()

NS_GD = "urn:EEC:R:055:GoodsDeclaration:v1.1.0"
NS_CACDO = "urn:EEC:M:CA:ComplexDataObjects:v1.10.3"
NS_CASDO = "urn:EEC:M:CA:SimpleDataObjects:v1.10.3"
NS_CSDO = "urn:EEC:M:SimpleDataObjects:v0.4.16"

_NSMAP = {
    "gd": NS_GD,
    "cacdo": NS_CACDO,
    "casdo": NS_CASDO,
    "csdo": NS_CSDO,
}

XSD_DIR = Path(__file__).parent.parent.parent / "xsd" / "eec_5.27.0"

_xsd_schema: Optional[etree.XMLSchema] = None


def _load_xsd_schema() -> etree.XMLSchema | None:
    """Load XSD schema with dependency resolution. Returns None if files missing."""
    xsd_path = XSD_DIR / "EEC_GoodsDeclaration.xsd"
    if not xsd_path.exists():
        logger.warning("xsd_schema_not_found", path=str(xsd_path))
        return None
    try:
        schema_doc = etree.parse(str(xsd_path))
        schema = etree.XMLSchema(schema_doc)
        logger.info("xsd_schema_loaded", path=str(xsd_path))
        return schema
    except etree.XMLSchemaParseError as exc:
        logger.error("xsd_schema_parse_error", error=str(exc))
        return None


def _get_schema() -> etree.XMLSchema | None:
    global _xsd_schema
    if _xsd_schema is None:
        _xsd_schema = _load_xsd_schema()
    return _xsd_schema


def _text(root: etree._Element, xpath: str) -> str | None:
    els = root.xpath(xpath, namespaces=_NSMAP)
    if not els:
        return None
    t = els[0].text if hasattr(els[0], "text") else str(els[0])
    return (t or "").strip() or None


def validate_declaration_xml(xml_string: str) -> dict:
    """Validate XML and return ``{valid, errors, warnings, xsd_valid}``.

    Runs L1 (XSD) validation first, then L2 (business rules) regardless.
    """
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

    # --- L1: XSD validation ---
    schema = _get_schema()
    if schema is not None:
        xsd_valid = schema.validate(root)
        if not xsd_valid:
            for err in schema.error_log:
                errors.append(f"XSD: {err.message} (line {err.line})")
    else:
        warnings.append("XSD schema not available — structural validation skipped")

    # --- L2: Business rules ---
    dk = _text(root, ".//casdo:DeclarationKindCode")
    if not dk:
        errors.append("DeclarationKindCode is missing or empty")

    declarant = root.xpath(".//cacdo:DeclarantDetails", namespaces=_NSMAP)
    if not declarant:
        errors.append("DeclarantDetails (графа 14) is missing")
    else:
        inn = _text(declarant[0], ".//csdo:INN")
        if not inn:
            warnings.append("DeclarantDetails: INN is missing")

    shipment = root.xpath(".//cacdo:GDGoodsShipmentDetails", namespaces=_NSMAP)
    if not shipment:
        errors.append("GDGoodsShipmentDetails is missing")
    else:
        items = shipment[0].xpath("cacdo:GDGoodsItemDetails", namespaces=_NSMAP)
        if not items:
            errors.append("At least one GDGoodsItemDetails is required")
        else:
            for idx, item_el in enumerate(items, start=1):
                ordinal = _text(item_el, "casdo:ConsignmentItemOrdinal") or str(idx)

                hs = _text(item_el, "csdo:CommodityCode")
                if not hs:
                    errors.append(f"Item {ordinal}: CommodityCode (ТН ВЭД) is missing")
                elif not re.fullmatch(r"\d{10}", hs):
                    errors.append(f"Item {ordinal}: CommodityCode must be 10 digits, got '{hs}'")

                desc = item_el.xpath("casdo:GoodsDescriptionText", namespaces=_NSMAP)
                if not desc:
                    errors.append(f"Item {ordinal}: GoodsDescriptionText is missing")

        container = _text(shipment[0], ".//casdo:ContainerIndicator")
        if container and container not in ("0", "1"):
            errors.append(f"ContainerIndicator must be '0' or '1', got '{container}'")

        value = _text(shipment[0], "casdo:CAValueAmount")
        if value:
            try:
                if float(value) <= 0:
                    errors.append(f"CAValueAmount (total invoice value) must be > 0, got {value}")
            except ValueError:
                errors.append(f"CAValueAmount is not a valid number: {value}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "xsd_valid": xsd_valid,
    }
