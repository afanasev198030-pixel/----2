"""
Robust invoice/packing list parser for customs declaration system.
Handles combined INV+PL documents, multi-format tables, Russian/English bilingual PDFs.
"""
import re
from typing import Optional, Any
from pydantic import BaseModel, field_validator
import structlog

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
def _extract_currency(text: str) -> Optional[str]:
    """Extract currency code."""
    # Explicit currency mentions
    m = re.search(r'(?:Currency|Валюта)[\s:]+([A-Z]{3})', text, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    # In context of amounts: "Total, CNY" / "Amount, USD" / "ЦЕНА, CNY"
    m = re.search(r'(?:Total|Amount|Price|ЦЕНА|СТОИМОСТЬ)[,\s]+([A-Z]{3})\b', text, re.IGNORECASE)
    if m:
        cur = m.group(1).upper()
        # Skip false positives
        if cur not in ('VAT', 'THE', 'AND', 'FOR', 'PER', 'TAX', 'NET', 'QTY', 'ALL'):
            return cur

    # Standalone known currency codes (strict list)
    m = re.search(r'\b(USD|EUR|CNY|GBP|RUB|JPY|CHF|KRW|AED|SEK|NOK|DKK|PLN|CZK|HUF|TRY|INR|BRL|CAD|AUD|SGD|THB|MYR|VND|IDR)\b', text)
    if m:
        return m.group(1)

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
    invoice_section = text[:min(pl_start, 3000)]

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
            # Find all numbers in the rest of the line
            nums_raw = re.findall(r'([\d]+[,.][\d]+)', after_hs)
            nums = [_parse_number(n) for n in nums_raw if _parse_number(n) is not None and _parse_number(n) > 0]

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
            # Extract description from the HS code line: "73043990 ... Труба бесш. / PIPE SMLS 18"..."
            if full_line and hs in full_line:
                after_hs_text = full_line[full_line.find(hs) + len(hs):]
                # Look for Russian text followed by optional English
                ru_desc = re.search(r'([А-Яа-я][\wА-Яа-я\s\.\"]+(?:/\s*[A-Z][\w\s"\'\.]+)?)', after_hs_text)
                if ru_desc:
                    clean = ru_desc.group(1).strip()
                    # Remove trailing numbers (qty, price, etc.)
                    clean = re.sub(r'\s+[\d,]+\s*$', '', clean).strip()
                    if len(clean) > 5:
                        item_desc = clean
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

    # Strategy 3: Keyword-based product detection (deduplicated)
    product_keywords = [
        'труб', 'мотор', 'двигатель', 'насос', 'клапан', 'трансформатор',
        'кабель', 'провод', 'лампа', 'компрессор', 'генератор', 'pipe',
        'motor', 'pump', 'valve', 'cable', 'transformer', 'compressor',
        'модуль', 'блок', 'устройство', 'деталь', 'узел', 'аппарат',
    ]
    lines = text.split('\n')
    seen_desc = set()
    for i, line in enumerate(lines):
        lower = line.lower().strip()
        if any(kw in lower for kw in product_keywords):
            desc = line.strip()
            # Clean: remove leading numbers/codes
            desc = re.sub(r'^\d+\s+', '', desc).strip()
            if len(desc) < 3:
                continue

            # Deduplicate by normalized description
            norm = re.sub(r'\s+', ' ', desc.lower())[:80]
            if norm in seen_desc:
                continue
            seen_desc.add(norm)

            # Look for HS code in nearby text
            context = '\n'.join(lines[max(0, i - 3):i + 5])
            hs_matches = re.findall(r'\b(\d{8,10})\b', context)
            # Filter out dates
            real_hs = [c for c in hs_matches if not re.match(r'^(19|20)\d{6}$', c)]
            hs_code = real_hs[0] if real_hs else None

            # Look for qty/price/total in the invoice section (first 2000 chars)
            inv_section = text[:2000]
            # Find "Total qty XXX" pattern
            qty_match = re.search(r'Total\s+qty\s+([\d][\d\s]*[,.]?\d*)', inv_section, re.IGNORECASE)
            qty = _parse_number(qty_match.group(1)) if qty_match else None

            # Find unit price from table row
            price_match = re.search(r'(?:' + re.escape(hs_code or '73043990') + r')\s+\S+\s+\w+\s+[\d,.\s]+\s+([\d,.\s]+)\s+([\d,.\s]+)', inv_section) if hs_code else None
            price = None
            total = None
            if price_match:
                price = _parse_number(price_match.group(1))
                total = _parse_number(price_match.group(2))
            else:
                # Fallback: look for price near the description
                nearby_nums = re.findall(r'([\d]+[,.][\d]+)', context)
                parsed = [_parse_number(n) for n in nearby_nums if _parse_number(n) is not None and _parse_number(n) > 0]
                if len(parsed) >= 3:
                    qty = qty or parsed[0]
                    price = parsed[1]
                    total = parsed[2]

            items.append(InvoiceItemParsed(
                line_no=len(items) + 1,
                description_raw=desc[:200],
                quantity=qty,
                unit_price=price,
                line_total=total,
                hs_code=hs_code,
                confidence=0.6,
            ))

            # For this document type (single product), stop after first unique match
            if len(items) >= 1:
                break

    return items


def _find_item_description(text: str, hs_code: str) -> Optional[str]:
    """Find item description near HS code or in 'Item description' section."""
    # Look in "Item description / Название груза" section
    desc_section = _find_near_keyword(text, ['Название груза', 'Item description', 'Description of cargo'], 500)
    if desc_section:
        # Take the first non-empty line after the keyword that looks like a product name
        lines = desc_section.split('\n')
        for line in lines:
            line = line.strip()
            # Skip the keyword line itself and metadata lines
            if not line or len(line) < 5:
                continue
            if re.match(r'^(Item\s+description|Название\s+груза|Description|COUNTRY|INCOTERMS|PACKING|PAYMENT|OKBM)', line, re.IGNORECASE):
                continue
            # Good candidate: contains product-like content
            if re.search(r'[А-Яа-я]', line) or re.search(r'(?:PIPE|MOTOR|PUMP|CABLE|VALVE)', line, re.IGNORECASE):
                return line[:200]

    # Look for description in the line containing the HS code
    if hs_code:
        hs_idx = text.find(hs_code)
        if hs_idx >= 0:
            line_start = text.rfind('\n', 0, hs_idx) + 1
            line_end = text.find('\n', hs_idx)
            if line_end < 0:
                line_end = len(text)
            full_line = text[line_start:line_end]

            # Look for Russian+English description like "Труба бесш. / PIPE SMLS..."
            desc_match = re.search(r'([А-Яа-я][\wА-Яа-я\s\.]+(?:/\s*[A-Z][\w\s"\'\.]+)?)', full_line)
            if desc_match:
                d = desc_match.group(1).strip()
                if len(d) > 5:
                    return d[:200]

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
            return {}
        from app.services.llm_client import get_llm_client, get_model
        import json as _json
        client = get_llm_client()

        # Check if items have placeholder descriptions (regex failed) or items list is empty
        items = result.get("items", [])
        has_no_items = len(items) == 0
        has_bad_items = has_no_items or any(
            (it.get("description_raw", "") or "").lower().startswith("item ")
            or not it.get("description_raw")
            for it in items
        )

        missing = []
        if not result.get("invoice_number"):
            missing.append("invoice_number")
        if not result.get("country_origin"):
            missing.append("country_origin (2-letter ISO code)")
        if not result.get("total_amount"):
            missing.append("total_amount (number)")
        if not result.get("seller_name"):
            missing.append("seller_name")
        if not result.get("buyer_name"):
            missing.append("buyer_name")

        if not missing and not has_bad_items:
            return {}

        # Always ask for items when descriptions are bad
        item_prompt = """Also extract items (ONLY physical goods, NOT freight/shipping/insurance/handling fees): [{description, quantity, unit, unit_price, line_total, country_origin}].
IMPORTANT: quantity is REQUIRED for each item. Look for columns: Qty, Количество, Кол-во, Amount, pcs, шт. If not stated explicitly, calculate: quantity = line_total / unit_price.""" if has_bad_items else ""

        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "Extract data from a commercial invoice. Return ONLY valid JSON. Include ONLY physical goods as items — do NOT include freight charges, shipping fees, insurance, handling fees, delivery charges, or transport costs."},
                {"role": "user", "content": f"""Extract from this invoice:
{', '.join(missing) if missing else 'Verify existing data.'}

{item_prompt}

Text:
{raw_text[:12000]}

Return JSON with keys: {', '.join(missing)}{', items' if has_bad_items else ''}"""},
            ],
            temperature=0,
            max_tokens=4000,
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return _json.loads(text)
    except Exception as e:
        logger.warning("llm_enrich_failed", error=str(e))
        return {}


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

        # Enrich items with country_origin
        for item in items:
            if not item.country_origin and country_origin:
                item.country_origin = country_origin
            if not item.gross_weight and gross_weight and len(items) > 0:
                item.gross_weight = round(gross_weight / len(items), 3)
            if not item.net_weight and net_weight and len(items) > 0:
                item.net_weight = round(net_weight / len(items), 3)

        # LLM enrichment
        regex_result = {
            "invoice_number": invoice_number,
            "country_origin": country_origin,
            "total_amount": total_amount,
            "seller_name": seller.name if seller else None,
            "buyer_name": buyer.name if buyer else None,
        }
        regex_result["items"] = [{"description_raw": it.description_raw} for it in items]
        llm_data = _llm_enrich(raw_text, regex_result)
        if llm_data:
            if not country_origin and llm_data.get("country_origin"):
                country_origin = llm_data["country_origin"]
            if not invoice_number and llm_data.get("invoice_number"):
                invoice_number = llm_data["invoice_number"]
            # Replace items if LLM returned better ones
            llm_items = llm_data.get("items", [])
            if llm_items and isinstance(llm_items, list):
                has_bad = any(
                    (it.description_raw or "").lower().startswith("item ") or not it.description_raw
                    for it in items
                )
                if has_bad:
                    new_items = []
                    for idx, li in enumerate(llm_items):
                        new_items.append(InvoiceItemParsed(
                            line_no=idx + 1,
                            description_raw=li.get("description", ""),
                            quantity=li.get("quantity"),
                            unit=li.get("unit", "pcs"),
                            unit_price=li.get("unit_price"),
                            line_total=li.get("line_total"),
                            country_origin=li.get("country_origin"),
                            confidence=0.85,
                        ))
                    if new_items:
                        items = new_items
                        logger.info("llm_replaced_items", count=len(new_items))

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
