import { AlertCircle, AlertTriangle, Info, Search, Keyboard, Eye, ArrowRightLeft, CheckCircle2, FileText, Pencil, RefreshCw } from "lucide-react";

export function IssuesPanel() {
  return (
    <div className="space-y-4">
      <h3 className="text-[14px] text-slate-900 flex items-center gap-2" style={{ fontWeight: 600 }}>
        Что требует внимания
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-600" style={{ fontWeight: 400 }}>4</span>
      </h3>

      {/* Blocking — currently none, show success message */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          <span className="text-[11px] text-slate-500" style={{ fontWeight: 500 }}>Блокирующие</span>
        </div>
        <div className="flex items-center gap-2.5 p-3 rounded-xl bg-emerald-50/50 border border-emerald-200/50 text-[12px] text-emerald-700">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>Критических проблем не обнаружено</span>
        </div>
      </div>

      {/* Review recommended */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <div className="w-1.5 h-1.5 rounded-full bg-amber-500" />
          <span className="text-[11px] text-slate-500" style={{ fontWeight: 500 }}>Рекомендуется проверить</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-600">2</span>
        </div>
        <div className="space-y-2">
          <IssueCard
            variant="warning"
            title="Товар 3 — низкая уверенность по коду ТН ВЭД"
            description='Код 8533 21 000 0 «Резисторы SMD» — AI уверен на 68%'
            actions={[
              { icon: <Eye className="w-3 h-3" />, label: "Посмотреть источник" },
              { icon: <ArrowRightLeft className="w-3 h-3" />, label: "Альтернатива" },
              { icon: <CheckCircle2 className="w-3 h-3" />, label: "Подтвердить", primary: true },
            ]}
          />
          <IssueCard
            variant="warning"
            title="Графа 22 — конфликт между инвойсом и контрактом"
            description="Инвойс: USD 12 540,00 · Контракт: USD 12 500,00"
            actions={[
              { icon: <Eye className="w-3 h-3" />, label: "Сравнить" },
              { icon: <ArrowRightLeft className="w-3 h-3" />, label: "Выбрать источник" },
            ]}
          />
        </div>
      </div>

      {/* Info */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <div className="w-1.5 h-1.5 rounded-full bg-slate-400" />
          <span className="text-[11px] text-slate-500" style={{ fontWeight: 500 }}>Информация</span>
        </div>
        <div className="space-y-1">
          <InfoRow icon={<Pencil className="w-3 h-3" />} text="5 полей были заполнены вручную" />
          <InfoRow icon={<RefreshCw className="w-3 h-3" />} text="Использована новая версия инвойса (v2)" />
          <InfoRow icon={<FileText className="w-3 h-3" />} text="Добавлен сертификат происхождения" />
        </div>
      </div>

      {/* DTS Issues */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <div className="w-1.5 h-1.5 rounded-full bg-violet-500" />
          <span className="text-[11px] text-slate-500" style={{ fontWeight: 500 }}>ДТС — Декларация таможенной стоимости</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-violet-50 border border-violet-200 text-violet-600">1</span>
        </div>
        <div className="space-y-2">
          <IssueCard
            variant="warning"
            title="ДТС — расхождение в структуре стоимости"
            description="Сумма компонентов таможенной стоимости (USD 13 240) не совпадает с итогом инвойса (USD 12 540)"
            actions={[
              { icon: <Eye className="w-3 h-3" />, label: "Открыть ДТС" },
              { icon: <ArrowRightLeft className="w-3 h-3" />, label: "Сверить источники" },
            ]}
          />
        </div>
      </div>
    </div>
  );
}

function IssueCard({ variant, title, description, actions }: {
  variant: "error" | "warning";
  title: string;
  description: string;
  actions: { icon: React.ReactNode; label: string; primary?: boolean }[];
}) {
  const border = variant === "error" ? "border-red-200" : "border-amber-200/70";
  const leftAccent = variant === "error" ? "bg-red-500" : "bg-amber-400";
  const iconBg = variant === "error" ? "bg-red-50" : "bg-amber-50";
  const iconColor = variant === "error" ? "text-red-500" : "text-amber-500";
  const Icon = variant === "error" ? AlertCircle : AlertTriangle;

  return (
    <div className={`relative rounded-xl border ${border} bg-white overflow-hidden`}>
      <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${leftAccent} rounded-l-xl`} />
      <div className="pl-4 pr-3 py-3">
        <div className="flex items-start gap-2.5">
          <div className={`p-1.5 rounded-lg ${iconBg} shrink-0 mt-0.5`}>
            <Icon className={`w-3.5 h-3.5 ${iconColor}`} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[12px] text-slate-800 mb-0.5" style={{ fontWeight: 500 }}>{title}</div>
            <div className="text-[11px] text-slate-400 mb-2.5">{description}</div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {actions.map((a, i) => (
                <button key={i}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] transition-colors ${a.primary
                    ? "bg-slate-900 text-white hover:bg-slate-800"
                    : "border border-slate-200 text-slate-600 hover:bg-slate-50 bg-white"
                  }`}>
                  {a.icon}{a.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-slate-50 text-[12px] text-slate-500 transition-colors cursor-default">
      <span className="text-slate-400">{icon}</span>
      {text}
    </div>
  );
}