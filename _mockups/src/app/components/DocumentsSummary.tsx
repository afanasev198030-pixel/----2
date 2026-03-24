import { CheckCircle2, AlertTriangle, FileText, FolderOpen } from "lucide-react";

const docs = [
  { name: "Инвойс", status: "ok" as const },
  { name: "Контракт", status: "ok" as const },
  { name: "Упаковочный лист", status: "ok" as const },
  { name: "Транспортный документ", status: "ok" as const },
  { name: "Сертификат происхождения", status: "optional" as const },
];

export function DocumentsSummary() {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-[14px] text-slate-900" style={{ fontWeight: 600 }}>Документы</h3>
        <button className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-600 transition-colors">
          <FolderOpen className="w-3 h-3" />Открыть документы
        </button>
      </div>

      {/* Metrics */}
      <div className="flex items-center gap-5 mb-4">
        <MetricPill label="Загружено" value="5" />
        <MetricPill label="Обязательные" value="4/4" success />
        <MetricPill label="Дополнительные" value="1" />
        <MetricPill label="Проблемы качества" value="0" />
      </div>

      {/* Doc chips */}
      <div className="flex items-center gap-2 flex-wrap">
        {docs.map((d) => (
          <DocChip key={d.name} name={d.name} status={d.status} />
        ))}
      </div>
    </div>
  );
}

function MetricPill({ label, value, success }: { label: string; value: string; success?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[11px] text-slate-400">{label}:</span>
      <span className={`text-[12px] ${success ? "text-emerald-600" : "text-slate-700"}`} style={{ fontWeight: 500 }}>{value}</span>
    </div>
  );
}

function DocChip({ name, status }: { name: string; status: "ok" | "warning" | "missing" | "optional" }) {
  const config = {
    ok: { icon: <CheckCircle2 className="w-3 h-3 text-emerald-500" />, bg: "bg-emerald-50 border-emerald-200/60", text: "text-slate-700" },
    warning: { icon: <AlertTriangle className="w-3 h-3 text-amber-500" />, bg: "bg-amber-50 border-amber-200", text: "text-slate-700" },
    missing: { icon: <AlertTriangle className="w-3 h-3 text-red-500" />, bg: "bg-red-50 border-red-200", text: "text-red-700" },
    optional: { icon: <FileText className="w-3 h-3 text-slate-400" />, bg: "bg-slate-50 border-slate-200", text: "text-slate-500" },
  };
  const c = config[status];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-[11px] ${c.bg} ${c.text}`}>
      {c.icon}{name}
    </span>
  );
}
