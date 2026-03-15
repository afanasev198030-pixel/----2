"""
Robust invoice/packing list parser for customs declaration system.
Handles combined INV+PL documents, multi-format tables, Russian/English bilingual PDFs.
"""
import re
from typing import Optional, Any
from pydantic import BaseModel, field_validator
import structlog

from app.services.llm_json import strip_code_fences
from app.services.ocr_service import extract_text

logger = structlog.get_logger()


def _safe_float(v: Any) -> Optional[float]:
    """Безопасное преобразование в float — не падает на строках вроде 'N/A', '2pcs'."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        cleaned = re.sub(r'[^\d.\-]', '', v.strip())
        if cleaned:
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                pass
    return None


class CounterpartyParsed(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    country_code: Optional[str] = None
    tax_number: Optional[str] = None


class InvoiceItemParsed(BaseModel):
    line_no: int = 0
    description_raw: str = ""
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    hs_code: Optional[str] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    country_origin: Optional[str] = None
    confidence: float = 0.5

    @field_validator('quantity', 'unit_price', 'line_total', 'gross_weight', 'net_weight', mode='before')
    @classmethod
    def parse_float_safe(cls, v: Any) -> Optional[float]:
        return _safe_float(v)

    @field_validator('confidence', mode='before')
    @classmethod
    def parse_confidence_safe(cls, v: Any) -> float:
        r = _safe_float(v)
        return r if r is not None else 0.5


class InvoiceParsed(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    seller: Optional[CounterpartyParsed] = None
    buyer: Optional[CounterpartyParsed] = None
    currency: Optional[str] = None
    total_amount: Optional[float] = None

    @field_validator('total_amount', mode='before')
    @classmethod
    def parse_total_safe(cls, v: Any) -> Optional[float]:
        return _safe_float(v)
    total_quantity: Optional[float] = None
    country_origin: Optional[str] = None
    country_destination: Optional[str] = None
    incoterms: Optional[str] = None
    contract_number: Optional[str] = None
    total_gross_weight: Optional[float] = None
    total_net_weight: Optional[float] = None
    total_packages: Optional[int] = None
    items: list[InvoiceItemParsed] = []
    confidence: float = 0.5
    raw_text: str = ""


# ── Country mapping ──────────────────────────────────────────
COUNTRY_MAP = {
    "china": "CN", "chinese": "CN", "hong kong": "HK",
    "germany": "DE", "deutschland": "DE",
    "usa": "US", "united states": "US", "u.s.a": "US",
    "russia": "RU", "russian federation": "RU",
    "moscow": "RU", "москва": "RU", "россия": "RU",
    "ukraine": "UA", "poland": "PL", "france": "FR", "italy": "IT",
    "spain": "ES", "netherlands": "NL", "belgium": "BE",
    "uk": "GB", "united kingdom": "GB", "japan": "JP",
    "south korea": "KR", "korea": "KR", "turkey": "TR", "india": "IN",
    "vietnam": "VN", "thailand": "TH", "indonesia": "ID",
    "singapore": "SG", "malaysia": "MY", "taiwan": "TW",
    "uae": "AE", "emirates": "AE", "brazil": "BR",
    "canada": "CA", "australia": "AU",
    "shenzhen": "CN", "guangzhou": "CN", "shanghai": "CN", "beijing": "CN",
    "nantong": "CN", "wuxi": "CN", "jiangsu": "CN", "zhejiang": "CN",
    "fujian": "CN", "guangdong": "CN", "shandong": "CN",
    "китай": "CN", "германия": "DE", "турция": "TR",
    "италия": "IT", "франция": "FR", "япония": "JP",
    "индия": "IN", "вьетнам": "VN", "сша": "US",
}


def _detect_country(text: str) -> Optional[str]:
    """Detect country code from text, prioritizing longer matches."""
    if not text:
        return None
    text_lower = text.lower()
    # Sort by key length descending for longest match first
    for keyword in sorted(COUNTRY_MAP.keys(), key=len, reverse=True):
        if keyword in text_lower:
            return COUNTRY_MAP[keyword]
    return None


def _parse_number(s: str) -> Optional[float]:
    """Parse number from string like '360 993,92' or '10.6400' or '20 334,000'."""
    if not s:
        return None
    s = s.strip().replace('\xa0', '').replace('\n', '').replace('\r', '')
    # Remove spaces between digits (thousand separators)
    s = re.sub(r'(\d)\s+(\d)', r'\1\2', s)
    # Handle European format: 360.993,92 -> 360993.92
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        # Check if comma is decimal separator (e.g. "148,62") or thousand sep (e.g. "1,000")
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) <= 3:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    try:
        return float(s)
    except ValueError:
        return None


def _find_near_keyword(text: str, keywords: list[str], max_distance: int = 200) -> Optional[str]:
    """Find the text section near a keyword."""
    text_lower = text.lower()
    for kw in keywords:
        idx = text_lower.find(kw.lower())
        if idx >= 0:
            return text[idx:idx + max_distance]
    return None


# ── Invoice Number ───────────────────────────────────────────
def _extract_invoice_number(text: str) -> Optional[str]:
    """Extract invoice number from document text."""
    patterns = [
        # "№ Инвойса DY-VS-WX25-001" or "No Инвойса DY-VS-WX25-001"
        r'[№No#]\s*(?:INVOICE\s*/\s*)?[№No#]?\s*Инвойса\s+([A-Z0-9][\w\-/]+)',
        # "Invoice No DY-VS-WX25-001" (skip "INVOICE" as literal, look for ID)
        r'Invoice\s+[№No#]+\s+(?:INVOICE\s*/\s*[№No#]?\s*Инвойса\s+)?([A-Z0-9][\w\-/]+)',
        # "Invoice: XXX" or "Invoice # XXX"
        r'Invoice\s*[:]\s*([A-Z0-9][\w\-/]+)',
        r'Invoice\s*#\s*([A-Z0-9][\w\-/]+)',
        # Generic: "Инвойс XXX"
        r'Инвойс[аеу]?\s+([A-Z0-9][\w\-/]+)',
        # "INV-XXX" or "INV XXX" (but not "INV&PL" which is filename prefix)
        r'\bINV[\-\s]([A-Z0-9][\w\-/]+)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            num = m.group(1).strip()
            # Skip if it's just "INVOICE" or too short
            if num.upper() in ('INVOICE', 'INV', 'NO', 'NUMBER') or len(num) < 3:
                continue
            return num
    return None


# ── Invoice Date ─────────────────────────────────────────────
def _extract_invoice_date(text: str) -> Optional[str]:
    """Extract invoice date, specifically near 'Дата Инвойса' or 'Date of Invoice'."""
    # Priority 1: Near "Дата Инвойса" / "DATE of INVOICE"
    date_section = _find_near_keyword(text, ['Дата Инвойса', 'DATE of INVOICE', 'Date of Invoice', 'Invoice Date'], 100)
    if date_section:
        m = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_section)
        if m:
            return m.group(1)
        m = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2})', date_section)
        if m:
            return m.group(1)

    # Priority 2: Right after invoice number line
    m = re.search(r'Инвойса.*?(\d{2}\.\d{2}\.\d{4})', text, re.DOTALL)
    if m:
        return m.group(1)

    # Priority 3: Generic date patterns (first occurrence, but skip obvious contract dates)
    # Skip dates that appear right after "контракт" or "contract"
    dates = re.findall(r'(\d{2}\.\d{2}\.\d{4})', text)
    if dates:
        # Return the date that is NOT the contract date
        for d in dates:
            before_idx = text.find(d) - 100
            before = text[max(0, before_idx):text.find(d)].lower()
            if 'контракт' not in before and 'contract' not in before and 'спецификац' not in before:
                return d
        return dates[0]  # fallback to first date

    return None


# ── Currency ─────────────────────────────────────────────────
_VALID_CURRENCIES = {
    'USD', 'EUR', 'CNY', 'GBP', 'RUB', 'JPY', 'CHF', 'KRW', 'AED', 'SEK',
    'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'TRY', 'INR', 'BRL', 'CAD', 'AUD',
    'SGD', 'THB', 'MYR', 'VND', 'IDR', 'HKD', 'TWD', 'NZD', 'ZAR', 'MXN',
    'PHP', 'KZT', 'BYN', 'UAH', 'GEL', 'AMD', 'AZN', 'UZS', 'KGS', 'TJS',
    'MDL', 'TMT', 'SAR', 'QAR', 'OMR', 'BHD', 'KWD', 'EGP',
}
_CURRENCY_FALSE_POS = {'VAT', 'THE', 'AND', 'FOR', 'PER', 'TAX', 'NET', 'QTY', 'ALL', 'AMO', 'PCS', 'KGS', 'CTN', 'BOX', 'SET', 'LOT', 'UNT', 'PCE'}


def _extract_currency(text: str) -> Optional[str]:
    """Extract currency code with strict validation."""
    def _validate(code: str) -> Optional[str]:
        c = code.upper().strip()
        if c in _VALID_CURRENCIES and c not in _CURRENCY_FALSE_POS:
            return c
        return None

    # Explicit currency mentions
    m = re.search(r'(?:Currency|Валюта)[\s:]+([A-Z]{3})', text, re.IGNORECASE)
    if m:
        v = _validate(m.group(1))
        if v:
            return v

    # In context of amounts: "Total, CNY" / "Amount, USD"
    m = re.search(r'(?:Total|Amount|Price|ЦЕНА|СТОИМОСТЬ)[,\s]+([A-Z]{3})\b', text, re.IGNORECASE)
    if m:
        v = _validate(m.group(1))
        if v:
            return v

    # Standalone known currency codes (strict whitelist)
    for m in re.finditer(r'\b([A-Z]{3})\b', text):
        v = _validate(m.group(1))
        if v:
            return v

    # Symbols
    sym_map = {'$': 'USD', '€': 'EUR', '¥': 'CNY', '£': 'GBP', '₽': 'RUB'}
    for sym, code in sym_map.items():
        if sym in text:
            return code
    return None


# ── Total Amount ─────────────────────────────────────────────
def _extract_total_amount(text: str, currency: Optional[str] = None) -> Optional[float]:
    """Extract total invoice amount."""
    cur = currency or r'(?:USD|EUR|CNY|GBP|RUB|JPY)'
    patterns = [
        # "Total, CNY 203 218,53" or "Total USD 360 993,92"
        rf'Total[,\s]+{cur}\s+([\d][\d\s]*[,.]?\d*)',
        # "Amount, CNY 203 218,53"
        rf'Amount[,\s]+{cur}\s+([\d][\d\s]*[,.]?\d*)',
        # "ИТОГОВАЯ СТОИМОСТЬ, CNY\n203218,53"  (multiline)
        rf'(?:ИТОГОВАЯ\s+СТОИМОСТЬ|Total\s+Value)[,/\s]*{cur}\s*([\d][\d\s]*[,.]?\d*)',
        # "Grand Total: 203218.53"
        r'(?:Grand\s*Total|ИТОГО|ВСЕГО)\s*:?\s*([\d][\d\s]*[,.]?\d+)',
        # "Total qty" should NOT match - skip
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            val = _parse_number(m.group(1))
            if val and val > 0:
                logger.debug("total_amount_matched", pattern=pat[:40], raw=m.group(1), value=val)
                return val
    return None


# ── Total Quantity ───────────────────────────────────────────
def _extract_total_quantity(text: str) -> Optional[float]:
    """Extract total quantity."""
    m = re.search(r'Total\s+qty\s+([\d][\d\s]*[,.]?\d*)', text, re.IGNORECASE)
    if m:
        return _parse_number(m.group(1))
    return None


# ── Country of Origin ────────────────────────────────────────
def _extract_country_origin(text: str) -> Optional[str]:
    """Extract country of origin from document."""
    patterns = [
        # "COUNTRY OF ORIGIN ... CHINA" (English, possibly with extra words)
        r'COUNTRY\s+OF\s+ORIGIN[\s\w/]*?[:\s]+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)',
        # "Страна происхождения ... Китай"
        r'Страна\s+происхождения[\s\w/]*?[:\s]+([А-Яа-яA-Za-z]+)',
        # "СТРАНА ПРОИСХОЖДЕНИЯ ... CHINA"
        r'СТРАНА\s+ПРОИСХОЖДЕНИЯ[\s\w/]*?[:\s]+([A-Z][A-Za-z]+)',
        # "Origin: CN" or "Origin: China"
        r'Origin[\s:]+([A-Z]{2,})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            # Filter out non-country words
            skip_words = {'AND', 'OF', 'THE', 'MANUFACTURER', 'ПРОИЗВОДИТЕЛ', 'НАЗВАНИЕ', 'NAME', 'ФИРМА'}
            if raw.upper() in skip_words or len(raw) < 2:
                continue
            code = _detect_country(raw)
            if code:
                logger.debug("country_origin_found", raw=raw, code=code)
                return code
    return None


# ── Country Destination ──────────────────────────────────────
def _extract_country_destination(text: str) -> Optional[str]:
    """Extract destination country (usually Russia for import declarations)."""
    # Look near buyer/consignee sections
    for kw in ['Покупатель', 'Buyer', 'Consignee', 'Получатель']:
        section = _find_near_keyword(text, [kw], 500)
        if section:
            lower = section.lower()
            if 'moscow' in lower or 'russia' in lower or 'москва' in lower or 'россия' in lower:
                return 'RU'
    # Fallback
    if 'Moscow' in text or 'Москва' in text or 'Russian Federation' in text:
        return 'RU'
    return None


# ── Incoterms ────────────────────────────────────────────────
def _extract_incoterms(text: str) -> Optional[str]:
    """Extract Incoterms and delivery place."""
    # Near INCOTERMS keyword
    section = _find_near_keyword(text, ['INCOTERMS', 'Incoterms', 'УСЛОВИЯ ПОСТАВКИ', 'Условия поставки'], 200)
    if section:
        m = re.search(r'\b(EXW|FOB|CIF|CIP|CPT|FCA|DAP|DDP|DPU|FAS|CFR)\b', section, re.IGNORECASE)
        if m:
            return m.group(1).upper()

    # Standalone
    m = re.search(r'\b(EXW|FOB|CIF|CIP|CPT|FCA|DAP|DDP|DPU|FAS|CFR)\b', text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


# ── Contract Number ──────────────────────────────────────────
def _extract_contract_number(text: str) -> Optional[str]:
    """Extract contract number."""
    patterns = [
        # "Контракта № 17092024-LNG/L3-ТМ-ТО" or "Contract No 17092024-LNG/L3-ТМ-ТО"
        r'(?:Контракта|Контракт)\s*(?:No|[№#])[\s.]*([\dA-ZА-Я][\dA-ZА-Яа-яa-z\-/]+[\dA-ZА-Яа-яa-z])',
        # "contract No. KGS-05/244-2022" 
        r'(?:contract)\s+(?:No\.?|[№#])\s*([A-ZА-Я\d][\w\-/]+)',
        # "№ 17092024-LNG/L3-ТМ-ТО dated/от" or "No 17092024-LNG/L3-ТМ-ТО dated"
        r'(?:[№#]|No\.?)\s*([\d]+[\-/][\dA-ZА-Яа-яa-z\-/]+)\s+(?:dated|от)',
        # "контракта от DD.MM.YYYY №КГС-05/244-2022"
        r'контракта\s+от\s+\d{2}\.\d{2}\.\d{4}\s*[№#]?\s*([A-ZА-Я\d][\w\-/]+)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            num = m.group(1).strip()
            # Filter noise
            noise = {'number', 'номер', 'дата', 'date', 'no', 'and', 'или', 'от', 'dated'}
            if num.lower() in noise:
                continue
            if len(num) < 4:
                continue
            # Must contain at least a digit to be a contract number
            if not re.search(r'\d', num):
                continue
            return num
    return None


# ── Counterparty Extraction ──────────────────────────────────
def _extract_seller(text: str) -> Optional[CounterpartyParsed]:
    """Extract seller/supplier information."""
    # Strategy: look for company names (Co., Ltd., Trading, etc.) near supplier section
    # Pattern for Chinese companies — stop at period/semicolon/newline after "Ltd."
    companies = re.findall(
        r'([A-Z][A-Za-z\s]+(?:Co\.?,?\s*Ltd\.?|Trading\s+Co|Corporation|Inc\.?|Group)[,.\s]*(?:Ltd\.?)?)',
        text
    )
    # Find which one is the seller (near Supplier/Shipper/Поставщик)
    seller_section = _find_near_keyword(text, ['Поставщик', 'Supplier', 'Shipper', 'Грузоотправитель'], 800)

    seller_name = None
    seller_address = None
    seller_country = None
    seller_tax = None

    if seller_section:
        # Find company name in this section
        for comp in companies:
            if comp.strip() in seller_section:
                seller_name = comp.strip()
                break

    # If no company found in section, look for explicit Chinese-style company
    if not seller_name:
        for comp in companies:
            country = _detect_country(comp)
            if country and country != 'RU':
                seller_name = comp.strip()
                seller_country = country
                break

    # Address near seller name
    if seller_name:
        name_idx = text.find(seller_name)
        if name_idx >= 0:
            after = text[name_idx:name_idx + 400]
            # Find address (lines with Building, Street, District, etc.)
            addr_parts = []
            for line in after.split('\n')[1:4]:
                line = line.strip()
                if line and len(line) > 5 and not re.match(r'^(Contract|Supplier|Buyer|Shipper|Invoice)', line, re.IGNORECASE):
                    addr_parts.append(line)
            if addr_parts:
                seller_address = ', '.join(addr_parts)
            if not seller_country:
                seller_country = _detect_country(after)

    if seller_name:
        return CounterpartyParsed(
            name=seller_name[:200],
            address=seller_address[:300] if seller_address else None,
            country_code=seller_country,
            tax_number=seller_tax,
        )
    return None


def _extract_buyer(text: str) -> Optional[CounterpartyParsed]:
    """Extract buyer/consignee information."""
    buyer_name = None
    buyer_address = None
    buyer_country = None
    buyer_tax = None

    # Look for Russian companies (ООО, ОАО, ЗАО, LLC)
    ru_companies = re.findall(
        r'((?:ООО|ОАО|ЗАО|ПАО|АО)\s*[«"(]?[\wА-Яа-я\s\-]+?[»")]?)\s*(?:[,/\n]|by\s|$)',
        text
    )
    en_companies = re.findall(
        r'([A-Z][A-Za-z\s]+?\s+LLC)\b',
        text
    )

    buyer_section = _find_near_keyword(text, ['Покупатель', 'Buyer', 'Consignee', 'Грузополучатель'], 800)

    if buyer_section:
        # Russian company in buyer section
        for comp in ru_companies:
            if comp.strip() in buyer_section:
                buyer_name = comp.strip()
                break
        # English LLC in buyer section
        if not buyer_name:
            for comp in en_companies:
                if comp.strip() in buyer_section:
                    buyer_name = comp.strip()
                    break

    # Fallback: first Russian company overall
    if not buyer_name and ru_companies:
        buyer_name = ru_companies[0].strip()

    # Extract INN/tax
    if buyer_name:
        name_idx = text.find(buyer_name)
        if name_idx >= 0:
            after = text[name_idx:name_idx + 500]
            # INN
            inn_match = re.search(r'(?:ИНН|INN)[\s:]*(\d{10,12})', after, re.IGNORECASE)
            if inn_match:
                buyer_tax = inn_match.group(1)
            # Address
            addr_parts = []
            for line in after.split('\n')[1:4]:
                line = line.strip()
                if line and len(line) > 5:
                    if re.search(r'(?:Moscow|Москва|\d{6}|St\.|ул\.|д\.|str\.)', line, re.IGNORECASE):
                        addr_parts.append(line)
            if addr_parts:
                buyer_address = ', '.join(addr_parts)
            buyer_country = _detect_country(after)

    if buyer_name:
        return CounterpartyParsed(
            name=buyer_name[:200],
            address=buyer_address[:300] if buyer_address else None,
            country_code=buyer_country or 'RU',
            tax_number=buyer_tax,
        )
    return None


# ── Items Extraction ─────────────────────────────────────────
def _extract_items(text: str) -> list[InvoiceItemParsed]:
    """Extract items from invoice table."""
    items = []

    # Strategy 1: Use invoice section (first ~3000 chars before packing list starts)
    # Identify invoice section vs packing list section
    pl_start = len(text)
    for marker in ['PACKING LIST', 'Упаковочный лист', 'PACKING\nLIST', 'Package No']:
        idx = text.upper().find(marker.upper())
        if idx > 0 and idx < pl_start:
            pl_start = idx
    invoice_section = text[:min(pl_start, 8000)]

    # Find unique HS codes in invoice section
    hs_codes_in_inv = re.findall(r'\b(\d{8,10})\b', invoice_section)
    # Filter out dates (DDMMYYYY, YYYYMMDD) and phone-like numbers
    def _is_hs_code(code: str) -> bool:
        if re.match(r'^(19|20)\d{6}$', code):
            return False  # YYYYMMDD dates
        if re.match(r'^\d{2}(0[1-9]|1[0-2])(19|20)\d{2}$', code):
            return False  # DDMMYYYY dates
        # HS codes start with groups 01-97 (first 2 digits)
        first2 = int(code[:2])
        if first2 == 0 or first2 > 97:
            return False
        return True
    real_hs_inv = list(dict.fromkeys([c for c in hs_codes_in_inv if _is_hs_code(c)]))

    # Extract total qty and total amount for the invoice
    total_qty = None
    total_price = None
    total_val = None
    qty_m = re.search(r'Total\s+qty\s+([\d][\d\s]*[,.]?\d*)', invoice_section, re.IGNORECASE)
    if qty_m:
        total_qty = _parse_number(qty_m.group(1))

    # Get item description
    desc = _find_item_description(text, real_hs_inv[0] if real_hs_inv else '')

    # If we have HS codes in invoice section, create ONE item per unique HS code
    if real_hs_inv:
        for hs in real_hs_inv[:5]:  # Max 5 unique items
            # Find the full line containing this HS code
            hs_idx = invoice_section.find(hs)
            if hs_idx < 0:
                continue
            # Get the line containing the HS code
            line_start = invoice_section.rfind('\n', 0, hs_idx) + 1
            line_end = invoice_section.find('\n', hs_idx)
            if line_end < 0:
                line_end = len(invoice_section)
            full_line = invoice_section[line_start:line_end]

            # Extract numbers after the HS code: "73043990 L03-02-010 ... m 148,62 1367,37 203218,53"
            after_hs = full_line[full_line.find(hs) + len(hs):]
            nums_raw = re.findall(r'([\d][\d\s]*[,.][\d]+|\b\d{2,}\b)', after_hs)
            nums = [_parse_number(n) for n in nums_raw if _parse_number(n) is not None and _parse_number(n) > 0]

            # Многострочный fallback: если на строке с HS-кодом нашлось <2 чисел,
            # проверяем 2 строки ниже (таблица может быть multi-line).
            if len(nums) < 2:
                next_lines_start = line_end + 1
                next_lines_end = invoice_section.find('\n', next_lines_start)
                if next_lines_end < 0:
                    next_lines_end = len(invoice_section)
                next_block = invoice_section[next_lines_start:next_lines_end]
                second_end = invoice_section.find('\n', next_lines_end + 1)
                if second_end > 0:
                    next_block += ' ' + invoice_section[next_lines_end + 1:second_end]
                extra = re.findall(r'([\d][\d\s]*[,.][\d]+|\b\d{2,}\b)', next_block)
                extra_nums = [_parse_number(n) for n in extra if _parse_number(n) is not None and _parse_number(n) > 0]
                nums.extend(extra_nums)

            unit = None
            qty = None
            price = None
            line_total = None

            # Look for unit (m, pcs, kg, etc.) before the numbers
            unit_match = re.search(r'\b(m|pcs|pc|шт|кг|kg|л|l|unit)\b', after_hs, re.IGNORECASE)
            if unit_match:
                unit = unit_match.group(1)

            # Assign numbers: typically qty, unit_price, total
            if len(nums) >= 3:
                qty = nums[-3]
                price = nums[-2]
                line_total = nums[-1]
            elif len(nums) >= 2:
                qty = nums[-2]
                line_total = nums[-1]
            elif len(nums) >= 1:
                qty = nums[-1]

            # Override qty from "Total qty" if available
            if total_qty and (not qty or abs(qty - total_qty) < 0.01):
                qty = total_qty

            # If we found qty and total but no price, calculate
            if qty and line_total and not price:
                price = round(line_total / qty, 2)

            # Find proper description
            item_desc = desc  # from _find_item_description (may be None for garbled PDFs)
            if full_line and hs in full_line:
                hs_pos = full_line.find(hs)
                after_hs_text = full_line[hs_pos + len(hs):]
                before_hs_text = full_line[:hs_pos]

                # 1) Russian text after HS code: "73043990 Труба бесш. / PIPE SMLS"
                ru_desc = re.search(r'([А-Яа-я][\wА-Яа-я\s\.\"]+(?:/\s*[A-Z][\w\s"\'\.]+)?)', after_hs_text)
                if ru_desc:
                    clean = re.sub(r'\s+[\d,]+\s*$', '', ru_desc.group(1)).strip()
                    if len(clean) > 5:
                        item_desc = clean

                # 2) English text after HS code: "73043990 Steel pipe seamless"
                if not item_desc or len(item_desc) < 5:
                    en_desc = re.search(r'([A-Z][a-zA-Z][a-zA-Z\s\.\-,/]{3,})', after_hs_text)
                    if en_desc:
                        clean = re.sub(r'\s+[\d,.]+\s*$', '', en_desc.group(1)).strip()
                        if len(clean) > 5:
                            item_desc = clean

                # 3) Text BEFORE HS code: "Steel pipe 73043990 100 5.50"
                if not item_desc or len(item_desc) < 5:
                    before = re.sub(r'^\s*\d+[\.\)\-]*\s*', '', before_hs_text).strip()
                    before = re.sub(r'\s+[\d,.]+\s*$', '', before).strip()
                    if len(before) > 5 and sum(1 for c in before if c.isalpha()) >= 4:
                        item_desc = before

                # 4) Look at lines above HS code line for description
                if not item_desc or len(item_desc) < 5:
                    above_text = invoice_section[:line_start].rstrip()
                    if above_text:
                        for prev_line in reversed(above_text.split('\n')[-3:]):
                            pl = prev_line.strip()
                            if not pl or len(pl) < 5:
                                continue
                            if re.match(r'^[\d\s.,/:]+$', pl):
                                continue
                            if re.match(r'^(Item|No|Pos|#|Total|Итого)', pl, re.IGNORECASE) and len(pl) < 15:
                                continue
                            alpha = sum(1 for c in pl if c.isalpha())
                            if alpha >= 4:
                                item_desc = re.sub(r'\s+[\d,.]+\s*$', '', pl).strip()[:200]
                                break

            if not item_desc or len(item_desc) < 5:
                item_desc = f"Item {len(items) + 1}"

            items.append(InvoiceItemParsed(
                line_no=len(items) + 1,
                description_raw=(item_desc or f"Item {len(items) + 1}")[:200],
                quantity=qty or total_qty,
                unit=unit,
                unit_price=price,
                line_total=line_total,
                hs_code=hs,
                confidence=0.8,
            ))
        if items:
            return items

    # Strategy 1 found no items and LLM is unavailable — return empty list.
    # _llm_enrich will be called in parse() and is the proper fallback for
    # item extraction when regex cannot find structured table data.
    return items


_DESC_SECTION_KEYWORDS = [
    'Название груза', 'Наименование товара', 'Описание товара',
    'Item description', 'Description of cargo', 'Description of goods',
    'Product name', 'Product description', 'Name of goods',
    'Goods description', 'Commodity', 'Наименование',
]

_DESC_SKIP_LINE = re.compile(
    r'^(Item\s+description|Название\s+(груза|товар)|Description\s+(of|$)|'
    r'Product\s+(name|desc)|Goods\s+desc|Commodity|'
    r'COUNTRY|INCOTERMS|PACKING|PAYMENT|OKBM|'
    r'Qty|Quantity|Amount|Price|Total|Unit|Currency|'
    r'HS\s*Code|Code|Код)',
    re.IGNORECASE,
)


def _find_item_description(text: str, hs_code: str) -> Optional[str]:
    """Find item description near HS code or in 'Item description' section."""
    # Look in labelled description sections
    desc_section = _find_near_keyword(text, _DESC_SECTION_KEYWORDS, 500)
    if desc_section:
        lines = desc_section.split('\n')
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            if _DESC_SKIP_LINE.match(line):
                continue
            # Accept any line with enough word characters (not just numbers/codes)
            alpha_chars = sum(1 for c in line if c.isalpha())
            if alpha_chars >= 4:
                clean = re.sub(r'\s+[\d,.]+\s*$', '', line).strip()
                if len(clean) >= 5:
                    return clean[:200]

    # Look for description in the line containing the HS code
    if hs_code:
        hs_idx = text.find(hs_code)
        if hs_idx >= 0:
            line_start = text.rfind('\n', 0, hs_idx) + 1
            line_end = text.find('\n', hs_idx)
            if line_end < 0:
                line_end = len(text)
            full_line = text[line_start:line_end]

            # Russian+English: "Труба бесш. / PIPE SMLS..."
            desc_match = re.search(r'([А-Яа-я][\wА-Яа-я\s\.]+(?:/\s*[A-Z][\w\s"\'\.]+)?)', full_line)
            if desc_match:
                d = desc_match.group(1).strip()
                if len(d) > 5:
                    return d[:200]

            # English-only: "Steel pipe seamless" or "Electronic module XYZ-100"
            en_match = re.search(r'([A-Z][a-zA-Z][a-zA-Z\s\.\-,/]{3,})', full_line)
            if en_match:
                d = re.sub(r'\s+[\d,.]+\s*$', '', en_match.group(1)).strip()
                if len(d) > 5:
                    return d[:200]

            # Text before HS code: "Steel pipe 73043990 100 pcs..."
            before_hs = full_line[:full_line.find(hs_code)]
            before_clean = re.sub(r'^\s*\d+[\.\)]*\s*', '', before_hs).strip()
            before_clean = re.sub(r'\s+[\d,.]+\s*$', '', before_clean).strip()
            if len(before_clean) > 5 and sum(1 for c in before_clean if c.isalpha()) >= 4:
                return before_clean[:200]

    return None


# ── Weights ──────────────────────────────────────────────────
def _extract_weights(text: str) -> tuple[Optional[float], Optional[float], Optional[int]]:
    """Extract gross weight, net weight, and package count."""
    gross = None
    net = None
    packages = None

    # Net weight
    for pat in [
        r'(?:TOTAL\s+)?(?:NETT|NET)\s+WEIGHT\s*(?:KG)?[/\s]*[^:\d]*?([\d][\d\s]*[,.]?\d*)',
        r'(?:Итоговый\s+)?[Вв]ес\s+[Нн]етто[^:\d]*?([\d][\d\s]*[,.]?\d*)',
        r'Nett\s+weight\s+total[^:\d]*?([\d][\d\s]*[,.]?\d*)',
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            net = _parse_number(m.group(1))
            if net and net > 0:
                break

    # Gross weight
    for pat in [
        r'(?:TOTAL\s+)?GROSS\s+WEIGHT\s*(?:KG)?[/\s]*[^:\d]*?([\d][\d\s]*[,.]?\d*)',
        r'(?:Итоговый\s+)?[Вв]ес\s+[Бб]рутто[^:\d]*?([\d][\d\s]*[,.]?\d*)',
        r'Gross\s+weight\s+total[^:\d]*?([\d][\d\s]*[,.]?\d*)',
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            gross = _parse_number(m.group(1))
            if gross and gross > 0:
                break

    # Combined "Nett/Gross weight: 20 334,000 20 360,000"
    m = re.search(r'Nett/Gross\s+weight[:\s]*([\d][\d\s]*[,.]?\d*)\s+([\d][\d\s]*[,.]?\d*)', text, re.IGNORECASE)
    if m:
        net = net or _parse_number(m.group(1))
        gross = gross or _parse_number(m.group(2))

    # Packages
    for pat in [
        r'(?:QTY|КОЛИЧЕСТВО)[\s\w]*(?:CLL|МЕСТ|PACKAGE|ГРУЗОВЫХ)[^:\d]*?(\d+)\s*(?:pc|шт|pcs)',
        r'Total\s+package\s+qty[^:\d]*?(\d+)',
        r'(?:Итоговое\s+)?количество\s+(?:грузовых\s+)?мест[^:\d]*?(\d+)',
        r'Итоговое\s+количество\s+грузовых\s+мест\s*\n\s*(\d+)',
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            p = int(m.group(1))
            if 0 < p < 100000:
                packages = p
                break

    return gross, net, packages


# ── LLM Enrichment ───────────────────────────────────────────
def _llm_enrich(raw_text: str, result: dict) -> dict:
    """Use LLM (DeepSeek/OpenAI) to fill missing fields that regex couldn't extract."""
    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.has_llm:
            logger.debug("llm_enrich_skip_no_llm")
            return {}
        from app.services.llm_client import get_llm_client, get_model
        import json as _json
        client = get_llm_client(operation="invoice_llm_enrich")

        items = result.get("items", [])
        has_no_items = len(items) == 0
        has_bad_items = has_no_items or any(
            _is_garbage_desc(it.get("description_raw", ""))
            for it in items
        )
        has_no_prices = bool(items) and any(
            not it.get("unit_price") and not it.get("line_total")
            for it in items
        )

        missing = []
        if not result.get("invoice_number"):
            missing.append("invoice_number")
        if not result.get("country_origin"):
            missing.append("country_origin (2-letter ISO code)")
        if not result.get("total_amount"):
            missing.append("total_amount (number)")
        if not result.get("currency"):
            missing.append("currency (3-letter ISO 4217 code, e.g. USD, EUR, CNY)")
        if not result.get("seller_name"):
            missing.append("seller_name")
        if not result.get("buyer_name"):
            missing.append("buyer_name")

        if not missing and not has_bad_items and not has_no_prices:
            logger.debug("llm_enrich_skip_nothing_missing")
            return {}

        logger.info("llm_enrich_start", missing=missing, has_bad_items=has_bad_items,
                     has_no_prices=has_no_prices, items_count=len(items))

        need_items_from_llm = has_bad_items or has_no_prices
        item_prompt = """Also extract ALL items (ONLY physical goods, NOT freight/shipping/insurance/handling fees).
Return items as JSON array: [{"description": "full product name in original language", "quantity": 100, "unit": "pcs", "unit_price": 5.50, "line_total": 550.00, "country_origin": "CN"}]
CRITICAL: "description" must be the REAL product name from the document, NOT generic labels like "Item 1".
IMPORTANT: quantity, unit_price, line_total are ALL REQUIRED. Look for columns: Qty, Количество, Кол-во, Price, Unit Price, Цена, Amount, Total, Сумма. Calculate: quantity = line_total / unit_price if needed.""" if need_items_from_llm else ""

        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "You are an expert customs document parser. Extract structured data from a commercial invoice. Return ONLY valid JSON, no markdown. Include ONLY physical goods as items — do NOT include freight charges, shipping fees, insurance, handling fees, delivery charges, or transport costs."},
                {"role": "user", "content": f"""Extract the following from this invoice document:
{', '.join(missing) if missing else 'Verify existing data.'}

{item_prompt}

Document text:
{raw_text[:12000]}

Return JSON object with keys: {', '.join(missing)}{', items' if has_bad_items else ''}"""},
            ],
            temperature=0,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        text = strip_code_fences(resp.choices[0].message.content)
        logger.debug("llm_enrich_raw_response", response_length=len(text), first_100=text[:100])
        data = _json.loads(text)
        logger.info("llm_enrich_parsed", keys=list(data.keys()),
                     items_count=len(data.get("items", [])),
                     currency=data.get("currency"),
                     total_amount=data.get("total_amount"),
                     country=data.get("country_origin"))
        return data
    except Exception as e:
        logger.warning("llm_enrich_failed", error=str(e))
        try:
            from app.services.issue_reporter import report_issue
            report_issue("llm_enrich", "error", f"LLM enrich failed: {str(e)[:200]}", {"error": str(e)[:500], "text_length": len(raw_text)})
        except Exception:
            pass
        return {}


