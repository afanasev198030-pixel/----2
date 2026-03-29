import React, { useState } from "react";
import { Search, ToggleLeft, ChevronDown, ChevronRight, AlertTriangle, CheckCircle2, PanelLeftOpen } from "lucide-react";
import { FieldRow } from "./FieldRow";

interface Props {
  selectedField: string;
  onFieldSelect: (f: string) => void;
  contentRef?: React.RefObject<HTMLDivElement | null>;
  navCollapsed?: boolean;
  onToggleNav?: () => void;
}

export function DeclContent({ selectedField, onFieldSelect, contentRef, navCollapsed, onToggleNav }: Props) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const toggle = (s: string) => setCollapsed(p => ({ ...p, [s]: !p[s] }));

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full bg-[#f8f8fa]">
      {/* Toolbar */}
      <div className="bg-white border-b border-slate-200/80 px-4 py-2 flex items-center gap-3">
        <div className="flex items-center gap-2">
          {navCollapsed && (
            <button
              onClick={onToggleNav}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 transition-colors mr-1"
              title="Развернуть навигацию"
            >
              <PanelLeftOpen className="w-4 h-4" />
            </button>
          )}
          <button className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-900 bg-slate-900 text-white text-[10px]">
            <ToggleLeft className="w-3.5 h-3.5" />Рабочий вид
          </button>
          <button className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-200 text-slate-500 text-[10px] bg-white hover:bg-slate-50">
            Печатная форма
          </button>
          <div className="w-px h-4 bg-slate-200 mx-1" />
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-400" />
            <input className="pl-7 pr-3 py-1 text-[11px] bg-slate-50 border border-slate-200 rounded-lg outline-none focus:border-slate-300 w-48 placeholder-slate-400" placeholder="Поиск по графам..." />
          </div>
        </div>
      </div>

      {/* Scrollable content */}
      <div ref={contentRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {/* Section 1: Общие сведения */}
        <div id="section-general">
        <Section title="Общие сведения" stats="12/12" open={!collapsed["s1"]} onToggle={() => toggle("s1")}>
          <div className="space-y-1.5">
            <FieldRow label="Графа 1. Тип декларации" value="ИМ 40" state="confirmed" source="Контракт" confidence={98} selected={selectedField === "f1"} onClick={() => onFieldSelect("f1")} />
            <FieldRow label="Графа 2. Отправитель" value="Shanghai Electronics Co., Ltd" state="ai" source="Инвойс · стр.1" confidence={96} selected={selectedField === "f2"} onClick={() => onFieldSelect("f2")} />
            <FieldRow label="Графа 8. Получатель" value='ООО "Альфа Импорт"' state="confirmed" source="Контракт" confidence={99} selected={selectedField === "f8"} onClick={() => onFieldSelect("f8")} />
            <FieldRow label="Графа 9. Лицо, ответственное за финансовое урегулирование" value='ООО "Альфа Импорт"' state="ai" source="Контракт · стр.1" confidence={97} selected={selectedField === "f9"} onClick={() => onFieldSelect("f9")} />
            <FieldRow label="Графа 11. Торгующая страна" value="Китай" state="confirmed" source="Контракт" confidence={99} selected={selectedField === "f11"} onClick={() => onFieldSelect("f11")} />
            <FieldRow label="Графа 14. Декларант" value='ООО "Альфа Импорт" · ИНН 7701234567' state="confirmed" source="Контракт" confidence={99} selected={selectedField === "f14"} onClick={() => onFieldSelect("f14")} />
            <FieldRow label="Графа 15. Страна отправления" value="Китай" state="review" source="Инвойс · стр.1" confidence={76} selected={selectedField === "f15"} onClick={() => onFieldSelect("f15")} />
            <FieldRow label="Графа 15a. Код страны отправления" value="CN" state="ai" source="Инвойс" confidence={95} selected={selectedField === "f15a"} onClick={() => onFieldSelect("f15a")} />
          </div>
        </Section>
        </div>

        {/* Section 2: Декларант / отправитель / получатель */}
        <div id="section-parties">
        <Section title="Декларант / отправитель / получатель" stats="8/8" open={!collapsed["s2"]} onToggle={() => toggle("s2")}>
          <div className="space-y-1.5">
            <FieldRow label="Декларант" value='ООО "Альфа Импорт"' state="confirmed" source="Контракт" confidence={99} selected={selectedField === "fd1"} onClick={() => onFieldSelect("fd1")} />
            <FieldRow label="Отправитель" value="Shanghai Electronics Co., Ltd" state="ai" source="Инвойс · стр.1" confidence={97} selected={selectedField === "fd2"} onClick={() => onFieldSelect("fd2")} />
            <FieldRow label="Получатель" value='ООО "Альфа Импорт"' state="manual" source="Изменено вручную · Пользователь" selected={selectedField === "fd3"} onClick={() => onFieldSelect("fd3")} />
            <FieldRow label="ИНН декларанта" value="7701234567" state="confirmed" source="Контракт" confidence={99} selected={selectedField === "fd4"} onClick={() => onFieldSelect("fd4")} />
            <FieldRow label="КПП декларанта" value="770101001" state="ai" source="Контракт" confidence={98} selected={selectedField === "fd5"} onClick={() => onFieldSelect("fd5")} />
            <FieldRow label="Адрес получателя" value="г. Москва, ул. Складская, д. 15" state="manual" source="Изменено вручную · Пользователь" selected={selectedField === "fd6"} onClick={() => onFieldSelect("fd6")} />
          </div>
        </Section>
        </div>

        {/* Section 3: Коммерческие данные */}
        <div id="section-commercial">
        <Section title="Коммерческие данные" stats="7/8 · 1 предупреждение" warn open={!collapsed["s3"]} onToggle={() => toggle("s3")}>
          <div className="space-y-1.5">
            <FieldRow label="Номер инвойса" value="INV-2026-0847" state="confirmed" source="Инвойс · стр.1" confidence={99} selected={selectedField === "fc1"} onClick={() => onFieldSelect("fc1")} />
            <FieldRow label="Дата инвойса" value="12.02.2026" state="ai" source="Инвойс · стр.1" confidence={98} selected={selectedField === "fc2"} onClick={() => onFieldSelect("fc2")} />
            <FieldRow label="Номер контракта" value="AE-2026/0112" state="confirmed" source="Контракт · стр.1" confidence={99} selected={selectedField === "fc3"} onClick={() => onFieldSelect("fc3")} />
            <FieldRow label="Графа 22. Валюта и сумма по счету" value="USD 12 540,00" state="conflict" source="Конфликт · 2 источника" selected={selectedField === "fc4"} onClick={() => onFieldSelect("fc4")} />
            <FieldRow label="Графа 24. Характер сделки" value="010" state="manual" source="Изменено вручную · Пользователь" selected={selectedField === "fc5"} onClick={() => onFieldSelect("fc5")} />
            <FieldRow label="Влюта контракта" value="USD" state="ai" source="Контракт" confidence={99} selected={selectedField === "fc6"} onClick={() => onFieldSelect("fc6")} />
            <FieldRow label="Общая стоимость" value="USD 12 540,00" state="ai" source="Инвойс" confidence={92} selected={selectedField === "fc7"} onClick={() => onFieldSelect("fc7")} />
            <FieldRow label="Графа 20. Условия поставки" value="" state="empty" selected={selectedField === "fc8"} onClick={() => onFieldSelect("fc8")} />
          </div>
        </Section>
        </div>

        {/* Section 4: Товарные позиции */}
        <div id="section-goods">
        <Section title="Товарные позиции" stats="3 позиции · 2 замечания" warn open={!collapsed["s4"]} onToggle={() => toggle("s4")}>
          <div className="bg-white rounded-xl border border-slate-200/70 overflow-hidden">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200/70 text-slate-400 text-left">
                  <th className="px-3 py-2" style={{ fontWeight: 500 }}>№</th>
                  <th className="px-3 py-2" style={{ fontWeight: 500 }}>Описание</th>
                  <th className="px-3 py-2" style={{ fontWeight: 500 }}>Код ТН ВЭД</th>
                  <th className="px-3 py-2" style={{ fontWeight: 500 }}>Кол-во</th>
                  <th className="px-3 py-2" style={{ fontWeight: 500 }}>Вес, кг</th>
                  <th className="px-3 py-2" style={{ fontWeight: 500 }}>Стоимость</th>
                  <th className="px-3 py-2" style={{ fontWeight: 500 }}>Страна</th>
                  <th className="px-3 py-2 text-right" style={{ fontWeight: 500 }}>Статус</th>
                </tr>
              </thead>
              <tbody>
                <GoodsRow n={1} desc="Микросхемы интегральные" code="8542 31 000 0" qty="5 000 шт" weight="120,5" cost="USD 8 200,00" country="CN" status="ok"
                  selected={selectedField === "g1"} onClick={() => onFieldSelect("g1")} />
                <GoodsRow n={2} desc="Конденсаторы керамические" code="8532 24 000 0" qty="10 000 шт" weight="85,3" cost="USD 2 840,00" country="CN" status="review"
                  selected={selectedField === "g2"} onClick={() => onFieldSelect("g2")} />
                <GoodsRow n={3} desc="Резисторы SMD" code="8533 21 000 0" qty="20 000 шт" weight="42,1" cost="USD 1 500,00" country="CN" status="conflict"
                  selected={selectedField === "g3"} onClick={() => onFieldSelect("g3")} />
              </tbody>
            </table>
          </div>
        </Section>
        </div>

        {/* Section 5: Транспорт */}
        <div id="section-transport">
        <Section title="Транспорт" stats="6/6" open={collapsed["s5"] === false} onToggle={() => toggle("s5")}>
          <div className="space-y-1.5">
            <FieldRow label="Вид транспорта на границе" value="Морской — 10" state="ai" source="Транспортный документ" confidence={97} />
            <FieldRow label="Транспортное средство на границе" value="EVER GIVEN / IMO 9811000" state="ai" source="Коносамент · стр.1" confidence={94} />
            <FieldRow label="Вид транспорта внутри страны" value="Автомобильный — 30" state="manual" source="Изменено вручную · Пользователь" />
          </div>
        </Section>
        </div>

        <div className="h-6" />
      </div>
    </div>
  );
}

