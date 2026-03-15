"""
Unified LLM document parser.
Single LLM call per document: classifies type AND extracts structured data.
Replaces all regex-based parsers and heuristic type detection.
"""
import json
import re
import time
from typing import Optional

import structlog

from app.services.llm_client import get_llm_client, get_model
from app.services.llm_json import strip_code_fences

logger = structlog.get_logger()

_VALID_DOC_TYPES = {
    "invoice", "contract", "packing_list", "specification",
    "tech_description", "transport_doc", "transport_invoice",
    "application_statement", "payment_order", "reference_gtd",
    "svh_doc", "origin_certificate", "other",
}

_SYSTEM_PROMPT = """You are an expert customs document parser for Russian Federation customs declarations (ДТ).
You receive a document (OCR text) and must:
1. Determine the document type from the allowed list.
2. Extract ALL relevant structured data from the FULL document text.

Return ONLY valid JSON — no markdown, no explanations.

CRITICAL RULES:
- Extract data in the ORIGINAL language of the document. For Russian buyer/declarant names — use Russian.
- Numbers: return as numbers (float/int), not strings. Use dot as decimal separator.
- Dates: return as strings in format YYYY-MM-DD or DD.MM.YYYY (as found in document).
- Country codes: 2-letter ISO 3166-1 alpha-2 (CN, RU, DE, US...).
- Currency codes: 3-letter ISO 4217 (USD, EUR, CNY...).
- Items: include ALL product lines. Do NOT include freight, shipping, insurance, or handling fee lines.
- If a field is not found in the document, use null.
- For seller/buyer: extract name, address, country_code, inn, kpp, ogrn, tax_number when available."""

_USER_PROMPT_TEMPLATE = """Filename: {filename}

Determine the document type and extract data.

ALLOWED DOCUMENT TYPES:
- invoice — commercial invoice for goods (товарный инвойс)
- contract — sale/purchase contract or agreement (контракт/договор)
- packing_list — packing list with weights and packages (упаковочный лист)
- specification — product specification / appendix to contract (спецификация)
- tech_description — technical description of products (техническое описание)
- transport_doc — transport document: AWB, CMR, B/L, waybill (транспортная накладная)
- transport_invoice — freight/shipping invoice (транспортный инвойс, инвойс за перевозку)
- application_statement — forwarding application/order (заявка на перевозку)
- payment_order — payment order (платёжное поручение)
- reference_gtd — reference customs declaration (эталонная ГТД)
- svh_doc — temporary storage warehouse document (документ СВХ)
- origin_certificate — certificate of origin: CT-1, Form A, EUR.1 (сертификат происхождения)
- other — if none of the above match

FIELDS TO EXTRACT BY TYPE:

For "invoice":
  invoice_number, invoice_date, currency (ISO 4217), total_amount (number),
  incoterms, contract_number, country_origin (ISO alpha-2),
  seller: {{name, address, country_code, tax_number}},
  buyer: {{name, address, country_code, tax_number}},
  items: [{{description, quantity, unit, unit_price, line_total, country_origin, hs_code, gross_weight, net_weight}}],
  total_gross_weight, total_net_weight, total_packages

For "contract":
  contract_number, contract_date, currency (ISO 4217), total_amount,
  incoterms, delivery_place, subject, payment_terms,
  is_trilateral (true/false),
  seller: {{name, address, country_code, inn, kpp, ogrn}},
  buyer: {{name, address, country_code, inn, kpp, ogrn}} — buyer name and address MUST be in RUSSIAN,
  receiver: {{name, address, country_code, inn, kpp, ogrn}} (only if trilateral),
  financial_party: {{name, address, country_code, inn, kpp, ogrn}} (only if trilateral)

For "packing_list":
  total_packages, package_type, total_gross_weight, total_net_weight, country_origin,
  items: [{{description, quantity, packages_count, package_type, gross_weight, net_weight, country_origin}}]

For "specification":
  items: [{{description, quantity, unit, unit_price, line_total, country_origin}}],
  total_amount, items_count

For "tech_description":
  products: [{{name, purpose, materials, specifications, application_area, operating_conditions}}]

For "transport_doc":
  awb_number, shipper_name, shipper_address, consignee_name, consignee_address,
  departure_airport, destination_airport, transport_type (10=sea, 30=auto, 40=air),
  flight_number, vehicle_reg_number, vessel_name, vehicle_country_code,
  container_numbers: [string], departure_country (ISO alpha-2)

For "transport_invoice":
  doc_number, doc_date, freight_amount, freight_currency (ISO 4217),
  carrier_name, shipper_name, shipper_address,
  awb_number, transport_type, route

For "application_statement":
  incoterms, delivery_place, forwarding_agent: {{name, address}},
  shipper: {{name, address}}, departure_country

For "payment_order":
  payment_number, amount, currency, date, payer, recipient

For "reference_gtd":
  header: {{customs_office_code, date, number}},
  items: [{{item_no, hs_code, description, country_origin, gross_weight, net_weight, customs_value}}]

For "svh_doc":
  svh_number, warehouse_name, acceptance_date, warehouse_address

For "origin_certificate":
  certificate_type ("CT-1" / "Form A" / "EUR.1" / "Declaration of Origin" / "other"),
  certificate_number, certificate_date, issuing_country,
  exporter_name, country_origin (ISO alpha-2),
  items: [{{description, country_origin}}],
  trade_agreement

For "other":
  doc_title, summary (brief content description)

RESPONSE FORMAT:
{{
  "doc_type": "<type from the list above>",
  "doc_type_confidence": <0.0-1.0>,
  "extracted": {{ ... fields depending on doc_type ... }}
}}

FULL DOCUMENT TEXT:
{text}"""


