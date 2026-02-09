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

## .env переменные

См. `.env.example` для полного списка.