function Section({ title, stats, warn, open, onToggle, children }: {
  title: string; stats: string; warn?: boolean; open: boolean; onToggle: () => void; children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200/70 bg-white overflow-hidden shadow-sm shadow-slate-100">
      <button onClick={onToggle} className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-50/50 transition-colors">
        <div className="flex items-center gap-2">
          {open ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
          <span className="text-[12px] text-slate-900" style={{ fontWeight: 600 }}>{title}</span>
        </div>
        <div className="flex items-center gap-2">
          {warn && <AlertTriangle className="w-3 h-3 text-amber-500" />}
          <span className="text-[10px] text-slate-400">{stats}</span>
          {!warn && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
        </div>
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

function GoodsRow({ n, desc, code, qty, weight, cost, country, status, selected, onClick }: {
  n: number; desc: string; code: string; qty: string; weight: string; cost: string; country: string; status: "ok" | "review" | "conflict"; selected?: boolean; onClick?: () => void;
}) {
  const rowBg = status === "review" ? "bg-amber-50/30" : status === "conflict" ? "bg-orange-50/30" : "";
  const statusEl = status === "ok"
    ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200/70 text-emerald-600 text-[9px]"><CheckCircle2 className="w-2.5 h-2.5" />OK</span>
    : status === "review"
      ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-600 text-[9px]"><AlertTriangle className="w-2.5 h-2.5" />Проверка</span>
      : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-orange-50 border border-orange-200 text-orange-600 text-[9px]"><AlertTriangle className="w-2.5 h-2.5" />Конфликт</span>;

  return (
    <tr className={`border-b border-slate-100/70 hover:bg-slate-50/50 cursor-pointer transition-colors ${rowBg} ${selected ? "ring-1 ring-inset ring-slate-300" : ""}`} onClick={onClick}>
      <td className="px-3 py-2.5 text-slate-500">{n}</td>
      <td className="px-3 py-2.5 text-slate-800" style={{ fontWeight: 450 }}>{desc}</td>
      <td className="px-3 py-2.5 font-mono text-[10px] text-slate-600">{code}</td>
      <td className="px-3 py-2.5 text-slate-600">{qty}</td>
      <td className="px-3 py-2.5 text-slate-600">{weight}</td>
      <td className="px-3 py-2.5 text-slate-700" style={{ fontWeight: 450 }}>{cost}</td>
      <td className="px-3 py-2.5 text-slate-500">{country}</td>
      <td className="px-3 py-2.5 text-right">{statusEl}</td>
    </tr>
  );
}