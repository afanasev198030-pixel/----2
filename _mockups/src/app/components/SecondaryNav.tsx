import { FileSearch, FolderOpen, History, ClipboardCheck, ChevronRight } from "lucide-react";
import { useNavigate } from "react-router";

const links = [
  { icon: <FileSearch className="w-4 h-4" />, label: "Открыть полную декларацию", desc: "148 полей · Режим просмотра" },
  { icon: <FolderOpen className="w-4 h-4" />, label: "Открыть документы", desc: "5 документов загружено" },
  { icon: <History className="w-4 h-4" />, label: "История изменений", desc: "12 событий сегодня" },
  { icon: <ClipboardCheck className="w-4 h-4" />, label: "Детали проверок", desc: "23 проверки пройдены" },
];

export function SecondaryNav() {
  const navigate = useNavigate();
  return (
    <div className="grid grid-cols-4 gap-3">
      {links.map((l) => (
        <button key={l.label} onClick={l.label === "Открыть полную декларацию" ? () => navigate("/declaration") : undefined} className="flex items-center gap-3 p-3.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 hover:border-slate-300 transition-all text-left group">
          <div className="p-2 rounded-lg bg-slate-50 text-slate-400 group-hover:text-slate-600 transition-colors">
            {l.icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[12px] text-slate-700" style={{ fontWeight: 500 }}>{l.label}</div>
            <div className="text-[11px] text-slate-400">{l.desc}</div>
          </div>
          <ChevronRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-400 transition-colors" />
        </button>
      ))}
    </div>
  );
}