_PLACEHOLDER_RE = re.compile(
    r'^(item|товар|product|goods?|позиция|pos|position|line)\s*\d*$',
    re.IGNORECASE,
)


def _is_placeholder_desc(desc: str) -> bool:
    """Check if description is a placeholder like 'Item 1', 'Товар 2', 'Product 3', empty, etc."""
    if not desc:
        return True
    d = desc.strip()
    if len(d) < 3:
        return True
    if _PLACEHOLDER_RE.match(d):
        return True
    return False


_GARBAGE_RE = re.compile(
    r'^(payment|terms?|condition|total|subtotal|amount|invoice\s*no|'
    r'contract|address|tel:|fax:|email|www\.|http|bank|swift|iban|'
    r'оплата|условия|итого|адрес|банк|счет|счёт|подпись|signature|'
    r'no\.\s|number|date|дата|from:|to:|unit\s*price|qty\b|'
    r'description\s*$|наименование\s+товара|item\s+description)',
    re.IGNORECASE,
)


def _is_garbage_desc(desc: str) -> bool:
    """Check if description is garbage: placeholder, header row, service line, code without text."""
    if _is_placeholder_desc(desc):
        return True
    d = desc.strip()
    # Too few alphabetic characters — likely an article code or raw numbers
    alpha_count = sum(1 for c in d if c.isalpha())
    if alpha_count < 5:
        return True
    # More than 65% non-alpha non-space characters — mostly digits/symbols
    non_alpha = sum(1 for c in d if not c.isalpha() and c != ' ')
    if len(d) > 5 and non_alpha > len(d) * 0.65:
        return True
    # Known garbage patterns: headers, service lines, payment conditions, etc.
    if _GARBAGE_RE.match(d):
        return True
    return False


