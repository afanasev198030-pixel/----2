"""Клиент API ЦБ РФ — курсы валют."""
import json
from datetime import date, datetime
from typing import Optional
import httpx
import structlog

logger = structlog.get_logger()

# In-memory cache (Redis not always available)
_rates_cache: dict[str, dict] = {}


async def fetch_cbr_rates(rate_date: Optional[date] = None) -> dict[str, float]:
    """Получить курсы валют ЦБ РФ на дату.
    Returns: {"USD": 92.5431, "EUR": 100.1234, "CNY": 12.8765, ...}
    """
    target_date = rate_date or date.today()
    cache_key = target_date.isoformat()

    if cache_key in _rates_cache:
        logger.debug("cbr_cache_hit", date=cache_key)
        return _rates_cache[cache_key]

    url = f"https://www.cbr.ru/scripts/XML_daily.asp?date_req={target_date.strftime('%d/%m/%Y')}"
    rates = {}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            from lxml import etree
            root = etree.fromstring(resp.content)

            for valute in root.findall("Valute"):
                char_code = valute.findtext("CharCode")
                nominal = int(valute.findtext("Nominal", "1"))
                value_str = valute.findtext("Value", "0").replace(",", ".")
                value = float(value_str)

                if char_code and value > 0:
                    rates[char_code] = round(value / nominal, 6)

        _rates_cache[cache_key] = rates
        logger.info("cbr_rates_fetched", date=cache_key, count=len(rates))

    except Exception as e:
        logger.error("cbr_fetch_failed", error=str(e), date=cache_key)
        # Fallback: hardcoded rates
        if not rates:
            rates = {"USD": 92.50, "EUR": 100.00, "CNY": 12.80, "GBP": 117.00, "JPY": 0.62, "CHF": 104.00, "KRW": 0.067}
            logger.warning("cbr_using_fallback_rates")

    return rates


async def get_rate(currency: str, rate_date: Optional[date] = None) -> float:
    """Получить курс одной валюты."""
    if currency == "RUB":
        return 1.0
    rates = await fetch_cbr_rates(rate_date)
    rate = rates.get(currency.upper(), 0)
    if rate == 0:
        logger.warning("cbr_rate_not_found", currency=currency)
    return rate
