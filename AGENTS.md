# Агенты в этом репозитории

В Cursor включён конвейер из правила `.cursor/rules/multi-agent-pipeline.mdc` (**alwaysApply**).

Ожидаемый режим: **Writer → Critic → Refiner** с секциями `## Writer` / `## Critic` / `## Refiner`.

Для облачных агентов и автоматизаций при необходимости продублируйте этот порядок в промпте задачи.
