"""
Classifier cache — loads EAEU classifiers from core-api and provides
deterministic lookup / validation without LLM calls.

Usage:
    from app.services.classifier_cache import get_cache
    cache = get_cache()
    cache.validate_code("currency", "USD")      # True
    cache.lookup_code("country", "Китай")        # "CN"
    cache.get_table("transport_type")            # [{"code":"10","name_ru":"Морской"}, ...]
    cache.format_for_prompt("transport_type")    # "10 — Морской | 20 — Железнодорожный | ..."
"""
import time
from typing import Optional

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger()

_CLASSIFIER_TYPES = (
    "country", "currency", "transport_type", "incoterms",
    "procedure", "deal_nature", "mos_method", "doc_type",
    "customs_post",
)

_TTL_SECONDS = 3600


class ClassifierCache:
    def __init__(self) -> None:
        self._data: dict[str, list[dict]] = {}
        self._code_sets: dict[str, set[str]] = {}
        self._name_to_code: dict[str, dict[str, str]] = {}
        self._loaded_at: float = 0.0

    @property
    def is_loaded(self) -> bool:
        return self._loaded_at > 0

    @property
    def is_stale(self) -> bool:
        return time.time() - self._loaded_at > _TTL_SECONDS

    def load(self) -> None:
        settings = get_settings()
        url = f"{settings.CORE_API_URL}/api/v1/classifiers/internal"
        types_param = ",".join(_CLASSIFIER_TYPES)

        try:
            resp = httpx.get(url, params={"classifier_type": types_param}, timeout=15)
            resp.raise_for_status()
            grouped: dict[str, list[dict]] = resp.json()
        except Exception as e:
            logger.warning("classifier_cache_load_failed", error=str(e)[:200])
            if self._data:
                logger.info("classifier_cache_using_stale")
                return
            self._load_fallback_from_seeds()
            return

        self._data = grouped
        self._rebuild_indices()
        self._loaded_at = time.time()
        total = sum(len(v) for v in grouped.values())
        logger.info(
            "classifier_cache_loaded",
            types=list(grouped.keys()),
            total_entries=total,
        )

    def _load_fallback_from_seeds(self) -> None:
        """Fallback: load seed JSON files shipped with ai-service."""
        import json
        from pathlib import Path

        seeds_dir = Path(__file__).parent.parent.parent.parent.parent / "core-api" / "app" / "seeds"
        if not seeds_dir.exists():
            seeds_dir = Path("/app/seeds_fallback")

        _FILE_MAP = {
            "country": "countries.json",
            "currency": "currencies.json",
            "transport_type": "transport_types.json",
            "incoterms": "incoterms.json",
            "procedure": "procedures.json",
            "deal_nature": "deal_nature.json",
            "mos_method": "mos_methods.json",
            "doc_type": "doc_type.json",
            "customs_post": "customs_posts.json",
        }

        for ctype, fname in _FILE_MAP.items():
            path = seeds_dir / fname
            if path.exists():
                try:
                    with open(path) as f:
                        self._data[ctype] = json.load(f)
                except Exception:
                    pass

        if self._data:
            self._rebuild_indices()
            self._loaded_at = time.time()
            logger.info("classifier_cache_fallback_seeds", types=list(self._data.keys()))

    def _rebuild_indices(self) -> None:
        self._code_sets.clear()
        self._name_to_code.clear()

        for ctype, items in self._data.items():
            codes: set[str] = set()
            name_map: dict[str, str] = {}
            for item in items:
                code = item.get("code", "")
                codes.add(code)
                codes.add(code.upper())
                codes.add(code.lower())

                for name_field in ("name_ru", "name_en"):
                    name = (item.get(name_field) or "").strip()
                    if name:
                        name_map[name.lower()] = code

            self._code_sets[ctype] = codes
            self._name_to_code[ctype] = name_map

    def _ensure_loaded(self) -> None:
        if not self.is_loaded or self.is_stale:
            self.load()

    def get_table(self, classifier_type: str) -> list[dict]:
        self._ensure_loaded()
        return self._data.get(classifier_type, [])

    def validate_code(self, classifier_type: str, code: str) -> bool:
        self._ensure_loaded()
        codes = self._code_sets.get(classifier_type)
        if not codes:
            return True
        return code in codes or code.upper() in codes

    def lookup_code(self, classifier_type: str, value: str) -> Optional[str]:
        """Find classifier code by name or code value.

        Tries exact code match first, then name_ru/name_en lookup.
        """
        self._ensure_loaded()
        if not value:
            return None

        codes = self._code_sets.get(classifier_type)
        if codes and (value in codes or value.upper() in codes):
            return value.upper() if value.upper() in codes else value

        name_map = self._name_to_code.get(classifier_type, {})
        return name_map.get(value.lower())

    def format_for_prompt(self, classifier_type: str) -> str:
        """Format classifier as a compact one-line string for LLM prompt."""
        items = self.get_table(classifier_type)
        if not items:
            return ""
        return " | ".join(
            f"{item['code']} — {item.get('name_ru', '')}"
            for item in items
        )

    def get_country_name_map(self) -> dict[str, str]:
        """Return {lowercase_name: ISO_code} for all country names (ru + en)."""
        self._ensure_loaded()
        result: dict[str, str] = {}
        for item in self._data.get("country", []):
            code = item["code"]
            for field in ("name_ru", "name_en"):
                name = (item.get(field) or "").strip()
                if name:
                    result[name.lower()] = code
        return result

    def get_currency_name_map(self) -> dict[str, str]:
        """Return {lowercase_name: ISO_code} for all currency names."""
        self._ensure_loaded()
        result: dict[str, str] = {}
        for item in self._data.get("currency", []):
            code = item["code"]
            for field in ("name_ru", "name_en"):
                name = (item.get(field) or "").strip()
                if name:
                    result[name.lower()] = code
        return result


_cache_instance: Optional[ClassifierCache] = None


def get_cache() -> ClassifierCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ClassifierCache()
    return _cache_instance
