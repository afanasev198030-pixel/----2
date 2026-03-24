import { CheckCircle2, AlertTriangle, ChevronRight, ShieldCheck } from "lucide-react";

const checks = [
  { text: "Все обязательные поля заполнены", ok: true },
  { text: "Комплект документов полный", ok: true },
  { text: "XML валиден", ok: true },
  { text: "Расчетные проверки пройдены", ok: true },
  { text: "Есть 2 предупреждения", ok: false },
];

export function ValidationSection() {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-emerald-50 border border-emerald-200/60">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
          </div>
          <div>
            <h3 className="text-[14px] text-slate-900" style={{ fontWeight: 600 }}>Автопроверка завершена</h3>
            <p className="text-[11px] text-slate-400">Все валидации пройдены. 2 рекомендации.</p>
          </div>
        </div>
        <button className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-600 transition-colors">
          Показать детали проверки<ChevronRight className="w-3 h-3" />
        </button>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        {checks.map((c, i) => (
          <span key={i} className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[11px] ${
            c.ok
              ? "bg-emerald-50/50 border-emerald-200/50 text-emerald-700"
              : "bg-amber-50 border-amber-200 text-amber-700"
          }`}>
            {c.ok
              ? <CheckCircle2 className="w-3 h-3" />
              : <AlertTriangle className="w-3 h-3" />
            }
            {c.text}
          </span>
        ))}
      </div>
    </div>
  );
}
