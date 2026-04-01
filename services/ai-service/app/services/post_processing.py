"""
Post-processing functions for declaration compilation.

These functions handle deterministic operations after LLM compilation:
customs office resolution, item processing, customs value calculation,
classifier validation, and output formatting.
"""
import math
import re
import mimetypes
from typing import Optional

import structlog

from app.services.parsing_utils import safe_float as _safe_float, normalize_hs_code as _normalize_hs_code, to_dict
from app.services.invoice_parser import _is_garbage_desc
from app.services.reference_data import lookup_customs_office, resolve_iata_city, get_eu_countries

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# calc-service integration
# ---------------------------------------------------------------------------

def _fetch_exchange_rates() -> dict:
    """Fetch latest CBR exchange rates from calc-service."""
    import httpx
    from app.config import get_settings
    url = f"{get_settings().CALC_SERVICE_URL}/api/v1/calc/exchange-rates/latest"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json().get("rates", {})
    except Exception as e:
        logger.warning("fetch_exchange_rates_failed", error=str(e)[:200])
        return {}


def _fetch_payments(items: list[dict], currency: str, exchange_rate: float) -> dict:
    """Call calc-service to calculate customs payments (duty, VAT, excise, fees)."""
    import httpx
    from app.config import get_settings
    url = f"{get_settings().CALC_SERVICE_URL}/api/v1/calc/payments/calculate"
    try:
        resp = httpx.post(url, json={
            "items": items,
            "currency": currency,
            "exchange_rate": exchange_rate,
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("fetch_payments_failed", error=str(e)[:200])
        return {}


def _determine_preference_code(cert_type: str | None, trade_agreement: str | None) -> str:
    """Determine 4-element preference code (gr. 36)."""
    el1 = "ОО"
    el2 = "ТП" if cert_type in ("CT-1", "Form A", "EUR.1") else "ОО"
    el3 = "-"
    el4 = "ОО"
    return f"{el1} {el2} {el3} {el4}"


def document_payload(obj) -> dict | None:
    """Подготовить лёгкий parsed_data для хранения в core-api Document."""
    data = to_dict(obj)
    if not data:
        return None
    cleaned: dict = {}
    for key, value in data.items():
        if key in {"raw_text", "_cache_type"}:
            continue
        if isinstance(key, str) and key.startswith("_"):
            continue
        cleaned[key] = value
    return cleaned or None



def build_documents_list(parsed_docs: dict, inv: dict, contract: dict, awb_number: str | None) -> list[dict]:
    """Графа 44: перечень документов с кодами классификатора, номерами и датами."""
    import mimetypes

    _DOC_TYPE_CODES = {
        "invoice":               "04021",
        "contract":              "03011",
        "packing":               "04024",
        "packing_list":          "04024",
        "specification":         "04091",
        "transport_invoice":     "04025",
        "application_statement": "05999",
        "tech_description":      "05011",
        "insurance":             "03041",
        "payment_order":         "03031",
        "reference_gtd":         "09023",
        "svh_doc":               "09023",
        "certificate_origin":    "06019",
        "origin_certificate":    "06019",
        "license":               "01011",
        "permit":                "01999",
        "sanitary":              "07013",
        "veterinary":            "07012",
        "phytosanitary":         "07011",
        "conformity_declaration": "01191",
        "other":                 "09023",
    }
    _TRANSPORT_DOC_CODES = {
        "40": "02013",  # AWB
        "30": "02011",  # CMR
        "10": "02015",  # B/L
        "20": "02011",  # Railway
        "80": "02015",  # Inland waterway
    }
    _ORIGIN_CERT_CODES = {
        "CT-1":                  "06011",
        "Form A":                "06012",
        "EUR.1":                 "06013",
        "Declaration of Origin": "06021",
    }

    def _resolve_doc_code(doc_type: str, source_data) -> str:
        sd = to_dict(source_data) if source_data else {}
        if doc_type in ("transport", "transport_doc"):
            tt = str(sd.get("transport_type", ""))
            return _TRANSPORT_DOC_CODES.get(tt, "02091")
        if doc_type in ("origin_certificate", "certificate_origin"):
            ct = str(sd.get("certificate_type", ""))
            return _ORIGIN_CERT_CODES.get(ct, "06019")
        return _DOC_TYPE_CODES.get(doc_type, "09023")
    docs: list[dict] = []

    def _append_doc(
        *,
        doc_type: str,
        doc_code: str,
        doc_type_name: str,
        parsed_source,
        doc_number: str | None = None,
        doc_date: str | None = None,
    ):
        source_dict = to_dict(parsed_source)
        filename = source_dict.get("_filename")
        payload = document_payload(source_dict)
        if not filename and not doc_number and not payload:
            return
        docs.append({
            "doc_type": doc_type,
            "doc_code": doc_code,
            "doc_number": doc_number,
            "doc_date": doc_date,
            "doc_type_name": doc_type_name,
            "original_filename": filename,
            "mime_type": mimetypes.guess_type(filename or "")[0] or "application/pdf",
            "parsed_data": payload,
        })

    _append_doc(
        doc_type="invoice",
        doc_code=_DOC_TYPE_CODES["invoice"],
        doc_type_name="Инвойс (счёт-фактура)",
        parsed_source=inv,
        doc_number=inv.get("invoice_number"),
        doc_date=inv.get("invoice_date"),
    )
    _append_doc(
        doc_type="contract",
        doc_code=_DOC_TYPE_CODES["contract"],
        doc_type_name="Контракт (договор)",
        parsed_source=contract,
        doc_number=contract.get("contract_number"),
        doc_date=contract.get("contract_date"),
    )

    transport_data = parsed_docs.get("transport") or {}
    _resolved_transport_code = _resolve_doc_code("transport_doc", transport_data)
    _TRANSPORT_DOC_NAMES = {
        "02013": "Авиационная накладная (AWB)",
        "02011": "Транспортная накладная (CMR)",
        "02015": "Коносамент (B/L)",
        "02091": "Транспортный документ",
    }
    _append_doc(
        doc_type="transport_doc",
        doc_code=_resolved_transport_code,
        doc_type_name=_TRANSPORT_DOC_NAMES.get(_resolved_transport_code, "Транспортный документ"),
        parsed_source=transport_data,
        doc_number=awb_number or transport_data.get("awb_number") or transport_data.get("vehicle_id"),
        doc_date=None,
    )

    packing_data = parsed_docs.get("packing") or {}
    _append_doc(
        doc_type="packing_list",
        doc_code=_DOC_TYPE_CODES["packing"],
        doc_type_name="Упаковочный лист",
        parsed_source=packing_data,
        doc_number=packing_data.get("packing_list_number") or packing_data.get("doc_number"),
        doc_date=packing_data.get("packing_list_date") or packing_data.get("doc_date"),
    )
    transport_inv_data = parsed_docs.get("transport_invoice") or {}
    _append_doc(
        doc_type="transport_invoice",
        doc_code=_DOC_TYPE_CODES["transport_invoice"],
        doc_type_name="Транспортный инвойс (фрахт)",
        parsed_source=transport_inv_data,
        doc_number=transport_inv_data.get("doc_number") or transport_inv_data.get("invoice_number"),
        doc_date=transport_inv_data.get("doc_date") or transport_inv_data.get("invoice_date"),
    )

    specification = parsed_docs.get("specification") or {}
    _append_doc(
        doc_type="specification",
        doc_code=_DOC_TYPE_CODES["specification"],
        doc_type_name="Спецификация",
        parsed_source=specification,
        doc_number=specification.get("doc_number"),
        doc_date=specification.get("doc_date"),
    )

    application_statement = parsed_docs.get("application_statement") or {}
    _append_doc(
        doc_type="application_statement",
        doc_code=_DOC_TYPE_CODES["application_statement"],
        doc_type_name="Заявка / поручение экспедитору",
        parsed_source=application_statement,
        doc_number=application_statement.get("doc_number"),
        doc_date=application_statement.get("doc_date"),
    )

    for tech_desc in parsed_docs.get("tech_descriptions") or []:
        _append_doc(
            doc_type="tech_description",
            doc_code=_DOC_TYPE_CODES["tech_description"],
            doc_type_name="Техническое описание",
            parsed_source=tech_desc,
            doc_number=tech_desc.get("doc_number"),
            doc_date=tech_desc.get("doc_date"),
        )

    for pay_order in parsed_docs.get("payment_orders") or []:
        _append_doc(
            doc_type="payment_order",
            doc_code=_DOC_TYPE_CODES["payment_order"],
            doc_type_name="Платёжное поручение",
            parsed_source=pay_order,
            doc_number=pay_order.get("doc_number"),
            doc_date=pay_order.get("doc_date"),
        )

    ref_gtd = parsed_docs.get("reference_gtd") or {}
    if ref_gtd:
        _append_doc(
            doc_type="reference_gtd",
            doc_code=_DOC_TYPE_CODES["reference_gtd"],
            doc_type_name="Эталонная ГТД (справочно)",
            parsed_source=ref_gtd,
            doc_number=ref_gtd.get("header", {}).get("customs_office_code"),
            doc_date=None,
        )

    svh = parsed_docs.get("svh_doc") or {}
    if svh:
        _append_doc(
            doc_type="svh_doc",
            doc_code=_DOC_TYPE_CODES["svh_doc"],
            doc_type_name="Документ СВХ",
            parsed_source=svh,
            doc_number=svh.get("svh_number"),
            doc_date=svh.get("placement_date"),
        )

    origin_cert = parsed_docs.get("origin_certificate") or {}
    if origin_cert:
        _cert_code = _resolve_doc_code("origin_certificate", origin_cert)
        _CERT_NAMES = {
            "06011": "Сертификат происхождения СТ-1",
            "06012": "Сертификат происхождения Form A",
            "06013": "Сертификат происхождения EUR.1",
            "06021": "Декларация о происхождении",
            "06019": "Сертификат происхождения",
        }
        _append_doc(
            doc_type="origin_certificate",
            doc_code=_cert_code,
            doc_type_name=_CERT_NAMES.get(_cert_code, "Сертификат происхождения"),
            parsed_source=origin_cert,
            doc_number=origin_cert.get("certificate_number"),
            doc_date=origin_cert.get("certificate_date"),
        )

    insurance_data = parsed_docs.get("insurance") or {}
    if insurance_data:
        _append_doc(
            doc_type="insurance",
            doc_code=_DOC_TYPE_CODES["insurance"],
            doc_type_name="Страховой полис / сертификат",
            parsed_source=insurance_data,
            doc_number=insurance_data.get("policy_number"),
            doc_date=insurance_data.get("issue_date"),
        )

    for conf_decl in parsed_docs.get("conformity_declarations") or []:
        _append_doc(
            doc_type="conformity_declaration",
            doc_code=_DOC_TYPE_CODES["conformity_declaration"],
            doc_type_name="Декларация о соответствии ЕАЭС",
            parsed_source=conf_decl,
            doc_number=conf_decl.get("declaration_number"),
            doc_date=conf_decl.get("registration_date"),
        )

    return docs

# ------------------------------------------------------------------
# Declaration compilation (delegated to declaration_compiler.py)
# ------------------------------------------------------------------

def _compile_declaration_llm(self, parsed_docs: dict) -> dict:
    from app.services.declaration_compiler import compile_declaration
    return compile_declaration(parsed_docs)



def distribute_weights(items: list, packing: dict | None, invoice: dict | None) -> list:
    """Distribute weights from PL to items, fallback to proportional by cost."""
    if not items:
        return items

    packing = packing or {}
    invoice = invoice or {}
    pl_items = packing.get("items") or []

    def _desc_similarity(a: str, b: str) -> float:
        wa = set(re.sub(r'[^a-zа-я0-9]', ' ', (a or "").lower()).split())
        wb = set(re.sub(r'[^a-zа-я0-9]', ' ', (b or "").lower()).split())
        if not wa or not wb:
            return 0.0
        return len(wa & wb) / max(len(wa), len(wb))

    pl_items_with_weights = [
        it for it in pl_items
        if _safe_float(it.get("gross_weight")) or _safe_float(it.get("net_weight"))
    ]

    weights_assigned = 0
    used_indices: set = set()

    if pl_items_with_weights:
        if len(pl_items_with_weights) == len(items):
            for j, item in enumerate(items):
                pl_it = pl_items_with_weights[j]
                pg = _safe_float(pl_it.get("gross_weight"))
                pn = _safe_float(pl_it.get("net_weight"))
                if pg and not item.get("gross_weight"):
                    item["gross_weight"] = round(pg, 3)
                if pn and not item.get("net_weight"):
                    item["net_weight"] = round(pn, 3)
                if pg or pn:
                    weights_assigned += 1
        else:
            for item in items:
                best_score, best_match = 0.3, None
                for idx, pl_it in enumerate(pl_items_with_weights):
                    if idx in used_indices:
                        continue
                    sim = _desc_similarity(item.get("description", ""), pl_it.get("description", ""))
                    if sim > best_score:
                        best_score = sim
                        best_match = (idx, pl_it)
                if best_match:
                    idx, pl_it = best_match
                    used_indices.add(idx)
                    pg = _safe_float(pl_it.get("gross_weight"))
                    pn = _safe_float(pl_it.get("net_weight"))
                    if pg and not item.get("gross_weight"):
                        item["gross_weight"] = round(pg, 3)
                    if pn and not item.get("net_weight"):
                        item["net_weight"] = round(pn, 3)
                    if pg or pn:
                        weights_assigned += 1

    # Packaging from PL
    pl_pkg_items = [it for it in pl_items if it.get("packages_count") or it.get("package_type")]
    if pl_pkg_items and items:
        if len(pl_pkg_items) == len(items):
            for j, item in enumerate(items):
                pl_it = pl_pkg_items[j]
                if not item.get("package_count"):
                    item["package_count"] = pl_it.get("packages_count")
                if not item.get("package_type"):
                    item["package_type"] = pl_it.get("package_type") or packing.get("package_type")
    if packing.get("package_type"):
        for item in items:
            if not item.get("package_type"):
                item["package_type"] = packing["package_type"]

    # Fallback: proportional by cost
    total_gross = _safe_float(
        packing.get("total_gross_weight") or
        (invoice.get("total_gross_weight") if invoice else None)
    )
    total_net = _safe_float(
        packing.get("total_net_weight") or
        (invoice.get("total_net_weight") if invoice else None)
    )
    items_missing_weight = [it for it in items if not it.get("gross_weight")]
    if items_missing_weight and total_gross:
        assigned_gross = sum((_safe_float(it.get("gross_weight")) or 0.0) for it in items if it.get("gross_weight"))
        assigned_net = sum((_safe_float(it.get("net_weight")) or 0.0) for it in items if it.get("net_weight"))
        remaining_gross = max(0.0, (total_gross or 0.0) - assigned_gross)
        remaining_net = max(0.0, (total_net or 0.0) - assigned_net) if total_net else None

        total_price = sum((_safe_float(it.get("line_total")) or 0.0) for it in items_missing_weight)
        for item in items_missing_weight:
            price = _safe_float(item.get("line_total")) or 0.0
            share = (price / total_price) if total_price > 0 else (1.0 / len(items_missing_weight))
            item["gross_weight"] = round(remaining_gross * share, 3)
            if remaining_net:
                item["net_weight"] = round(remaining_net * share, 3)
            elif item.get("gross_weight"):
                item["net_weight"] = round(item["gross_weight"] * 0.9, 3)

    # Net weight fallback from gross
    for item in items:
        if item.get("gross_weight") and not item.get("net_weight"):
            item["net_weight"] = round(_safe_float(item["gross_weight"]) * 0.9, 3)

    return items



def enrich_evidence_map(result: dict, parsed_docs: dict, inco_src: str) -> dict:
    """Fill gaps in evidence_map so every field with a value has a source."""
    ev = dict(result.get("evidence_map") or {})

    _KEY_RENAMES = {
        "transport_vehicle_border": "border_vehicle_info",
        "transport_vehicle_departure": "departure_vehicle_info",
        "transport_vehicle_border_country": "border_vehicle_country",
        "transport_vehicle_departure_country": "departure_vehicle_country",
        "transport_type_internal": "transport_type_inland",
    }
    for old_key, new_key in _KEY_RENAMES.items():
        if old_key in ev and new_key not in ev:
            ev[new_key] = ev.pop(old_key)
        elif old_key in ev:
            del ev[old_key]

    def _add(field: str, source: str, confidence: float,
             graph: int | None = None, note: str = ""):
        if result.get(field) is None or field in ev:
            return
        entry: dict = {
            "value_preview": str(result[field])[:120],
            "source": source,
            "confidence": confidence,
        }
        if graph:
            entry["graph"] = graph
        if note:
            entry["note"] = note
        ev[field] = entry

    transport_d = to_dict(parsed_docs.get("transport"))

    _add("exchange_rate", "heuristic", 0.99, 23, "Курс ЦБ РФ")
    _add("total_customs_value", "aggregated_items", 0.95, 12, "Рассчитано из позиций")
    _add("total_gross_weight", "aggregated_items", 0.95, 35, "Сумма из позиций")
    _add("total_net_weight", "aggregated_items", 0.95, 38, "Сумма из позиций")
    _add("total_items_count", "heuristic", 1.0, 5, "Количество позиций")
    _add("total_sheets", "heuristic", 1.0, 3)
    _add("preference_code", "heuristic", 0.7, 36, "По умолчанию")
    _add("country_origin", "aggregated_items", 0.9, 16, "Из позиций")

    if result.get("incoterms") and "incoterms" not in ev:
        ev["incoterms"] = {
            "value_preview": str(result["incoterms"])[:120],
            "source": inco_src if inco_src != "none" else "heuristic",
            "confidence": 0.95 if inco_src != "none" else 0.5,
            "graph": 20,
        }
    if result.get("delivery_place") and "delivery_place" not in ev:
        dp_src = inco_src if inco_src != "none" else (
            "transport_doc" if transport_d else "heuristic"
        )
        ev["delivery_place"] = {
            "value_preview": str(result["delivery_place"])[:120],
            "source": dp_src,
            "confidence": 0.85,
            "graph": 20,
        }

    _add("customs_office_code", "heuristic", 0.9, 29, "Определён по IATA-коду")
    _add("goods_location", "heuristic", 0.9, 30, "Определён по IATA-коду")

    _add("invoice_number", "invoice", 0.95, 44)
    _add("invoice_date", "invoice", 0.95, 44)
    _add("contract_number", "contract", 0.95, 44)
    _add("contract_date", "contract", 0.95, 44)
    _add("total_amount", "invoice", 0.9, 22)
    _add("transport_doc_number", "transport_doc", 0.9, 44)
    _add("freight_amount", "transport_invoice", 0.9)
    _add("freight_currency", "transport_invoice", 0.9)
    _add("deal_nature_code", "contract", 0.85, 24)
    _add("deal_specifics_code", "contract", 0.8, 24)
    _add("type_code", "heuristic", 0.99, 1)

    _add("border_vehicle_info", "transport_doc", 0.9, 21)
    _add("departure_vehicle_info", "transport_doc", 0.9, 18)
    _add("border_vehicle_country", "transport_doc", 0.9, 21)
    _add("departure_vehicle_country", "transport_doc", 0.9, 18)
    _add("transport_type", "transport_doc", 0.9, 25)
    _add("transport_type_inland", "transport_doc", 0.8, 26)

    _add("country_dispatch", "transport_doc", 0.9, 15)
    _add("country_destination", "transport_doc", 0.9, 17)
    _add("trading_partner_country", "contract", 0.9, 11)

    # ── Item-level evidence (гр. 31-46) ──
    items = result.get("items") or []
    if items:
        inv_data = to_dict(parsed_docs.get("invoice"))
        packing_data = to_dict(parsed_docs.get("packing"))
        has_inv = bool(inv_data)
        has_pl = bool(packing_data)

        _ITEM_EV = {
            "description": ("invoice", 0.85, 31),
            "country_origin_code": ("conformity_declaration", 0.85, 34),
            "gross_weight": ("packing_list" if has_pl else "invoice", 0.9, 35),
            "net_weight": ("packing_list" if has_pl else "invoice", 0.85, 38),
            "additional_unit_qty": ("invoice", 0.85, 41),
            "unit_price": ("invoice", 0.9, 42),
            "customs_value_rub": ("heuristic", 0.95, 45),
            "statistical_value_usd": ("heuristic", 0.95, 46),
            "hs_code": ("heuristic", 0.8, 33),
            "procedure_code": ("heuristic", 0.9, 37),
            "preference_code": ("heuristic", 0.7, 36),
        }
        first_item = items[0] if items else {}
        for field, (src, conf, graph) in _ITEM_EV.items():
            if first_item.get(field) is not None and field not in ev:
                note = ""
                if src == "heuristic" and field == "customs_value_rub":
                    note = "Рассчитано: цена × курс + фрахт"
                elif src == "heuristic" and field == "statistical_value_usd":
                    note = "Рассчитано: тамож. стоимость / курс USD"
                entry: dict = {
                    "value_preview": str(first_item[field])[:120],
                    "source": src,
                    "confidence": conf,
                    "graph": graph,
                }
                if note:
                    entry["note"] = note
                ev[field] = entry

    # ── Declarant / financial responsible (гр. 9, 14) ──
    contract_d = to_dict(parsed_docs.get("contract"))
    td_data = to_dict(parsed_docs.get("transport")) or to_dict(parsed_docs.get("transport_doc"))

    if result.get("declarant") and "declarant" not in ev:
        ev["declarant"] = {
            "value_preview": str(result["declarant"])[:120],
            "source": "contract" if contract_d else "transport_doc",
            "confidence": 0.9,
            "graph": 14,
        }
    if td_data and "declarant" not in ev:
        consignee = td_data.get("consignee_name") or td_data.get("consignee_inn")
        if consignee:
            ev["declarant"] = {
                "value_preview": str(consignee)[:120],
                "source": "transport_doc",
                "confidence": 0.85,
                "graph": 14,
                "note": "Грузополучатель из AWB",
            }

    if "financial_responsible" not in ev and "responsible_person" not in ev:
        src = "contract" if contract_d else "transport_doc"
        ev["financial_responsible"] = {
            "value_preview": result.get("financial_responsible", result.get("buyer", {})
                if isinstance(result.get("buyer"), dict) else ""),
            "source": src,
            "confidence": 0.85,
            "graph": 9,
        }

    result["evidence_map"] = ev
    logger.info("evidence_map_enriched", total_entries=len(ev),
                 keys=sorted(ev.keys()))
    return result



def post_process_compilation(llm_result: dict, parsed_docs: dict,
                             match_items_to_techop=None) -> dict:
    """Deterministic post-processing after LLM compilation.

    Handles: IATA lookups, weight distribution, summing, normalization,
    item filtering, sheet count, description formatting.

    match_items_to_techop: optional callable(invoice_items, tech_products) -> items
    for LLM-based techop matching (passed from DeclarationCrew).
    """
    import math
    result = dict(llm_result)

    # ── IATA -> customs office lookup (гр. 29, 30) ──
    destination_airport = (result.get("destination_airport") or "").upper().strip()
    if not destination_airport:
        awb = result.get("transport_doc_number") or ""
        for doc_key in ("transport", "transport_doc"):
            td = to_dict(parsed_docs.get(doc_key))
            if td:
                destination_airport = (td.get("destination_airport") or "").upper().strip()
                if destination_airport:
                    break

    customs_office_code = result.get("customs_office_code")
    customs_office_name = result.get("customs_office_name")
    goods_location = result.get("goods_location")

    from app.services.reference_data import lookup_customs_office
    awb_number = result.get("transport_doc_number") or ""
    transport_type = result.get("transport_type")
    resolved = lookup_customs_office(
        iata_code=destination_airport,
        awb_prefix=awb_number,
        transport_type=transport_type,
    )
    if resolved:
        customs_office_code, customs_office_name, goods_location = resolved

    result["customs_office_code"] = customs_office_code
    result["customs_office_name"] = customs_office_name
    result["goods_location"] = goods_location

    # ── Transport vehicle info (гр. 18, 21, 44) from parsed docs ──
    td = to_dict(parsed_docs.get("transport")) or to_dict(parsed_docs.get("transport_doc"))
    if td:
        flight = td.get("flight_number") or td.get("flight_no") or ""
        awb = td.get("awb_number") or td.get("transport_doc_number") or ""
        vehicle_country = td.get("vehicle_country_code") or td.get("departure_country") or ""

        if flight and not result.get("departure_vehicle_info"):
            result["departure_vehicle_info"] = flight
        if flight and not result.get("border_vehicle_info"):
            result["border_vehicle_info"] = flight
        if awb and not result.get("transport_doc_number"):
            result["transport_doc_number"] = awb
        if vehicle_country and not result.get("departure_vehicle_country"):
            result["departure_vehicle_country"] = vehicle_country[:2].upper()
        if vehicle_country and not result.get("border_vehicle_country"):
            result["border_vehicle_country"] = vehicle_country[:2].upper()

    # ── Items processing ──
    items = result.get("items") or []
    inv_data = to_dict(parsed_docs.get("invoice"))
    packing_data = to_dict(parsed_docs.get("packing"))
    pl_items = (packing_data.get("items") or []) if packing_data else []

    inv_items = inv_data.get("items", []) if inv_data else []
    if inv_items and len(items) != len(inv_items):
        logger.warning(
            "items_count_mismatch_llm_vs_invoice",
            llm_count=len(items),
            invoice_count=len(inv_items),
            msg="LLM вернул другое количество позиций, чем в инвойсе — "
                "принудительно используем позиции из инвойса",
        )
        items = list(inv_items)

    _SKIP_ITEM = re.compile(
        r'\b(freight|shipping|insurance|handling|delivery\s*fee|transport.*fee|'
        r'фрахт|доставка|страхов|транспортн)',
        re.IGNORECASE,
    )

    filtered_items = []
    for item in items:
        desc = item.get("description") or ""
        if _SKIP_ITEM.search(desc):
            continue
        if _is_garbage_desc(desc):
            continue
        item["hs_code"] = _normalize_hs_code(item.get("hs_code"))
        co = (item.get("country_origin_code") or "")
        if co:
            item["country_origin_code"] = co.strip().upper()[:2]
        filtered_items.append(item)
    items = filtered_items

    # ── Deduplication: LLM may create duplicates from invoice + packing list ──
    if len(items) > 1:
        def _dedup_key(it: dict) -> str:
            d = re.sub(r'[^a-zа-я0-9]', '', (it.get("description") or "").lower())
            return d

        seen_keys: dict[str, int] = {}
        deduplicated: list[dict] = []
        for item in items:
            key = _dedup_key(item)
            if not key:
                deduplicated.append(item)
                continue
            prev_idx = seen_keys.get(key)
            if prev_idx is not None:
                prev = deduplicated[prev_idx]
                prev_lt = _safe_float(prev.get("line_total")) or 0.0
                cur_lt = _safe_float(item.get("line_total")) or 0.0
                prev_up = _safe_float(prev.get("unit_price")) or 0.0
                cur_up = _safe_float(item.get("unit_price")) or 0.0
                if (prev_lt > 0 and cur_lt > 0 and abs(prev_lt - cur_lt) / max(prev_lt, cur_lt) < 0.05) or \
                   (prev_up > 0 and cur_up > 0 and abs(prev_up - cur_up) / max(prev_up, cur_up) < 0.05) or \
                   (prev_lt == 0 and cur_lt == 0):
                    for f in ("gross_weight", "net_weight", "package_count", "package_type"):
                        if item.get(f) and not prev.get(f):
                            prev[f] = item[f]
                    logger.warning("duplicate_item_removed",
                                   description=(item.get("description") or "")[:60],
                                   msg="Дубль позиции удалён (совпадение описания + цены)")
                    continue
            seen_keys[key] = len(deduplicated)
            deduplicated.append(item)

        if len(deduplicated) < len(items):
            logger.info("items_deduplicated",
                        before=len(items), after=len(deduplicated))
            items = deduplicated

    result["items"] = items

    # ── Weight distribution (гр. 35/38) ──
    items = distribute_weights(items, packing_data, inv_data)
    result["items"] = items

    # ── Обогащение из техописаний (гр. 31, пункт 1) ──
    # Техописание — приоритетный источник наименования товара.
    # Вызываем ПОСЛЕ распределения весов (которое матчит по invoice-описаниям),
    # но ДО форматирования description (пункт 1 + пункт 2).
    tech_descs = parsed_docs.get("tech_descriptions", [])
    if tech_descs and items:
        all_tech_products = []
        for td in tech_descs:
            if isinstance(td, dict):
                all_tech_products.extend(td.get("products", []))
        if all_tech_products and match_items_to_techop:
            logger.info("techop_match_start_postprocess",
                        items=len(items), tech_products=len(all_tech_products))
            items = match_items_to_techop(items, all_tech_products)
            result["items"] = items
            for item in items:
                if item.get("description_source") != "tech_description":
                    logger.warning(
                        "techop_no_match_for_item",
                        description=(item.get("description") or "")[:60],
                        msg="Граф 31: наименование из инвойса (тех.описание не совпало) — требует проверки",
                    )
        else:
            logger.warning("techop_no_products",
                           msg="Граф 31: техописания загружены, но products[] пуст")
    else:
        if not tech_descs:
            logger.warning("techop_missing_postprocess",
                           msg="Граф 31: документ «Техническое описание» не загружен — "
                               "наименования берутся из инвойса")

    # ── Fallback: обогащение из деклараций соответствия ──
    conf_decls = parsed_docs.get("conformity_declarations", [])
    if conf_decls and items:
        for item in items:
            needs_enrichment = not any(item.get(f) for f in
                ("manufacturer", "trademark", "model_name", "brand", "model"))
            if not needs_enrichment:
                continue
            best_cd = None
            for cd in conf_decls:
                if not isinstance(cd, dict):
                    continue
                if cd.get("manufacturer_name") or cd.get("product_name"):
                    best_cd = cd
                    break
            if not best_cd:
                continue
            if not item.get("manufacturer") and best_cd.get("manufacturer_name"):
                item["manufacturer"] = best_cd["manufacturer_name"]
            if not item.get("brand") and not item.get("trademark"):
                val = best_cd.get("brand") or ""
                if val:
                    item["brand"] = val
                    item["trademark"] = val
            if not item.get("model") and not item.get("model_name"):
                val = best_cd.get("model") or ""
                if val:
                    item["model"] = val
                    item["model_name"] = val
            if not item.get("article_number") and best_cd.get("article_number"):
                item["article_number"] = best_cd["article_number"]
            if not item.get("serial_numbers") and not item.get("serial_number"):
                val = best_cd.get("serial_numbers") or ""
                if val:
                    item["serial_numbers"] = val
                    item["serial_number"] = val
            if not item.get("commercial_name") or item.get("commercial_name") == item.get("description_invoice", ""):
                pn = best_cd.get("product_name") or ""
                if pn:
                    item["commercial_name"] = pn
            logger.info("conformity_fallback_applied",
                        item_desc=(item.get("description") or "")[:40],
                        manufacturer=item.get("manufacturer", ""),
                        source=best_cd.get("_filename", "conformity_declaration"))

    # ── Sum totals ──
    total_gross = sum(_safe_float(it.get("gross_weight")) or 0.0 for it in items)
    total_net = sum(_safe_float(it.get("net_weight")) or 0.0 for it in items)
    if total_gross > 0:
        result["total_gross_weight"] = round(total_gross, 3)
    if total_net > 0:
        result["total_net_weight"] = round(total_net, 3)

    total_invoice = sum(_safe_float(it.get("line_total")) or 0.0 for it in items)
    invoice_total_amount = _safe_float(result.get("total_amount")) or 0.0

    if total_invoice > 0 and invoice_total_amount > 0:
        diff = abs(total_invoice - invoice_total_amount)
        threshold = max(invoice_total_amount, total_invoice) * 0.01
        if diff > threshold:
            logger.warning(
                "graph22_vs_graph42_mismatch",
                sum_items=round(total_invoice, 2),
                invoice_total=round(invoice_total_amount, 2),
                diff=round(diff, 2),
                msg=(
                    f"Графа 22: сумма позиций (гр.42) = {round(total_invoice, 2)} "
                    f"≠ итогу инвойса = {round(invoice_total_amount, 2)}, "
                    f"расхождение {round(diff, 2)}"
                ),
            )
            result.setdefault("issues", []).append({
                "id": "graph22_vs_graph42_mismatch",
                "severity": "warning",
                "graph": 22,
                "field": "total_amount",
                "message": (
                    f"Графа 22: рассчитанная сумма позиций (∑ гр.42) = {round(total_invoice, 2)} "
                    f"не совпадает с итоговой суммой инвойса = {round(invoice_total_amount, 2)}. "
                    f"Расхождение: {round(diff, 2)}. Проверьте позиции и итог инвойса."
                ),
            })
        result["total_amount"] = round(total_invoice, 2)
    elif total_invoice > 0:
        result["total_amount"] = round(total_invoice, 2)
        logger.info("graph22_from_items_sum", total=round(total_invoice, 2),
                    msg="Графа 22: итог инвойса отсутствует, сумма рассчитана из позиций")

    # ── Exchange rate (гр. 23) ──
    currency = (result.get("currency") or "").upper()
    exchange_rate = 0.0
    usd_rate = 0.0
    calc_debug = {}
    if currency and currency != "RUB":
        rates = _fetch_exchange_rates()
        exchange_rate = rates.get(currency, 0.0)
        usd_rate = rates.get("USD", 0.0)
        if exchange_rate > 0:
            result["exchange_rate"] = round(exchange_rate, 4)
            result["exchange_rate_currency"] = currency
            calc_debug["exchange_rate"] = exchange_rate
            calc_debug["usd_rate"] = usd_rate
            logger.info("exchange_rate_fetched", currency=currency, rate=exchange_rate)
        else:
            logger.warning("exchange_rate_not_found", currency=currency)
    elif currency == "RUB":
        exchange_rate = 1.0
        result["exchange_rate"] = 1.0
        result["exchange_rate_currency"] = "RUB"

    # ── Customs value (гр. 45) + freight distribution ──
    freight_amount = _safe_float(result.get("freight_amount")) or 0.0
    freight_currency = (result.get("freight_currency") or currency or "").upper()
    freight_rub = 0.0

    if freight_amount > 0 and exchange_rate > 0:
        if freight_currency == currency:
            freight_rub = freight_amount * exchange_rate
        elif freight_currency == "RUB":
            freight_rub = freight_amount
        else:
            rates = rates if 'rates' in dir() else _fetch_exchange_rates()
            fr_rate = rates.get(freight_currency, exchange_rate)
            freight_rub = freight_amount * fr_rate

    if exchange_rate > 0 and items:
        freight_distributed = []
        for item in items:
            line_total = _safe_float(item.get("line_total")) or 0.0
            item_value_rub = line_total * exchange_rate

            item_freight = 0.0
            if freight_rub > 0 and total_gross > 0:
                item_gross = _safe_float(item.get("gross_weight")) or 0.0
                item_freight = freight_rub * (item_gross / total_gross) if item_gross > 0 else 0.0
                item_value_rub += item_freight

            if item_value_rub > 0:
                item["customs_value_rub"] = round(item_value_rub, 2)
                freight_distributed.append({
                    "description": (item.get("description") or "")[:60],
                    "line_total_fcy": line_total,
                    "line_total_rub": round(line_total * exchange_rate, 2),
                    "freight_share_rub": round(item_freight, 2),
                    "customs_value_rub": round(item_value_rub, 2),
                })

        total_customs_value = sum(_safe_float(it.get("customs_value_rub")) or 0.0 for it in items)
        if total_customs_value > 0:
            result["total_customs_value"] = round(total_customs_value, 2)

        calc_debug["freight_rub"] = round(freight_rub, 2) if freight_rub > 0 else 0
        calc_debug["freight_distribution"] = freight_distributed
        calc_debug["total_customs_value"] = round(total_customs_value, 2)

        # ── Statistical value (гр. 46) ──
        if usd_rate <= 0 and currency != "USD":
            rates = _fetch_exchange_rates() if 'rates' not in dir() else rates
            usd_rate = rates.get("USD", 0.0)
        elif currency == "USD":
            usd_rate = exchange_rate

        if usd_rate > 0:
            for item in items:
                cv = _safe_float(item.get("customs_value_rub")) or 0.0
                if cv > 0:
                    item["statistical_value_usd"] = round(cv / usd_rate, 2)

            total_stat = sum(_safe_float(it.get("statistical_value_usd")) or 0.0 for it in items)
            if total_stat > 0:
                result["total_statistical_value"] = round(total_stat, 2)
            calc_debug["total_statistical_value"] = round(total_stat, 2) if total_stat > 0 else 0

        logger.info("customs_values_calculated",
                    total_customs_value=result.get("total_customs_value"),
                    total_statistical_value=result.get("total_statistical_value"))

    # ── Preference code (гр. 36) ──
    origin_cert = parsed_docs.get("origin_certificate")
    cert_type = None
    trade_agreement = None
    if origin_cert and isinstance(origin_cert, dict):
        cert_type = origin_cert.get("certificate_type")
        trade_agreement = origin_cert.get("trade_agreement")

    preference_code = _determine_preference_code(cert_type, trade_agreement)
    result["preference_code"] = preference_code
    calc_debug["preference_code"] = preference_code
    calc_debug["origin_certificate_type"] = cert_type

    # ── Classifier validation (countries, currency, transport, procedure) ──
    from app.services.classifier_cache import get_cache as _get_clf_cache
    _clf = _get_clf_cache()
    issues = result.get("issues") or []

    _COUNTRY_FIELDS = (
        "country_dispatch", "country_destination", "country_origin",
        "trading_partner_country", "departure_vehicle_country",
        "border_vehicle_country",
    )
    for _cf in _COUNTRY_FIELDS:
        _cv = result.get(_cf)
        if _cv and isinstance(_cv, str) and _cv not in ("РАЗНЫЕ", "НЕИЗВЕСТНО", "ЕВРОСОЮЗ", "EU"):
            resolved = _clf.lookup_code("country", _cv)
            if resolved:
                result[_cf] = resolved
            elif len(_cv) == 2 and _cv.upper().isalpha():
                result[_cf] = _cv.upper()
            else:
                issues.append({
                    "id": f"unknown_country_{_cf}",
                    "severity": "warning",
                    "message": f"Неизвестный код страны '{_cv}' в поле {_cf}",
                })

    _cur = result.get("currency")
    if _cur and not _clf.validate_code("currency", _cur):
        resolved_cur = _clf.lookup_code("currency", _cur)
        if resolved_cur:
            result["currency"] = resolved_cur
        else:
            issues.append({
                "id": "unknown_currency",
                "severity": "warning",
                "message": f"Неизвестный код валюты: {_cur}",
            })

    _tt = result.get("transport_type")
    if _tt and not _clf.validate_code("transport_type", str(_tt)):
        issues.append({
            "id": "unknown_transport_type",
            "severity": "warning",
            "message": f"Неизвестный код вида транспорта: {_tt}",
        })

    for _item in items:
        _ico = (_item.get("country_origin_code") or "").strip().upper()
        if _ico and len(_ico) == 2:
            _item["country_origin_code"] = _ico
        elif _ico:
            _resolved_co = _clf.lookup_code("country", _ico)
            if _resolved_co:
                _item["country_origin_code"] = _resolved_co

    result["issues"] = issues

    # ── Инкотермс (гр. 20): детерминированная логика приоритетов ──
    # Приоритет: 1) заявка, 2) контракт, 3) спецификация.
    # Инвойс НЕ является источником. Если LLM уже вернул — перезаписываем
    # по строгому приоритету из extracted data, чтобы исключить ошибки LLM.
    application_d = to_dict(parsed_docs.get("application_statement"))
    contract_d = to_dict(parsed_docs.get("contract"))
    spec_d = to_dict(parsed_docs.get("specification"))
    transport_d = to_dict(parsed_docs.get("transport"))

    app_inco = application_d.get("incoterms") if application_d else None
    contract_inco = contract_d.get("incoterms") if contract_d else None
    spec_inco = spec_d.get("incoterms") if spec_d else None

    if app_inco:
        result["incoterms"] = app_inco
        inco_src = "application_statement"
    elif contract_inco:
        result["incoterms"] = contract_inco
        inco_src = "contract"
    elif spec_inco:
        result["incoterms"] = spec_inco
        inco_src = "specification"
    else:
        inco_src = "none"

    dp_val = (
        application_d.get("delivery_place") if application_d else None
    ) or (
        contract_d.get("delivery_place") if contract_d else None
    ) or (
        spec_d.get("delivery_place") if spec_d else None
    )

    _COUNTRY_ONLY = {
        "china", "cn", "hong kong", "hk", "taiwan", "tw",
        "korea", "kr", "japan", "jp", "india", "in",
        "turkey", "tr", "germany", "de", "italy", "it",
        "usa", "us", "russia", "ru", "vietnam", "vn",
        "thailand", "th", "indonesia", "id", "malaysia", "my",
        "китай", "гонконг", "тайвань", "корея", "япония",
        "индия", "турция", "германия", "италия", "россия",
    }

    _DESTINATION_CITIES_RU = {
        "moscow", "москва", "svo", "dme", "vko", "zia",
        "saint-petersburg", "санкт-петербург", "led", "пулково",
        "novosibirsk", "новосибирск", "ovb",
        "vladivostok", "владивосток", "vvo",
        "ekaterinburg", "екатеринбург", "svx",
        "kazan", "казань", "kzn",
        "krasnodar", "краснодар", "krr",
    }

    _SELLER_TERMS = {"EXW", "FCA", "FAS", "FOB"}

    from app.services.reference_data import resolve_iata_city as _resolve_iata

    transport_departure = (
        (transport_d.get("departure_airport") if transport_d else None)
        or (transport_d.get("departure_point") if transport_d else None)
        or ""
    )
    if transport_departure:
        transport_departure = _resolve_iata(transport_departure)

    inco_code = (result.get("incoterms") or "").upper().strip()

    if dp_val and dp_val.strip().lower() in _COUNTRY_ONLY and transport_departure:
        logger.info("delivery_place_refined", original=dp_val, refined=transport_departure)
        dp_val = transport_departure
    elif dp_val and inco_code in _SELLER_TERMS and dp_val.strip().lower() in _DESTINATION_CITIES_RU:
        logger.warning("delivery_place_is_destination",
                       incoterms=inco_code, wrong_place=dp_val,
                       transport_departure=transport_departure or None,
                       msg=f"Графа 20: для {inco_code} место поставки должно быть "
                           f"городом ПРОДАВЦА, а не назначения ('{dp_val}')")
        if transport_departure:
            dp_val = transport_departure
        else:
            dp_val = None
    elif not dp_val and transport_departure:
        dp_val = transport_departure

    if dp_val:
        dp_val = _resolve_iata(dp_val)
        result["delivery_place"] = dp_val
    elif result.get("delivery_place") and inco_code in _SELLER_TERMS:
        llm_dp = result["delivery_place"].strip().lower()
        if llm_dp in _DESTINATION_CITIES_RU:
            logger.warning("delivery_place_llm_destination_removed",
                           incoterms=inco_code,
                           removed=result["delivery_place"],
                           msg=f"LLM указал '{result['delivery_place']}' как пункт поставки "
                               f"для {inco_code} — это город назначения, удалён")
            result.pop("delivery_place", None)

    if result.get("incoterms"):
        logger.info("incoterms_postprocess",
                    incoterms=result["incoterms"],
                    delivery_place=result.get("delivery_place"),
                    source=inco_src)

    issues = result.get("issues") or []
    issues.append({
        "id": "preference_check",
        "severity": "warning",
        "graph": 36,
        "message": "Проверьте преференции (гр.36). Коды определены по умолчанию.",
    })
    result["issues"] = issues

    result["_calc_debug"] = calc_debug

    # ── Sheet count (гр. 3) ──
    n_items = len(items)
    if n_items > 0:
        total_sheets = 1 + math.ceil(max(0, n_items - 1) / 3) if n_items > 1 else 1
        result["total_sheets"] = total_sheets
        result["total_items_count"] = n_items

    # ── Description formatting (гр. 31) ──
    # Краткая форма в description (для ячейки ДТ),
    # полное описание из тех.описания в commercial_name (для дополнения к гр. 31, поле «наименование»).
    for item in items:
        full_desc = item.get("description") or ""
        hs_name = (item.get("hs_code_name") or "").strip().upper()

        if hs_name:
            short_name = hs_name
        else:
            short_name = full_desc[:200].upper()

        pc = item.get("package_count") or item.get("packages_count")
        pt = item.get("package_type") or ""
        pkg_line = ""
        if pc:
            pt_code = pt.upper() if pt else "PK"
            pkg_line = f"2-{pc}, {pt_code}-{pc}"

        if pkg_line:
            item["description"] = f"1-{short_name}\n{pkg_line}"
        else:
            item["description"] = f"1-{short_name}"

        # commercial_name = полное описание товара из тех. описания (без обрезки)
        if item.get("description_source") == "tech_description" and full_desc:
            item["commercial_name"] = full_desc
        elif not item.get("commercial_name"):
            item["commercial_name"] = full_desc

        if item.get("brand"):
            item.setdefault("trademark", item["brand"])
        if item.get("model"):
            item.setdefault("model_name", item["model"])
        if item.get("serial_numbers"):
            item.setdefault("serial_number", item["serial_numbers"])

        logger.debug("item_fields_after_format",
                     desc=(item.get("description") or "")[:50],
                     manufacturer=item.get("manufacturer"),
                     trademark=item.get("trademark"),
                     model_name=item.get("model_name"),
                     article=item.get("article_number"),
                     serial=item.get("serial_number"),
                     comm_name_len=len(item.get("commercial_name") or ""))

    # ── Country origin aggregation (гр. 16) ──
    from app.services.reference_data import get_eu_countries
    _EU_COUNTRIES = get_eu_countries()
    unique_origins = set()
    for it in items:
        co = (it.get("country_origin_code") or "").strip().upper()
        if co:
            unique_origins.add(co)
    if unique_origins:
        if len(unique_origins) == 1:
            result["country_origin"] = unique_origins.pop()
        elif unique_origins.issubset(_EU_COUNTRIES):
            result["country_origin"] = "EU"
        else:
            result["country_origin"] = "РАЗНЫЕ"

    # ── Documents list (гр. 44) ──
    if not result.get("documents"):
        result["documents"] = build_documents_list(
            parsed_docs,
            inv_data or {},
            to_dict(parsed_docs.get("contract")) or {},
            awb_number,
        )

    # ── Reference GTD enrichment ──
    ref_gtd = parsed_docs.get("reference_gtd")
    if ref_gtd and isinstance(ref_gtd, dict):
        gtd_items = ref_gtd.get("items", [])
        if gtd_items and items:
            for item in items:
                if item.get("hs_code"):
                    continue
                desc = (item.get("description") or "").lower()
                for g_item in gtd_items:
                    g_desc = (g_item.get("description") or "").lower()
                    if desc and g_desc and (desc[:30] in g_desc or g_desc[:30] in desc):
                        item["hs_code"] = _normalize_hs_code(g_item.get("hs_code"))
                        item["hs_confidence"] = 0.75
                        item["hs_reasoning"] = f"Из эталонной ГТД"
                        break

    # ── SVH data (гр. 30/49) ──
    svh_doc = parsed_docs.get("svh_doc")
    if svh_doc and isinstance(svh_doc, dict):
        svh_number = svh_doc.get("svh_number")
        if svh_number:
            result["warehouse_requisites"] = svh_number
            result["goods_location_svh_doc_id"] = svh_number
        if svh_doc.get("warehouse_name"):
            result["warehouse_name"] = svh_doc["warehouse_name"]

    # ── Evidence map enrichment ──
    result = enrich_evidence_map(result, parsed_docs, inco_src)

    return result

