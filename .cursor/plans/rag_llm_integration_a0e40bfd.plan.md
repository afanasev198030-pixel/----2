---
name: RAG LLM Integration
overview: "Скорректированный план v3. Стек: LlamaIndex (RAG ядро) + DSPy (оптимизация промптов) + CrewAI (мультиагенты) + Arize-Phoenix (observability) + Cortex Memory (прецеденты) + Open-RAG-Eval (тестирование)."
todos:
  - id: stage0-env
    content: .env.example + .env, проверка docker-compose up
    status: pending
  - id: stage0-alembic
    content: "Alembic: initial migration (все таблицы ER-схемы), запуск"
    status: pending
  - id: stage0-seeds
    content: "Seeds: загрузка справочников + ТН ВЭД"
    status: pending
  - id: stage0-frontend-fix
    content: "Frontend: исправления, недостающие компоненты"
    status: pending
  - id: rag-infra
    content: ChromaDB + LlamaIndex + DSPy + Arize-Phoenix в docker-compose и requirements
    status: pending
  - id: rag-llamaindex-core
    content: "LlamaIndex: index_manager.py (ТН ВЭД index + СУР index + прецеденты), query_engines"
    status: pending
  - id: rag-dspy-parser
    content: "DSPy: dspy_modules.py (InvoiceExtractor, ContractExtractor, PackingExtractor) — автооптимизация промптов"
    status: pending
  - id: rag-crewai-agents
    content: "CrewAI: agent_crew.py (DocumentParser, HSClassifier, RiskAnalyzer, PrecedentLearner)"
    status: pending
  - id: rag-phoenix-observability
    content: "Arize-Phoenix: трейсинг LLM вызовов, оценка quality, обнаружение галлюцинаций"
    status: pending
  - id: rag-router-frontend
    content: smart_parser.py роутер (CrewAI kickoff) + фронтенд мультизагрузка
    status: pending
  - id: rag-eval-test
    content: "Open-RAG-Eval: тестирование RAG ТН ВЭД + СУР на PDF из dek/"
    status: pending
  - id: stage2-integration-svc
    content: "integration-service: xml_builder, xml_validator, signature (mock), customs_gateway (mock), spot"
    status: pending
  - id: stage2-frontend
    content: "Frontend: отправка, SPOTBlock, StatusTimeline, SignaturePanel"
    status: pending
  - id: stage3-calc-svc
    content: "calc-service: payment_calculator, cbr_client, currency_control"
    status: pending
  - id: stage3-frontend
    content: "Frontend: PaymentsBlock, CurrencyControlBlock, Notifications, WebSocket"
    status: pending
  - id: stage4-cortex-memory
    content: "Cortex Memory: REST API для прецедентов, автоизвлечение, векторный поиск"
    status: pending
  - id: stage4-knowledge
    content: База знаний, чек-листы, AI retraining (DSPy auto-optimize), dashboard, admin panel
    status: pending
isProject: true
---

# Скорректированный общий план работ v3

## Стек AI-инструментов


| Приоритет | Инструмент        | Где в проекте                                           | Заменяет                                                   |
| --------- | ----------------- | ------------------------------------------------------- | ---------------------------------------------------------- |
| 1         | **LlamaIndex**    | RAG ядро: ТН ВЭД index, СУР index, query engines        | Самописные vector_store.py, rag_classifier.py, rag_risk.py |
| 2         | **DSPy**          | Оптимизация промптов парсинга и классификации           | Ручной prompt engineering в llm_parser.py                  |
| 3         | **Arize-Phoenix** | Observability ai-service: трейсинг LLM, quality metrics | Ручное логирование structlog                               |
| 4         | **Open-RAG-Eval** | Тестирование RAG без golden answers                     | Ручное сравнение результатов                               |
| 5         | **Cortex Memory** | База прецедентов с REST API                             | Самописный precedent_store.py                              |
| 6         | **CrewAI**        | Мультиагентная оркестрация: parse → classify → risk     | Линейный pipeline в smart_parser.py                        |


### Ключевая синергия: LlamaIndex + DSPy

