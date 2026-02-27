"""Pydantic schemas for validating LLM JSON responses."""
from typing import Optional, Any

from pydantic import BaseModel, field_validator


class LLMItemResponse(BaseModel):
    """Single item from LLM invoice/specification extraction."""
    description: str = ""
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    hs_code: Optional[str] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    country_origin: Optional[str] = None

    @field_validator("quantity", "unit_price", "line_total", "gross_weight", "net_weight", mode="before")
    @classmethod
    def coerce_float(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                cleaned = v.replace(",", ".").strip()
                return float(cleaned) if cleaned else None
            except (ValueError, TypeError):
                return None
        return None


class LLMInvoiceResponse(BaseModel):
    """LLM response for invoice enrichment."""
    invoice_number: Optional[str] = None
    seller_name: Optional[str] = None
    buyer_name: Optional[str] = None
    country_origin: Optional[str] = None
    total_amount: Optional[float] = None
    items: list[LLMItemResponse] = []

    @field_validator("total_amount", mode="before")
    @classmethod
    def coerce_total(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                cleaned = v.replace(",", ".").strip()
                return float(cleaned) if cleaned else None
            except (ValueError, TypeError):
                return None
        return None

    @field_validator("items", mode="before")
    @classmethod
    def coerce_items(cls, v: Any) -> list:
        if not v:
            return []
        if not isinstance(v, list):
            return []
        out = []
        for x in v:
            if isinstance(x, LLMItemResponse):
                out.append(x)
            elif isinstance(x, dict):
                try:
                    out.append(LLMItemResponse.model_validate(x))
                except Exception:
                    out.append(LLMItemResponse(description=(x.get("description") or x.get("description_raw") or "")[:500]))
            else:
                continue
        return out


class LLMBatchParseResponse(BaseModel):
    """LLM batch parse response (contract + specification + tech_description + transport)."""
    contract: Optional[dict] = None
    specification: Optional[dict] = None
    tech_description: Optional[dict] = None
    transport_invoice: Optional[dict] = None

    model_config = {"extra": "allow"}
