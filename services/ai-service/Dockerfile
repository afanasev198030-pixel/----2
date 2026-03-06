# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl poppler-utils && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/ai-service/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --retries 10 --default-timeout=120 -r requirements.txt
COPY services/ai-service/app ./app
EXPOSE 8003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
