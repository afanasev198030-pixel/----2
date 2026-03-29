"""
Two-stage LLM document parser.

Stage 1 (classify):  short prompt → doc_type + confidence
Stage 2 (extract):   focused prompt with type-specific schema + few-shot → structured data
Fallback:            single call with all 13 schemas if classification confidence < 0.7
"""
import json
import re
import time
from typing import Optional

import structlog

from app.services.llm_client import get_llm_client, get_model, json_format_kwargs
from app.services.llm_json import strip_code_fences

logger = structlog.get_logger()

_VALID_DOC_TYPES = {
    "invoice", "contract", "packing_list", "specification",
    "tech_description", "transport_doc", "transport_invoice",
    "application_statement", "payment_order", "reference_gtd",
    "svh_doc", "origin_certificate", "insurance",
    "conformity_declaration", "other",
}

_CONFIDENCE_THRESHOLD = 0.7

# ---------------------------------------------------------------------------
# Stage 1: Classification prompts
# ---------------------------------------------------------------------------

_CLASSIFY_SYSTEM = """You are an expert customs document classifier for Russian Federation customs declarations.
Given a document filename and a text preview, determine the document type.
Return ONLY valid JSON with no extra text.

CRITICAL DISAMBIGUATION RULES:
1. tech_description vs invoice: "Техническое описание" — product specs (frequencies, voltages, materials, dimensions) but NO prices/amounts. Addressed to customs ("В таможенные органы"), has outgoing number ("Исх. №"). Invoice — has invoice number, unit prices, line totals, currency, total amount.
2. invoice vs transport_invoice: Invoice has product items table with unit prices. Transport invoice — ONLY freight/shipping/delivery charges, NO product line items.
3. specification vs invoice: Specification is an appendix/order to a contract ("Приложение к контракту", "Заказ №"), has delivery terms (Incoterms), payment schedule. Invoice has standalone invoice number ("Invoice №") and itemized totals.
4. contract vs specification: Contract is the main agreement with parties, subject, legal terms, signatures. Specification/order is an appendix ("Приложение") with specific items and prices for one shipment.
5. "air freight", "shipping", "logistics" in filename does NOT automatically mean transport — always check content."""

_CLASSIFY_USER = """Filename: {filename}

DOCUMENT TYPES AND THEIR KEY FEATURES:

invoice — Коммерческий инвойс (счёт-фактура).
  KEY: Invoice No., date, seller (FROM:), buyer (TO:), table of goods with Qty, Unit Price, Total, currency, Grand Total.
  ALWAYS has prices per item and total amount.

contract — Контракт / договор купли-продажи.
  KEY: Contract No., date, "Продавец/Покупатель" or "Seller/Buyer", subject of agreement, payment terms, legal clauses, bank details, signatures, seals.
  Usually multi-page with legal language.

packing_list — Упаковочный лист.
  KEY: "Packing List", reference to invoice No., table with Gross Weight, Net Weight, number of packages/cartons, dimensions/volume.
  Focus is on WEIGHTS and PACKAGING, not prices.

specification — Спецификация / заказ к контракту.
  KEY: "Приложение к контракту" / "Appendix" / "Заказ №" / "Order No.", delivery terms (EXW/FOB/CIF + place), payment schedule, table of items with prices.
  Linked to a framework contract. May have Incoterms and delivery schedule.

tech_description — Техническое описание товара для таможни.
  KEY: "Техническое описание" title, outgoing number "Исх. №", addressed "В таможенные органы".
  Contains: product name, purpose, technical specs (frequencies, voltages, power, materials, dimensions), manufacturer, model, brand.
  NEVER has prices, totals, or currency. Describes WHAT the product IS, not how much it costs.

transport_doc — Транспортная накладная (AWB / CMR / B/L / коносамент).
  KEY: "Air Waybill" / "AWB" / "CMR" / "Bill of Lading", waybill number (e.g. 555-12345678), shipper/consignee, origin/destination airports or ports, weight, pieces count, "Notify Party".
  Standard transport document format.

transport_invoice — Транспортный инвойс (счёт за перевозку/фрахт).
  KEY: Invoice for freight/shipping/delivery services. Has freight amount + currency.
  Contains shipper (FROM:), consignee (TO:), AWB reference, but NO product items with individual prices — ONLY total freight charge.

application_statement — Заявка на перевозку / поручение экспедитору.
  KEY: "Заявка" / "Application", route (откуда-куда), cargo description, delivery terms (Incoterms), transport mode, shipper/consignee contacts.
  An order for transportation services.

payment_order — Платёжное поручение.
  KEY: "Платёжное поручение" / "Payment Order", PP number, date, payer, payee, amount, purpose of payment ("Назначение платежа"), bank details (БИК, к/с, р/с).

reference_gtd — Эталонная таможенная декларация (ГТД / ДТ).
  KEY: Declaration number format XX/XXXXXX/XXXXXXX, "ДЕКЛАРАЦИЯ НА ТОВАРЫ", customs office code, declaration fields (графы), HS codes (ТН ВЭД).

svh_doc — Документ склада временного хранения (СВХ).
  KEY: "СВХ" / "склад временного хранения", warehouse number, acceptance/placement date, warehouse address.

origin_certificate — Сертификат происхождения товара.
  KEY: "Certificate of Origin" / "СТ-1" / "Form A" / "EUR.1", certificate number, country of origin, exporter name, issuing authority.

insurance — Страховой полис / сертификат на груз.
  KEY: "Insurance" / "Policy" / "страховой полис", policy number, insured amount, insurance conditions (All Risks), insured cargo description, route.

conformity_declaration — Декларация о соответствии ЕАЭС (ТР ТС).
  KEY: "ДЕКЛАРАЦИЯ О СООТВЕТСТВИИ" / "ЕВРАЗИЙСКИЙ ЭКОНОМИЧЕСКИЙ СОЮЗ", registration number "ЕАЭС N RU Д-...", applicant (заявитель), product name, HS code (ТН ВЭД), technical regulation "ТР ТС", test protocol, conformity scheme.

other — Ни один из вышеперечисленных типов.

Return JSON: {{"doc_type": "<type>", "doc_type_confidence": <0.0-1.0>, "reasoning": "<1 sentence>"}}

TEXT PREVIEW:
{text_preview}"""