# ── Main Parse Function ──────────────────────────────────────
def parse(file_bytes: bytes, filename: str) -> InvoiceParsed:
    """Parse invoice/packing list PDF and extract structured data."""
    try:
        raw_text = extract_text(file_bytes, filename)
        if not raw_text:
            logger.warning("no_text_extracted", filename=filename)
            return InvoiceParsed(raw_text="", confidence=0.0)

        logger.info("parsing_invoice", filename=filename, text_length=len(raw_text))

        # Extract all fields
        invoice_number = _extract_invoice_number(raw_text)
        invoice_date = _extract_invoice_date(raw_text)
        currency = _extract_currency(raw_text)
        total_amount = _extract_total_amount(raw_text, currency)
        total_quantity = _extract_total_quantity(raw_text)
        country_origin = _extract_country_origin(raw_text)
        country_destination = _extract_country_destination(raw_text)
        incoterms = _extract_incoterms(raw_text)
        contract_number = _extract_contract_number(raw_text)
        seller = _extract_seller(raw_text)
        buyer = _extract_buyer(raw_text)
        items = _extract_items(raw_text)
        gross_weight, net_weight, total_packages = _extract_weights(raw_text)

        # Enrich items with HS code from text if found
        if items:
            hs_codes_in_text = re.findall(r'\b(\d{8})\b', raw_text)
            # Filter out dates and other 8-digit numbers
            real_hs = [c for c in hs_codes_in_text if not re.match(r'^(19|20)\d{6}$', c)]
            if real_hs and not items[0].hs_code:
                items[0].hs_code = real_hs[0]

        # Enrich items with country_origin.
        # Веса НЕ распределяем поровну — это приведёт к одинаковому весу у всех позиций.
        # Per-item веса будут назначены в agent_crew по данным Packing List.
        for item in items:
            if not item.country_origin and country_origin:
                item.country_origin = country_origin

        # LLM enrichment
        regex_result = {
            "invoice_number": invoice_number,
            "country_origin": country_origin,
            "total_amount": total_amount,
            "currency": currency,
            "seller_name": seller.name if seller else None,
            "buyer_name": buyer.name if buyer else None,
        }
        regex_result["items"] = [{"description_raw": it.description_raw} for it in items]
        llm_data = _llm_enrich(raw_text, regex_result)
        if llm_data:
            if not country_origin and llm_data.get("country_origin"):
                co = str(llm_data["country_origin"]).strip().upper()[:2]
                if len(co) == 2:
                    country_origin = co
            if not invoice_number and llm_data.get("invoice_number"):
                invoice_number = str(llm_data["invoice_number"]).strip()
            if not currency and llm_data.get("currency"):
                llm_cur = str(llm_data["currency"]).strip().upper()
                if llm_cur in _VALID_CURRENCIES:
                    currency = llm_cur
                    logger.info("currency_from_llm", currency=currency)
            if not total_amount and llm_data.get("total_amount"):
                llm_amt = _safe_float(llm_data["total_amount"])
                if llm_amt and llm_amt > 0:
                    total_amount = llm_amt
                    logger.info("total_amount_from_llm", amount=total_amount)

            # Replace items if LLM returned better ones, or merge prices.
            # LLM is the preferred source: replace regex items whenever LLM
            # returns an equal or greater number of valid (non-garbage) items.
            llm_items = llm_data.get("items", [])
            if llm_items and isinstance(llm_items, list):
                # Build a clean list from LLM output, skipping garbage/placeholders
                llm_good: list[InvoiceItemParsed] = []
                for idx, li in enumerate(llm_items):
                    if not isinstance(li, dict):
                        continue
                    desc = li.get("description", "") or li.get("description_raw", "") or li.get("name", "")
                    if _is_garbage_desc(desc):
                        continue
                    llm_good.append(InvoiceItemParsed(
                        line_no=idx + 1,
                        description_raw=str(desc)[:200],
                        quantity=li.get("quantity"),
                        unit=li.get("unit", "pcs"),
                        unit_price=li.get("unit_price"),
                        line_total=li.get("line_total"),
                        country_origin=li.get("country_origin"),
                        confidence=0.85,
                    ))

                current_good = sum(1 for it in items if not _is_garbage_desc(it.description_raw))
                has_bad = (len(items) == 0) or (current_good < len(items))

                if llm_good and (has_bad or len(llm_good) >= current_good):
                    # LLM returned at least as many clean items — prefer it
                    items = llm_good
                    logger.info("llm_replaced_items", count=len(llm_good),
                                descs=[it.description_raw[:40] for it in llm_good])
                elif not llm_good:
                    logger.warning("llm_items_all_bad", raw_items=len(llm_items))
                elif items and any(not it.unit_price and not it.line_total for it in items):
                    # Описания хорошие, но цены пустые — мержим цены из LLM-позиций.
                    # Сопоставляем по индексу (порядку): LLM обычно возвращает
                    # позиции в том же порядке, что и в документе.
                    merged = 0
                    for idx, item in enumerate(items):
                        if item.unit_price or item.line_total:
                            continue
                        if idx < len(llm_items) and isinstance(llm_items[idx], dict):
                            li = llm_items[idx]
                            lp = _safe_float(li.get("unit_price"))
                            lt = _safe_float(li.get("line_total"))
                            lq = _safe_float(li.get("quantity"))
                            if lt and lt > 0:
                                item.line_total = lt
                                item.unit_price = lp
                                if not item.quantity and lq:
                                    item.quantity = lq
                                merged += 1
                            elif lp and lp > 0:
                                item.unit_price = lp
                                if not item.quantity and lq:
                                    item.quantity = lq
                                merged += 1
                    if merged:
                        logger.info("llm_prices_merged", merged=merged, total_items=len(items))

        # Confidence
        fields_found = sum([
            bool(invoice_number), bool(invoice_date), bool(seller), bool(buyer),
            bool(currency), bool(total_amount), len(items) > 0,
            bool(country_origin), bool(incoterms), bool(contract_number),
            bool(gross_weight), bool(net_weight),
        ])
        confidence = min(0.95, 0.15 + (fields_found * 0.07))

        logger.info("invoice_parsed_result",
                     invoice_number=invoice_number,
                     invoice_date=invoice_date,
                     currency=currency,
                     total_amount=total_amount,
                     items_count=len(items),
                     country_origin=country_origin,
                     seller=seller.name if seller else None,
                     buyer=buyer.name if buyer else None,
                     incoterms=incoterms,
                     contract=contract_number,
                     gross_weight=gross_weight,
                     net_weight=net_weight,
                     packages=total_packages,
                     confidence=confidence)

        return InvoiceParsed(
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            seller=seller,
            buyer=buyer,
            currency=currency,
            total_amount=total_amount,
            total_quantity=total_quantity,
            country_origin=country_origin,
            country_destination=country_destination,
            incoterms=incoterms,
            contract_number=contract_number,
            total_gross_weight=gross_weight,
            total_net_weight=net_weight,
            total_packages=total_packages,
            items=items,
            confidence=confidence,
            raw_text=raw_text,
        )
    except Exception as e:
        logger.error("invoice_parsing_failed", filename=filename, error=str(e), exc_info=True)
        return InvoiceParsed(raw_text="", confidence=0.0)


