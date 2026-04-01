"""
Shared parsing utilities used across ai-service modules.

Consolidates duplicated helpers (_safe_float, _normalize_hs_code, etc.)
into a single canonical implementation.
"""
import re
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


def safe_float(value: Any) -> Optional[float]:
    """Convert value to float, handling international number formats.

    Covers:
    - Non-breaking spaces (\\xa0) and regular spaces as thousands separators
    - Comma as decimal separator (European: "1.234,56" → 1234.56)
    - Comma as thousands separator (US: "1,234.56" → 1234.56)
    - Embedded non-numeric chars like "2pcs", "N/A" → None
    - int/float passthrough
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().replace("\xa0", " ").replace(" ", "")
    if not s:
        return None

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")

    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s in (".", "-", "-."):
        return None

    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def normalize_hs_code(raw: Any) -> str:
    """Normalize HS code to 10 digits, validate first 2 digits are 01-97."""
    code = re.sub(r"\D", "", str(raw or ""))
    if len(code) < 6:
        return ""
    if len(code) < 10:
        code = code.ljust(10, "0")
    else:
        code = code[:10]
    try:
        first2 = int(code[:2])
        if first2 < 1 or first2 > 97:
            return ""
    except ValueError:
        return ""
    return code


def to_dict(obj: Any) -> dict:
    """Pydantic model or dict → dict. Returns {} for None."""
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return {}


def count_good_items(items: list) -> int:
    """Count items with meaningful descriptions (not 'Item N', not empty)."""
    good = 0
    for item in (items or []):
        desc = (item.get("description") or item.get("commercial_name") or "").strip()
        if desc and not re.match(r'^item\s*\d+$', desc.strip(), re.I):
            good += 1
    return good


def invoice_score(inv: dict) -> tuple:
    """Score invoice quality for choosing the best one from several.

    Priority (descending): good item count, has seller+buyer, confidence, total items.
    """
    items = inv.get("items") or []
    good = count_good_items(items)
    has_parties = 1 if (inv.get("seller") and inv.get("buyer")) else 0
    conf = inv.get("confidence") or 0.0
    total = len(items)
    return (good, has_parties, conf, total)


_VISION_RETRY_FIELDS: dict[str, list[str]] = {
    "invoice": ["seller", "buyer", "invoice_number"],
    "contract": ["contract_number"],
    "specification": ["items"],
    "packing_list": ["items"],
    "transport_doc": ["transport_number"],
}


def check_needs_vision_retry(doc_type: str, extracted: dict) -> list[str]:
    """Return list of critical fields that are empty after LLM extraction."""
    required = _VISION_RETRY_FIELDS.get(doc_type, [])
    missing = []
    for f in required:
        val = extracted.get(f)
        if not val:
            missing.append(f)
        elif isinstance(val, dict) and not any(val.values()):
            missing.append(f)
        elif isinstance(val, list) and len(val) == 0:
            missing.append(f)
    return missing
