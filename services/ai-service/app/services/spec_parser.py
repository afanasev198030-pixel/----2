"""
Парсер спецификаций (Specification / Приложение к контракту).
Извлекает: полный список товаров с qty, unit_price, описанием, country_origin.
Приоритет над инвойсом для items — спецификация обычно содержит более полные данные.
"""
import json
import structlog

from app.services.ocr_service import extract_text

logger = structlog.get_logger()


def _to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("\xa0", " ").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def parse(file_bytes: bytes, filename: str) -> dict:
    """Извлечь таблицу товаров из спецификации через LLM."""
    raw_text = extract_text(file_bytes, filename)
    if not raw_text or len(raw_text.strip()) < 20:
        return {"raw_text": raw_text or "", "doc_type": "specification", "_filename": filename, "items": []}

    result = {
        "raw_text": raw_text,
        "doc_type": "specification",
        "_filename": filename,
        "items": [],
        "total_amount": None,
        "currency": None,
        "total_gross_weight": None,
        "total_net_weight": None,
    }

    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.has_llm:
            return result

        from app.services.llm_client import get_llm_client, get_model
        client = get_llm_client(operation="specification_llm_parse")

        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "Ты эксперт по таможенному оформлению. Извлеки таблицу товаров из спецификации к контракту. Ответь ТОЛЬКО валидным JSON. Не включай транспортные расходы, страховку, фрахт — только физические товары."},
                {"role": "user", "content": f"""Извлеки из спецификации:

items: массив товаров, каждый:
- description: полное описание товара (на языке документа)
- quantity: количество (число)
- unit: единица измерения (pcs, kg, m, шт и т.д.)
- unit_price: цена за единицу (число)
- line_total: сумма по позиции (число)
- gross_weight: вес брутто в кг (если указан)
- net_weight: вес нетто в кг (если указан)
- country_origin: страна происхождения (2-буквенный ISO, если указана)
- hs_code: код ТН ВЭД (если указан в документе)

Также извлеки:
- total_amount: итоговая сумма
- currency: валюта (USD, EUR, CNY, RUB и т.д.)
- total_gross_weight: общий вес брутто (кг)
- total_net_weight: общий вес нетто (кг)

Текст спецификации:
{raw_text[:12000]}

Ответ JSON: {{"items": [...], "total_amount": ..., "currency": "..."}}"""},
            ],
            temperature=0,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        result["items"] = data.get("items", [])
        result["total_amount"] = _to_float(data.get("total_amount"))
        result["currency"] = data.get("currency")
        result["total_gross_weight"] = _to_float(data.get("total_gross_weight"))
        result["total_net_weight"] = _to_float(data.get("total_net_weight"))
        logger.info("spec_parsed", filename=filename, items=len(result["items"]), total=result["total_amount"])

    except Exception as e:
        logger.warning("spec_parse_failed", error=str(e), filename=filename)
        try:
            from app.services.issue_reporter import report_issue
            report_issue("spec_parse", "warning", f"Spec parse failed: {str(e)[:150]}", {"filename": filename})
        except Exception:
            pass

    return result