def classify_and_extract(raw_text: str, filename: str) -> dict:
    """Single LLM call: classify document type AND extract structured data.

    Args:
        raw_text: Full OCR text (no truncation).
        filename: Original filename for context.

    Returns:
        dict with doc_type, doc_type_confidence, extracted, llm_debug.
    """
    t_start = time.monotonic()

    if not raw_text or not raw_text.strip():
        logger.warning("llm_parser_empty_text", filename=filename)
        return _empty_result(filename, "empty_text")

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        filename=filename,
        text=raw_text,
    )

    try:
        client = get_llm_client(operation="classify_and_extract")
        model = get_model()

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        raw_response = resp.choices[0].message.content or ""
        duration_ms = int((time.monotonic() - t_start) * 1000)

        tokens = {
            "prompt": getattr(resp.usage, "prompt_tokens", 0),
            "completion": getattr(resp.usage, "completion_tokens", 0),
        }

        parsed = json.loads(strip_code_fences(raw_response))

        doc_type = parsed.get("doc_type", "other")
        if doc_type not in _VALID_DOC_TYPES:
            logger.warning("llm_parser_unknown_type", doc_type=doc_type, filename=filename)
            doc_type = "other"

        result = {
            "doc_type": doc_type,
            "doc_type_confidence": parsed.get("doc_type_confidence", 0.5),
            "extracted": parsed.get("extracted", {}),
            "llm_debug": {
                "prompt_system": _SYSTEM_PROMPT[:500],
                "prompt_user": user_prompt[:500] + f"... [{len(user_prompt)} chars total]",
                "raw_response": raw_response,
                "duration_ms": duration_ms,
                "model": model,
                "tokens": tokens,
            },
        }
        logger.info(
            "llm_parser_ok",
            filename=filename,
            doc_type=doc_type,
            confidence=result["doc_type_confidence"],
            duration_ms=duration_ms,
            tokens_prompt=tokens["prompt"],
            tokens_completion=tokens["completion"],
            extracted_keys=list(result["extracted"].keys()),
        )
        return result

    except json.JSONDecodeError as e:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        logger.warning("llm_parser_json_error", error=str(e), filename=filename)
        return _fallback_result(raw_text, filename, f"json_error: {e}", duration_ms)

    except Exception as e:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        logger.warning("llm_parser_failed", error=str(e), filename=filename)
        return _fallback_result(raw_text, filename, f"llm_error: {e}", duration_ms)


def classify_and_extract_debug(raw_text: str, filename: str) -> dict:
    """Same as classify_and_extract but returns full prompts for debug panel."""
    t_start = time.monotonic()

    if not raw_text or not raw_text.strip():
        return _empty_result(filename, "empty_text")

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        filename=filename,
        text=raw_text,
    )

    try:
        client = get_llm_client(operation="classify_and_extract_debug")
        model = get_model()

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        raw_response = resp.choices[0].message.content or ""
        duration_ms = int((time.monotonic() - t_start) * 1000)

        tokens = {
            "prompt": getattr(resp.usage, "prompt_tokens", 0),
            "completion": getattr(resp.usage, "completion_tokens", 0),
        }

        parsed = json.loads(strip_code_fences(raw_response))

        doc_type = parsed.get("doc_type", "other")
        if doc_type not in _VALID_DOC_TYPES:
            doc_type = "other"

        return {
            "doc_type": doc_type,
            "doc_type_confidence": parsed.get("doc_type_confidence", 0.5),
            "extracted": parsed.get("extracted", {}),
            "llm_debug": {
                "prompt_system": _SYSTEM_PROMPT,
                "prompt_user": user_prompt,
                "raw_response": raw_response,
                "duration_ms": duration_ms,
                "model": model,
                "tokens": tokens,
            },
        }

    except Exception as e:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        return _fallback_result(raw_text, filename, str(e), duration_ms, full_debug=True)


