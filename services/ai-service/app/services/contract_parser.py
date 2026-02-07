import re
from typing import Optional
from pydantic import BaseModel
import structlog

from app.services.ocr_service import extract_text

logger = structlog.get_logger()


class ContractParsed(BaseModel):
    contract_number: Optional[str] = None
    contract_date: Optional[str] = None
    seller_name: Optional[str] = None
    buyer_name: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    incoterms: Optional[str] = None
    confidence: float = 0.5
    raw_text: str = ""


def _parse_date(text: str) -> Optional[str]:
    """Parse various date formats."""
    date_patterns = [
        r'\d{2}\.\d{2}\.\d{4}',  # DD.MM.YYYY
        r'\d{4}-\d{2}-\d{2}',     # YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',     # DD/MM/YYYY
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}',
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return matches[0]
    
    return None


def parse(file_bytes: bytes, filename: str) -> ContractParsed:
    """
    Parse contract document and extract structured data.
    """
    try:
        raw_text = extract_text(file_bytes, filename)
        
        if not raw_text:
            logger.warning("no_text_extracted", filename=filename)
            return ContractParsed(raw_text="", confidence=0.0)
        
        # Extract contract number
        contract_number = None
        contract_patterns = [
            r'(?:Contract\s*(?:No|Number|#|Nr\.?))[\s:]*([A-Z0-9\-/]+)',
            r'(?:CONTRACT[-/]?)([A-Z0-9\-/]+)',
            r'(?:Договор|Контракт)[\s№:]*([A-Z0-9\-/]+)',
        ]
        for pattern in contract_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                contract_number = match.group(1).strip()
                break
        
        # Extract date
        contract_date = _parse_date(raw_text)
        
        # Extract seller name
        seller_name = None
        seller_patterns = [
            r'(?:Seller|Vendor|Supplier|Продавец)[\s:]*([A-ZА-Я][^\n]{5,100})',
        ]
        for pattern in seller_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                seller_name = match.group(1).strip().split('\n')[0]
                break
        
        # Extract buyer name
        buyer_name = None
        buyer_patterns = [
            r'(?:Buyer|Purchaser|Customer|Покупатель)[\s:]*([A-ZА-Я][^\n]{5,100})',
        ]
        for pattern in buyer_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                buyer_name = match.group(1).strip().split('\n')[0]
                break
        
        # Extract total amount
        total_amount = None
        amount_patterns = [
            r'(?:Total\s+Amount|Contract\s+Value|Сумма\s+договора)[\s:]*([\d\s,\.]+)',
            r'([\d\s,\.]+)\s*(?:USD|EUR|CNY|GBP|RUB)',
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(' ', '').replace(',', '.')
                try:
                    total_amount = float(amount_str)
                    break
                except ValueError:
                    pass
        
        # Extract currency
        currency = None
        currency_patterns = [
            r'\b(USD|EUR|CNY|GBP|RUB|JPY|CHF)\b',
            r'[$€¥£₽]',
        ]
        for pattern in currency_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                currency = match.group(1) if match.lastindex else match.group(0)
                if currency in ['$', '€', '¥', '£', '₽']:
                    currency_map = {'$': 'USD', '€': 'EUR', '¥': 'CNY', '£': 'GBP', '₽': 'RUB'}
                    currency = currency_map.get(currency, currency)
                break
        
        # Extract Incoterms
        incoterms = None
        incoterms_codes = ['EXW', 'FCA', 'CPT', 'CIP', 'DAP', 'DPU', 'DDP', 'FAS', 'FOB', 'CFR', 'CIF']
        for code in incoterms_codes:
            if re.search(rf'\b{code}\b', raw_text, re.IGNORECASE):
                incoterms = code
                break
        
        # Calculate confidence
        fields_found = sum([
            bool(contract_number),
            bool(contract_date),
            bool(seller_name),
            bool(buyer_name),
            bool(total_amount),
            bool(currency),
            bool(incoterms),
        ])
        confidence = min(0.9, 0.3 + (fields_found * 0.1))
        
        return ContractParsed(
            contract_number=contract_number,
            contract_date=contract_date,
            seller_name=seller_name,
            buyer_name=buyer_name,
            total_amount=total_amount,
            currency=currency,
            incoterms=incoterms,
            confidence=confidence,
            raw_text=raw_text
        )
    except Exception as e:
        logger.error("contract_parsing_failed", filename=filename, error=str(e))
        return ContractParsed(raw_text="", confidence=0.0)
