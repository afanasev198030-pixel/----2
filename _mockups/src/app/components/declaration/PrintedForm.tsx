import React, { useState, useRef, useEffect } from "react";
import { Info, Pencil, Sparkles, Check, AlertTriangle, GitBranch, AlertCircle, X, FileUp } from "lucide-react";

/* ─── Types ─── */
type CellState = "ai" | "confirmed" | "review" | "conflict" | "manual" | "empty" | "default";

interface CellDef {
  id: string;
  num: string;        // box number e.g. "1", "2", "14"
  label: string;      // small label
  value: string;
  state: CellState;
  // grid placement
  col: string;        // tailwind col-start / span
  row: string;        // tailwind row-start / span
  tall?: boolean;
  labelPosition?: "top" | "left";
}

const stateStyles: Record<CellState, { border: string; dot: React.ReactNode }> = {
  ai: { border: "border-violet-300/60", dot: <Sparkles className="w-2.5 h-2.5 text-violet-500" /> },
  confirmed: { border: "border-emerald-300/60", dot: <Check className="w-2.5 h-2.5 text-emerald-500" /> },
  review: { border: "border-amber-300/70", dot: <AlertTriangle className="w-2.5 h-2.5 text-amber-500" /> },
  conflict: { border: "border-orange-400/70", dot: <GitBranch className="w-2.5 h-2.5 text-orange-500" /> },
  manual: { border: "border-blue-300/60", dot: <Pencil className="w-2.5 h-2.5 text-blue-500" /> },
  empty: { border: "border-red-300/60", dot: <AlertCircle className="w-2.5 h-2.5 text-red-500" /> },
  default: { border: "border-slate-200", dot: null },
};

