import { useState } from "react";
import { Sparkles, CheckCircle2, Pencil, AlertTriangle, AlertCircle, GitBranch, PanelLeftClose, PanelLeftOpen } from "lucide-react";

const sections = [
  { id: "general", label: "Общие сведения", fields: 12, issues: 0 },
  { id: "parties", label: "Декларант / отправитель / получатель", fields: 8, issues: 0 },
  { id: "commercial", label: "Коммерческие данные", fields: 8, issues: 1 },
  { id: "transport", label: "Транспорт", fields: 6, issues: 0 },
  { id: "financial", label: "Финансовые сведения", fields: 10, issues: 0 },
  { id: "goods", label: "Товарные позиции", fields: 12, issues: 2 },
  { id: "docs", label: "Документы", fields: 5, issues: 0 },
  { id: "additional", label: "Дополнительные сведения", fields: 4, issues: 0 },
];

const filters = ["Все поля", "Проблемные", "Ручные", "AI", "Пустые"];

const legend = [
  { icon: <Sparkles className="w-2.5 h-2.5" />, label: "AI", color: "text-violet-500" },
  { icon: <CheckCircle2 className="w-2.5 h-2.5" />, label: "Подтверждено", color: "text-emerald-500" },
  { icon: <Pencil className="w-2.5 h-2.5" />, label: "Ручное", color: "text-blue-400" },
  { icon: <AlertTriangle className="w-2.5 h-2.5" />, label: "Предупреждение", color: "text-amber-500" },
  { icon: <AlertCircle className="w-2.5 h-2.5" />, label: "Ошибка", color: "text-red-500" },
  { icon: <GitBranch className="w-2.5 h-2.5" />, label: "Конфликт", color: "text-orange-500" },
];

interface Props {
  activeSection: string;
  onSectionChange: (id: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export function SectionNav({ activeSection, onSectionChange, collapsed, onToggleCollapse }: Props) {
  const [activeFilter, setActiveFilter] = useState("Все поля");

  const handleSectionClick = (id: string) => {
    onSectionChange(id);
    const el = document.getElementById(`section-${id}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  if (collapsed) {
    return null;
  }

  return (
    <aside className="w-[256px] min-w-[256px] bg-white border-r border-slate-200/80 flex flex-col h-full select-none">
      <div className="px-4 pt-4 pb-2 flex items-center justify-between">
        <h4 className="text-[12px] text-slate-400" style={{ fontWeight: 500 }}>НАВИГАЦИЯ</h4>
        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 transition-colors"
          title="Свернуть навигацию"
        >
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {/* Sections */}
      <div className="flex-1 overflow-y-auto px-3 space-y-0.5">
        {sections.map(s => {
          const active = activeSection === s.id;
          return (
            <button key={s.id} onClick={() => handleSectionClick(s.id)}
              className={`w-full text-left px-3 py-2 rounded-xl transition-all text-[12px] ${active ? "bg-slate-100 text-slate-900" : "text-slate-600 hover:bg-slate-50"}`}>
              <div className="flex items-center justify-between">
                <span style={{ fontWeight: active ? 500 : 400 }} className="leading-snug">{s.label}</span>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="text-[10px] text-slate-400">{s.fields}</span>
                  {s.issues > 0 && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-600" style={{ fontWeight: 500 }}>{s.issues}</span>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Filters */}
      <div className="px-4 py-3 border-t border-slate-100">
        <div className="text-[10px] text-slate-400 mb-2" style={{ fontWeight: 500 }}>ФИЛЬТРЫ</div>
        <div className="flex flex-wrap gap-1">
          {filters.map(f => (
            <button key={f} onClick={() => setActiveFilter(f)}
              className={`px-2 py-1 rounded-lg text-[10px] transition-colors ${activeFilter === f ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200"}`}>
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="px-4 py-3 border-t border-slate-100">
        <div className="text-[10px] text-slate-400 mb-2" style={{ fontWeight: 500 }}>ОБОЗНАЧЕНИЯ</div>
        <div className="grid grid-cols-2 gap-x-2 gap-y-1">
          {legend.map(l => (
            <div key={l.label} className={`flex items-center gap-1.5 text-[10px] ${l.color}`}>
              {l.icon}<span className="text-slate-500">{l.label}</span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}