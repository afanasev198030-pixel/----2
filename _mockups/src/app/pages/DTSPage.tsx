import { ArrowLeft, FileText, FileCode, Download, Clock, Sparkles } from "lucide-react";
import { useNavigate } from "react-router";

export function DTSPage() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-full flex flex-col bg-[#f5f6f8] overflow-hidden" style={{ minWidth: 1280 }}>
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-slate-200/80 px-6 py-2.5 flex items-center justify-between" style={{ minHeight: 56 }}>
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="h-5 w-px bg-slate-200" />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[13px] text-slate-900" style={{ fontWeight: 600 }}>ДТС-1 — DC-2026-001245</span>
              <span className="text-[11px] text-slate-400">·</span>
              <span className="text-[12px] text-slate-500">ООО Альфа Импорт</span>
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
              <Clock className="w-3 h-3" />
              <span>Сформировано сегодня в 14:35</span>
              <span className="mx-1">·</span>
              <Sparkles className="w-3 h-3 text-violet-400" />
              <span>Автозаполнение AI</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-50 border border-violet-200 text-violet-700 text-[11px]" style={{ fontWeight: 500 }}>
            Форма ДТС-1
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-[12px] hover:bg-slate-50 transition-colors bg-white">
            <FileText className="w-3.5 h-3.5" />PDF
          </button>
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-[12px] hover:bg-slate-50 transition-colors bg-white">
            <FileCode className="w-3.5 h-3.5" />XML
          </button>
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-[12px] hover:bg-slate-50 transition-colors bg-white">
            <Download className="w-3.5 h-3.5" />Скачать
          </button>
        </div>
      </header>

      {/* Form content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1100px] mx-auto py-6 px-4">
          <Sheet1 />
          <div className="h-8" />
          <Sheet2 />
        </div>
      </main>
    </div>
  );
}

/* ───── Shared helpers ───── */
const cellCls = "border border-slate-300 px-2.5 py-1.5 text-[11px] text-slate-800 align-top";
const headerCellCls = `${cellCls} bg-slate-50 text-slate-500`;
const labelCls = "text-[10px] text-slate-400 leading-tight";
const valueCls = "text-[12px] text-slate-900" ;

function XMark() {
  return <span className="text-[14px] text-slate-900" style={{ fontWeight: 700 }}>✕</span>;
}
function EmptyMark() {
  return <span className="text-slate-300">—</span>;
}

function YesNoCell({ yes }: { yes: boolean }) {
  return (
    <td className={`${cellCls} text-center w-10`}>
      {yes ? <XMark /> : <EmptyMark />}
    </td>
  );
}

/* ───── ЛИСТ 1 ───── */
function Sheet1() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Title bar */}
      <div className="bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-[14px] text-slate-900" style={{ fontWeight: 600 }}>ДЕКЛАРАЦИЯ ТАМОЖЕННОЙ СТОИМОСТИ</span>
          <span className="text-[12px] text-slate-400">Форма ДТС-1</span>
        </div>
        <span className="text-[12px] text-slate-500">Лист № <span style={{ fontWeight: 600 }}>1</span></span>
      </div>

      <div className="p-5 space-y-0">
        <table className="w-full border-collapse">
          <tbody>
            {/* Row 1 — Продавец */}
            <tr>
              <td className={`${cellCls} w-[55%]`} rowSpan={2}>
                <div className={labelCls}>1. Продавец</div>
                <div className={valueCls} style={{ fontWeight: 500 }}>ZED GROUP TRADING CO., LIMITED</div>
                <div className="text-[11px] text-slate-600 mt-0.5">ГОНКОНГ, MONG KOK, HONG KONG, FLAT/1005 10/F HO KING COMMERCIAL CENTER, FA YUEN</div>
              </td>
              <td className={cellCls}>
                <div className={labelCls}>ДЛЯ ОТМЕТОК ТАМОЖЕННОГО ОРГАНА</div>
                <div className={valueCls} style={{ fontWeight: 500 }}>10005030/271125/5338816</div>
              </td>
            </tr>

            {/* Row 2a — Покупатель */}
            <tr>
              <td className={cellCls} rowSpan={2}>
                <div className={labelCls}>3. Условия поставки</div>
                <div className={valueCls} style={{ fontWeight: 500 }}>EXW GUANGZHOU</div>
                <div className={`${labelCls} mt-2`}>4. Номер и дата счета (чеков)</div>
                <div className={valueCls} style={{ fontWeight: 500 }}>AGZED20251009/2025 ОТ 09.10.25</div>
              </td>
            </tr>
            <tr>
              <td className={cellCls}>
                <div className={labelCls}>2. (а) Покупатель</div>
                <div className={valueCls} style={{ fontWeight: 500 }}>ООО "АГ-ЛОГИСТИК"</div>
                <div className="text-[11px] text-slate-600">РОССИЯ, ВН.ТЕР.Г. МУНИЦИПАЛЬНЫЙ ОКРУГ ВОЙКОВСКИЙ, Г. МОСКВА, Ш. ЛЕНИНГРАДСКОЕ, Д. 16А, СТР.3</div>
                <div className="text-[11px] text-slate-500 mt-0.5">9728100494/774301001 · 1237700467652</div>
              </td>
            </tr>

            {/* Row 2b — Декларант */}
            <tr>
              <td className={cellCls}>
                <div className={labelCls}>2. (б) Декларант</div>
                <div className={valueCls} style={{ fontWeight: 500 }}>ООО "АГ-ЛОГИСТИК"</div>
                <div className="text-[11px] text-slate-600">РОССИЯ, ВН.ТЕР.Г. МУНИЦИПАЛЬНЫЙ ОКРУГ</div>
                <div className="text-[11px] text-slate-500 mt-0.5">9728100494/774301001 · 1237700467652</div>
              </td>
              <td className={cellCls}>
                <div className={labelCls}>5. Номер и дата контракта (договора, соглашения)</div>
                <div className={valueCls} style={{ fontWeight: 500 }}>AG-ZED/2025/0029 ОТ 23.01.25</div>
              </td>
            </tr>

            {/* Row 6 — Документы */}
            <tr>
              <td className={cellCls} colSpan={2}>
                <div className={labelCls}>6. Номера и даты документов, имеющих отношение к сведениям, указанным в графах 7–9</div>
                <div className="text-[11px] text-slate-500 mt-1 italic">—</div>
              </td>
            </tr>
          </tbody>
        </table>

        {/* Questions 7–8 */}
        <table className="w-full border-collapse mt-[-1px]">
          <thead>
            <tr>
              <th className={`${headerCellCls} text-left`} style={{ width: "70%" }}>&nbsp;</th>
              <th className={`${headerCellCls} text-center w-10`}>ДА</th>
              <th className={`${headerCellCls} text-center w-10`}>НЕТ</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className={cellCls} colSpan={3}>
                <span style={{ fontWeight: 500 }}>7. (а)</span> Имеются ли ВЗАИМОСВЯЗЬ между продавцом и покупателем в значении, указанном в статье 37 Таможенного кодекса Евразийского экономического союза?
              </td>
            </tr>
            <tr>
              <td className={cellCls}>&nbsp;</td>
              <YesNoCell yes={false} />
              <YesNoCell yes={true} />
            </tr>
            <tr>
              <td className={cellCls}>
                <span style={{ fontWeight: 500 }}>(б)</span> Оказала ли взаимосвязь между продавцом и покупателем влияние на цену, фактически уплаченную или подлежащую уплате за ввозимые товары?
              </td>
              <YesNoCell yes={false} />
              <YesNoCell yes={true} />
            </tr>
            <tr>
              <td className={cellCls}>
                <span style={{ fontWeight: 500 }}>(в)</span> Стоимость сделки с ввозимыми товарами близка к одной из возможных проверочных величин, указанных пункте 5 статьи 39 Таможенного кодекса?
              </td>
              <YesNoCell yes={false} />
              <YesNoCell yes={true} />
            </tr>

            <tr>
              <td className={cellCls} colSpan={3}>
                <span style={{ fontWeight: 500 }}>8. (а)</span> Имеются ли ОГРАНИЧЕНИЯ в отношении прав покупателя на пользование и распоряжение ввозимыми товарами?
              </td>
            </tr>
            <tr>
              <td className={cellCls}>&nbsp;</td>
              <YesNoCell yes={false} />
              <YesNoCell yes={true} />
            </tr>
            <tr>
              <td className={cellCls}>
                <span style={{ fontWeight: 500 }}>(б)</span> Зависит ли продажа товаров или их цена от соблюдения УСЛОВИЙ или ОБЯЗАТЕЛЬСТВ, оказывающих влияние на цену ввозимых товаров?
              </td>
              <YesNoCell yes={false} />
              <YesNoCell yes={true} />
            </tr>

            <tr>
              <td className={cellCls} colSpan={3}>
                <span style={{ fontWeight: 500 }}>9.</span> (а) Имеются ли ДОГОВОРНЫЕ ОТНОШЕНИЯ (лицензионный договор, субконцессия, договор коммерческой концессии)?
              </td>
            </tr>
            <tr>
              <td className={cellCls}>&nbsp;</td>
              <YesNoCell yes={false} />
              <YesNoCell yes={true} />
            </tr>
            <tr>
              <td className={cellCls}>
                <span style={{ fontWeight: 500 }}>(б)</span> Предусмотрены ли ЛИЦЕНЗИОННЫЕ и иные подобные ПЛАТЕЖИ за использование объектов ИНТЕЛЛЕКТУАЛЬНОЙ СОБСТВЕННОСТИ?
              </td>
              <YesNoCell yes={false} />
              <YesNoCell yes={true} />
            </tr>
            <tr>
              <td className={cellCls}>
                <span style={{ fontWeight: 500 }}>(в)</span> Зависит ли продажа товаров от соблюдения условий, в соответствии с которыми ЧАСТЬ ДОХОДА (ВЫРУЧКИ) причитается прямо или косвенно продавцу?
              </td>
              <YesNoCell yes={false} />
              <YesNoCell yes={true} />
            </tr>
          </tbody>
        </table>

        {/* Bottom section */}
        <table className="w-full border-collapse mt-[-1px]">
          <tbody>
            <tr>
              <td className={cellCls} style={{ width: "50%" }}>
                <div className={labelCls}>{'<*>'} Лица являются взаимосвязанными исключительно в том случае, если они:</div>
                <div className="text-[10px] text-slate-400 mt-1 leading-relaxed">
                  (а) являются сотрудниками или директорами организаций друг друга;<br/>
                  (б) являются юридически признанными деловыми партнёрами;<br/>
                  (в) являются работодателем и работником;<br/>
                  (г) какое-либо лицо прямо или косвенно владеет, контролирует или является держателем 5 и более процентов голосующих акций обоих из них;<br/>
                  (д) оба из них прямо или косвенно контролируются третьим лицом;<br/>
                  (е) являются родственниками или членами одной семьи.
                </div>
              </td>
              <td className={cellCls}>
                <div className="flex gap-8 mb-3">
                  <div>
                    <div className={labelCls}>10</div>
                  </div>
                  <div>
                    <div className={labelCls}>(а) Количество добавочных листов</div>
                    <div className={valueCls} style={{ fontWeight: 500 }}>—</div>
                  </div>
                </div>
                <div className="border-t border-slate-200 pt-2 mt-2">
                  <div className={labelCls}>(б) Сведения о лице, заполнившем ДТС</div>
                  <div className={valueCls} style={{ fontWeight: 500 }}>ШИРОВА ВИКТОРИЯ СЕРГЕЕВНА</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">ПАСФ 92 163919 16.11.2022</div>
                  <div className="text-[11px] text-slate-500">89953604290</div>
                  <div className="text-[11px] text-slate-600 mt-1" style={{ fontWeight: 500 }}>СПЕЦИАЛИСТ ПО ТО</div>
                </div>
                <div className="border-t border-slate-200 pt-2 mt-2">
                  <div className={labelCls}>Дата</div>
                  <div className={valueCls} style={{ fontWeight: 500 }}>27.11.25</div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ───── ЛИСТ 2 (Расчёт) ───── */
function Sheet2() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-[14px] text-slate-900" style={{ fontWeight: 600 }}>Метод 1</span>
          <span className="text-[12px] text-slate-400">Форма ДТС-1 · Лист № 2</span>
        </div>
        <span className="text-[12px] text-slate-500">Товар № <span style={{ fontWeight: 600 }}>1</span></span>
      </div>

      <div className="p-5">
        <table className="w-full border-collapse">
          <tbody>
            {/* Header row */}
            <tr>
              <td className={`${headerCellCls}`} style={{ width: "35%" }}>
                <div className={labelCls}>ДЛЯ ОТМЕТОК ТАМОЖЕННОГО ОРГАНА</div>
                <div className={valueCls} style={{ fontWeight: 500 }}>10005030/171225/5367378</div>
              </td>
              <td className={`${headerCellCls} text-center`}>
                <div className={labelCls}>Товар №</div>
                <div className={valueCls} style={{ fontWeight: 600 }}>1</div>
              </td>
              <td className={`${headerCellCls} text-center`}>
                <div className={labelCls}>Код ТН ВЭД ЕАЭС</div>
                <div className={valueCls} style={{ fontWeight: 500 }}>8525891900</div>
              </td>
              <td className={`${headerCellCls} text-center text-slate-300`}>Товар №</td>
              <td className={`${headerCellCls} text-center text-slate-300`}>Код ТН ВЭД ЕАЭС</td>
            </tr>

            {/* Графа 11 */}
            <tr>
              <td className={`${cellCls}`} colSpan={2}>
                <div className="flex items-start gap-2">
                  <span className="text-[10px] text-slate-400 shrink-0" style={{ fontWeight: 500 }}>ОСНОВА ДЛЯ РАСЧЁТА</span>
                  <div>
                    <div className={labelCls}>11 (а) цена, фактически уплаченная или подлежащая уплате за ввозимые товары в ВАЛЮТЕ СЧЁТА</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">(курс пересчёта <span style={{ fontWeight: 500 }}>USD 79.4302</span>)</div>
                  </div>
                </div>
              </td>
              <td className={`${cellCls} text-right`}>
                <div className={valueCls} style={{ fontWeight: 600 }}>239 400.00</div>
              </td>
              <td className={cellCls} colSpan={2}></td>
            </tr>
            <tr>
              <td className={cellCls} colSpan={2}>
                <div className="text-[10px] text-slate-400 pl-4">в НАЦИОНАЛЬНОЙ ВАЛЮТЕ</div>
              </td>
              <td className={`${cellCls} text-right`}>
                <div className={valueCls} style={{ fontWeight: 600 }}>19 015 589.88</div>
              </td>
              <td className={cellCls} colSpan={2}></td>
            </tr>
            <tr>
              <td className={cellCls} colSpan={2}>
                <div className={labelCls}>(б) Косвенные платежи (условия или обязательства) в НАЦИОНАЛЬНОЙ ВАЛЮТЕ</div>
              </td>
              <td className={`${cellCls} text-right text-slate-300`}>—</td>
              <td className={cellCls} colSpan={2}></td>
            </tr>

            {/* Графа 12 */}
            <CalcRow num="12" label="Итого по разделам «а» и «б» графы 11 в национальной валюте" value="19 015 589.88" highlight />

            {/* Графы 13–16 */}
            <tr>
              <td className={cellCls} rowSpan={8}>
                <span className="text-[10px] text-slate-400" style={{ fontWeight: 500 }}>ДОПОЛНИТЕЛЬНЫЕ НАЧИСЛЕНИЯ:</span>
                <div className="text-[9px] text-slate-400 mt-1 leading-relaxed">
                  расходы в национальной валюте, которые не включены в графу 12 {'<*>'}
                </div>
              </td>
            </tr>
            <CalcRowInner num="13" label="Расходы покупателя: (а) вознаграждения посреднику (агенту), брокеру" />
            <CalcRowInner num="" label="(б) тару и упаковку, в том числе стоимость упаковочных материалов и работ по упаковке" />
            <CalcRowInner num="14" label="Соответствующая обратная распределённая стоимость товаров и услуг, прямо или косвенно предоставленных покупателем бесплатно" />
            <CalcRowInner num="15" label="Лицензионные и иные подобные платежи за использование объектов интеллектуальной собственности" />
            <CalcRowInner num="16" label="Часть дохода (выручки), полученного в результате последующей продажи" />
            <CalcRowInner num="17" label="Расходы по перевозке (транспортировке) ввозимых товаров до Т/П АЭРОПОРТ ШЕРЕМЕТЬЕВО (ГРУЗОВОЙ)" value="110 732.16" />
            <CalcRowInner num="18" label="Расходы на погрузку, разгрузку или перегрузку ввозимых товаров" />

            <CalcRowInner num="19" label="Расходы на страхование в связи с операциями, указанными в графах 17 и 18" />
            <CalcRow num="20" label="Итого по графам 13–19 в национальной валюте" value="110 732.16" highlight />

            {/* Вычеты */}
            <tr>
              <td className={cellCls} rowSpan={5}>
                <span className="text-[10px] text-slate-400" style={{ fontWeight: 500 }}>ВЫЧЕТЫ:</span>
                <div className="text-[9px] text-slate-400 mt-1 leading-relaxed">
                  расходы в национальной валюте, которые включены в графу 12 {'<*>'}
                </div>
              </td>
            </tr>
            <CalcRowInner num="21" label="Расходы на строительство, возведение, сборку, монтаж, обслуживание после ввоза товаров" />
            <CalcRowInner num="22" label="Расходы по перевозке (транспортировке) ввозимых товаров по территории ЕАЭС" />
            <CalcRowInner num="23" label="Сумма пошлин, налогов и сборов" />
            <CalcRow num="24" label="Итого по графам 21–23 в национальной валюте" value="—" />

            {/* Графа 25 */}
            <tr>
              <td className={cellCls} colSpan={2}>
                <div style={{ fontWeight: 500 }} className="text-[11px] text-slate-800">25. Таможенная стоимость ввозимых товаров (12 + 20 − 24):</div>
              </td>
              <td className={cellCls} colSpan={3}></td>
            </tr>
            <tr>
              <td className={`${cellCls} pl-6`}>
                <div className={labelCls}>(а) в НАЦИОНАЛЬНОЙ ВАЛЮТЕ</div>
              </td>
              <td className={cellCls} colSpan={2}>
                <div className="text-right text-[13px] text-emerald-700" style={{ fontWeight: 700 }}>19 126 322.04</div>
              </td>
              <td className={cellCls} colSpan={2}></td>
            </tr>
            <tr>
              <td className={`${cellCls} pl-6`}>
                <div className={labelCls}>(б) в ДОЛЛАРАХ США (курс пересчёта 79.4302)</div>
              </td>
              <td className={cellCls} colSpan={2}>
                <div className="text-right text-[13px] text-slate-900" style={{ fontWeight: 600 }}>240 794.08</div>
              </td>
              <td className={cellCls} colSpan={2}></td>
            </tr>

            {/* Footer */}
            <tr>
              <td className={cellCls} colSpan={2}>
                <div className={labelCls}>Порядковый номер товара в ДТС-1 и номер графы ДТС-1</div>
                <div className="flex gap-4 mt-1">
                  <span className={valueCls}>1</span>
                  <span className={valueCls}>17</span>
                </div>
              </td>
              <td className={cellCls}>
                <div className={labelCls}>Буквенный код валюты, сумма</div>
                <div className={valueCls}>CNY 9937.00</div>
              </td>
              <td className={cellCls} colSpan={2}>
                <div className={labelCls}>Курс пересчёта</div>
                <div className={valueCls}>11.2567</div>
              </td>
            </tr>

            <tr>
              <td className={cellCls} colSpan={3}>
                <div className={labelCls}>Дополнительные данные</div>
                <div className={valueCls} style={{ fontWeight: 500 }}>СЧЁТ ЗА ПЕРЕВОЗКУ № 999-38226521 ОТ 13.12.2025</div>
              </td>
              <td className={cellCls} colSpan={2}>
                <div className={labelCls}>Дата, подпись, печать</div>
                <div className={valueCls} style={{ fontWeight: 500 }}>ШИРОВА ВИКТОРИЯ СЕРГЕЕВНА</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CalcRow({ num, label, value, highlight }: { num: string; label: string; value: string; highlight?: boolean }) {
  return (
    <tr>
      <td className={cellCls} colSpan={2}>
        <div className="flex items-start gap-1.5">
          <span className="text-[10px] text-slate-400 shrink-0" style={{ fontWeight: 500 }}>{num}</span>
          <span className="text-[11px] text-slate-700">{label}</span>
        </div>
      </td>
      <td className={`${cellCls} text-right ${highlight ? "bg-slate-50" : ""}`}>
        <div className={`${valueCls}`} style={{ fontWeight: highlight ? 600 : 400 }}>{value}</div>
      </td>
      <td className={cellCls} colSpan={2}></td>
    </tr>
  );
}

function CalcRowInner({ num, label, value }: { num?: string; label: string; value?: string }) {
  return (
    <tr>
      <td className={cellCls}>
        <div className="flex items-start gap-1.5 pl-2">
          {num && <span className="text-[10px] text-slate-400 shrink-0" style={{ fontWeight: 500 }}>{num}</span>}
          <span className="text-[10px] text-slate-600">{label}</span>
        </div>
      </td>
      <td className={`${cellCls} text-right`}>
        {value ? (
          <div className={valueCls} style={{ fontWeight: 500 }}>{value}</div>
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>
      <td className={cellCls} colSpan={2}></td>
    </tr>
  );
}