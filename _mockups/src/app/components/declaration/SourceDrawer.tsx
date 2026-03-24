import React, { useState, useEffect } from "react";
import {
  X, Check, Pencil, FileText, Sparkles, Clock,
  ChevronRight, GitBranch, ExternalLink, ZoomIn, ZoomOut, RotateCcw,
  AlertTriangle, Info, FileUp, Shield, ChevronDown, AlertCircle,
  FileSpreadsheet, FileImage, ChevronLeft, ArrowRight
} from "lucide-react";
import type { FieldInfo } from "./fieldData";

type DrawerTab = "overview" | "source";

interface ExtractedField {
  id: string;
  label: string;
  value: string;
  confidence: number;
  page?: string;
}

interface SourceDoc {
  id: string;
  name: string;
  type: "pdf" | "xlsx" | "image";
  extractedFields: ExtractedField[];
}

const sourceDocuments: SourceDoc[] = [
  {
    id: "sd1", name: "Инвойс AG-ZED/2025/0029", type: "pdf",
    extractedFields: [
      { id: "e1", label: "Сумма по счёту", value: "RUB 9 058 816.00", confidence: 97, page: "Стр. 1" },
      { id: "e2", label: "Валюта", value: "RUB", confidence: 99, page: "Стр. 1" },
      { id: "e3", label: "Отправитель", value: "HK SAN GENSHIN INDUSTRY CO., LIMITED", confidence: 96, page: "Стр. 1" },
      { id: "e4", label: "Условия поставки", value: "EXW BEIJING", confidence: 88, page: "Стр. 1" },
      { id: "e5", label: "Дата инвойса", value: "23.01.2025", confidence: 99, page: "Стр. 1" },
    ],
  },
  {
    id: "sd2", name: "Контракт поставки №2673", type: "pdf",
    extractedFields: [
      { id: "e6", label: "Сумма контракта", value: "RUB 9 100 000.00", confidence: 94, page: "Стр. 3" },
      { id: "e7", label: "Характер сделки", value: "010", confidence: 91, page: "Стр. 2" },
      { id: "e8", label: "Получатель", value: "ООО \"АГ-ЛОГИСТИК\"", confidence: 98, page: "Стр. 1" },
      { id: "e9", label: "Условия поставки", value: "FOB SHANGHAI", confidence: 85, page: "Стр. 2" },
    ],
  },
  {
    id: "sd3", name: "Упаковочный лист", type: "pdf",
    extractedFields: [
      { id: "e10", label: "Вес брутто", value: "20.030 кг", confidence: 99, page: "Стр. 1" },
      { id: "e11", label: "Вес нетто", value: "19.030 кг", confidence: 99, page: "Стр. 1" },
      { id: "e12", label: "Кол-во мест", value: "9", confidence: 97, page: "Стр. 1" },
      { id: "e13", label: "Страна отправления", value: "КИТАЙ", confidence: 95, page: "Стр. 1" },
    ],
  },
  {
    id: "sd4", name: "Коносамент MSKU-7284561", type: "pdf",
    extractedFields: [
      { id: "e14", label: "Порт погрузки", value: "SHANGHAI, CHINA", confidence: 96, page: "Стр. 1" },
      { id: "e15", label: "Порт выгрузки", value: "VLADIVOSTOK, RUSSIA", confidence: 96, page: "Стр. 1" },
      { id: "e16", label: "Страна отправления", value: "ГОНКОНГ", confidence: 78, page: "Стр. 1" },
    ],
  },
  {
    id: "sd5", name: "Прайс-лист производителя", type: "xlsx",
    extractedFields: [
      { id: "e17", label: "Цена за единицу", value: "RUB 1 044.00", confidence: 92, page: "Лист 1" },
      { id: "e18", label: "Кол-во позиций", value: "1600 шт", confidence: 94, page: "Лист 1" },
    ],
  },
];

const docTypeIcon: Record<string, React.ReactNode> = {
  pdf: <FileText className="w-4 h-4" />,
  xlsx: <FileSpreadsheet className="w-4 h-4" />,
  image: <FileImage className="w-4 h-4" />,
};