- **LlamaIndex** — retrieval (поиск по 3500 ТН ВЭД, правилам СУР, прецедентам)
- **DSPy** — автоматическая оптимизация промптов классификации (критично при 3500+ кодах)
- Вместо ручной подгонки промптов → декларативное описание задачи → DSPy подбирает оптимальный промпт

---

## Текущее состояние проекта

### Готово (Этап 0 ~80%)


| Компонент          | Статус    | Детали                                                                                     |
| ------------------ | --------- | ------------------------------------------------------------------------------------------ |
| docker-compose.yml | ✅         | 8 сервисов: postgres, redis, minio, core-api, file-service, ai-service, nginx, frontend    |
| core-api           | ✅         | 10 моделей, schemas, 7 роутеров, JWT auth, structlog, middleware                           |
| file-service       | ✅         | Upload/download/delete через MinIO                                                         |
| ai-service (regex) | ✅ Базовый | OCR (pdfplumber), regex парсеры, keyword HS classifier (~60 кодов), rule engine (5 правил) |
| Frontend           | ✅ Базовый | Login, DeclarationsList, DeclarationEdit (wizard 7 этапов), DocumentUploadPanel            |
| nginx              | ✅         | Reverse proxy для всех сервисов                                                            |


### НЕ готово


| Компонент           | Что сделать                                                |
| ------------------- | ---------------------------------------------------------- |
| .env                | Создать .env.example + .env                                |
| Alembic             | Initial migration                                          |
| Seeds               | Загрузка справочников + ТН ВЭД                             |
| Frontend компоненты | CounterpartyLookup, ClassifierSelect, DeclarationChecklist |
| integration-service | Не создан (порт 8004)                                      |
| calc-service        | Не создан (порт 8005)                                      |


---

## Порядок реализации

### ФАЗА 1: Завершение MVP — 1-2 недели

**Цель:** `docker-compose up` → рабочая система ручного заполнения ДТ.

#### 1.1. Инфраструктура

- `.env.example` и `.env` со всеми переменными
- Проверить Dockerfile'ы, `docker-compose up --build`
- Починить ошибки запуска

#### 1.2. База данных

- Alembic: initial migration (10 таблиц)
- `alembic upgrade head`
- Seeds: справочники + ТН ВЭД
- Проверить API `/api/v1/classifiers/`

#### 1.3. Auth + Frontend

- Регистрация → логин → JWT → CRUD декларации
- Починить DeclarationEditPage
- CounterpartyLookup, ClassifierSelect

---

### ФАЗА 2: RAG + LLM (LlamaIndex + DSPy + CrewAI) — 4-5 недель

**Цель:** интеллектуальный парсинг PDF, RAG классификация ТН ВЭД, мультиагентная оценка рисков.

> Существующие regex-парсеры остаются как fallback.

#### 2.1. Инфраструктура AI-стека

**docker-compose.yml — новые контейнеры:**

```yaml
chromadb:
  image: chromadb/chroma:latest
  ports: ["8100:8000"]
  volumes: [chromadata:/chroma/chroma]

phoenix:  # Arize-Phoenix для LLM observability
  image: arizephoenix/phoenix:latest
  ports: ["6006:6006"]
  volumes: [phoenixdata:/phoenix]
```

**ai-service/requirements.txt — новые зависимости:**

```
# RAG ядро
llama-index>=0.11
llama-index-vector-stores-chroma>=0.3
llama-index-embeddings-openai>=0.3

# Оптимизация промптов
dspy-ai>=2.5

# Мультиагентная оркестрация
crewai>=0.80
crewai-tools>=0.14

# LLM
openai>=1.50
tiktoken>=0.7

# Observability
arize-phoenix>=5.0
openinference-instrumentation-llama-index>=3.0
openinference-instrumentation-dspy>=0.2

# Тестирование RAG
# open-rag-eval (dev dependency)
```

