"""
Reference data loader — lookup tables loaded from JSON files at startup.

Data files live in app/data/*.json and are loaded once on first access.
To add a new airport/customs post, edit customs_offices.json — no code change needed.
"""
import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_cache: dict[str, Any] = {}


def _load(filename: str) -> Any:
    if filename in _cache:
        return _cache[filename]
    path = _DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _cache[filename] = data
    logger.info("reference_data_loaded", file=filename, keys=len(data) if isinstance(data, (dict, list)) else 1)
    return data


def get_customs_offices() -> dict:
    """Returns {"by_iata": {...}, "by_awb_prefix": {...}, "default": [...]}."""
    return _load("customs_offices.json")


def get_document_codes() -> dict:
    """Returns {"doc_type_codes": {...}, "transport_doc_codes": {...}, ...}."""
    return _load("document_codes.json")


def get_iata_cities() -> dict:
    """Returns {"HKG": "HONG KONG", ...}."""
    return _load("iata_cities.json")


def get_eu_countries() -> set[str]:
    """Returns {"AT", "BE", "BG", ...}."""
    data = _load("eu_countries.json")
    return set(data)


def lookup_customs_office(iata_code: str | None = None,
                          awb_prefix: str | None = None,
                          transport_type: str | None = None) -> tuple[str, str, str] | None:
    """Resolve customs office by IATA code, AWB prefix, or transport type fallback.

    Returns (office_code, office_name, goods_location) or None.
    """
    offices = get_customs_offices()

    if iata_code:
        entry = offices["by_iata"].get(iata_code.upper().strip())
        if entry:
            return tuple(entry)

    if awb_prefix:
        prefix = awb_prefix.split("-")[0] if "-" in awb_prefix else awb_prefix[:3]
        entry = offices["by_awb_prefix"].get(prefix)
        if entry:
            return tuple(entry)

    if str(transport_type) == "40":
        return tuple(offices["default"])

    return None


def resolve_iata_city(code: str) -> str:
    """Convert IATA airport code to city name. Returns original if not found."""
    cities = get_iata_cities()
    return cities.get(code.strip().upper(), code)
