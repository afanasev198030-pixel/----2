import { Send, FileText, FileCode, FileSearch, AlertTriangle, ShieldCheck } from "lucide-react";

export function ReleaseActions() {
  return (
    <div className="rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-50 to-white p-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[14px] text-slate-900 mb-1" style={{ fontWeight: 600 }}>Выпуск декларации</h3>
          <p className="text-[12px] text-slate-400">Декларация прошла все проверки и готова к подписанию</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 text-slate-500 text-[12px] hover:bg-white transition-colors bg-white">
            <FileText className="w-3.5 h-3.5" />Скачать PDF
          </button>
          <button className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 text-slate-500 text-[12px] hover:bg-white transition-colors bg-white">
            <FileCode className="w-3.5 h-3.5" />Скачать XML
          </button>
          <button className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 text-slate-500 text-[12px] hover:bg-white transition-colors bg-white">
            <FileSearch className="w-3.5 h-3.5" />Декларация
          </button>
          <button className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 text-slate-500 text-[12px] hover:bg-white transition-colors bg-white">
            <AlertTriangle className="w-3.5 h-3.5" />Замечания
          </button>
          <div className="w-px h-8 bg-slate-200 mx-1" />
          <button className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 text-white text-[13px] hover:bg-emerald-700 transition-colors shadow-sm shadow-emerald-200" style={{ fontWeight: 500 }}>
            <ShieldCheck className="w-4 h-4" />Подписать и отправить
          </button>
        </div>
      </div>
    </div>
  );
}