def _fallback_result(
    raw_text: str, filename: str, error: str, duration_ms: int = 0,
    full_debug: bool = False,
) -> dict:
    """Fallback to heuristic type detection when LLM fails."""
    doc_type = _detect_doc_type_heuristic(filename, raw_text)
    logger.info("llm_parser_fallback", filename=filename, doc_type=doc_type, error=error)
    prompt_user = _USER_PROMPT_TEMPLATE.format(filename=filename, text=raw_text)
    return {
        "doc_type": doc_type,
        "doc_type_confidence": 0.3,
        "extracted": {},
        "llm_debug": {
            "prompt_system": _SYSTEM_PROMPT if full_debug else _SYSTEM_PROMPT[:500],
            "prompt_user": prompt_user if full_debug else prompt_user[:500],
            "raw_response": f"FALLBACK: {error}",
            "duration_ms": duration_ms,
            "model": "heuristic_fallback",
            "tokens": {"prompt": 0, "completion": 0},
        },
    }


def _empty_result(filename: str, reason: str) -> dict:
    return {
        "doc_type": "other",
        "doc_type_confidence": 0.0,
        "extracted": {},
        "llm_debug": {
            "prompt_system": "",
            "prompt_user": "",
            "raw_response": f"SKIPPED: {reason}",
            "duration_ms": 0,
            "model": "none",
            "tokens": {"prompt": 0, "completion": 0},
        },
    }


# ---------------------------------------------------------------------------
# Heuristic fallback (preserved from agent_crew._detect_doc_type)
# ---------------------------------------------------------------------------

def _detect_doc_type_heuristic(filename: str, text: str) -> str:
    """Heuristic document type detection — fallback when LLM is unavailable."""
    fn_lower = filename.lower()
    text_lower = (text[:3000].lower()) if text else ""

    if fn_lower.endswith(('.xlsx', '.xls')):
        return "packing_list"

    if ("inv" in fn_lower and "pl" in fn_lower) or ("инвойс" in fn_lower and "упаков" in fn_lower):
        return "invoice"

    if any(k in fn_lower for k in ["gtd", "гтд", "декларация на товары"]):
        return "reference_gtd"
    if re.search(r'\d{8}[_\-]\d{6}[_\-]\d{7}', fn_lower):
        return "reference_gtd"

    if any(k in fn_lower for k in ["cbx", "свх", "свх_", "warehouse"]):
        return "svh_doc"

    if any(k in fn_lower for k in ["certificate", "сертификат", "ct-1", "form a", "eur.1"]):
        return "origin_certificate"

    if any(k in fn_lower for k in ["contract", "договор", "контракт"]):
        return "contract"
    if any(k in fn_lower for k in ["packing", "упаков", "packing_list", "packing-list"]):
        return "packing_list"
    if re.search(r'\bpl\b', fn_lower) and "inv" not in fn_lower:
        return "packing_list"
    if any(k in fn_lower for k in ["awb", "waybill", "накладная", "cmr"]):
        return "transport_doc"
    if any(k in fn_lower for k in ["application", "заявка"]):
        return "application_statement"
    if any(k in fn_lower for k in ["spec", "спец"]):
        return "specification"
    if any(k in fn_lower for k in ["teh", "тех"]):
        return "tech_description"

    if any(k in fn_lower for k in ["пп", "платеж", "платёж", "payment order"]):
        return "payment_order"
    if any(k in text_lower for k in [
        "платежное поручение", "платёжное поручение", "payment order",
    ]):
        return "payment_order"

    _transport_invoice_name = any(k in fn_lower for k in [
        "invoice for transport", "transport invoice", "freight invoice",
        "инвойс за перевозку", "транспортный инвойс",
    ])
    if _transport_invoice_name:
        return "transport_invoice"

    is_invoice_by_name = any(k in fn_lower for k in [
        "invoice", "инвойс", "счёт", "счет", "inv-", "inv_",
    ])
    is_invoice_by_content = (
        ("invoice" in text_lower or "инвойс" in text_lower)
        and ("total" in text_lower or "amount" in text_lower or "итого" in text_lower)
    )
    if is_invoice_by_name or is_invoice_by_content:
        return "invoice"

    if any(k in text_lower for k in [
        "contract №", "contract no", "договор №", "контракт №",
    ]):
        return "contract"

    if any(k in text_lower for k in ["specification", "спецификация"]):
        return "specification"

    if any(k in text_lower for k in [
        "технические характеристики", "техническое описание",
        "technical specifications",
    ]):
        return "tech_description"

    if "packing list" in text_lower or "gross weight" in text_lower:
        return "packing_list"

    if "air waybill" in text_lower or re.search(r'\bawb\b', text_lower):
        return "transport_doc"

    if any(k in text_lower for k in [
        "сертификат происхождения", "certificate of origin",
        "форма ст-1", "form a", "eur.1",
    ]):
        return "origin_certificate"

    return "other"


