# Система автоматизированного создания таможенных деклараций

AI-система для автозаполнения таможенных деклараций (ДТ) из PDF-документов.

## Быстрый старт (Docker)

```bash
# 1. Клонировать
git clone https://github.com/afanasev198030-pixel/----2.git
cd ----2

# 2. Настроить
cp .env.example .env
# Отредактировать .env — указать пароли и OpenAI ключ

# 3. Запустить (для production с bridge сетью)
cp infrastructure/nginx/nginx.prod.conf infrastructure/nginx/nginx.conf
docker-compose -f docker-compose.prod.yml up --build -d

# 4. Миграции + seeds
docker exec customs-core-api alembic upgrade head
docker exec customs-core-api python -m app.seeds.load
docker exec customs-core-api python -m app.seeds.load_tnved
docker exec customs-core-api python -m app.seeds.update_tnved_online

# 5. Открыть
# http://localhost:3000 — фронтенд
# Логин: admin@customs.local / admin123
# http://localhost:3000/settings — настройка OpenAI ключа
```

## Архитектура

**Актуальное описание архитектуры** находится в [`docs/architecture.md`](docs/architecture.md) (создано и обновлено 20 марта 2026 на основе анализа реального кода проекта).

**Кратко:**
- **core-api (8001)** — основной сервис (авторизация, CRUD деклараций, `apply_parsed`, `graph_rules`, админка)
- **ai-service (8003)** — AI-движок (`smart_parser`, RAG/ChromaDB, DSPy, rules engine) — **главный кандидат на рефакторинг**
- **file-service (8002)** — работа с файлами (MinIO + Gotenberg для PDF)
- **integration-service (8004)** — XML-экспорт
- **calc-service (8005)** — расчёты платежей и курсы ЦБ
- **bot-service** — Telegram-бот
- Nginx — единый reverse proxy со сквозным `X-Request-ID` для трассировки

## AI стек (актуально)

- **LLM:** DeepSeek (по умолчанию `deepseek-chat` / `deepseek-reasoner`), совместимость с OpenAI и Cloud.ru
- **RAG:** ChromaDB (коллекции `hs_codes`, `risk_rules`, `precedents`)
- **Structured output:** DSPy
- **OCR:** встроенный + Vision-модели (DeepSeek-OCR-2)
- **Правила:** `declaration_mapping_v3.yaml` + данные из БД + `docs/declaration_ai_filling_rules.md`

## Коды ТН ВЭД

39722 актуальных 10-значных кода из официального файла ФНС РФ.
Обновление: `python -m app.seeds.update_tnved_online`

## Обновление фронта на сервере (82.148.28.122)

### Вариант A: автоматически (рекомендуется)

Деплой идёт на сервер по SSH при каждом пуше в `main` (менялись `frontend/`, `docker-compose.prod.yml` или этот workflow).

1. **Один раз** в GitHub: репозиторий → Settings → Secrets and variables → Actions → New repository secret. Добавь:
   - `SSH_PRIVATE_KEY` — приватный ключ (содержимое файла без пароля или с паролем, если ключ с паролем — укажи его в `SSH_PASSPHRASE`).
   - `SERVER_HOST` — `82.148.28.122`.
   - `SERVER_USER` — пользователь SSH на сервере (например `root`).

2. На сервере репозиторий должен лежать в `/home/2/----2` (или отредактируй путь в `.github/workflows/deploy-frontend.yml`).

3. Дальше: пушишь в `main` → workflow «Deploy frontend to server» подтягивает код на сервер, пересобирает образ фронта и перезапускает контейнер. Открываешь http://82.148.28.122/ и делаешь **Ctrl+F5**.

Ручной запуск того же деплоя: Actions → Deploy frontend to server → Run workflow.

### Вариант B: вручную на сервере

Зайти по SSH на 82.148.28.122, затем:

```bash
cd /home/2/----2
git pull
./deploy-frontend.sh
```

Или без скрипта: `docker-compose -f docker-compose.prod.yml build frontend --no-cache && docker-compose -f docker-compose.prod.yml up -d frontend`.

Прод отдаёт собранный фронт (статика), а не dev-сервер.

## .env переменные

См. `.env.example` для полного списка.
