"""Калькулятор таможенных платежей: пошлина + НДС + акциз + сборы.

Таможенные сборы: Постановление Правительства РФ от 28.11.2024 N 1637
  (ред. Постановления N 1638 от 23.10.2025, вступила 01.01.2026).
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Таможенные сборы за таможенные операции (ВВОЗ)
# Постановление 1637 п.1, ред. 01.01.2026
# ---------------------------------------------------------------------------
CUSTOMS_FEES_IMPORT_2026 = [
    (Decimal("0"),           Decimal("200000"),   Decimal("1231")),
    (Decimal("200000.01"),   Decimal("450000"),   Decimal("2462")),
    (Decimal("450000.01"),   Decimal("1200000"),  Decimal("4924")),
    (Decimal("1200000.01"),  Decimal("2700000"),  Decimal("13541")),
    (Decimal("2700000.01"),  Decimal("4200000"),  Decimal("18465")),
    (Decimal("4200000.01"),  Decimal("5500000"),  Decimal("21344")),
    (Decimal("5500000.01"),  Decimal("10000000"), Decimal("49240")),
    (Decimal("10000000.01"), None,                Decimal("73860")),
]

# Приложение 1 к Постановлению 1637 — товары радиоэлектроники,
# сбор = 73 860 руб фиксированный (п.4).
RADIOELECTRONICS_HS_PREFIXES = [
    "844331", "844332", "8471", "847330", "847350",
    "8517130000", "8517140000", "851761000", "851762000",
    "851769", "851771",
    "851810", "851822000", "851840", "8518500000",
    "851920", "8519300000", "851981", "851989",
    "852110", "852190000", "852351",
    "852560000", "852610000", "852691", "852692000",
    "852842", "852849", "852859", "852869",
    "852871", "852872", "8528730000",
    "853110", "853620", "8544700000",
    "9006300000", "9006400000", "900653", "900659000", "900669000",
    "9007100000", "9007200000", "9008500000",
    "9010500000", "9010600000", "901210",
    "9014100000", "901420", "9014800000",
    "901510", "901520", "901540", "901580", "901600",
    "901710", "901720", "902410", "902480",
    "902511", "902519", "902580",
    "902610", "902620", "902680",
    "902710", "9027200000", "9027300000", "9027500000", "902790",
    "9028100000", "9028200000", "902830",
    "902910000", "902920",
    "9030100000", "903020", "9030310000", "903033", "903039000",
    "9030400000", "903089",
    "9031200000", "9031410000", "903149", "903180",
    "903210", "9032200000", "9032810000", "9032890000",
    "9101910000", "9102120000", "9102190000", "9102910000",
    "910400000", "9106100000", "9106900000",
    "950450000",
]

# ---------------------------------------------------------------------------
# Fallback: ставки пошлин по группам ТН ВЭД (первые 2 цифры).
# Используются когда core-api недоступен или ставка для кода не загружена.
# ---------------------------------------------------------------------------
DEFAULT_DUTY_RATES: dict[str, dict] = {
    "85": {"type": "ad_valorem", "rate": Decimal("5")},
    "84": {"type": "ad_valorem", "rate": Decimal("0")},
    "87": {"type": "ad_valorem", "rate": Decimal("15")},
    "61": {"type": "ad_valorem", "rate": Decimal("10")},
    "62": {"type": "ad_valorem", "rate": Decimal("10")},
    "39": {"type": "ad_valorem", "rate": Decimal("6.5")},
    "73": {"type": "ad_valorem", "rate": Decimal("5")},
    "90": {"type": "ad_valorem", "rate": Decimal("0")},
    "94": {"type": "ad_valorem", "rate": Decimal("8")},
    "DEFAULT": {"type": "ad_valorem", "rate": Decimal("11")},
}

_duty_rate_cache: dict[str, dict] = {}

# Ставки НДС (с 2025 года — 22%)
VAT_RATES: dict[str, Decimal] = {
    "DEFAULT": Decimal("22"),
    "FOOD": Decimal("10"),       # Продовольствие (группы 01-24)
    "CHILDREN": Decimal("10"),   # Детские товары
    "MEDICAL": Decimal("10"),    # Медицинские (30, 9018)
    "ZERO": Decimal("0"),        # Экспорт
}


def _is_radioelectronics(hs_code: str) -> bool:
    """Check if HS code falls under Appendix 1 of Decree 1637 (electronics)."""
    if not hs_code:
        return False
    for prefix in RADIOELECTRONICS_HS_PREFIXES:
        if hs_code.startswith(prefix):
            return True
    return False


def _fetch_duty_rate_from_core(hs_code: str) -> Optional[dict]:
    """Try to get duty rate from core-api classifier meta.duty_rate."""
    if hs_code in _duty_rate_cache:
        return _duty_rate_cache[hs_code]
    try:
        import httpx
        resp = httpx.get(
            "http://core-api:8001/api/v1/classifiers/hs-duty-rate",
            params={"code": hs_code},
            timeout=3,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("duty_rate") is not None:
                result = {
                    "type": data.get("duty_type", "ad_valorem"),
                    "rate": Decimal(str(data["duty_rate"])),
                }
                _duty_rate_cache[hs_code] = result
                return result
    except Exception:
        pass
    return None


def get_duty_rate(hs_code: str) -> dict:
    """Получить ставку пошлины по коду ТН ВЭД.

    Приоритет: core-api (meta.duty_rate) -> fallback по группе (первые 2 цифры).
    """
    if not hs_code:
        return DEFAULT_DUTY_RATES["DEFAULT"]
    from_core = _fetch_duty_rate_from_core(hs_code)
    if from_core is not None:
        return from_core
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


def calculate_customs_fee(
    customs_value_rub: Decimal,
    hs_codes: list[str] | None = None,
) -> Decimal:
    """Рассчитать таможенный сбор по Постановлению 1637 (ред. 01.01.2026).

    П.4: если хотя бы один товар из Приложения 1 (радиоэлектроника) → 73 860 руб.
    П.1: иначе — по общей таможенной стоимости (8 диапазонов).
    """
    if hs_codes:
        for hs in hs_codes:
            if _is_radioelectronics(hs):
                logger.info("customs_fee_radioelectronics", hs_code=hs)
                return Decimal("73860")

    for min_val, max_val, fee in CUSTOMS_FEES_IMPORT_2026:
        if max_val is None and customs_value_rub >= min_val:
            return fee
        if max_val is not None and min_val <= customs_value_rub <= max_val:
            return fee
    return Decimal("1231")


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

    all_hs_codes = [item.get("hs_code", "") for item in items if item.get("hs_code")]
    customs_fee = calculate_customs_fee(total_customs_value, hs_codes=all_hs_codes)
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