**.env — новые переменные:**

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
CHROMADB_HOST=chromadb
CHROMADB_PORT=8000
PHOENIX_HOST=phoenix
PHOENIX_PORT=6006
CORTEX_MEMORY_URL=http://cortex:8080  # Фаза 5
```

- Обновить docker-compose.yml (ChromaDB + Phoenix)
- Обновить requirements.txt
- Обновить .env
- Обновить config.py ai-service

#### 2.2. LlamaIndex — RAG ядро

**Новый файл: `services/ai-service/app/services/index_manager.py**`

Заменяет: `vector_store.py`, `rag_classifier.py`, `rag_risk.py`

```
IndexManager:
├── hs_codes_index      # VectorStoreIndex: 3500 ТН ВЭД (code + name_ru + description)
├── risk_rules_index    # VectorStoreIndex: 50+ правил СУР (conditions + severity + recommendation)
├── precedents_index    # VectorStoreIndex: успешные декларации (description → hs_code)
│
├── hs_query_engine     # RetrieverQueryEngine: top-10 кодов → GPT-4o выбирает точный
├── risk_query_engine   # RetrieverQueryEngine: релевантные правила → GPT-4o анализирует
├── precedent_retriever # VectorIndexRetriever: поиск похожих прецедентов
│
├── init_indices()      # Загрузка данных при старте (из PostgreSQL → ChromaDB)
└── add_precedent()     # Добавление нового прецедента после успешного выпуска
```

**Почему LlamaIndex, а не raw ChromaDB:**

- Нативная поддержка ChromaDB (`ChromaVectorStore`)
- Встроенные query engines с structured output
- Автоматическое управление embeddings (OpenAI/local)
- Response synthesizer для обоснования выбора кода ТН ВЭД
- `SubQuestionQueryEngine` для сложных запросов (код + правила + прецеденты одновременно)

**Новый файл: `services/ai-service/app/seeds/init_indices.py**`

```python
# Загрузка данных при первом старте:
# 1. 3500 ТН ВЭД из PostgreSQL → hs_codes_index
# 2. 50+ правил СУР из risk_rules.json → risk_rules_index
# 3. Прецеденты (если есть) → precedents_index
```

- Создать `index_manager.py` с LlamaIndex
- Создать `init_indices.py` для загрузки данных
- Подключить ChromaVectorStore
- Настроить query engines с structured output
- Тест: поиск ТН ВЭД по описанию товара

#### 2.3. DSPy — автооптимизация промптов

**Новый файл: `services/ai-service/app/services/dspy_modules.py**`

Заменяет: ручные промпты в `llm_parser.py`

```python
# DSPy модули (декларативное описание задач):

class InvoiceExtractor(dspy.Module):
    """Извлечение данных из инвойса — DSPy сам подберёт оптимальный промпт"""
    # Сигнатура: document_text → InvoiceParsed (structured output)
    # DSPy оптимизирует промпт на примерах из dek/

class HSCodeClassifier(dspy.Module):
    """Классификация ТН ВЭД — retrieval (LlamaIndex) + selection (DSPy)"""
    # Сигнатура: description + rag_results → {hs_code, name_ru, reasoning, confidence}
    # DSPy автоматически подбирает few-shot примеры

class RiskAnalyzer(dspy.Module):
    """Анализ рисков — правила СУР (LlamaIndex) + оценка (DSPy)"""
    # Сигнатура: declaration_data + relevant_rules → [RiskItem]

class ContractExtractor(dspy.Module):
    """Извлечение данных из контракта"""

class PackingExtractor(dspy.Module):
    """Извлечение данных из упаковочного листа"""
```

**Почему DSPy, а не ручные промпты:**

- При 3500+ кодах ТН ВЭД ручная подгонка промптов нереальна
- DSPy.BootstrapFewShot — автоматический подбор few-shot примеров
- DSPy.MIPRO — оптимизация промптов по метрике (accuracy кода ТН ВЭД)
- Промпты улучшаются автоматически при накоплении данных (self-learning)

**Новый файл: `services/ai-service/app/services/dspy_optimizer.py**`

```python
# Оптимизация промптов:
# 1. Собрать примеры из успешных деклараций (ml_feedback)
# 2. Запустить DSPy.BootstrapFewShot с метрикой: hs_code_match
# 3. Сохранить оптимизированный модуль
# Запускается: при накоплении 50+ новых примеров (Celery task)
```

- Создать `dspy_modules.py` с DSPy модулями
- Создать `dspy_optimizer.py` для авто-оптимизации
- Интегрировать с LlamaIndex (retrieval → DSPy selection)
- Тест: парсинг реальных PDF через DSPy модули

#### 2.4. CrewAI — мультиагентная оркестрация

**Новый файл: `services/ai-service/app/services/agent_crew.py**`

Заменяет: линейный pipeline в `smart_parser.py`

```python
# Вместо: PDF → parse → classify → risk (линейно)
# Теперь: команда автономных агентов с ролями

