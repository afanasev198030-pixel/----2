"""Расчёт таможенных платежей и курсы ЦБ."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import structlog

from app.services.payment_calculator import calculate_payments
from app.services.cbr_client import fetch_cbr_rates, get_rate

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/calc", tags=["calc"])


class CalcRequest(BaseModel):
    items: list[dict]
    currency: str = "USD"
    exchange_rate: Optional[float] = None


@router.post("/payments/calculate")
async def calculate(data: CalcRequest):
    """Рассчитать таможенные платежи для позиций."""
    rate = data.exchange_rate
    if not rate or rate <= 0:
        rate = await get_rate(data.currency)
        if rate <= 0:
            raise HTTPException(400, f"Не удалось получить курс для {data.currency}")

    result = calculate_payments(data.items, rate, data.currency)
    return result


@router.get("/exchange-rates")
async def get_exchange_rates(currency: Optional[str] = None, rate_date: Optional[str] = None):
    """Получить курсы валют ЦБ РФ."""
    d = None
    if rate_date:
        try:
            d = date.fromisoformat(rate_date)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    rates = await fetch_cbr_rates(d)

    if currency:
        rate = rates.get(currency.upper(), 0)
        return {"currency": currency.upper(), "rate_to_rub": rate, "date": (d or date.today()).isoformat()}

    return {"rates": rates, "date": (d or date.today()).isoformat(), "count": len(rates)}


@router.get("/exchange-rates/latest")
async def get_latest_rates():
    """Последние курсы основных валют."""
    rates = await fetch_cbr_rates()
    main = {k: rates.get(k, 0) for k in ["USD", "EUR", "CNY", "GBP", "JPY", "CHF", "KRW"]}
    return {"rates": main, "date": date.today().isoformat()}
