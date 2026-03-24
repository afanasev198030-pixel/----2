import { CheckCircle2, Send, AlertTriangle, FileSearch, ShieldCheck, FileText, FileCode, Sparkles, ClipboardList, Plus } from "lucide-react";
import { useNavigate } from "react-router";
import { useState } from "react";

export function HeroStatus() {
  const navigate = useNavigate();
  const [dtsCreated, setDtsCreated] = useState(() => localStorage.getItem("dtsCreated") === "true");

  const handleCreateDts = () => {
    localStorage.setItem("dtsCreated", "true");
    setDtsCreated(true);
    navigate("/dts");
  };
  return (
    <div className="relative overflow-hidden rounded-2xl border border-emerald-200/60 bg-gradient-to-br from-emerald-50/80 via-white to-emerald-50/40 p-6 shadow-sm">
      {/* Subtle decorative element */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-100/20 rounded-full -translate-y-1/2 translate-x-1/3 blur-3xl" />

      <div className="relative flex items-start justify-between">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-2xl bg-emerald-100/80 border border-emerald-200/60">
            <CheckCircle2 className="w-7 h-7 text-emerald-600" />
          </div>
          <div>
            <h2 className="text-[20px] text-slate-900 mb-1" style={{ fontWeight: 600 }}>Декларация готова к отправке</h2>
            <p className="text-[13px] text-slate-500 mb-4">Система завершила автозаполнение и валидацию. Обнаружено 2 рекомендации для проверки.</p>

            <div className="flex items-center gap-3 flex-wrap">
              <StatusPill icon={<CheckCircle2 className="w-3 h-3" />} text="Все обязательные поля заполнены" variant="success" />
              <StatusPill icon={<CheckCircle2 className="w-3 h-3" />} text="Комплект документов полный" variant="success" />
              <StatusPill icon={<CheckCircle2 className="w-3 h-3" />} text="XML валиден" variant="success" />
              <StatusPill icon={<CheckCircle2 className="w-3 h-3" />} text="PDF сформирован" variant="success" />
              <StatusPill icon={<CheckCircle2 className="w-3 h-3" />} text="Критических ошибок: 0" variant="success" />
              <StatusPill icon={<AlertTriangle className="w-3 h-3" />} text="Предупреждений: 2" variant="warning" />
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2 shrink-0 ml-6">
          <button className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 text-white text-[13px] hover:bg-emerald-700 transition-colors shadow-sm shadow-emerald-200" style={{ fontWeight: 500 }}>
            <Send className="w-4 h-4" />Подписать и отправить
          </button>
          <button onClick={() => navigate("/declaration")} className="flex items-center justify-center gap-2 px-5 py-2 rounded-xl border border-slate-200 text-slate-600 text-[12px] hover:bg-white/80 transition-colors bg-white/60">
            <FileSearch className="w-3.5 h-3.5" />Открыть декларацию
          </button>
          {dtsCreated ? (
            <button onClick={() => navigate("/dts")} className="flex items-center justify-center gap-2 px-5 py-2 rounded-xl border border-violet-200 text-violet-700 text-[12px] hover:bg-violet-50/80 transition-colors bg-violet-50/40">
              <ClipboardList className="w-3.5 h-3.5" />Открыть ДТС
            </button>
          ) : (
            <button onClick={handleCreateDts} className="flex items-center justify-center gap-2 px-5 py-2 rounded-xl border border-dashed border-slate-300 text-slate-500 text-[12px] hover:border-violet-300 hover:text-violet-600 hover:bg-violet-50/30 transition-colors bg-white/40">
              <Plus className="w-3.5 h-3.5" />Сформировать ДТС
            </button>
          )}
        </div>
      </div>

      {/* AI credit line */}
      <div className="mt-4 pt-3 border-t border-emerald-200/40 flex items-center gap-2 text-[11px] text-slate-400">
        <Sparkles className="w-3 h-3 text-violet-400" />
        <span>Автозаполнение: 148 полей обработано · 142 подтверждены автоматически · Время обработки: 12 сек</span>
      </div>
    </div>
  );
}

function StatusPill({ icon, text, variant }: { icon: React.ReactNode; text: string; variant: "success" | "warning" }) {
  const styles = variant === "success"
    ? "bg-emerald-50 border-emerald-200/60 text-emerald-700"
    : "bg-amber-50 border-amber-200 text-amber-700";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] ${styles}`}>
      {icon}{text}
    </span>
  );
}