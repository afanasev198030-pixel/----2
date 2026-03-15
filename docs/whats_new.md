# What's New — LLM Parsing Pipeline v3

**Дата:** 2026-03-15
**Ветка:** `feature/llm-parsing-pipeline-v3`

## Обзор

Полный переход парсинга документов с архитектуры «эвристика + regex + LLM» на «LLM-only» с гибридной компиляцией. Один вызов LLM на документ вместо цепочки regex → LLM. Компиляция декларации: LLM для семантических решений + Python для арифметики и справочников.

## Новая архитектура

```
OCR → LLM (classify + extract) → LLM Compile → Python Post-Process → Validate → HS RAG + DSPy
```

**Было:**
- Эвристическая детекция типа документа (по имени файла и ключевым словам)
- Отдельный regex-парсер для каждого типа (invoice_parser, contract_parser, spec_parser...)
- LLM дополнял regex (заполнял пропущенные поля)
- Python-компиляция `_compile_declaration()` (~700 строк хардкода)
- LLM-компиляция `_compile_by_rules()` поверх Python-результата

**Стало:**
- LLM определяет тип документа (13 типов) и извлекает данные за один вызов
- Полный текст документа без обрезки (раньше truncation до 6000-16000 символов)
- LLM-компиляция заполняет все графы ДТ (1-54) по правилам
- Python post-process: только арифметика, справочники, нормализация

## Новые файлы

### `services/ai-service/app/services/llm_parser.py`
Единый LLM-парсер. Ключевые функции:
- `classify_and_extract(raw_text, filename)` — тип + извлечение за один LLM-вызов
- `classify_and_extract_debug()` — версия с полными промптами для debug-панели
- `_detect_doc_type_heuristic()` — fallback при недоступности LLM
- Поддержка 13 типов: invoice, contract, packing_list, specification, tech_description, transport_doc, transport_invoice, application_statement, payment_order, reference_gtd, svh_doc, origin_certificate, other

### `frontend/src/pages/AdminParseDebugPage.tsx`
Дебаг-панель в админке (полностью переписана). Визуализирует:
- OCR: метод, символы, страницы, полный текст
- LLM classify + extract: тип, уверенность, извлечённые данные, промпты, raw response, токены
- LLM-компиляция: заполненные поля, позиции
- Python post-process: таможенный пост, веса, листы, суммы
- Валидация: список проблем
- Evidence Map: источник и уверенность для каждого поля

## Изменённые файлы

### `services/ai-service/app/services/agent_crew.py`
- **Новые методы:**
  - `_compile_declaration_llm()` — LLM заполняет все графы ДТ по правилам из `declaration_ai_filling_rules.md`
  - `_post_process_compilation()` — Python: IATA lookup (гр.29/30), распределение весов (гр.35/38), суммирование, нормализация HS-кодов, агрегация страны (гр.16), расчёт листов (гр.3), формирование описания (гр.31)
  - `_distribute_weights()` — PL per-item matching + proportional by cost fallback
- **Обновлённые:** `process_documents()` — новый пайплайн через `classify_and_extract()`
- **Вынесены на уровень модуля:** `_DESTINATION_TO_POST`, `_AWB_PREFIX_TO_POST`, `_DEFAULT_POST`, `_normalize_hs_code()`
- **Legacy:** `_compile_declaration()`, `_compile_by_rules()` помечены как legacy, не вызываются

### `services/ai-service/app/routers/smart_parser.py`
- Эндпоинт `/parse-debug` переписан: этапы `classify_and_extract`, `llm_compile`, `post_process`, `validation`
- Убраны: `regex`, `batch_parse`, `merged`, `doc_type` (отдельный этап)

### `frontend/src/api/ai.ts`
- Новые интерфейсы: `ParseDebugClassifyExtract`, `ParseDebugLlmCompile`, `ParseDebugPostProcess`, `ParseDebugValidation`, `ParseDebugCompilation`
- Убраны: `ParseDebugRegexField`, `ParseDebugBatchParse`, `ParseDebugStageLlm`, `ParseDebugStageDocType`

### Прочие (из предыдущей сессии, ещё не закоммичены)
- `contract_parser.py` — добавлен `_smart_slice_contract()`, `parse_debug()`
- `invoice_parser.py` — добавлен `parse_debug()` с трейсом regex/LLM
- `ocr_service.py` — добавлена `extract_text_debug()`
- `App.tsx`, `AppLayout.tsx` — маршрут и меню дебаг-панели
- `apply_parsed.py` — мелкие правки обработки результатов
- `declaration_ai_filling_rules.md` — уточнения правил граф ДТ