class DeclarationCrew:
    agents:
        DocumentParserAgent:
            role: "Таможенный документовед"
            tools: [DSPy InvoiceExtractor, ContractExtractor, PackingExtractor]
            goal: "Извлечь все данные из загруженных PDF"

        HSClassifierAgent:
            role: "Таможенный классификатор"
            tools: [LlamaIndex hs_query_engine, DSPy HSCodeClassifier]
            goal: "Подобрать точный 10-значный код ТН ВЭД с обоснованием"

        RiskAnalyzerAgent:
            role: "Инспектор СУР"
            tools: [LlamaIndex risk_query_engine, DSPy RiskAnalyzer]
            goal: "Оценить риски декларации и дать рекомендации"

        PrecedentLearnerAgent:
            role: "Аналитик прецедентов"
            tools: [LlamaIndex precedent_retriever]
            goal: "Найти похожие успешные декларации для подсказок"

    tasks:
        1. parse_documents → DocumentParserAgent
        2. classify_items → HSClassifierAgent (зависит от 1)
        3. find_precedents → PrecedentLearnerAgent (параллельно с 2)
        4. assess_risks → RiskAnalyzerAgent (зависит от 1, 2)
        5. compile_result → собрать всё в единый результат

    # CrewAI сам определяет порядок, параллелит независимые задачи,
    # передаёт контекст между агентами
```

**Почему CrewAI, а не линейный router:**

- Агенты работают параллельно (classify + precedents одновременно)
- Каждый агент может запросить доп. информацию у другого
- Встроенная память между запусками
- Логирование решений каждого агента (для Arize-Phoenix)
- Создать `agent_crew.py` с CrewAI
- Определить 4 агента + 5 задач
- Интегрировать инструменты (LlamaIndex + DSPy)
- Тест: мультизагрузка PDF → полный результат

#### 2.5. Arize-Phoenix — LLM Observability

**Новый файл: `services/ai-service/app/services/observability.py**`

```python
# Интеграция Phoenix для трейсинга:
# 1. Автоинструментация LlamaIndex (каждый retrieval + synthesis)
# 2. Автоинструментация DSPy (каждый вызов модуля)
# 3. Метрики: latency, token usage, retrieval relevance, hallucination score
# 4. UI: http://localhost:6006 — дашборд с трейсами
```

**Что даёт в проде:**

- Трейсинг каждого LLM вызова (input → output → latency → tokens)
- Оценка релевантности retrieval (правильные ли коды ТН ВЭД нашлись)
- Обнаружение галлюцинаций (LLM выдумал несуществующий код)
- A/B сравнение: regex vs LLM vs DSPy-optimized
- Настроить Phoenix в docker-compose
- Инструментировать LlamaIndex + DSPy
- Создать кастомные метрики (hs_code_accuracy, parse_completeness)

#### 2.6. Smart Parser Router (обновлённый)

**Обновлённый файл: `services/ai-service/app/routers/smart_parser.py**`

```
POST /api/v1/ai/parse-smart
  → CrewAI DeclarationCrew.kickoff(files=[...])
  → Возвращает: parsed_data + hs_suggestions + risks + precedents
  → Fallback: если CrewAI/OpenAI недоступен → regex pipeline

POST /api/v1/ai/classify-hs-rag
  → LlamaIndex hs_query_engine + DSPy HSCodeClassifier
  → Возвращает: top-3 кода с confidence + reasoning

