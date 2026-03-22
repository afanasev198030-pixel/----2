"""
Обновление справочника ТН ВЭД из онлайн-источников.
Источники (по приоритету):
1. ФНС РФ: https://data.nalog.ru/files/tnved/tnved.zip
2. data.egov.kz (Казахстан API): /api/v4/euraziyalyk_ekonomikalyk_odakt/v1
3. alta.ru парсинг (fallback)

Запуск: python -m app.seeds.update_tnved_online
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import httpx
import structlog
from sqlalchemy import select, func
from app.database import async_sessionmaker
from app.models import Classifier

logger = structlog.get_logger()

KZ_API_BASE = "https://data.egov.kz/api/v4"
KZ_DATASET = "euraziyalyk_ekonomikalyk_odakt"
FNS_URL = "https://data.nalog.ru/files/tnved/tnved.zip"


async def fetch_from_kz_api(page: int = 0, size: int = 500) -> list[dict]:
    """Загрузить коды ТН ВЭД из API Казахстана (data.egov.kz)."""
    codes = []
    try:
        source_query = json.dumps({
            "from": page * size,
            "size": size,
            "query": {"match_all": {}}
        })
        url = f"{KZ_API_BASE}/{KZ_DATASET}/v1?source={source_query}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                for item in data if isinstance(data, list) else data.get("hits", {}).get("hits", []):
                    src = item.get("_source", item)
                    code = src.get("kod_tn_ved", src.get("code", ""))
                    name = src.get("naimenovanie_tovara_ru", src.get("name_ru", src.get("name", "")))
                    if code and name:
                        codes.append({"code": str(code).strip(), "name_ru": name.strip()})

        logger.info("kz_api_fetched", page=page, count=len(codes))
    except Exception as e:
        logger.warning("kz_api_failed", error=str(e))

    return codes


async def fetch_from_fns() -> list[dict]:
    """Попытка скачать ZIP с ФНС (может быть заблокировано)."""
    codes = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/zip,application/octet-stream,*/*",
            "Referer": "https://data.nalog.ru/",
        }
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(FNS_URL, headers=headers)
            if resp.status_code == 200 and len(resp.content) > 1000:
                # Parse ZIP
                import zipfile
                import io
                import csv

                zf = zipfile.ZipFile(io.BytesIO(resp.content))
                # TNVED4.Txt = main codes, format: group|sub|code6|name|date_from|date_to|
                target = None
                for name in zf.namelist():
                    if 'TNVED4' in name.upper():
                        target = name
                        break
                if not target:
                    target = zf.namelist()[-1]  # largest file

                with zf.open(target) as f:
                    text = f.read().decode('cp866', errors='ignore')
                    seen = set()
                    for line in text.split('\n')[1:]:
                        parts = line.strip().split('|')
                        if len(parts) >= 4:
                            group = parts[0].strip()
                            sub = parts[1].strip()
                            code6 = parts[2].strip()
                            name_ru = parts[3].strip()
                            date_to = parts[5].strip() if len(parts) > 5 else ""
                            if not code6 or not code6[0].isdigit() or not name_ru:
                                continue
                            full_code = f"{group}{sub}{code6}"
                            # Only active codes (date_to empty or future)
                            if date_to and date_to < "2025":
                                continue
                            if full_code not in seen and len(full_code) == 10:
                                codes.append({"code": full_code, "name_ru": name_ru})
                                seen.add(full_code)

                logger.info("fns_zip_loaded", count=len(codes))
            else:
                logger.warning("fns_zip_unavailable", status=resp.status_code, size=len(resp.content))
    except Exception as e:
        logger.warning("fns_download_failed", error=str(e))

    return codes


async def load_codes_to_db(codes: list[dict]) -> int:
    """Загрузить коды в PostgreSQL."""
    loaded = 0
    async with async_sessionmaker() as session:
        for code_data in codes:
            code = code_data["code"].replace(".", "").replace(" ", "")
            if not code or not code[0].isdigit():
                continue

            result = await session.execute(
                select(Classifier).where(
                    Classifier.classifier_type == "hs_code",
                    Classifier.code == code,
                )
            )
            if result.scalar_one_or_none():
                continue

            # Determine level
            level = "group" if len(code) == 2 else "position" if len(code) == 4 else "subposition" if len(code) == 6 else "subsubposition"
            parent = code[:4] if len(code) > 4 else code[:2] if len(code) > 2 else None

            c = Classifier(
                classifier_type="hs_code",
                code=code,
                name_ru=code_data["name_ru"],
                parent_code=parent,
                meta={"level": level, "source": "online"},
                is_active=True,
            )
            session.add(c)
            loaded += 1

            if loaded % 500 == 0:
                await session.commit()

        await session.commit()

    return loaded


async def main():
    print("=" * 60)
    print("Обновление справочника ТН ВЭД из онлайн-источников")
    print("=" * 60)

    # Current count
    async with async_sessionmaker() as session:
        result = await session.execute(
            select(func.count()).select_from(Classifier).where(Classifier.classifier_type == "hs_code")
        )
        current = result.scalar() or 0
        print(f"\nТекущее количество кодов: {current}")

    all_codes = []

    # 1. Try FNS
    print("\n1. Загрузка с ФНС РФ (data.nalog.ru)...")
    fns_codes = await fetch_from_fns()
    if fns_codes:
        print(f"   Получено: {len(fns_codes)} кодов")
        all_codes.extend(fns_codes)

    # 2. Try Kazakhstan API
    print("\n2. Загрузка из API Казахстана (data.egov.kz)...")
    for page in range(10):  # до 5000 записей
        kz_codes = await fetch_from_kz_api(page=page, size=500)
        if not kz_codes:
            break
        all_codes.extend(kz_codes)
    print(f"   Получено: {len(all_codes) - len(fns_codes)} кодов из KZ API")

    # 3. Load to DB
    if all_codes:
        print(f"\n3. Загрузка в БД ({len(all_codes)} кодов)...")
        loaded = await load_codes_to_db(all_codes)
        print(f"   Загружено новых: {loaded}")
    else:
        print("\n3. Нет новых кодов для загрузки")

    # Final count
    async with async_sessionmaker() as session:
        result = await session.execute(
            select(func.count()).select_from(Classifier).where(Classifier.classifier_type == "hs_code")
        )
        total = result.scalar() or 0
        print(f"\nИтого кодов ТН ВЭД: {total}")

    print("\n" + "=" * 60)
    print("Готово!")


if __name__ == "__main__":
    from app.utils.logging import setup_logging
    setup_logging()
    asyncio.run(main())
