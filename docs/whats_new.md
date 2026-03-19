# What's New

---

## Fix: Инкотермс (гр.20) — delivery_place + IATA-маппинг

**Дата:** 2026-03-19
**Ветка:** `fix/incoterms-delivery-place`

### Проблемы

1. **LLM ставил пункт прибытия вместо отправления** — для EXW/FOB система записывала «Moscow» (город покупателя) как delivery_place, хотя для этих условий Инкотермс пункт поставки — город ПРОДАВЦА (отправления).

2. **Слишком длинное описание delivery_place в JSON-шаблоне LLM** — содержало стрелки (`→`), примеры и восклицательные знаки прямо в значении JSON-поля. LLM путался и возвращал пустые `incoterms` и `delivery_place`.

3. **IATA-коды вместо названий городов** — при фоллбэке на транспортный документ, `departure_airport` содержит 3-буквенный IATA-код (HKG), а не читаемое название города (HONG KONG).

### Исправления

- **Промпт LLM-компиляции**: описание `delivery_place` в JSON-шаблоне сокращено до `"город поставки из спецификации или контракта (гр.20)"`. Подробные правила (город продавца vs покупателя, примеры) перенесены в системный промпт отдельным блоком «ГРАФА 20 (УСЛОВИЯ ПОСТАВКИ)».

- **Защита от городов назначения**: добавлен словарь `_DESTINATION_CITIES_RU` (Москва, СПб, Новосибирск, Владивосток, Екатеринбург, Казань, Краснодар + их IATA-коды). Для условий группы E/F (EXW, FCA, FAS, FOB) — если delivery_place содержит российский город, он автоматически заменяется на пункт отправления из транспортного документа, либо удаляется с предупреждением.

- **IATA → город маппинг**: добавлен словарь `_IATA_TO_CITY` (40+ аэропортов: HKG→HONG KONG, SZX→SHENZHEN, CAN→GUANGZHOU, PVG→SHANGHAI и т.д.). Конвертация применяется автоматически при использовании transport_departure как fallback для delivery_place.

- Логика исправлена в обоих блоках Инкотермс: `_compile_declaration()` (legacy) и `_post_process_compilation()` (production).

### Изменённые файлы

| Файл | Изменения |
|---|---|
| `services/ai-service/app/services/agent_crew.py` | +108/−5: промпты компиляции, IATA-маппинг, защита от городов назначения |

---

# What's New — Vision OCR + Quality Gate + Enhanced Parsing v4

**Дата:** 2026-03-16
**Ветка:** `feature/vision-ocr-quality-gate`
**Предыдущая версия:** LLM Parsing Pipeline v3

---

## Обзор

Интеграция Vision OCR (DeepSeek-OCR-2), качественный скачок в полноте и точности распознавания документов. Решена проблема потери данных из шапок PDF. Добавлены новые типы документов, few-shot примеры, валидация экстракции, нормализация данных. Полностью переработана документация по архитектуре AI-пайплайна.

---

## Ключевые изменения

### 1. Vision OCR (DeepSeek-OCR-2)

Новый OCR-движок для сканированных документов и изображений.

- **Новый файл `ocr_client.py`** (253 строки): клиент DeepSeek-OCR-2 через Cloud.ru Foundation Models. Рендеринг страниц в PNG (300 DPI), отправка в Vision LLM, очистка grounding-координат, конвертация HTML-таблиц.
- **Конфигурация**: переменные `OCR_ENABLED`, `OCR_BASE_URL`, `OCR_API_KEY`, `OCR_MODEL`, `OCR_PROJECT_ID`, `OCR_TIMEOUT` в `.env.example`, `docker-compose.yml`, `docker-compose.prod.yml`, `config.py`.
- **Маршрутизация OCR**: текстовый PDF → pdfplumber; сканированный PDF → Vision OCR; изображения → Vision OCR; DOCX → python-docx.

### 2. Починка pdfplumber (потеря данных из шапок)

**Проблема**: `_extract_pdf_enhanced()` использовала `outside_bbox()` для удаления зон таблиц. Это обрезало шапку инвойса — seller, buyer, contract_number терялись.

**Решение**: убран `outside_bbox()`. Теперь всегда `extract_text(layout=True)` для полного текста страницы + `find_tables()` для таблиц как дополнительного Markdown. Ничего не вырезается.

### 3. Vision OCR quality gate

Автоматическая подстраховка: если после LLM-экстракции критичные поля пустые — повторная экстракция через Vision OCR с merge результатов.

- **Критичные поля по типам**: invoice → seller/buyer/invoice_number, contract → contract_number, specification → items, packing_list → items, transport_doc → transport_number.
- **Реализация**: `_check_needs_vision_retry()` + retry-логика в `process_documents()` (agent_crew.py) и `parse_debug()` (smart_parser.py).
- **Debug-панель**: результат retry отображается в `doc_trace.stages.classify_and_extract.vision_retry`.

### 4. Поддержка DOCX

- Новая функция `_extract_text_from_docx()` в `ocr_service.py` — извлечение текста из `.docx` через `python-docx` с дедупликацией ячеек таблиц.
- Добавлена зависимость `python-docx>=1.1.0` в `requirements.txt`.

