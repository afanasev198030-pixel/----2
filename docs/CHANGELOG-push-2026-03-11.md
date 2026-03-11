# Изменения для push 2026-03-11

Описание всех изменений относительно текущей remote-версии (`origin/main`).

**Коммиты:** 4 | **Файлов затронуто:** 62 | **Строк:** +34 710 / −616

---

## Коммит 1: `27971c9` — fix: prevent AI from overwriting user-selected declaration type_code

Исправление бага: LLM-шаг compile мог вернуть `type_code` в неправильном формате (например, кириллицей «ИМ 40» вместо латиницы «IM40»), из-за чего декларации отображались как «Экспорт» вместо «Импорт».

**Два исправления:**
1. `type_code` добавлен в `_PRIORITY_FIELDS`, чтобы LLM не мог переопределить захардкоженное значение.
2. В `apply_parsed` пропускается перезапись `type_code`, если он уже установлен пользователем.

| Файл | Что изменено |
|---|---|
| `services/ai-service/app/services/agent_crew.py` | `type_code` добавлен в `_PRIORITY_FIELDS` |
| `services/core-api/app/routers/apply_parsed.py` | Условие: не перезаписывать `type_code` если уже задан |

---

## Коммит 2: `aa670ec` — feat(ai): полное описание товара в графе 31 из тех. описания

Промпт `_match_items_to_techop` доработан: теперь LLM обязан включать в `description_ru` все сведения из технического описания — материалы, тех. характеристики, назначение, модель, производителя. Добавлено поле `commercial_name_ru` (краткое наименование). Грузовые места из Packing List дописываются в description как пункт 2 графы 31. Исправлен баг распаковки `_invoice_score` (4 элемента вместо 3).

| Файл | Что изменено |
|---|---|
| `services/ai-service/app/services/agent_crew.py` | Обновлён промпт `_match_items_to_techop`: обогащение описания из тех. описания, новое поле `commercial_name_ru`, исправление распаковки `_invoice_score` |

---

## Коммит 3: `f3d617d` — feat: item documents, PDF viewer, XML/XSD validation, calc & parsing improvements

Большой коммит с несколькими функциональными блоками.

### 3.1. Документы к товарным позициям (документы и предшествующие документы)

Полная реализация документов, привязанных к конкретным товарным позициям декларации (графы 44, 40).

**Новые файлы:**

| Файл | Описание |
|---|---|
| `services/core-api/app/models/declaration_item_document.py` | SQLAlchemy модель `DeclarationItemDocument` — документы к товару (гр. 44) |
| `services/core-api/app/models/declaration_item_preceding_doc.py` | SQLAlchemy модель `DeclarationItemPrecedingDoc` — предшествующие документы (гр. 40) |
| `services/core-api/app/schemas/item_document.py` | Pydantic-схемы Create/Update/Response для документов |
| `services/core-api/app/schemas/item_preceding_doc.py` | Pydantic-схемы для предшествующих документов |
| `services/core-api/app/routers/item_documents.py` | CRUD-роутер: `/api/v1/declarations/{id}/items/{item_id}/documents` |
| `services/core-api/app/routers/item_preceding_docs.py` | CRUD-роутер: `/api/v1/declarations/{id}/items/{item_id}/preceding-docs` |
| `frontend/src/api/itemDocuments.ts` | API-клиент для документов к товарам |
| `frontend/src/api/itemPrecedingDocs.ts` | API-клиент для предшествующих документов |
| `frontend/src/components/ItemEditCard.tsx` | Карточка редактирования товарной позиции с блоками документов |

### 3.2. Просмотр PDF прямо в системе

| Файл | Описание |
|---|---|
| `frontend/src/components/PdfViewer.tsx` | Компонент просмотра PDF на базе pdf.js |
| `frontend/public/pdf.worker.min.mjs` | Web Worker для рендеринга PDF |
| `frontend/src/components/DocumentViewer.tsx` | Расширение: встроенный PdfViewer вместо ссылки на скачивание |

### 3.3. XML-экспорт с валидацией по XSD-схемам ЕЭК

