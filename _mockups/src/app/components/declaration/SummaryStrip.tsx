import { CheckCircle2, AlertTriangle, Pencil, FileText, FileCode, ArrowRight } from "lucide-react";

export function SummaryStrip() {
  return (
    <div className="bg-white border-b border-slate-200/80 px-5 py-2 flex items-center justify-between" style={{ minHeight: 40 }}>
      <div className="flex items-center gap-4">
        <Metric icon={<CheckCircle2 className="w-3 h-3 text-emerald-500" />} label="Заполнено" value="148/148" />
        <Sep />
        <Metric icon={<AlertTriangle className="w-3 h-3 text-red-400" />} label="Ошибки" value="0" muted />
        <Metric icon={<AlertTriangle className="w-3 h-3 text-amber-500" />} label="Предупреждения" value="2" warn />
        <Metric icon={<Pencil className="w-3 h-3 text-blue-400" />} label="Ручные" value="3" />
        <Sep />
        <Metric icon={<FileText className="w-3 h-3 text-slate-400" />} label="Документы" value="5" />
        <Metric icon={<FileCode className="w-3 h-3 text-emerald-500" />} label="XML" value="Готов" success />
      </div>
      <button className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-[10px] hover:bg-amber-100 transition-colors">
        Следующее замечание<ArrowRight className="w-3 h-3" />
      </button>
    </div>
  );
}

function Metric({ icon, label, value, warn, muted, success }: { icon: React.ReactNode; label: string; value: string; warn?: boolean; muted?: boolean; success?: boolean }) {
  let valColor = "text-slate-800";
  if (warn) valColor = "text-amber-600";
  if (muted) valColor = "text-slate-400";
  if (success) valColor = "text-emerald-600";
  return (
    <div className="flex items-center gap-1.5 text-[11px]">
      {icon}
      <span className="text-slate-400">{label}</span>
      <span className={valColor} style={{ fontWeight: 500 }}>{value}</span>
    </div>
  );
}

function Sep() {
  return <div className="h-4 w-px bg-slate-200" />;
}
