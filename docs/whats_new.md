# What's New

---

## Полный редизайн UI, модель статусов, DeclarationFormPage, Provider Profiles

**Дата:** 2026-03-25 — 2026-03-28
**Ветка:** `feature/provider-profiles-landing`

### Обзор

Масштабный рефакторинг фронтенда: новая MUI-тема в стиле premium enterprise, модель статусов декларации (state machine), 2 новые страницы (DeclarationFormPage — форма редактирования по образцу печатной ДТ, DeclarationStatusPage — статусная страница с pre-send и AI-анализом), редизайн всех существующих страниц (Kanban, dashboard, view, DTS, 8 админских, профиль, настройки, клиенты), централизация конфигурации LLM-провайдеров (PROVIDER_PROFILES), совместимость JSON mode с Cloud.ru, редизайн лэндинга, защита от расхождения количества товарных позиций.

---

### 1. Модель статусов декларации (Declaration State Machine)

**Проблема**: декларация имела одно текстовое поле `status` без чёткого жизненного цикла. Переходы между статусами (draft → submitted → released) не контролировались — можно было перескочить из draft в released, минуя проверки.

**Что такое state machine**: это модель, в которой объект (декларация) может находиться только в определённых состояниях, и переходить между ними только по определённым правилам. Например: draft → submitted → released, но не draft → released напрямую.

**Решение**:
- **Миграция 029**: добавлены поля `state`, `substatus`, `assigned_to`, `priority`, `sla_deadline`, `last_state_change_at` в таблицу `declarations`
- **`declaration_state_service.py`** (199 строк): сервис переходов состояний с валидацией допустимых переходов, логированием, обновлением временных меток
- **Рефакторинг `workflow.py`**: все операции (submit, approve, release, reject, revise) переведены на state machine через `declaration_state_service`
- **StatusChip**: обновлён для отображения новых состояний с семантическими цветами (slate/emerald/amber/indigo)

### 2. DeclarationFormPage — форма по образцу печатной ДТ

**Проблема**: существующая `DeclarationEditPage` — это обычная веб-форма с полями в столбик. Брокеру неудобно: он привык к расположению граф как в бумажной/печатной ДТ (таможенной декларации), и при переносе данных с экрана на бумагу постоянно путается.

**Что такое ДТ**: Декларация на Товары — стандартизированный документ для таможенного оформления. Имеет фиксированную сетку граф (графа 1 — тип, графа 2 — отправитель, графа 14 — декларант и т.д.), расположенных по определённой схеме.

**Решение**: новая страница `DeclarationFormPage` (1603 строки):
- **Сетка граф** как в печатной ДТ — каждая ячейка имеет номер графы, название и привязку к полю
- **Статусы ячеек** (CellState): `ai` (заполнено AI), `confirmed` (подтверждено), `review` (требует проверки), `conflict` (конфликт источников), `manual` (заполнено вручную), `empty` (не заполнено) — с цветовой индикацией (фиолетовый/зелёный/жёлтый/оранжевый/синий/красный)
- **SourceDrawer**: боковая панель с информацией об источнике данных для каждого поля — из какого документа, с какой уверенностью, исходное значение
- **HS Code Suggestions**: подсказки кодов ТН ВЭД из истории компании прямо в боковой панели при редактировании графы 33
- **Разрешение контрагентов**: UUID покупателя/продавца автоматически конвертируются в читаемые имена
- **Просмотр документов**: DocumentViewer интегрирован в страницу

### 3. DeclarationStatusPage — статусная страница декларации

**Проблема**: для понимания «что с декларацией» нужно было открывать форму редактирования, проверять чеклист, смотреть документы в отдельной панели. Единого обзора состояния не было.

**Решение**: новая страница `DeclarationStatusPage` (690 строк):
- **Обзор готовности**: pre-send проверки, AI-проблемы (blocking/warning), полнота документов
- **Панель документов**: список прикреплённых документов с типами, просмотр через DocumentViewer
- **Позиции товаров**: список с кодами ТН ВЭД, AI-классификацией и подсказками из истории
- **Журнал действий**: лог изменений декларации
- **Навигация**: кнопки перехода к форме редактирования, просмотру для печати

### 4. Редизайн фронтенда — premium enterprise тема

**Проблема**: интерфейс выглядел как прототип — разные стили на разных страницах, мелкий шрифт, неконсистентные цвета, отсутствие единой дизайн-системы.

**Решение**: полная переработка визуальной темы (23+ файла):

