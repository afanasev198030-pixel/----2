import { FileSearch, ExternalLink } from "lucide-react";

const summaryFields = [
  { label: "Тип процедуры", value: "ИМ 40" },
  { label: "Декларант", value: "ООО Альфа Импорт" },
  { label: "Отправитель", value: "Shanghai Industrial Co., Ltd" },
  { label: "Получатель", value: "ООО Альфа Импорт" },
  { label: "Инвойс", value: "INV-2026-101" },
  { label: "Контракт", value: "CTR-55/26" },
  { label: "Условия поставки", value: "FOB Shanghai" },
  { label: "Валюта", value: "USD" },
  { label: "Сумма", value: "12 540,00" },
  { label: "Товарных позиций", value: "12" },
  { label: "Вес брутто", value: "2 340 кг" },
  { label: "Страна отправления", value: "Китай" },
];

export function DeclarationSummary() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[14px] text-slate-900" style={{ fontWeight: 600 }}>Краткая сводка</h3>
        <button className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-600 transition-colors">
          <FileSearch className="w-3 h-3" />Открыть декларацию
        </button>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
        <div className="divide-y divide-slate-100">
          {summaryFields.map((f, i) => (
            <div key={i} className="flex items-center justify-between px-4 py-2.5 hover:bg-slate-50/50 transition-colors">
              <span className="text-[12px] text-slate-400">{f.label}</span>
              <span className="text-[12px] text-slate-800" style={{ fontWeight: 500 }}>{f.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
