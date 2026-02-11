"""
Курсы валют ЦБ РФ.
Кэш на 1 час. Источник: https://www.cbr.ru/scripts/XML_daily.asp
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
import httpx
import structlog

logger = structlog.get_logger()

_cache: dict = {}
_cache_time: Optional[datetime] = None
CACHE_TTL = timedelta(hours=1)

CBR_URL = "https://www.cbr.ru/scripts/XML_daily.asp"


async def fetch_rates(date: Optional[datetime] = None) -> dict[str, Decimal]:
    """Fetch exchange rates from CBR. Returns {currency_code: rate_per_unit_in_rub}."""
    global _cache, _cache_time

    # Check cache
    if _cache and _cache_time and (datetime.now() - _cache_time) < CACHE_TTL:
        return _cache

    try:
        params = {}
        if date:
            params["date_req"] = date.strftime("%d/%m/%Y")

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(CBR_URL, params=params)
            r.raise_for_status()

        root = ET.fromstring(r.content)
        rates = {}

        for valute in root.findall("Valute"):
            code = valute.find("CharCode").text
            nominal = int(valute.find("Nominal").text)
            value_str = valute.find("Value").text.replace(",", ".")
            value = Decimal(value_str)
            # Rate per 1 unit of currency
            rate = value / nominal
            rates[code] = rate

        # Always add RUB = 1
        rates["RUB"] = Decimal("1")

        _cache = rates
        _cache_time = datetime.now()

        logger.info("cbr_rates_fetched", count=len(rates), date=params.get("date_req", "today"))
        return rates

    except Exception as e:
        logger.error("cbr_rates_failed", error=str(e))
        # Return cached or hardcoded fallback
        if _cache:
            return _cache
        return {
            "USD": Decimal("92.50"),
            "EUR": Decimal("100.50"),
            "CNY": Decimal("12.80"),
            "GBP": Decimal("117.00"),
            "JPY": Decimal("0.62"),
            "RUB": Decimal("1"),
        }


async def convert_to_rub(amount: Decimal, currency: str, date: Optional[datetime] = None) -> tuple[Decimal, Decimal]:
    """
    Convert amount to RUB.
    Returns (amount_rub, exchange_rate).
    """
    if currency == "RUB":
        return amount, Decimal("1")

    rates = await fetch_rates(date)
    rate = rates.get(currency.upper())

    if not rate:
        logger.warning("currency_not_found", currency=currency)
        return amount, Decimal("1")

    amount_rub = (amount * rate).quantize(Decimal("0.01"))
    return amount_rub, rate
