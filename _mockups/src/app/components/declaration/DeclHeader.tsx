import { ArrowLeft, FileText, FileCode, Clock, CheckCircle2, FolderOpen } from "lucide-react";
import { useNavigate } from "react-router";

interface Props {
  docsOpen: boolean;
  onToggleDocs: () => void;
}

export function DeclHeader({ docsOpen, onToggleDocs }: Props) {
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-slate-200/80 px-5 flex items-center justify-between" style={{ height: 52 }}>
      <div className="flex items-center gap-2.5">
        <button onClick={() => navigate("/")} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 transition-colors">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="h-5 w-px bg-slate-200" />
        <button
          onClick={onToggleDocs}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-[11px] transition-colors ${
            docsOpen
              ? "bg-blue-50 border-blue-200 text-blue-600"
              : "bg-white border-slate-200 text-slate-500 hover:bg-slate-50"
          }`}
          style={{ fontWeight: 500 }}
        >
          <FolderOpen className="w-3.5 h-3.5" />Документы
          <span className={`ml-0.5 px-1.5 py-0.5 rounded-full text-[9px] ${docsOpen ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-500"}`} style={{ fontWeight: 600 }}>9</span>
        </button>
        <div className="h-5 w-px bg-slate-200" />
        <div className="flex items-center gap-2">
          <span className="text-[13px] text-slate-900" style={{ fontWeight: 600 }}>Полная декларация</span>
          <span className="text-[11px] text-slate-400">DC-2026-001245</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200/70 text-emerald-700 text-[11px]" style={{ fontWeight: 500 }}>
          <CheckCircle2 className="w-3 h-3" />Готово к отправке
        </span>
        <span className="text-[11px] text-slate-400 flex items-center gap-1"><Clock className="w-3 h-3" />14:22</span>
      </div>

      <div className="flex items-center gap-1.5">
        <button className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-[11px] hover:bg-slate-50 transition-colors bg-white">
          <FileText className="w-3.5 h-3.5" />PDF
        </button>
        <button className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-[11px] hover:bg-slate-50 transition-colors bg-white">
          <FileCode className="w-3.5 h-3.5" />XML
        </button>
      </div>
    </header>
  );
}