# ---------------------------------------------------------------------------
# Stage 2: Extraction system prompt (no type list — type already known)
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM = """You are an expert customs document data extractor for Russian Federation customs declarations (ДТ).
The document type has been determined. Extract ALL structured data from the FULL document text.

Return ONLY valid JSON — no markdown, no explanations outside JSON.

CRITICAL RULES:
- Extract data in the ORIGINAL language of the document. For Russian buyer/declarant names — use Russian.
- Numbers: return as numbers (float/int), not strings. Use dot as decimal separator.
- Dates: return as strings in the format found in the document.
- Country codes: 2-letter ISO 3166-1 alpha-2 (CN, RU, DE, US...).
- Currency codes: 3-letter ISO 4217 (USD, EUR, CNY...).
- Items: include ALL product lines from the document. Do NOT skip any line items.
- Do NOT include freight, shipping, insurance, or handling fee lines as product items.
- If a field is not found in the document, use null.
- For seller/buyer: extract name, address, country_code, inn, kpp, ogrn, tax_number when available.

VISION OCR TABLE PARSING:
- Tables from Vision OCR may appear inside [TABLE_START]...[TABLE_END] markers with cell values concatenated WITHOUT separators.
- Use column headers to split the concatenated data row into individual cell values.
- Numbers with spaces (e.g., "1 094 239,00") are European-formatted: 1094239.00
- Comma before decimals (e.g., "643,6700") is a decimal separator: 643.67
- ALWAYS extract quantity, unit_price, and line_total as separate numeric fields — NEVER merge them into the description.

OCR ARTIFACT HANDLING:
- OCR may distort "№" as "N&", "N°" — strip these from document numbers.
- OCR may distort Cyrillic: "Договор" → "Doropov". Use context to determine meaning.
- Bank INN (from "BENEFICIARY BANK" section) is NOT the buyer's or seller's INN.

RESPONSE FORMAT:
{{"doc_type": "{doc_type}", "doc_type_confidence": {confidence}, "reasoning": "<1 sentence>", "extracted": {{ ... }}}}"""

# ---------------------------------------------------------------------------
# Type-specific field schemas
# ---------------------------------------------------------------------------

