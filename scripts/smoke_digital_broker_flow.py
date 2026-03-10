#!/usr/bin/env python3
"""
Smoke test for the core digital broker flow:
parse-smart -> from-parsed -> pre-send-check -> validate/export XML.

By default the script cleans up the created draft declaration.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost")
AI_BASE_URL = os.environ.get("AI_BASE_URL", BASE_URL)
INTEGRATION_BASE_URL = os.environ.get("INTEGRATION_BASE_URL", BASE_URL)
DEK_DIR = Path(os.environ.get("DEK_DIR", Path(__file__).resolve().parent.parent / "dek"))
LOGIN_EMAIL = os.environ.get("LOGIN_EMAIL", "admin@customs.local")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD", "admin123")
SMOKE_LOG_PATH = Path(os.environ.get("SMOKE_LOG_PATH", "/tmp/digital_broker_smoke.log"))
REQUEST_TIMEOUT = int(os.environ.get("SMOKE_REQUEST_TIMEOUT", "60"))
LONG_REQUEST_TIMEOUT = int(os.environ.get("SMOKE_LONG_REQUEST_TIMEOUT", "120"))
PARSE_TIMEOUT = int(os.environ.get("SMOKE_PARSE_TIMEOUT", "900"))


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("digital_broker_smoke")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    try:
        SMOKE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(SMOKE_LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("failed to initialize file log at %s", SMOKE_LOG_PATH)

    return logger


logger = configure_logging()


def json_preview(data: Any, limit: int = 1200) -> str:
    text = json.dumps(data, ensure_ascii=False, default=str)
    return text[:limit]


def login(session: requests.Session) -> str:
    response = session.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    logger.info("login_ok email=%s", LOGIN_EMAIL)
    return token


def get_pdf_folders() -> list[Path]:
    if not DEK_DIR.exists():
        return []
    return sorted([path for path in DEK_DIR.iterdir() if path.is_dir()], key=lambda path: path.name)


def pdfs_in_folder(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.pdf")) + sorted(folder.glob("*.PDF"))


def split_input_and_reference_pdfs(folder: Path) -> tuple[list[Path], list[Path]]:
    input_pdfs: list[Path] = []
    reference_gtd_pdfs: list[Path] = []
    for pdf in pdfs_in_folder(folder):
        if pdf.name.upper().startswith("GTD"):
            reference_gtd_pdfs.append(pdf)
        else:
            input_pdfs.append(pdf)
    return input_pdfs, reference_gtd_pdfs


def body_for_from_parsed(parsed: dict) -> dict:
    items = []
    for i, item in enumerate(parsed.get("items") or []):
        items.append({
            "line_no": item.get("line_no") or i + 1,
            "description": item.get("description") or item.get("commercial_name") or "",
            "commercial_name": item.get("commercial_name") or item.get("description") or "",
            "quantity": item.get("quantity"),
            "unit": item.get("unit") or "pcs",
            "unit_price": item.get("unit_price"),
            "line_total": item.get("line_total"),
            "hs_code": (item.get("hs_code") or "")[:20],
            "hs_code_name": item.get("hs_code_name"),
            "country_origin_code": item.get("country_origin_code"),
            "gross_weight": item.get("gross_weight"),
            "net_weight": item.get("net_weight"),
        })

    seller = parsed.get("seller")
    buyer = parsed.get("buyer")
    return {
        "invoice_number": parsed.get("invoice_number"),
        "invoice_date": parsed.get("invoice_date"),
        "seller": {
            "name": seller.get("name"),
            "country_code": seller.get("country_code"),
            "address": seller.get("address"),
            "type": "seller",
        } if seller else None,
        "buyer": {
            "name": buyer.get("name"),
            "country_code": buyer.get("country_code"),
            "address": buyer.get("address"),
            "type": "buyer",
        } if buyer else None,
        "currency": parsed.get("currency"),
        "total_amount": parsed.get("total_amount"),
        "incoterms": parsed.get("incoterms"),
        "country_origin": parsed.get("country_origin"),
        "country_destination": parsed.get("country_destination") or "RU",
        "trading_partner_country": parsed.get("trading_partner_country"),
        "country_dispatch": parsed.get("country_dispatch"),
        "container": parsed.get("container"),
        "contract_number": parsed.get("contract_number"),
        "contract_date": parsed.get("contract_date"),
        "declarant_inn_kpp": parsed.get("declarant_inn_kpp"),
        "total_packages": parsed.get("total_packages"),
        "package_type": parsed.get("package_type"),
        "total_gross_weight": parsed.get("total_gross_weight"),
        "total_net_weight": parsed.get("total_net_weight"),
        "transport_type": parsed.get("transport_type") or "40",
        "transport_doc_number": parsed.get("transport_doc_number"),
        "transport_id": parsed.get("transport_id"),
        "transport_country_code": parsed.get("transport_country_code"),
        "customs_office_code": parsed.get("customs_office_code"),
        "delivery_place": parsed.get("delivery_place"),
        "goods_location": parsed.get("goods_location"),
        "buyer_matches_declarant": parsed.get("buyer_matches_declarant", True),
        "responsible_person": parsed.get("responsible_person"),
        "responsible_person_matches_declarant": parsed.get("responsible_person_matches_declarant", True),
        "deal_nature_code": parsed.get("deal_nature_code") or "01",
        "type_code": parsed.get("type_code") or "IM40",
        "freight_amount": parsed.get("freight_amount"),
        "freight_currency": parsed.get("freight_currency"),
        "items": items,
        "documents": parsed.get("documents") or [],
        "risk_score": parsed.get("risk_score"),
        "risk_flags": parsed.get("risk_flags"),
        "confidence": parsed.get("confidence"),
        "issues": parsed.get("issues") or [],
        "evidence_map": parsed.get("evidence_map") or {},
    }


def parse_smart(session: requests.Session, pdf_paths: list[Path]) -> dict:
    files = []
    handles = []
    try:
        for path in pdf_paths:
            handle = path.open("rb")
            handles.append(handle)
            files.append(("files", (path.name, handle, "application/pdf")))

        logger.info("parse_smart_start files=%s", [path.name for path in pdf_paths])
        response = session.post(
            f"{AI_BASE_URL}/api/v1/ai/parse-smart",
            files=files,
            timeout=PARSE_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        logger.info(
            "parse_smart_ok request_id=%s items=%s confidence=%s",
            data.get("request_id"),
            len(data.get("items") or []),
            data.get("confidence"),
        )
        return data
    finally:
        for handle in handles:
            handle.close()


def extract_gtd_references(session: requests.Session, pdf_paths: list[Path]) -> list[dict]:
    files = []
    handles = []
    try:
        for path in pdf_paths:
            handle = path.open("rb")
            handles.append(handle)
            files.append(("files", (path.name, handle, "application/pdf")))

        logger.info("extract_gtd_reference_start files=%s", [path.name for path in pdf_paths])
        response = session.post(
            f"{AI_BASE_URL}/api/v1/ai/extract-gtd-reference",
            files=files,
            timeout=PARSE_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        references = data.get("references") or []
        logger.info("extract_gtd_reference_ok files=%s", len(references))
        return references
    finally:
        for handle in handles:
            handle.close()


def normalize_hs(value: str | None) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) < 6:
        return ""
    return digits[:10].ljust(10, "0")


def compare_with_gtd_reference(parsed: dict, references: list[dict]) -> dict:
    parsed_items = sorted(parsed.get("items") or [], key=lambda item: item.get("line_no") or 0)
    reference_items: list[dict] = []
    reference_headers: list[dict] = []
    for ref in references:
        reference_headers.append(ref.get("header") or {})
        reference_items.extend(ref.get("items") or [])
    reference_items.sort(key=lambda item: item.get("line_no") or 0)

    parsed_hs = [normalize_hs(item.get("hs_code")) for item in parsed_items if normalize_hs(item.get("hs_code"))]
    reference_hs = [normalize_hs(item.get("hs_code")) for item in reference_items if normalize_hs(item.get("hs_code"))]
    exact_pairs = sum(1 for parsed_hs_code, reference_hs_code in zip(parsed_hs, reference_hs) if parsed_hs_code == reference_hs_code)

    reference_header = next((header for header in reference_headers if header), {})
    header_checks = []
    header_match_count = 0
    for field_name in ("country_dispatch", "country_destination", "currency", "transport_type", "customs_office_code"):
        reference_value = reference_header.get(field_name)
        if reference_value in (None, ""):
            continue
        parsed_value = parsed.get(field_name)
        matched = str(parsed_value or "").strip().upper() == str(reference_value).strip().upper()
        if matched:
            header_match_count += 1
        header_checks.append({
            "field": field_name,
            "parsed": parsed_value,
            "reference": reference_value,
            "matched": matched,
        })

    comparison = {
        "reference_items_count": len(reference_items),
        "parsed_items_count": len(parsed_items),
        "hs_exact_match_count": exact_pairs,
        "hs_exact_match_rate": round(exact_pairs / max(len(reference_hs), 1), 3),
        "missing_reference_hs": sorted(set(reference_hs) - set(parsed_hs)),
        "unexpected_parsed_hs": sorted(set(parsed_hs) - set(reference_hs)),
        "header_match_count": header_match_count,
        "header_checks": header_checks,
    }
    logger.info("gtd_reference_compare summary=%s", json_preview(comparison, limit=1500))
    return comparison


def create_from_parsed(session: requests.Session, body: dict) -> dict:
    logger.info("create_from_parsed_start")
    response = session.post(
        f"{BASE_URL}/api/v1/declarations/from-parsed",
        json=body,
        timeout=LONG_REQUEST_TIMEOUT,
    )
    if response.status_code >= 400:
        logger.error("create_from_parsed_failed status=%s body=%s", response.status_code, response.text[:2000])
    response.raise_for_status()
    data = response.json()
    logger.info("create_from_parsed_ok declaration_id=%s", data.get("declaration_id"))
    return data


def pre_send_check(session: requests.Session, declaration_id: str) -> dict:
    response = session.get(
        f"{BASE_URL}/api/v1/declarations/{declaration_id}/pre-send-check",
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    logger.info(
        "pre_send_check_ok declaration_id=%s passed=%s blocking=%s",
        declaration_id,
        data.get("passed"),
        data.get("blocking_count"),
    )
    return data


def validate_xml(session: requests.Session, declaration_id: str) -> dict:
    response = session.get(
        f"{INTEGRATION_BASE_URL}/api/v1/integration/validate-xml/{declaration_id}",
        timeout=LONG_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    logger.info(
        "validate_xml_ok declaration_id=%s valid=%s errors=%s warnings=%s",
        declaration_id,
        data.get("valid"),
        len(data.get("errors") or []),
        len(data.get("warnings") or []),
    )
    return data


def export_xml(session: requests.Session, declaration_id: str) -> str:
    response = session.get(
        f"{INTEGRATION_BASE_URL}/api/v1/integration/export-xml/{declaration_id}",
        timeout=LONG_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    text = response.text
    logger.info("export_xml_ok declaration_id=%s bytes=%s", declaration_id, len(text))
    return text


def delete_declaration(session: requests.Session, declaration_id: str) -> None:
    response = session.delete(
        f"{BASE_URL}/api/v1/declarations/{declaration_id}",
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code not in (204, 404):
        response.raise_for_status()
    logger.info("delete_declaration_ok declaration_id=%s status=%s", declaration_id, response.status_code)


def pick_folder(preferred_folder: str | None) -> Path:
    folders = get_pdf_folders()
    if not folders:
        raise RuntimeError(f"Не найдены подпапки с PDF в {DEK_DIR}")
    if preferred_folder:
        candidate = DEK_DIR / preferred_folder
        if not candidate.exists():
            raise RuntimeError(f"Папка smoke-набора не найдена: {candidate}")
        return candidate
    return folders[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for digital broker core flow")
    parser.add_argument("--folder", help="Имя подпапки внутри dek/ для smoke-прогона")
    parser.add_argument("--keep-declaration", action="store_true", help="Не удалять созданную декларацию")
    parser.add_argument("--allow-blocking", action="store_true", help="Не падать на blocking issues pre-send")
    parser.add_argument("--compare-gtd", action="store_true", help="Сравнить parse-smart с GTD reference")
    parser.add_argument("--enforce-gtd", action="store_true", help="Падать при несовпадении с GTD reference")
    args = parser.parse_args()

    session = requests.Session()
    session.headers["Accept"] = "application/json"

    declaration_id: str | None = None
    folder = pick_folder(args.folder)
    input_pdfs, gtd_reference_pdfs = split_input_and_reference_pdfs(folder)
    if not input_pdfs:
        raise RuntimeError(f"В папке {folder} нет входных PDF для parse-smart после исключения GTD reference")

    logger.info(
        "smoke_start base_url=%s ai_base_url=%s integration_base_url=%s folder=%s log_path=%s gtd_references=%s",
        BASE_URL,
        AI_BASE_URL,
        INTEGRATION_BASE_URL,
        folder.name,
        SMOKE_LOG_PATH,
        [path.name for path in gtd_reference_pdfs],
    )

    try:
        token = login(session)
        session.headers["Authorization"] = f"Bearer {token}"

        parsed = parse_smart(session, input_pdfs)
        gtd_comparison = None
        if gtd_reference_pdfs and (args.compare_gtd or args.enforce_gtd):
            references = extract_gtd_references(session, gtd_reference_pdfs)
            gtd_comparison = compare_with_gtd_reference(parsed, references)
            if args.enforce_gtd and gtd_comparison["hs_exact_match_rate"] < 1.0:
                raise RuntimeError(f"GTD reference mismatch: {json_preview(gtd_comparison)}")
        body = body_for_from_parsed(parsed)
        created = create_from_parsed(session, body)
        declaration_id = created["declaration_id"]

        pre_send = pre_send_check(session, declaration_id)
        if pre_send.get("blocking_count") and not args.allow_blocking:
            raise RuntimeError(
                f"Pre-send check returned blocking issues: {json_preview(pre_send.get('checks') or [])}"
            )

        xml_validation = validate_xml(session, declaration_id)
        if not xml_validation.get("valid"):
            raise RuntimeError(
                f"XML validation failed: {json_preview(xml_validation)}"
            )

        xml_payload = export_xml(session, declaration_id)
        if "<" not in xml_payload[:20]:
            raise RuntimeError("Exported XML payload does not look like XML")

        summary = {
            "folder": folder.name,
            "input_files": [path.name for path in input_pdfs],
            "gtd_reference_files": [path.name for path in gtd_reference_pdfs],
            "declaration_id": declaration_id,
            "items_created": created.get("items_created"),
            "documents_linked": created.get("documents_linked"),
            "pre_send_passed": pre_send.get("passed"),
            "pre_send_blocking_count": pre_send.get("blocking_count"),
            "xml_valid": xml_validation.get("valid"),
            "xml_warnings": len(xml_validation.get("warnings") or []),
        }
        if gtd_comparison:
            summary["gtd_comparison"] = gtd_comparison
        logger.info("smoke_success summary=%s", json_preview(summary))
        print(json.dumps(summary, ensure_ascii=False))
        return 0

    except Exception as exc:
        logger.exception("smoke_failed error=%s", exc)
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1

    finally:
        if declaration_id and not args.keep_declaration:
            try:
                delete_declaration(session, declaration_id)
            except Exception as cleanup_error:
                logger.exception("cleanup_failed declaration_id=%s error=%s", declaration_id, cleanup_error)


if __name__ == "__main__":
    sys.exit(main())
