import { ArrowLeft, FileText, FileCode, ShieldCheck, Send, Clock, CheckCircle2 } from "lucide-react";
import { useNavigate } from "react-router";

export function TopHeader() {
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-slate-200/80 px-6 py-2.5 flex items-center justify-between" style={{ minHeight: 56 }}>
      <div className="flex items-center gap-3">
        <button onClick={() => navigate("/")} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 transition-colors">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="h-5 w-px bg-slate-200" />
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[13px] text-slate-900" style={{ fontWeight: 600 }}>DC-2026-001245</span>
            <span className="text-[11px] text-slate-400">·</span>
            <span className="text-[12px] text-slate-500">ООО Альфа Импорт</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <Clock className="w-3 h-3" />
            <span>Обновлено сегодня в 14:22</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-[11px]" style={{ fontWeight: 500 }}>
          <CheckCircle2 className="w-3.5 h-3.5" />
          Готово к отправке
        </span>
      </div>

      <div className="flex items-center gap-1.5">
        <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-[12px] hover:bg-slate-50 transition-colors bg-white">
          <FileText className="w-3.5 h-3.5" />PDF
        </button>
        <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-[12px] hover:bg-slate-50 transition-colors bg-white">
          <FileCode className="w-3.5 h-3.5" />XML
        </button>
        <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-[12px] hover:bg-slate-50 transition-colors bg-white">
          <ShieldCheck className="w-3.5 h-3.5" />Подписать ЭЦП
        </button>
        <button className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 text-white text-[12px] hover:bg-emerald-700 transition-colors shadow-sm" style={{ fontWeight: 500 }}>
          <Send className="w-3.5 h-3.5" />Подписать и отправить
        </button>
      </div>
    </header>
  );
}