**Тема (theme.ts)**:
- Палитра: slate (#0f172a, #64748b, #e2e8f0), emerald (success), amber (warning), indigo (accent)
- MUI overrides: Card (borderRadius 14, subtle border), Table (uppercase headers, stripe rows), Button (no shadow, rounded), Chip (refined), Paper (soft shadows)
- Шрифт Inter с оптимизированными размерами и weight

**Переработанные страницы**:

| Страница | Изменения |
|----------|-----------|
| `DeclarationsListPage` | Kanban-доска с цветовыми колонками, DeclarationKanbanCard с badges |
| `DeclarationViewPage` | Sticky header, documents sidebar, summary strip, bottom action bar |
| `DtsViewPage` | Тот же shell-паттерн — header, status, bottom bar |
| `BrokerDashboard` | KPI-карточки, welcome section, обновлённые графики |
| `AppLayout` | Белый header с логотипом Customs AI, slate-навигация |
| `ClientsListPage` + `ClientDetailPage` | Таблицы, кнопки, тарифные чипы, KPI-карточки |
| `ProfilePage` + `SettingsPage` | Paper/Card стили, статусы сервисов |
| 8 admin pages | Унифицированные Paper/Card/Chip/Typography |

**Новые/обновлённые компоненты**:
- `DeclarationKanbanCard` — карточка для Kanban с badges обработки/подписания
- `StatusChip` — расширен на все новые состояния state machine
- `ConfidenceBadge`, `RiskPanel`, `HistoryPanel` — унифицированные цвета
- `HSCodeSuggestions` — подсказки ТН ВЭД из истории компании

### 5. Миграция транспортных полей + AI-промпты

**Проблема**: поля транспорта в БД назывались абстрактно (`transport_at_border`, `transport_on_border_id`), не соответствовали графам ДТ. AI-промпт компиляции не разделял источники по графам — путал продавца (гр.11) с отправителем (гр.2).

**Решение**:
- **Миграция 030**: переименование полей в семантические имена:
  - `transport_at_border` → `departure_vehicle_info` (гр.18)
  - `transport_nationality_code` → `departure_vehicle_country` (гр.18)
  - `transport_on_border_id` → `border_vehicle_info` (гр.21)
  - Новые поля: `border_vehicle_country` (гр.21), `transport_doc_number` (AWB/CMR)
- **AI-промпт**: добавлены строгие приоритеты источников по графам:
  - Гр.2 (отправитель): ТОЛЬКО из транспортных источников (AWB/CMR → shipper_name). Использование invoice.seller/contract.seller ЗАПРЕЩЕНО
  - Гр.14 (покупатель): контракт > инвойс, ОБЯЗАТЕЛЬНО на русском
  - Гр.22 (валюта): ТОЛЬКО из контракта

### 6. Мокапы дизайн-системы

В папке `_mockups/` создан Vite-проект с Tailwind CSS — референсные макеты для всех ключевых страниц:
- Kanban-доска (BrokerHeader, DeclarationCard, KanbanBoard)
- Dashboard декларации (HeroStatus, IssuesPanel, DeclarationSummary, DocumentsSummary)
- Форма редактирования (PrintedForm, FieldRow, SectionNav, SourceDrawer, DocsSidebar)
- DTS-страница
- Полная UI-библиотека компонентов (shadcn/ui)

Мокапы используются как визуальный эталон при реализации MUI-компонентов в основном проекте.

### 7. Provider Profiles — единый реестр LLM-провайдеров

**Проблема**: информация о провайдерах (base_url, модель по умолчанию, поддержка JSON mode) была размазана по 10+ файлам в виде повторяющихся словарей `model_defaults`, `url_defaults`, `base_url_map`, `model_map`. Добавление нового провайдера требовало правок в 5–7 файлах, и каждый мог забыть обновить один из словарей.

**Что такое Provider Profile**: это словарь с характеристиками LLM-провайдера — адрес API (`base_url`), модель по умолчанию (`default_model`), модель для рассуждений (`reasoning_model`) и флаг поддержки JSON-ответов (`supports_json_mode`). Все провайдеры (DeepSeek, OpenAI, Cloud.ru) описаны в одном месте.

**Решение**: в `llm_client.py` добавлен словарь `PROVIDER_PROFILES` — единственный источник правды:

| Провайдер | base_url | default_model | supports_json_mode |
|-----------|----------|---------------|-------------------|
| deepseek | api.deepseek.com | deepseek-chat | да |
| openai | api.openai.com/v1 | gpt-4o | да |
| cloud_ru | foundation-models.api.cloud.ru/v1 | openai/gpt-oss-120b | нет |

Добавлены helper-функции:
- `get_provider_profile(provider)` — возвращает профиль по имени провайдера
- `supports_json_mode()` — проверяет, поддерживает ли текущий провайдер `response_format=json_object`
- `json_format_kwargs()` — возвращает `{"response_format": {"type": "json_object"}}` для совместимых провайдеров, пустой словарь для остальных

Все потребители обновлены:
- `config.py` — `effective_base_url` и `effective_model` используют `get_provider_profile()` вместо хардкода
- `main.py` — `configure_ai` endpoint берёт дефолты из профиля
- `settings.py` (core-api) — `provider_defaults` — единый словарь вместо двух отдельных маппингов; исправлена дефолтная модель OpenAI с `gpt-4o-mini` на `gpt-4o`

### 8. JSON mode — совместимость с Cloud.ru

**Проблема**: все LLM-вызовы в парсерах использовали `response_format={"type": "json_object"}`. Cloud.ru (gpt-oss-120b) не поддерживает этот параметр и возвращал ошибку. Система падала или деградировала при переключении на Cloud.ru.

**Что такое JSON mode**: это параметр API OpenAI, который заставляет модель гарантированно возвращать валидный JSON (а не текст с пояснениями). Не все провайдеры его поддерживают.

**Решение**: во всех 10 парсерах/модулях `response_format={"type": "json_object"}` заменён на `**json_format_kwargs()`. Для DeepSeek и OpenAI — работает как раньше. Для Cloud.ru — JSON запрашивается только через промпт (без параметра `response_format`), модель отвечает JSON благодаря инструкции в системном сообщении.

Затронутые парсеры: `llm_parser.py`, `agent_crew.py`, `contract_parser.py`, `invoice_parser.py`, `spec_parser.py`, `techop_parser.py`, `transport_parser.py`, `dspy_modules.py`, `gtd_reference_extractor.py`.

### 9. Items Guard — защита количества позиций

**Проблема**: LLM при компиляции декларации мог создать позиции из спецификации вместо инвойса. Если в инвойсе 1 товар, а в спецификации 5 — LLM возвращал 5 позиций, задваивая данные.

**Решение** (три уровня защиты):

1. **Промпт**: усилены инструкции — спецификация ЯВНО отмечена как НЕ источник товарных позиций, только для items_count/incoterms/delivery_place. Добавлено правило: количество позиций СТРОГО совпадает с инвойсом.

2. **Контекст**: из данных спецификации, передаваемых в LLM, убраны отдельные `items` — остаются только `items_count` и итоговые суммы. LLM физически не видит товарные позиции спецификации.

3. **Пост-валидация**: после ответа LLM проверяется `len(items) == len(invoice.items)`. При расхождении — принудительная замена на позиции из инвойса с логированием предупреждения.

### 10. Редизайн лэндинга

**Проблема**: лэндинг использовал тёмную «кибер»-тему с неоновыми свечениями (GlowOrb, shimmer, pulse-анимации). Визуально не соответствовал профессиональному B2B-продукту для таможенных брокеров.

**Решение**: полная переработка визуальной темы:

| До | После |
|----|-------|
| Тёмный фон `#0B1120` | Светлый `#f8fafc` |
| Неоновый cyan `#00D4FF` | Деловой синий `#2563eb` |
| GlowOrb, pulse, shimmer | Чистые карточки, минимальный float |
| Абстрактные описания | Скриншоты реального продукта |
| ClickAwayListener, GlassCard | LandingCard с border и тенью |

Добавлены 3 скриншота продукта (`/screenshots/dashboard.png`, `declarations.png`, `form.png`) в компоненте BrowserFrame — пользователь видит реальный интерфейс до регистрации. Новые MUI-иконки: `DescriptionOutlined`, `Search`, `CalculateOutlined`, `ShieldOutlined`, `ViewKanbanOutlined`, `FolderOpenOutlined`, `Business`, `Public`, `LocalShipping`, `ArrowForward`.

### Затронутые файлы

**Frontend — новые страницы и компоненты (7 файлов):**

| Файл | Строк | Назначение |
|---|---|---|
| `frontend/src/pages/DeclarationFormPage.tsx` | 1603 | Форма редактирования по образцу печатной ДТ |
| `frontend/src/pages/DeclarationStatusPage.tsx` | 690 | Статусная страница с pre-send и AI-анализом |
| `frontend/src/pages/DeclarationDashboardPage.tsx` | 671 | Dashboard декларации (hero status, issues, docs) |
| `frontend/src/components/DeclarationKanbanCard.tsx` | 258 | Карточка Kanban с badges обработки |
| `frontend/src/components/MetricCard.tsx` | 98 | KPI-карточка для дашбордов |
| `frontend/src/components/PageHeader.tsx` | 75 | Унифицированный заголовок страницы |
| `frontend/public/screenshots/*.png` | — | 3 скриншота продукта для лэндинга |

**Frontend — переработанные файлы (23 файла):**

| Файл | Изменения |
|---|---|
| `frontend/src/theme.ts` | Полная переработка MUI темы: slate palette, premium overrides |
| `frontend/src/pages/DeclarationsListPage.tsx` | Kanban-доска, таблица, фильтры — новый визуал |
| `frontend/src/pages/DeclarationViewPage.tsx` | Sticky header, docs sidebar, summary strip |
| `frontend/src/pages/DtsViewPage.tsx` | Shell-паттерн: header, status, bottom bar |
| `frontend/src/pages/BrokerDashboard.tsx` | KPI-карточки, welcome, графики |
| `frontend/src/pages/LandingPage.tsx` | +436/−495: dark → light тема, скриншоты |
| `frontend/src/pages/DeclarationEditPage.tsx` | Минорные обновления для совместимости |
| `frontend/src/pages/ClientsListPage.tsx` | Таблицы, кнопки, тарифные чипы |
| `frontend/src/pages/ClientDetailPage.tsx` | KPI-карточки, таблицы |
| `frontend/src/pages/ProfilePage.tsx` | Paper/Card стили |
| `frontend/src/pages/SettingsPage.tsx` | Статусы сервисов, Paper/Card |
| `frontend/src/pages/Admin*.tsx` (8 файлов) | Унификация Paper/Card/Chip |
| `frontend/src/components/AppLayout.tsx` | Белый header с Customs AI |
| `frontend/src/components/KanbanView.tsx` | Цветовые колонки, новые карточки |
| `frontend/src/components/StatusChip.tsx` | Расширен для state machine |
| `frontend/src/components/ConfidenceBadge.tsx` | Унифицированные цвета |
| `frontend/src/components/HSCodeSuggestions.tsx` | Подсказки ТН ВЭД |
| `frontend/src/types/index.ts` | Новые типы для state machine |

**Backend — ai-service (12 файлов):**

| Файл | Изменения |
|---|---|
| `llm_client.py` | +70: PROVIDER_PROFILES, json_format_kwargs() |
| `agent_crew.py` | +313: промпты источников по графам, items guard, json_format_kwargs |
| `config.py`, `main.py` | Profile-driven конфигурация |
| 7 парсеров | response_format → **json_format_kwargs() |
| `rules_engine.py` | Расширение правил заполнения |

**Backend — core-api (10 файлов):**

| Файл | Изменения |
|---|---|
| `declaration_state_service.py` | 199 строк — state machine для декларации |
| `workflow.py` | Переведён на state machine |
| `apply_parsed.py` | Обновлён под новые поля транспорта |
| `declarations.py`, `declaration_items.py` | Обновлены роутеры |
| `settings.py` | provider_defaults единый словарь |
| `models/declaration.py` | Новые поля state machine + транспорт |
| `schemas/declaration.py`, `schemas/declaration_item.py` | Обновлены схемы |

**Миграции:**

| Файл | Назначение |
|---|---|
| `029_declaration_status_model_v2.py` | State machine: state, substatus, assigned_to, priority, sla_deadline |
| `030_rename_transport_fields.py` | Семантические имена транспортных полей |

**Прочее:**

| Файл | Назначение |
|---|---|
| `_mockups/` (~120 файлов) | Vite + Tailwind референсные макеты |
| `docker-compose.yml` | +3: onnx_cache volume для ChromaDB |

---

## Этап 1.5: Секреты в prod-compose

**Дата:** 2026-03-22
**Ветка:** `feature/prod-secrets-hardening`

### Обзор

Устранение дефолтных паролей-заглушек из production-конфигурации, добавление аутентификации Redis, закрытие внутренних портов наружу и создание шаблона `.env.production.example`.

---

### 1. Убраны дефолтные секреты из docker-compose.prod.yml

**Проблема**: production-compose содержал fallback-значения вроде `${POSTGRES_PASSWORD:-customs_pass}`, `${JWT_SECRET_KEY:-change-me-in-production}`, `${MINIO_SECRET_KEY:-minioadmin}`. Если `.env` на сервере забыт или неполон — система стартовала с публично известными паролями (они видны в `.env.example` и git-истории).

**Решение**: все секретные переменные теперь используют `${VAR}` без `:-default`. Если переменная не задана — Docker Compose предупредит, а сервис не сможет аутентифицироваться (вместо тихого запуска с заглушкой).

Затронуты:
- `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` — postgres, core-api
- `JWT_SECRET_KEY` — core-api
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` — minio
- `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` — file-service

### 2. Redis — аутентификация в prod

**Проблема**: Redis не требовал пароля, а порт 6379 был открыт наружу. Любой с доступом к серверу мог подключиться и читать/модифицировать данные (кэш, ARQ-очередь, сессии бота).

**Решение**:
- Добавлен `command: redis-server --requirepass ${REDIS_PASSWORD}`
- Healthcheck обновлён: `redis-cli -a ${REDIS_PASSWORD} ping | grep PONG`
- Connection strings всех сервисов обновлены: `redis://redis:6379/N` → `redis://:${REDIS_PASSWORD}@redis:6379/N`
- Затронуты: bot-service, core-api, ai-service, ai-worker, calc-service

### 3. Закрыты внутренние порты

**Проблема**: PostgreSQL (5432), Redis (6379), MinIO (9000/9001), ChromaDB (8100), все API-сервисы (8001-8005) и frontend (3000) были проброшены на хост через `ports`. Это позволяло обращаться к ним напрямую, минуя Nginx (и JWT-авторизацию).

**Решение**: `ports` заменены на `expose` для всех внутренних сервисов. Единственный открытый порт — `nginx:80` (единая точка входа с X-Request-ID и проксированием).

| До (ports) | После (expose) |
|-----------|----------------|
| postgres 5432 | expose 5432 |
| redis 6379 | expose 6379 |
| minio 9000, 9001 | expose 9000, 9001 |
| chromadb 8100→8000 | expose 8000 |
| core-api 8001 | expose 8001 |
| file-service 8002 | expose 8002 |
| ai-service 8003 | expose 8003 |
| calc-service 8005 | expose 8005 |
| integration-service 8004 | expose 8004 |
| frontend 3000 | expose 3000 |
| **nginx 80** | **ports 80 (оставлен)** |

### 4. Python config — убраны дефолтные секреты

- **file-service/config.py**: `MINIO_ACCESS_KEY` и `MINIO_SECRET_KEY` — убран дефолт `"minioadmin"`. Pydantic не даст запустить сервис без явного значения.
- **bot-service/config.py**: `TELEGRAM_BOT_TOKEN` — убран дефолт `"YOUR_BOT_TOKEN_HERE"`, заменён на пустую строку.
- **ai-service/routers/chat.py**: захардкоженный `redis.from_url("redis://redis:6379/2")` заменён на `get_settings().REDIS_BROKER_URL` из config.

### 5. Создан `.env.production.example`

Шаблон для production-деплоя с инструкциями по генерации секретов (`openssl rand -hex 16/32`), группировкой по обязательности, и комментариями по каждой переменной.

**Затронутые файлы (7 файлов):**
- `docker-compose.prod.yml` — секреты, Redis password, ports→expose
- `services/file-service/app/config.py`
- `services/bot-service/app/config.py`
- `services/ai-service/app/routers/chat.py`
- `.env.example` — добавлен `REDIS_PASSWORD`
- `.env.production.example` — новый файл
- `docs/architecture.md` — статус 1.5 → ВЫПОЛНЕНО

---

## Этап 1.3: Унификация logging + Этап 1.4: Resource Limits + ai-service non-blocking fix

**Дата:** 2026-03-22
**Ветка:** `feature/infra-logging-limits`

### Обзор

Унификация structlog JSON-логирования во всех сервисах, добавление resource limits (memory + CPU) во все Docker-контейнеры, и исправление блокировки event loop в ai-service при LLM-обработке.

---

### 1. Унификация logging — structlog JSON (Этап 1.3)

**Проблема**: ai-service, calc-service, bot-service, file-service и integration-service не имели единого `structlog.configure()` с `JSONRenderer`. Логи выводились в plain text, `correlation_id` и `service_name` не попадали в вывод — трассировка между сервисами была невозможна.

**Решение**: единый шаблон `app/utils/logging.py` во всех сервисах.

- **`setup_logging()`** — стандартная функция в каждом сервисе: `JSONRenderer` + `PrintLoggerFactory` + `merge_contextvars` + фильтрация по `LOG_LEVEL`.
- **`merge_contextvars`** — критический процессор: обеспечивает попадание `correlation_id` и `service_name` в каждую JSON-строку лога.
- **`PrintLoggerFactory`** — вместо `LoggerFactory` (stdlib), чтобы логи гарантированно попадали в stdout (не терялись при отсутствии Python logging handlers).
- **`TracingMiddleware`** — во всех HTTP-сервисах прокидывает `X-Request-ID` → `correlation_id` через `structlog.contextvars`.
- **`tracing_headers()`** — helper для межсервисных вызовов (передаёт `X-Request-ID` в исходящие HTTP-запросы).
- **ai-worker** — вызывает `setup_logging()` в `_worker_startup` для JSON-логов в фоновых задачах.
- **bot-service** — `fetch_telegram_config()` вынесен из `config.py` в `main.py` (устранено логирование до инициализации structlog).
- **CLI-скрипты** (`offline_eval.py`, `update_tnved_online.py`) — вызывают `setup_logging()` в `__main__`.
- **`__init__.py`** — добавлены в `app/utils/` для file-service, calc-service, bot-service, integration-service.

**Затронутые файлы (20 файлов, 6 сервисов):**
- `*/app/utils/logging.py` — создан/обновлён в каждом сервисе
- `*/app/main.py` — убраны дублирующие `setup_logging()`, импорт из `utils`
- `*/app/middleware/tracing.py` — добавлен `tracing_headers()`
- `bot-service/app/config.py` — рефакторинг `fetch_telegram_config()`

---

### 2. Resource Limits в Docker Compose (Этап 1.4)

**Проблема**: ни один контейнер не имел ограничений по памяти и CPU. При пиковой нагрузке (LLM-обработка, PDF-конвертация) один контейнер мог забрать всю RAM хоста и вызвать OOM-killer, который убивал случайный процесс (например, PostgreSQL).

**Решение**: `deploy.resources` (limits + reservations) во всех контейнерах.

Лимиты рассчитаны для production-сервера 32 GB RAM / 8 CPU:

| Категория | Сервис | Memory | CPU |
|-----------|--------|--------|-----|
| Тяжёлый | ai-worker | 4G | 4.0 |
| Тяжёлый | ai-service | 2G | 2.0 |
| Тяжёлый | postgres | 2G | 2.0 |
| Тяжёлый | chromadb | 2G | 1.0 |
| Средний | core-api | 1G | 2.0 |
| Средний | gotenberg | 1G | 1.0 |
| Средний | minio | 1G | 1.0 |
| Лёгкий | file-service | 512M | 1.0 |
| Лёгкий | calc/integration/bot/redis | 512M | 0.5 |
| Лёгкий | nginx | 256M | 0.5 |
| Dev only | frontend (webpack) | 2G | 1.0 |
| Prod only | frontend (nginx static) | 256M | 0.5 |
| Dev only | phoenix | 1G | 0.5 |

- **Суммарно limits**: ~16.5 GB (~51% от 32 GB) — запас для ОС и пиков.
- **Суммарно reservations**: ~5 GB — гарантированный минимум.
- **frontend dev**: потребовал 2G + `NODE_OPTIONS=--max-old-space-size=1536` (webpack-dev-server React + TS + MUI).

**Затронутые файлы:**
- `docker-compose.yml` — все 15 сервисов
- `docker-compose.prod.yml` — все 14 сервисов

---

### 3. ai-service — non-blocking sync fallback

**Проблема**: при sync fallback (`TASK_QUEUE_ENABLED=false` или ошибка enqueue в ARQ) вызов `crew.process_documents()` блокировал asyncio event loop FastAPI на минуты. Docker healthcheck не получал ответа на `/health` и `/ready`, помечал контейнер как `unhealthy`.

**Решение**: `asyncio.run_in_executor()` для всех блокирующих вызовов.

- **`/parse-smart` sync fallback** — `crew.process_documents(file_data)` обёрнут в `await loop.run_in_executor(None, ...)`. Тяжёлая LLM-обработка идёт в ThreadPoolExecutor, event loop свободен для healthchecks.
- **`/parse-debug`** — вся обработка (OCR + classify + compile) вынесена в sync-функцию `_run_parse_debug()` и запускается через `run_in_executor()`.
- **`/ready`** — sync-вызовы `chromadb.heartbeat()` и `redis.ping()` обёрнуты в `run_in_executor()` — healthcheck не зависнет при проблемах с сетью.

**Результат**: `/health` отвечает за 18ms, `/ready` за 11-26ms. ai-service стабильно `healthy` даже при обработке LLM-задач.

**Затронутые файлы:**
- `services/ai-service/app/routers/smart_parser.py`
- `services/ai-service/app/main.py`

---

## Этап 1.1: Task Queue (ARQ) + Этап 1.2: Healthchecks

**Дата:** 2026-03-20
**Ветка:** `feature/task-queue-healthchecks`

### Обзор

Внедрение фоновой обработки документов через ARQ (Async Redis Queue) и полноценных healthcheck-ов (liveness + readiness) для всех микросервисов. Это первые два этапа плана рефакторинга инфраструктуры (Phase 0).

---

### 1. Task Queue — асинхронная обработка документов (Этап 1.1)

**Проблема**: парсинг пакета PDF (OCR + LLM классификация + HS-коды + риски) занимает 1–10 минут. Всё это время ai-service блокирован одним запросом, при нескольких параллельных пользователях рискует упасть по OOM или timeout.

**Решение**: обработка вынесена в отдельный ARQ worker процесс.

- **Новый сервис `ai-worker`** — Docker-контейнер с `arq app.workers.tasks.WorkerSettings`. Обрабатывает задачи из Redis DB 2, очередь `ai_tasks`. До 3 параллельных задач, timeout 30 минут.
- **`workers/tasks.py`** — задача `process_declaration_task`: OCR → LLM extraction → HS classification → risk assessment → автоматическое применение результата через `POST /api/v1/internal/apply-parsed/{id}`.
- **Гибридный режим `/parse-smart`** — задача ставится в worker (безопасная обработка в изолированном процессе), но endpoint ждёт результат (polling каждые 3 сек, timeout 9 мин) и возвращает полный ответ фронтенду. Фронтенд не требует доработки.
- **LLM config at startup** — worker при старте загружает актуальный API-ключ и настройки LLM из БД через `core-api/api/v1/settings/internal/llm-config`.
- **Internal apply-parsed endpoint** — `POST /api/v1/internal/apply-parsed/{id}` в core-api: находит декларацию, подтягивает пользователя-создателя, вызывает `apply_parsed_data` без JWT.
- **Миграция** — `028_task_queue_fields.py`: колонки `ai_task_id` и `processing_status` в `core.declarations`.

### 2. Healthchecks — liveness и readiness пробы (Этап 1.2)

**Проблема**: Docker проверял «контейнер запустился», но не проверял «сервис реально готов принимать запросы». При падении PostgreSQL или Redis — сервисы продолжали получать трафик и падали с ошибками.

**Решение**: разделение на два уровня проверок.

| Сервис | `/health` (liveness) | `/ready` (readiness) — проверяет |
|--------|---------------------|----------------------------------|
| core-api | `{"status":"ok"}` | PostgreSQL (SELECT 1), Redis (ping) |
| ai-service | `{"status":"ok"}` | ChromaDB (heartbeat), Redis (ping), LLM config (info) |
| ai-worker | — | Redis ping (Python one-liner) |
| file-service | `{"status":"ok"}` | MinIO (bucket_exists), Gotenberg (/health) |
| calc-service | `{"status":"ok"}` | (нет внешних зависимостей) |
| integration-service | `{"status":"ok"}` | core-api (/health) |
| frontend | — | wget http://127.0.0.1:3000/ |
| nginx | — | curl http://localhost:80/ |
| gotenberg | — | curl /health |

- **Liveness** (`/health`) — легковесная проверка «процесс жив», всегда 200 OK.
- **Readiness** (`/ready`) — проверка зависимостей. Возвращает 503 при недоступности критических сервисов, 200 когда всё работает. Docker использует `/ready` для healthcheck.
- **depends_on с condition: service_healthy** — ai-service ждёт ChromaDB + Redis, file-service ждёт Gotenberg, ai-worker ждёт Redis + core-api + ai-service.
- **start_period** — для сервисов с долгим стартом (frontend: 30s, ai-service: 20s, core-api: 15s).
- **Деградация и восстановление** — при падении зависимости readiness возвращает 503 с детализацией ошибки. После восстановления автоматически возвращается в 200.

### Результаты тестирования

Проведено полное тестирование:
- `/health` и `/ready` для всех 5 бэкенд-сервисов — PASS
- Docker healthcheck статусы 14 контейнеров — все healthy
- ARQ worker: запуск, LLM config, Redis, queue name — PASS
- Internal apply-parsed: edge cases + реальная декларация — PASS
- Деградация: остановка ChromaDB → ai-service `/ready` 503, `/health` 200 — PASS
- Деградация: остановка Redis → core-api `/ready` 503, PostgreSQL ok — PASS
- Восстановление: после запуска зависимости → `/ready` 200 — PASS

### Изменённые файлы

| Файл | Изменения |
|---|---|
| `docker-compose.yml` | +99: healthchecks для всех сервисов, ai-worker, depends_on с service_healthy, start_period |
| `docker-compose.prod.yml` | +45: healthchecks для prod |
| `services/core-api/app/main.py` | +120: `/ready` (PostgreSQL + Redis), `internal/apply-parsed`, `internal/task-complete` |
| `services/core-api/app/models/declaration.py` | +4: `ai_task_id`, `processing_status` |
| `services/ai-service/app/main.py` | +64: `/ready` (ChromaDB + Redis + LLM info) |
| `services/ai-service/app/routers/smart_parser.py` | +144: hybrid polling mode, task-status endpoint |
| `services/ai-service/app/config.py` | +7: ARQ settings (queue name, max_jobs, timeout, Redis broker URL) |
| `services/ai-service/requirements.txt` | +3: arq, redis |
| `services/file-service/app/main.py` | +46: `/ready` (MinIO + Gotenberg) |
| `services/calc-service/app/main.py` | +7: `/ready` |
| `services/integration-service/app/main.py` | +31: `/ready` (core-api) |

### Новые файлы

| Файл | Строк | Назначение |
|---|---|---|
| `services/ai-service/app/workers/__init__.py` | 0 | Package init |
| `services/ai-service/app/workers/tasks.py` | 178 | ARQ задача: OCR + LLM + HS + риски + auto-apply |
| `services/core-api/alembic/versions/028_task_queue_fields.py` | — | Миграция: ai_task_id + processing_status |
| `docs/architecture.md` | 284 | Архитектурная документация с планом рефакторинга |

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

## Vision OCR + Quality Gate + Enhanced Parsing v4

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

---

## 2026-03-12 — Обучение AI, Drift Detection и Эскалация агентов

### Автоматический сбор обучающих данных для AI (Phase 1.1)

Раньше: AI-модель классификации кодов ТН ВЭД работала только на базовых правилах и не училась на реальных данных компании.

Теперь:
- В `core-api` добавлен фоновый процесс (`ai_training_sync_loop`), который раз в сутки собирает успешно отправленные или выпущенные декларации.
- Утверждённые позиции (описание товара + код ТН ВЭД) отправляются в `ai-service` как эталонные примеры.
- `ai-service` сохраняет эти примеры в локальный датасет (`hs_offline_eval_dataset.jsonl`) для последующего дообучения или few-shot промптинга.
- Добавлен ручной запуск синхронизации через админку (`POST /api/v1/admin/ai-training-sync`).

### Обнаружение дрифта кодов ТН ВЭД (Drift Detection)

Раньше: Если AI или пользователь выбирал код ТН ВЭД, который отличался от того, что компания исторически использовала для этого товара, система молчала.

Теперь:
- При загрузке позиций декларации `core-api` проверяет текущий код ТН ВЭД по исторической базе (`hs_code_history`).
- Если для похожего товара (similarity > 0.4) исторически использовался другой код, позиция помечается флагом `drift_status = true`.
- На фронтенде в карточке позиции (`ItemEditCard`) появляется желтое предупреждение о дрифте.
- Пользователь может в один клик "Вернуть исторический код" или осознанно "Оставить текущий код".

### Офлайн-оценка AI и CI/CD Quality Gate

Раньше: Изменения в промптах или логике AI выкатывались на продакшен без автоматической проверки того, не стало ли качество классификации хуже.

Теперь:
- В `ai-service` добавлен скрипт `offline_eval.py`, который прогоняет текущую логику классификации по накопленному датасету эталонных примеров.
- Скрипт вычисляет метрику Accuracy (доля правильных предсказаний).
- В GitHub Actions (`deploy-backend.yml`) добавлен обязательный шаг: перед деплоем запускается `offline_eval.py`. Если Accuracy падает ниже 85%, деплой блокируется.

### Эскалация сложных случаев (Triage Agents)

Раньше: Парсинг документов шел по одному линейному пути. Если случай был сложным, AI мог выдать галлюцинацию или ошибиться, не имея возможности перепроверить себя.

Теперь:
- Внедрен паттерн Triage (маршрутизация). Быстрый пайплайн обрабатывает простые документы.
- Если обнаружены расхождения (например, сумма в инвойсе не бьется с контрактом) или низкая уверенность (confidence < 0.7), задача эскалируется.
- Подключаются специализированные агенты:
  - `ReconciliationAgent` — ищет причину расхождений в документах.
  - `ReviewerAgent` — финально проверяет качество извлеченных данных перед сохранением.
- Это повышает надежность системы на сложных многостраничных пакетах документов.

### Исправления инфраструктуры и фронтенда

- Устранены циклические 307 редиректы при обращении к API без завершающего слеша.
- Исправлено состояние гонки (race condition) при логине, из-за которого пользователя выкидывало обратно на страницу авторизации.
- Устранены предупреждения React Router v7 (добавлены future flags).
- Восстановлены пароли тестовых пользователей (`admin@customs.local` и `user@customs.local`) в базе данных для корректной работы локального окружения.

---

## 2026-03-07 — GTD как эталон, живой smoke и умный pre-send

### GTD-файлы теперь не мешают парсингу

Раньше: файлы вида `GTD*.pdf` лежали в тех же папках, что и входные документы сделки. Из-за этого они могли случайно улетать в `parse-smart` как обычные PDF и искажать результат.

Теперь:
- `GTD*.pdf` исключаются из входного пакета для `parse-smart`,
- они трактуются как **эталонные готовые декларации**,
- на их основе можно строить regression/eval и проверять, насколько AI приблизился к правильному результату.

### Сквозной smoke на production теперь проверяет реальный core flow

Раньше: можно было проверить отдельные куски системы, но не весь путь цифрового брокера целиком на живом сервере.

Теперь:
- есть `scripts/smoke_digital_broker_flow.py`,
- он проходит цепочку:
  - `parse-smart`,
  - `from-parsed`,
  - `pre-send-check`,
  - `validate-xml`,
  - `export-xml`,
- smoke подтверждён на production: XML строится и валидируется, а draft после прогона удаляется автоматически.

### Pre-send стал умнее и ближе к реальной работе брокера

Раньше: сервер проверял только базовые вещи вроде пустых полей и отсутствия документов, но не видел многих бизнес-конфликтов.

Теперь:
- `pre-send` проверяет базовую матрицу документов (`invoice`, `contract`, `transport_doc`, `packing_list`),
- добавлена cross-doc сверка:
  - сумма декларации vs инвойс,
  - валюта декларации vs договор / инвойс,
  - веса и количество мест vs packing list,
  - количество позиций vs invoice,
  - наличие transport doc без переноса реквизитов,
- добавлено предупреждение о **drift по ТН ВЭД**: если текущий код расходится с устойчивой историей компании по похожему товару, система предупреждает до отправки.

### Серверные замечания теперь можно показать пользователю

Раньше: часть важных проверок существовала только на backend и была видна в момент ошибки или по API, но не в обычном интерфейсе пользователя.

Теперь:
- `DeclarationChecklist` можно расширять реальными server-side результатами `pre-send-check`,
- пользователь видит не только локальный чек-лист формы, но и проблемы из сохранённой версии декларации.

---

## 2026-03-07 — Core flow цифрового брокера, smoke-проверка и новый приоритет roadmap

### Цифровой брокер теперь проверяет не только поля, но и состав пакета

Раньше: `pre-send` проверял базовые вещи вроде пустых полей, отсутствия позиций и кодов ТН ВЭД. Но система почти не понимала, **какие именно документы приложены**, и не могла надёжно сверять декларацию с инвойсом, packing list и договором.

Теперь:
- документы из `parse-smart` передаются в `core-api` с нормализованным `doc_type`, filename, датой и облегчённым `parsed_data`,
- `pre-send` умеет проверять обязательный состав пакета: инвойс, контракт, транспортный документ, packing list,
- добавлены cross-doc проверки:
  - сумма декларации vs инвойс,
  - валюта декларации vs договор / инвойс,
  - веса и количество мест vs packing list,
  - число позиций в декларации vs инвойс,
  - приложен транспортный документ, но его реквизиты не перенесены в декларацию.

Это переводит систему от проверки "заполнено / не заполнено" к проверке "декларация реально согласована с пакетом документов".

### Появился smoke-контур для ключевого сценария брокера

Раньше: после изменений в AI и маппинге можно было проверить только куски сценария вручную. Не было одной команды, которая прогоняет основной путь целиком.

Теперь:
- добавлен `scripts/smoke_digital_broker_flow.py`,
- он проходит цепочку:
  - `parse-smart`,
  - `from-parsed`,
  - `pre-send-check`,
  - `validate-xml`,
  - `export-xml`,
- скрипт пишет лог и пытается удалить созданный draft, чтобы не засорять базу,
- backend deploy workflow теперь запускает этот smoke после выкладки.

Это значит, что "цифровой брокер работает" теперь можно проверять не на словах, а реальным сквозным сценарием.

### Roadmap перестроен под цифрового брокера

Раньше: roadmap смешивал инфраструктуру, цифрового логиста, мультиагентов и брокерское ядро почти на одном уровне. Из-за этого было неочевидно, что делать сначала.

Теперь:
- первым приоритетом зафиксирован **цифровой брокер таможенных деклараций**,
- сначала закрываются core flow, UX, AI-качество, оплата и юридически значимый контур,
- цифровой логист и тяжёлая event-driven мультиагентность вынесены в следующий горизонт роста,
- внутри Фазы 0 отдельно выделено, что нужно делать сразу, а что не должно тормозить продукт.

Итог: roadmap стал не просто стратегическим документом, а реальным порядком исполнения.

---

## 2026-03-03 — Observability, AI-стратегии, PDF viewer, evidence_map, pre-send gate

### Сквозной trace-id (Фаза 0.4)

Раньше: если у клиента что-то сломалось при загрузке документа — непонятно где искать. Запрос прошёл через nginx, попал в core-api, оттуда ушёл в ai-service, потом в file-service. В логах каждого сервиса — свои записи, никак не связанные между собой. Искать ошибку — как искать иголку в стоге сена.

Теперь: каждый запрос получает уникальный ID на входе. Этот ID проходит через все сервисы как нитка через бусины. Если что-то упало — берёшь один ID, grep по логам всех сервисов, и видишь весь путь запроса: что пришло, куда ушло, где сломалось, сколько заняло. Время на поиск ошибок сокращается с часов до минут.

### AI-стратегии заполнения (Фаза 1.2)

Раньше: чтобы изменить поведение AI при заполнении деклараций — нужен разработчик. Лезть в код, менять промпты, деплоить.

Теперь: брокер или админ заходит в `/admin/strategies`, пишет обычным русским языком: «Если поставщик ZED Group — ставить EXW и пост Шереметьево». Сохраняет. AI начинает это учитывать при следующем парсинге. Без разработчика, без деплоя, за 30 секунд. Бизнес-логика управляется бизнесом, а не кодом.

### Просмотр документов рядом с декларацией (Фаза 1.3)

Раньше: чтобы сверить, правильно ли AI заполнил декларацию — нужно открывать PDF-документ в отдельной вкладке, переключаться туда-сюда, сравнивать глазами.

Теперь: кнопка «Документы» прямо на странице редактирования. Справа выезжает панель — список всех прикреплённых документов. Кликнул на инвойс — видишь его содержимое рядом с формой. Слева форма, справа документ. Сверяешь не переключаясь.

### Контракт результата AI (Фаза 1.6)

Раньше: AI заполнил декларацию, но непонятно — откуда он взял каждое значение? Насколько уверен? Есть ли проблемы?

Теперь: для каждой декларации хранится:
- **evidence_map** — какое поле откуда взято (инвойс, контракт), с какой уверенностью, какое было исходное значение в документе.
- **ai_issues** — список проблем с чёткой классификацией: код ошибки, серьёзность, какое поле затронуто, блокирующая или нет.

Это фундамент для объяснимости AI и для автоматических проверок перед отправкой.

### Серверная проверка перед отправкой (Фаза 1.7)

Раньше: чеклист был только на фронте. Технически можно было отправить декларацию с пустыми полями или без документов.

Теперь: сервер не даст отправить декларацию, пока не пройдены 8 проверок:
- Обязательные поля декларации заполнены.
- Указаны отправитель и получатель.
- Есть хотя бы одна позиция товара.
- Прикреплены документы.
- У всех позиций есть код ТН ВЭД.
- Нет нерешённых блокирующих проблем парсинга.
- Нет блокирующих AI-проблем.
- Вес нетто не превышает вес брутто.

Если руководитель всё равно хочет отправить — может, но обязан написать причину, и это записывается в аудит.

**Итог:** проект перешёл от «работает, но на доверии» к «работает, контролирует себя и объясняет свои решения».

---

## 2026-03-03 — Автозаполнение контрагентов и история ТН ВЭД

### Автозаполнение контрагентов (Phase 1.5)

Раньше: после парсинга документов поля «Отправитель» и «Получатель» оставались пустыми в форме, хотя контрагенты создавались в БД. При каждом новом парсинге мог создаваться дубль контрагента.

Теперь:
- Контрагенты автоматически привязываются к форме декларации после парсинга.
- Поиск существующих контрагентов: сначала по ИНН/Tax ID, потом по точному имени, потом по похожему имени (ilike). Дубли не создаются.
- Если у найденного контрагента не было страны/адреса — данные дополняются из нового документа.
- Вся привязка в рамках компании пользователя (tenant isolation).

### История кодов ТН ВЭД (Phase 1.5)

Раньше: каждый раз AI подбирал код ТН ВЭД с нуля, даже если этот товар от этого поставщика уже оформлялся 10 раз.

Теперь:
- Каждый применённый код ТН ВЭД записывается в таблицу `hs_code_history` с привязкой к компании, контрагенту и описанию товара.
- При следующей декларации с похожим товаром — если AI не определил код, система автоматически подставит код из истории (pg_trgm similarity search).
- Счётчик usage_count растёт при повторных использованиях — чем чаще код применялся, тем выше приоритет.
- API `/api/v1/hs-history/suggest?description=...` — подсказки из истории для UI.

### LLM-ключи и модели

- Исправлено автоопределение провайдера: OpenAI ключ (sk-proj-*) автоматически ставит провайдер openai.
- Обновлён список моделей: gpt-4.1, gpt-4.1-mini, gpt-4.1-nano.
- При смене модели ai-service переконфигурируется автоматически.
- Уведомления: если LLM-ключ невалидный — красный баннер на Dashboard и сообщение при парсинге.
- Админ-навигация: AI-стратегии, пользователи, аудит, база знаний, чек-листы добавлены в верхнюю панель.

---

## 2026-03-06 — Explainability UI и AI-затраты

### Объяснимость AI в декларации (Phase 1.5 + 1.6)

Раньше: история кодов ТН ВЭД, источники полей и проблемы AI уже сохранялись в БД, но пользователь этого не видел. Для декларанта это выглядело как "что-то там внутри работает".

Теперь:
- В правой колонке `DeclarationEditPage` появился блок **AI-анализ**.
- Показывается общий confidence AI.
- Видны блокирующие и неблокирующие проблемы (`issues[]`).
- Видно, из какого документа пришли поля (`evidence_map`).
- Появилась история кодов ТН ВЭД компании: какие коды уже применялись и как часто.

### Unit-экономика AI (Phase 4.3)

Раньше: модель и токены тратились, но система не считала, сколько это реально стоит.

Теперь:
- Каждый вызов LLM пишет в `ai_usage_log`: входные/выходные токены, стоимость, модель, операция, декларация.
- Учитываются и прямые OpenAI-вызовы, и DSPy-вызовы.
- В админке появилась страница **AI-затраты** (`/admin/ai-costs`):
  - общие затраты,
  - стоимость 1 декларации,
  - общее число токенов,
  - среднее время ответа,
  - разбивка по операциям и моделям.

---

## 2026-03-06 — AI-затраты доведены до конца и стабилизация apply-parsed

### AI-затраты теперь считаются по-настоящему

Раньше: страница **AI-затраты** уже была, но там были нули. Таблица и дашборд существовали, а реальные вызовы моделей в базу не писались.

Теперь:
- любой вызов LLM через общий клиент автоматически пишет токены и стоимость в `ai_usage_log`,
- вызовы через DSPy тоже считаются, а не только прямые OpenAI-вызовы,
- `declaration_id` передаётся в AI-сервис, поэтому можно посчитать **стоимость одной конкретной декларации**,
- страница `/admin/ai-costs` показывает уже не заглушку, а живые данные: вызовы, токены, стоимость и разбивку по операциям.

### Стабилизация apply-parsed

Раньше: `apply-parsed` мог падать из-за того, что AI возвращал значения в старом или слишком длинном формате для полей декларации. Из-за этого декларация не сохранялась, хотя сами данные были распознаны.

Теперь:
- `deal_nature_code` нормализуется в единый рабочий формат (`01`, `02`, `03`),
- значения для коротких полей приводятся к допустимой длине до сохранения,
- устранён конфликт между старым AI-форматом и реальной схемой БД,
- загрузка документов стала устойчивее: меньше падений на этапе применения распознанных данных.

### Новое правило для разработки

Добавлено постоянное правило проекта: **не оставлять фичи полуготовыми**.

Это значит:
- если есть UI, должен работать backend,
- если есть backend, должен быть проверен реальный сценарий,
- если заявлен дашборд, в нём должны появляться реальные данные, а не нули и заглушки.