interface Props {
  field: FieldInfo;
  onClose: () => void;
  onStartManualEdit?: () => void;
  onApplySourceValue?: (value: string) => void;
  isEditing?: boolean;
  forceSourceTab?: boolean;
}

const stateLabels: Record<string, { label: string; cls: string; icon: React.ReactNode }> = {
  ai: { label: "AI заполнено", cls: "bg-violet-50 border-violet-200/70 text-violet-600", icon: <Sparkles className="w-3 h-3" /> },
  confirmed: { label: "Подтверждено", cls: "bg-emerald-50 border-emerald-200/70 text-emerald-600", icon: <Check className="w-3 h-3" /> },
  review: { label: "Требует проверки", cls: "bg-amber-50 border-amber-200/70 text-amber-600", icon: <AlertTriangle className="w-3 h-3" /> },
  conflict: { label: "Конфликт", cls: "bg-orange-50 border-orange-300/70 text-orange-700", icon: <GitBranch className="w-3 h-3" /> },
  manual: { label: "Вручную", cls: "bg-blue-50 border-blue-200/70 text-blue-600", icon: <Pencil className="w-3 h-3" /> },
  empty: { label: "Пусто · Обязательное", cls: "bg-red-50 border-red-200/70 text-red-600", icon: <AlertCircle className="w-3 h-3" /> },
};

