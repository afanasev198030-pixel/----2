# Изменения для push 2026-03-05

Описание всех изменений относительно текущей remote-версии (`origin/main`).

**Коммиты:** 3 | **Файлов затронуто:** 32 | **Строк:** +2 943 / −508

---

## Коммит 1: `33b1395` — feat: classifier sync with EEC, AI agent improvements

### Новый функционал: синхронизация справочников с порталом ЕАЭС

Добавлен полный цикл автоматической синхронизации справочников ТН ВЭД
с портала `portal.eaeunion.org` (OData API).

**Новые файлы:**

| Файл | Описание |
|---|---|
| `services/core-api/app/services/eec_connector.py` | HTTP-клиент для OData API портала ЕАЭС |
| `services/core-api/app/services/eec_classifier_config.py` | Конфигурация 13+ типов справочников (GUID, маппинг полей) |
| `services/core-api/app/services/classifier_sync.py` | Логика full/incremental sync с дедупликацией и логированием |
| `services/core-api/app/models/classifier_sync_log.py` | Модель для логов синхронизации |
| `services/core-api/alembic/versions/014_classifier_sync.py` | Миграция: поля `source`, `eec_record_id`, `start_date`, `end_date` в classifiers + таблица `classifier_sync_log` |
| `services/core-api/alembic/versions/015_classifier_name_length.py` | Миграция: увеличение `classifiers.name_ru` до varchar(2000) |
| `services/ai-service/app/ml_models/hs_classifier_optimized.json` | Оптимизированная модель для классификации HS-кодов |
| `docs/ROADMAP.md` | Дорожная карта проекта |

**Изменённые файлы:**

| Файл | Что изменено |
|---|---|
| `docker-compose.yml` | Добавлены env-переменные для EEC-синхронизации (`EEC_PORTAL_BASE_URL`, `EEC_SYNC_ENABLED`, `EEC_SYNC_INTERVAL_HOURS`) |
| `services/core-api/app/config.py` | Новые настройки EEC sync |
| `services/core-api/app/main.py` | Автозапуск фоновой синхронизации при старте сервиса |
| `services/core-api/app/models/__init__.py` | Экспорт `ClassifierSyncLog` |
| `services/core-api/app/models/classifier.py` | Поля `source`, `eec_record_id`, `start_date`, `end_date` |
| `services/core-api/app/models/declaration.py` | Мелкие правки типов полей |
| `services/core-api/app/routers/admin.py` | **+143 строки:** эндпоинты `POST /admin/classifiers-sync` (запуск синхронизации), `GET /admin/classifiers-sync/status` (статус), `GET /admin/classifiers-sync/logs` (логи) |
| `services/core-api/app/routers/classifiers.py` | Фильтрация по `source`, поиск по `eec_record_id` |
| `services/core-api/app/seeds/load.py` | Обновлены seed-данные |
| `services/core-api/app/seeds/load_graph_rules.py` | Рефакторинг загрузки graph rules |

### Улучшения AI-сервиса

| Файл | Что изменено |
|---|---|
| `services/ai-service/app/services/agent_crew.py` | **+550 строк:** улучшенная логика заполнения декларации — расчёт Graph 42 (фактурная стоимость), корректный `mos_method_code`, привязка весов из packing list, маппинг тех. описания к позициям инвойса |
| `services/ai-service/app/services/contract_parser.py` | Улучшенное извлечение данных из контрактов |
| `services/ai-service/app/services/packing_parser.py` | Улучшенный парсинг упаковочных листов |
| `services/ai-service/app/services/transport_parser.py` | Расширенный парсинг транспортных документов (AWB, CMR) |
| `services/ai-service/app/services/dspy_modules.py` | Обновлённые DSPy-модули |
| `services/ai-service/app/services/hs_classifier.py` | Мелкие улучшения классификатора |
| `services/ai-service/app/rules/declaration_mapping_v3.yaml` | Обновлённые правила маппинга полей декларации (v3) |

### Изменения на фронтенде

| Файл | Что изменено |
|---|---|
| `frontend/src/api/ai.ts` | Обновлённый API-клиент для AI-сервиса |
| `frontend/src/pages/DeclarationEditPage.tsx` | Доработка страницы редактирования декларации |

### Обновление роутера apply_parsed

| Файл | Что изменено |
|---|---|
| `services/core-api/app/routers/apply_parsed.py` | Graph 42 (приоритет `line_total` → `unit_price × quantity` → `unit_price`), расчёт `customs_value_rub` через курс ЦБ, сборка `tax_number` из `inn/kpp`, логирование ошибок AI-feedback |

### Документация

| Файл | Что изменено |
|---|---|
| `docs/declaration_ai_filling_rules.md` | Масштабное обновление правил заполнения деклараций |
| `docs/audit-2025-02-18.md` | Обновление аудита |

---

## Коммит 2: `3bd84a7` — fix: resolve migration conflicts and create parse_issues table

Исправление конфликтов Alembic-миграций, возникших из-за параллельной разработки.

| Что было | Что стало |
|---|---|
| `011_classifier_sync.py` (конфликт с remote `011_ai_strategies.py`) | Переименован → `014_classifier_sync.py` (revision 014, depends on 013) |
| `012_classifier_name_length.py` (конфликт с remote `012_evidence_map.py`) | Переименован → `015_classifier_name_length.py` (revision 015, depends on 014) |
| `012_evidence_map.py` — пытался добавить колонки к несуществующей `parse_issues` | Исправлен: теперь создаёт таблицу `parse_issues` целиком |

**Цепочка миграций после исправления:**
```
010 → 011_ai_strategies → 012_evidence_map → 013_hs_code_history → 014_classifier_sync → 015_classifier_name_length
```

---

## Коммит 3: `0294664` — fix: add selectinload for Counterparty.company in all CRUD endpoints

Исправление ошибки `MissingGreenlet` (500 Internal Server Error) при запросе контрагентов.

**Причина:** async SQLAlchemy не поддерживает lazy loading связанных объектов. При сериализации `CounterpartyResponse` (включает вложенный `company`) Pydantic пытался обратиться к `counterparty.company`, вызывая ошибку.

**Исправлено в `counterparties.py`:**

| Эндпоинт | Что добавлено |
|---|---|
| `GET /counterparties/` (list) | `selectinload(Counterparty.company)` |
| `POST /counterparties/` (create) | Re-fetch с `selectinload` после commit |
| `PUT /counterparties/{id}` (update) | Re-fetch с `selectinload` после commit |
| `GET /counterparties/{id}` (get) | Был уже исправлен, убран лишний `from` import |
