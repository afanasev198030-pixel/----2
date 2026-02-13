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

| Сервис | Порт | Описание |
|--------|------|----------|
| **PostgreSQL** | 5432 | БД (39722 кода ТН ВЭД) |
| **Redis** | 6379 | Кеш курсов ЦБ |
| **MinIO** | 9000 | Файловое хранилище |
| **ChromaDB** | 8100 | Векторная БД (RAG) |
| **core-api** | 8001 | Ядро: декларации, auth, справочники |
| **file-service** | 8002 | Загрузка PDF файлов |
| **ai-service** | 8003 | AI: парсинг, ТН ВЭД, риски |
| **calc-service** | 8005 | Расчёт платежей, курсы ЦБ |
| **Nginx** | 80 | Reverse proxy |
| **Frontend** | 3000 | React SPA |

## AI стек

- **OpenAI GPT-4o** — парсинг PDF документов
- **LlamaIndex + ChromaDB** — RAG поиск по ТН ВЭД
- **DSPy** — авто-оптимизация промптов
- **CrewAI** — мультиагентная оркестрация
- **Regex fallback** — работает без OpenAI ключа

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
