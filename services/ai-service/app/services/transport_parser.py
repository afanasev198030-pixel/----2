"""
Парсер транспортных инвойсов (freight invoice).
Извлекает: стоимость перевозки, маршрут, перевозчик.
Данные нужны для расчёта таможенных платежей (графа 17 — транспортные расходы).
"""
import json
import structlog

from app.services.ocr_service import extract_text

logger = structlog.get_logger()


def parse(file_bytes: bytes, filename: str) -> dict:
    """Извлечь данные из транспортного инвойса."""
    raw_text = extract_text(file_bytes, filename)
    if not raw_text or len(raw_text.strip()) < 20:
        return {"raw_text": raw_text or "", "doc_type": "transport_invoice", "_filename": filename}

    result = {
        "raw_text": raw_text,
        "doc_type": "transport_invoice",
        "_filename": filename,
        "freight_amount": None,
        "freight_currency": None,
        "carrier_name": None,
        "shipper_name": None,    # Отправитель груза (для гр. 2)
        "shipper_address": None, # Адрес отправителя
        "transport_route": None,
        "awb_number": None,
        "flight_number": None,
        "transport_type": None,
    }

    # Regex fallback: извлечь базовые данные без LLM
    import re as _re
    awb_match = _re.search(r'(\d{3})[- ]?(\d{8})', raw_text)
    if awb_match:
        result["awb_number"] = f"{awb_match.group(1)}-{awb_match.group(2)}"
        result["transport_type"] = "40"
    freight_match = _re.search(r'(?:total|amount|freight|charge)[:\s]*([A-Z]{3})\s*([\d,. ]+)', raw_text, _re.IGNORECASE)
    if freight_match:
        result["freight_currency"] = freight_match.group(1).upper()
        amt = freight_match.group(2).replace(" ", "").replace(",", "")
        try:
            result["freight_amount"] = float(amt)
        except ValueError:
            pass
    if not result.get("transport_type"):
        lower = raw_text.lower()
        if "cmr" in lower or "consignment note" in lower:
            result["transport_type"] = "30"
        elif "bill of lading" in lower or "b/l" in lower:
            result["transport_type"] = "10"
        elif "airway" in lower or "awb" in lower:
            result["transport_type"] = "40"

    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.has_llm:
            logger.info("transport_parsed_regex_only", filename=filename, awb=result.get("awb_number"))
            return result

        from app.services.llm_client import get_llm_client, get_model
        client = get_llm_client(operation="transport_doc_llm_parse")

        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "Извлеки данные из транспортного инвойса (счёт за перевозку). Ответь ТОЛЬКО валидным JSON."},
                {"role": "user", "content": f"""Извлеки из транспортного инвойса:
- freight_amount: стоимость перевозки (число)
- freight_currency: валюта (USD, EUR, CNY, RUB)
- carrier_name: название перевозчика/экспедитора
- shipper_name: наименование ОТПРАВИТЕЛЯ груза (для графы 2 ДТ).
    Искать: "Shipper", "Shipper's Name", "Consignor", "Отправитель", "Грузоотправитель".
    Это компания-отправитель, НЕ перевозчик и НЕ экспедитор.
- shipper_address: ПОЛНЫЙ адрес отправителя (для графы 2 ДТ).
    Искать: "Shipper's Address", "Address", "Адрес отправителя" — рядом с именем отправителя.
    Включить: улицу, город, индекс, страну.
- transport_route: маршрут (откуда — куда)
- awb_number: номер авианакладной (AWB) или транспортной накладной (только номер, без слова AWB)
- flight_number: номер рейса (например "CA836", "SU100") — для графы 21 ДТ; null если не авиа
- transport_type: тип транспорта (40=воздушный, 10=морской, 30=авто, 20=ж/д)

Текст:
{raw_text[:8000]}

JSON:"""},
            ],
            temperature=0,
            max_tokens=800,
            response_format={"type": "json_object"},
        )

        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        result.update({k: v for k, v in data.items() if v is not None and k in result})
        logger.info("transport_invoice_parsed", filename=filename, freight=result["freight_amount"], currency=result["freight_currency"])

    except Exception as e:
        logger.warning("transport_invoice_parse_failed", error=str(e), filename=filename)

    return result
