"""
Declaration compiler — LLM-based compilation of parsed documents into declaration fields.

Takes extracted document data + filling rules, sends to LLM for semantic decisions
(source priority, field selection, party identification, document type codes).
Arithmetic, lookups and normalization are handled in post_processing.
"""
import structlog

from app.services.llm_json import strip_code_fences
from app.services.parsing_utils import to_dict
from app.services.rules_engine import build_full_rules_for_llm

logger = structlog.get_logger()


def compile_declaration(parsed_docs: dict) -> dict:
    """LLM-based declaration compilation.

    Sends all extracted document data + filling rules to LLM.
    LLM handles semantic decisions: source priority, field selection,
    party identification, document type codes.
    Arithmetic, lookups and normalization are done in _post_process_compilation.
    """
    import json as _json
    from app.config import get_settings as _get_settings
    from app.services.llm_client import get_llm_client, get_model, json_format_kwargs
    from app.services.rules_engine import get_filling_rules_text

    settings = _get_settings()
    rules_text = build_full_rules_for_llm(section="header", core_api_url=settings.CORE_API_URL)
    filling_rules = get_filling_rules_text()

    docs_ctx = {}
    for doc_key, doc_data in parsed_docs.items():
        if doc_key.startswith("_"):
            continue
        data = to_dict(doc_data) if not isinstance(doc_data, list) else doc_data
        if not data:
            continue
        if isinstance(data, dict):
            cleaned = {k: v for k, v in data.items()
                       if v is not None and k not in ("raw_text", "_cache_type", "_filename")
                       and not (isinstance(k, str) and k.startswith("_"))}
            if doc_key == "specification" and cleaned:
                cleaned.pop("items", None)
                logger.info("spec_items_stripped_for_llm",
                            msg="Removed individual spec items from LLM context — "
                                "only items_count/totals sent")
            if cleaned:
                docs_ctx[doc_key] = cleaned
        elif isinstance(data, list):
            items_list = []
            for item in data:
                if isinstance(item, dict):
                    c = {k: v for k, v in item.items()
                         if v is not None and k not in ("raw_text", "_cache_type", "_filename")}
                    if c:
                        items_list.append(c)
            if items_list:
                docs_ctx[doc_key] = items_list

    docs_json = _json.dumps(docs_ctx, ensure_ascii=False, indent=2)

    from app.services.classifier_cache import get_cache
    _clf = get_cache()
    classifier_tables = (
        "СПРАВОЧНИК ВИДОВ ТРАНСПОРТА (гр.25/26): "
        + (_clf.format_for_prompt("transport_type") or "10—Морской|20—ЖД|30—Авто|40—Воздушный")
        + "\n"
        "СПРАВОЧНИК ХАРАКТЕРА СДЕЛКИ (гр.24, подраздел 1 — 2-значный код + '0'→3 цифры): "
        + (_clf.format_for_prompt("deal_nature") or "01—Купля-продажа|02—Бартер|03—Безвозмездная")
        + "\n"
        "СПРАВОЧНИК МОС (гр.43, подраздел 1): "
        + (_clf.format_for_prompt("mos_method") or "01—По цене сделки|02—Идентичные|03—Однородные")
        + "\n"
        "СПРАВОЧНИК ПРОЦЕДУР (гр.1/37): "
        + (_clf.format_for_prompt("procedure") or "IM40—Выпуск|IM51—Переработка")
        + "\n"
    )

    system_prompt = (
        "Ты опытный таможенный брокер РФ. Заполняешь таможенную декларацию ИМ40 (импорт).\n"
        "Тебе предоставлены извлечённые данные из документов и официальные правила.\n"
        "СТРОГО следуй правилам: приоритеты источников, форматы, специальные значения.\n"
        "Ответь ТОЛЬКО валидным JSON. Если данных нет — null. Не придумывай данные.\n"
        "НЕ делай арифметические расчёты (суммирование, распределение весов) — это сделает Python.\n\n"
        "ПРИОРИТЕТЫ ИСТОЧНИКОВ ПО ГРАФАМ (СТРОГО СОБЛЮДАЙ):\n"
        "- Графа 2 (seller / отправитель): ТОЛЬКО транспортные источники в порядке: "
        "1) transport (AWB/CMR/B/L) → shipper_name, "
        "2) application_statement → forwarding_agent или shipper, "
        "3) transport_invoice → shipper_name. "
        "Товарный инвойс (invoice.seller) и контракт (contract.seller) — это стороны СДЕЛКИ (гр.11), "
        "а НЕ грузоотправитель. Использовать их для seller ЗАПРЕЩЕНО.\n"
        "- Графа 14 (buyer / декларант): контракт > инвойс.\n"
        "- Графа 22 (currency / валюта): ТОЛЬКО из контракта.\n"
        "- Графа 11 (trading_partner_country): страна ПРОДАВЦА по контракту (contract.seller.country_code).\n\n"
        "ИСТОЧНИКИ ТОВАРНЫХ ПОЗИЦИЙ (items[]):\n"
        "- items[] формируются ТОЛЬКО из invoice (товарный инвойс). "
        "НЕ создавай позиции из specification, packing list или любого другого документа!\n"
        "- Specification (спецификация) — источник ТОЛЬКО для items_count (для сверки), "
        "incoterms и delivery_place. Спецификация НЕ источник товарных позиций!\n"
        "- Packing list — источник весов (gross_weight, net_weight) и упаковки, "
        "но НЕ источник товарных позиций.\n"
        "- Если один и тот же товар присутствует и в invoice, и в packing list — "
        "это ОДНА позиция, а не две. Бери описание/цену из invoice, веса из packing list.\n"
        "- Количество позиций в items[] должно СТРОГО совпадать с количеством товаров в инвойсе. "
        "Если в инвойсе 1 товар — в items[] должна быть 1 позиция, даже если в спецификации их больше.\n\n"
        "ОБРАБОТКА КОНФЛИКТОВ:\n"
        "- Если одно и то же поле содержит разные значения в разных документах, "
        "используй приоритеты источников для конкретной графы (см. выше). "
        "Для полей без специального приоритета: контракт > инвойс > упаковочный лист > транспортная накладная.\n"
        "- Добавь конфликт в issues[] с описанием: какие значения в каких документах.\n"
        "- Формат issue: {\"id\": \"conflict_<field>\", \"severity\": \"warning\", \"message\": \"описание\"}\n\n"
        "ГРАФА 20 (УСЛОВИЯ ПОСТАВКИ):\n"
        "- incoterms: ВСЕГДА указывай 3-буквенный код (EXW, FOB, CIF, FCA и т.д.)\n"
        "- delivery_place: город, написанный ПОСЛЕ кода Инкотермс в спецификации или контракте.\n"
        "  Для EXW/FCA/FOB/FAS — это город ПРОДАВЦА (отправления), НЕ город получателя.\n"
        "  Пример: если в спецификации написано 'EXW Hongkong', incoterms='EXW', delivery_place='Hongkong'."
    )

    user_prompt = f"""=== ИЗВЛЕЧЁННЫЕ ДАННЫЕ ИЗ ДОКУМЕНТОВ ===
{docs_json}

=== ПРАВИЛА ЗАПОЛНЕНИЯ ГРАФ ДТ (из БД) ===
{rules_text or ''}

=== ПРАВИЛА ЗАПОЛНЕНИЯ ГРАФ (полные) ===
{filling_rules or ''}

=== СПРАВОЧНИКИ КЛАССИФИКАТОРОВ (используй ТОЛЬКО коды из этих таблиц) ===
{classifier_tables}
=== ЗАДАЧА ===
На основе документов и правил заполни ВСЕ поля декларации, для которых есть данные.
Соблюдай приоритет источников для каждой графы.
Если между документами есть конфликтующие данные — выбери значение по приоритету и добавь issues[].

ФОРМАТ ОТВЕТА — JSON:
{{
  "type_code": "ИМ40 или другой код (гр.1)",
  "seller": {{"name": "...", "country_code": "ISO2", "address": "...", "inn": "...", "kpp": "...", "ogrn": "..."}},  // гр.2 ОТПРАВИТЕЛЬ: ТОЛЬКО из транспортных источников! 1) transport.shipper_name, 2) application_statement.forwarding_agent/shipper, 3) transport_invoice.shipper_name. НЕ из invoice.seller и НЕ из contract.seller!
  "buyer": {{"name": "...", "country_code": "ISO2", "address": "...", "inn": "...", "kpp": "...", "ogrn": "..."}},  // гр.14 ПОКУПАТЕЛЬ/ДЕКЛАРАНТ: name и address ОБЯЗАТЕЛЬНО на русском языке!
  "declarant": {{"name": "ТОЛЬКО НА РУССКОМ", "address": "ТОЛЬКО НА РУССКОМ", "inn": "...", "kpp": "...", "ogrn": "..."}},
  "buyer_matches_declarant": true,
  "consignee": null,
  "financial_responsible": null,
  "trading_partner_country": "ISO2 (гр.11)",
  "declarant_inn_kpp": "ИНН/КПП (гр.14)",
  "country_dispatch": "ISO2 (гр.15)",
  "country_origin": "ISO2 или РАЗНЫЕ/НЕИЗВЕСТНО/ЕВРОСОЮЗ (гр.16)",
  "country_destination": "ISO2 (гр.17, дефолт RU)",
  "departure_vehicle_info": "рег.номер/рейс/судно (гр.18)",
  "departure_vehicle_country": "ISO2 или 00/99 (гр.18)",
  "container": true/false,
  "incoterms": "3-буквенный код Инкотермс (гр.20): EXW/FCA/FOB/CIF и т.д.",
  "delivery_place": "город поставки из спецификации или контракта (гр.20)",
  "border_vehicle_info": "рейс/номер/судно (гр.21)",
  "border_vehicle_country": "ISO2 или 00/99 (гр.21)",
  "currency": "ISO4217 (гр.22) — ТОЛЬКО из контракта",
  "deal_nature_code": "3-значный код (гр.24, дефолт 010)",
  "deal_specifics_code": "2-значный код (гр.24, дефолт 01)",
  "transport_type": "10/20/30/40 (гр.25)",
  "transport_type_inland": "10/20/30/40 (гр.26)",
  "special_features_code": "код особенности или null (гр.7)",
  "contract_number": "номер контракта",
  "contract_date": "дата контракта",
  "invoice_number": "номер инвойса",
  "invoice_date": "дата инвойса",
  "transport_doc_number": "номер AWB/CMR/B-L",
  "destination_airport": "IATA код аэропорта назначения (для гр.29 lookup)",
  "total_packages": число (гр.6),
  "package_type": "тип упаковки",
  "freight_amount": число,
  "freight_currency": "ISO4217",
  "valuation_method": "1 (гр.43, дефолт)",
  "items": [
{{
  "line_no": 1,
  "description": "наименование товара (из техописания если есть, иначе из инвойса)",
  "quantity": число,
  "unit": "единица измерения",
  "unit_price": число,
  "line_total": число,
  "country_origin_code": "ISO2 (гр.34)",
  "procedure_code": "4000 (гр.37)"
}}
  ],
  "evidence_map": {{
"seller": {{"source": "transport_doc", "confidence": 0.9, "graph": 2}},
"buyer": {{"source": "contract", "confidence": 0.95, "graph": 14}},
"currency": {{"source": "contract", "confidence": 0.97, "graph": 22}}
  }}
}}

JSON:"""

    try:
        client = get_llm_client(operation="compile_declaration_llm")
        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=6000,
            **json_format_kwargs(),
        )
        raw = strip_code_fences(resp.choices[0].message.content)
        finish_reason = resp.choices[0].finish_reason

        if finish_reason == "length":
            logger.warning("compile_declaration_truncated_retrying")
            resp = client.chat.completions.create(
                model=get_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=10000,
                **json_format_kwargs(),
            )
            raw = strip_code_fences(resp.choices[0].message.content)

        result = _json.loads(raw)
        logger.info("compile_declaration_llm_ok", fields=list(result.keys()),
                    items_count=len(result.get("items", [])))
        return result
    except Exception as e:
        logger.error("compile_declaration_llm_failed", error=str(e))
        return {"items": [], "evidence_map": {}, "issues": [
            {"id": "compile_llm_failed", "severity": "error", "message": f"LLM compilation failed: {e}"}
        ]}
