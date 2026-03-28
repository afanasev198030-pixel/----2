import re
from typing import Optional
from pydantic import BaseModel
import structlog

from app.services.llm_json import strip_code_fences
from app.services.ocr_service import extract_text

logger = structlog.get_logger()


class ContractParty(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    country_code: Optional[str] = None
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None  # ОГРН или эквивалент (Company Reg. No., Business Reg. No.)
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
    delivery_place: Optional[str] = None
    payment_terms: Optional[str] = None
    delivery_terms: Optional[str] = None
    confidence: float = 0.5
    raw_text: str = ""


def _smart_slice_contract(raw_text: str, max_chars: int = 16000) -> str:
    """Extract key sections of a contract instead of naive [:N] truncation.

    Strategy: take the beginning (title, parties, number, date),
    search for key sections in the middle (Incoterms, currency, payment),
    and always include the end (requisites, signatures, bank details).
    """
    if len(raw_text) <= max_chars:
        return raw_text

    head_size = max_chars // 3
    tail_size = max_chars // 4
    mid_budget = max_chars - head_size - tail_size

    head = raw_text[:head_size]
    tail = raw_text[-tail_size:]

    _SECTION_KEYWORDS = [
        "инкотермс", "incoterms", "условия поставки", "delivery terms",
        "валют", "currency", "расчёты", "расчеты", "payment",
        "цена", "price", "стоимость", "total amount", "contract value",
        "реквизиты", "bank details", "банковские",
        "юридические адреса", "legal address", "адреса и реквизиты",
        "подписи сторон", "signatures",
        "ответственность", "liability", "форс-мажор", "force majeure",
        "предмет договора", "subject of contract",
    ]

    text_lower = raw_text.lower()
    found_sections: list[tuple[int, str]] = []
    for kw in _SECTION_KEYWORDS:
        pos = text_lower.find(kw, head_size)
        if pos != -1 and pos < len(raw_text) - tail_size:
            found_sections.append((pos, kw))

    found_sections.sort(key=lambda x: x[0])

    mid_parts: list[str] = []
    mid_used = 0
    seen_ranges: list[tuple[int, int]] = []
    ctx_window = 800

    for pos, kw in found_sections:
        if mid_used >= mid_budget:
            break
        start = max(head_size, pos - ctx_window)
        end = min(len(raw_text) - tail_size, pos + ctx_window)
        overlaps = any(s <= start <= e or s <= end <= e for s, e in seen_ranges)
        if overlaps:
            continue
        chunk = raw_text[start:end]
        mid_parts.append(f"\n... [{kw}] ...\n{chunk}")
        mid_used += len(chunk) + 30
        seen_ranges.append((start, end))

    if mid_parts:
        return head + "\n".join(mid_parts) + f"\n... [конец документа] ...\n{tail}"
    return head + f"\n... [конец документа] ...\n{tail}"


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
        
        # Extract currency — приоритет: ключевые фразы контракта, затем ISO-коды
        currency = None

        # Словарь: название валюты → ISO 4217
        _CURRENCY_NAMES: dict[str, str] = {
            "доллар сша": "USD", "доллары сша": "USD", "долларов сша": "USD",
            "доллар": "USD", "доллары": "USD", "долларов": "USD",
            "евро": "EUR",
            "юань": "CNY", "юани": "CNY", "юаней": "CNY",
            "китайский юань": "CNY", "renminbi": "CNY", "rmb": "CNY",
            "рубль": "RUB", "рубли": "RUB", "рублей": "RUB", "рублях": "RUB",
            "фунт стерлингов": "GBP", "фунт": "GBP",
            "йена": "JPY", "иена": "JPY",
            "франк": "CHF",
            "us dollar": "USD", "us dollars": "USD",
            "euro": "EUR", "euros": "EUR",
            "chinese yuan": "CNY", "yuan": "CNY",
            "pound sterling": "GBP",
        }

        def _text_to_iso(text: str) -> Optional[str]:
            """Привести извлечённое название/код валюты к ISO 4217."""
            t = text.strip().lower().rstrip(".,;")
            # Если уже ISO-код
            iso_match = re.search(r'\b(USD|EUR|CNY|GBP|RUB|JPY|CHF|HKD|SGD|AED)\b', text, re.I)
            if iso_match:
                return iso_match.group(1).upper()
            # По символу
            sym = {"$": "USD", "€": "EUR", "¥": "CNY", "£": "GBP", "₽": "RUB"}
            for s, code in sym.items():
                if s in text:
                    return code
            # По названию
            for name, code in _CURRENCY_NAMES.items():
                if name in t:
                    return code
            return None

        # 1) Ключевые фразы — самый надёжный способ найти валюту контракта
        _CURRENCY_KW_PATTERNS = [
            r"[Вв]алютой\s+[Кк]онтракта\s+(?:является|являются)\s+([^.;\n]{2,60})",
            r"[Вв]алюта\s+[Кк]онтракта\s*[—\-–:]\s*([^.;\n]{2,40})",
            r"[Рр]асч[её]ты\s+(?:по\s+настоящему\s+[Кк]онтракту\s+)?производятся\s+в\s+([^.;\n]{2,40})",
            r"[Оо]плата\s+(?:производится|осуществляется)\s+в\s+([^.;\n]{2,40})",
            r"[Cc]ontract\s+[Cc]urrency\s+is\s+([A-Za-z ()\s]{2,35})",
            r"[Pp]ayment\s+[Cc]urrency\s*[:\-–]\s*([A-Za-z\s]{2,30})",
            r"[Pp]rice\s+(?:and\s+payment\s+)?[Cc]urrency\s*[:\-–]\s*([A-Za-z\s]{2,30})",
        ]
        for pattern in _CURRENCY_KW_PATTERNS:
            m = re.search(pattern, raw_text, re.IGNORECASE)
            if m:
                found = _text_to_iso(m.group(1))
                if found:
                    currency = found
                    logger.info("contract_currency_from_keyword",
                                pattern=pattern[:50], raw=m.group(1)[:40], iso=currency)
                    break

        # 2) Fallback: первый ISO-код после слова currency/валют
        if not currency:
            ctx_match = re.search(
                r'(?:currency|валют[аыеёу])\s*[^\w]{0,10}(USD|EUR|CNY|GBP|RUB|JPY|CHF)',
                raw_text, re.IGNORECASE,
            )
            if ctx_match:
                currency = ctx_match.group(1).upper()

        # 3) Fallback: символы валют (наименее надёжно)
        if not currency:
            sym_match = re.search(r'[$€¥£₽]', raw_text)
            if sym_match:
                currency = {"$": "USD", "€": "EUR", "¥": "CNY", "£": "GBP", "₽": "RUB"}.get(
                    sym_match.group(0)
                )
        
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
        from app.services.llm_client import get_llm_client, get_model, json_format_kwargs
        client = get_llm_client(operation="contract_llm_enrich")

        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "Извлеки реквизиты сторон из контракта/договора. Ответь ТОЛЬКО валидным JSON."},
                {"role": "user", "content": f"""Извлеки из контракта/договора купли-продажи:
- seller: {{name, address, country_code (2 буквы ISO), inn, kpp, ogrn}}
  Искать в разделах «Продавец», «Seller», «Поставщик», «Supplier».
  Для иностранных компаний: inn = налоговый номер (VAT, Tax ID, 统一社会信用代码 и т.п.),
  ogrn = регистрационный номер компании (Company Reg. No., Business Registration No.).
- buyer: {{name, address, country_code, inn, kpp, ogrn}}
  Искать в разделах «Покупатель», «Buyer», «Заказчик».
  ВАЖНО: name и address покупателя ОБЯЗАТЕЛЬНО на русском языке!
  В контракте часто дублируется наименование на двух языках — всегда выбирай РУССКИЙ вариант.
  Например: «ООО «АГ-ЛОГИСТИК»» вместо «AG-Logistik LLC», «г. Москва, ул. ...» вместо «Moscow, ...».
- currency: ВАЛЮТА КОНТРАКТА (ISO 4217: USD/EUR/CNY/RUB).
  ВАЖНО: искать ключевые фразы «Валютой Контракта являются», «Валюта контракта —»,
  «расчёты производятся в», «Contract currency is», «Payment currency:».
  После фразы следует название валюты — вернуть ISO 4217 код.
  Доллары США → USD, евро → EUR, юани/RMB → CNY, рубли → RUB.
- incoterms: код условий поставки (только 3 буквы: EXW/FCA/FOB/CIF/DAP/DDP и т.д.)
- delivery_place: географический пункт поставки (город/порт/склад), к которому относится базис Инкотермс. Например: "Shanghai", "Москва", "Hamburg". Только название места, без кода Инкотермс.
- payment_terms: условия оплаты (кратко)
- contract_number: номер договора/контракта
- contract_date: дата договора (YYYY-MM-DD)

Текст контракта:
{_smart_slice_contract(raw_text, max_chars=16000)}

JSON:"""},
            ],
            temperature=0,
            max_tokens=2000,
            **json_format_kwargs(),
        )
        text = strip_code_fences(resp.choices[0].message.content)
        data = _json.loads(text)

        if data.get("seller"):
            s = data["seller"]
            result.seller = ContractParty(
                name=s.get("name"), address=s.get("address"),
                country_code=(s.get("country_code") or "")[:2] or None,
                inn=s.get("inn"), kpp=s.get("kpp"), ogrn=s.get("ogrn"),
            )
            if not result.seller_name and s.get("name"):
                result.seller_name = s["name"]

        if data.get("buyer"):
            b = data["buyer"]
            result.buyer = ContractParty(
                name=b.get("name"), address=b.get("address"),
                country_code=(b.get("country_code") or "")[:2] or None,
                inn=b.get("inn"), kpp=b.get("kpp"), ogrn=b.get("ogrn"),
            )
            if not result.buyer_name and b.get("name"):
                result.buyer_name = b["name"]

        # Валюта: LLM перекрывает regex, но только если нашёл через ключевые фразы
        llm_currency = data.get("currency")
        if llm_currency and isinstance(llm_currency, str) and len(llm_currency) <= 5:
            result.currency = llm_currency.upper().strip()
        if data.get("incoterms") and not result.incoterms:
            result.incoterms = data["incoterms"]
        if data.get("delivery_place") and not result.delivery_place:
            result.delivery_place = data["delivery_place"]
        if data.get("payment_terms"):
            result.payment_terms = data["payment_terms"]
        if data.get("contract_number") and not result.contract_number:
            result.contract_number = data["contract_number"]
        if data.get("contract_date") and not result.contract_date:
            result.contract_date = data["contract_date"]

        result.confidence = min(0.95, result.confidence + 0.15)
        logger.info("contract_llm_enriched",
                    seller=result.seller_name, buyer=result.buyer_name,
                    currency=result.currency, incoterms=result.incoterms)

    except Exception as e:
        logger.warning("contract_llm_enrich_failed", error=str(e))

    return result


