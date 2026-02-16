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
        "transport_route": None,
        "awb_number": None,
        "transport_type": None,
    }

    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.has_llm:
            return result

        from app.services.llm_client import get_llm_client, get_model
        client = get_llm_client()

        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "Извлеки данные из транспортного инвойса (счёт за перевозку). Ответь ТОЛЬКО валидным JSON."},
                {"role": "user", "content": f"""Извлеки из транспортного инвойса:
- freight_amount: стоимость перевозки (число)
- freight_currency: валюта (USD, EUR, CNY, RUB)
- carrier_name: название перевозчика/экспедитора
- transport_route: маршрут (откуда — куда)
- awb_number: номер авианакладной (AWB) или транспортной накладной
- transport_type: тип транспорта (40=воздушный, 10=морской, 30=авто, 20=ж/д)

Текст:
{raw_text[:8000]}

JSON: {{"freight_amount": ..., "freight_currency": "...", "carrier_name": "...", "transport_route": "...", "awb_number": "...", "transport_type": "..."}}"""},
            ],
            temperature=0,
            max_tokens=800,
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
