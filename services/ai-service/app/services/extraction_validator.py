"""
Post-extraction validation for LLM parser output.

Checks required fields per document type, validates data formats,
and returns a list of issues that can trigger a self-correction retry.
"""
import re
from typing import Optional

import structlog

logger = structlog.get_logger()

_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{2}\.\d{2}\.\d{4}$")
_INN_RE = re.compile(r"^\d{10}(\d{2})?$")

_VALID_INCOTERMS = {
    "EXW", "FCA", "FAS", "FOB", "CFR", "CIF",
    "CPT", "CIP", "DAP", "DPU", "DDP",
}

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "invoice": ["invoice_number", "currency", "total_amount", "items"],
    "contract": ["contract_number", "contract_date", "currency", "seller", "buyer"],
    "packing_list": ["items"],
    "specification": ["items"],
    "transport_doc": ["transport_type"],
    "transport_invoice": ["freight_amount", "freight_currency"],
    "origin_certificate": ["certificate_type", "country_origin"],
    "payment_order": ["payment_number", "amount", "currency"],
    "application_statement": ["departure_country"],
    "svh_doc": ["svh_number"],
}

_CRITICAL_FIELDS: dict[str, list[str]] = {
    "invoice": ["items", "total_amount"],
    "contract": ["contract_number", "seller", "buyer"],
    "packing_list": ["items"],
    "specification": ["items"],
    "payment_order": ["payment_number", "amount"],
}


class ValidationIssue:
    __slots__ = ("field", "severity", "message")

    def __init__(self, field: str, severity: str, message: str):
        self.field = field
        self.severity = severity
        self.message = message

    def to_dict(self) -> dict:
        return {"field": self.field, "severity": self.severity, "message": self.message}


def validate_extraction(doc_type: str, extracted: dict) -> list[ValidationIssue]:
    """Validate extracted data against required fields and format rules.

    Returns list of issues. Empty list = all checks passed.
    Severity levels: "critical" (triggers retry), "warning" (logged only).
    """
    issues: list[ValidationIssue] = []

    if not extracted:
        issues.append(ValidationIssue("extracted", "critical", "Extraction returned empty dict"))
        return issues

    required = _REQUIRED_FIELDS.get(doc_type, [])
    critical = _CRITICAL_FIELDS.get(doc_type, [])

    for field in required:
        val = extracted.get(field)
        if val is None or val == "" or val == []:
            severity = "critical" if field in critical else "warning"
            issues.append(ValidationIssue(field, severity, f"Missing required field: {field}"))

    _validate_country_codes(extracted, issues)
    _validate_currency(extracted, issues)
    _validate_dates(extracted, issues)
    _validate_items(doc_type, extracted, issues)
    _validate_amounts(extracted, issues)
    _validate_incoterms(extracted, issues)
    _validate_inn(extracted, issues)

    return issues


def has_critical_issues(issues: list[ValidationIssue]) -> bool:
    return any(i.severity == "critical" for i in issues)