| Файл | Описание |
|---|---|
| `services/integration-service/app/services/xml_builder.py` | Полная переработка: генерация XML по стандарту EEC 5.27.0 |
| `services/integration-service/app/services/xml_validator.py` | Валидация XML по XSD-схемам ЕЭК (6 файлов XSD) |
| `services/integration-service/xsd/eec_5.27.0/*.xsd` | 6 XSD-файлов стандарта EEC 5.27.0 (~30 000 строк) |

### 3.4. Улучшения калькулятора таможенных платежей

| Файл | Что изменено |
|---|---|
| `services/calc-service/app/services/payment_calculator.py` | Доработка логики расчёта пошлин, сборов, НДС |

### 3.5. Улучшения AI-парсинга и маппинга полей

| Файл | Что изменено |
|---|---|
| `services/ai-service/app/services/agent_crew.py` | Улучшенная логика маппинга полей декларации |
| `services/ai-service/app/services/rules_engine.py` | Улучшения правил |
| `services/core-api/app/routers/apply_parsed.py` | Более точный AI-маппинг полей при применении результатов парсинга |
| `services/core-api/app/routers/classifiers.py` | Новые эндпоинты для справочников |

### 3.6. Миграции и конфигурация

| Файл | Описание |
|---|---|
| `services/core-api/alembic/versions/022_fts_xml_data_model.py` | Миграция: добавление полей для XML-модели данных |
| `services/core-api/alembic/versions/023_declaration_fields_fix.py` | Миграция: фикс полей декларации |
| `services/core-api/app/seeds/doc_type.json` | Seed-данные: типы документов |
| `docker-compose.yml`, `docker-compose.prod.yml` | Обновление конфигурации контейнеров |
| `frontend/Dockerfile`, `frontend/Dockerfile.dev` | Обновление Dockerfile фронтенда |
| `services/integration-service/Dockerfile` | Обновление Dockerfile integration-service |

### 3.7. Фронтенд

| Файл | Что изменено |
|---|---|
| `frontend/src/pages/DeclarationEditPage.tsx` | Интеграция ItemEditCard, PdfViewer, улучшение UX |
| `frontend/src/pages/DeclarationViewPage.tsx` | Отображение документов к товарам |
| `frontend/src/types/index.ts` | Новые TypeScript-типы: `ItemDocument`, `ItemPrecedingDoc` и др. |
| `frontend/src/api/declarations.ts` | Новые API-вызовы |
| `frontend/src/api/documents.ts` | Обновлённый API-клиент для документов |
| `frontend/src/components/AiExplainPanel.tsx` | Мелкие улучшения панели AI-пояснений |
| `frontend/src/components/DocumentUploadPanel.tsx` | Улучшение панели загрузки документов |
| `frontend/package.json` | Обновление зависимостей |

---

## Коммит 4: `198e3c2` — feat: customs value declaration (ДТС-1) — full module

Полная реализация модуля Декларации таможенной стоимости (ДТС-1, метод 1 — стоимость сделки) по форме Решения ЕЭК №160.

### 4.1. База данных — 2 новые таблицы

**Миграция `024_customs_value_declaration.py`:**

| Таблица | Описание |
|---|---|
| `core.customs_value_declarations` | Заголовок ДТС: форма, графы 7–9 (взаимосвязь, ограничения, ИС), графа 6 (документы), графа 10б (заполнивший), перевозчик, курс USD |
| `core.customs_value_items` | Расчёт по товару: гр.11 (цена сделки), гр.12 (основа), гр.13–19 (начисления), гр.20 (итого начислений), гр.21–23 (вычеты), гр.24 (итого вычетов), гр.25 (таможенная стоимость руб/USD) |

**Миграция `025_dts_fixes_invoice_contract_transport.py`:**

| Таблица | Добавлены колонки |
|---|---|
| `core.declarations` | `invoice_number`, `invoice_date`, `contract_number`, `contract_date` — для граф 4 и 5 ДТС |
| `core.customs_value_declarations` | `transport_carrier_name`, `transport_destination`, `usd_exchange_rate` — для граф 17 и 25б |