/* ─── Cell Data (mirrors printed ДТ form) ─── */
const cells: CellDef[] = [
  // Row 1
  { id: "f1", num: "1", label: "Декларация", value: "ИМ  40  ЭД", state: "confirmed", col: "col-start-1 col-span-4", row: "row-start-1" },
  { id: "a", num: "A", label: "Регистрационный номер", value: "10131010/190126/5012553", state: "default", col: "col-start-5 col-span-8", row: "row-start-1" },

  // Row 2
  { id: "f2", num: "2", label: "Отправитель / Экспортёр", value: "HK SAN GENSHIN INDUSTRY CO., LIMITED\nCHINA, YIWU CITY, ROOM 202, NO.1, BLOCK 16,\nINTEGRITY ZONE 1, FUTIAN STREET", state: "ai", col: "col-start-1 col-span-6", row: "row-start-2 row-span-2", tall: true },
  { id: "f3", num: "3", label: "Формы", value: "1      2", state: "confirmed", col: "col-start-7 col-span-2", row: "row-start-2" },
  { id: "f4", num: "4", label: "Отгр. спец.", value: "", state: "default", col: "col-start-9 col-span-1", row: "row-start-2" },
  { id: "f5", num: "5", label: "Всего т-ов", value: "2", state: "confirmed", col: "col-start-7 col-span-1", row: "row-start-3" },
  { id: "f6", num: "6", label: "Всего мест", value: "9", state: "confirmed", col: "col-start-8 col-span-1", row: "row-start-3" },
  { id: "f7", num: "7", label: "Справочный номер", value: "", state: "default", col: "col-start-9 col-span-4", row: "row-start-3" },

  // Row 3
  { id: "f8", num: "8", label: "Получатель", value: "СМ. ГРАФУ 14 ДТ", state: "confirmed", col: "col-start-1 col-span-6", row: "row-start-4" },
  { id: "f9", num: "9", label: "Лицо, ответств. за финансовое урегулирование", value: "СМ. ГРАФУ 14 ДТ", state: "confirmed", col: "col-start-7 col-span-6", row: "row-start-4" },

  // Row 4
  { id: "f10", num: "10", label: "Стр. перв. назн. / посл. отпр.", value: "НК", state: "confirmed", col: "col-start-1 col-span-3", row: "row-start-5" },
  { id: "f11", num: "11", label: "Торг. страна", value: "НК", state: "confirmed", col: "col-start-4 col-span-2", row: "row-start-5" },
  { id: "f12", num: "12", label: "Общая таможенная стоимость", value: "9 126 279.55", state: "ai", col: "col-start-6 col-span-5", row: "row-start-5" },
  { id: "f13", num: "13", label: "", value: "", state: "default", col: "col-start-11 col-span-2", row: "row-start-5" },

  // Row 5 – Declarant
  { id: "f14", num: "14", label: "Декларант", value: "ООО \"АГ-ЛОГИСТИК\"\nРОССИЯ, ВН.ТЕР.Г. МУНИЦИПАЛЬНЫЙ ОКРУГ ВОЙКОВСКИЙ,\nГ. МОСКВА, Ш. ЛЕНИНГРАДСКОЕ, Д. 16А, СТР.3\nИНН: 9728100494 / КПП: 774301001\nОГРН: 1237700467652", state: "confirmed", col: "col-start-1 col-span-12", row: "row-start-6 row-span-2", tall: true },

  // Row 6
  { id: "f15", num: "15", label: "Страна отправления", value: "КИТАЙ", state: "review", col: "col-start-1 col-span-4", row: "row-start-8" },
  { id: "f15a", num: "15а", label: "Код страны отпр.", value: "CN", state: "confirmed", col: "col-start-5 col-span-1", row: "row-start-8" },
  { id: "f16", num: "16", label: "Страна происхождения", value: "КИТАЙ", state: "ai", col: "col-start-1 col-span-4", row: "row-start-9" },
  { id: "f17", num: "17", label: "Код страны назнач.", value: "RU", state: "confirmed", col: "col-start-6 col-span-2", row: "row-start-8" },
  { id: "f17a", num: "17а", label: "Страна назначения", value: "РОССИЯ", state: "confirmed", col: "col-start-6 col-span-2", row: "row-start-9" },

  // Row 7
  { id: "f18", num: "18", label: "Идент. и страна регистр. трансп. средства", value: "", state: "default", col: "col-start-1 col-span-4", row: "row-start-10" },
  { id: "f19", num: "19", label: "Конт.", value: "0", state: "confirmed", col: "col-start-5 col-span-1", row: "row-start-10" },
  { id: "fc8", num: "20", label: "Условия поставки", value: "EXW  BEIJING", state: "empty", col: "col-start-6 col-span-7", row: "row-start-10" },

  // Row 8
  { id: "f21", num: "21", label: "Идент. и страна актив. трансп. средства", value: "1: HZ-5469", state: "default", col: "col-start-1 col-span-4", row: "row-start-11" },
  { id: "fc4", num: "22", label: "Валюта и общая сумма по счёту", value: "RUB  9 058 816.00", state: "conflict", col: "col-start-5 col-span-4", row: "row-start-11" },
  { id: "f23", num: "23", label: "Курс валюты", value: "010 00", state: "confirmed", col: "col-start-9 col-span-2", row: "row-start-11" },
  { id: "fc5", num: "24", label: "Характер сделки", value: "010", state: "manual", col: "col-start-11 col-span-2", row: "row-start-11" },

  // Row 9
  { id: "f25", num: "25", label: "Вид транспорта", value: "40", state: "confirmed", col: "col-start-1 col-span-2", row: "row-start-12" },
  { id: "f26", num: "26", label: "Вид транспорта внутр.", value: "", state: "default", col: "col-start-3 col-span-2", row: "row-start-12" },
  { id: "f27", num: "27", label: "Место погрузки/разгрузки", value: "", state: "default", col: "col-start-5 col-span-4", row: "row-start-12" },
  { id: "f28", num: "28", label: "Финансовые и банковские сведения", value: "", state: "default", col: "col-start-9 col-span-4", row: "row-start-12" },

  // Row 10
  { id: "f29", num: "29", label: "Орган въезда/выезда", value: "10702010\nТ/П АЭРОПОРТ ВЛАДИВОСТОК", state: "confirmed", col: "col-start-1 col-span-4", row: "row-start-13" },
  { id: "f30", num: "30", label: "Местонахождение товаров", value: "ПРИМОРСКИЙ КРАЙ Г. АРТЁМ УЛ.\nВЛАДИМИРА САЙБЕЛЯ, Д. 41, 10702/10611/10/16 14.01.15", state: "confirmed", col: "col-start-5 col-span-8", row: "row-start-13" },

  // Row 11 – Goods description
  { id: "f31", num: "31", label: "Грузовые места и описание товаров — Маркировка и количество — Номера контейнеров — Количество и отличительные особенности", value: "1-ПРИЕМНИКИ РАДИОНАВИГАЦИОННЫЕ. НЕ ВОЕННОГО\nНАЗНАЧЕНИЯ. НЕ ЯВЛЯЮТСЯ ЛОМОМ ЭЛЕКТРООБОРУДОВАНИЯ\n2-1, РК-1", state: "ai", col: "col-start-1 col-span-6", row: "row-start-14 row-span-2", tall: true },
  { id: "f32", num: "32", label: "Товар №", value: "1", state: "confirmed", col: "col-start-7 col-span-1", row: "row-start-14" },
  { id: "f33", num: "33", label: "Код товара", value: "8526912000", state: "ai", col: "col-start-8 col-span-3", row: "row-start-14" },
  { id: "f34", num: "34", label: "Код стр. происх.", value: "CN", state: "confirmed", col: "col-start-7 col-span-2", row: "row-start-15" },
  { id: "f35", num: "35", label: "Вес брутто (кг)", value: "20.030", state: "ai", col: "col-start-9 col-span-2", row: "row-start-15" },
  { id: "f36", num: "36", label: "Преференции", value: "0000-00", state: "default", col: "col-start-11 col-span-2", row: "row-start-15" },

  // Row 12
  { id: "f37", num: "37", label: "ПРОЦЕДУРА", value: "4000    000", state: "confirmed", col: "col-start-7 col-span-2", row: "row-start-16" },
  { id: "f38", num: "38", label: "Вес нетто (кг)", value: "19.030", state: "ai", col: "col-start-9 col-span-2", row: "row-start-16" },
  { id: "f39", num: "39", label: "Квота", value: "", state: "default", col: "col-start-11 col-span-2", row: "row-start-16" },

  // Row 13
  { id: "f40", num: "40", label: "Общая декларация / Предшествующий документ", value: "", state: "default", col: "col-start-1 col-span-12", row: "row-start-17" },

  // Row 14
  { id: "f41", num: "41", label: "Дополн. единицы", value: "1600 / ШТ / 796", state: "ai", col: "col-start-1 col-span-4", row: "row-start-18" },
  { id: "f42", num: "42", label: "Цена товара", value: "1 670 288.00", state: "ai", col: "col-start-5 col-span-4", row: "row-start-18" },
  { id: "f43", num: "43", label: "Код МОС", value: "1  0", state: "default", col: "col-start-9 col-span-4", row: "row-start-18" },

  // Row 15
  { id: "f44", num: "44", label: "Дополн. информация / Предстваляемые документы", value: "03011/2 AG-ZED/2025/0029 от 23.01.2025 10005030/250325/5074378\n03031/0 25010321/2673/0000/2/1 от 30.01.2025; СМ.ДОПОЛНЕНИЕ", state: "ai", col: "col-start-1 col-span-8", row: "row-start-19 row-span-2", tall: true },
  { id: "f45", num: "45", label: "Таможенная стоимость", value: "1 679 607.23", state: "ai", col: "col-start-9 col-span-4", row: "row-start-19" },
  { id: "f46", num: "46", label: "Статистическая стоимость", value: "21 579.57", state: "ai", col: "col-start-9 col-span-4", row: "row-start-20" },

  // Row 16 – Payments
  { id: "f47", num: "47", label: "Исчисление платежей", value: "1010          73860РУБ          73860.00  ИУ\n2010  1679607.23   5%          83980.36  ИУ\n5010  1763587.59   22%        387989.27  ИУ", state: "ai", col: "col-start-1 col-span-7", row: "row-start-21 row-span-2", tall: true },
  { id: "f48", num: "48", label: "Отсрочка платежей", value: "", state: "default", col: "col-start-8 col-span-2", row: "row-start-21" },
  { id: "fb", num: "B", label: "Подробности подсчёта", value: "1010-73860.00-643-9728100494\n2010-83980.36-643-9728100494\n5010-2026257.18-643-9728100494", state: "confirmed", col: "col-start-8 col-span-5", row: "row-start-22", tall: true },

  // Total
  { id: "ftotal", num: "", label: "Всего:", value: "ИТОГО: 2 184 097.54 РУБ", state: "default", col: "col-start-1 col-span-12", row: "row-start-23" },

  // Row 17 – Decision
  { id: "f54", num: "54", label: "Место и дата", value: "1-09034 1509 от 29.07.2022, 11002 0142/НЧ ОТ 10.01.2024\n2-ШИРОВА ВИКТОРИЯ СЕРГЕЕВНА\nRU01001 92 22 163919 ОТ 16.11.2022,\nСПЕЦИАЛИСТ ПО ТО\nТЕЛ. 89953604290, SHIROVA@RTLV.RU\n11004 ДОВЕРЕННОСТЬ 26 ОТ 27.08.2025 ДО 27.08.2026", state: "confirmed", col: "col-start-7 col-span-6", row: "row-start-24 row-span-2", tall: true },
  { id: "fd_num", num: "D", label: "", value: "10    19.01.2026 16:05:13    000", state: "default", col: "col-start-1 col-span-6", row: "row-start-24" },
  { id: "fd_result", num: "", label: "ВЫПУСК ТОВАРОВ РАЗРЕШЕН", value: "АВТОМАТ", state: "confirmed", col: "col-start-1 col-span-6", row: "row-start-25" },
];