def parse_debug(raw_text: str, filename: str) -> dict:
    """Parse invoice and return debug trace with regex/LLM stage details."""
    import time as _time
    debug: dict = {"regex": {}, "llm": {}, "merged": {}}

    if not raw_text:
        debug["regex"]["error"] = "no_text"
        return debug

    t0 = _time.monotonic()

    invoice_number = _extract_invoice_number(raw_text)
    invoice_date = _extract_invoice_date(raw_text)
    currency = _extract_currency(raw_text)
    total_amount = _extract_total_amount(raw_text, currency)
    country_origin = _extract_country_origin(raw_text)
    country_destination = _extract_country_destination(raw_text)
    incoterms = _extract_incoterms(raw_text)
    contract_number = _extract_contract_number(raw_text)
    seller = _extract_seller(raw_text)
    buyer = _extract_buyer(raw_text)
    items = _extract_items(raw_text)
    gross_weight, net_weight, total_packages = _extract_weights(raw_text)

    regex_ms = int((_time.monotonic() - t0) * 1000)

    debug["regex"] = {
        "duration_ms": regex_ms,
        "invoice_number": {"found": bool(invoice_number), "value": invoice_number},
        "invoice_date": {"found": bool(invoice_date), "value": invoice_date},
        "currency": {"found": bool(currency), "value": currency},
        "total_amount": {"found": bool(total_amount), "value": total_amount},
        "country_origin": {"found": bool(country_origin), "value": country_origin},
        "country_destination": {"found": bool(country_destination), "value": country_destination},
        "incoterms": {"found": bool(incoterms), "value": incoterms},
        "contract_number": {"found": bool(contract_number), "value": contract_number},
        "seller": {"found": bool(seller), "value": seller.name if seller else None},
        "buyer": {"found": bool(buyer), "value": buyer.name if buyer else None},
        "gross_weight": {"found": bool(gross_weight), "value": gross_weight},
        "net_weight": {"found": bool(net_weight), "value": net_weight},
        "total_packages": {"found": bool(total_packages), "value": total_packages},
        "items_count": len(items),
        "items": [
            {"line_no": it.line_no, "description": (it.description_raw or "")[:80],
             "quantity": it.quantity, "unit_price": it.unit_price, "line_total": it.line_total}
            for it in items[:20]
        ],
    }

    regex_result = {
        "invoice_number": invoice_number,
        "country_origin": country_origin,
        "total_amount": total_amount,
        "currency": currency,
        "seller_name": seller.name if seller else None,
        "buyer_name": buyer.name if buyer else None,
        "items": [{"description_raw": it.description_raw} for it in items],
    }
    llm_debug = _llm_enrich_debug(raw_text, regex_result)
    debug["llm"] = llm_debug

    merged = {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "currency": currency,
        "total_amount": total_amount,
        "country_origin": country_origin,
        "incoterms": incoterms,
        "seller": seller.name if seller else None,
        "buyer": buyer.name if buyer else None,
        "items_count": len(items),
    }
    llm_data = llm_debug.get("parsed", {})
    if llm_data:
        for field in ["invoice_number", "country_origin", "total_amount", "currency"]:
            if not merged.get(field) and llm_data.get(field):
                merged[field] = llm_data[field]
                merged[f"{field}_source"] = "llm"
    debug["merged"] = merged

    return debug