def parse_debug(raw_text: str, filename: str) -> dict:
    """Parse contract and return debug trace with regex/LLM stage details."""
    import time as _time
    debug: dict = {"regex": {}, "llm": {}, "merged": {}}

    if not raw_text:
        debug["regex"]["error"] = "no_text"
        return debug

    t0 = _time.monotonic()

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

    contract_date = _parse_date(raw_text)

    seller_name = None
    for pattern in [r'(?:Seller|Vendor|Supplier|Продавец)[\s:]*([A-ZА-Я][^\n]{5,100})']:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            seller_name = match.group(1).strip().split('\n')[0]
            break

    buyer_name = None
    for pattern in [r'(?:Buyer|Purchaser|Customer|Покупатель)[\s:]*([A-ZА-Я][^\n]{5,100})']:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            buyer_name = match.group(1).strip().split('\n')[0]
            break

    currency = None
    cur_match = re.search(r'\b(USD|EUR|CNY|GBP|RUB|JPY|CHF)\b', raw_text)
    if cur_match:
        currency = cur_match.group(1)

    incoterms = None
    for code in ['EXW', 'FCA', 'CPT', 'CIP', 'DAP', 'DPU', 'DDP', 'FAS', 'FOB', 'CFR', 'CIF']:
        if re.search(rf'\b{code}\b', raw_text, re.IGNORECASE):
            incoterms = code
            break

    regex_ms = int((_time.monotonic() - t0) * 1000)

    debug["regex"] = {
        "duration_ms": regex_ms,
        "contract_number": {"found": bool(contract_number), "value": contract_number},
        "contract_date": {"found": bool(contract_date), "value": contract_date},
        "seller_name": {"found": bool(seller_name), "value": seller_name},
        "buyer_name": {"found": bool(buyer_name), "value": buyer_name},
        "currency": {"found": bool(currency), "value": currency},
        "incoterms": {"found": bool(incoterms), "value": incoterms},
    }

    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.has_llm:
            debug["llm"] = {"skipped": True, "skipped_reason": "no_llm_configured"}
        else:
            import json as _json
            from app.services.llm_client import get_llm_client, get_model, json_format_kwargs

            system_msg = "Извлеки реквизиты сторон из контракта/договора. Ответь ТОЛЬКО валидным JSON."
            sliced_text = _smart_slice_contract(raw_text, max_chars=16000)
            user_msg = f"""Извлеки из контракта/договора купли-продажи:
- seller: {{name, address, country_code (2 буквы ISO), inn, kpp, ogrn}}
- buyer: {{name, address, country_code, inn, kpp, ogrn}}
- currency: ВАЛЮТА КОНТРАКТА (ISO 4217)
- incoterms: код условий поставки
- contract_number, contract_date (YYYY-MM-DD)

Текст контракта:
{sliced_text}

JSON:"""
            debug["llm"] = {
                "skipped": False,
                "prompt_system": system_msg,
                "prompt_user": user_msg[:6000] + ("..." if len(user_msg) > 6000 else ""),
                "model": get_model(),
                "raw_text_chars": len(raw_text),
                "sliced_text_chars": len(sliced_text),
                "smart_slice_applied": len(raw_text) > 16000,
            }

            client = get_llm_client(operation="contract_llm_enrich")
            t0 = _time.monotonic()
            resp = client.chat.completions.create(
                model=get_model(),
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,
                max_tokens=2000,
                **json_format_kwargs(),
            )
            debug["llm"]["duration_ms"] = int((_time.monotonic() - t0) * 1000)
            raw_response = resp.choices[0].message.content or ""
            debug["llm"]["raw_response"] = raw_response
            debug["llm"]["sliced_text_sent_to_llm"] = sliced_text
            if hasattr(resp, 'usage') and resp.usage:
                debug["llm"]["tokens"] = {
                    "prompt": resp.usage.prompt_tokens,
                    "completion": resp.usage.completion_tokens,
                }
            text = strip_code_fences(raw_response)
            data = _json.loads(text)
            debug["llm"]["parsed"] = data
    except Exception as e:
        debug["llm"]["error"] = str(e)[:500]

    merged = {
        "contract_number": contract_number,
        "contract_date": contract_date,
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "currency": currency,
        "incoterms": incoterms,
    }
    llm_parsed = debug.get("llm", {}).get("parsed", {})
    if llm_parsed:
        for field in ["contract_number", "contract_date", "currency", "incoterms"]:
            if not merged.get(field) and llm_parsed.get(field):
                merged[field] = llm_parsed[field]
                merged[f"{field}_source"] = "llm"
        if llm_parsed.get("seller"):
            s = llm_parsed["seller"]
            merged["seller_name"] = s.get("name") or merged.get("seller_name")
            merged["seller_detail"] = s
        if llm_parsed.get("buyer"):
            b = llm_parsed["buyer"]
            merged["buyer_name"] = b.get("name") or merged.get("buyer_name")
            merged["buyer_detail"] = b
    debug["merged"] = merged

    return debug