interface Props {
  selectedField: string;
  onFieldSelect: (id: string) => void;
  contentRef?: React.RefObject<HTMLDivElement | null>;
  editingField?: string | null;
  cellOverrides?: Record<string, string>;
  onSaveEdit?: (id: string, value: string) => void;
  onCancelEdit?: () => void;
  onStartManualEdit?: (id: string) => void;
  onOpenSourceChange?: (id: string) => void;
}

export function PrintedForm({ selectedField, onFieldSelect, contentRef, editingField, cellOverrides, onSaveEdit, onCancelEdit, onStartManualEdit, onOpenSourceChange }: Props) {
  const [hoveredCell, setHoveredCell] = useState<string | null>(null);

  return (
    <div ref={contentRef} className="flex-1 overflow-y-auto bg-[#f5f6f8] p-8">
      <div className="max-w-[1100px] mx-auto bg-white rounded-2xl shadow-[0_1px_4px_rgba(0,0,0,0.06),0_0_0_1px_rgba(0,0,0,0.04)] overflow-hidden">
        {/* Form Title */}
        <div className="border-b border-slate-200 px-6 py-3.5 flex items-center justify-between bg-gradient-to-r from-slate-50/80 to-white">
          <h1 className="text-[14px] text-slate-700 tracking-wide" style={{ fontWeight: 600, letterSpacing: '0.04em' }}>
            ДЕКЛАРАЦИЯ НА ТОВАРЫ
          </h1>
          <div className="text-[11px] text-slate-400" style={{ fontWeight: 500 }}>
            DC-2026-001245
          </div>
        </div>

        {/* Grid Form */}
        <div
          className="grid"
          style={{
            gridTemplateColumns: "repeat(12, 1fr)",
            gap: 0,
          }}
        >
          {cells.map((cell) => (
            <FormCell
              key={cell.id}
              cell={cell}
              isSelected={selectedField === cell.id}
              isHovered={hoveredCell === cell.id}
              onHover={setHoveredCell}
              onClick={() => onFieldSelect(cell.id)}
              isEditing={editingField === cell.id}
              overrideValue={cellOverrides?.[cell.id]}
              onSaveEdit={onSaveEdit}
              onCancelEdit={onCancelEdit}
              onStartManualEdit={onStartManualEdit}
              onOpenSourceChange={onOpenSourceChange}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function FormCell({
  cell,
  isSelected,
  isHovered,
  onHover,
  onClick,
  isEditing,
  overrideValue,
  onSaveEdit,
  onCancelEdit,
  onStartManualEdit,
  onOpenSourceChange,
}: {
  cell: CellDef;
  isSelected: boolean;
  isHovered: boolean;
  onHover: (id: string | null) => void;
  onClick: () => void;
  isEditing: boolean;
  overrideValue?: string;
  onSaveEdit?: (id: string, value: string) => void;
  onCancelEdit?: () => void;
  onStartManualEdit?: (id: string) => void;
  onOpenSourceChange?: (id: string) => void;
}) {
  const st = stateStyles[cell.state];
  const hasState = cell.state !== "default";
  const displayValue = overrideValue ?? cell.value;

  const selectedBorder = isSelected
    ? isEditing
      ? "ring-2 ring-blue-500/60 ring-inset z-20 bg-blue-50/40"
      : "ring-2 ring-blue-400/50 ring-inset z-10 bg-blue-50/30"
    : "";

  const hoverBg = isHovered && !isSelected ? "bg-slate-50/80" : "";
  const stateBg =
    cell.state === "review" ? "bg-amber-50/25" :
    cell.state === "conflict" ? "bg-orange-50/25" :
    cell.state === "empty" ? "bg-red-50/15" :
    "";

  const isMultiline = displayValue.includes("\n");

  const [localValue, setLocalValue] = useState(displayValue);
  const editRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (isEditing) {
      setLocalValue(displayValue);
      setTimeout(() => editRef.current?.focus(), 50);
    }
  }, [isEditing]);

  const handleSave = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSaveEdit?.(cell.id, localValue);
  };

  const handleCancel = (e: React.MouseEvent) => {
    e.stopPropagation();
    setLocalValue(displayValue);
    onCancelEdit?.();
  };

  return (
    <div
      className={`relative border border-slate-150 cursor-pointer transition-all duration-150 ${cell.col} ${cell.row} ${selectedBorder} ${hoverBg} ${!isEditing ? stateBg : ""} ${cell.tall ? "min-h-[80px]" : "min-h-[48px]"}`}
      style={{ margin: "-0.5px", borderColor: isEditing ? undefined : "rgba(226,232,240,0.7)" }}
      onMouseEnter={() => onHover(cell.id)}
      onMouseLeave={() => onHover(null)}
      onClick={isEditing ? undefined : onClick}
    >
      {/* Cell header: number + label */}
      <div className="flex items-baseline gap-1.5 px-2.5 pt-1.5">
        {cell.num && (
          <span className="text-[9px] text-slate-400/80 shrink-0" style={{ fontWeight: 600 }}>
            {cell.num}
          </span>
        )}
        {cell.label && (
          <span className="text-[8px] text-slate-400/70 truncate leading-tight">
            {cell.label}
          </span>
        )}
        {/* State dot */}
        {hasState && !isEditing && (
          <span className="ml-auto shrink-0">{st.dot}</span>
        )}
        {/* Editing label */}
        {isEditing && (
          <span className="ml-auto text-[8px] text-blue-500 px-1.5 py-0.5 rounded bg-blue-50 border border-blue-200/60" style={{ fontWeight: 600 }}>
            Редактирование
          </span>
        )}
      </div>

      {/* Cell value */}
      <div className="px-2.5 pb-2 pt-0.5">
        {isEditing ? (
          <textarea
            ref={editRef}
            className="w-full resize-none border-none outline-none bg-white/80 text-[11px] text-slate-900 font-[inherit] rounded-md px-1.5 py-1 -mx-1.5"
            style={{ fontWeight: 500, minHeight: cell.tall ? 56 : 22 }}
            rows={cell.tall ? 3 : 1}
            value={localValue}
            onChange={(e) => setLocalValue(e.target.value)}
            onClick={(e) => e.stopPropagation()}
          />
        ) : cell.state === "empty" && !displayValue ? (
          <span className="text-[10px] text-red-400 italic">Не заполнено</span>
        ) : isMultiline ? (
          <pre className="text-[10px] text-slate-800 whitespace-pre-wrap leading-[1.4] m-0 font-[inherit]" style={{ fontWeight: 500 }}>
            {displayValue}
          </pre>
        ) : (
          <div className="text-[11px] text-slate-800 truncate" style={{ fontWeight: 500 }}>
            {displayValue}
          </div>
        )}
      </div>

      {/* Editing save/cancel buttons */}
      {isEditing && (
        <div className="absolute top-1 right-1 flex items-center gap-0.5 z-30">
          <button
            onClick={handleSave}
            className="p-1.5 rounded-lg bg-emerald-500 shadow-sm border border-emerald-600 hover:bg-emerald-600 transition-colors"
            title="Сохранить"
          >
            <Check className="w-3 h-3 text-white" />
          </button>
          <button
            onClick={handleCancel}
            className="p-1.5 rounded-lg bg-white shadow-sm border border-slate-200 hover:bg-red-50 transition-colors"
            title="Отменить"
          >
            <X className="w-3 h-3 text-slate-400" />
          </button>
        </div>
      )}

      {/* Hover overlay with action icons */}
      {isHovered && !isEditing && (
        <div className="absolute top-1 right-1 flex items-center gap-0.5 z-20">
          <button
            onClick={(e) => { e.stopPropagation(); onClick(); }}
            className="p-1 rounded-md bg-white/90 shadow-sm border border-slate-200/80 hover:bg-blue-50 transition-colors"
            title="Информация"
          >
            <Info className="w-3 h-3 text-slate-500" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onStartManualEdit?.(cell.id); }}
            className="p-1 rounded-md bg-white/90 shadow-sm border border-slate-200/80 hover:bg-violet-50 transition-colors"
            title="Изменить вручную"
          >
            <Pencil className="w-3 h-3 text-slate-500" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onOpenSourceChange?.(cell.id); }}
            className="p-1 rounded-md bg-white/90 shadow-sm border border-slate-200/80 hover:bg-amber-50 transition-colors"
            title="Изменить источник"
          >
            <FileUp className="w-3 h-3 text-slate-500" />
          </button>
        </div>
      )}

      {/* Left colored border for state */}
      {hasState && cell.state !== "default" && (
        <div className={`absolute left-0 top-0 bottom-0 w-[2.5px] ${
          cell.state === "confirmed" ? "bg-emerald-400/70" :
          cell.state === "ai" ? "bg-violet-400/70" :
          cell.state === "review" ? "bg-amber-400/80" :
          cell.state === "conflict" ? "bg-orange-400/80" :
          cell.state === "manual" ? "bg-blue-400/70" :
          cell.state === "empty" ? "bg-red-400/80" : ""
        }`} />
      )}
    </div>
  );
}