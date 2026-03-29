import type { Declaration, DeclarationStatus } from "./types";
import { STATUS_CONFIG } from "./types";
import { DeclarationCard } from "./DeclarationCard";
import { declarations } from "./mockData";

const COLUMNS: DeclarationStatus[] = ["NEW", "REQUIRES_ATTENTION", "READY_TO_SEND", "SENT"];

const COLUMN_ACCENTS: Record<DeclarationStatus, { headerBg: string; borderAccent: string; countBg: string; countText: string }> = {
  NEW: {
    headerBg: "bg-blue-50/60",
    borderAccent: "border-blue-200/40",
    countBg: "bg-blue-100/80",
    countText: "text-blue-700",
  },
  REQUIRES_ATTENTION: {
    headerBg: "bg-amber-50/60",
    borderAccent: "border-amber-200/40",
    countBg: "bg-amber-100/80",
    countText: "text-amber-700",
  },
  READY_TO_SEND: {
    headerBg: "bg-emerald-50/60",
    borderAccent: "border-emerald-200/40",
    countBg: "bg-emerald-100/80",
    countText: "text-emerald-700",
  },
  SENT: {
    headerBg: "bg-slate-50/80",
    borderAccent: "border-slate-200/40",
    countBg: "bg-slate-100",
    countText: "text-slate-500",
  },
};

function KanbanColumn({ status, items }: { status: DeclarationStatus; items: Declaration[] }) {
  const cfg = STATUS_CONFIG[status];
  const accent = COLUMN_ACCENTS[status];

  return (
    <div className="flex flex-col min-w-0 flex-1">
      {/* Column header */}
      <div className={`flex items-center justify-between px-3 py-2.5 rounded-[12px] ${accent.headerBg} border ${accent.borderAccent} mb-3`}>
        <div className="flex items-center gap-2">
          <div className={`w-[6px] h-[6px] rounded-full ${cfg.dot}`} />
          <span className="text-[12px] text-slate-700 tracking-[-0.01em]" style={{ fontWeight: 600 }}>{cfg.label}</span>
        </div>
        <span className={`text-[11px] px-2 py-0.5 rounded-md ${accent.countBg} ${accent.countText} tabular-nums`} style={{ fontWeight: 600 }}>
          {items.length}
        </span>
      </div>

      {/* Cards */}
      <div
        className="flex flex-col gap-2 flex-1 overflow-y-auto pr-0.5 scrollbar-thin"
        style={{ maxHeight: "calc(100vh - 230px)" }}
      >
        {items.map((d) => (
          <DeclarationCard key={d.id} declaration={d} />
        ))}
        {items.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mb-2">
              <span className="text-slate-300 text-[16px]">∅</span>
            </div>
            <span className="text-[11px] text-slate-400">Нет деклараций</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function KanbanBoard() {
  const grouped = COLUMNS.map((status) => ({
    status,
    items: declarations.filter((d) => d.status === status),
  }));

  return (
    <div className="grid grid-cols-4 gap-5">
      {grouped.map(({ status, items }) => (
        <KanbanColumn key={status} status={status} items={items} />
      ))}
    </div>
  );
}