POST /api/v1/ai/check-risks-rag
  → LlamaIndex risk_query_engine + DSPy RiskAnalyzer
  → Возвращает: risk_score + risks[] + recommendations[]
```

- Обновить `smart_parser.py` — интеграция с CrewAI
- Fallback на regex pipeline
- Обновить `ai-service/main.py`

#### 2.7. Frontend обновления

- `api/ai.ts` — `parseSmartDocument()`, `classifyHsRag()`, `checkRisksRag()`
- `DocumentUploadPanel.tsx` — мультизагрузка, прогресс, результат CrewAI
- HSCodeSuggestions — top-3 с confidence + reasoning (от DSPy)
- RiskPanel — risk_score + предупреждения + рекомендации
- PrecedentHints — "Похожие декларации" (от PrecedentLearnerAgent)

#### 2.8. Тестирование (Open-RAG-Eval)

**Open-RAG-Eval** — оценка RAG без golden answers:

- Не нужны заранее размеченные эталоны
- Оценивает: relevance, faithfulness, context utilization
- Идеально для проверки ТН ВЭД (3500 кодов, невозможно вручную проверить все)
- Настроить Open-RAG-Eval для hs_codes_index
- Настроить Open-RAG-Eval для risk_rules_index
- Тестирование на PDF из `dek/1 dek/`, `dek/2 dek/`, `dek/3 dek/`
- Сравнение: regex vs LlamaIndex+DSPy (метрики Phoenix)
- Проверка fallback: отключить OpenAI → regex работает

---

### ФАЗА 3: Интеграция ФТС — 4-6 недель

Без изменений от предыдущей версии плана.

#### 3.1. integration-service

- Структура `services/integration-service/`
- `xml_builder.py`, `xml_validator.py`
- `signature_service.py` (mock → КриптоПро)
- `customs_gateway.py` + `mock_gateway.py`
- `spot_service.py`

#### 3.2. Frontend

- Кнопка "Отправить в таможню"
- SPOTBlock, StatusTimeline, SignaturePanel

---

### ФАЗА 4: Платежи и мониторинг — 3-4 недели

Без изменений от предыдущей версии плана.

#### 4.1. calc-service

- `payment_calculator.py`, `cbr_client.py`, `currency_control_service.py`
- Seeds: тарифы, сборы 2026

#### 4.2. WebSocket + уведомления

- Redis pub/sub, WebSocket, `core.notifications`
- Frontend: NotificationsDropdown, StatusLiveIndicator, ExchangeRateWidget

#### 4.3. Frontend

- PaymentsBlock, CurrencyControlBlock

---

### ФАЗА 5: Compliance + Self-Learning (Cortex Memory) — 2-3 недели

**Обновлено:** Cortex Memory заменяет самописный precedent_store.py

#### 5.1. Cortex Memory — база прецедентов (production)

**Развертывание:**

```yaml
cortex:
  image: cortexmemory/cortex:latest
  ports: ["8080:8080"]
  volumes: [cortexdata:/data]
  environment:
    - EMBEDDING_MODEL=openai
    - OPENAI_API_KEY=${OPENAI_API_KEY}
```

**Интеграция с ai-service:**

```python
# При успешном выпуске декларации (status=released):
# 1. Cortex Memory автоматически извлекает ключевые факты
# 2. Сохраняет: description → hs_code, seller → country, items → weights
# 3. При следующей классификации: REST API поиск похожих прецедентов
# 4. Автоматическая оптимизация embeddings (self-improving)
```

**Почему Cortex Memory, а не самописный precedent_store.py:**

- Автоматическое извлечение фактов (не нужно вручную указывать что сохранять)
- REST API из коробки (не нужен кастомный код)
- Self-improving: автоматическая оптимизация поиска
- Insights dashboard: визуализация базы прецедентов
- Добавить Cortex Memory в docker-compose
- Интегрировать с ai-service (webhook при status=released)
- Заменить LlamaIndex precedent_retriever на Cortex Memory API
- Настроить автоизвлечение фактов из деклараций

#### 5.2. DSPy Auto-Retraining

**Замена ручного retraining на DSPy авто-оптимизацию:**

```python
# Celery periodic task (вместо train_hs_classifier.py):
@celery.task
def optimize_dspy_modules():
    """Запуск раз в месяц: DSPy оптимизирует промпты на новых данных"""
    
    # 1. Собрать feedback из ml_feedback (released, corrected, rejected)
    examples = load_training_examples()
    
    if len(examples) >= 50:
        # 2. DSPy.BootstrapFewShot оптимизирует HSCodeClassifier
        optimizer = BootstrapFewShot(metric=hs_code_accuracy)
        optimized_classifier = optimizer.compile(HSCodeClassifier(), trainset=examples)
        
        # 3. Сохранить оптимизированный модуль
        optimized_classifier.save(f"models/hs_classifier_v{version}")
        
        # 4. DSPy.MIPRO оптимизирует InvoiceExtractor
        # ...
