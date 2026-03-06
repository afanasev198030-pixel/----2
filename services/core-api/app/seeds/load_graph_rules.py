"""
Сид-скрипт: загрузить правила заполнения граф ДТ в БД.
Данные основаны на официальной инструкции по заполнению ДТ (ЕАЭС)
плюс AI-специфические правила из declaration_mapping_v3.yaml.

Запуск:
    cd services/core-api
    python -m app.seeds.load_graph_rules
"""
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, text

from app.config import settings

DATABASE_URL = settings.database_url

# ── Данные правил ─────────────────────────────────────────────────────────────
# fill_instruction — официальное описание из нормативной инструкции
# ai_rule          — специальное правило для LLM/AI-агента
# source_priority  — приоритет источников (уточняется на 2-м шаге)
# confidence_map   — уверенность по источнику (0..1)
# validation_rules — машиночитаемые правила валидации
# target_field     — поле в схеме core-api
# ─────────────────────────────────────────────────────────────────────────────

GRAPH_RULES = [
    # ── РАЗДЕЛ: ОБЩИЕ СВЕДЕНИЯ (header) ──────────────────────────────────────
    {
        "graph_number": 1,
        "graph_name": "Декларация",
        "section": "header",
        "fill_instruction": (
            "Тип декларации. Три подраздела: "
            "1) ИМ (импорт) или ЭК (экспорт); "
            "2) двузначный код таможенной процедуры (по Классификатору видов таможенных процедур); "
            "3) ЭД — только при подаче ДТ в виде электронного документа."
        ),
        "fill_format": "Подраздел 1: ИМ/ЭК. Подраздел 2: код процедуры (40, 10...). Подраздел 3: ЭД.",
        "ai_rule": (
            "Заполнять код процедуры в соответствии с выбранным пользователем типом декларации. "
            "Если тип не задан — предложить ИМ40 для импорта с флагом «проверьте»."
        ),
        "is_required": True,
        "default_value": "IM40",
        "default_flag": "проверьте тип процедуры",
        "validation_rules": {"type": "string", "examples": ["IM40", "EX10", "TT"]},
        "source_priority": ["application_statement", "contract"],
        "confidence_map": {"application_statement": 0.9, "contract": 0.7, "default": 0.3},
        "target_field": "type_code",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 2,
        "graph_name": "Отправитель/Экспортёр",
        "section": "header",
        "fill_instruction": (
            "Сведения об иностранном отправителе/экспортёре товара. "
            "Заполнить: наименование (полное), ИНН или эквивалентный иностранный налоговый номер "
            "(VAT, Tax ID и т.п.), КПП (если применимо), ОГРН или эквивалентный регистрационный номер, "
            "адрес (улица, город, страна). "
            "При наличии нескольких отправителей — делается отметка «Различные»."
        ),
        "fill_format": "Наименование, ИНН/Tax ID, КПП (если есть), ОГРН/Reg.No., адрес (улица, город, страна).",
        "ai_rule": (
            "Приоритет источников: заявка (Application) → транспортный инвойс → инвойс на товары. "
            "Контракт/договор НЕ является источником для этой графы. "
            "1. Наименование компании (полное). "
            "2. ИНН или эквивалент (VAT, Tax ID, ИНН — в зависимости от страны компании). "
            "3. КПП — если применимо; для иностранных компаний может отсутствовать. "
            "4. ОГРН или эквивалент (Company Reg. No., Commercial Register No. и т.п.). "
            "5. Адрес: улица, город, страна. "
            "6. Код страны (ISO 3166-1 alpha-2). "
            "Страна обычно не RU при импорте — если RU, поднять warning. "
            "При нескольких отправителях указать «Различные»."
        ),
        "is_required": True,
        "validation_rules": {
            "type": "object",
            "required_fields": ["name", "inn", "address", "country_code"],
            "optional_fields": ["kpp", "ogrn"],
            "country_code": {"type": "iso3166_1_alpha2", "not_eq": "RU"},
            "note": "обычно не RU при импорте; ИНН/КПП/ОГРН — российские аналоги, для иностранных компаний брать эквиваленты"
        },
        "source_priority": ["application_statement", "transport_invoice", "invoice"],
        "source_fields": {
            "application_statement": {
                "fields": ["forwarding_agent_name", "forwarding_agent_address", "forwarding_agent_inn", "отправитель"],
                "notes": (
                    "Заявка (Application forwarder / Application transport) — поле «Отправитель» / «Forwarding Agent». "
                    "Приоритетный источник актуальных данных по конкретной отгрузке."
                ),
            },
            "transport_invoice": {
                "fields": ["shipper_name", "shipper_address"],
                "notes": "Поле «Shipper» / «Отправитель груза» — резервный источник.",
            },
            "invoice": {
                "fields": ["seller_name", "seller_address", "seller_tax_id"],
                "notes": "Поле «Seller» — резервный источник если заявка и транспортный инвойс не содержат данных.",
            },
        },
        "confidence_map": {
            "application_statement": 0.95,
            "transport_invoice": 0.85,
            "invoice": 0.75,
        },
        "target_field": "sender_counterparty_id",
        "target_kind": "core_declaration_relation",
    },
    {
        "graph_number": 3,
        "graph_name": "Формуляры (листы ДТ)",
        "section": "header",
        "fill_instruction": (
            "Указывает порядковый номер текущего листа и общее количество листов ДТ. "
            "Подраздел 1: порядковый номер текущего листа (X). "
            "Подраздел 2: общее количество листов ДТ, включая основной и все добавочные (Y). "
            "Формат: «X/Y», например «2/3». На основном листе не заполняется."
        ),
        "fill_format": "X/Y (например: 2/3). На основном листе — пусто.",
        "ai_rule": (
            "Количество позиций брать ТОЛЬКО из инвойса на товары. "
            "Расчёт: total_sheets = 1 + ceil((total_items - 1) / 3) при total_items > 1. "
            "Основной лист вмещает 1 товар, каждый добавочный — до 3 товаров. "
            "На основном листе (лист 1) Графа 3 не заполняется. "
            "На добавочных листах: X = номер листа начиная с 2, Y = total_sheets."
        ),
        "compute_expression": "1 + ceil((total_items - 1) / 3) if total_items > 1 else 1",
        "validation_rules": {"type": "integer", "min": 1},
        "source_priority": ["invoice"],
        "confidence_map": {"computed": 0.9},
        "target_field": "forms_count",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 4,
        "graph_name": "Отгрузочные спецификации",
        "section": "header",
        "fill_instruction": (
            "Количество приложенных к ДТ отгрузочных спецификаций. "
            "Заполняется только если отгрузочные спецификации есть. "
            "В остальных случаях оставить пустым."
        ),
        "fill_format": "Целое число ≥ 1. Если спецификаций нет — пусто.",
        "ai_rule": (
            "Проверить наличие документов типа specification среди загруженных файлов. "
            "Если есть — указать их количество. Если нет — оставить поле пустым (null)."
        ),
        "compute_expression": "count(specification_docs) if specification_docs else null",
        "validation_rules": {"type": "integer", "min": 1, "nullable": True},
        "source_priority": ["specification"],
        "confidence_map": {"computed": 0.8},
        "target_field": "specifications_count",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 5,
        "graph_name": "Всего товаров",
        "section": "header",
        "fill_instruction": (
            "Общее количество наименований товаров, указанных в ДТ (по всем листам). "
            "Это количество товарных наименований (позиций), а не штук."
        ),
        "fill_format": "Целое число ≥ 1 — количество наименований, не штук.",
        "ai_rule": (
            "Источник — инвойс на товары (goods invoice). "
            "ВАЖНО: не использовать транспортный инвойс (freight invoice/инвойс за перевозку). "
            "В инвойсе: считать строки товарных позиций (line items). "
            "В PL: считать уникальные наименования товаров, а не штуки/места. "
            "Контроль: если есть оба документа — сравнить количество наименований. "
            "При расхождении — поднять issue и показать обе цифры."
        ),
        "is_required": True,
        "compute_expression": "len(distinct_item_names)",
        "conflict_check": "count(invoice.line_items) == count(pl.distinct_names); при расхождении — issue с обеими цифрами",
        "validation_rules": {"type": "integer", "min": 1},
        "source_priority": ["invoice", "packing_list"],
        "confidence_map": {"invoice": 0.95, "packing_list": 0.9},
        "target_field": "total_items_count",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 6,
        "graph_name": "Количество мест",
        "section": "header",
        "fill_instruction": (
            "Общее количество грузовых мест по всем товарам в ДТ."
        ),
        "fill_format": "Целое число.",
        "ai_rule": (
            "Брать total packages из PL. "
            "Если PL и транспортный документ расходятся — показать обе цифры и поднять флаг."
        ),
        "validation_rules": {"type": "integer", "min": 0},
        "conflict_check": "Если packing_list и transport_doc расходятся — показать обе цифры и поднять flag",
        "source_priority": ["packing_list", "transport_doc", "acceptance_act"],
        "confidence_map": {"packing_list": 0.9, "transport_doc": 0.7},
        "target_field": "total_packages_count",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 7,
        "graph_name": "Особенности декларирования",
        "section": "header",
        "fill_instruction": (
            "Код особенности декларирования товаров из классификатора особенностей "
            "таможенного декларирования. "
            "Заполняется только если для данной партии есть применимый код. "
            "Если особенностей нет или код не предусмотрен классификатором — оставить пустым."
        ),
        "fill_format": "Код из классификатора, до 9 знаков. Если не применимо — пусто.",
        "ai_rule": (
            "НЕ заполнять автоматически. "
            "Оставить пустым и подсветить для пользователя с сообщением: "
            "«Укажите код особенности декларирования из классификатора или оставьте пустым». "
            "Уровень подсветки: info."
        ),
        "validation_rules": {"type": "string", "max_len": 9, "nullable": True},
        "source_priority": [],
        "confidence_map": {},
        "target_field": "special_ref_code",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 8,
        "graph_name": "Получатель",
        "section": "header",
        "fill_instruction": (
            "Сведения о получателе товара на территории ЕАЭС: наименование, ИНН/КПП, ОГРН, адрес."
        ),
        "fill_format": "Наименование, ИНН (10 или 12 цифр), КПП (9 цифр), ОГРН (13 или 15 цифр), адрес.",
        "ai_rule": (
            "Источники в порядке приоритета: "
            "1) профиль компании в системе (наивысший приоритет); "
            "2) контракт — раздел «Buyer» / «Покупатель»; "
            "3) инвойс на товары — поле «Buyer» / «Покупатель» (не транспортный инвойс). "
            "Приоритет языка: если реквизиты есть и на русском, и на английском — "
            "использовать русскоязычный вариант."
        ),
        "is_required": True,
        "validation_rules": {
            "type": "object",
            "required_fields": ["name", "address"],
            "inn": {"type": "digits", "length": [10, 12]},
            "kpp": {"type": "digits", "length": [9]},
            "ogrn": {"type": "digits", "length": [13, 15]},
        },
        "source_priority": ["company_profile", "contract", "invoice"],
        "source_fields": {
            "company_profile": {"fields": ["company_name_ru", "inn", "kpp", "ogrn", "legal_address"], "notes": "Наивысший приоритет"},
            "contract": {"fields": ["buyer.name", "buyer.address", "buyer.inn", "buyer.kpp"], "notes": "Раздел Buyer/Покупатель, предпочитать русский язык"},
            "invoice": {"fields": ["buyer.name", "buyer.address"], "notes": "Поле Buyer/Покупатель, предпочитать русский язык"},
        },
        "confidence_map": {"company_profile": 0.95, "contract": 0.85, "invoice": 0.8},
        "target_field": "receiver_counterparty_id",
        "target_kind": "core_declaration_relation",
    },
    {
        "graph_number": 9,
        "graph_name": "Лицо, ответственное за финансовое урегулирование",
        "section": "header",
        "fill_instruction": (
            "Лицо, несущее финансовую ответственность за сделку. "
            "Если есть доверенность или договор с таможенным представителем — "
            "извлечь реквизиты из документа. "
            "Если таких документов нет — заполнить: «СМ. ГРАФУ 14 ДТ»."
        ),
        "fill_format": "Реквизиты лица (наименование, ИНН/КПП) или фиксированный текст «СМ. ГРАФУ 14 ДТ».",
        "default_value": "СМ. ГРАФУ 14 ДТ",
        "ai_rule": (
            "Проверить наличие доверенности или договора с брокером среди загруженных документов. "
            "Если документы есть — извлечь реквизиты. "
            "Если документов нет — заполнить фиксированным текстом «СМ. ГРАФУ 14 ДТ»."
        ),
        "validation_rules": {"type": "string"},
        "source_priority": ["power_of_attorney", "broker_agreement"],
        "source_fields": {
            "power_of_attorney": {"fields": ["principal.name", "principal.inn", "principal.kpp"], "notes": "Доверенность на таможенного представителя"},
            "broker_agreement": {"fields": ["party.name", "party.inn", "party.kpp"], "notes": "Договор с таможенным представителем (брокером)"},
        },
        "confidence_map": {"power_of_attorney": 0.9, "broker_agreement": 0.8, "fallback": 1.0},
        "target_field": "financial_responsible",
        "target_kind": "extension",
    },

    # ── РАЗДЕЛ: ТРАНСПОРТ И МАРШРУТ ───────────────────────────────────────────
    {
        "graph_number": 10,
        "graph_name": "Станция 1-го назначения",
        "section": "header",
        "fill_instruction": "Графа 10 не заполняется.",
        "skip": True,
        "ai_rule": "Не заполнять.",
        "source_priority": [],
        "target_field": "first_destination_country_code",
        "target_kind": "extension",
    },
    {
        "graph_number": 11,
        "graph_name": "Торгующая страна",
        "section": "header",
        "fill_instruction": (
            "Страна местонахождения иностранного контрагента (продавца)."
        ),
        "fill_format": "ISO 3166-1 alpha-2, например: CN, DE, US.",
        "ai_rule": (
            "Источники в порядке приоритета: "
            "1) контракт — страна из реквизитов продавца/поставщика; "
            "2) сертификат происхождения — страна контрагента; "
            "3) инвойс на товары — страна из реквизитов продавца. "
            "При конфликте: приоритет контракт > сертификат > инвойс."
        ),
        "validation_rules": {"type": "iso3166_1_alpha2"},
        "source_priority": ["contract", "origin_certificate", "invoice"],
        "source_fields": {
            "contract": {"fields": ["seller.country", "supplier.country"], "notes": "Страна из реквизитов продавца/поставщика"},
            "origin_certificate": {"fields": ["exporter.country", "consignor.country"], "notes": "Страна контрагента в сертификате"},
            "invoice": {"fields": ["seller.country", "shipper.country"], "notes": "Страна из реквизитов продавца в инвойсе на товары"},
        },
        "confidence_map": {"contract": 0.9, "origin_certificate": 0.85, "invoice": 0.8},
        "target_field": "trading_country_code",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 12,
        "graph_name": "Общая таможенная стоимость",
        "section": "header",
        "fill_instruction": (
            "Суммарная таможенная стоимость всех товаров по ДТ в валюте государства — "
            "члена ЕАЭС (в рублях для РФ)."
        ),
        "fill_format": "Число в рублях, округление до 2 знаков после запятой.",
        "ai_rule": (
            "Сумма значений графы 45 по всем позициям. "
            "Требует курс ЦБ (гр. 23). Если нет ДТС-1 — считать приближённо «по инвойсу × курс» "
            "и пометить как предварительное."
        ),
        "compute_expression": "sum(items[].customs_value_rub)",
        "validation_rules": {"type": "money_rub", "round": 2},
        "source_priority": ["dts1_customs_value_calc", "invoice", "contract", "transport_invoice"],
        "confidence_map": {"dts1_customs_value_calc": 0.95, "computed_invoice_fx": 0.6},
        "target_field": "total_customs_value",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 13,
        "graph_name": "Резервная",
        "section": "header",
        "fill_instruction": (
            "Не заполняется участниками ВЭД. "
            "Предназначена для служебных отметок таможенного органа."
        ),
        "skip": True,
        "target_field": None,
        "target_kind": None,
    },
    {
        "graph_number": 14,
        "graph_name": "Декларант",
        "section": "header",
        "fill_instruction": (
            "Краткое наименование организации, место нахождения, ИНН/КПП, ОГРН лица, подающего ДТ. "
            "Если есть доверенность или договор с брокером — заполнить данными брокера. "
            "Если таких документов нет — заполнить данными Получателя (как в Графе 8)."
        ),
        "fill_format": "Краткое наименование, место нахождения, ИНН, КПП, ОГРН.",
        "ai_rule": (
            "Проверить наличие доверенности или договора с брокером. "
            "Если есть — брать данные брокера/таможенного представителя. "
            "Если нет — брать данные Получателя: "
            "1) профиль компании в системе; "
            "2) контракт — раздел «Buyer» / «Покупатель»; "
            "3) инвойс на товары — поле «Buyer» / «Покупатель». "
            "Приоритет языка: русский > английский."
        ),
        "is_required": True,
        "validation_rules": {
            "type": "object",
            "required_fields": ["short_name", "location", "inn", "kpp", "ogrn"],
            "inn": {"type": "digits", "length": [10, 12]},
            "kpp": {"type": "digits", "length": [9]},
            "ogrn": {"type": "digits", "length": [13, 15]},
        },
        "source_priority": ["power_of_attorney", "broker_agreement", "company_profile", "contract", "invoice"],
        "source_fields": {
            "power_of_attorney": {"fields": ["broker.short_name", "broker.location", "broker.inn", "broker.kpp", "broker.ogrn"], "notes": "Данные брокера при наличии доверенности"},
            "broker_agreement": {"fields": ["broker.short_name", "broker.location", "broker.inn", "broker.kpp"], "notes": "Данные брокера при наличии договора"},
            "company_profile": {"fields": ["short_name_ru", "legal_address", "inn", "kpp", "ogrn"], "notes": "Данные получателя из профиля, если нет брокера"},
            "contract": {"fields": ["buyer.short_name", "buyer.location", "buyer.inn", "buyer.kpp"], "notes": "Раздел Buyer/Покупатель, предпочитать русский язык"},
            "invoice": {"fields": ["buyer.short_name", "buyer.address"], "notes": "Поле Buyer/Покупатель в инвойсе на товары, предпочитать русский язык"},
        },
        "confidence_map": {
            "power_of_attorney": 0.95, "broker_agreement": 0.9,
            "company_profile": 0.95, "contract": 0.85, "invoice": 0.8,
        },
        "target_field": "declarant_inn_kpp",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 15,
        "graph_name": "Страна отправления",
        "section": "header",
        "fill_instruction": (
            "Страна, из которой непосредственно прибыл товар (не страна происхождения). "
            "Определяется на основании транспортных документов международной перевозки. "
            "Графа 15 — словесное наименование страны. "
            "Графа 15А — буквенный код страны (ISO 3166-1 alpha-2)."
        ),
        "fill_format": "15А: ISO 3166-1 alpha-2. 15: полное наименование страны.",
        "ai_rule": (
            "Источники в порядке приоритета: "
            "1) AWB или CMR — поле «Departure» / «From»; "
            "2) транспортный инвойс — поле «Departure». "
            "Не путать со страной происхождения товара (Графа 16)."
        ),
        "is_required": True,
        "validation_rules": {"type": "iso3166_1_alpha2"},
        "source_priority": ["transport_doc", "transport_invoice"],
        "source_fields": {
            "transport_doc": {"fields": ["departure_country", "from_country"], "notes": "AWB или CMR — поле Departure / From"},
            "transport_invoice": {"fields": ["departure_country", "departure"], "notes": "Транспортный инвойс — поле Departure"},
        },
        "confidence_map": {"transport_doc": 0.95, "transport_invoice": 0.85},
        "target_field": "country_dispatch_code",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 16,
        "graph_name": "Страна происхождения",
        "section": "header",
        "fill_instruction": (
            "Страна, в которой товар был произведён или подвергнут достаточной обработке. "
            "Используется для определения ставки пошлины и преференций. "
            "Источники: сертификат происхождения, декларация соответствия (страна изготовителя)."
        ),
        "fill_format": (
            "ISO 3166-1 alpha-2, или «ЕВРОСОЮЗ», или «РАЗНЫЕ». "
            "Если все неизвестны — пусто + подсветка для пользователя."
        ),
        "ai_rule": (
            "Источники: сертификат происхождения (приоритет), декларация соответствия (страна изготовителя). "
            "Логика заполнения: "
            "1) если маркировка/документы указывают на ЕС без конкретной страны → «ЕВРОСОЮЗ»; "
            "2) если товары из разных стран ИЛИ страна хотя бы одного товара неизвестна → «РАЗНЫЕ»; "
            "3) если страна всех товаров неизвестна → записать «НЕИЗВЕСТНО» и подсветить пользователю (severity: warning); "
            "4) не заполнять при декларировании наличной валюты (банкноты/монеты) на транспорте."
        ),
        "is_required": True,
        "validation_rules": {
            "type": "string",
            "special_values": ["ЕВРОСОЮЗ", "РАЗНЫЕ"],
            "or_iso3166_1_alpha2": True,
            "nullable": True,
        },
        "source_priority": ["origin_certificate", "conformity_declaration"],
        "source_fields": {
            "origin_certificate": {"fields": ["country_of_origin", "origin_country"], "notes": "Сертификат происхождения — основной источник"},
            "conformity_declaration": {"fields": ["manufacturer_country", "country_of_manufacture"], "notes": "Декларация соответствия — поле «страна изготовителя»"},
        },
        "confidence_map": {"origin_certificate": 0.95, "conformity_declaration": 0.85},
        "target_field": "country_origin_code",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 17,
        "graph_name": "Страна назначения",
        "section": "header",
        "fill_instruction": (
            "Краткое название страны, известной на день подачи ДТ в качестве страны назначения, "
            "где товары будут потребляться, использоваться или подвергнуты дальнейшей переработке. "
            "Если конечная страна неизвестна — указать страну доставки. "
            "«НЕИЗВЕСТНА» допустимо только для: беспошлинной торговли (вывоз), "
            "неполной/периодической ДТ, временной ДТ."
        ),
        "fill_format": (
            "Графа 17: краткое наименование страны. "
            "Графа 17А: двузначный буквенный код по классификатору стран мира (ISO 3166-1 alpha-2) — "
            "заполняется автоматически из значения Графы 17. "
            "Или «НЕИЗВЕСТНА» (только в допустимых случаях)."
        ),
        "ai_rule": (
            "Источник: транспортные документы AWB/CMR — поле «страна прибытия» / destination. "
            "Если конечная страна потребления неизвестна — указать страну доставки. "
            "«НЕИЗВЕСТНА» использовать только для процедур беспошлинной торговли, "
            "неполной/периодической ДТ или временной ДТ. В остальных случаях не применять."
        ),
        "is_required": True,
        "validation_rules": {
            "type": "string",
            "special_values": ["НЕИЗВЕСТНА"],
            "or_iso3166_1_alpha2": True,
        },
        "source_priority": ["transport_doc"],
        "conflict_check": "Гр. 17 обычно совпадает с гр. 10; при расхождении — поднять warning для пользователя",
        "source_fields": {
            "transport_doc": {"fields": ["destination_country", "country_of_destination", "arrival_country"], "notes": "AWB/CMR — поле страна прибытия / destination"},
        },
        "confidence_map": {"transport_doc": 0.95},
        "target_field": "country_destination_code",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 18,
        "graph_name": "Идентификация и страна регистрации ТС при отправлении",
        "section": "header",
        "fill_instruction": (
            "Идентификационный номер транспортного средства, перевозящего товар "
            "при прибытии/убытии с таможенной территории. "
            "Подраздел 1: кол-во ТС + номера через «;». "
            "Подраздел 2: код страны регистрации ТС (ISO). "
            "При ж/д транспорте — подраздел 2 не заполняется. "
            "Не заполняется при отсутствии международной перевозки и для МПО."
        ),
        "fill_format": (
            "Авто: рег. номера (активное/прицепы через «/»). "
            "ЖД: номера вагонов. Море: названия судов. Авиа: номера рейсов."
        ),
        "ai_rule": (
            "Извлечь из транспортного документа. "
            "Тип транспорта определяет формат: авто/жд/море/авиа/трубопровод."
        ),
        "validation_rules": {
            "type": "string",
            "max_len": 512,
            "skip_condition": "при отсутствии международной перевозки и для МПО",
        },
        "source_priority": ["transport_doc"],
        "confidence_map": {"transport_doc": 0.9},
        "target_field": "transport_at_border",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 19,
        "graph_name": "Контейнер",
        "section": "header",
        "fill_instruction": (
            "Признак перевозки в контейнере: «1» — да, «0» — нет. "
            "Определяется из транспортных документов."
        ),
        "fill_format": "1 — контейнер, 0 — иные случаи.",
        "ai_rule": (
            "Источник: транспортные документы AWB / CMR / B/L. "
            "Если в документе есть номер контейнера (формат XXXX 1234567) или "
            "явное указание на контейнерную перевозку — ставить «1». "
            "В остальных случаях — «0»."
        ),
        "default_value": "0",
        "validation_rules": {
            "type": "enum",
            "values": ["0", "1"],
            "labels": {"1": "перевозка в контейнере", "0": "иные случаи"},
        },
        "source_priority": ["transport_doc"],
        "source_fields": {
            "transport_doc": {"fields": ["container_number", "container_id", "container"], "notes": "AWB/CMR/B/L — наличие номера контейнера или пометки container"},
        },
        "confidence_map": {"transport_doc": 0.95},
        "target_field": "container_info",
        "target_kind": "core_declaration",
    },

    # ── РАЗДЕЛ: ФИНАНСОВЫЕ И ТРАНСПОРТНЫЕ УСЛОВИЯ ────────────────────────────
    {
        "graph_number": 20,
        "graph_name": "Условия поставки",
        "section": "header",
        "fill_instruction": (
            "Код поставки по Инкотермс и место поставки — наименование географического пункта, "
            "к которому относится базис. Например: CIF Москва, FOB Shanghai."
        ),
        "fill_format": "Код Инкотермс (3 буквы) + наименование географического пункта.",
        "ai_rule": (
            "Источники (по приоритету): заявка → договор поставки. "
            "Извлечь: 1) код Инкотермс (3 буквы: EXW, FCA, CPT, CIP, DAP, DPU, DDP, FAS, FOB, CFR, CIF); "
            "2) наименование географического пункта (город/порт/склад), к которому относится базис. "
            "Хранить оба значения: код и место. "
            "Если заявка и договор содержат разные условия — приоритет заявки, поднять предупреждение."
        ),
        "is_required": True,
        "validation_rules": {
            "type": "incoterms_2020",
            "valid_codes": ["EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS", "FOB", "CFR", "CIF"],
        },
        "source_priority": ["application_statement", "contract"],
        "source_fields": {
            "application_statement": {
                "fields": ["delivery_terms", "incoterms", "delivery_place", "delivery_basis"],
                "notes": "Заявка — приоритетный источник: условия поставки для данной конкретной отгрузки.",
            },
            "contract": {
                "fields": ["delivery_terms", "incoterms", "delivery_basis", "basis_of_delivery"],
                "notes": "Договор поставки — раздел «Delivery Terms» / «Базис поставки». Резервный источник.",
            },
        },
        "confidence_map": {"application_statement": 0.97, "contract": 0.95},
        "target_field": "incoterms_code",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 21,
        "graph_name": "Активное ТС на границе",
        "section": "header",
        "fill_instruction": (
            "Идентификация транспортного средства, пересекающего таможенную границу. "
            "Формат: [кол-во ТС]: [идентификатор1];[идентификатор2] — без пробелов вокруг «;»."
        ),
        "fill_format": (
            "Подраздел 1: [кол-во ТС]:[id1];[id2] без пробелов. "
            "Авто: рег. номера. Море/река: названия судов. Авиа: номера рейсов. "
            "Трубопровод/ЛЭП: «газопровод», «нефтепровод», «нефтепродуктопровод», «линии электропередачи». "
            "Подраздел 2: ISO-код страны регистрации ТС / «00» (неизвестна) / «99» (разные страны). "
            "При трубопроводе/ЛЭП — подраздел 2 не заполняется."
        ),
        "ai_rule": (
            "Источник: транспортный документ AWB / CMR / B/L (НЕ транспортный инвойс). "
            "Шаг 1: определить тип транспортного документа. "
            "Шаг 2: извлечь идентификатор ТС в зависимости от типа: "
            "AWB → номер рейса (flight number, например CA836); "
            "CMR → государственный регистрационный номер грузового автомобиля (тягача); "
            "B/L → название судна (vessel name); "
            "ж/д — номер поезда. "
            "Шаг 3: сформировать подраздел 1: [кол-во ТС]:[id1];[id2] без пробелов. "
            "Подраздел 2 — код страны регистрации ТС (ISO alpha-2): "
            "состав ТС → код страны тягача; "
            "страна неизвестна → «00»; "
            "несколько ТС из разных стран → «99»; "
            "трубопровод/ЛЭП → не заполнять."
        ),
        "validation_rules": {"type": "string", "format": "N:id1;id2"},
        "source_priority": ["transport_doc"],
        "source_fields": {
            "transport_doc": {
                "fields": ["vehicle_id", "flight_number", "truck_plate", "vessel_name", "transport_country_code"],
                "notes": (
                    "AWB: vehicle_id = номер рейса (flight number). "
                    "CMR: vehicle_id = рег. номер грузовика (тягача). "
                    "B/L: vehicle_id = название судна. "
                    "НЕ использовать транспортный инвойс для этой графы."
                ),
            },
        },
        "confidence_map": {"transport_doc": 0.9},
        "target_field": "transport_on_border_id",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 22,
        "graph_name": "Валюта и общая фактурная стоимость",
        "section": "header",
        "fill_instruction": (
            "Подраздел 1: код валюты ТОЛЬКО из договора/контракта купли-продажи (ISO 4217). "
            "Инвойс не является источником для кода валюты. "
            "Подраздел 2: общая стоимость = сумма значений Графы 42 по всем позициям "
            "основного и добавочных листов ДТ."
        ),
        "fill_format": "Код валюты ISO 4217 (из контракта) + сумма (sum гр. 42). Пример: USD 125000.00",
        "ai_rule": (
            "Код валюты — брать ТОЛЬКО из договора/контракта купли-продажи. "
            "Инвойс для валюты НЕ использовать. "
            "Для поиска валюты в тексте контракта искать ключевые фразы: "
            "«Валютой Контракта являются», «Валюта контракта —», "
            "«Contract currency is», «Payment currency:», «расчёты производятся в». "
            "После ключевой фразы следует название или код валюты — привести к ISO 4217: "
            "доллары США → USD, евро → EUR, юани / RMB / CNY → CNY, рубли → RUB. "
            "Если ключевые фразы не найдены — взять валюту из раздела оплаты/платежей контракта. "
            "Сумму рассчитывать как sum(items[].graph_42). "
            "Для проверки суммы сравнить с итоговой суммой инвойса на товары. "
            "При расхождении суммы — поднять warning."
        ),
        "is_required": True,
        "compute_expression": "sum(items[].graph_42)",
        "conflict_check": "sum(items[].graph_42) должна совпадать с итогом инвойса на товары; при расхождении — warning",
        "validation_rules": {
            "currency": {"type": "iso4217"},
            "amount": {"type": "money", "min": 0},
        },
        "source_priority": ["contract", "invoice"],
        "source_fields": {
            "contract": {
                "fields": ["currency", "contract_currency"],
                "keywords": [
                    "Валютой Контракта являются",
                    "Валюта контракта",
                    "Contract currency is",
                    "Payment currency",
                    "расчёты производятся в",
                ],
                "notes": (
                    "Договор/контракт купли-продажи — ЕДИНСТВЕННЫЙ источник кода валюты. "
                    "Искать ключевые фразы выше, после которых следует название валюты. "
                    "Привести к ISO 4217: доллары США→USD, евро→EUR, юани/RMB→CNY, рубли→RUB."
                ),
            },
            "invoice": {
                "fields": ["total_amount", "invoice_total"],
                "notes": "Инвойс на товары — только для сверки суммы. НЕ источник валюты. НЕ транспортный инвойс.",
            },
        },
        "confidence_map": {"contract": 0.97, "invoice": 0.0},
        "target_field": "total_invoice_value",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 23,
        "graph_name": "Курс валюты",
        "section": "header",
        "fill_instruction": (
            "Курс иностранной валюты к валюте государства — члена ЕАЭС "
            "на дату регистрации ДТ."
        ),
        "fill_format": "Десятичное число. Курс ЦБ РФ на дату подачи/принятия ДТ.",
        "ai_rule": (
            "Использовать официальный курс ЦБ РФ на дату принятия ДТ. "
            "Запросить через API ЦБ или использовать ближайший доступный."
        ),
        "validation_rules": {"type": "decimal", "min": 0},
        "source_priority": ["cbr_official_rate"],
        "target_field": "exchange_rate",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 24,
        "graph_name": "Характер сделки",
        "section": "header",
        "fill_instruction": (
            "Три подраздела. "
            "Подраздел 1: трёхзначный код характера сделки (по Классификатору характера сделки). "
            "Подраздел 2: двузначный код особенности сделки (по Классификатору особенности сделки). "
            "Подраздел 3: не заполняется."
        ),
        "fill_format": "Подраздел 1: 3-значный код (010, 020, 030). Подраздел 2: 2-значный код (01). Подраздел 3: пусто.",
        "ai_rule": "Если не найдено в документах — дефолт 010/01 с флагом «проверьте».",
        "default_value": "010",
        "default_flag": "проверьте характер сделки",
        "validation_rules": {
            "type": "object",
            "subsection1": {"type": "string", "length": 3, "examples": ["010", "020", "030"]},
            "subsection2": {"type": "string", "length": 2, "examples": ["01"]},
            "labels": {"010": "купля-продажа", "020": "бартер", "030": "безвозмездная"},
        },
        "source_priority": ["contract"],
        "source_fields": {
            "contract": {"fields": ["deal_type", "transaction_type", "contract_type"], "notes": "Контракт/договор — тип сделки (купля-продажа, бартер, безвозмездная и т.д.)"},
        },
        "confidence_map": {"contract": 0.9},
        "target_field": "deal_nature_code",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 25,
        "graph_name": "Вид транспорта на границе",
        "section": "header",
        "fill_instruction": (
            "Код вида транспорта, которым товар пересекает таможенную границу "
            "(морской, воздушный, железнодорожный, автомобильный и т.д.)."
        ),
        "fill_format": "10 — море, 20 — ж/д, 30 — авто, 40 — воздух.",
        "ai_rule": (
            "Источник: транспортные документы AWB / CMR / B/L. "
            "Определить код по типу документа: "
            "AWB → «40» (воздух); CMR → «30» (авто); B/L → «10» (море); ж/д накладная → «20»."
        ),
        "is_required": True,
        "validation_rules": {
            "type": "enum",
            "values": ["10", "20", "30", "40"],
            "labels": {"10": "морской", "20": "железнодорожный", "30": "автомобильный", "40": "воздушный"},
        },
        "source_priority": ["transport_doc"],
        "source_fields": {
            "transport_doc": {"fields": ["document_type", "transport_mode"], "notes": "AWB→40, CMR→30, B/L→10, ж/д накладная→20"},
        },
        "confidence_map": {"transport_doc": 0.95},
        "target_field": "transport_type_border",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 26,
        "graph_name": "Вид транспорта внутри страны",
        "section": "header",
        "fill_instruction": (
            "Подраздел 1: код вида ТС, сведения о котором указаны в Графе 18 "
            "(по Классификатору видов транспорта и транспортировки товаров). "
            "Подраздел 2: не заполняется. "
            "Не заполняется при отсутствии международной перевозки; в РБ."
        ),
        "fill_format": "Код вида транспорта из графы 18. Подраздел 2: пусто.",
        "ai_rule": (
            "Код вида транспорта — тот же, что использован во внутренней перевозке (графа 18). "
            "AWB→40, CMR→30, B/L→10, ж/д→20. "
            "Не заполняется при отсутствии международной перевозки."
        ),
        "source_priority": ["transport_doc"],
        "target_field": "transport_type_inland",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 27,
        "graph_name": "Место погрузки/разгрузки",
        "section": "header",
        "fill_instruction": "Графа 27 не заполняется.",
        "skip": True,
        "ai_rule": "Не заполнять.",
        "source_priority": [],
        "target_field": "loading_place",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 28,
        "graph_name": "Финансовые и банковские сведения",
        "section": "header",
        "fill_instruction": "Графа 28 не заполняется.",
        "skip": True,
        "ai_rule": "Не заполнять.",
        "source_priority": [],
        "target_field": "financial_info",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 29,
        "graph_name": "Таможня на границе",
        "section": "header",
        "fill_instruction": (
            "Код таможенного органа места ввоза/вывоза — пункта пропуска через "
            "государственную границу. "
            "Для РФ: 8-значный код. "
            "Для ввоза через РБ/КЗ: «ZZZ XXXXX» (3 цифры государства + 5 цифр органа). "
            "При нескольких пунктах — перечислить все коды."
        ),
        "fill_format": "8 цифр (РФ) или ZZZ XXXXX (через РБ/КЗ).",
        "ai_rule": (
            "Определить место прибытия из транспортных документов. "
            "Сопоставить с классификатором таможенных органов для получения кода."
        ),
        "validation_rules": {
            "formats": [
                {"type": "digits", "length": [8], "description": "8-значный код таможенного органа РФ"},
                {"pattern": "\\d{3} \\d{5}", "description": "код органа через РБ/КЗ"},
            ],
            "multiple_allowed": True,
            "skip_for": ["pipeline", "electric"],
        },
        "source_priority": ["transport_doc", "application_statement"],
        "target_field": "entry_customs_code",
        "target_kind": "core_declaration",
    },
    {
        "graph_number": 30,
        "graph_name": "Местонахождение товаров",
        "section": "header",
        "fill_instruction": (
            "Место нахождения товара на момент подачи ДТ: СВХ, склад декларанта, порт и т.д. "
            "Определяется из транспортных документов."
        ),
        "fill_format": "Наименование места хранения (СВХ, склад, порт и т.д.).",
        "ai_rule": (
            "Источник: транспортные документы AWB / CMR / B/L — поле «Place of Delivery» / «Место доставки». "
            "Если информация не найдена — оставить пустым и подсветить пользователю "
            "с сообщением: «Укажите место нахождения товаров». Severity: warning."
        ),
        "source_priority": ["transport_doc"],
        "source_fields": {
            "transport_doc": {"fields": ["place_of_delivery", "delivery_place", "destination_address"], "notes": "AWB/CMR/B/L — поле Place of Delivery / Место доставки"},
        },
        "confidence_map": {"transport_doc": 0.85},
        "target_field": "goods_location",
        "target_kind": "core_declaration",
    },

    # ── РАЗДЕЛ: ТОВАРНЫЕ ПОЗИЦИИ (items) ──────────────────────────────────────
    {
        "graph_number": 31,
        "graph_name": "Грузовые места и описание товаров",
        "section": "item",
        "fill_instruction": (
            "Сведения указываются с новой строки с порядковым номером. "
            "1. Наименование товара — брать из документа «Техническое описание». "
            "Без обобщений «Item 1», «Товар 1». "
            "2. Грузовые места и упаковка — брать из Packing List: "
            "общее кол-во грузовых мест; если неполные — в скобках (N часть места); "
            "коды видов упаковки по Классификатору через «-» количество упаковок каждого вида. "
            "Пример: «3, 21-2, 4G-1»."
        ),
        "fill_format": (
            "1. [Наименование из техописания]\n"
            "2. [кол-во мест], [код упаковки]-[кол-во] (напр.: 3, 21-2, 4G-1)"
        ),
        "ai_rule": (
            "Пункт 1 — наименование: извлечь из технического описания (technical_docs). "
            "Без обобщений и шаблонных названий. "
            "Пункт 2 — грузовые места: из PL (packing_list): "
            "кол-во мест занятых товаром; если неполные — добавить (N часть места); "
            "коды упаковки по классификатору через «-» количество."
        ),
        "is_required": True,
        "source_priority": ["technical_docs", "packing_list"],
        "source_fields": {
            "technical_docs": {"fields": ["product_name", "description", "item_name"], "notes": "Техническое описание — наименование товара (пункт 1)"},
            "packing_list": {"fields": ["packages_count", "package_type", "package_code"], "notes": "PL — кол-во грузовых мест и коды упаковки (пункт 2)"},
        },
        "confidence_map": {"technical_docs": 0.9, "packing_list": 0.9},
        "target_field": "description",
        "target_kind": "core_item",
    },
    {
        "graph_number": 32,
        "graph_name": "Порядковый номер товара",
        "section": "item",
        "fill_instruction": (
            "Порядковый номер декларируемого товара (от 1 до 999). "
            "На основном листе — не более 1 товара, на добавочном — до 3."
        ),
        "fill_format": "Целое число от 1 до 999.",
        "ai_rule": "Присваивать автоматически по порядку позиций.",
        "compute_expression": "line_no",
        "validation_rules": {"type": "integer", "min": 1, "max": 999},
        "target_field": "line_no",
        "target_kind": "core_item",
    },
    {
        "graph_number": 33,
        "graph_name": "Код товара (ТН ВЭД ЕАЭС)",
        "section": "item",
        "fill_instruction": (
            "10-значный код товара по ТН ВЭД ЕАЭС. "
            "Определяет ставки пошлин, налогов, запреты и ограничения."
        ),
        "fill_format": "Ровно 10 цифр. Первые 2 цифры: 01–97.",
        "ai_rule": (
            "Если есть классификационное решение ФТС — использовать его. "
            "Иначе AI выдаёт top-N кандидатов с обоснованием и confidence, "
            "помечает как «нужна проверка пользователя»."
        ),
        "is_required": True,
        "validation_rules": {"type": "hs10", "pattern": "^\\d{10}$"},
        "source_priority": [
            "fcs_classification_decision", "preliminary_classification",
            "tnved_reference", "technical_docs",
        ],
        "confidence_map": {
            "fcs_classification_decision": 0.99,
            "preliminary_classification": 0.9,
            "technical_docs": 0.6,
        },
        "target_field": "hs_code",
        "target_kind": "core_item",
    },
    {
        "graph_number": 34,
        "graph_name": "Код страны происхождения",
        "section": "item",
        "fill_instruction": (
            "Двузначный буквенный код страны происхождения товара "
            "(например, CN, DE, US) по классификатору."
        ),
        "fill_format": "ISO 3166-1 alpha-2.",
        "ai_rule": (
            "Источники в порядке приоритета: "
            "1) сертификат происхождения; "
            "2) декларация о соответствии — поле «страна изготовителя»; "
            "3) техническое описание — страна производителя."
        ),
        "validation_rules": {"type": "iso3166_1_alpha2"},
        "source_priority": ["origin_certificate", "conformity_declaration", "technical_docs"],
        "source_fields": {
            "origin_certificate": {"fields": ["country_of_origin", "origin_country"], "notes": "Сертификат происхождения — основной источник"},
            "conformity_declaration": {"fields": ["manufacturer_country", "country_of_manufacture"], "notes": "Декларация о соответствии — страна изготовителя"},
            "technical_docs": {"fields": ["manufacturer_country", "made_in", "country_of_origin"], "notes": "Техническое описание — страна производителя"},
        },
        "confidence_map": {"origin_certificate": 0.95, "conformity_declaration": 0.85, "technical_docs": 0.75},
        "target_field": "country_origin_code",
        "target_kind": "core_item",
    },
    {
        "graph_number": 35,
        "graph_name": "Вес брутто (кг)",
        "section": "item",
        "fill_instruction": (
            "Масса брутто ДАННОГО товара (с упаковкой) в килограммах — только по этой позиции, "
            "не суммарный вес всей партии. Округляется до 3 знаков после запятой."
        ),
        "fill_format": "Десятичное число, 3 знака после запятой.",
        "ai_rule": (
            "ВАЖНО: брать вес ТОЛЬКО данного конкретного товара, не суммарный вес всей партии. "
            "Найти в PL все строки данного наименования товара (match по названию/артикулу). "
            "Суммировать gross_weight только по этим строкам. "
            "НЕ использовать итоговую строку PL (total gross weight — это вес всей партии). "
            "Приоритет источников: PL > сертификат взвешивания > транспортные документы. "
            "При расхождении между источниками — приоритет PL."
        ),
        "is_required": True,
        "validation_rules": {"type": "decimal", "min": 0, "round": 3},
        "source_priority": ["packing_list", "weighing_certificate", "transport_doc"],
        "source_fields": {
            "packing_list": {"fields": ["gross_weight", "weight_gross", "brutto"], "notes": "PL — вес брутто по позиции (наивысший приоритет)"},
            "weighing_certificate": {"fields": ["gross_weight", "weight"], "notes": "Сертификат взвешивания"},
            "transport_doc": {"fields": ["gross_weight", "total_weight"], "notes": "AWB/CMR/B/L — если нет PL"},
        },
        "confidence_map": {"packing_list": 0.95, "weighing_certificate": 0.85, "transport_doc": 0.8},
        "target_field": "gross_weight",
        "target_kind": "core_item",
    },
    {
        "graph_number": 36,
        "graph_name": "Преференции",
        "section": "item",
        "fill_instruction": (
            "4 элемента по Инструкции к Решению КТС № 257: "
            "1 — тарифная преференция по пошлине (ЗСТ, СНГ, наименее развитые страны); "
            "2 — льготы по таможенной пошлине; "
            "3 — льготы по акцизу; "
            "4 — льготы по НДС при ввозе. "
            "«00» — ставка есть, льгота не заявляется. «--» — платёж не возникает. "
            "Данные вносятся в соответствии с кодом ТН ВЭД товара (гр. 33). "
            "Коды из Классификатора льгот/преференций (национальный + ЕАЭС)."
        ),
        "fill_format": "4 элемента: [эл.1][эл.2][эл.3][эл.4]. Каждый: код или «00» или «--».",
        "ai_rule": (
            "Источники: 1) сертификат происхождения (СТ-1, Form A, EUR.1); "
            "2) международные соглашения о преференциях (ЗСТ, СНГ); "
            "3) решения о предоставлении тарифных преференций. "
            "Определить применимые льготы по каждому из 4 элементов. "
            "Если льгота не заявляется — «00»; если платёж не возникает — «--». "
            "Подсветить пользователю для проверки (severity: info)."
        ),
        "validation_rules": {"type": "string", "elements": 4, "element_values": ["code", "00", "--"]},
        "source_priority": ["origin_certificate", "preference_agreement", "preference_decision"],
        "source_fields": {
            "origin_certificate": {"fields": ["form_type", "origin_country"], "notes": "СТ-1 / Form A / EUR.1 — основание для элемента 1"},
            "preference_agreement": {"fields": ["agreement_name", "preference_type"], "notes": "Международное соглашение о преференциях"},
            "preference_decision": {"fields": ["decision_number", "preference_type"], "notes": "Решение о предоставлении преференции"},
        },
        "confidence_map": {"origin_certificate": 0.8, "preference_agreement": 0.75},
        "target_field": "preference_code",
        "target_kind": "core_item",
    },
    {
        "graph_number": 37,
        "graph_name": "Процедура",
        "section": "item",
        "fill_instruction": (
            "Два подраздела. "
            "Подраздел 1: составной код ААББ — "
            "АА: код заявляемой процедуры; "
            "ББ: код предшествующей процедуры или «00» если не было. "
            "Пример: «4000» (ИМ40, без предшествующей). "
            "Подраздел 2: 3-значный код особенности перемещения или «000»."
        ),
        "fill_format": "Подраздел 1: ААББ (4 символа, напр. «4000»). Подраздел 2: 3 символа (напр. «000»).",
        "ai_rule": (
            "Подраздел 1: взять код процедуры из гр. 1 (АА), "
            "добавить код предшествующей процедуры (ББ) или «00» если её не было. "
            "Подраздел 2: код особенности перемещения или «000». "
            "При несоответствии с гр. 1 — подсветить пользователю (severity: warning)."
        ),
        "conflict_check": "АА из гр. 37 должно совпадать с кодом процедуры из гр. 1; при расхождении — warning",
        "validation_rules": {"type": "string", "subsection_1_len": 4, "subsection_2_len": 3},
        "source_priority": ["contract", "application_statement"],
        "source_fields": {
            "contract": {"fields": ["contract_type", "deal_type"], "notes": "Контракт/договор купли-продажи — тип сделки определяет процедуру"},
            "application_statement": {"fields": ["procedure_code", "customs_procedure"], "notes": "Заявление на оформление — код заявляемой процедуры"},
        },
        "confidence_map": {"contract": 0.85, "application_statement": 0.85, "derived_from_graph_1": 0.9},
        "target_field": "procedure_code",
        "target_kind": "core_item",
    },
    {
        "graph_number": 38,
        "graph_name": "Вес нетто (кг)",
        "section": "item",
        "fill_instruction": (
            "Масса нетто товара (без упаковки) в килограммах. Источник: Packing List. "
            "Суммировать net weight по всем строкам PL, относящимся к данному наименованию товара — "
            "не брать значение одной строки."
        ),
        "fill_format": "Десятичное число.",
        "ai_rule": (
            "ВАЖНО: брать вес ТОЛЬКО данного конкретного товара, не суммарный нетто всей партии. "
            "Найти в PL все строки данного наименования товара (match по названию/артикулу). "
            "Суммировать net_weight только по этим строкам. "
            "НЕ использовать итоговую строку PL (total net weight — это нетто всей партии). "
            "Нетто должно быть меньше брутто (гр. 35); если нет — поднять warning."
        ),
        "is_required": True,
        "conflict_check": "net_weight < gross_weight (гр. 35); при нарушении — warning",
        "validation_rules": {"type": "decimal", "min": 0},
        "source_priority": ["packing_list"],
        "source_fields": {
            "packing_list": {"fields": ["net_weight", "weight_net", "netto"], "notes": "Суммировать по всем строкам данного товара, не одна строка"},
        },
        "confidence_map": {"packing_list": 0.95},
        "target_field": "net_weight",
        "target_kind": "core_item",
    },
    {
        "graph_number": 39,
        "graph_name": "Квота",
        "section": "item",
        "fill_instruction": (
            "Сведения о тарифной квоте, если декларируемый товар ввозится в рамках квоты."
        ),
        "fill_format": "Номер квоты, срок, объём.",
        "ai_rule": "Заполнять только при наличии квотного свидетельства/лицензии.",
        "source_priority": ["license_or_quota"],
        "target_field": "quota_info",
        "target_kind": "core_item",
    },
    {
        "graph_number": 40,
        "graph_name": "Общая декларация/предшествующий документ",
        "section": "item",
        "fill_instruction": (
            "Регистрационные номера предшествующих таможенных документов: "
            "транзитных деклараций, ДТ по предшествующим процедурам и т.д."
        ),
        "fill_format": "Номер предыдущей ДТ + дата регистрации.",
        "source_priority": ["previous_declaration", "temporary_storage_doc"],
        "target_field": "prev_doc_ref",
        "target_kind": "core_item",
    },
    {
        "graph_number": 41,
        "graph_name": "Единица дополнительных единиц",
        "section": "item",
        "fill_instruction": (
            "Количество товара в дополнительной единице измерения, если она установлена "
            "для данного кода ТН ВЭД (штуки, литры, пары и т.д.). "
            "Заполняется только если дополнительная единица предусмотрена."
        ),
        "fill_format": "Число + единица измерения (шт, л, пара и т.д.).",
        "ai_rule": (
            "Проверить по коду ТН ВЭД (гр. 33), предусмотрена ли дополнительная единица измерения. "
            "Если предусмотрена — взять количество из Packing List по конкретной позиции товара. "
            "Если не предусмотрена — не заполнять. "
            "Спецификацию для этого поля НЕ использовать."
        ),
        "source_priority": ["packing_list"],
        "source_fields": {
            "packing_list": {
                "fields": ["quantity", "qty", "units"],
                "notes": "PL — количество в доп. единице измерения по конкретной позиции.",
            },
        },
        "confidence_map": {"packing_list": 0.9},
        "target_field": "additional_unit",
        "target_kind": "core_item",
    },
    {
        "graph_number": 42,
        "graph_name": "Цена товара",
        "section": "item",
        "fill_instruction": (
            "Фактурная стоимость конкретного товара в валюте контракта (гр. 22). "
            "Стоимость берётся из инвойса на товары; валюта определяется из договора/контракта купли-продажи. "
            "Является базой для расчёта таможенной стоимости и НДС."
        ),
        "fill_format": "Число в валюте контракта (гр. 22).",
        "ai_rule": (
            "ВАЖНО: брать стоимость ТОЛЬКО данной позиции, не итоговую сумму инвойса. "
            "1. Найти строку данного товара в инвойсе на товары (match по наименованию/артикулу). "
            "Взять line_total или unit_price × quantity ТОЛЬКО этой строки. "
            "НЕ использовать транспортный инвойс. НЕ использовать grand total / итого инвойса. "
            "2. Определить валюту контракта из гр. 22 (только договор/контракт купли-продажи). "
            "3. Если валюта инвойса совпадает с валютой контракта — использовать сумму напрямую. "
            "4. Если валюты различаются — пересчитать по курсу ЦБ на дату инвойса, "
            "результат отметить предупреждением о конвертации для проверки пользователем. "
            "5. Контроль: sum(гр. 42 по всем позициям) должна совпадать с подразделом 2 гр. 22."
        ),
        "is_required": True,
        "validation_rules": {"type": "money", "min": 0},
        "source_priority": ["invoice", "contract"],
        "source_fields": {
            "invoice": {
                "fields": ["line_total", "unit_price", "amount", "total_price"],
                "notes": "Инвойс на товары — стоимость конкретной позиции (НЕ транспортный инвойс).",
            },
            "contract": {
                "fields": ["currency", "contract_currency"],
                "notes": "Договор/контракт — валюта сделки для гр. 22; используется при конвертации.",
            },
        },
        "confidence_map": {"invoice": 0.95, "contract": 0.97},
        "conflict_check": "sum(гр. 42 по всем позициям) = подраздел 2 гр. 22",
        "target_field": "unit_price",
        "target_kind": "core_item",
    },
    {
        "graph_number": 43,
        "graph_name": "Код МОС",
        "section": "item",
        "fill_instruction": (
            "Код метода определения таможенной стоимости (МОС): "
            "1 — по стоимости сделки с ввозимыми товарами, "
            "2 — по стоимости сделки с идентичными товарами, "
            "3 — с однородными товарами, "
            "4 — метод вычитания, "
            "5 — метод сложения, "
            "6 — резервный метод. "
            "Второй подраздел — код признака корректировки таможенной стоимости (КТС)."
        ),
        "fill_format": "1–6. Второй подраздел: код КТС.",
        "ai_rule": "Если нет данных — дефолт 1 (метод по стоимости сделки) с флагом «проверьте».",
        "default_value": "1",
        "default_flag": "проверьте метод определения стоимости",
        "validation_rules": {"type": "enum", "values": ["1", "2", "3", "4", "5", "6"]},
        "source_priority": ["customs_valuation_rules", "dts1_customs_value_calc"],
        "target_field": "mos_method_code",
        "target_kind": "core_item",
    },
    {
        "graph_number": 44,
        "graph_name": "Дополнительная информация/Представленные документы",
        "section": "item",
        "fill_instruction": (
            "Перечень всех документов, на основании которых заполнена ДТ и подтверждаются "
            "заявленные сведения. Каждый документ указывается с кодом вида документа "
            "по классификатору ФТС, номером и датой. "
            "Формат строки: КОД_ФТС; №НОМЕР; ДД.ММ.ГГГГ"
        ),
        "fill_format": "КОД_ФТС; №НОМЕР; ДД.ММ.ГГГГ — по одной строке на документ.",
        "ai_rule": (
            "Автоматически сформировать перечень из всех загруженных пользователем файлов. "
            "Для каждого файла: 1) определить тип документа; "
            "2) извлечь номер и дату; "
            "3) подобрать код по классификатору видов документов ФТС; "
            "4) сформировать строку: КОД_ФТС; №НОМЕР; ДД.ММ.ГГГГ. "
            "Итог — список строк, по одной на каждый документ."
        ),
        "is_required": True,
        "source_priority": ["all_uploaded_documents"],
        "source_fields": {
            "all_uploaded_documents": {
                "fields": ["doc_type", "doc_number", "doc_date"],
                "notes": (
                    "Все загруженные файлы: инвойс, транспортные документы, контракт, "
                    "упаковочный лист, сертификаты происхождения, доверенности, лицензии, "
                    "разрешения и прочие документы пакета."
                ),
            }
        },
        "confidence_map": {"all_uploaded_documents": 0.90},
        "target_field": "documents_codes",
        "target_kind": "extension",
    },
    {
        "graph_number": 45,
        "graph_name": "Таможенная стоимость",
        "section": "item",
        "fill_instruction": (
            "Таможенная стоимость ДАННОЙ товарной позиции в рублях (не суммарная по всей декларации). "
            "Округляется до двух знаков после запятой. "
            "Не заполняется при декларировании товаров различных наименований с одним кодом ТН ВЭД, "
            "а также при декларировании национальной валюты. "
            "Метод 1 (по стоимости сделки): "
            "1. Базовая цена = стоимость данного товара из инвойса на товары (гр. 42). "
            "2. Прибавить стоимость перевозки до границы ЕАЭС: если транспортный инвойс содержит "
            "общую сумму за партию — распределить пропорционально массе брутто данного товара: "
            "freight_item = total_freight × (gross_weight_item / total_gross_weight_all_items). "
            "3. Прибавить (только если загружены соответствующие документы): "
            "страхование груза, комиссионные посредникам (кроме комиссионера по покупке), "
            "стоимость упаковки и упаковочных работ, роялти/лицензионные платежи "
            "(если связаны с данным товаром и являются условием продажи). "
            "4. Итог перевести в рубли по курсу ЦБ (гр. 23). Округлить до 2 знаков."
        ),
        "fill_format": "Рубли, 2 знака после запятой.",
        "ai_rule": (
            "ВАЖНО: рассчитывать таможенную стоимость ТОЛЬКО для данной позиции, не для всей партии. "
            "Если есть ДТС-1 — использовать значение по данной позиции. "
            "Иначе применять метод 1: "
            "1. Базовая цена = line_total ДАННОГО товара из инвойса на товары (гр. 42, не grand total инвойса). "
            "2. Прибавить стоимость перевозки до границы ЕАЭС из транспортного инвойса: "
            "   — если транспортный инвойс содержит общую стоимость за всю партию: "
            "     weight_share = gross_weight_данного_товара / суммарный_gross_weight_всех_товаров; "
            "     freight_item = total_freight × weight_share; "
            "   — если стоимость перевозки указана по данному товару отдельно — брать напрямую. "
            "3. Если загружены страховые документы — прибавить страховку "
            "   (пропорционально массе брутто данного товара, если нет разбивки по позициям). "
            "4. Если загружены документы по комиссионным/посредникам — прибавить "
            "   (кроме комиссионера по покупке). "
            "5. Если загружены документы по упаковке — прибавить стоимость упаковки. "
            "6. Если загружены документы по роялти/лицензиям — прибавить "
            "   (только если связаны с данным товаром). "
            "7. Итог умножить на курс ЦБ (гр. 23). Округлить до 2 знаков. "
            "8. Пометить результат «предварительно — нет ДТС-1». "
            "Указать какие компоненты учтены, а какие документы отсутствуют."
        ),
        "is_required": True,
        "compute_expression": (
            "dts1.item_customs_value OR "
            "(invoice.line_total + transport_invoice.freight_total * (item_gross_weight / total_gross_weight) "
            "+ insurance.amount * (item_gross_weight / total_gross_weight) "
            "+ commissions.amount + royalty.amount + packaging.amount) * exchange_rate"
        ),
        "validation_rules": {"type": "money_rub", "round": 2},
        "source_priority": [
            "dts1_customs_value_calc",
            "invoice",
            "transport_invoice",
            "insurance_doc",
            "royalty_doc",
            "packaging_doc",
        ],
        "source_fields": {
            "dts1_customs_value_calc": {
                "fields": ["item_customs_value"],
                "notes": "ДТС-1 — итоговая таможенная стоимость по позиции (приоритетный источник).",
            },
            "invoice": {
                "fields": ["line_total", "unit_price", "amount"],
                "notes": "Инвойс на товары — базовая цена товара (гр. 42).",
            },
            "transport_invoice": {
                "fields": ["freight_amount", "freight_to_border"],
                "notes": "Транспортный инвойс — стоимость международной перевозки до границы ЕАЭС.",
            },
            "insurance_doc": {
                "fields": ["insurance_amount", "premium"],
                "notes": "Страховые документы — стоимость страхования груза.",
            },
            "royalty_doc": {
                "fields": ["royalty_amount", "license_fee"],
                "notes": "Документы по роялти/лицензиям — если связаны с товаром и являются условием продажи.",
            },
            "packaging_doc": {
                "fields": ["packaging_cost", "packing_amount"],
                "notes": "Документы по упаковке — стоимость упаковки и упаковочных работ.",
            },
        },
        "confidence_map": {
            "dts1_customs_value_calc": 0.97,
            "invoice": 0.85,
            "transport_invoice": 0.80,
            "insurance_doc": 0.80,
            "royalty_doc": 0.75,
            "packaging_doc": 0.75,
            "computed_method_1": 0.65,
        },
        "conflict_check": (
            "Проверить: сумма гр. 45 по всем позициям × курс не должна сильно расходиться "
            "с гр. 12 (общей таможенной стоимостью)."
        ),
        "target_field": "customs_value_rub",
        "target_kind": "core_item",
    },
    {
        "graph_number": 46,
        "graph_name": "Статистическая стоимость",
        "section": "item",
        "fill_instruction": (
            "Статистическая стоимость по товарной подсубпозиции в долларах США. "
            "Вносится без пробелов, разделителей и знака валюты, 2 знака после запятой (пример: 12345.67). "
            "Алгоритм расчёта: "
            "1) Основа — таможенная стоимость из гр. 45; "
            "если гр. 45 не заполнена — использовать цену из гр. 42; "
            "если не заполнены ни 42, ни 45 — фактически уплаченная цена по документам. "
            "2) При экспорте привести к базису FOB последний порт убытия или DAP/граница ЕАЭС "
            "(добавить/исключить транспортные расходы до/после границы). "
            "3) Пересчитать в USD по официальному курсу ЦБ на дату регистрации ДТ. "
            "4) Округлить по математическим правилам до 2 знаков."
        ),
        "fill_format": "Доллары США, 2 знака, без пробелов и знака валюты (пример: 12345.67).",
        "ai_rule": (
            "ВАЖНО: рассчитывать статистическую стоимость ТОЛЬКО для данной позиции, не для всей партии. "
            "1. Взять customs_value_rub ДАННОГО товара из гр. 45. "
            "Если гр. 45 пуста — взять price ДАННОГО товара из гр. 42 и перевести в рубли по курсу ЦБ. "
            "2. При экспорте скорректировать на транспортные расходы (доля данного товара) до базиса FOB/DAP. "
            "3. Разделить на курс ЦБ USD на дату регистрации ДТ. "
            "4. Округлить до 2 знаков. Формат вывода: 12345.67 (без знака $ и разделителей)."
        ),
        "is_required": True,
        "compute_expression": (
            "graph_45.customs_value_rub / cbr_usd_rate "
            "OR graph_42.price_rub_equivalent / cbr_usd_rate"
        ),
        "validation_rules": {"type": "money_usd", "round": 2, "format": "no_currency_sign"},
        "source_priority": ["graph_45", "graph_42", "cbr_official_rate"],
        "source_fields": {
            "graph_45": {
                "fields": ["customs_value_rub"],
                "notes": "Таможенная стоимость (гр. 45) — основной источник.",
            },
            "graph_42": {
                "fields": ["line_total", "unit_price"],
                "notes": "Цена товара (гр. 42) — резервный источник, если гр. 45 не заполнена.",
            },
            "cbr_official_rate": {
                "fields": ["usd_rate"],
                "notes": "Официальный курс ЦБ USD на дату регистрации ДТ.",
            },
        },
        "confidence_map": {
            "graph_45_based": 0.95,
            "graph_42_based": 0.75,
        },
        "conflict_check": (
            "Сумма гр. 46 по всем позициям × курс USD не должна сильно расходиться "
            "с общей таможенной стоимостью декларации (гр. 12)."
        ),
        "target_field": "statistical_value_usd",
        "target_kind": "core_item",
    },

    # ── РАЗДЕЛ: ПЛАТЕЖИ ───────────────────────────────────────────────────────
    {
        "graph_number": 47,
        "graph_name": "Исчисление платежей",
        "section": "payment",
        "fill_instruction": (
            "Сведения об исчислении таможенных и иных платежей. Колонки: "
            "Вид (код: 2010 — ввозная пошлина, 5010 — НДС, 1010 — сборы), "
            "Основа начисления, Ставка, Сумма, "
            "СП (код специфики: ИУ — уплачен, УР — условно исчислен, "
            "УМ — освобождён, ОП — отсрочка). "
            "В Альта-ГТД заполняется автоматически."
        ),
        "fill_format": "Таблица: вид платежа | основа | ставка | сумма | СП.",
        "ai_rule": "Считать через формулы/сервис расчёта по ставкам ТН ВЭД. Не угадывать.",
        "source_priority": ["hs_code", "customs_value_rub", "preference_code", "vat_rules"],
        "target_field": None,
        "target_kind": "derived",
    },
    {
        "graph_number": 48,
        "graph_name": "Отсрочка платежей",
        "section": "payment",
        "fill_instruction": (
            "Код вида таможенного платежа, по уплате которого предоставлена отсрочка/рассрочка, "
            "номер и дата НПА, дата последнего дня уплаты. "
            "Элементы разделяются знаком «–» без пробелов. "
            "Не заполняется, если отсрочка не предоставлялась."
        ),
        "fill_format": "КОД–номерНПА–датаНПА–датаУплаты. Без пробелов.",
        "ai_rule": "Заполнять только при наличии решения о предоставлении отсрочки.",
        "source_priority": ["deferral_request", "customs_decision", "bank_guarantee", "pledge"],
        "target_field": "payment_deferral",
        "target_kind": "extension",
    },
    # ── РАЗДЕЛ: ЗАВЕРШЕНИЕ ────────────────────────────────────────────────────
    {
        "graph_number": 54,
        "graph_name": "Место и дата",
        "section": "other",
        "fill_instruction": (
            "Сведения о лице, составившем ДТ: "
            "№1 — данные таможенного представителя (номер свидетельства, дата и номер договора "
            "с декларантом, ИНН/КПП). Не заполняется при самостоятельном декларировании. "
            "№2 — ФИО."
        ),
        "fill_format": "[Город], [ДД.ММ.ГГГГ]. ФИО подписанта.",
        "ai_rule": (
            "Взять город из адреса декларанта (профиль компании). "
            "Дата — дата подачи ДТ. ФИО — из доверенности."
        ),
        "compute_expression": "city_from_declarant + ', ' + today_dd_mm_yyyy",
        "source_priority": ["company_profile", "power_of_attorney"],
        "target_field": "place_and_date",
        "target_kind": "core_declaration",
    },
]