_TYPE_SCHEMAS: dict[str, str] = {
    "invoice": (
        "invoice_number, invoice_date, currency (ISO 4217), total_amount (number),\n"
        "incoterms,\n"
        "contract_number (look for 'Contract No.', 'Per Contract', 'Контракт №', 'Ref:' — often in header or footer),\n"
        "contract_date,\n"
        "country_origin (ISO alpha-2),\n"
        "seller: {name, address, country_code, tax_number},\n"
        "buyer: {name, address, country_code, tax_number},\n"
        "items: [{description, quantity, unit, unit_price, line_total, country_origin, hs_code, gross_weight, net_weight}],\n"
        "total_gross_weight, total_net_weight, total_packages"
    ),
    "contract": (
        "contract_number, contract_date, currency (ISO 4217), total_amount,\n"
        "incoterms (code only, e.g. EXW/FOB/CIF),\n"
        "delivery_place (city/place written AFTER Incoterms code — NOT the destination),\n"
        "subject, payment_terms,\n"
        "is_trilateral (true/false),\n"
        "seller: {name, address, country_code, inn, kpp, ogrn},\n"
        "buyer: {name, address, country_code, inn, kpp, ogrn} — buyer name and address MUST be in RUSSIAN,\n"
        "receiver: {name, address, country_code, inn, kpp, ogrn} (only if trilateral),\n"
        "financial_party: {name, address, country_code, inn, kpp, ogrn} (only if trilateral)"
    ),
    "packing_list": (
        "total_packages, package_type, total_gross_weight, total_net_weight, country_origin,\n"
        "items: [{description, quantity, packages_count, package_type, gross_weight, net_weight, country_origin}]"
    ),
    "specification": (
        "incoterms (e.g. EXW, FOB, CIF — the code ONLY, without the place),\n"
        "delivery_place (the place/city written AFTER the Incoterms code, e.g. 'EXW Hongkong' → delivery_place='Hongkong'. "
        "This is NOT the destination airport/city — it is where the seller delivers the goods),\n"
        "items: [{description, quantity, unit, unit_price, line_total, country_origin}],\n"
        "total_amount, items_count"
    ),
    "tech_description": (
        "products: [{name, purpose, materials, specifications, application_area, operating_conditions}]"
    ),
    "transport_doc": (
        "awb_number, shipper_name, shipper_address, consignee_name, consignee_address,\n"
        "consignee_inn, consignee_kpp, consignee_ogrn,\n"
        "departure_airport, destination_airport, transport_type (10=sea, 30=auto, 40=air),\n"
        "flight_number, vehicle_reg_number, vessel_name, vehicle_country_code,\n"
        "container_numbers: [string], departure_country (ISO alpha-2)"
    ),
    "transport_invoice": (
        "doc_number, doc_date, freight_amount, freight_currency (ISO 4217),\n"
        "shipper_name (company issuing the invoice), shipper_address, shipper_contact,\n"
        "consignee_name (TO: party), consignee_address, consignee_inn,\n"
        "contract_number, contract_date,\n"
        "awb_number, transport_type (10=sea, 30=auto, 40=air), route,\n"
        "flight_number, bank_details"
    ),
    "application_statement": (
        "incoterms, delivery_place, forwarding_agent: {name, address},\n"
        "shipper: {name, address}, departure_country"
    ),
    "payment_order": "payment_number, amount, currency, date, payer, recipient",
    "reference_gtd": (
        "header: {customs_office_code, date, number},\n"
        "items: [{item_no, hs_code, description, country_origin, gross_weight, net_weight, customs_value}]"
    ),
    "svh_doc": "svh_number, warehouse_name, acceptance_date, warehouse_address",
    "origin_certificate": (
        'certificate_type ("CT-1" / "Form A" / "EUR.1" / "Declaration of Origin" / "other"),\n'
        "certificate_number, certificate_date, issuing_country,\n"
        "exporter_name, country_origin (ISO alpha-2),\n"
        "items: [{description, country_origin}],\n"
        "trade_agreement"
    ),
    "insurance": (
        "policy_number, issue_date, insured_name, insured_amount, insured_currency (ISO 4217),\n"
        "goods_description, route, transport_type (10=sea, 30=auto, 40=air),\n"
        "awb_number, bl_number, insurer_name, conditions,\n"
        "claim_payable_at"
    ),
    "conformity_declaration": (
        "declaration_number (format: ЕАЭС N RU Д-XX.XXXX.X.XXXXX/XX),\n"
        "registration_date, valid_until,\n"
        "applicant_name, applicant_ogrn,\n"
        "product_name (full product description with model),\n"
        "manufacturer_name, manufacturer_country (ISO alpha-2),\n"
        "hs_code (ТН ВЭД ЕАЭС code, 10 digits),\n"
        "quantity, quantity_unit,\n"
        "invoice_number, invoice_date, contract_number, contract_date,\n"
        "technical_regulation (ТР ТС/ТР ЕАЭС number and name),\n"
        "conformity_scheme (e.g. 1д, 2д, 3д, 4д, 6д),\n"
        "test_protocol_number, test_protocol_date, test_lab_name"
    ),
    "other": "doc_title, summary (brief content description)",
}

_EXTRACT_USER_TEMPLATE = """Filename: {filename}

Document type: {doc_type}

FIELDS TO EXTRACT:
{schema}

FULL DOCUMENT TEXT:
{text}"""

# ---------------------------------------------------------------------------
# Full prompt (fallback — used when classification confidence < threshold)
# ---------------------------------------------------------------------------

