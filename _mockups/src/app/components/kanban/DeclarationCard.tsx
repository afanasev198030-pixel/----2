import { useNavigate } from "react-router";
import {
  AlertTriangle,
  Clock,
  Package,
  ShieldCheck,
  ShieldOff,
  Loader2,
  AlertCircle,
  Sparkles,
  FileQuestion,
  MessageSquare,
  Mail,
  PenLine,
  ChevronRight,
  MapPin,
} from "lucide-react";
import type { Declaration } from "./types";
import { PROCESSING_LABELS } from "./types";

function timeAgo(dateStr: string): string {
  const now = new Date("2026-03-24T15:00:00");
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `${diffMins} мин назад`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}ч назад`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}д назад`;
}

function ProcessingBadge({ status }: { status: Declaration["processingStatus"] }) {
  const config: Record<string, { icon: React.ReactNode; cls: string; border: string }> = {
    NOT_STARTED: {
      icon: <FileQuestion className="w-3 h-3" />,
      cls: "text-slate-500 bg-slate-50",
      border: "border-slate-200/80",
    },
    PROCESSING: {
      icon: <Loader2 className="w-3 h-3 animate-spin" />,
      cls: "text-blue-600 bg-blue-50/80",
      border: "border-blue-200/60",
    },
    AUTO_FILLED: {
      icon: <Sparkles className="w-3 h-3" />,
      cls: "text-violet-600 bg-violet-50/80",
      border: "border-violet-200/60",
    },
    PROCESSING_ERROR: {
      icon: <AlertCircle className="w-3 h-3" />,
      cls: "text-red-600 bg-red-50/80",
      border: "border-red-200/60",
    },
  };
  const c = config[status];
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-[3px] rounded-md text-[10px] border ${c.cls} ${c.border}`} style={{ fontWeight: 500 }}>
      {c.icon}
      {PROCESSING_LABELS[status]}
    </span>
  );
}

function SourceBadge({ source }: { source: Declaration["source"] }) {
  const config: Record<string, { icon: React.ReactNode; label: string }> = {
    telegram: { icon: <MessageSquare className="w-2.5 h-2.5" />, label: "TG" },
    email: { icon: <Mail className="w-2.5 h-2.5" />, label: "Email" },
    manual: { icon: <PenLine className="w-2.5 h-2.5" />, label: "Вручную" },
  };
  const c = config[source];
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-slate-400">
      {c.icon}
      {c.label}
    </span>
  );
}

export function DeclarationCard({ declaration }: { declaration: Declaration }) {
  const navigate = useNavigate();
  const d = declaration;
  const isNew = d.status === "NEW";
  const needsAttention = d.status === "REQUIRES_ATTENTION";
  const isSent = d.status === "SENT";

  return (
    <button
      onClick={() => navigate(`/dashboard/${d.id}`)}
      className={`
        group w-full text-left rounded-[14px] border transition-all duration-200 cursor-pointer relative
        ${isNew
          ? "bg-white border-blue-200/50 hover:border-blue-300/70 shadow-sm hover:shadow-md"
          : needsAttention
          ? "bg-white border-amber-200/50 hover:border-amber-300/70 shadow-sm hover:shadow-md"
          : isSent
          ? "bg-slate-50/80 border-slate-200/60 hover:border-slate-300/70 hover:bg-white hover:shadow-sm"
          : "bg-white border-slate-200/60 hover:border-slate-300/80 shadow-sm hover:shadow-md"
        }
      `}
    >
      {/* New indicator accent */}
      {isNew && (
        <div className="absolute left-0 top-3 bottom-3 w-[3px] rounded-r-full bg-blue-500" />
      )}
      {needsAttention && (
        <div className="absolute left-0 top-3 bottom-3 w-[3px] rounded-r-full bg-amber-400" />
      )}

      <div className="p-3.5">
        {/* Top row: ID + time */}
        <div className="flex items-center justify-between mb-1">
          <span className="text-[13px] text-slate-900 tracking-[-0.01em]" style={{ fontWeight: 600 }}>
            {d.id}
          </span>
          <span className="flex items-center gap-1 text-[10px] text-slate-400">
            <Clock className="w-2.5 h-2.5" />
            {timeAgo(d.updatedAt)}
          </span>
        </div>

        {/* Client + destination */}
        <div className="flex items-center gap-1.5 mb-2.5">
          <span className="text-[12px] text-slate-600">{d.clientName}</span>
          {d.destination && (
            <>
              <span className="text-slate-300">·</span>
              <span className="flex items-center gap-0.5 text-[10px] text-slate-400">
                <MapPin className="w-2.5 h-2.5" />
                {d.destination}
              </span>
            </>
          )}
        </div>

        {/* Badges row */}
        <div className="flex items-center gap-1.5 flex-wrap mb-2.5">
          <ProcessingBadge status={d.processingStatus} />
          {(d.status === "READY_TO_SEND" || d.status === "SENT") && (
            <span className={`inline-flex items-center gap-1 px-2 py-[3px] rounded-md text-[10px] border ${
              d.signatureStatus === "SIGNED"
                ? "text-emerald-600 bg-emerald-50/80 border-emerald-200/60"
                : "text-slate-400 bg-slate-50 border-slate-200/80"
            }`} style={{ fontWeight: 500 }}>
              {d.signatureStatus === "SIGNED" ? <ShieldCheck className="w-3 h-3" /> : <ShieldOff className="w-3 h-3" />}
              {d.signatureStatus === "SIGNED" ? "Подписана" : "Не подписана"}
            </span>
          )}
        </div>

        {/* Issues */}
        {d.issueCount > 0 && (
          <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-amber-50/80 border border-amber-200/40 text-[11px] text-amber-700 mb-2.5">
            <AlertTriangle className="w-3 h-3 shrink-0" />
            <span style={{ fontWeight: 500 }}>
              {d.issueCount} {d.issueCount === 1 ? "замечание" : d.issueCount < 5 ? "замечания" : "замечаний"}
            </span>
          </div>
        )}

        {/* Footer: meta */}
        <div className="flex items-center justify-between pt-2.5 border-t border-slate-100/80">
          <div className="flex items-center gap-2.5">
            {d.goodsCount > 0 && (
              <span className="flex items-center gap-1 text-[10px] text-slate-400">
                <Package className="w-3 h-3" />
                <span className="tabular-nums">{d.goodsCount} {d.goodsCount === 1 ? "товар" : d.goodsCount < 5 ? "товара" : "товаров"}</span>
              </span>
            )}
            {d.totalValue && (
              <span className="text-[11px] text-slate-500 tabular-nums" style={{ fontWeight: 500 }}>{d.totalValue}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <SourceBadge source={d.source} />
            <ChevronRight className="w-3.5 h-3.5 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>
      </div>
    </button>
  );
}