async def run_seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    # Импортируем модель (нужен контекст приложения)
    from app.models.graph_rule import DeclarationGraphRule

    async with Session() as session:
        created = updated = 0

        for rule_data in GRAPH_RULES:
            # Заполнить пустые JSONB-поля
            rule_data.setdefault("validation_rules", {})
            rule_data.setdefault("source_priority", [])
            rule_data.setdefault("source_fields", {})
            rule_data.setdefault("confidence_map", {})
            rule_data.setdefault("fill_instruction", "")
            rule_data.setdefault("fill_format", "")
            rule_data.setdefault("ai_rule", "")
            rule_data.setdefault("is_required", False)
            rule_data.setdefault("skip", False)
            rule_data.setdefault("requires_document", False)
            rule_data.setdefault("declaration_type", "IM40")
            rule_data.setdefault("version", "5.0")
            rule_data.setdefault("is_active", True)

            result = await session.execute(
                select(DeclarationGraphRule).where(
                    DeclarationGraphRule.graph_number == rule_data["graph_number"],
                    DeclarationGraphRule.declaration_type == rule_data["declaration_type"],
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                for field, value in rule_data.items():
                    setattr(existing, field, value)
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                session.add(DeclarationGraphRule(**rule_data))
                created += 1

        await session.commit()
        print(f"✓ Загружено правил граф: создано={created}, обновлено={updated}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_seed())
