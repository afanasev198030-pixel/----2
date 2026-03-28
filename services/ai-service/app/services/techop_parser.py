"""
Парсер техописаний (ТехОп) для обогащения классификации ТН ВЭД.
Извлекает: назначение, материалы, тех. характеристики, область применения.
"""
import json
import structlog

from app.services.llm_json import strip_code_fences
from app.services.ocr_service import extract_text

logger = structlog.get_logger()


def parse(file_bytes: bytes, filename: str) -> dict:
    """Извлечь технические характеристики из ТехОп через LLM."""
    raw_text = extract_text(file_bytes, filename)
    if not raw_text or len(raw_text.strip()) < 20:
        return {"raw_text": raw_text or "", "doc_type": "tech_description", "_filename": filename}

    result = {
        "raw_text": raw_text,
        "doc_type": "tech_description",
        "_filename": filename,
        "products": [],
    }

    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.has_llm:
            return result

        from app.services.llm_client import get_llm_client, get_model, json_format_kwargs
        client = get_llm_client(operation="techop_llm_parse")

        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "Ты эксперт по таможенному оформлению. Извлеки технические характеристики товаров из технического описания. Ответь ТОЛЬКО валидным JSON."},
                {"role": "user", "content": f"""Извлеки из технического описания:

products: массив товаров, каждый:
- product_name: полное название товара
- purpose: назначение / область применения
- materials: основные материалы (строка)
- technical_specs: ключевые характеристики (напряжение, мощность, размер, вес, частота и т.д.)
- country_origin: страна происхождения (2-буквенный ISO код, если указана)
- suggested_hs_description: описание для классификации ТН ВЭД (одно предложение, включающее материал + назначение + тип)

Текст:
{raw_text[:10000]}

Ответ JSON: {{"products": [...]}}"""},
            ],
            temperature=0,
            max_tokens=3000,
            **json_format_kwargs(),
        )

        text = strip_code_fences(resp.choices[0].message.content)
        data = json.loads(text)
        result["products"] = data.get("products", [])
        logger.info("techop_parsed", filename=filename, products=len(result["products"]))

    except Exception as e:
        logger.warning("techop_parse_failed", error=str(e), filename=filename)
        try:
            from app.services.issue_reporter import report_issue
            report_issue("techop_parse", "warning", f"TechOp parse failed: {str(e)[:150]}", {"filename": filename})
        except Exception:
            pass

    return result
