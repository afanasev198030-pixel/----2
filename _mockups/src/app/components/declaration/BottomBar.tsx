import { CheckCircle2, AlertTriangle, Pencil, ShieldCheck, Send } from "lucide-react";

export function BottomBar() {
  return (
    <div className="sticky bottom-0 z-50 bg-white/95 backdrop-blur-sm border-t border-slate-200/80 px-5 py-2 flex items-center justify-between shrink-0" style={{ height: 46 }}>
      <div className="flex items-center gap-4">
        <Ind icon={<CheckCircle2 className="w-3 h-3" />} text="0 критических ошибок" color="text-emerald-600" bg="bg-emerald-50" />
        <Ind icon={<AlertTriangle className="w-3 h-3" />} text="2 предупреждения" color="text-amber-600" bg="bg-amber-50" />
        <Ind icon={<Pencil className="w-3 h-3" />} text="3 ручных изменения" color="text-blue-500" bg="bg-blue-50" />
      </div>
      <div className="flex items-center gap-1.5">
        <button className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-[11px] hover:bg-slate-50 bg-white transition-colors">
          <ShieldCheck className="w-3.5 h-3.5" />ЭЦП
        </button>
        <button className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 text-white text-[11px] hover:bg-emerald-700 transition-colors shadow-sm" style={{ fontWeight: 500 }}>
          <Send className="w-3.5 h-3.5" />Подписать и отправить
        </button>
      </div>
    </div>
  );
}

function Ind({ icon, text, color, bg }: { icon: React.ReactNode; text: string; color: string; bg: string }) {
  return (
    <div className={`flex items-center gap-1.5 text-[11px] ${color} px-2.5 py-1 rounded-lg ${bg}`}>
      {icon}{text}
    </div>
  );
}
