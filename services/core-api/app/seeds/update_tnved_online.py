"""
Обновление справочника ТН ВЭД из classifikators.ru
Парсит актуальные коды с сайта и загружает в БД.

Запуск: python -m app.seeds.update_tnved_online
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

# All 97 groups (2-digit codes)
GROUPS = [f"{i:02d}" for i in range(1, 98)]


def parse_codes_from_html(html: str, parent_code: str) -> list[dict]:
    """Parse HS codes and descriptions from classifikators.ru page HTML."""
    codes = []
    # Pattern: table rows with code and description
    # Format: | 8501 | [Description](link) |
    pattern = re.findall(
        r'\|\s*(\d{4,10})\s*\|\s*\[([^\]]+)\]',
        html
    )
    for code, name in pattern:
        codes.append({
            "code": code.strip(),
            "name_ru": name.strip()[:500],
            "parent_code": parent_code,
        })

    # Also try plain text pattern: "8501 | Description"
    if not codes:
        pattern2 = re.findall(
            r'\|\s*(\d{4,10})\s*\|\s*([^|]+)\|',
            html
        )
        for code, name in pattern2:
            name = re.sub(r'\[|\]|\(https?://[^\)]+\)', '', name).strip()
            if name and len(name) > 3:
                codes.append({
                    "code": code.strip(),
                    "name_ru": name[:500],
                    "parent_code": parent_code,
                })

    return codes


async def fetch_group(client: httpx.AsyncClient, group_code: str) -> list[dict]:
    """Fetch all codes for a 2-digit group from classifikators.ru."""
    all_codes = []

    try:
        # Fetch group page (4-digit codes)
        r = await client.get(f"{BASE_URL}/{group_code}", timeout=15)
        if r.status_code != 200:
            print(f"  ⚠ Group {group_code}: HTTP {r.status_code}")
            return []

        text = r.text
        # Extract group name from title
        title_match = re.search(r'<title>.*?(\d{2})\s*[—–-]\s*(.+?)</title>', text, re.DOTALL)
        group_name = title_match.group(2).strip()[:500] if title_match else f"Группа {group_code}"
        group_name = re.sub(r'<[^>]+>', '', group_name)

        all_codes.append({
            "code": group_code,
            "name_ru": group_name,
            "parent_code": None,
            "level": "group",
        })

        # Parse 4-digit positions from the page
        # Pattern in HTML: href="/tnved/8501" ... text
        positions = re.findall(
            r'href="/tnved/(\d{4})"\s*[^>]*>([^<]+)<',
            text
        )
        for code, name in positions:
            name = name.strip()
            if name and len(name) > 3 and code.startswith(group_code):
                all_codes.append({
                    "code": code,
                    "name_ru": name[:500],
                    "parent_code": group_code,
                    "level": "position",
                })

        print(f"  ✓ Group {group_code}: {group_name[:50]}... ({len(all_codes)-1} positions)")

    except Exception as e:
        print(f"  ✗ Group {group_code}: {e}")

    return all_codes


async def update_tnved():
    """Main function: fetch all groups and update DB."""
    print("=" * 60)
    print("Обновление ТН ВЭД из classifikators.ru")
    print("=" * 60)

    all_codes = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "CustomsDeclarationSystem/1.0"},
        follow_redirects=True,
    ) as client:
        # Fetch groups in batches of 5 (don't overwhelm the server)
        for i in range(0, len(GROUPS), 5):
            batch = GROUPS[i:i+5]
            tasks = [fetch_group(client, g) for g in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_codes.extend(result)
            # Be polite
            if i + 5 < len(GROUPS):
                await asyncio.sleep(1)

    print(f"\nВсего получено: {len(all_codes)} кодов")

    if len(all_codes) < 50:
        print("⚠ Слишком мало кодов, возможно ошибка парсинга. Пропуск загрузки.")
        return

    # Load into DB
    async with async_sessionmaker() as session:
        loaded = 0
        updated = 0

        for item in all_codes:
            code = item["code"]
            name_ru = item["name_ru"]
            parent_code = item.get("parent_code")
            level = item.get("level", "position" if len(code) == 4 else "group")

            result = await session.execute(
                select(Classifier).where(
                    Classifier.classifier_type == "hs_code",
                    Classifier.code == code,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update name if changed
                if existing.name_ru != name_ru:
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

        # Total count
        result = await session.execute(
            select(func.count()).select_from(Classifier).where(
                Classifier.classifier_type == "hs_code"
            )
        )
        total = result.scalar() or 0

        print(f"\n{'='*60}")
        print(f"Загружено новых: {loaded}")
        print(f"Обновлено: {updated}")
        print(f"Всего кодов ТН ВЭД в БД: {total}")
        print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(update_tnved())
