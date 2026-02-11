"""
Глубокая загрузка ТН ВЭД: все уровни (2→4→6→8→10 знаков) с classifikators.ru.
Параллельный рекурсивный обход с asyncio.Semaphore.

Запуск: python -u -m app.seeds.update_tnved_deep
"""
import asyncio
import re
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import httpx
from sqlalchemy import select, func
from app.database import async_sessionmaker
from app.models import Classifier

BASE_URL = "https://classifikators.ru/tnved"
GROUPS = [f"{i:02d}" for i in range(1, 98) if i != 77]

# Concurrency control
SEM = asyncio.Semaphore(10)
TOTAL_FETCHED = 0
TOTAL_REQUESTS = 0


def parse_child_codes(html: str, parent_code: str) -> list[dict]:
    """Parse child codes from classifikators.ru page."""
    codes = []
    pattern = re.findall(
        r'href="/tnved/(\d{4,10})"\s*[^>]*>([^<]+)<',
        html
    )
    seen = set()
    for code, name in pattern:
        name = name.strip()
        if name and len(name) > 2 and code.startswith(parent_code) and code not in seen:
            seen.add(code)
            codes.append({
                "code": code,
                "name_ru": name[:500],
                "parent_code": parent_code,
            })
    return codes


async def fetch_page(client: httpx.AsyncClient, code: str) -> str | None:
    """Fetch page with semaphore throttling."""
    global TOTAL_REQUESTS
    async with SEM:
        try:
            TOTAL_REQUESTS += 1
            r = await client.get(f"{BASE_URL}/{code}", timeout=20)
            if r.status_code == 200:
                return r.text
            return None
        except Exception:
            return None


async def fetch_children_recursive(client: httpx.AsyncClient, code: str) -> list[dict]:
    """Recursively fetch all child codes with parallel requests."""
    global TOTAL_FETCHED

    html = await fetch_page(client, code)
    if not html:
        return []

    children = parse_child_codes(html, code)
    all_codes = list(children)
    TOTAL_FETCHED += len(children)

    # For codes that are not 10-digit leaves, go deeper in parallel
    tasks = []
    for child in children:
        if len(child["code"]) < 10:
            tasks.append(fetch_children_recursive(client, child["code"]))

    if tasks:
        results = await asyncio.gather(*tasks)
        for r in results:
            all_codes.extend(r)

    return all_codes


async def fetch_group(client: httpx.AsyncClient, group_code: str) -> list[dict]:
    """Fetch entire group hierarchy."""
    html = await fetch_page(client, group_code)
    if not html:
        print(f"  Skip {group_code}: no response", flush=True)
        return []

    # Group name from title
    title_match = re.search(r'<title>.*?(\d{2})\s*[—–-]\s*(.+?)</title>', html, re.DOTALL)
    group_name = re.sub(r'<[^>]+>', '', title_match.group(2).strip()[:500]) if title_match else f"Группа {group_code}"

    all_codes = [{
        "code": group_code,
        "name_ru": group_name,
        "parent_code": None,
    }]

    # Get 4-digit positions from group page
    positions = parse_child_codes(html, group_code)
    all_codes.extend(positions)

    # Go deeper for each 4-digit code in parallel
    tasks = []
    for pos in positions:
        tasks.append(fetch_children_recursive(client, pos["code"]))

    if tasks:
        results = await asyncio.gather(*tasks)
        for r in results:
            all_codes.extend(r)

    n4 = sum(1 for c in all_codes if len(c["code"]) == 4)
    n6 = sum(1 for c in all_codes if len(c["code"]) == 6)
    n10 = sum(1 for c in all_codes if len(c["code"]) == 10)
    print(f"  Gr {group_code}: {group_name[:50]}... | 4d:{n4} 6d:{n6} 10d:{n10} tot:{len(all_codes)}", flush=True)

    return all_codes


async def save_batch_to_db(batch: list[dict]) -> tuple[int, int]:
    """Save a batch of codes to PostgreSQL."""
    async with async_sessionmaker() as session:
        loaded = 0
        updated = 0

        for item in batch:
            code = item["code"]
            name_ru = item["name_ru"]
            parent_code = item.get("parent_code")
            level = {2: "group", 4: "position", 6: "subposition"}.get(len(code), "subsubposition")

            result = await session.execute(
                select(Classifier).where(
                    Classifier.classifier_type == "hs_code",
                    Classifier.code == code,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                if existing.name_ru != name_ru and name_ru:
                    existing.name_ru = name_ru
                    updated += 1
            else:
                session.add(Classifier(
                    classifier_type="hs_code",
                    code=code,
                    name_ru=name_ru,
                    parent_code=parent_code,
                    meta={"level": level, "source": "classifikators.ru"},
                    is_active=True,
                ))
                loaded += 1

        await session.commit()
        return loaded, updated


async def main():
    t0 = time.time()
    print("=" * 60, flush=True)
    print("Глубокая загрузка ТН ВЭД (все уровни до 10 знаков)", flush=True)
    print(f"Параллельность: {SEM._value} запросов", flush=True)
    print("=" * 60, flush=True)

    total_loaded = 0
    total_updated = 0
    all_count = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": "CustomsDeclarationSystem/1.0"},
        follow_redirects=True,
        limits=httpx.Limits(max_connections=15, max_keepalive_connections=10),
    ) as client:
        # Process groups in batches of 8 for parallelism
        for batch_start in range(0, len(GROUPS), 8):
            batch_groups = GROUPS[batch_start:batch_start + 8]
            tasks = [fetch_group(client, g) for g in batch_groups]
            results = await asyncio.gather(*tasks)

            batch_codes = []
            for r in results:
                batch_codes.extend(r)

            if batch_codes:
                loaded, updated = await save_batch_to_db(batch_codes)
                total_loaded += loaded
                total_updated += updated
                all_count += len(batch_codes)

            elapsed = time.time() - t0
            print(f"  --- Batch {batch_start//8 + 1}/{(len(GROUPS)+7)//8}: "
                  f"+{len(batch_codes)} codes, total:{all_count}, "
                  f"time:{elapsed:.0f}s, requests:{TOTAL_REQUESTS}", flush=True)

    elapsed = time.time() - t0

    # Final stats from DB
    async with async_sessionmaker() as session:
        result = await session.execute(
            select(func.count()).select_from(Classifier).where(
                Classifier.classifier_type == "hs_code"
            )
        )
        db_total = result.scalar() or 0

        print(f"\n{'='*60}", flush=True)
        print(f"Время: {elapsed:.0f} сек", flush=True)
        print(f"HTTP запросов: {TOTAL_REQUESTS}", flush=True)
        print(f"Получено с сайта: {all_count}", flush=True)
        print(f"Загружено новых: {total_loaded}", flush=True)
        print(f"Обновлено: {total_updated}", flush=True)
        print(f"Всего кодов ТН ВЭД в БД: {db_total}", flush=True)

        for length in [2, 4, 6, 8, 10]:
            r = await session.execute(
                select(func.count()).select_from(Classifier).where(
                    Classifier.classifier_type == "hs_code",
                    func.length(Classifier.code) == length,
                )
            )
            print(f"  {length}-значных: {r.scalar()}", flush=True)

    print("=" * 60, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