_FULL_SYSTEM_PROMPT = """You are an expert customs document parser for Russian Federation customs declarations (ДТ).
You receive a document (OCR text or Markdown) and must:
1. Think step-by-step about the document type — write your reasoning in the "reasoning" field.
2. Determine the document type from the allowed list.
3. Extract ALL relevant structured data from the FULL document text.

Return ONLY valid JSON — no markdown, no explanations outside JSON.

CRITICAL RULES:
- Extract data in the ORIGINAL language of the document. For Russian buyer/declarant names — use Russian.
- Numbers: return as numbers (float/int), not strings. Use dot as decimal separator.
- Dates: return as strings in format YYYY-MM-DD or DD.MM.YYYY (as found in document).
- Country codes: 2-letter ISO 3166-1 alpha-2 (CN, RU, DE, US...).
- Currency codes: 3-letter ISO 4217 (USD, EUR, CNY...).
- Items: include ALL product lines from the document. Do NOT skip any line items.
- Do NOT include freight, shipping, insurance, or handling fee lines as product items.
- If a field is not found in the document, use null.
- For seller/buyer: extract name, address, country_code, inn, kpp, ogrn, tax_number when available.

TYPE DISAMBIGUATION RULES:
- invoice vs transport_invoice: if the document contains ONLY freight/shipping charges without product items — it is "transport_invoice". If it has product lines with prices — it is "invoice".
- specification vs invoice: if the document is an appendix to a contract without final totals or invoice number — it is "specification". If it has an invoice number and totals — it is "invoice".
- Completeness: extract ALL items. The number of extracted items MUST match the document. If the document has 15 lines, return 15 items.
- Confidence: set doc_type_confidence below 0.7 if you are unsure about the type.

VISION OCR TABLE PARSING:
- Tables from Vision OCR may appear inside [TABLE_START]...[TABLE_END] markers with cell values concatenated WITHOUT separators.
- Use column headers to split the concatenated data row into individual cell values.
- Numbers with spaces (e.g., "1 094 239,00") are European-formatted: 1094239.00
- Comma before decimals (e.g., "643,6700") is a decimal separator: 643.67
- ALWAYS extract quantity, unit_price, and line_total as separate numeric fields — NEVER merge them into the description.

OCR ARTIFACT HANDLING:
- OCR may distort "№" as "N&", "N°" — strip these from document numbers.
- OCR may distort Cyrillic: "Договор" → "Doropov". Use context to determine meaning.
- Bank INN (from "BENEFICIARY BANK" section) is NOT the buyer's or seller's INN.

RESPONSE FORMAT (always include "reasoning"):
{
  "doc_type": "<type>",
  "doc_type_confidence": <0.0-1.0>,
  "reasoning": "<1-2 sentences explaining why you chose this type>",
  "extracted": { ... }
}"""