```

- Настроить Celery task для DSPy авто-оптимизации
- ml_feedback таблица: сбор обратной связи
- Метрики: до/после оптимизации (через Phoenix)

#### 5.3. Backend (без изменений)

- knowledge_articles, checklists, checklist_results
- API: CRUD статей, чек-листов
- Диспетчеризация

#### 5.4. Frontend (без изменений)

- KnowledgeBasePage, ChecklistPanel, ContextualHelp
- DashboardPage, AdminPanel

---

## Архитектура AI-стека

```
                    ┌──────────────────────────────────────────────┐
                    │              Frontend (React)                │
                    │  DocumentUploadPanel → HSCodeSuggestions     │
                    │  RiskPanel → PrecedentHints                  │
                    └──────────────────┬───────────────────────────┘
                                       │
                    ┌──────────────────┴───────────────────────────┐
                    │              Nginx :80                       │
                    │  /api/v1/ai/* → ai-service                  │
                    └──────────────────┬───────────────────────────┘
                                       │
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                        ai-service :8003                                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    CrewAI DeclarationCrew                           │    │
│  │                                                                     │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐              │    │
│  │  │ DocumentParser│  │ HSClassifier │  │ RiskAnalyzer│              │    │
│  │  │   Agent       │  │   Agent      │  │   Agent     │              │    │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘              │    │
│  │         │                  │                  │                     │    │
│  │  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼──────┐              │    │
│  │  │ DSPy Modules │  │ DSPy Modules │  │ DSPy Modules│              │    │
│  │  │ Invoice/     │  │ HSCode       │  │ Risk        │              │    │
│  │  │ Contract/    │  │ Classifier   │  │ Analyzer    │              │    │
│  │  │ Packing      │  │              │  │             │              │    │
│  │  └──────────────┘  └──────┬───────┘  └──────┬──────┘              │    │
│  └───────────────────────────┼─────────────────┼─────────────────────┘    │
│                              │                  │                          │
│  ┌───────────────────────────▼──────────────────▼─────────────────────┐   │
│  │                    LlamaIndex (RAG ядро)                           │   │
│  │                                                                     │   │
│  │  hs_codes_index ──── hs_query_engine                               │   │
│  │  risk_rules_index ── risk_query_engine                             │   │
│  │  precedents_index ── precedent_retriever                           │   │
│  └───────────────────────────┬────────────────────────────────────────┘   │
│                              │                                            │
│  ┌───────────────────────────▼────────────────────────────────────────┐   │
│  │              Arize-Phoenix (Observability)                         │   │
│  │  Трейсинг каждого LLM вызова, retrieval relevance,                │   │
│  │  hallucination detection, A/B metrics                             │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────┐  Fallback: regex parsers (invoice/contract/packing)    │
│  │ OCR Service  │  При недоступности OpenAI/CrewAI                      │
│  │ (pdfplumber) │                                                        │
│  └──────────────┘                                                        │
└──────────────────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────────┐
    │ChromaDB │         │OpenAI   │         │Cortex Memory│
    │  :8100  │         │GPT-4o   │         │   :8080     │
    │hs_codes │         │         │         │ прецеденты  │
    │risk_rules│        │         │         │             │
    └─────────┘         └─────────┘         └─────────────┘
```

## Файловая структура ai-service (обновлённая)

```
services/ai-service/
├── app/
│   ├── main.py
│   ├── config.py                    # + OPENAI, CHROMADB, PHOENIX, CORTEX
│   ├── routers/
│   │   ├── parser.py                # Существующий (regex, fallback)
│   │   ├── classifier.py            # Существующий (keyword, fallback)
│   │   ├── risk.py                  # Существующий (rule engine, fallback)
│   │   └── smart_parser.py          # НОВЫЙ: CrewAI kickoff endpoint
│   ├── services/
│   │   ├── ocr_service.py           # Существующий
│   │   ├── invoice_parser.py        # Существующий (fallback)
│   │   ├── contract_parser.py       # Существующий (fallback)
│   │   ├── packing_parser.py        # Существующий (fallback)
│   │   ├── hs_classifier.py         # Существующий (fallback)
│   │   ├── risk_engine.py           # Существующий (fallback)
│   │   ├── price_analyzer.py        # Существующий (placeholder)
│   │   │
│   │   ├── index_manager.py         # НОВЫЙ: LlamaIndex RAG ядро
│   │   ├── dspy_modules.py          # НОВЫЙ: DSPy модули (5 экстракторов)
│   │   ├── dspy_optimizer.py        # НОВЫЙ: DSPy авто-оптимизация
│   │   ├── agent_crew.py            # НОВЫЙ: CrewAI мультиагенты
│   │   ├── observability.py         # НОВЫЙ: Arize-Phoenix интеграция
│   │   └── cortex_client.py         # НОВЫЙ: Cortex Memory REST клиент
│   ├── seeds/
│   │   └── init_indices.py          # НОВЫЙ: загрузка данных в LlamaIndex
│   ├── rules/
│   │   └── risk_rules.json          # Существующий (50+ правил)
│   └── utils/
│       └── text_processing.py       # Существующий
├── Dockerfile
└── requirements.txt                 # Обновлённый
```

## Timeline


| Фаза              | Срок          | Инструменты                       | Результат                                               |
| ----------------- | ------------- | --------------------------------- | ------------------------------------------------------- |
| 1. Завершение MVP | 1-2 нед       | —                                 | docker-compose up, auth, CRUD, справочники              |
| 2. RAG + LLM      | 4-5 нед       | LlamaIndex, DSPy, CrewAI, Phoenix | GPT-4o парсинг, RAG ТН ВЭД, мультиагенты, observability |
| 3. ФТС + ЭЦП      | 4-6 нед       | —                                 | XML, подпись, отправка, СПОТ                            |
| 4. Платежи        | 3-4 нед       | —                                 | Калькулятор, курсы ЦБ, валютный контроль                |
| 5. Compliance     | 2-3 нед       | Cortex Memory, DSPy retraining    | Прецеденты, база знаний, self-learning                  |
| **ИТОГО**         | **14-20 нед** |                                   | **~3.5-5 месяцев**                                      |


## Ключевые архитектурные решения

1. **LlamaIndex как RAG ядро** — единый стек вместо самописного vector_store + classifier + risk. Нативная поддержка ChromaDB, structured output, query engines
2. **DSPy вместо ручных промптов** — автоматическая оптимизация при 3500+ кодах ТН ВЭД. Self-improving при накоплении данных
3. **CrewAI вместо линейного pipeline** — параллельное выполнение (classify + precedents), агенты обмениваются контекстом
4. **Arize-Phoenix** — observability LLM в проде: трейсинг, hallucination detection, A/B тестирование regex vs LLM
5. **Cortex Memory** — production-ready хранилище прецедентов с REST API, самоулучшающийся поиск
6. **Open-RAG-Eval** — тестирование RAG без заранее размеченных эталонов
7. **Regex fallback** — все существующие парсеры сохранены, автопереключение при сбое OpenAI/CrewAI
8. **Mock-first** — ФТС, ЭЦП, СПОТ через mock, переключение через env

## Следующий шаг

**Начинаем с Фазы 1.1** — `.env.example`, `docker-compose up`, починка ошибок.