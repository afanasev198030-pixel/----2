#!/usr/bin/env python3
"""
Загрузка PDF из папки dek/, распознавание через parse-smart и создание деклараций (from-parsed).
Запуск: из корня проекта, с сервером 82.148.28.122 и админом admin@customs.local / admin123.

  python scripts/load_dek_declarations.py
  BASE_URL=http://82.148.28.122 python scripts/load_dek_declarations.py
"""
import os
import sys
import json
import requests
from pathlib import Path

BASE_URL = os.environ.get("BASE_URL", "http://82.148.28.122")
DEK_DIR = Path(__file__).resolve().parent.parent / "dek"
LOGIN_EMAIL = os.environ.get("LOGIN_EMAIL", "admin@customs.local")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD", "admin123")


def login(session: requests.Session) -> str:
    r = session.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def get_pdf_folders():
    if not DEK_DIR.exists():
        return []
    return [d for d in DEK_DIR.iterdir() if d.is_dir()]


def pdfs_in_folder(folder: Path):
    return sorted(folder.glob("*.pdf")) + sorted(folder.glob("*.PDF"))


def parse_smart(session: requests.Session, pdf_paths: list[Path]) -> dict:
    files = []
    for p in pdf_paths:
        files.append(("files", (p.name, p.read_bytes(), "application/pdf")))
        print(f"    📄 {p.name}", flush=True)
    print(f"    ⏳ Отправка {len(files)} файлов на parse-smart...", flush=True)
    import time as _t
    t0 = _t.time()
    r = session.post(
        f"{BASE_URL}/api/v1/ai/parse-smart",
        files=files,
        timeout=600,
    )
    elapsed = _t.time() - t0
    print(f"    ⏱ Ответ за {elapsed:.1f}с (status={r.status_code})", flush=True)
    r.raise_for_status()
    return r.json()


def body_for_from_parsed(parsed: dict) -> dict:
    """Привести ответ parse-smart к телу ApplyParsedRequest."""
    items = []
    for i, it in enumerate(parsed.get("items") or []):
        items.append({
            "line_no": it.get("line_no") or i + 1,
            "description": it.get("description") or it.get("commercial_name") or "",
            "commercial_name": it.get("commercial_name") or it.get("description") or "",
            "quantity": it.get("quantity"),
            "unit": it.get("unit") or "pcs",
            "unit_price": it.get("unit_price"),
            "line_total": it.get("line_total"),
            "hs_code": (it.get("hs_code") or "")[:20],
            "hs_code_name": it.get("hs_code_name"),
            "country_origin_code": it.get("country_origin_code"),
            "gross_weight": it.get("gross_weight"),
            "net_weight": it.get("net_weight"),
        })
    seller = parsed.get("seller")
    buyer = parsed.get("buyer")
    return {
        "invoice_number": parsed.get("invoice_number"),
        "invoice_date": parsed.get("invoice_date"),
        "seller": {"name": seller.get("name"), "country_code": seller.get("country_code"), "address": seller.get("address"), "type": "seller"} if seller else None,
        "buyer": {"name": buyer.get("name"), "country_code": buyer.get("country_code"), "address": buyer.get("address"), "type": "buyer"} if buyer else None,
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
        "delivery_place": parsed.get("delivery_place"),
        "goods_location": parsed.get("goods_location"),
        "buyer_matches_declarant": parsed.get("buyer_matches_declarant", True),
        "responsible_person": parsed.get("responsible_person"),
        "responsible_person_matches_declarant": parsed.get("responsible_person_matches_declarant", True),
        "deal_nature_code": "01",
        "type_code": parsed.get("type_code") or "IM40",
        "freight_amount": parsed.get("freight_amount"),
        "freight_currency": parsed.get("freight_currency"),
        "items": items,
        "documents": parsed.get("documents") or [],
        "risk_score": parsed.get("risk_score"),
        "risk_flags": parsed.get("risk_flags"),
        "confidence": parsed.get("confidence"),
    }


def create_from_parsed(session: requests.Session, body: dict) -> dict:
    r = session.post(
        f"{BASE_URL}/api/v1/declarations/from-parsed",
        json=body,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def main():
    print(f"BASE_URL={BASE_URL}, dek={DEK_DIR}")
    folders = get_pdf_folders()
    if not folders:
        print("Папка dek/ или подпапки не найдены.")
        sys.exit(1)

    session = requests.Session()
    session.headers["Accept"] = "application/json"

    try:
        token = login(session)
        session.headers["Authorization"] = f"Bearer {token}"
        print("Логин OK")
    except Exception as e:
        print("Ошибка логина:", e)
        sys.exit(2)

    created = []
    for folder in folders:
        pdfs = pdfs_in_folder(folder)
        if not pdfs:
            print(f"  [{folder.name}] PDF не найдены, пропуск")
            continue
        print(f"\n[{folder.name}] PDF: {len(pdfs)} файлов")
        try:
            parsed = parse_smart(session, pdfs)
            items_count = len(parsed.get("items") or [])
            print(f"  Распознано: позиций={items_count}, confidence={parsed.get('confidence')}")
            body = body_for_from_parsed(parsed)
            resp = create_from_parsed(session, body)
            decl_id = resp.get("declaration_id")
            created.append((folder.name, decl_id, resp))
            print(f"  Создана декларация: {decl_id}, items_created={resp.get('items_created')}, counterparties={resp.get('counterparties_created')}")
        except requests.HTTPError as e:
            print(f"  Ошибка HTTP: {e.response.status_code} {e.response.text[:300]}")
        except Exception as e:
            print(f"  Ошибка: {e}")

    print(f"\nИтого создано деклараций: {len(created)}")
    for name, decl_id, _ in created:
        print(f"  {name} -> {BASE_URL}/declarations/{decl_id}/edit")
    return 0 if created else 1


if __name__ == "__main__":
    sys.exit(main())
