import re
from typing import Optional
from pydantic import BaseModel
import structlog

from app.services.ocr_service import extract_text

logger = structlog.get_logger()


class ContractParty(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    country_code: Optional[str] = None
    inn: Optional[str] = None
    kpp: Optional[str] = None
    bank_name: Optional[str] = None
    account: Optional[str] = None


class ContractParsed(BaseModel):
    contract_number: Optional[str] = None
    contract_date: Optional[str] = None
    seller_name: Optional[str] = None
    buyer_name: Optional[str] = None
    seller: Optional[ContractParty] = None
    buyer: Optional[ContractParty] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    incoterms: Optional[str] = None
    payment_terms: Optional[str] = None
    delivery_terms: Optional[str] = None
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
        
        result = ContractParsed(
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

        # LLM-обогащение: полные реквизиты сторон
        result = _llm_enrich_contract(raw_text, result)
        return result

    except Exception as e:
        logger.error("contract_parsing_failed", filename=filename, error=str(e))
        return ContractParsed(raw_text="", confidence=0.0)


def _llm_enrich_contract(raw_text: str, result: ContractParsed) -> ContractParsed:
    """Извлечь реквизиты сторон из контракта через LLM."""
    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.has_llm:
            return result

        import json as _json
        from app.services.llm_client import get_llm_client, get_model
        client = get_llm_client()

        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "Извлеки реквизиты сторон из контракта/договора. Ответь ТОЛЬКО валидным JSON."},
                {"role": "user", "content": f"""Извлеки из контракта:
- seller: {{name, address, country_code (2 буквы ISO), inn, kpp}}
- buyer: {{name, address, country_code, inn, kpp}}
- currency (валюта расчётов: USD, EUR, CNY, RUB)
- incoterms (условия поставки: EXW, FOB, CIF и т.д.)
- payment_terms (условия оплаты, кратко)

Текст:
{raw_text[:8000]}

JSON: {{"seller": {{...}}, "buyer": {{...}}, "currency": "...", "incoterms": "...", "payment_terms": "..."}}"""},
            ],
            temperature=0,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = _json.loads(text)

        if data.get("seller"):
            s = data["seller"]
            result.seller = ContractParty(
                name=s.get("name"), address=s.get("address"),
                country_code=(s.get("country_code") or "")[:2] or None,
                inn=s.get("inn"), kpp=s.get("kpp"),
            )
            if not result.seller_name and s.get("name"):
                result.seller_name = s["name"]

        if data.get("buyer"):
            b = data["buyer"]
            result.buyer = ContractParty(
                name=b.get("name"), address=b.get("address"),
                country_code=(b.get("country_code") or "")[:2] or None,
                inn=b.get("inn"), kpp=b.get("kpp"),
            )
            if not result.buyer_name and b.get("name"):
                result.buyer_name = b["name"]

        if data.get("currency") and not result.currency:
            result.currency = data["currency"]
        if data.get("incoterms") and not result.incoterms:
            result.incoterms = data["incoterms"]
        if data.get("payment_terms"):
            result.payment_terms = data["payment_terms"]

        result.confidence = min(0.95, result.confidence + 0.15)
        logger.info("contract_llm_enriched", seller=result.seller_name, buyer=result.buyer_name)

    except Exception as e:
        logger.warning("contract_llm_enrich_failed", error=str(e))

    return result
