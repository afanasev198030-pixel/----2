"""
Загрузка данных в ChromaDB через LlamaIndex.
Читает ТН ВЭД из PostgreSQL (core-api DB) и правила СУР из risk_rules.json.

Запуск: python -m app.seeds.init_indices
"""
import asyncio
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import structlog
import httpx

logger = structlog.get_logger()


async def load_hs_codes_from_db() -> list[dict]:
    """Загрузить коды ТН ВЭД из core-api."""
    core_url = os.environ.get("CORE_API_URL", "http://localhost:8001")

    # Login to get token
    async with httpx.AsyncClient(timeout=30) as client:
        login_resp = await client.post(f"{core_url}/api/v1/auth/login", json={
            "email": "admin@customs.local",
            "password": "admin123",
        })
        token = login_resp.json().get("access_token", "")
        headers = {"Authorization": f"Bearer {token}"}

        # Fetch HS codes
        codes = []
        page = 1
        while True:
            resp = await client.get(
                f"{core_url}/api/v1/classifiers/",
                params={"classifier_type": "hs_code", "page": page, "per_page": 100},
                headers=headers,
            )
            data = resp.json()
            items = data if isinstance(data, list) else data.get("items", [])
            if not items:
                break
            for item in items:
                codes.append({
                    "code": item["code"],
                    "name_ru": item.get("name_ru", ""),
                    "parent_code": item.get("parent_code", ""),
                    "description": item.get("name_ru", ""),
                })
            if len(items) < 100:
                break
            page += 1

    logger.info("hs_codes_loaded_from_db", count=len(codes))
    return codes


def load_risk_rules() -> list[dict]:
    """Загрузить правила СУР из JSON."""
    rules_path = Path(__file__).parent.parent / "rules" / "risk_rules.json"
    if not rules_path.exists():
        logger.warning("risk_rules_not_found", path=str(rules_path))
        return []

    with open(rules_path) as f:
        rules = json.load(f)

    logger.info("risk_rules_loaded", count=len(rules))
    return rules


async def main():
    print("=" * 60)
    print("Загрузка данных в ChromaDB через LlamaIndex")
    print("=" * 60)

    from app.config import get_settings
    settings = get_settings()

    if not settings.has_openai:
        print("WARNING: OPENAI_API_KEY не установлен. Embeddings не будут созданы.")
        print("Установите ключ через Settings page или переменную окружения.")

    # Load HS codes
    print("\n1. Загрузка кодов ТН ВЭД из PostgreSQL...")
    try:
        hs_codes = await load_hs_codes_from_db()
        print(f"   Загружено: {len(hs_codes)} кодов")
    except Exception as e:
        print(f"   Ошибка: {e}")
        hs_codes = []

    # Load risk rules
    print("\n2. Загрузка правил СУР...")
    risk_rules = load_risk_rules()
    print(f"   Загружено: {len(risk_rules)} правил")

    # Init indices
    print("\n3. Инициализация LlamaIndex индексов...")
    from app.services.index_manager import get_index_manager
    idx = get_index_manager()
    idx.init_indices(hs_codes=hs_codes, risk_rules=risk_rules)

    if idx.available:
        print("   ✓ Индексы созданы и готовы к использованию")
    else:
        print("   ✗ Индексы не созданы (проверьте OpenAI ключ и ChromaDB)")

    print("\n" + "=" * 60)
    print("Готово!")


if __name__ == "__main__":
    asyncio.run(main())