### 4.2. Backend — модели и схемы

**Новые файлы:**

| Файл | Описание |
|---|---|
| `services/core-api/app/models/customs_value_declaration.py` | SQLAlchemy модель `CustomsValueDeclaration` — заголовок ДТС с relationship к items |
| `services/core-api/app/models/customs_value_item.py` | SQLAlchemy модель `CustomsValueItem` — строка расчёта по товару (25+ числовых полей) |
| `services/core-api/app/schemas/customs_value_declaration.py` | Pydantic v2 схемы: `CustomsValueDeclarationUpdate`, `CustomsValueDeclarationResponse`, `CustomsValueItemCreate`, `CustomsValueItemUpdate`, `CustomsValueItemResponse` |

**Изменённые файлы:**

| Файл | Что изменено |
|---|---|
| `services/core-api/app/models/__init__.py` | Экспорт `CustomsValueDeclaration`, `CustomsValueItem` |
| `services/core-api/app/models/declaration.py` | Добавлены поля `invoice_number`, `invoice_date`, `contract_number`, `contract_date` + relationship `customs_value_declaration` |
| `services/core-api/app/schemas/__init__.py` | Экспорт ДТС-схем |
| `services/core-api/app/schemas/declaration.py` | Поля `invoice_number/date`, `contract_number/date` в `DeclarationUpdate` и `DeclarationResponse` |

### 4.3. Backend — CRUD-роутер ДТС

**Новый файл: `services/core-api/app/routers/customs_value.py`**

Полный REST API для управления ДТС:

| Метод | Эндпоинт | Описание |
|---|---|---|
| `GET` | `/api/v1/declarations/{id}/dts/` | Получить ДТС с позициями |
| `POST` | `/api/v1/declarations/{id}/dts/generate` | Автогенерация ДТС из данных декларации |
| `PUT` | `/api/v1/declarations/{id}/dts/` | Обновить заголовок ДТС |
| `PUT` | `/api/v1/declarations/{id}/dts/items/{item_id}` | Обновить строку расчёта по товару |
| `POST` | `/api/v1/declarations/{id}/dts/recalculate` | Пересчитать все позиции (графы 12, 20, 24, 25) |
| `DELETE` | `/api/v1/declarations/{id}/dts/` | Удалить ДТС |

**Логика автогенерации (`POST /generate`):**
- Берёт данные из декларации: курс валюты, условия поставки, фрахт
- Конвертирует фрахт в рубли через exchange_rate
- Распределяет транспортные расходы по товарам пропорционально весу брутто
- Рассчитывает для каждого товара: цену в валюте → цену в руб → основу → начисления → вычеты → ТС
- Получает курс USD из calc-service для расчёта ТС в долларах

**Изменённые файлы:**

| Файл | Что изменено |
|---|---|
| `services/core-api/app/main.py` | Подключён роутер `customs_value.router` |
| `services/core-api/app/routers/declarations.py` | Копирование полей invoice/contract при дублировании декларации |

### 4.4. AI-парсинг — извлечение страховки и погрузки

| Файл | Что изменено |
|---|---|
| `services/ai-service/app/services/agent_crew.py` | В результат compile добавлены `insurance_amount/currency`, `loading_cost/currency` из транспортных документов |
| `services/ai-service/app/services/transport_parser.py` | Расширен парсинг: извлечение `insurance_amount`, `insurance_currency`, `loading_cost`, `loading_currency` из AWB/CMR/накладных |

### 4.5. apply_parsed — автообновление ДТС при повторном парсинге

| Файл | Что изменено |
|---|---|
| `services/core-api/app/routers/apply_parsed.py` | **+83 строки:** маппинг `invoice_number/date`, `contract_number/date` из AI-парсинга; блок «3b-dts» — если ДТС уже существует, обновляет страховку и погрузку/разгрузку пропорционально весу, пересчитывает итоги |

### 4.6. XML-экспорт ДТС

**Новые файлы:**

