import { X, FileText, FileSpreadsheet, FileImage, FileCheck2, AlertTriangle, ExternalLink, Eye } from "lucide-react";

interface DocItem {
  id: string;
  name: string;
  type: "pdf" | "xlsx" | "image" | "xml" | "other";
  status: "ok" | "warning" | "missing";
  pages?: number;
  size: string;
  date: string;
}

const documents: DocItem[] = [
  { id: "d1", name: "Инвойс AG-ZED/2025/0029", type: "pdf", status: "ok", pages: 3, size: "245 КБ", date: "23.01.2025" },
  { id: "d2", name: "Упаковочный лист", type: "pdf", status: "ok", pages: 2, size: "182 КБ", date: "23.01.2025" },
  { id: "d3", name: "Контракт поставки №2673", type: "pdf", status: "ok", pages: 12, size: "1.4 МБ", date: "30.01.2025" },
  { id: "d4", name: "Коносамент MSKU-7284561", type: "pdf", status: "warning", pages: 1, size: "98 КБ", date: "15.01.2025" },
  { id: "d5", name: "Сертификат соответствия", type: "image", status: "ok", size: "3.2 МБ", date: "10.12.2024" },
  { id: "d6", name: "Платёжное поручение №1842", type: "pdf", status: "ok", pages: 1, size: "67 КБ", date: "25.01.2025" },
  { id: "d7", name: "Доверенность №26", type: "pdf", status: "ok", pages: 1, size: "156 КБ", date: "27.08.2025" },
  { id: "d8", name: "Прайс-лист производителя", type: "xlsx", status: "missing", size: "—", date: "—" },
  { id: "d9", name: "Фото маркировки товара", type: "image", status: "ok", size: "5.1 МБ", date: "18.01.2025" },
];

const typeIcon: Record<string, React.ReactNode> = {
  pdf: <FileText className="w-4 h-4" />,
  xlsx: <FileSpreadsheet className="w-4 h-4" />,
  image: <FileImage className="w-4 h-4" />,
  xml: <FileText className="w-4 h-4" />,
  other: <FileText className="w-4 h-4" />,
};

const statusConfig = {
  ok: { bg: "bg-emerald-50", text: "text-emerald-600", border: "border-emerald-200/60", icon: <FileCheck2 className="w-3 h-3 text-emerald-500" /> },
  warning: { bg: "bg-amber-50", text: "text-amber-600", border: "border-amber-200/60", icon: <AlertTriangle className="w-3 h-3 text-amber-500" /> },
  missing: { bg: "bg-red-50", text: "text-red-500", border: "border-red-200/60", icon: <AlertTriangle className="w-3 h-3 text-red-400" /> },
};

interface Props {
  onClose: () => void;
}

export function DocsSidebar({ onClose }: Props) {
  const okCount = documents.filter(d => d.status === "ok").length;
  const warnCount = documents.filter(d => d.status === "warning").length;
  const missCount = documents.filter(d => d.status === "missing").length;

  return (
    <div className="h-full flex flex-col bg-white border-r border-slate-200/80">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between shrink-0">
        <div>
          <h2 className="text-[13px] text-slate-800" style={{ fontWeight: 600 }}>Документы</h2>
          <div className="flex items-center gap-2.5 mt-1">
            <span className="text-[10px] text-emerald-600">{okCount} загружено</span>
            {warnCount > 0 && <span className="text-[10px] text-amber-600">{warnCount} внимание</span>}
            {missCount > 0 && <span className="text-[10px] text-red-500">{missCount} отсутствует</span>}
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-y-auto py-1.5">
        {documents.map(doc => {
          const sc = statusConfig[doc.status];
          return (
            <div
              key={doc.id}
              className={`mx-2 mb-1 px-3 py-2.5 rounded-xl border cursor-pointer transition-all duration-150 hover:shadow-[0_2px_8px_rgba(0,0,0,0.05)] group ${
                doc.status === "missing"
                  ? "bg-red-50/40 border-red-200/50"
                  : doc.status === "warning"
                    ? "bg-amber-50/30 border-amber-200/40"
                    : "bg-white border-slate-100 hover:border-slate-200"
              }`}
            >
              <div className="flex items-start gap-2.5">
                {/* Icon */}
                <div className={`mt-0.5 p-1.5 rounded-lg ${sc.bg} ${sc.text} shrink-0`}>
                  {typeIcon[doc.type]}
                </div>
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] text-slate-800 truncate" style={{ fontWeight: 500 }}>
                      {doc.name}
                    </span>
                    {sc.icon}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px] text-slate-400">{doc.size}</span>
                    {doc.pages && <span className="text-[10px] text-slate-400">{doc.pages} стр.</span>}
                    <span className="text-[10px] text-slate-400">{doc.date}</span>
                  </div>
                  {doc.status === "missing" && (
                    <span className="text-[10px] text-red-500 italic mt-0.5 block">Документ не загружен</span>
                  )}
                </div>
                {/* Actions */}
                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                  {doc.status !== "missing" && (
                    <button className="p-1 rounded-md hover:bg-slate-100 text-slate-400 transition-colors" title="Просмотр">
                      <Eye className="w-3 h-3" />
                    </button>
                  )}
                  <button className="p-1 rounded-md hover:bg-slate-100 text-slate-400 transition-colors" title="Открыть">
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="px-4 py-2.5 border-t border-slate-100 shrink-0">
        <button className="w-full text-center text-[11px] text-blue-600 hover:text-blue-700 py-1.5 rounded-lg hover:bg-blue-50/50 transition-colors" style={{ fontWeight: 500 }}>
          + Загрузить документ
        </button>
      </div>
    </div>
  );
}
