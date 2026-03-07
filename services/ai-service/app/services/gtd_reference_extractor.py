"""
Extract reference data from final GTD declarations.

Used for golden dataset regression: GTD PDFs are treated as reference output,
not as input documents for parse-smart.
"""
from __future__ import annotations

import json
import re
import structlog

from app.services.llm_client import get_llm_client, get_model
from app.services.ocr_service import extract_text

logger = structlog.get_logger()


def _strip_code_fences(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 2:
            cleaned = parts[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return cleaned.strip()


def _normalize_hs(value: str | None) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) < 6:
        return ""
    return digits[:10].ljust(10, "0")


def _normalize_header(header: dict | None) -> dict:
    src = header or {}
    normalized = {
        "type_code": (src.get("type_code") or "").strip() or None,
        "country_dispatch": (src.get("country_dispatch") or "").strip()[:2].upper() or None,
        "country_destination": (src.get("country_destination") or "").strip()[:2].upper() or None,
        "currency": (src.get("currency") or "").strip()[:3].upper() or None,
        "transport_type": (src.get("transport_type") or "").strip()[:2] or None,
        "customs_office_code": re.sub(r"\D", "", str(src.get("customs_office_code") or ""))[:8] or None,
        "invoice_number": (src.get("invoice_number") or "").strip() or None,
        "contract_number": (src.get("contract_number") or "").strip() or None,
    }
    amount = src.get("total_amount")
    try:
        normalized["total_amount"] = float(amount) if amount not in (None, "") else None
    except (TypeError, ValueError):
        normalized["total_amount"] = None
    return normalized


def _normalize_items(items: list[dict] | None) -> list[dict]:
    result: list[dict] = []
    for idx, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        hs_code = _normalize_hs(item.get("hs_code"))
        description = (item.get("description") or "").strip()
        if not hs_code and not description:
            continue
        line_no = item.get("line_no") or idx + 1
        try:
            line_no = int(line_no)
        except (TypeError, ValueError):
            line_no = idx + 1
        result.append({
            "line_no": line_no,
            "hs_code": hs_code,
            "description": description,
        })
    result.sort(key=lambda item: item.get("line_no") or 0)
    return result


def extract_gtd_reference(file_bytes: bytes, filename: str) -> dict:
    text = extract_text(file_bytes, filename)
    if not text:
        logger.warning("gtd_reference_no_text", filename=filename)
        return {"filename": filename, "header": {}, "items": [], "text_chars": 0}

    client = get_llm_client(operation="extract_gtd_reference")
    response = client.chat.completions.create(
        model=get_model(),
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты таможенный эксперт. Извлеки из текста готовой декларации на товары (ГТД) "
                    "эталонные данные для regression-проверки. Верни ТОЛЬКО валидный JSON-объект формата:\n"
                    "{"
                    "\"header\": {"
                    "\"type_code\": \"IM40\", "
                    "\"country_dispatch\": \"CN\", "
                    "\"country_destination\": \"RU\", "
                    "\"currency\": \"USD\", "
                    "\"total_amount\": 12345.67, "
                    "\"transport_type\": \"40\", "
                    "\"customs_office_code\": \"10005030\", "
                    "\"invoice_number\": \"...\", "
                    "\"contract_number\": \"...\""
                    "}, "
                    "\"items\": ["
                    "{\"line_no\": 1, \"hs_code\": \"XXXXXXXXXX\", \"description\": \"...\"}"
                    "]"
                    "}.\n"
                    "Если поле отсутствует в ГТД — верни null. "
                    "Описание товара бери максимально полное из графы 31 и приложений, код — из графы 33."
                ),
            },
            {"role": "user", "content": text[:18000]},
        ],
        temperature=0,
        max_tokens=4000,
        response_format={"type": "json_object"},
    )

    raw = _strip_code_fences(response.choices[0].message.content)
    data = json.loads(raw)

    header = _normalize_header(data.get("header") if isinstance(data, dict) else {})
    items = _normalize_items(data.get("items") if isinstance(data, dict) else [])

    logger.info(
        "gtd_reference_extracted",
        filename=filename,
        items_count=len(items),
        customs_office_code=header.get("customs_office_code"),
        currency=header.get("currency"),
    )

    return {
        "filename": filename,
        "header": header,
        "items": items,
        "text_chars": len(text),
    }