def _llm_enrich_debug(raw_text: str, result: dict) -> dict:
    """LLM enrichment that captures full debug info: prompt, response, timing."""
    import time as _time
    debug: dict = {"skipped": True}
    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.has_llm:
            debug["skipped_reason"] = "no_llm_configured"
            return debug

        from app.services.llm_client import get_llm_client, get_model
        import json as _json

        items = result.get("items", [])
        has_bad_items = not items or any(
            _is_garbage_desc(it.get("description_raw", "")) for it in items
        )
        has_no_prices = bool(items) and any(
            not it.get("unit_price") and not it.get("line_total") for it in items
        )

        missing = []
        if not result.get("invoice_number"):
            missing.append("invoice_number")
        if not result.get("country_origin"):
            missing.append("country_origin (2-letter ISO code)")
        if not result.get("total_amount"):
            missing.append("total_amount (number)")
        if not result.get("currency"):
            missing.append("currency (3-letter ISO 4217 code)")
        if not result.get("seller_name"):
            missing.append("seller_name")
        if not result.get("buyer_name"):
            missing.append("buyer_name")

        if not missing and not has_bad_items and not has_no_prices:
            debug["skipped_reason"] = "nothing_missing"
            return debug

        debug["skipped"] = False
        debug["missing_fields"] = missing
        debug["has_bad_items"] = has_bad_items
        debug["has_no_prices"] = has_no_prices

        need_items = has_bad_items or has_no_prices
        item_prompt = """Also extract ALL items (ONLY physical goods, NOT freight/shipping/insurance/handling fees).
Return items as JSON array: [{"description": "full product name in original language", "quantity": 100, "unit": "pcs", "unit_price": 5.50, "line_total": 550.00, "country_origin": "CN"}]""" if need_items else ""

        system_msg = "You are an expert customs document parser. Extract structured data from a commercial invoice. Return ONLY valid JSON, no markdown."
        user_msg = f"""Extract the following from this invoice document:
{', '.join(missing) if missing else 'Verify existing data.'}

{item_prompt}

Document text:
{raw_text[:12000]}

Return JSON object with keys: {', '.join(missing)}{', items' if has_bad_items else ''}"""

        debug["prompt_system"] = system_msg
        debug["prompt_user"] = user_msg[:2000] + ("..." if len(user_msg) > 2000 else "")
        debug["model"] = get_model()

        client = get_llm_client(operation="invoice_llm_enrich")
        t0 = _time.monotonic()
        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        debug["duration_ms"] = int((_time.monotonic() - t0) * 1000)

        raw_response = resp.choices[0].message.content or ""
        debug["raw_response"] = raw_response[:5000]
        if hasattr(resp, 'usage') and resp.usage:
            debug["tokens"] = {
                "prompt": resp.usage.prompt_tokens,
                "completion": resp.usage.completion_tokens,
            }

        text = strip_code_fences(raw_response)
        data = _json.loads(text)
        debug["parsed"] = data

    except Exception as e:
        debug["error"] = str(e)[:500]

    return debug
