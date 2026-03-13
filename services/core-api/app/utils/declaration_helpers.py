import re
from typing import Optional

from app.models.company import Company


_CUSTOMS_POST_ADDRESS_FALLBACKS = {
    "10005020": "г. Москва, аэропорт Внуково, Внуковское шоссе, д. 1",
    "10005030": "г. Москва, ул. Яузская, д. 8",
    "10002010": "Московская обл., г.о. Химки, аэропорт Шереметьево",
    "10002020": "Московская обл., г.о. Химки, аэропорт Шереметьево, Карго",
    "10009100": "Московская обл., г. Домодедово, аэропорт Домодедово",
    "10129060": "г. Санкт-Петербург, аэропорт Пулково",
    "10216120": "г. Санкт-Петербург, Гладкий остров",
    "10130090": "Приморский край, г. Находка, бухта Восточная",
    "10012020": "Новосибирская обл., аэропорт Толмачёво",
    "10009000": "Московская обл., г. Реутов, ул. Железнодорожная, д. 9",
}


def normalize_digits(value: Optional[str]) -> str:
    return re.sub(r"\D", "", value or "")


def parse_inn_kpp(raw_value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    raw = (raw_value or "").strip()
    if not raw:
        return None, None
    if "/" in raw:
        left, right = raw.split("/", 1)
        inn = normalize_digits(left)
        kpp = normalize_digits(right)
        return (inn or None), (kpp or None)

    digits = normalize_digits(raw)
    if len(digits) == 19:
        return digits[:10], digits[10:]
    if len(digits) == 21:
        return digits[:12], digits[12:]
    if len(digits) in (10, 12):
        return digits, None
    return (digits or None), None


def merge_company_inn_kpp(company: Optional[Company], raw_value: Optional[str]) -> Optional[str]:
    """Мёрдж ИНН/КПП: приоритет контракт/инвойс (raw_value) > профиль компании."""
    parsed_inn, parsed_kpp = parse_inn_kpp(raw_value)
    company_inn = normalize_digits(company.inn) if company and company.inn else ""
    company_kpp = normalize_digits(company.kpp) if company and company.kpp else ""
    inn = (parsed_inn or "") or company_inn
    kpp = (parsed_kpp or "") or company_kpp
    if inn and kpp:
        return f"{inn}/{kpp}"
    if inn:
        return inn
    return None


def post_address_fallback(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return _CUSTOMS_POST_ADDRESS_FALLBACKS.get(code[:8])