_FULL_USER_TEMPLATE = """Filename: {filename}

Determine the document type and extract data.

ALLOWED DOCUMENT TYPES:
- invoice — commercial invoice for goods (товарный инвойс)
- contract — sale/purchase contract or agreement (контракт/договор)
- packing_list — packing list with weights and packages (упаковочный лист)
- specification — product specification / appendix to contract (спецификация)
- tech_description — technical description for customs, NO prices (техническое описание для таможни)
- transport_doc — transport document: AWB, CMR, B/L, waybill (транспортная накладная)
- transport_invoice — freight/shipping invoice (транспортный инвойс, инвойс за перевозку)
- application_statement — forwarding application/order (заявка на перевозку)
- payment_order — payment order (платёжное поручение)
- reference_gtd — reference customs declaration (эталонная ГТД)
- svh_doc — temporary storage warehouse document (документ СВХ)
- origin_certificate — certificate of origin: CT-1, Form A, EUR.1 (сертификат происхождения)
- insurance — cargo transportation insurance policy/certificate (страховой полис груза)
- conformity_declaration — EAEU/EAC conformity declaration (декларация о соответствии ЕАЭС/ТР ТС)
- other — if none of the above match

FIELDS TO EXTRACT BY TYPE:

For "invoice":
  invoice_number, invoice_date, currency (ISO 4217), total_amount (number),
  incoterms,
  contract_number (look for "Contract No.", "Per Contract", "Контракт №", "Ref:" — often in header or footer),
  contract_date,
  country_origin (ISO alpha-2),
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
  incoterms (code only: EXW, FOB, CIF etc.),
  delivery_place (city/place AFTER Incoterms code, e.g. "EXW Hongkong" → "Hongkong". NOT the destination airport!),
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
  shipper_name (company issuing the invoice), shipper_address, shipper_contact,
  consignee_name (TO: party), consignee_address, consignee_inn,
  contract_number, contract_date,
  awb_number, transport_type (10=sea, 30=auto, 40=air), route,
  flight_number, bank_details

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

For "insurance":
  policy_number, issue_date, insured_name, insured_amount, insured_currency (ISO 4217),
  goods_description, route, transport_type (10=sea, 30=auto, 40=air),
  awb_number, bl_number, insurer_name, conditions,
  claim_payable_at

For "conformity_declaration":
  declaration_number (ЕАЭС N RU Д-XX.XXXX.X.XXXXX/XX),
  registration_date, valid_until,
  applicant_name, applicant_ogrn,
  product_name (full product description with model),
  manufacturer_name, manufacturer_country (ISO alpha-2),
  hs_code (ТН ВЭД 10 digits), quantity, quantity_unit,
  invoice_number, invoice_date, contract_number, contract_date,
  technical_regulation, conformity_scheme,
  test_protocol_number, test_protocol_date, test_lab_name

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

_MAX_TOKENS_CLASSIFY = 200
_MAX_TOKENS_PRIMARY = 8000
_MAX_TOKENS_RETRY = 12000


# ---------------------------------------------------------------------------
# LLM call helpers
# ---------------------------------------------------------------------------

def _llm_call_with_json_fallback(client, model: str, messages: list, max_tokens: int):
    """Call LLM requesting JSON output. Uses response_format for providers that support it,
    falls back to prompt-only JSON for others (e.g. Cloud.ru gpt-oss-120b)."""
    from app.services.llm_client import json_format_kwargs
    fmt = json_format_kwargs()

    if fmt:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=max_tokens,
                **fmt,
            )
            content = resp.choices[0].message.content
            if content and content.strip():
                return resp
            logger.info("llm_json_mode_empty_response_retrying_without")
        except Exception as e:
            logger.info("llm_json_mode_unsupported_fallback", error=str(e)[:200])

    return client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        max_tokens=max_tokens,
    )


def _build_messages_for_extract(
    user_prompt: str,
    doc_type: Optional[str] = None,
    system_prompt: str = _FULL_SYSTEM_PROMPT,
) -> list[dict]:
    """Build message list: system + few-shot (filtered by type) + user query."""
    messages = [{"role": "system", "content": system_prompt}]
    try:
        from app.services.fewshot_examples import build_fewshot_messages
        messages.extend(build_fewshot_messages(doc_type=doc_type))
    except Exception:
        pass
    messages.append({"role": "user", "content": user_prompt})
    return messages


# ---------------------------------------------------------------------------
# Stage 1: Classification
# ---------------------------------------------------------------------------

def _classify_document(raw_text: str, filename: str) -> dict:
    """Stage 1: Classify document type with a short LLM call.

    Returns dict with doc_type, doc_type_confidence, reasoning, classify_debug.
    """
    t0 = time.monotonic()
    text_preview = raw_text[:1500] if raw_text else ""

    messages = [
        {"role": "system", "content": _CLASSIFY_SYSTEM},
        {"role": "user", "content": _CLASSIFY_USER.format(
            filename=filename, text_preview=text_preview,
        )},
    ]

    try:
        client = get_llm_client(operation="classify_document")
        model = get_model()

        resp = _llm_call_with_json_fallback(
            client, model, messages, _MAX_TOKENS_CLASSIFY)

        raw = resp.choices[0].message.content or ""
        parsed = json.loads(strip_code_fences(raw))
        duration_ms = int((time.monotonic() - t0) * 1000)

        doc_type = parsed.get("doc_type", "other")
        if doc_type not in _VALID_DOC_TYPES:
            doc_type = "other"

        confidence = parsed.get("doc_type_confidence", 0.5)

        logger.info(
            "llm_classify_ok",
            filename=filename,
            doc_type=doc_type,
            confidence=confidence,
            reasoning=str(parsed.get("reasoning", ""))[:200],
            duration_ms=duration_ms,
            tokens_prompt=getattr(getattr(resp, "usage", None), "prompt_tokens", 0),
            tokens_completion=getattr(getattr(resp, "usage", None), "completion_tokens", 0),
        )

        return {
            "doc_type": doc_type,
            "doc_type_confidence": confidence,
            "reasoning": parsed.get("reasoning", ""),
            "classify_debug": {
                "duration_ms": duration_ms,
                "tokens_prompt": getattr(getattr(resp, "usage", None), "prompt_tokens", 0),
                "tokens_completion": getattr(getattr(resp, "usage", None), "completion_tokens", 0),
            },
        }

    except Exception as e:
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.warning("llm_classify_failed", error=str(e)[:200],
                        filename=filename, duration_ms=duration_ms)
        return {
            "doc_type": "other",
            "doc_type_confidence": 0.0,
            "reasoning": f"classification_error: {e}",
            "classify_debug": {"duration_ms": duration_ms, "error": str(e)[:200]},
        }


# ---------------------------------------------------------------------------
# Stage 2: Focused extraction (type already known)
# ---------------------------------------------------------------------------

def _extract_by_type(raw_text: str, filename: str, doc_type: str,
                     confidence: float) -> dict:
    """Stage 2: Extract structured data with a type-focused prompt."""
    t0 = time.monotonic()

    schema = _TYPE_SCHEMAS.get(doc_type, _TYPE_SCHEMAS["other"])
    system = _EXTRACT_SYSTEM.format(doc_type=doc_type, confidence=confidence)
    user_prompt = _EXTRACT_USER_TEMPLATE.format(
        filename=filename,
        doc_type=doc_type,
        schema=schema,
        text=raw_text,
    )
    messages = _build_messages_for_extract(
        user_prompt, doc_type=doc_type, system_prompt=system)

    try:
        client = get_llm_client(operation="extract_by_type")
        model = get_model()

        resp = _llm_call_with_json_fallback(
            client, model, messages, _MAX_TOKENS_PRIMARY)

        raw_response = resp.choices[0].message.content or ""
        finish_reason = resp.choices[0].finish_reason

        if finish_reason == "length":
            logger.warning("llm_extract_truncated_retrying", filename=filename)
            resp = _llm_call_with_json_fallback(
                client, model, messages, _MAX_TOKENS_RETRY)
            raw_response = resp.choices[0].message.content or ""

        duration_ms = int((time.monotonic() - t0) * 1000)
        tokens = {
            "prompt": getattr(resp.usage, "prompt_tokens", 0),
            "completion": getattr(resp.usage, "completion_tokens", 0),
        }

        parsed = json.loads(strip_code_fences(raw_response))
        extracted = parsed.get("extracted", {})

        from app.services.extraction_normalizer import normalize_extraction
        extracted = normalize_extraction(doc_type, extracted)

        result = {
            "doc_type": doc_type,
            "doc_type_confidence": confidence,
            "extracted": extracted,
            "reasoning": parsed.get("reasoning", ""),
            "pipeline": "two_stage",
            "llm_debug": {
                "prompt_system": system[:500],
                "prompt_user": user_prompt[:500] + f"... [{len(user_prompt)} chars total]",
                "raw_response": raw_response,
                "duration_ms": duration_ms,
                "model": model,
                "tokens": tokens,
                "finish_reason": finish_reason,
            },
        }

        logger.info(
            "llm_extract_ok",
            filename=filename,
            doc_type=doc_type,
            duration_ms=duration_ms,
            tokens_prompt=tokens["prompt"],
            tokens_completion=tokens["completion"],
            extracted_keys=list(extracted.keys()),
        )
        return result

    except json.JSONDecodeError as e:
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.warning("llm_extract_json_error", error=str(e), filename=filename)
        return _fallback_result(raw_text, filename, f"extract_json_error: {e}", duration_ms)

    except Exception as e:
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.warning("llm_extract_failed", error=str(e), filename=filename)
        return _fallback_result(raw_text, filename, f"extract_error: {e}", duration_ms)


# ---------------------------------------------------------------------------
# Fallback: full single-call extraction (all 13 types)
# ---------------------------------------------------------------------------

def _extract_full(raw_text: str, filename: str) -> dict:
    """Fallback: classify + extract in a single LLM call with all type schemas."""
    t0 = time.monotonic()

    user_prompt = _FULL_USER_TEMPLATE.format(filename=filename, text=raw_text)
    messages = _build_messages_for_extract(
        user_prompt, doc_type=None, system_prompt=_FULL_SYSTEM_PROMPT)

    try:
        client = get_llm_client(operation="extract_full_fallback")
        model = get_model()

        resp = _llm_call_with_json_fallback(
            client, model, messages, _MAX_TOKENS_PRIMARY)

        raw_response = resp.choices[0].message.content or ""
        finish_reason = resp.choices[0].finish_reason

        if finish_reason == "length":
            logger.warning("llm_full_truncated_retrying", filename=filename)
            resp = _llm_call_with_json_fallback(
                client, model, messages, _MAX_TOKENS_RETRY)
            raw_response = resp.choices[0].message.content or ""

        duration_ms = int((time.monotonic() - t0) * 1000)
        tokens = {
            "prompt": getattr(resp.usage, "prompt_tokens", 0),
            "completion": getattr(resp.usage, "completion_tokens", 0),
        }

        parsed = json.loads(strip_code_fences(raw_response))
        doc_type = parsed.get("doc_type", "other")
        if doc_type not in _VALID_DOC_TYPES:
            doc_type = "other"

        extracted = parsed.get("extracted", {})

        from app.services.extraction_normalizer import normalize_extraction
        extracted = normalize_extraction(doc_type, extracted)

        result = {
            "doc_type": doc_type,
            "doc_type_confidence": parsed.get("doc_type_confidence", 0.5),
            "extracted": extracted,
            "reasoning": parsed.get("reasoning", ""),
            "pipeline": "full_fallback",
            "llm_debug": {
                "prompt_system": _FULL_SYSTEM_PROMPT[:500],
                "prompt_user": user_prompt[:500] + f"... [{len(user_prompt)} chars total]",
                "raw_response": raw_response,
                "duration_ms": duration_ms,
                "model": model,
                "tokens": tokens,
                "finish_reason": finish_reason,
            },
        }

        logger.info(
            "llm_parser_ok",
            filename=filename,
            doc_type=doc_type,
            confidence=result["doc_type_confidence"],
            reasoning=result["reasoning"][:200] if result["reasoning"] else "",
            duration_ms=duration_ms,
            tokens_prompt=tokens["prompt"],
            tokens_completion=tokens["completion"],
            pipeline="full_fallback",
        )
        return result

    except json.JSONDecodeError as e:
        duration_ms = int((time.monotonic() - t0) * 1000)
        return _fallback_result(raw_text, filename, f"json_error: {e}", duration_ms)

    except Exception as e:
        duration_ms = int((time.monotonic() - t0) * 1000)
        return _fallback_result(raw_text, filename, f"llm_error: {e}", duration_ms)


# ---------------------------------------------------------------------------
# Public API (same signatures as before)
# ---------------------------------------------------------------------------

def classify_and_extract(raw_text: str, filename: str) -> dict:
    """Two-stage pipeline: classify -> extract.  Falls back to single call
    when classification confidence is below threshold.

    Signature unchanged from previous version for backward compatibility.
    """
    if not raw_text or not raw_text.strip():
        logger.warning("llm_parser_empty_text", filename=filename)
        return _empty_result(filename, "empty_text")

    classification = _classify_document(raw_text, filename)
    doc_type = classification["doc_type"]
    confidence = classification["doc_type_confidence"]

    if confidence >= _CONFIDENCE_THRESHOLD and doc_type != "other":
        result = _extract_by_type(raw_text, filename, doc_type, confidence)
        result.setdefault("classify_debug", classification.get("classify_debug"))
    else:
        logger.info("llm_parser_low_confidence_fallback",
                     filename=filename, doc_type=doc_type, confidence=confidence)
        result = _extract_full(raw_text, filename)
        result.setdefault("classify_debug", classification.get("classify_debug"))

    return result


def classify_and_extract_with_correction(raw_text: str, filename: str) -> dict:
    """classify_and_extract + 1 validation/correction retry if critical issues found."""
    from app.services.extraction_validator import (
        validate_extraction, has_critical_issues, build_correction_prompt,
    )

    result = classify_and_extract(raw_text, filename)

    doc_type = result.get("doc_type", "other")
    extracted = result.get("extracted", {})
    issues = validate_extraction(doc_type, extracted)

    result["validation_issues"] = [i.to_dict() for i in issues]

    if not has_critical_issues(issues):
        return result

    logger.info("llm_parser_correction_retry", filename=filename,
                issues_count=len(issues),
                critical=[i.field for i in issues if i.severity == "critical"])

    correction_prompt = build_correction_prompt(issues)
    raw_response = result.get("llm_debug", {}).get("raw_response", "")

    schema = _TYPE_SCHEMAS.get(doc_type, _TYPE_SCHEMAS["other"])
    system = _EXTRACT_SYSTEM.format(doc_type=doc_type,
                                     confidence=result.get("doc_type_confidence", 0.9))

    try:
        client = get_llm_client(operation="classify_and_extract_correction")
        model = get_model()

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": _EXTRACT_USER_TEMPLATE.format(
                    filename=filename, doc_type=doc_type,
                    schema=schema, text=raw_text)},
                {"role": "assistant", "content": raw_response},
                {"role": "user", "content": correction_prompt},
            ],
            temperature=0,
            max_tokens=_MAX_TOKENS_PRIMARY,
            **json_format_kwargs(),
        )

        corrected_raw = resp.choices[0].message.content or ""
        corrected = json.loads(strip_code_fences(corrected_raw))

        corrected_doc_type = corrected.get("doc_type", doc_type)
        corrected_extracted = corrected.get("extracted", extracted)

        from app.services.extraction_normalizer import normalize_extraction
        corrected_extracted = normalize_extraction(corrected_doc_type, corrected_extracted)

        re_issues = validate_extraction(corrected_doc_type, corrected_extracted)

        if len([i for i in re_issues if i.severity == "critical"]) < \
           len([i for i in issues if i.severity == "critical"]):
            result["doc_type"] = corrected_doc_type
            result["extracted"] = corrected_extracted
            result["reasoning"] = corrected.get("reasoning", result.get("reasoning", ""))
            result["validation_issues"] = [i.to_dict() for i in re_issues]
            result["correction_applied"] = True
            logger.info("llm_parser_correction_ok", filename=filename,
                        remaining_issues=len(re_issues))
        else:
            result["correction_applied"] = False
            logger.info("llm_parser_correction_no_improvement", filename=filename)

    except Exception as e:
        logger.warning("llm_parser_correction_failed", error=str(e), filename=filename)
        result["correction_applied"] = False

    return result


def classify_and_extract_debug(raw_text: str, filename: str) -> dict:
    """Same as classify_and_extract but returns full prompts for debug panel."""
    if not raw_text or not raw_text.strip():
        return _empty_result(filename, "empty_text")

    classification = _classify_document(raw_text, filename)
    doc_type = classification["doc_type"]
    confidence = classification["doc_type_confidence"]

    t0 = time.monotonic()

    if confidence >= _CONFIDENCE_THRESHOLD and doc_type != "other":
        schema = _TYPE_SCHEMAS.get(doc_type, _TYPE_SCHEMAS["other"])
        system = _EXTRACT_SYSTEM.format(doc_type=doc_type, confidence=confidence)
        user_prompt = _EXTRACT_USER_TEMPLATE.format(
            filename=filename, doc_type=doc_type, schema=schema, text=raw_text)
        messages = _build_messages_for_extract(
            user_prompt, doc_type=doc_type, system_prompt=system)
        pipeline = "two_stage"
    else:
        system = _FULL_SYSTEM_PROMPT
        user_prompt = _FULL_USER_TEMPLATE.format(filename=filename, text=raw_text)
        messages = _build_messages_for_extract(
            user_prompt, doc_type=None, system_prompt=system)
        pipeline = "full_fallback"

    try:
        client = get_llm_client(operation="classify_and_extract_debug")
        model = get_model()

        resp = _llm_call_with_json_fallback(
            client, model, messages, _MAX_TOKENS_PRIMARY)

        raw_response = resp.choices[0].message.content or ""
        finish_reason = resp.choices[0].finish_reason
        duration_ms = int((time.monotonic() - t0) * 1000)

        tokens = {
            "prompt": getattr(resp.usage, "prompt_tokens", 0),
            "completion": getattr(resp.usage, "completion_tokens", 0),
        }

        parsed = json.loads(strip_code_fences(raw_response))

        result_doc_type = parsed.get("doc_type", doc_type)
        if result_doc_type not in _VALID_DOC_TYPES:
            result_doc_type = doc_type

        extracted = parsed.get("extracted", {})
        from app.services.extraction_normalizer import normalize_extraction
        extracted = normalize_extraction(result_doc_type, extracted)

        return {
            "doc_type": result_doc_type,
            "doc_type_confidence": parsed.get("doc_type_confidence", confidence),
            "extracted": extracted,
            "reasoning": parsed.get("reasoning", ""),
            "pipeline": pipeline,
            "classify_debug": classification.get("classify_debug"),
            "llm_debug": {
                "prompt_system": system,
                "prompt_user": user_prompt,
                "raw_response": raw_response,
                "duration_ms": duration_ms,
                "model": model,
                "tokens": tokens,
                "finish_reason": finish_reason,
                "fewshot_count": (len(messages) - 2) // 2,
            },
        }

    except Exception as e:
        duration_ms = int((time.monotonic() - t0) * 1000)
        return _fallback_result(raw_text, filename, str(e), duration_ms, full_debug=True)


# ---------------------------------------------------------------------------
# Fallback helpers
# ---------------------------------------------------------------------------

def _fallback_result(
    raw_text: str, filename: str, error: str, duration_ms: int = 0,
    full_debug: bool = False,
) -> dict:
    """Fallback to heuristic type detection when LLM fails completely."""
    doc_type = _detect_doc_type_heuristic(filename, raw_text)
    logger.info("llm_parser_fallback", filename=filename, doc_type=doc_type, error=error)
    prompt_user = _FULL_USER_TEMPLATE.format(filename=filename, text=raw_text)
    return {
        "doc_type": doc_type,
        "doc_type_confidence": 0.3,
        "extracted": {},
        "pipeline": "heuristic_fallback",
        "llm_debug": {
            "prompt_system": _FULL_SYSTEM_PROMPT if full_debug else _FULL_SYSTEM_PROMPT[:500],
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
        "pipeline": "none",
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
# Heuristic fallback (used ONLY when ALL LLM calls fail)
# ---------------------------------------------------------------------------

def _detect_doc_type_heuristic(filename: str, text: str) -> str:
    """Heuristic document type detection — last-resort fallback."""
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
    if any(k in fn_lower for k in ["insurance", "страхов", "полис"]):
        return "insurance"
    if any(k in fn_lower for k in ["декларация еаэс", "декларация о соответствии", "еаэс n ru"]):
        return "conformity_declaration"
    if "еаэс" in text_lower and "декларация о соответствии" in text_lower:
        return "conformity_declaration"
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
