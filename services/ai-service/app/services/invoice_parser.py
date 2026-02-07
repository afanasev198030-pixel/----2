import re
from typing import Optional
from pydantic import BaseModel
import structlog

from app.services.ocr_service import extract_text

logger = structlog.get_logger()


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
    confidence: float = 0.5


class InvoiceParsed(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    seller: Optional[CounterpartyParsed] = None
    buyer: Optional[CounterpartyParsed] = None
    currency: Optional[str] = None
    total_amount: Optional[float] = None
    country_origin: Optional[str] = None
    country_destination: Optional[str] = None
    incoterms: Optional[str] = None
    contract_number: Optional[str] = None
    items: list[InvoiceItemParsed] = []
    confidence: float = 0.5
    raw_text: str = ""


COUNTRY_MAP = {
    "china": "CN", "chinese": "CN", "hong kong": "HK", "hk": "HK",
    "germany": "DE", "deutschland": "DE",
    "usa": "US", "united states": "US",
    "russia": "RU", "moscow": "RU", "москва": "RU", "россия": "RU",
    "ukraine": "UA", "poland": "PL", "france": "FR", "italy": "IT",
    "spain": "ES", "netherlands": "NL", "belgium": "BE",
    "uk": "GB", "united kingdom": "GB", "japan": "JP",
    "south korea": "KR", "korea": "KR", "turkey": "TR", "india": "IN",
    "vietnam": "VN", "thailand": "TH", "indonesia": "ID",
    "singapore": "SG", "malaysia": "MY", "taiwan": "TW",
    "uae": "AE", "emirates": "AE", "brazil": "BR",
    "canada": "CA", "australia": "AU", "mong kok": "HK",
    "shenzhen": "CN", "guangzhou": "CN", "shanghai": "CN", "beijing": "CN",
    "shijiazhuang": "CN", "китай": "CN",
}


def _detect_country(text: str) -> Optional[str]:
    if not text:
        return None
    text_lower = text.lower()
    for keyword, code in COUNTRY_MAP.items():
        if keyword in text_lower:
            return code
    return None


def _parse_number(s: str) -> Optional[float]:
    """Parse number from string like '360 993,92' or '10.6400'."""
    if not s:
        return None
    s = s.strip().replace(' ', '').replace('\xa0', '')
    # Handle European format: 360.993,92 -> 360993.92
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(text: str) -> Optional[str]:
    patterns = [
        r'(\d{2}\.\d{2}\.\d{4})',
        r'(\d{4}\.\d{2}\.\d{2})',
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{2}/\d{2}/\d{4})',
        r'(\d{2}/\d{2}/\d{2})',
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_counterparty(text: str, keywords: list[str]) -> Optional[CounterpartyParsed]:
    text_lower = text.lower()
    for keyword in keywords:
        idx = text_lower.find(keyword.lower())
        if idx == -1:
            continue
        section = text[idx:idx+600]
        lines = [l.strip() for l in section.split('\n') if l.strip() and len(l.strip()) > 2]

        name = None
        address_parts = []
        tax_number = None

        for line in lines[1:6]:  # skip keyword line, take next 5
            tax_match = re.search(r'(?:VAT|TAX|ИНН|INN|Tax\s*ID)[\s:]*([A-Z0-9\-]+)', line, re.IGNORECASE)
            if tax_match:
                tax_number = tax_match.group(1)
                continue
            if not name and len(line) > 3:
                # Clean common prefixes
                clean = re.sub(r'^(LLC|OOO|ООО|Ltd\.?|Co\.?,?\s*Limited|Inc\.?)\s*', '', line, flags=re.IGNORECASE).strip()
                name = line if not clean else line
            elif name:
                address_parts.append(line)

        address = ", ".join(address_parts[:3]) if address_parts else None
        country = _detect_country(section)

        if name:
            return CounterpartyParsed(name=name, address=address, country_code=country, tax_number=tax_number)
    return None


def _parse_items(text: str) -> list[InvoiceItemParsed]:
    """Parse items from invoice. Focus on table rows with product descriptions + numbers."""
    items = []
    lines = text.split('\n')

    # Skip words - these are NOT product descriptions
    skip_words = [
        'no.', 'qty', 'unit price', 'total', 'note:', 'payment', 'delivery',
        'bank', 'beneficiary', 'address', 'contract', 'terms', 'destination',
        'signature', 'director', 'supplier', 'buyer', 'invoice', 'поставщик',
        'покупатель', 'условия', 'директор', 'подпись', 'страна', 'inn', 'bik',
        'cor.', 'a/c', 'swift', 'road', 'street', 'building', 'flat', 'floor',
        'hong kong', 'moscow', 'москва', 'limited', 'trading', 'logistik',
        'предоплата', 'оплата', 'shipping', 'prospect', 'chelny', 'republic',
    ]

    # Strategy 1: Find the table header row, then parse rows after it
    header_idx = -1
    for i, line in enumerate(lines):
        l = line.lower().strip()
        # Table header contains: "No" + "Item" or "Qty" or "Price" or "Total"
        if ('item' in l and ('qty' in l or 'price' in l or 'total' in l)) or \
           ('no.' in l and ('qty' in l or 'unit' in l)):
            header_idx = i
            break

    if header_idx >= 0:
        # Parse rows after header
        for line in lines[header_idx + 1:]:
            line = line.strip()
            if not line:
                continue
            # Stop at "Note:", "Total USD", etc.
            if re.match(r'^(Note|Total\s+USD|Total\s+EUR|\d+\.\s)', line, re.IGNORECASE):
                if line.lower().startswith('note') or re.match(r'^total\s+(usd|eur)', line, re.IGNORECASE):
                    break

            # Try: "1 Description Qty Price Total"
            row_match = re.match(r'^(\d+)\s+(.+?)\s+(\d[\d\s]*)\s+(\d[\d\s,\.]+)\s+(\d[\d\s,\.]+)\s*$', line)
            if row_match:
                desc = row_match.group(2).strip()
                qty = _parse_number(row_match.group(3))
                price = _parse_number(row_match.group(4))
                total = _parse_number(row_match.group(5))
                if desc and not any(sw in desc.lower() for sw in skip_words):
                    items.append(InvoiceItemParsed(
                        line_no=int(row_match.group(1)),
                        description_raw=desc,
                        quantity=qty, unit_price=price, line_total=total,
                        confidence=0.8,
                    ))
                    continue

            # Try: "Description Qty Price Total" (no line number)
            parts = re.split(r'\s{2,}|\t', line)
            if len(parts) >= 3:
                desc = parts[0].strip()
                if any(sw in desc.lower() for sw in skip_words) or len(desc) < 3:
                    continue
                nums = [_parse_number(p) for p in parts[1:] if _parse_number(p) is not None]
                if len(nums) >= 2 and re.search(r'[a-zA-Zа-яА-Я]', desc):
                    items.append(InvoiceItemParsed(
                        line_no=len(items) + 1,
                        description_raw=desc,
                        quantity=nums[0], unit_price=nums[1],
                        line_total=nums[2] if len(nums) > 2 else None,
                        confidence=0.7,
                    ))

    # Strategy 2: If no header found, look for product keywords with nearby numbers
    if not items:
        product_words = [
            'motor', 'мотор', 'двигатель', 'насос', 'клапан', 'трансформатор',
            'кабель', 'провод', 'труба', 'лампа', 'компрессор', 'генератор',
            'widget', 'part', 'component', 'модуль', 'блок', 'устройство',
            'плата', 'деталь', 'узел', 'механизм', 'аппарат', 'прибор',
        ]
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if any(pw in line_lower for pw in product_words):
                desc = line.strip()
                if any(sw in line_lower for sw in skip_words):
                    continue

                # Extract just the product name (before numbers)
                name_match = re.match(r'^(?:\d+\s+)?([A-Za-zА-Яа-я][\w\s\-/]*[A-Za-zА-Яа-я\d])', desc)
                if name_match:
                    clean_desc = name_match.group(1).strip()
                else:
                    clean_desc = desc

                # Find qty/price/total in same line or context
                context = '\n'.join(lines[max(0, i-1):i+3])
                all_nums = re.findall(r'(\d[\d\s]*(?:[,\.]\d+)?)', context)
                parsed_nums = [_parse_number(n) for n in all_nums if _parse_number(n) is not None and _parse_number(n) > 0]

                qty = parsed_nums[0] if len(parsed_nums) > 0 and parsed_nums[0] > 1 else None
                price = parsed_nums[1] if len(parsed_nums) > 1 else None
                total = parsed_nums[2] if len(parsed_nums) > 2 else None

                items.append(InvoiceItemParsed(
                    line_no=len(items) + 1,
                    description_raw=clean_desc,
                    quantity=qty, unit_price=price, line_total=total,
                    confidence=0.5,
                ))
                break  # Usually one main product per invoice

    return items


def parse(file_bytes: bytes, filename: str) -> InvoiceParsed:
    try:
        raw_text = extract_text(file_bytes, filename)
        if not raw_text:
            return InvoiceParsed(raw_text="", confidence=0.0)

        # Invoice number + date (often together: "Invoice № XXX on 2025.09.25")
        invoice_number = None
        invoice_date = None
        
        # Try combined pattern first: "Invoice No/№ XXX on DATE"
        combined = re.search(
            r'Invoice\s*[№#No\.]*\s*([A-Z0-9\-/]+)\s+on\s+(\d{4}[.\-/]\d{2}[.\-/]\d{2})',
            raw_text, re.IGNORECASE
        )
        if combined:
            invoice_number = combined.group(1).strip()
            invoice_date = combined.group(2).strip()
        else:
            for pattern in [
                r'Invoice\s*[№#No\.]*\s*([A-Z0-9\-/]+)',
                r'(?:INV|Инв)[-/\s]*([A-Z0-9\-/]+)',
                r'[№#]\s*([A-Z0-9\-/]+)',
            ]:
                match = re.search(pattern, raw_text, re.IGNORECASE)
                if match:
                    invoice_number = match.group(1).strip()
                    # Clean: remove trailing "on" or date fragments
                    invoice_number = re.sub(r'\s+on\s*$', '', invoice_number).strip()
                    break
            invoice_date = _parse_date(raw_text)

        # Seller
        seller = _extract_counterparty(raw_text,
            ["Seller", "Shipper", "Exporter", "Supplier", "Продавец", "Поставщик", "The supplier", "Отправитель"])

        # Buyer
        buyer = _extract_counterparty(raw_text,
            ["Buyer", "Consignee", "Importer", "Покупатель", "Получатель", "Ship to", "Bill to"])

        # Currency
        currency = None
        for pattern in [
            r'\b(USD|EUR|CNY|GBP|RUB|JPY|CHF|KRW)\b',
            r'[$€¥£₽]',
            r'(?:Currency|Валюта)[\s:]*([A-Z]{3})',
        ]:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                currency = match.group(1) if match.lastindex else match.group(0)
                sym_map = {'$': 'USD', '€': 'EUR', '¥': 'CNY', '£': 'GBP', '₽': 'RUB'}
                currency = sym_map.get(currency, currency)
                break

        # Total amount (use [ ] instead of \s to avoid matching newlines)
        total_amount = None
        for pattern in [
            r'Total\s+(?:USD|EUR|CNY|GBP|RUB)\s+([\d .,]+)',
            r'Note:\s*Total\s+(?:USD|EUR|CNY|GBP|RUB)\s+([\d .,]+)',
            r'(?:Grand\s*Total|ИТОГО|ВСЕГО|Сумма)\s*:?\s*([\d .,]+)',
            r'Total\s*:?\s*([\d .,]+)',
        ]:
            match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
            if match:
                val = _parse_number(match.group(1))
                if val and val > 0:
                    total_amount = val
                    break

        # Incoterms
        incoterms_match = re.search(r'\b(EXW|FOB|CIF|CIP|CPT|FCA|DAP|DDP|DPU|FAS|CFR)\b', raw_text, re.IGNORECASE)
        
        # Country of origin
        origin_match = re.search(r'(?:Страна\s*происхождения|Country\s*of\s*origin|Origin)[\s:]*([А-Яа-яA-Za-z\s]+)', raw_text, re.IGNORECASE)
        origin_country = None
        if origin_match:
            origin_country = _detect_country(origin_match.group(1))

        # Items
        items = _parse_items(raw_text)

        # If seller not found but we detected country from text
        if not seller:
            country = origin_country or _detect_country(raw_text)
            if country:
                # Try to find company name near the top
                first_lines = raw_text[:500]
                company_match = re.search(r'([A-Z][A-Za-z\s&,\.]+(?:Co\.|Ltd|Inc|Corp|Limited|Trading|Group)[\w\s,\.]*)', first_lines)
                if company_match:
                    seller = CounterpartyParsed(name=company_match.group(1).strip(), country_code=country)

        # Confidence
        fields_found = sum([
            bool(invoice_number), bool(invoice_date), bool(seller), bool(buyer),
            bool(currency), bool(total_amount), len(items) > 0,
        ])
        confidence = min(0.95, 0.2 + (fields_found * 0.1))

        logger.info("invoice_parsed",
            invoice_number=invoice_number, currency=currency, total=total_amount,
            items_count=len(items), confidence=confidence,
            seller=seller.name if seller else None, buyer=buyer.name if buyer else None)

        # Contract number
        contract_number = None
        contract_match = re.search(r'(?:Contract|Договор|Контракт)\s*[№#No\.]*\s*([A-Z0-9][A-Z0-9\-/]+)', raw_text, re.IGNORECASE)
        if contract_match:
            contract_number = contract_match.group(1).strip()
            contract_number = re.sub(r'\s+on\s*$', '', contract_number).strip()

        # Country destination — look for buyer's country
        country_destination = None
        # Search near "Покупатель" / "Buyer" keywords
        buyer_section = ''
        for kw in ['Покупатель', 'Buyer', 'Consignee', 'Получатель']:
            idx = raw_text.find(kw)
            if idx >= 0:
                buyer_section = raw_text[idx:idx+500]
                break
        if buyer_section:
            # Prioritize Moscow/Russia over Hong Kong for destination
            bs_lower = buyer_section.lower()
            if 'moscow' in bs_lower or 'russia' in bs_lower:
                country_destination = 'RU'
            else:
                country_destination = _detect_country(buyer_section)
        # Fallback: if Moscow/Russia anywhere in text
        if not country_destination:
            text_lower = raw_text.lower()
            if 'moscow' in text_lower or 'russia' in text_lower:
                country_destination = 'RU'
            # Check for Cyrillic
            if not country_destination and ('\u041c\u043e\u0441\u043a\u0432\u0430' in raw_text or '\u0420\u043e\u0441\u0441\u0438\u044f' in raw_text):
                country_destination = 'RU'

        return InvoiceParsed(
            invoice_number=invoice_number, invoice_date=invoice_date,
            seller=seller, buyer=buyer, currency=currency,
            total_amount=total_amount,
            country_origin=origin_country,
            country_destination=country_destination,
            incoterms=incoterms_match.group(1).upper() if incoterms_match else None,
            contract_number=contract_number,
            items=items,
            confidence=confidence, raw_text=raw_text,
        )
    except Exception as e:
        logger.error("invoice_parsing_failed", filename=filename, error=str(e))
        return InvoiceParsed(raw_text="", confidence=0.0)
