import type { FieldState } from "./FieldRow";

export interface FieldInfo {
  id: string;
  label: string;
  value: string;
  state: FieldState;
  source?: string;
  confidence?: number;
  section: string;
  mainSource?: { file: string; docType: string; page?: string; detail?: string };
  alternatives?: { id: string; doc: string; docType: string; value: string; diff?: boolean; recommended?: boolean }[];
  reasons?: { text: string; ok: boolean }[];
  history?: { time: string; text: string; detail?: string; dot: string; actor: string | null }[];
}

export const fieldsData: Record<string, FieldInfo> = {
  f1: {
    id: "f1", label: "Графа 1. Тип декларации", value: "ИМ 40", state: "confirmed",
    section: "Общие сведения",
    mainSource: { file: "contract_2026.pdf", docType: "Контракт", page: "Страница 1" },
    confidence: 98,
    reasons: [
      { text: "Тип операции определён по условиям контракта", ok: true },
      { text: "Соответствует коду таможенной процедуры", ok: true },
    ],
    history: [
      { time: "14:05", text: "AI заполнил значение", detail: "Извлечено из contract_2026.pdf", dot: "bg-violet-400", actor: null },
      { time: "14:12", text: "Автоматически подтверждено", detail: "Высокая уверенность, нет конфликтов", dot: "bg-emerald-400", actor: null },
    ],
  },
  f2: {
    id: "f2", label: "Графа 2. Отправитель", value: "Shanghai Electronics Co., Ltd", state: "ai",
    section: "Общие сведения",
    mainSource: { file: "invoice_01.pdf", docType: "Инвойс", page: "Страница 1", detail: "Заголовок документа" },
    confidence: 96,
    alternatives: [
      { id: "a1", doc: "contract_2026.pdf", docType: "Контракт", value: "Shanghai Electronics Co., Ltd", recommended: true },
    ],
    reasons: [
      { text: "Наименование совпадает в инвойсе и контракте", ok: true },
      { text: "Формат соответствует справочнику контрагентов", ok: true },
    ],
    history: [
      { time: "14:06", text: "AI заполнил значение", detail: "Извлечено из invoice_01.pdf", dot: "bg-violet-400", actor: null },
    ],
  },
  f8: {
    id: "f8", label: "Графа 8. Получатель", value: 'ООО "Альфа Импорт"', state: "confirmed",
    section: "Общие сведения",
    mainSource: { file: "contract_2026.pdf", docType: "Контракт", page: "Страница 1" },
    confidence: 99,
    reasons: [
      { text: "Получатель указан в контракте", ok: true },
      { text: "ИНН подтверждён по базе ФНС", ok: true },
    ],
    history: [
      { time: "14:05", text: "AI заполнил значение", detail: "Извлечено из contract_2026.pdf", dot: "bg-violet-400", actor: null },
      { time: "14:12", text: "Автоматически подтверждено", detail: "Совпадение с профилем клиента", dot: "bg-emerald-400", actor: null },
    ],
  },
  f15: {
    id: "f15", label: "Графа 15. Страна отправления", value: "Китай", state: "review",
    section: "Общие сведения",
    mainSource: { file: "invoice_01.pdf", docType: "Инвойс", page: "Страница 1" },
    confidence: 76,
    alternatives: [
      { id: "a1", doc: "packing_list.pdf", docType: "Упаковочный лист", value: "Китай", recommended: true },
      { id: "a2", doc: "bl_2026.pdf", docType: "Коносамент", value: "Гонконг", diff: true },
    ],
    reasons: [
      { text: "Страна указана в инвойсе", ok: true },
      { text: "Коносамент указывает порт отправления Гонконг", ok: false },
      { text: "Низкая уверенность — рекомендуется проверка", ok: false },
    ],
    history: [
      { time: "14:06", text: "AI заполнил значение", detail: "Извлечено из invoice_01.pdf", dot: "bg-violet-400", actor: null },
      { time: "14:10", text: "Отмечено для проверки", detail: "Уверенность ниже порога (76%)", dot: "bg-amber-400", actor: null },
    ],
  },
  fc4: {
    id: "fc4", label: "Графа 22. Валюта и сумма по счету", value: "USD 12 540,00", state: "conflict",
    section: "Коммерческие данные",
    mainSource: { file: "invoice_01.pdf", docType: "Инвойс", page: "Страница 1", detail: "Таблица итогов" },
    confidence: 92,
    alternatives: [
      { id: "contract", doc: "contract_2026.pdf", docType: "Контракт", value: "USD 12 500,00", diff: true },
      { id: "proforma", doc: "proforma_01.pdf", docType: "Проформа", value: "USD 12 540,00", recommended: true },
      { id: "history", doc: "История клиента", docType: "Историческое значение", value: "USD 12 540,00" },
    ],
    reasons: [
      { text: "Найдено точное совпадение в итоговом блоке инвойса", ok: true },
      { text: "Значение соответствует валюте документа", ok: true },
      { text: "Формат совпадает с ожидаемым для поля", ok: true },
      { text: "Обнаружен альтернативный источник с расхождением", ok: false },
    ],
    history: [
      { time: "14:10", text: "AI заполнил значение", detail: "Извлечено из invoice_01.pdf, страница 1", dot: "bg-violet-400", actor: null },
      { time: "14:15", text: "Обнаружен конфликт источников", detail: "contract_2026.pdf содержит отличающееся значение", dot: "bg-orange-400", actor: null },
      { time: "14:18", text: "Пользователь открыл источник", detail: "Просмотрен invoice_01.pdf", dot: "bg-slate-300", actor: "Иванов А.В." },
      { time: "14:20", text: "Пользователь просмотрел альтернативы", detail: "Сравнение 3 источников", dot: "bg-slate-300", actor: "Иванов А.В." },
    ],
  },
  fc5: {
    id: "fc5", label: "Графа 24. Характер сделки", value: "010", state: "manual",
    section: "Коммерческие данные",
    mainSource: { file: "contract_2026.pdf", docType: "Контракт", page: "Страница 2" },
    reasons: [
      { text: "Код сделки определён по условиям контракта", ok: true },
      { text: "Изменено вручную пользователем", ok: true },
    ],
    history: [
      { time: "14:08", text: "AI заполнил значение", detail: "Предложено: 011", dot: "bg-violet-400", actor: null },
      { time: "14:19", text: "Значение изменено вручную", detail: "Изменено на 010 — ошибка в классификации", dot: "bg-blue-400", actor: "Иванов А.В." },
    ],
  },
  fc8: {
    id: "fc8", label: "Графа 20. Условия поставки", value: "", state: "empty",
    section: "Коммерческие данные",
    reasons: [
      { text: "Значение не найдено ни в одном документе", ok: false },
      { text: "Поле является обязательным для данной процедуры", ok: false },
    ],
    history: [
      { time: "14:10", text: "AI не нашёл значение", detail: "Просмотрены все документы комплекта", dot: "bg-red-400", actor: null },
    ],
  },
  fd3: {
    id: "fd3", label: "Получатель", value: 'ООО "Альфа Импорт"', state: "manual",
    section: "Декларант / отправитель / получатель",
    mainSource: { file: "contract_2026.pdf", docType: "Контракт", page: "Страница 1" },
    reasons: [
      { text: "Получатель подтверждён по контракту", ok: true },
      { text: "Изменено вручную пользователем", ok: true },
    ],
    history: [
      { time: "14:06", text: "AI заполнил значение", detail: "Извлечено из контракта", dot: "bg-violet-400", actor: null },
      { time: "14:17", text: "Пользователь изменил значение", detail: "Уточнение наименования", dot: "bg-blue-400", actor: "Иванов А.В." },
    ],
  },
  g2: {
    id: "g2", label: "Позиция 2. Конденсаторы керамические", value: "8532 24 000 0 · 10 000 шт · USD 2 840,00", state: "review",
    section: "Товарные позиции",
    mainSource: { file: "invoice_01.pdf", docType: "Инвойс", page: "Страница 2", detail: "Таблица товаров, строка 2" },
    confidence: 82,
    alternatives: [
      { id: "a1", doc: "packing_list.pdf", docType: "Упаковочный лист", value: "10 000 шт · 85,3 кг", recommended: true },
    ],
    reasons: [
      { text: "Код ТН ВЭД подтверждён по описанию товара", ok: true },
      { text: "Количество совпадает с упаковочным листом", ok: true },
      { text: "Рекомендуется проверить классификацию", ok: false },
    ],
    history: [
      { time: "14:08", text: "AI заполнил позицию", detail: "Извлечено из invoice_01.pdf", dot: "bg-violet-400", actor: null },
      { time: "14:11", text: "Отмечено для проверки", detail: "Классификация требует подтверждения", dot: "bg-amber-400", actor: null },
    ],
  },
  g3: {
    id: "g3", label: "Позиция 3. Резисторы SMD", value: "8533 21 000 0 · 20 000 шт · USD 1 500,00", state: "conflict",
    section: "Товарные позиции",
    mainSource: { file: "invoice_01.pdf", docType: "Инвойс", page: "Страница 2", detail: "Таблица товаров, строка 3" },
    confidence: 78,
    alternatives: [
      { id: "a1", doc: "packing_list.pdf", docType: "Упаковочный лист", value: "20 000 шт · 42,1 кг" },
      { id: "a2", doc: "contract_2026.pdf", docType: "Контракт", value: "USD 1 450,00", diff: true },
    ],
    reasons: [
      { text: "Описание товара совпадает с инвойсом", ok: true },
      { text: "Стоимость в контракте отличается на $50", ok: false },
    ],
    history: [
      { time: "14:08", text: "AI заполнил позицию", detail: "Извлечено из invoice_01.pdf", dot: "bg-violet-400", actor: null },
      { time: "14:14", text: "Обнаружен конфликт стоимости", detail: "Контракт: USD 1 450 vs Инвойс: USD 1 500", dot: "bg-orange-400", actor: null },
    ],
  },
};

// Default fallback for fields without detailed data
export function getFieldInfo(fieldId: string): FieldInfo | null {
  if (fieldsData[fieldId]) return fieldsData[fieldId];
  // Return null for unknown fields – the printed form cell click won't open drawer
  return null;
}