"""
Deterministic post-LLM normalizer for extracted document data.

Called AFTER LLM extraction, BEFORE validation.  Zero LLM calls.
Converts dates, numbers, country codes, document numbers and incoterms
to standard formats.  Cross-validates item arithmetic (report only, no
fabrication of missing values).
"""
import re
from typing import Any

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Date normalization  →  DD.MM.YYYY
# ---------------------------------------------------------------------------

_MONTH_MAP: dict[str, str] = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "oct": "10", "nov": "11", "dec": "12",
}

_EN_DATE_RE = re.compile(
    r"(?P<month>[A-Za-z]+)\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?,?\s*(?P<year>\d{4})",
)

_ISO_DATE_RE = re.compile(r"^(?P<y>\d{4})[.\-/](?P<m>\d{1,2})[.\-/](?P<d>\d{1,2})$")
_EU_DATE_RE = re.compile(r"^(?P<d>\d{1,2})[.\-/](?P<m>\d{1,2})[.\-/](?P<y>\d{2,4})$")


def _normalize_date(value: Any) -> str | None:
    """Convert various date formats to DD.MM.YYYY."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    m = _EN_DATE_RE.search(s)
    if m:
        month_str = m.group("month").lower()
        mm = _MONTH_MAP.get(month_str)
        if mm:
            dd = m.group("day").zfill(2)
            yyyy = m.group("year")
            return f"{dd}.{mm}.{yyyy}"

    m = _ISO_DATE_RE.match(s)
    if m:
        y, mo, d = m.group("y"), m.group("m").zfill(2), m.group("d").zfill(2)
        return f"{d}.{mo}.{y}"

    m = _EU_DATE_RE.match(s)
    if m:
        d, mo, y = m.group("d").zfill(2), m.group("m").zfill(2), m.group("y")
        if len(y) == 2:
            y = f"20{y}" if int(y) < 70 else f"19{y}"
        return f"{d}.{mo}.{y}"

    return s


# ---------------------------------------------------------------------------
# Number normalization  →  float | None
# ---------------------------------------------------------------------------

def _normalize_number(value: Any) -> float | None:
    """Convert string-formatted numbers to Python float.

    Handles European formats: "1 094 239,00" → 1094239.0
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if not s:
        return None

    s = s.replace("\u00a0", " ").replace("\u2009", " ")

    s = re.sub(r"[^\d,.\-\s]", "", s)
    if not s:
        return None

    comma_pos = s.rfind(",")
    dot_pos = s.rfind(".")

    if comma_pos > dot_pos:
        digits_after_comma = len(s) - comma_pos - 1
        if digits_after_comma <= 4:
            s = s.replace(".", "").replace(" ", "")
            s = s.replace(",", ".", 1)
        else:
            s = s.replace(",", "").replace(" ", "")
    else:
        s = s.replace(",", "").replace(" ", "")

    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Country code normalization  →  2-letter ISO alpha-2
# ---------------------------------------------------------------------------

_COUNTRY_MAP: dict[str, str] = {
    "китай": "CN", "china": "CN", "chn": "CN", "cn": "CN",
    "гонконг": "HK", "hong kong": "HK", "hongkong": "HK", "hkg": "HK", "hk": "HK",
    "россия": "RU", "russia": "RU", "rus": "RU", "ru": "RU",
    "российская федерация": "RU", "russian federation": "RU",
    "германия": "DE", "germany": "DE", "deu": "DE", "de": "DE",
    "турция": "TR", "turkey": "TR", "türkiye": "TR", "tur": "TR", "tr": "TR",
    "италия": "IT", "italy": "IT", "ita": "IT", "it": "IT",
    "франция": "FR", "france": "FR", "fra": "FR", "fr": "FR",
    "индия": "IN", "india": "IN", "ind": "IN",
    "япония": "JP", "japan": "JP", "jpn": "JP", "jp": "JP",
    "корея": "KR", "south korea": "KR", "korea": "KR", "kor": "KR", "kr": "KR",
    "тайвань": "TW", "taiwan": "TW", "twn": "TW", "tw": "TW",
    "вьетнам": "VN", "vietnam": "VN", "vnm": "VN", "vn": "VN",
    "таиланд": "TH", "thailand": "TH", "tha": "TH", "th": "TH",
    "малайзия": "MY", "malaysia": "MY", "mys": "MY", "my": "MY",
    "индонезия": "ID", "indonesia": "ID", "idn": "ID",
    "сша": "US", "usa": "US", "united states": "US",
    "великобритания": "GB", "uk": "GB", "united kingdom": "GB", "gbr": "GB", "gb": "GB",
    "нидерланды": "NL", "netherlands": "NL", "nld": "NL", "nl": "NL",
    "польша": "PL", "poland": "PL", "pol": "PL", "pl": "PL",
    "чехия": "CZ", "czech republic": "CZ", "czechia": "CZ", "cze": "CZ", "cz": "CZ",
    "беларусь": "BY", "belarus": "BY", "blr": "BY", "by": "BY",
    "казахстан": "KZ", "kazakhstan": "KZ", "kaz": "KZ", "kz": "KZ",
    "узбекистан": "UZ", "uzbekistan": "UZ", "uzb": "UZ", "uz": "UZ",
    "бразилия": "BR", "brazil": "BR", "bra": "BR", "br": "BR",
    "австрия": "AT", "austria": "AT", "aut": "AT", "at": "AT",
    "швейцария": "CH", "switzerland": "CH", "che": "CH", "ch": "CH",
    "испания": "ES", "spain": "ES", "esp": "ES", "es": "ES",
    "финляндия": "FI", "finland": "FI", "fin": "FI", "fi": "FI",
    "швеция": "SE", "sweden": "SE", "swe": "SE", "se": "SE",
    "оаэ": "AE", "uae": "AE", "united arab emirates": "AE", "ae": "AE",
    "сингапур": "SG", "singapore": "SG", "sgp": "SG", "sg": "SG",
}

_COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")
_COUNTRY_MAP_EXTENDED = False


def _ensure_country_map_extended() -> None:
    """Extend _COUNTRY_MAP with full classifier data from cache (once)."""
    global _COUNTRY_MAP_EXTENDED
    if _COUNTRY_MAP_EXTENDED:
        return
    try:
        from app.services.classifier_cache import get_cache
        cache = get_cache()
        extra = cache.get_country_name_map()
        if extra:
            for name_lower, code in extra.items():
                _COUNTRY_MAP.setdefault(name_lower, code)
            _COUNTRY_MAP_EXTENDED = True
    except Exception:
        pass


def _normalize_country(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    upper = s.upper()
    if _COUNTRY_CODE_RE.match(upper):
        return upper
    result = _COUNTRY_MAP.get(s.lower())
    if result:
        return result
    _ensure_country_map_extended()
    result = _COUNTRY_MAP.get(s.lower())
    if result:
        return result
    return s if len(s) == 2 else None


# ---------------------------------------------------------------------------
# Document number cleanup (OCR artifact removal)
# ---------------------------------------------------------------------------

_DOC_NUM_PREFIX_RE = re.compile(r"^(?:N&|N°|Nо|No\.?\s*)", re.IGNORECASE)


def _clean_doc_number(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = _DOC_NUM_PREFIX_RE.sub("", s).strip()
    return s or None


# ---------------------------------------------------------------------------
# Incoterms normalization
# ---------------------------------------------------------------------------

_VALID_INCOTERMS = {
    "EXW", "FCA", "FAS", "FOB", "CFR", "CIF",
    "CPT", "CIP", "DAP", "DPU", "DDP",
}


def _normalize_incoterms(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    code = s.split()[0].upper()
    if code in _VALID_INCOTERMS:
        return code
    return s


# ---------------------------------------------------------------------------
# Items cross-validation (report only — no value fabrication)
# ---------------------------------------------------------------------------

def _cross_validate_items(items: list[dict]) -> list[dict]:
    """Check qty * unit_price ≈ line_total.  Log warnings, never fabricate."""
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        qty = item.get("quantity")
        price = item.get("unit_price")
        total = item.get("line_total")

        if isinstance(qty, str):
            qty = _normalize_number(qty)
            if qty is not None:
                item["quantity"] = qty
        if isinstance(price, str):
            price = _normalize_number(price)
            if price is not None:
                item["unit_price"] = price
        if isinstance(total, str):
            total = _normalize_number(total)
            if total is not None:
                item["line_total"] = total

        if qty is not None and price is not None and total is not None:
            try:
                expected = float(qty) * float(price)
                actual = float(total)
                if actual > 0 and abs(expected - actual) / actual > 0.02:
                    logger.warning(
                        "item_arithmetic_mismatch",
                        item_index=i,
                        qty=qty, price=price,
                        expected_total=round(expected, 2),
                        actual_total=actual,
                    )
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        co = item.get("country_origin")
        if co:
            item["country_origin"] = _normalize_country(co)

    return items


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

_DATE_FIELDS = ("invoice_date", "contract_date", "certificate_date", "doc_date", "date",
                "acceptance_date")
_NUMBER_FIELDS = ("total_amount", "total_gross_weight", "total_net_weight",
                  "total_packages", "freight_amount", "amount")
_DOC_NUM_FIELDS = ("invoice_number", "contract_number", "certificate_number",
                   "doc_number", "awb_number", "svh_number", "payment_number")
_COUNTRY_FIELDS = ("country_origin", "departure_country", "issuing_country")
_PARTY_KEYS = ("seller", "buyer", "declarant", "receiver", "financial_party",
               "shipper", "forwarding_agent")


def normalize_extraction(doc_type: str, extracted: dict) -> dict:
    """Deterministic post-processing of LLM-extracted data.

    Normalizes dates, numbers, country codes, document numbers, incoterms.
    Cross-validates item arithmetic (report only, no fabrication).
    Returns modified copy of extracted dict.
    """
    if not extracted:
        return extracted

    data = dict(extracted)

    for f in _DATE_FIELDS:
        if f in data:
            data[f] = _normalize_date(data[f])

    for f in _NUMBER_FIELDS:
        if f in data and data[f] is not None:
            data[f] = _normalize_number(data[f])

    for f in _DOC_NUM_FIELDS:
        if f in data:
            data[f] = _clean_doc_number(data[f])

    for f in _COUNTRY_FIELDS:
        if f in data:
            data[f] = _normalize_country(data[f])

    if "incoterms" in data:
        data["incoterms"] = _normalize_incoterms(data["incoterms"])

    for pk in _PARTY_KEYS:
        party = data.get(pk)
        if isinstance(party, dict):
            cc = party.get("country_code")
            if cc:
                party["country_code"] = _normalize_country(cc)

    items = data.get("items")
    if isinstance(items, list):
        data["items"] = _cross_validate_items(items)

    products = data.get("products")
    if isinstance(products, list):
        pass

    return data
