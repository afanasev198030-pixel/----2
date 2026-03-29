import { Eye, Pencil, History, Sparkles, AlertTriangle, AlertCircle, GitBranch, Search, Keyboard } from "lucide-react";

export type FieldState = "ai" | "confirmed" | "review" | "conflict" | "manual" | "empty";

interface FieldRowProps {
  label: string;
  value: string;
  state: FieldState;
  source?: string;
  confidence?: number;
  selected?: boolean;
  onClick?: () => void;
}

const stateConfig: Record<FieldState, {
  accent: string;
  badge: { icon: React.ReactNode; label: string; cls: string } | null;
}> = {
  ai: {
    accent: "border-l-violet-300",
    badge: { icon: <Sparkles className="w-2.5 h-2.5" />, label: "AI", cls: "bg-violet-50 border-violet-200 text-violet-600" },
  },
  confirmed: {
    accent: "border-l-emerald-400",
    badge: null,
  },
  review: {
    accent: "border-l-amber-400",
    badge: { icon: <AlertTriangle className="w-2.5 h-2.5" />, label: "Требует проверки", cls: "bg-amber-50 border-amber-200 text-amber-600" },
  },
  conflict: {
    accent: "border-l-orange-400",
    badge: { icon: <GitBranch className="w-2.5 h-2.5" />, label: "Конфликт", cls: "bg-orange-50 border-orange-200 text-orange-600" },
  },
  manual: {
    accent: "border-l-blue-300",
    badge: { icon: <Pencil className="w-2.5 h-2.5" />, label: "Вручную", cls: "bg-blue-50 border-blue-200 text-blue-600" },
  },
  empty: {
    accent: "border-l-red-400",
    badge: { icon: <AlertCircle className="w-2.5 h-2.5" />, label: "Пусто · Обязательное", cls: "bg-red-50 border-red-200 text-red-600" },
  },
};

export function FieldRow({ label, value, state, source, confidence, selected, onClick }: FieldRowProps) {
  const cfg = stateConfig[state];
  const bgClass = state === "review" ? "bg-amber-50/20" : state === "conflict" ? "bg-orange-50/20" : state === "empty" ? "bg-red-50/20" : "bg-white";

  return (
    <div onClick={onClick}
      className={`group flex items-start border-l-[3px] ${cfg.accent} rounded-r-xl border border-l-0 border-slate-200/70 ${bgClass} cursor-pointer transition-all hover:shadow-sm ${selected ? "ring-1 ring-slate-300 shadow-sm" : ""}`}
      style={{ borderLeftStyle: "solid" }}>
      <div className="flex-1 min-w-0 px-4 py-2.5">
        <div className="text-[11px] text-slate-400 mb-0.5">{label}</div>
        {state === "empty" ? (
          <div>
            <div className="text-[13px] text-slate-300 italic mb-1.5">—</div>
            <div className="flex items-center gap-1.5 mb-1.5">
              {cfg.badge && (
                <span className={`inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full border ${cfg.badge.cls}`}>
                  {cfg.badge.icon}{cfg.badge.label}
                </span>
              )}
            </div>
            <div className="text-[10px] text-slate-400 mb-2">Значение не найдено в текущем комплекте документов</div>
            <div className="flex gap-1.5">
              <button className="flex items-center gap-1 px-2 py-1 rounded-lg border border-slate-200 text-[10px] text-slate-600 hover:bg-slate-50 bg-white">
                <Search className="w-2.5 h-2.5" />Найти
              </button>
              <button className="flex items-center gap-1 px-2 py-1 rounded-lg border border-slate-200 text-[10px] text-slate-600 hover:bg-slate-50 bg-white">
                <Keyboard className="w-2.5 h-2.5" />Ввести вручную
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="text-[13px] text-slate-900 mb-1" style={{ fontWeight: 500 }}>{value}</div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {cfg.badge && (
                <span className={`inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full border ${cfg.badge.cls}`}>
                  {cfg.badge.icon}{cfg.badge.label}
                </span>
              )}
              {state === "ai" || state === "confirmed" ? (
                <span className="inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full border bg-violet-50 border-violet-200 text-violet-500">
                  <Sparkles className="w-2.5 h-2.5" />AI
                </span>
              ) : null}
              {source && <span className="text-[10px] text-slate-400">{source}</span>}
              {confidence != null && (
                <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${confidence >= 90 ? "bg-emerald-50 border-emerald-200 text-emerald-600" : confidence >= 75 ? "bg-amber-50 border-amber-200 text-amber-600" : "bg-red-50 border-red-200 text-red-600"}`}>
                  {confidence}%
                </span>
              )}
            </div>
          </>
        )}
      </div>
      <div className="flex items-center gap-0.5 px-2 py-2.5 opacity-0 group-hover:opacity-100 transition-opacity">
        <button className="p-1 rounded-lg hover:bg-slate-100 text-slate-400"><Eye className="w-3.5 h-3.5" /></button>
        <button className="p-1 rounded-lg hover:bg-slate-100 text-slate-400"><Pencil className="w-3.5 h-3.5" /></button>
        <button className="p-1 rounded-lg hover:bg-slate-100 text-slate-400"><History className="w-3.5 h-3.5" /></button>
      </div>
    </div>
  );
}