export function SourceDrawer({ field, onClose, onStartManualEdit, onApplySourceValue, isEditing, forceSourceTab }: Props) {
  const [activeTab, setActiveTab] = useState<DrawerTab>("overview");
  const [selectedAlt, setSelectedAlt] = useState<string | null>(null);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [selectedSourceDoc, setSelectedSourceDoc] = useState<string | null>(null);
  const [selectedExtracted, setSelectedExtracted] = useState<string | null>(null);

  // Reset state when field changes
  useEffect(() => {
    setActiveTab(forceSourceTab ? "source" : "overview");
    setSelectedAlt(null);
    setShowAllHistory(false);
    setSelectedSourceDoc(null);
    setSelectedExtracted(null);
  }, [field.id, forceSourceTab]);

  const stateInfo = stateLabels[field.state];
  const hasAlts = field.alternatives && field.alternatives.length > 0;
  const hasSource = !!field.mainSource;
  const history = field.history ?? [];
  const confidence = field.confidence;

  const statusBarBg = field.state === "conflict" ? "bg-orange-50/40 border-orange-200/40" :
    field.state === "review" ? "bg-amber-50/40 border-amber-200/40" :
    field.state === "empty" ? "bg-red-50/40 border-red-200/40" :
    field.state === "manual" ? "bg-blue-50/40 border-blue-200/40" :
    "bg-emerald-50/40 border-emerald-200/40";

  const confColor = confidence != null ? (
    confidence >= 90 ? "text-emerald-600 bg-emerald-200" :
    confidence >= 75 ? "text-amber-600 bg-amber-200" :
    "text-red-600 bg-red-200"
  ) : "";

  const confBarColor = confidence != null ? (
    confidence >= 90 ? "bg-emerald-500" :
    confidence >= 75 ? "bg-amber-500" :
    "bg-red-500"
  ) : "";

  const confTrackColor = confidence != null ? (
    confidence >= 90 ? "bg-emerald-200" :
    confidence >= 75 ? "bg-amber-200" :
    "bg-red-200"
  ) : "";

  // Footer button label
  const footerLabel = selectedAlt ? "Выбрать и применить" :
    activeTab === "source" ? "Заменить и пересчитать" :
    field.state === "review" ? "Подтвердить значение" :
    "Применить";

  return (
    <aside className="w-full bg-[#fafafa] border-l border-slate-200/80 flex flex-col h-full">
      {/* ─── Header ─── */}
      <div className="bg-white px-5 py-3 border-b border-slate-200/60 shrink-0">
        <div className="flex items-center justify-between mb-1.5">
          <div className="text-[10px] text-slate-400 tracking-wide" style={{ fontWeight: 500 }}>ПОЛЕ ДЕКЛАРАЦИИ</div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="text-[14px] text-slate-900" style={{ fontWeight: 600 }}>{field.label}</div>
        <div className="flex items-center gap-1.5 mt-1.5 text-[10px] text-slate-400">
          <span className="hover:text-slate-600 cursor-pointer transition-colors">Декларация</span>
          <ChevronRight className="w-2.5 h-2.5" />
          <span className="hover:text-slate-600 cursor-pointer transition-colors">{field.section}</span>
          <ChevronRight className="w-2.5 h-2.5" />
          <span className="text-slate-600" style={{ fontWeight: 500 }}>{field.label.split(".")[0]?.trim() ?? field.label}</span>
        </div>
      </div>

      {/* ─── Scrollable body ─── */}
      <div className="flex-1 overflow-y-auto">

        {/* ─── Current Value Block ─── */}
        <div className="bg-white mx-4 mt-4 rounded-2xl border border-slate-200/70 shadow-sm overflow-hidden">
          <div className="px-4 py-3.5">
            <div className="flex items-center justify-between mb-1">
              <div className="text-[10px] text-slate-400 tracking-wide" style={{ fontWeight: 500 }}>ТЕКУЩЕЕ ЗНАЧЕНИЕ</div>
              <span className={`inline-flex items-center gap-1 text-[9px] px-2 py-0.5 rounded-full border ${stateInfo.cls}`}>
                {stateInfo.icon}{stateInfo.label}
              </span>
            </div>
            {field.state === "empty" ? (
              <div className="text-[18px] text-slate-300 italic" style={{ fontWeight: 500 }}>Не заполнено</div>
            ) : (
              <div className="text-[20px] text-slate-900 tracking-tight" style={{ fontWeight: 600 }}>{field.value}</div>
            )}
          </div>
          {/* Status row with confidence */}
          {(confidence != null || field.state === "conflict" || field.state === "review" || field.state === "empty") && (
            <div className={`border-t px-4 py-2.5 flex items-center justify-between ${statusBarBg}`}>
              <div className="flex items-center gap-2">
                {field.state === "conflict" && hasAlts && (
                  <span className="text-[10px] text-orange-600/80">{field.alternatives!.length} источник(а) с расхождением</span>
                )}
                {field.state === "review" && (
                  <span className="text-[10px] text-amber-600/80">Рекомендуется проверить</span>
                )}
                {field.state === "empty" && (
                  <span className="text-[10px] text-red-600/80">Обязательное поле не заполнено</span>
                )}
                {(field.state === "ai" || field.state === "confirmed") && (
                  <span className="text-[10px] text-emerald-600/80">Значение подтверждено</span>
                )}
              </div>
              {confidence != null && (
                <div className="flex items-center gap-1.5">
                  <div className={`w-[52px] h-[5px] rounded-full ${confTrackColor} overflow-hidden`}>
                    <div className={`h-full ${confBarColor} rounded-full`} style={{ width: `${confidence}%` }} />
                  </div>
                  <span className={`text-[10px] ${confColor.split(" ")[0]}`} style={{ fontWeight: 600 }}>{confidence}%</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ─── Main Source ─── */}
        {hasSource && (
          <div className="px-4 pt-4 pb-0">
            <SectionLabel label="ОСНОВНОЙ ИСТОЧНИК" />
            <div className="flex items-center gap-3 p-3 bg-white rounded-2xl border border-slate-200/70 shadow-sm cursor-pointer hover:border-slate-300 transition-colors group">
              <div className="p-2.5 bg-blue-50 rounded-xl border border-blue-200/60">
                <FileText className="w-5 h-5 text-blue-500" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[12px] text-slate-800" style={{ fontWeight: 500 }}>{field.mainSource!.file}</div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  {field.mainSource!.docType}{field.mainSource!.page ? ` · ${field.mainSource!.page}` : ""}{field.mainSource!.detail ? ` · ${field.mainSource!.detail}` : ""}
                </div>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full bg-violet-50 border border-violet-200/70 text-violet-600">
                    <Sparkles className="w-2.5 h-2.5" />AI извлечено
                  </span>
                </div>
              </div>
              <ExternalLink className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 transition-colors shrink-0" />
            </div>
          </div>
        )}

        {/* ─── Document Preview ─── */}
        {hasSource && (
          <div className="px-4 pt-4 pb-0">
            <div className="flex items-center justify-between mb-2">
              <SectionLabel label="ПРЕДПРОСМОТР ДОКУМЕНТА" noMb />
              <div className="flex items-center gap-0.5">
                <button className="p-1 rounded-md hover:bg-slate-200/60 text-slate-400 transition-colors"><ZoomOut className="w-3 h-3" /></button>
                <button className="p-1 rounded-md hover:bg-slate-200/60 text-slate-400 transition-colors"><ZoomIn className="w-3 h-3" /></button>
                <button className="p-1 rounded-md hover:bg-slate-200/60 text-slate-400 transition-colors"><ExternalLink className="w-3 h-3" /></button>
              </div>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200/70 shadow-sm overflow-hidden">
              <div className="p-4">
                <div className="bg-[#f5f5f2] rounded-xl border border-slate-200/50 p-5 relative" style={{ minHeight: 140 }}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="space-y-1">
                      <div className="h-2 bg-slate-300/50 rounded w-28" />
                      <div className="h-1.5 bg-slate-200/60 rounded w-20" />
                    </div>
                    <div className="space-y-1 text-right">
                      <div className="h-1.5 bg-slate-200/60 rounded w-16 ml-auto" />
                    </div>
                  </div>
                  <div className="space-y-1.5 mb-3">
                    <div className="h-1.5 bg-slate-200/50 rounded w-full" />
                    <div className="h-1.5 bg-slate-200/50 rounded w-5/6" />
                  </div>
                  {/* Highlighted extraction zone */}
                  <div className="relative p-3 -mx-1 rounded-xl border-2 border-amber-400 bg-amber-50/60 shadow-[0_0_0_3px_rgba(251,191,36,0.12)]">
                    <div className="flex items-center justify-between">
                      <div className="space-y-1.5">
                        <div className="h-1.5 bg-slate-300/60 rounded w-20" />
                        <div className="h-1.5 bg-slate-300/60 rounded w-14" />
                      </div>
                      <div className="text-right">
                        <div className="text-[12px] text-amber-800" style={{ fontWeight: 700 }}>{field.value || "—"}</div>
                      </div>
                    </div>
                    <div className="absolute -top-2.5 -right-2.5 w-5 h-5 rounded-full bg-amber-400 flex items-center justify-center shadow-sm">
                      <Sparkles className="w-3 h-3 text-white" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-slate-50 border-t border-slate-200/50 px-4 py-1.5 flex items-center justify-between">
                <span className="text-[9px] text-slate-400">{field.mainSource!.page ?? "Страница 1"}</span>
                <button className="text-[10px] text-blue-600 hover:text-blue-700 transition-colors flex items-center gap-1">
                  Открыть документ<ExternalLink className="w-2.5 h-2.5" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ─── Alternative Values ─── */}
        {hasAlts && (
          <div className="px-4 pt-4 pb-0">
            <SectionLabel label="АЛЬТЕРНАТИВНЫЕ ЗНАЧЕНИЯ" />
            <div className="space-y-1.5">
              {field.alternatives!.map(alt => (
                <AltRow
                  key={alt.id}
                  doc={alt.doc} docType={alt.docType} value={alt.value}
                  diff={alt.diff} recommended={alt.recommended}
                  selected={selectedAlt === alt.id}
                  onSelect={() => setSelectedAlt(selectedAlt === alt.id ? null : alt.id)}
                />
              ))}
            </div>
          </div>
        )}

        {/* ─── Why Selected ─── */}
        {field.reasons && field.reasons.length > 0 && (
          <div className="px-4 pt-4 pb-0">
            <SectionLabel label="ПОЧЕМУ ВЫБРАНО ЭТО ЗНАЧЕНИЕ" />
            <div className="bg-white rounded-2xl border border-slate-200/70 shadow-sm p-3.5">
              <ul className="space-y-2">
                {field.reasons.map((r, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-[11px] text-slate-600">
                    <span className="mt-0.5 shrink-0">
                      {r.ok ? <Check className="w-3 h-3 text-emerald-500" /> : <AlertTriangle className="w-3 h-3 text-amber-500" />}
                    </span>{r.text}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* ─── Correction Mode ─── */}
        <div className="px-4 pt-4 pb-0">
          <SectionLabel label="ИСПРАВЛЕНИЕ" />

          {isEditing && (
            <div className="flex items-center gap-2 p-3 bg-blue-50/60 rounded-xl border border-blue-200/50 mb-3">
              <Pencil className="w-3.5 h-3.5 text-blue-500 shrink-0" />
              <div className="flex-1">
                <div className="text-[11px] text-blue-700" style={{ fontWeight: 500 }}>Режим редактирования</div>
                <div className="text-[10px] text-blue-500/80 mt-0.5">Измените значение на форме и нажмите галочку для сохранения</div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-1.5 mb-3">
            <ActionCard
              icon={<Pencil className="w-3.5 h-3.5 text-violet-500" />}
              label="Изменить вручную"
              onClick={onStartManualEdit}
              active={isEditing}
            />
            <ActionCard
              icon={<FileUp className="w-3.5 h-3.5 text-amber-500" />}
              label="Изменить источник"
              onClick={() => { setActiveTab("source"); setSelectedSourceDoc(null); setSelectedExtracted(null); }}
              active={activeTab === "source"}
            />
          </div>

          {activeTab === "source" && !selectedSourceDoc && (
            <div className="bg-white rounded-2xl border border-slate-200/70 shadow-sm overflow-hidden">
              <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50/50">
                <div className="text-[10px] text-slate-500" style={{ fontWeight: 500 }}>Выберите документ</div>
              </div>
              <div className="p-2 space-y-0.5 max-h-[320px] overflow-y-auto">
                {sourceDocuments.map(doc => (
                  <button
                    key={doc.id}
                    onClick={() => { setSelectedSourceDoc(doc.id); setSelectedExtracted(null); }}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left hover:bg-slate-50 transition-colors group"
                  >
                    <div className="p-1.5 rounded-lg bg-slate-100 text-slate-500 group-hover:bg-blue-50 group-hover:text-blue-500 transition-colors shrink-0">
                      {docTypeIcon[doc.type]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[11px] text-slate-700 truncate" style={{ fontWeight: 500 }}>{doc.name}</div>
                      <div className="text-[9px] text-slate-400 mt-0.5">{doc.extractedFields.length} извлечённых полей</div>
                    </div>
                    <ChevronRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 transition-colors shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {activeTab === "source" && selectedSourceDoc && (() => {
            const doc = sourceDocuments.find(d => d.id === selectedSourceDoc);
            if (!doc) return null;
            return (
              <div className="bg-white rounded-2xl border border-slate-200/70 shadow-sm overflow-hidden">
                {/* Back header */}
                <div className="px-3 py-2 border-b border-slate-100 bg-slate-50/50 flex items-center gap-2">
                  <button
                    onClick={() => { setSelectedSourceDoc(null); setSelectedExtracted(null); }}
                    className="p-1 rounded-md hover:bg-slate-200/60 text-slate-400 transition-colors"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] text-slate-700 truncate" style={{ fontWeight: 500 }}>{doc.name}</div>
                    <div className="text-[9px] text-slate-400">Извлечённые данные</div>
                  </div>
                </div>
                {/* Extracted fields */}
                <div className="p-2 space-y-0.5">
                  {doc.extractedFields.map(ef => {
                    const isSelected = selectedExtracted === ef.id;
                    const confClr = ef.confidence >= 90 ? "text-emerald-600" : ef.confidence >= 75 ? "text-amber-600" : "text-red-500";
                    return (
                      <button
                        key={ef.id}
                        onClick={() => setSelectedExtracted(isSelected ? null : ef.id)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all ${
                          isSelected ? "bg-blue-50/60 border border-blue-200/60 shadow-sm" : "hover:bg-slate-50 border border-transparent"
                        }`}
                      >
                        <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${
                          isSelected ? "border-blue-500 bg-blue-500" : "border-slate-300"
                        }`}>
                          {isSelected && <Check className="w-2.5 h-2.5 text-white" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-[10px] text-slate-400">{ef.label}</div>
                          <div className="text-[12px] text-slate-800 mt-0.5" style={{ fontWeight: 600 }}>{ef.value}</div>
                        </div>
                        <div className="text-right shrink-0">
                          <div className={`text-[10px] ${confClr}`} style={{ fontWeight: 600 }}>{ef.confidence}%</div>
                          <div className="text-[9px] text-slate-400 mt-0.5">{ef.page}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
                {/* Apply button */}
                {selectedExtracted && (
                  <div className="px-3 pb-3">
                    <button
                      onClick={() => {
                        const ef = doc.extractedFields.find(e => e.id === selectedExtracted);
                        if (ef && onApplySourceValue) {
                          onApplySourceValue(ef.value);
                          setSelectedExtracted(null);
                          setSelectedSourceDoc(null);
                          setActiveTab("overview");
                        }
                      }}
                      className="w-full flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-white text-[11px] hover:bg-blue-700 transition-colors shadow-sm"
                      style={{ fontWeight: 500 }}
                    >
                      <ArrowRight className="w-3.5 h-3.5" />
                      Применить значение
                    </button>
                  </div>
                )}
              </div>
            );
          })()}
        </div>

        {/* ─── Change History ─── */}
        {history.length > 0 && (
          <div className="px-4 pt-4 pb-5">
            <div className="flex items-center justify-between mb-2">
              <SectionLabel label="ИСТОРИЯ ИЗМЕНЕНИЙ" noMb />
              {history.length > 3 && (
                <button
                  onClick={() => setShowAllHistory(!showAllHistory)}
                  className="text-[10px] text-blue-600 hover:text-blue-700 transition-colors flex items-center gap-0.5"
                >
                  {showAllHistory ? "Свернуть" : "Показать все"}<ChevronDown className={`w-2.5 h-2.5 transition-transform ${showAllHistory ? "rotate-180" : ""}`} />
                </button>
              )}
            </div>
            <div className="bg-white rounded-2xl border border-slate-200/70 shadow-sm p-3.5">
              <div className="space-y-0">
                {(showAllHistory ? history : history.slice(0, 3)).map((h, i, arr) => (
                  <div key={i} className="flex items-start gap-3 relative pb-3.5 last:pb-0">
                    {i < arr.length - 1 && <div className="absolute left-[6px] top-4 bottom-0 w-px bg-slate-200" />}
                    <div className={`w-[13px] h-[13px] rounded-full ${h.dot} shrink-0 mt-0.5 ring-2 ring-white`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-[11px] text-slate-700">{h.text}</span>
                        <span className="text-[10px] text-slate-400 shrink-0 flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5" />{h.time}
                        </span>
                      </div>
                      {h.detail && <div className="text-[10px] text-slate-400 mt-0.5">{h.detail}</div>}
                      {h.actor && (
                        <div className="flex items-center gap-1.5 mt-1">
                          <div className="w-4 h-4 rounded-full bg-slate-200 flex items-center justify-center">
                            <span className="text-[8px] text-slate-500" style={{ fontWeight: 600 }}>{h.actor[0]}</span>
                          </div>
                          <span className="text-[9px] text-slate-400">{h.actor}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ─── Sticky Footer ─── */}
      <div className="bg-white border-t border-slate-200/80 px-5 py-3 shrink-0">
        <div className="flex items-center gap-2">
          <button className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 text-white text-[12px] hover:bg-emerald-700 transition-colors shadow-sm" style={{ fontWeight: 500 }}>
            <Check className="w-3.5 h-3.5" />
            {footerLabel}
          </button>
          {field.state !== "empty" && (
            <button className="flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-200 text-slate-500 text-[11px] hover:bg-slate-50 bg-white transition-colors">
              <RotateCcw className="w-3 h-3" />Сбросить к AI
            </button>
          )}
        </div>
        <div className="flex items-center gap-1.5 mt-2 text-[9px] text-slate-400">
          <Shield className="w-3 h-3" />
          <span>Все изменения записываются в журнал аудита</span>
        </div>
      </div>
    </aside>
  );
}

function SectionLabel({ label, noMb }: { label: string; noMb?: boolean }) {
  return <div className={`text-[10px] text-slate-400 tracking-wide ${noMb ? "" : "mb-2"}`} style={{ fontWeight: 500 }}>{label}</div>;
}

function TabBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={`flex-1 px-3 py-1.5 rounded-lg text-[11px] transition-colors ${active ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
      style={{ fontWeight: active ? 500 : 400 }}
    >{label}</button>
  );
}

function AltRow({ doc, docType, value, diff, recommended, selected, onSelect }: {
  doc: string; docType: string; value: string; diff?: boolean; recommended?: boolean; selected?: boolean; onSelect?: () => void;
}) {
  return (
    <div onClick={onSelect}
      className={`flex items-center gap-3 p-3 rounded-2xl border cursor-pointer transition-all ${
        selected ? "border-blue-300 bg-blue-50/40 shadow-sm ring-1 ring-blue-200/50" :
        diff ? "border-orange-200/70 bg-white hover:border-orange-300" :
        "border-slate-200/70 bg-white hover:border-slate-300"
      }`}
    >
      <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${
        selected ? "border-blue-500 bg-blue-500" : "border-slate-300"
      }`}>
        {selected && <Check className="w-2.5 h-2.5 text-white" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <FileText className="w-3 h-3 text-slate-400 shrink-0" />
          <span className="text-[11px] text-slate-700" style={{ fontWeight: 500 }}>{doc}</span>
          {recommended && (
            <span className="text-[8px] px-1.5 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-600" style={{ fontWeight: 600 }}>Рекомендовано</span>
          )}
          {diff && (
            <span className="text-[8px] px-1.5 py-0.5 rounded-full bg-orange-50 border border-orange-200 text-orange-600">Расхождение</span>
          )}
        </div>
        <div className="text-[9px] text-slate-400 mt-0.5 ml-5">{docType}</div>
      </div>
      <span className={`text-[12px] shrink-0 ${diff ? "text-orange-600" : "text-slate-800"}`} style={{ fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function ActionCard({ icon, label, onClick, active }: { icon: React.ReactNode; label: string; onClick?: () => void; active?: boolean }) {
  return (
    <button onClick={onClick} className={`relative flex flex-col items-center gap-1.5 p-3 rounded-2xl border shadow-sm hover:shadow transition-all group ${
      active ? "bg-blue-50/60 border-blue-200/60" : "bg-white border-slate-200/70 hover:border-slate-300"
    }`}>
      {icon}
      <div className={`text-[10px] transition-colors ${active ? "text-blue-600" : "text-slate-600 group-hover:text-slate-900"}`} style={{ fontWeight: 500 }}>{label}</div>
    </button>
  );
}

function SourceOption({ icon, label, desc }: { icon: React.ReactNode; label: string; desc: string }) {
  return (
    <button className="w-full flex items-center gap-3 p-2.5 rounded-xl border border-slate-200/70 text-left hover:bg-slate-50 hover:border-slate-300 transition-all">
      <span className="shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="text-[11px] text-slate-700" style={{ fontWeight: 500 }}>{label}</div>
        <div className="text-[9px] text-slate-400 mt-0.5">{desc}</div>
      </div>
      <ChevronRight className="w-3 h-3 text-slate-300 shrink-0" />
    </button>
  );
}