| Файл | Описание |
|---|---|
| `services/integration-service/app/services/dts_xml_builder.py` | Генератор XML для ДТС-1 по стандарту EEC: namespace-ы `urn:EEC:R:CustomsValueDeclaration:v1.0.0`, структура SubjectDetails (продавец/покупатель/декларант), DeliveryTerms, TransactionCharacteristics (графы 7–9), Items с AdditionalCharges/Deductions/CustomsValue |

**Изменённые файлы:**

| Файл | Что изменено |
|---|---|
| `services/integration-service/app/routers/xml_export.py` | **+44 строки:** эндпоинт `GET /export-dts-xml/{id}` — скачивание ДТС в XML |

### 4.7. Фронтенд — UI для ДТС

**Новые файлы:**

| Файл | Описание |
|---|---|
| `frontend/src/api/customsValue.ts` | API-клиент: `getDts`, `generateDts`, `updateDts`, `updateDtsItem`, `recalculateDts`, `deleteDts` |
| `frontend/src/components/DtsPanel.tsx` | Панель ДТС на странице редактирования: Лист 1 (общие сведения, графы 7–9, документы, заполнивший), Лист 2 (расчёт по товарам), кнопки генерации/пересчёта/удаления |
| `frontend/src/components/DtsItemCard.tsx` | Карточка расчёта по товару: редактируемые поля граф 11–25 (цена, начисления, вычеты), readonly итоги |
| `frontend/src/pages/DtsViewPage.tsx` | Страница просмотра ДТС в официальной форме (Решение ЕЭК №160): Лист 1 (продавец, покупатель, условия, счёт, контракт, взаимосвязь), Лист 2+ (до 3 товаров на лист, все графы 11–25). Поддержка печати через `@media print` |

**Изменённые файлы:**

| Файл | Что изменено |
|---|---|
| `frontend/src/App.tsx` | Маршрут `/declarations/:id/dts-view` → `DtsViewPage` |
| `frontend/src/pages/DeclarationEditPage.tsx` | Добавлена `DtsPanel`, поля инвойса/контракта (гр. 4–5), кнопка «XML стоимости (ДТС)», разделены кнопки «XML декларации (ДТ)» и «XML стоимости (ДТС)» |
| `frontend/src/pages/DeclarationViewPage.tsx` | Кнопка «Просмотр ДТС» → навигация на `/dts-view` |
| `frontend/src/types/index.ts` | Новые TypeScript-типы: `CustomsValueItem` (25+ полей), `CustomsValueDeclaration` (20+ полей); добавлены `invoice_number/date`, `contract_number/date` в `Declaration` |

---

## Затронутые сервисы

| Сервис | Изменения |
|---|---|
| **core-api** (8001) | 2 миграции, 2 новые модели, 1 новый роутер, обновлены schemas + apply_parsed + declarations |
| **ai-service** (8003) | Расширен agent_crew (страховка/погрузка), transport_parser |
| **integration-service** (8004) | Новый dts_xml_builder, эндпоинт export-dts-xml |
| **calc-service** (8005) | Улучшение payment_calculator |
| **file-service** (8002) | Улучшения storage, routes |
| **frontend** | 4 новых файла, 5 изменённых, новый маршрут |

## Порядок деплоя

1. **Миграции БД** (обязательно до рестарта core-api):
   ```bash
   docker compose exec core-api alembic upgrade head
   ```
   Миграции: `022` → `023` → `024` (таблицы ДТС) → `025` (invoice/contract/transport поля)

2. **Пересобрать и перезапустить сервисы:**
   ```bash
   docker compose build core-api ai-service integration-service frontend
   docker compose up -d core-api ai-service integration-service frontend
   ```

3. **Проверка:**
   - Открыть декларацию → в редактировании появится блок «ДТС-1»
   - Нажать «Сформировать ДТС» → должна создаться ДТС с расчётом по товарам
   - Перейти в «Просмотр ДТС» → печатная форма по стандарту ЕЭК
   - Скачать «XML стоимости (ДТС)» → XML-файл
