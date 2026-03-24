import { BrokerHeader } from "../components/kanban/BrokerHeader";
import { KanbanBoard } from "../components/kanban/KanbanBoard";
import { FileText, AlertTriangle, CheckCircle2, Send, TrendingUp, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { declarations } from "../components/kanban/mockData";

function MetricCard({
  icon,
  label,
  value,
  accent,
  iconBg,
  trend,
  trendLabel,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  accent: string;
  iconBg: string;
  trend?: "up" | "down" | "neutral";
  trendLabel?: string;
}) {
  return (
    <div className={`relative overflow-hidden rounded-[14px] border bg-white p-4 transition-all hover:shadow-sm ${accent}`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[11px] text-slate-500 mb-1" style={{ fontWeight: 500 }}>{label}</div>
          <div className="text-[26px] text-slate-900 tabular-nums tracking-[-0.02em]" style={{ fontWeight: 700, lineHeight: 1.1 }}>{value}</div>
          {trendLabel && (
            <div className={`flex items-center gap-0.5 mt-1.5 text-[10px] ${
              trend === "up" ? "text-emerald-600" : trend === "down" ? "text-red-500" : "text-slate-400"
            }`} style={{ fontWeight: 500 }}>
              {trend === "up" && <ArrowUpRight className="w-3 h-3" />}
              {trend === "down" && <ArrowDownRight className="w-3 h-3" />}
              {trendLabel}
            </div>
          )}
        </div>
        <div className={`w-9 h-9 rounded-[10px] flex items-center justify-center ${iconBg}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const counts = {
    total: declarations.length,
    NEW: declarations.filter((d) => d.status === "NEW").length,
    REQUIRES_ATTENTION: declarations.filter((d) => d.status === "REQUIRES_ATTENTION").length,
    READY_TO_SEND: declarations.filter((d) => d.status === "READY_TO_SEND").length,
    SENT: declarations.filter((d) => d.status === "SENT").length,
  };

  return (
    <div className="h-screen w-full flex flex-col bg-[#f5f6f8] overflow-hidden" style={{ minWidth: 1280 }}>
      <BrokerHeader />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1440px] mx-auto px-6 pt-5 pb-6">
          {/* Page title + date */}
          <div className="flex items-end justify-between mb-5">
            <div>
              <h1 className="text-[20px] text-slate-900 tracking-[-0.02em]" style={{ fontWeight: 700 }}>Декларации</h1>
              <p className="text-[12px] text-slate-400 mt-0.5">Вторник, 24 марта 2026 · {counts.total} деклараций в работе</p>
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Обновлено только что
            </div>
          </div>

          {/* Metrics row */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <MetricCard
              icon={<FileText className="w-4 h-4 text-blue-600" />}
              label="Новые"
              value={counts.NEW}
              accent="border-blue-100/80"
              iconBg="bg-blue-50"
              trend="up"
              trendLabel="+2 сегодня"
            />
            <MetricCard
              icon={<AlertTriangle className="w-4 h-4 text-amber-600" />}
              label="Требуют внимания"
              value={counts.REQUIRES_ATTENTION}
              accent="border-amber-100/80"
              iconBg="bg-amber-50"
              trend="down"
              trendLabel="−1 за час"
            />
            <MetricCard
              icon={<CheckCircle2 className="w-4 h-4 text-emerald-600" />}
              label="Готово к отправке"
              value={counts.READY_TO_SEND}
              accent="border-emerald-100/80"
              iconBg="bg-emerald-50"
              trend="up"
              trendLabel="+1 за час"
            />
            <MetricCard
              icon={<Send className="w-4 h-4 text-slate-500" />}
              label="Отправлено"
              value={counts.SENT}
              accent="border-slate-200/60"
              iconBg="bg-slate-100"
              trend="neutral"
              trendLabel="3 за неделю"
            />
          </div>

          {/* Kanban */}
          <KanbanBoard />
        </div>
      </main>
    </div>
  );
}