def build_correction_prompt(issues: list[ValidationIssue]) -> str:
    """Build a targeted correction prompt from validation issues."""
    lines = ["The previous extraction had the following issues. Please fix them:"]
    for i, issue in enumerate(issues, 1):
        lines.append(f"{i}. [{issue.severity}] {issue.field}: {issue.message}")
    lines.append("\nReturn the corrected full JSON with the same structure.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Field-specific validators
# ---------------------------------------------------------------------------

def _validate_country_codes(data: dict, issues: list[ValidationIssue]) -> None:
    for key in ("country_origin", "country_dispatch", "country_destination",
                "departure_country", "issuing_country"):
        val = data.get(key)
        if val and isinstance(val, str) and not _COUNTRY_RE.match(val.upper()):
            issues.append(ValidationIssue(key, "warning", f"Invalid country code: '{val}'"))

    for party_key in ("seller", "buyer", "declarant", "receiver",
                      "financial_party", "shipper"):
        party = data.get(party_key)
        if isinstance(party, dict):
            cc = party.get("country_code")
            if cc and isinstance(cc, str) and not _COUNTRY_RE.match(cc.upper()):
                issues.append(ValidationIssue(
                    f"{party_key}.country_code", "warning", f"Invalid country code: '{cc}'"))


def _validate_currency(data: dict, issues: list[ValidationIssue]) -> None:
    for key in ("currency", "freight_currency"):
        val = data.get(key)
        if val and isinstance(val, str) and not _CURRENCY_RE.match(val.upper()):
            issues.append(ValidationIssue(key, "warning", f"Invalid currency code: '{val}'"))


def _validate_dates(data: dict, issues: list[ValidationIssue]) -> None:
    for key in ("invoice_date", "contract_date", "certificate_date",
                "doc_date", "date", "acceptance_date"):
        val = data.get(key)
        if val and isinstance(val, str) and not _DATE_RE.match(val):
            issues.append(ValidationIssue(key, "warning", f"Unexpected date format: '{val}'"))


def _validate_incoterms(data: dict, issues: list[ValidationIssue]) -> None:
    val = data.get("incoterms")
    if val and isinstance(val, str):
        code = val.split()[0].upper()
        if code not in _VALID_INCOTERMS:
            issues.append(ValidationIssue(
                "incoterms", "warning",
                f"Unknown Incoterms code: '{val}'. "
                f"Valid: {', '.join(sorted(_VALID_INCOTERMS))}"))


def _validate_inn(data: dict, issues: list[ValidationIssue]) -> None:
    for party_key in ("seller", "buyer", "declarant", "receiver", "financial_party"):
        party = data.get(party_key)
        if isinstance(party, dict):
            inn = party.get("inn")
            if inn and isinstance(inn, str) and not _INN_RE.match(inn):
                issues.append(ValidationIssue(
                    f"{party_key}.inn", "warning",
                    f"Invalid INN format (expected 10 or 12 digits): '{inn}'"))


def _validate_items(doc_type: str, data: dict, issues: list[ValidationIssue]) -> None:
    items = data.get("items")
    if not isinstance(items, list):
        return

    if len(items) == 0 and doc_type in ("invoice", "packing_list", "specification"):
        issues.append(ValidationIssue("items", "critical", "Items array is empty"))
        return

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        desc = item.get("description")
        if not desc or (isinstance(desc, str) and len(desc.strip()) < 2):
            issues.append(ValidationIssue(
                f"items[{i}].description", "warning", "Missing or empty description"))

        if doc_type == "invoice":
            qty = item.get("quantity")
            price = item.get("unit_price")
            total = item.get("line_total")

            if qty is not None and isinstance(qty, (int, float)) and qty <= 0:
                issues.append(ValidationIssue(
                    f"items[{i}].quantity", "warning", f"Non-positive quantity: {qty}"))
            if price is not None and isinstance(price, (int, float)) and price < 0:
                issues.append(ValidationIssue(
                    f"items[{i}].unit_price", "warning", f"Negative price: {price}"))

            if (qty is not None and price is not None and total is not None
                    and isinstance(qty, (int, float))
                    and isinstance(price, (int, float))
                    and isinstance(total, (int, float))):
                try:
                    expected = float(qty) * float(price)
                    actual = float(total)
                    if actual > 0 and abs(expected - actual) / actual > 0.02:
                        issues.append(ValidationIssue(
                            f"items[{i}].line_total", "warning",
                            f"qty({qty}) * price({price}) = {expected:.2f} "
                            f"differs from line_total({actual:.2f}) by "
                            f"{abs(expected - actual) / actual * 100:.1f}%"))
                except (ValueError, TypeError, ZeroDivisionError):
                    pass


def _validate_amounts(data: dict, issues: list[ValidationIssue]) -> None:
    total = data.get("total_amount")
    items = data.get("items")
    if total is None or not isinstance(items, list) or not items:
        return

    try:
        total_f = float(total)
    except (ValueError, TypeError):
        issues.append(ValidationIssue("total_amount", "warning",
                                      f"total_amount is not a number: {total}"))
        return

    item_sum = 0.0
    all_have_totals = True
    for item in items:
        lt = item.get("line_total")
        if lt is None:
            all_have_totals = False
            break
        try:
            item_sum += float(lt)
        except (ValueError, TypeError):
            all_have_totals = False
            break

    if all_have_totals and total_f > 0:
        diff_pct = abs(item_sum - total_f) / total_f * 100
        if diff_pct > 5:
            issues.append(ValidationIssue(
                "total_amount", "warning",
                f"Sum of line_totals ({item_sum:.2f}) differs from total_amount "
                f"({total_f:.2f}) by {diff_pct:.1f}%"))
