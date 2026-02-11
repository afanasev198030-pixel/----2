"""Калькулятор таможенных платежей: пошлина + НДС + акциз + сборы."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
import structlog

logger = structlog.get_logger()

# Таможенные сборы 2026 (Постановление Правительства РФ)
CUSTOMS_FEES_2026 = [
    (Decimal("0"), Decimal("200000"), Decimal("775")),
    (Decimal("200001"), Decimal("450000"), Decimal("1550")),
    (Decimal("450001"), Decimal("1200000"), Decimal("3100")),
    (Decimal("1200001"), Decimal("2500000"), Decimal("8530")),
    (Decimal("2500001"), Decimal("5000000"), Decimal("12000")),
    (Decimal("5000001"), Decimal("10000000"), Decimal("30000")),
    (Decimal("10000001"), None, Decimal("100000")),
]

# Базовые ставки пошлин по группам ТН ВЭД (упрощённые)
DEFAULT_DUTY_RATES: dict[str, dict] = {
    "85": {"type": "ad_valorem", "rate": Decimal("5")},       # Электроника
    "84": {"type": "ad_valorem", "rate": Decimal("0")},       # Оборудование
    "87": {"type": "ad_valorem", "rate": Decimal("15")},      # Транспорт
    "61": {"type": "ad_valorem", "rate": Decimal("10")},      # Одежда трикотаж
    "62": {"type": "ad_valorem", "rate": Decimal("10")},      # Одежда
    "39": {"type": "ad_valorem", "rate": Decimal("6.5")},     # Пластмассы
    "73": {"type": "ad_valorem", "rate": Decimal("5")},       # Изделия из металла
    "90": {"type": "ad_valorem", "rate": Decimal("0")},       # Оптика, приборы
    "94": {"type": "ad_valorem", "rate": Decimal("8")},       # Мебель
    "DEFAULT": {"type": "ad_valorem", "rate": Decimal("11")}, # По умолчанию
}

# Ставки НДС (с 2025 года — 22%)
VAT_RATES: dict[str, Decimal] = {
    "DEFAULT": Decimal("22"),
    "FOOD": Decimal("10"),       # Продовольствие (группы 01-24)
    "CHILDREN": Decimal("10"),   # Детские товары
    "MEDICAL": Decimal("10"),    # Медицинские (30, 9018)
    "ZERO": Decimal("0"),        # Экспорт
}


def get_duty_rate(hs_code: str) -> dict:
    """Получить ставку пошлины по коду ТН ВЭД."""
    if not hs_code:
        return DEFAULT_DUTY_RATES["DEFAULT"]
    group = hs_code[:2]
    return DEFAULT_DUTY_RATES.get(group, DEFAULT_DUTY_RATES["DEFAULT"])


def get_vat_rate(hs_code: str) -> Decimal:
    """Получить ставку НДС по коду ТН ВЭД."""
    if not hs_code:
        return VAT_RATES["DEFAULT"]
    group = int(hs_code[:2]) if hs_code[:2].isdigit() else 99
    if 1 <= group <= 24:
        return VAT_RATES["FOOD"]
    if hs_code.startswith("30") or hs_code.startswith("9018"):
        return VAT_RATES["MEDICAL"]
    return VAT_RATES["DEFAULT"]


def calculate_customs_fee(customs_value_rub: Decimal) -> Decimal:
    """Рассчитать таможенный сбор по стоимости партии (2026)."""
    for min_val, max_val, fee in CUSTOMS_FEES_2026:
        if max_val is None and customs_value_rub >= min_val:
            return fee
        if min_val <= customs_value_rub <= (max_val or Decimal("999999999")):
            return fee
    return Decimal("775")


def calculate_payments(
    items: list[dict],
    exchange_rate: float = 1.0,
    currency: str = "RUB",
) -> dict:
    """Рассчитать все таможенные платежи.

    Args:
        items: [{hs_code, unit_price, quantity, customs_value_rub, ...}]
        exchange_rate: курс валюты к рублю
        currency: код валюты

    Returns:
        {items: [...], totals: {...}}
    """
    rate = Decimal(str(exchange_rate))
    result_items = []
    total_customs_value = Decimal("0")
    total_duty = Decimal("0")
    total_vat = Decimal("0")
    total_excise = Decimal("0")

    for item in items:
        hs_code = item.get("hs_code", "")
        customs_value = Decimal(str(item.get("customs_value_rub", 0)))

        # Если стоимость в валюте — пересчитать
        if customs_value == 0 and item.get("unit_price") and item.get("quantity"):
            customs_value = Decimal(str(item["unit_price"])) * Decimal(str(item["quantity"])) * rate

        # Пошлина
        duty_info = get_duty_rate(hs_code)
        duty_rate = duty_info["rate"]
        duty = (customs_value * duty_rate / Decimal("100")).quantize(Decimal("0.01"), ROUND_HALF_UP)

        # Акциз (пока 0 для большинства товаров)
        excise = Decimal("0")

        # НДС
        vat_rate = get_vat_rate(hs_code)
        vat_base = customs_value + duty + excise
        vat = (vat_base * vat_rate / Decimal("100")).quantize(Decimal("0.01"), ROUND_HALF_UP)

        total_customs_value += customs_value
        total_duty += duty
        total_vat += vat
        total_excise += excise

        result_items.append({
            "item_no": item.get("item_no", 0),
            "hs_code": hs_code,
            "customs_value_rub": float(customs_value),
            "duty": {
                "type": duty_info["type"],
                "rate": float(duty_rate),
                "amount": float(duty),
            },
            "vat": {
                "rate": float(vat_rate),
                "base": float(vat_base),
                "amount": float(vat),
            },
            "excise": float(excise),
        })

    customs_fee = calculate_customs_fee(total_customs_value)
    grand_total = total_duty + total_vat + total_excise + customs_fee

    logger.info("payments_calculated",
        items_count=len(items),
        total_customs_value=float(total_customs_value),
        total_duty=float(total_duty),
        total_vat=float(total_vat),
        customs_fee=float(customs_fee),
        grand_total=float(grand_total),
    )

    return {
        "items": result_items,
        "totals": {
            "total_customs_value": float(total_customs_value),
            "total_duty": float(total_duty),
            "total_vat": float(total_vat),
            "total_excise": float(total_excise),
            "customs_fee": float(customs_fee),
            "grand_total": float(grand_total),
        },
        "exchange_rate": exchange_rate,
        "currency": currency,
    }