### 5. Новый тип документа: декларация соответствия ЕАЭС

- Тип `conformity_declaration` — декларации соответствия ТР ТС/ТР ЕАЭС.
- Схема экстракции: declaration_number, registration_date, valid_until, applicant_name, product_name, manufacturer_name, hs_code, technical_regulation, test_protocol_number и др.
- Классификационные подсказки для LLM, filename-эвристика.
- Интеграция в agent_crew.py: Графа 44 (код `01191`), список `conformity_declarations`.
- 2 few-shot примера в `fewshot_examples.py`.

### 6. Улучшенная классификация документов

Промпт классификации дополнен:
- **Правила дизамбигуации**: tech_description vs invoice (наличие цен/сумм), invoice vs transport_invoice (товары vs перевозка), specification vs invoice (приложение к контракту vs самостоятельный документ).
- **Детальные признаки** для каждого из 16 типов: ключевые маркеры, негативные маркеры.

### 7. Улучшенная экстракция полей

- **contract_number в invoice**: LLM ищет «Contract No.», «Per Contract», «Контракт №», «Ref:» — в шапке и подвале.
- **delivery_place в specification/contract**: разделение Incoterms-кода и места поставки (EXW Hongkong → incoterms=EXW, delivery_place=Hongkong). Явное указание: delivery_place — НЕ аэропорт назначения.

### 8. Детерминированная логика Инкотермс (гр. 20)

Перенесена из мёртвого кода `_compile_declaration()` в `_post_process_compilation()`:
- Приоритет: заявка > контракт > спецификация. Инвойс НЕ источник.
- Если место поставки — только страна → уточнение из departure_airport/departure_point транспортного документа.

### 9. Валидация и нормализация экстракции

- **`extraction_validator.py`** (239 строк): проверка обязательных полей, форматов дат/сумм, ISO-кодов. Критические проблемы → retry с коррекцией.
- **`extraction_normalizer.py`** (340 строк): приведение дат, чисел, кодов стран/валют к стандартным форматам.
- **`classify_and_extract_with_correction()`**: если после экстракции есть критичные проблемы → LLM получает свой ответ + ошибки, исправляет за одну итерацию.

### 10. Few-shot примеры

**`fewshot_examples.py`** (989 строк): эталонные пары «текст → JSON» для динамической подстановки в промпт:
- 2 примера `specification` (RUB/EXW Beijing, USD/EXW Hongkong).
- 2 примера `conformity_declaration`.

### 11. Кеширование классификаторов

**`classifier_cache.py`** (203 строки): кеш справочников (страны, валюты, IATA-коды) для пост-обработки без повторных запросов к БД.

---

## Изменённые файлы

| Файл | Изменения |
|---|---|
| `services/ai-service/app/services/ocr_service.py` | +523/−68: Vision OCR routing, DOCX support, fix pdfplumber (remove outside_bbox), extract_text_debug |
| `services/ai-service/app/services/llm_parser.py` | +772/−48: 16 типов, schema conformity_declaration, disambiguation rules, hints contract_number/delivery_place, correction retry |
| `services/ai-service/app/services/agent_crew.py` | +466/−62: vision quality gate, conformity_declaration, deterministic incoterms, _VISION_RETRY_FIELDS |
| `services/ai-service/app/routers/smart_parser.py` | +69/−4: vision quality gate в parse_debug, conformity_declaration routing |
| `services/ai-service/app/config.py` | +13: OCR settings (OCR_ENABLED, OCR_BASE_URL, OCR_API_KEY, OCR_MODEL, OCR_PROJECT_ID, OCR_TIMEOUT) |
| `services/ai-service/requirements.txt` | +3: python-docx>=1.1.0 |
| `services/core-api/app/routers/classifiers.py` | +40: новые эндпоинты справочников |
| `.env.example` | +7: OCR env vars |
| `docker-compose.yml` | +7: OCR env vars для ai-service |
| `docker-compose.prod.yml` | +6: OCR env vars для ai-service (prod) |
| `docs/declaration_ai_filling_rules.md` | +171: новый раздел 1А (архитектура AI-пайплайна, OCR методы, quality gate, LLM pipeline, пост-обработка) |

## Новые файлы

| Файл | Строк | Назначение |
|---|---|---|
| `services/ai-service/app/services/ocr_client.py` | 253 | Vision OCR клиент (DeepSeek-OCR-2 через Cloud.ru) |
| `services/ai-service/app/services/fewshot_examples.py` | 989 | Few-shot примеры для LLM-экстракции |
| `services/ai-service/app/services/extraction_normalizer.py` | 340 | Нормализация извлечённых данных |
| `services/ai-service/app/services/extraction_validator.py` | 239 | Валидация результатов экстракции |
| `services/ai-service/app/services/classifier_cache.py` | 203 | Кеш справочников для пост-обработки |

---

## Итого

- **16 файлов** затронуто (11 изменённых + 5 новых)
- **+3859 строк** кода
- **3 метода OCR** с умной маршрутизацией + quality gate
- **16 типов документов** (было 13)
- Полная документация архитектуры в `declaration_ai_filling_rules.md`
