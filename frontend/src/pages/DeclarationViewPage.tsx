import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, Button, CircularProgress, Typography } from '@mui/material';
import { Print as PrintIcon, Edit as EditIcon, PictureAsPdf } from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import client from '../api/client';
import { calculatePayments, PaymentResult } from '../api/calc';

const f = (v: any) => v ?? '';
const num = (v: any, d = 2) =>
  v ? Number(v).toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d }) : '';

const FORM: React.CSSProperties = {
  fontFamily: '"Courier New", monospace',
  fontSize: 10,
  lineHeight: 1.2,
  border: '2px solid #000',
  background: '#fff',
  width: '100%',
  maxWidth: 1000,
  margin: '0 auto',
  boxSizing: 'border-box',
  textTransform: 'uppercase',
};

const bR = '1px solid #000';
const bB = '1px solid #000';
const bT = '2px solid #000';

interface CellProps {
  w: string;
  h?: number;
  label?: string;
  br?: boolean;
  bb?: boolean;
  bt?: boolean;
  bold?: boolean;
  center?: boolean;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}

const G = ({ w, h, label, br, bb, bt, bold, center, children, style }: CellProps) => (
  <div
    style={{
      width: w,
      minHeight: h || 20,
      padding: '1px 3px',
      borderRight: br ? bR : undefined,
      borderBottom: bb ? bB : undefined,
      borderTop: bt ? bT : undefined,
      fontWeight: bold ? 700 : 400,
      textAlign: center ? 'center' : 'left',
      fontSize: 10,
      lineHeight: 1.2,
      overflow: 'hidden',
      boxSizing: 'border-box',
      ...style,
    }}
  >
    {label && <span style={{ fontSize: 7, color: '#555', fontWeight: 700 }}>{label} </span>}
    {children}
  </div>
);

const Row = ({ children, thick, h }: { children: React.ReactNode; thick?: boolean; h?: number }) => (
  <div style={{ display: 'flex', borderBottom: thick ? bT : bB, minHeight: h || 20 }}>{children}</div>
);

const ItemBlock = ({ itm, pi, docs }: { itm: any; pi: any; docs?: any[] }) => (
  <>
    <div style={{ display: 'flex', borderBottom: bB }}>
      <div style={{ width: '57%', borderRight: bR, minHeight: 140, padding: '1px 3px', fontSize: 10 }}>
        <span style={{ fontSize: 7, color: '#555', fontWeight: 700 }}>31 </span>
        Грузовые места и описание товаров<br />
        Маркировка и количество — Номера контейнеров — Количество и отличительные особенности
        <br />
        <span style={{ whiteSpace: 'pre-line' }}>{f(itm.description || itm.commercial_name)}</span>
        <br />
        {itm.additional_unit_qty != null && (
          <>
            {num(itm.additional_unit_qty, 0)} {f(itm.additional_unit) || 'ШТ'}
          </>
        )}
      </div>
      <div style={{ width: '43%', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', borderBottom: bB }}>
          <G w="35%" label="32" br>
            Товар
            <br />
            <b>№{f(itm.item_no)}</b>
          </G>
          <G w="65%" label="33">
            Код товара
            <br />
            <b style={{ fontSize: 12 }}>{f(itm.hs_code)}</b>
          </G>
        </div>
        <div style={{ display: 'flex', borderBottom: bB }}>
          <G w="35%" label="34" br>
            Код страны происх.
            <br />
            <span style={{ fontSize: 7 }}>a</span> <b>{f(itm.country_origin_code)}</b>{' '}
            <span style={{ fontSize: 7 }}>b</span> {f(itm.country_origin_pref_code)}
          </G>
          <G w="40%" label="35" br>
            Вес брутто (кг)
            <br />
            <b>{num(itm.gross_weight, 3)}</b>
          </G>
          <G w="25%" label="36">
            Преференция
            <br />
            {f(itm.preference_code)}
          </G>
        </div>
        <div style={{ display: 'flex', borderBottom: bB }}>
          <G w="35%" label="37" br>
            ПРОЦЕДУРА
            <br />
            <b>{f(itm.procedure_code)}</b>
          </G>
          <G w="40%" label="38" br>
            Вес нетто (кг)
            <br />
            <b>{num(itm.net_weight, 3)}</b>
          </G>
          <G w="25%" label="39">
            Квота
            <br />
            {f(itm.quota_info)}
          </G>
        </div>
        <div style={{ borderBottom: bB }}>
          <G w="100%" label="40">
            Общая декларация/Предшествующий документ
            <br />
            {f(itm.prev_doc_ref)}
          </G>
        </div>
        <div style={{ display: 'flex' }}>
          <G w="35%" label="41" br>
            Дополнит. единицы
            <br />
            {itm.additional_unit_qty
              ? `${num(itm.additional_unit_qty, 0)} ${f(itm.additional_unit) || 'ШТ'}`
              : ''}
          </G>
          <G w="40%" label="42" br>
            Цена товара
            <br />
            <b>{num(itm.unit_price, 4)}</b>
          </G>
          <G w="25%" label="43">
            Код МОС
            <br />
            {f(itm.mos_method_code)}
          </G>
        </div>
      </div>
    </div>
    <div style={{ display: 'flex', borderBottom: bB }}>
      <div style={{ width: '57%', borderRight: bR, minHeight: 36, padding: '1px 3px', fontSize: 10 }}>
        <span style={{ fontSize: 7, color: '#555', fontWeight: 700 }}>44 </span>
        Дополнит. информация / Представл. документы
        <br />
        {(docs && docs.length > 0 ? docs : itm.documents_json || []).map((doc: any, i: number) => {
          const code = doc.doc_kind_code || doc.code || '';
          const num = doc.doc_number || doc.number || '';
          const dt = doc.doc_date || doc.date || '';
          const pk = doc.presenting_kind_code || doc.marker || '';
          return (
            <span key={i}>
              {code}{pk ? `/${pk}` : ''} {num} {dt}
              <br />
            </span>
          );
        })}
      </div>
      <div style={{ width: '43%', display: 'flex', flexDirection: 'column' }}>
        <G w="100%" label="45" bb>
          Таможенная стоимость
          <br />
          <b style={{ fontSize: 12 }}>{num(pi?.customs_value_rub || itm.customs_value_rub)}</b>
        </G>
        <G w="100%" label="46">
          Статистическая стоимость
          <br />
          <b>{num(itm.statistical_value_usd)}</b>
        </G>
      </div>
    </div>
  </>
);

const payTh: React.CSSProperties = { border: '1px solid #999', padding: '1px 2px', textAlign: 'left', fontSize: 9 };
const payTd: React.CSSProperties = { border: '1px solid #999', padding: '1px 2px', fontSize: 9 };

const PaymentRows = ({
  totals,
  paymentItems,
}: {
  totals: PaymentResult['totals'] | undefined;
  paymentItems: PaymentResult['items'] | undefined;
}) => (
  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
    <thead>
      <tr>
        <th style={payTh}>Вид</th>
        <th style={{ ...payTh, textAlign: 'right' }}>Основа начисления</th>
        <th style={{ ...payTh, textAlign: 'center' }}>Ставка</th>
        <th style={{ ...payTh, textAlign: 'right' }}>Сумма</th>
        <th style={payTh}>СП</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style={payTd}>1010</td>
        <td style={{ ...payTd, textAlign: 'right' }}>{num(totals?.total_customs_value)}</td>
        <td style={{ ...payTd, textAlign: 'center' }}>—</td>
        <td style={{ ...payTd, textAlign: 'right' }}>{num(totals?.customs_fee)}</td>
        <td style={payTd}>ИУ</td>
      </tr>
      <tr>
        <td style={payTd}>2010</td>
        <td style={{ ...payTd, textAlign: 'right' }}>{num(totals?.total_customs_value)}</td>
        <td style={{ ...payTd, textAlign: 'center' }}>{paymentItems?.[0]?.duty?.rate || 0}%</td>
        <td style={{ ...payTd, textAlign: 'right' }}>{num(totals?.total_duty)}</td>
        <td style={payTd}>ИУ</td>
      </tr>
      <tr>
        <td style={payTd}>5010</td>
        <td style={{ ...payTd, textAlign: 'right' }}>{num(paymentItems?.[0]?.vat?.base)}</td>
        <td style={{ ...payTd, textAlign: 'center' }}>{paymentItems?.[0]?.vat?.rate || 20}%</td>
        <td style={{ ...payTd, textAlign: 'right' }}>{num(totals?.total_vat)}</td>
        <td style={payTd}>ИУ</td>
      </tr>
      <tr style={{ fontWeight: 700, borderTop: bT }}>
        <td style={payTd} colSpan={3}>
          Всего:
        </td>
        <td style={{ ...payTd, textAlign: 'right' }}>{num(totals?.grand_total)}</td>
        <td style={payTd} />
      </tr>
    </tbody>
  </table>
);

const DeclarationViewPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [decl, setDecl] = useState<any>(null);
  const [items, setItems] = useState<any[]>([]);
  const [sender, setSender] = useState<any>(null);
  const [receiver, setReceiver] = useState<any>(null);
  const [declarant, setDeclarant] = useState<any>(null);
  const [financial, setFinancial] = useState<any>(null);
  const [payments, setPayments] = useState<PaymentResult | null>(null);
  const [itemDocsMap, setItemDocsMap] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [declResp, itemsResp] = await Promise.all([
          client.get(`/declarations/${id}`),
          client.get(`/declarations/${id}/items`),
        ]);
        const d = declResp.data;
        const its = Array.isArray(itemsResp.data) ? itemsResp.data : itemsResp.data?.items || [];
        setDecl(d);
        setItems(its);

        const docsMap: Record<string, any[]> = {};
        await Promise.all(
          its.map(async (itm: any) => {
            try {
              const r = await client.get(`/declarations/${id}/items/${itm.id}/item-documents/`);
              if (Array.isArray(r.data) && r.data.length > 0) docsMap[itm.id] = r.data;
            } catch {}
          }),
        );
        setItemDocsMap(docsMap);

        const loadCp = async (cpId: string) => {
          try {
            return (await client.get(`/counterparties/${cpId}`)).data;
          } catch {
            return null;
          }
        };
        if (d.sender_counterparty_id) setSender(await loadCp(d.sender_counterparty_id));
        if (d.receiver_counterparty_id) setReceiver(await loadCp(d.receiver_counterparty_id));
        if (d.declarant_counterparty_id) setDeclarant(await loadCp(d.declarant_counterparty_id));
        if (d.financial_counterparty_id) setFinancial(await loadCp(d.financial_counterparty_id));

        if (its.length > 0) {
          try {
            const payItems = its.map((i: any) => ({
              item_no: i.item_no,
              hs_code: i.hs_code || '',
              unit_price: i.unit_price ? Number(i.unit_price) : 0,
              quantity: i.additional_unit_qty ? Number(i.additional_unit_qty) : 1,
              customs_value_rub: i.customs_value_rub ? Number(i.customs_value_rub) : 0,
            }));
            const p = await calculatePayments(
              payItems,
              d.currency_code || 'USD',
              d.exchange_rate ? Number(d.exchange_rate) : undefined,
            );
            setPayments(p);
          } catch (e) {
            console.error('Payment calc error:', e);
          }
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    if (id) load();
  }, [id]);

  if (loading)
    return (
      <AppLayout breadcrumbs={[{ label: 'Декларации', path: '/declarations' }, { label: 'Просмотр ДТ' }]}>
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      </AppLayout>
    );
  if (!decl)
    return (
      <AppLayout breadcrumbs={[{ label: 'Декларации', path: '/declarations' }, { label: 'Просмотр ДТ' }]}>
        <Typography sx={{ py: 4 }}>Не найдена</Typography>
      </AppLayout>
    );

  const totals = payments?.totals;
  const firstItem = items[0] || {};
  const firstPi = payments?.items?.[0];

  const dt2Sheets: any[][] = [];
  for (let i = 1; i < items.length; i += 3) {
    dt2Sheets.push(items.slice(i, i + 3));
  }
  const totalForms = 1 + dt2Sheets.length;

  const cpLine = (cp: any) =>
    cp ? `${cp.name || ''} ${cp.country_code || ''} ${cp.address || ''}` : 'НЕ УКАЗАН';

  return (
    <AppLayout breadcrumbs={[{ label: 'Декларации', path: '/declarations' }, { label: 'Просмотр ДТ' }]}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2, gap: 1 }} className="no-print">
        <Button
          variant="outlined"
          onClick={() => navigate(`/declarations/${id}/dts-view`)}
        >
          Просмотр ДТС
        </Button>
        <Button
          variant="outlined"
          startIcon={<EditIcon />}
          onClick={() => navigate(`/declarations/${id}/edit`)}
        >
          Редактировать
        </Button>
        <Button
          variant="outlined"
          startIcon={<PictureAsPdf />}
          onClick={async () => {
            try {
              const resp = await client.get(`/declarations/${id}/export-pdf`, { responseType: 'blob' });
              const url = window.URL.createObjectURL(new Blob([resp.data], { type: 'application/pdf' }));
              const a = document.createElement('a');
              a.href = url;
              a.download = `DT_${(id || '').slice(0, 8)}.pdf`;
              a.click();
            } catch (e) {
              console.error(e);
            }
          }}
        >
          PDF
        </Button>
        <Button variant="contained" startIcon={<PrintIcon />} onClick={() => window.print()}>
          Печать
        </Button>
      </Box>

      {/* ═══════════════════ ДТ1 — ОСНОВНОЙ ЛИСТ ═══════════════════ */}
      <div className="dt-sheet" style={FORM}>
        {/* ── Заголовок ── */}
        <Row thick>
          <G w="58%" bold center br>
            ДЕКЛАРАЦИЯ НА ТОВАРЫ
          </G>
          <G w="27%" label="1" br>
            <b>{f(decl.type_code)}</b>
          </G>
          <G w="15%" label="А" center />
        </Row>

        {/* ── Графа 2 / 3-4 / 5-7 ── */}
        <Row h={60}>
          <G w="50%" label="2" h={60} br>
            Отправитель/Экспортер
            <br />
            <b>{cpLine(sender)}</b>
          </G>
          <div style={{ width: '25%', borderRight: bR, display: 'flex', flexDirection: 'column' }}>
            <G w="100%" label="3" bb>
              Формы
              <br />
              <b>{f(decl.forms_count) || totalForms}</b>
            </G>
            <G w="100%" label="4">
              Отгр.спец.
              <br />
              {f(decl.specifications_count)}
            </G>
          </div>
          <div style={{ width: '25%', display: 'flex', flexDirection: 'column' }}>
            <G w="100%" label="5" bb>
              Всего т-ов
              <br />
              <b>{f(decl.total_items_count) || items.length}</b>
            </G>
            <G w="100%" label="6" bb>
              Всего мест
              <br />
              <b>{f(decl.total_packages_count)}</b>
            </G>
            <G w="100%" label="7">
              Справочный номер
              <br />
              {f(decl.special_ref_code)}
            </G>
          </div>
        </Row>

        {/* ── Графа 8 / 9 ── */}
        <Row h={60}>
          <G w="50%" label="8" h={60} br>
            Получатель
            <br />
            <b>
              {decl.receiver_counterparty_id && decl.declarant_counterparty_id && decl.receiver_counterparty_id !== decl.declarant_counterparty_id
                ? cpLine(receiver)
                : 'СМ. ГРАФУ 14 ДТ'}
            </b>
          </G>
          <G w="25%" label="9" br>
            Лицо, ответственное за финансовое урегулирование
            <br />
            {decl.financial_counterparty_id && decl.declarant_counterparty_id && decl.financial_counterparty_id !== decl.declarant_counterparty_id
              ? cpLine(financial)
              : 'СМ. ГРАФУ 14 ДТ'}
          </G>
          <div style={{ width: '25%' }} />
        </Row>

        {/* ── Графы 10 / 11 / 12 / 13 ── */}
        <Row>
          <G w="50%" br style={{ visibility: 'hidden', minHeight: 0, padding: 0, height: 0 }} />
          <G w="12%" label="10" br>
            Страна перв. назн./посл. отпр.
            <br />
            {f(decl.country_first_destination_code)}
          </G>
          <G w="13%" label="11" br>
            Торг. страна
            <br />
            <b>{f(decl.trading_country_code)}</b>
          </G>
          <G w="18%" label="12" br>
            Общая таможенная стоимость
            <br />
            <b>{num(totals?.total_customs_value || decl.total_customs_value)}</b>
          </G>
          <G w="7%" label="13" />
        </Row>

        {/* ── Графа 14 / 15 / 15a-b / 17a-b ── */}
        <Row h={44}>
          <G w="50%" label="14" h={44} br>
            Декларант
            <br />
            <b>{declarant ? cpLine(declarant) : cpLine(receiver)}</b>
            <br />
            {f(decl.declarant_inn_kpp)} {f(decl.declarant_ogrn)} {f(decl.declarant_phone)}
          </G>
          <G w="14%" label="15" br>
            Страна отправления
            <br />
            <b>{f(decl.country_dispatch_code)}</b>
          </G>
          <div style={{ width: '11%', borderRight: bR, display: 'flex', flexDirection: 'column' }}>
            <G w="100%" bb>
              <span style={{ fontSize: 7, color: '#555', fontWeight: 700 }}>15 </span>
              Код страны отпр.
            </G>
            <div style={{ display: 'flex' }}>
              <G w="50%" br>
                <span style={{ fontSize: 7 }}>a</span>
                <br />
                {f(decl.country_dispatch_code)}
              </G>
              <G w="50%">
                <span style={{ fontSize: 7 }}>b</span>
              </G>
            </div>
          </div>
          <div style={{ width: '11%', borderRight: bR, display: 'flex', flexDirection: 'column' }}>
            <G w="100%" bb>
              <span style={{ fontSize: 7, color: '#555', fontWeight: 700 }}>17 </span>
              Код страны назнач.
            </G>
            <div style={{ display: 'flex' }}>
              <G w="50%" br>
                <span style={{ fontSize: 7 }}>a</span>
                <br />
                {f(decl.country_destination_code)}
              </G>
              <G w="50%">
                <span style={{ fontSize: 7 }}>b</span>
              </G>
            </div>
          </div>
          <G w="14%" />
        </Row>

        {/* ── Графы 16 / 17 ── */}
        <Row>
          <G w="50%" br style={{ visibility: 'hidden', minHeight: 0, padding: 0, height: 0 }} />
          <G w="25%" label="16" br>
            Страна происхождения
            <br />
            <b>{f(decl.country_origin_name)}</b>
          </G>
          <G w="25%" label="17">
            Страна назначения
            <br />
            <b>{f(decl.country_destination_code)}</b>
          </G>
        </Row>

        {/* ── Графы 18 / 19 / 20 ── */}
        <Row h={30}>
          <G w="42%" label="18" h={30} br>
            Идентификация и страна регистрации трансп. средства при отправлении/прибытии
            <br />
            <b>{f(decl.departure_vehicle_info)}</b>
          </G>
          <G w="8%" label="19" br>
            Конт.
            <br />
            <b>{f(decl.container_info) || '0'}</b>
          </G>
          <G w="50%" label="20">
            Условия поставки
            <br />
            <b>
              {f(decl.incoterms_code)} {f(decl.delivery_place)}
            </b>
          </G>
        </Row>

        {/* ── Графы 21 / 22 / 23 / 24 ── */}
        <Row h={30}>
          <G w="50%" label="21" h={30} br>
            Идентификация и страна регистрации активного транспортного средства на границе
            <br />
            <b>{f(decl.border_vehicle_info)}</b>
          </G>
          <G w="22%" label="22" br>
            Валюта и общая сумма по счету
            <br />
            <b>
              {f(decl.currency_code)} {num(decl.total_invoice_value)}
            </b>
          </G>
          <G w="14%" label="23" br>
            Курс валюты
            <br />
            <b>{payments ? num(payments.exchange_rate, 4) : num(decl.exchange_rate, 4)}</b>
          </G>
          <G w="14%" label="24">
            Характер сделки
            <br />
            <b>
              {f(decl.deal_nature_code)}
              {decl.deal_specifics_code ? '/' + decl.deal_specifics_code : ''}
            </b>
          </G>
        </Row>

        {/* ── Графы 25 / 26 / 27 / 28 ── */}
        <Row h={30}>
          <G w="12%" label="25" br>
            Вид транспорта на границе
            <br />
            <b>{f(decl.transport_type_border)}</b>
          </G>
          <G w="12%" label="26" br>
            Вид транспорта внутри страны
            <br />
            <b>{f(decl.transport_type_inland)}</b>
          </G>
          <G w="26%" label="27" br>
            Место погрузки/разгрузки
            <br />
            {f(decl.loading_place)}
          </G>
          <G w="50%" label="28">
            Финансовые и банковские сведения
            <br />
            {f(decl.financial_info)}
          </G>
        </Row>

        {/* ── Графы 29 / 30 ── */}
        <Row h={30}>
          <G w="25%" label="29" br>
            Орган въезда/выезда
            <br />
            <b>{f(decl.entry_customs_code)}</b>
          </G>
          <G w="75%" label="30">
            Местонахождение товаров
            <br />
            {f(decl.goods_location)}
          </G>
        </Row>

        {/* ── БЛОК ТОВАРА №1 (графы 31-46) ── */}
        <ItemBlock itm={firstItem} pi={firstPi} docs={itemDocsMap[firstItem?.id]} />

        {/* ── Графа 47: Исчисление платежей / 48 / 49 ── */}
        <div style={{ display: 'flex', borderBottom: bB }}>
          <div style={{ width: '50%', borderRight: bR, padding: '1px 3px', minHeight: 100, fontSize: 10 }}>
            <span style={{ fontSize: 7, color: '#555', fontWeight: 700 }}>47 </span>
            Исчисление платежей
            <PaymentRows totals={totals} paymentItems={payments?.items} />
          </div>
          <div style={{ width: '50%', display: 'flex', flexDirection: 'column' }}>
            <G w="100%" label="48" bb h={30}>
              Отсрочка платежей
              <br />
              {f(decl.payment_deferral)}
            </G>
            <G w="100%" label="49" bb h={30}>
              Реквизиты склада
              <br />
              {f(decl.warehouse_requisites)}
            </G>
            <G w="100%" label="В" h={40}>
              ПОДРОБНОСТИ ПОДСЧЕТА
            </G>
          </div>
        </div>

        {/* ── Секция С ── */}
        <Row>
          <G w="100%" label="С" center h={24} />
        </Row>

        {/* ── Графы 51 / 52 / 53 ── */}
        <Row h={50}>
          <G w="33%" label="51" h={50} br>
            Предполагаемые таможенные органы (и страна) транзита
            <br />
            {f(decl.transit_offices)}
          </G>
          <G w="33%" label="52" h={50} br>
            Гарантия недействительна для
            <br />
            {f(decl.guarantee_info)}
          </G>
          <G w="34%" label="53" h={50}>
            Таможенный орган назначения (и страна)
            <br />
            <b>{f(decl.destination_office_code)}</b>
          </G>
        </Row>

        {/* ── Секция D / 54 ── */}
        <div style={{ display: 'flex', borderBottom: bB }}>
          <div style={{ width: '50%', borderRight: bR, padding: '1px 3px', fontSize: 10, minHeight: 80 }}>
            <span style={{ fontSize: 7, color: '#555', fontWeight: 700 }}>D </span>
            <br />
            Результат:
            <br />
            Наложенные пломбы:
            <br />
            Номер:
            <br />
            Срок доставки (дата):
            <br />
            Подпись:
          </div>
          <G w="50%" label="54" h={80}>
            Место и дата
            <br />
            <b>{f(decl.place_and_date)}</b>
            <br />
            <br />
            Подпись и печать декларанта
          </G>
        </div>

        {/* ── Служебная строка ── */}
        <div
          style={{
            padding: '3px 6px',
            textAlign: 'center',
            background: '#e8f5e9',
            fontSize: 12,
            fontWeight: 700,
          }}
        >
          {decl.number_internal || 'ЧЕРНОВИК'} — Статус: {decl.status}
          {decl.customs_office_code && <> | Таможенный орган: {decl.customs_office_code}</>}
        </div>
      </div>

      {/* ═══════════════════ ДТ2 — ДОБАВОЧНЫЕ ЛИСТЫ ═══════════════════ */}
      {dt2Sheets.map((sheetItems, sheetIdx) => {
        const sheetNumber = sheetIdx + 2;
        const startItemIdx = 1 + sheetIdx * 3;
        return (
          <div key={sheetIdx} className="dt-sheet dt-additional" style={{ ...FORM, marginTop: 20 }}>
            {/* ── Заголовок ДТ2 ── */}
            <Row thick>
              <G w="58%" bold center br>
                ДОБАВОЧНЫЙ ЛИСТ К ДЕКЛАРАЦИИ НА ТОВАРЫ
              </G>
              <G w="27%" label="1" br>
                <b>{f(decl.type_code)}</b>
              </G>
              <G w="15%" label="А" center />
            </Row>

            {/* ── Графы 2 / 8 / 3 ── */}
            <Row h={36}>
              <G w="40%" label="2" h={36} br>
                Отправитель/Экспортер
                <br />
                <b>{sender?.name || 'НЕ УКАЗАН'}</b>
              </G>
              <G w="40%" label="8" h={36} br>
                Получатель
                <br />
                <b>
                  {decl.receiver_counterparty_id && decl.declarant_counterparty_id && decl.receiver_counterparty_id !== decl.declarant_counterparty_id
                    ? (receiver?.name || 'НЕ УКАЗАН')
                    : 'СМ. ГРАФУ 14 ДТ'}
                </b>
              </G>
              <G w="20%" label="3">
                Формы
                <br />
                <b>
                  {sheetNumber}/{totalForms}
                </b>
              </G>
            </Row>

            {/* ── Три блока товаров ── */}
            {[0, 1, 2].map((slotIdx) => {
              const itm = sheetItems[slotIdx];
              const globalIdx = startItemIdx + slotIdx;
              const pi = payments?.items?.[globalIdx];
              if (!itm) {
                return (
                  <div key={slotIdx}>
                    <div
                      style={{
                        borderBottom: bB,
                        borderTop: slotIdx === 0 ? bT : undefined,
                        minHeight: 100,
                        position: 'relative',
                      }}
                    >
                      <div
                        style={{
                          position: 'absolute',
                          top: '50%',
                          left: '5%',
                          right: '5%',
                          borderTop: '2px solid #000',
                        }}
                      />
                    </div>
                  </div>
                );
              }
              return (
                <div key={slotIdx} style={{ borderTop: slotIdx === 0 ? bT : undefined }}>
                  <ItemBlock itm={itm} pi={pi} docs={itemDocsMap[itm?.id]} />
                </div>
              );
            })}

            {/* ── Графа 47: Исчисление платежей (по 3 товарам) ── */}
            <div style={{ display: 'flex', borderBottom: bB, borderTop: bT }}>
              <div style={{ width: '50%', borderRight: bR, padding: '1px 3px', minHeight: 80, fontSize: 10 }}>
                <span style={{ fontSize: 7, color: '#555', fontWeight: 700 }}>47 </span>
                Исчисление платежей
                {sheetItems.map((itm: any, si: number) => {
                  const gi = startItemIdx + si;
                  const pi = payments?.items?.[gi];
                  if (!pi) return null;
                  return (
                    <div key={si} style={{ marginTop: 2 }}>
                      <div style={{ fontSize: 8, fontWeight: 700 }}>Товар №{itm.item_no}:</div>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <tbody>
                          <tr>
                            <td style={payTd}>2010</td>
                            <td style={{ ...payTd, textAlign: 'right' }}>{num(pi.customs_value_rub)}</td>
                            <td style={{ ...payTd, textAlign: 'center' }}>{pi.duty?.rate || 0}%</td>
                            <td style={{ ...payTd, textAlign: 'right' }}>{num(pi.duty?.amount)}</td>
                            <td style={payTd}>ИУ</td>
                          </tr>
                          <tr>
                            <td style={payTd}>5010</td>
                            <td style={{ ...payTd, textAlign: 'right' }}>{num(pi.vat?.base)}</td>
                            <td style={{ ...payTd, textAlign: 'center' }}>{pi.vat?.rate || 20}%</td>
                            <td style={{ ...payTd, textAlign: 'right' }}>{num(pi.vat?.amount)}</td>
                            <td style={payTd}>ИУ</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  );
                })}
              </div>
              <div style={{ width: '50%', display: 'flex', flexDirection: 'column' }}>
                <G w="100%" label="ВСЕГО" bold center h={24} bb>
                  {num(
                    sheetItems.reduce((sum: number, _: any, si: number) => {
                      const gi = startItemIdx + si;
                      const pi = payments?.items?.[gi];
                      return sum + (pi ? (pi.duty?.amount || 0) + (pi.vat?.amount || 0) : 0);
                    }, 0),
                  )}
                </G>
                <G w="100%" label="С" center />
              </div>
            </div>
          </div>
        );
      })}

      {/* ── ДОПОЛНЕНИЕ (лист дополнения к ДТ) ── */}
      {items.length > 0 && (
        <div className="dt-sheet" style={{ border: bT, padding: 10, marginTop: 20, fontSize: 10, fontFamily: 'Arial, sans-serif' }}>
          <div style={{ textAlign: 'center', fontWeight: 700, fontSize: 12, marginBottom: 10, textTransform: 'uppercase' }}>
            Дополнение на {items.length} л., к ДТ N {f(decl.number_internal || '')}
          </div>
          {items.map((itm: any, idx: number) => (
            <div key={itm.id || idx} style={{ marginBottom: 16, pageBreakInside: 'avoid' }}>
              <div style={{ fontWeight: 700, fontSize: 11, borderBottom: '1px solid #333', paddingBottom: 2, marginBottom: 6 }}>
                Товар № {itm.item_no || idx + 1}
              </div>
              {itm.documents_json?.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontWeight: 600, fontSize: 10, marginBottom: 3 }}>К ГРАФЕ 44 (Документы)</div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 9 }}>
                    <thead>
                      <tr>
                        <th style={{ border: '1px solid #999', padding: '2px 4px', textAlign: 'left', fontWeight: 600 }}>Код</th>
                        <th style={{ border: '1px solid #999', padding: '2px 4px', textAlign: 'left', fontWeight: 600 }}>Номер</th>
                        <th style={{ border: '1px solid #999', padding: '2px 4px', textAlign: 'left', fontWeight: 600 }}>Дата</th>
                      </tr>
                    </thead>
                    <tbody>
                      {itm.documents_json.map((doc: any, di: number) => (
                        <tr key={di}>
                          <td style={{ border: '1px solid #ccc', padding: '2px 4px' }}>{doc.doc_kind_code || doc.code || ''}</td>
                          <td style={{ border: '1px solid #ccc', padding: '2px 4px' }}>{doc.doc_number || doc.number || ''}</td>
                          <td style={{ border: '1px solid #ccc', padding: '2px 4px' }}>{doc.doc_date || doc.date || ''}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div>
                <div style={{ fontWeight: 600, fontSize: 10, marginBottom: 3 }}>К ГРАФЕ 31 (Описание и характеристики товара)</div>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 9 }}>
                  <thead>
                    <tr>
                      {['Гр.', 'Наименование', 'Производитель', 'Марка', 'Модель', 'Кол-во', 'Ед.изм', 'Артикул', 'Серийные NN'].map(h => (
                        <th key={h} style={{ border: '1px solid #999', padding: '2px 4px', textAlign: 'left', fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={{ border: '1px solid #ccc', padding: '2px 4px', textAlign: 'center' }}>{itm.item_no || idx + 1}</td>
                      <td style={{ border: '1px solid #ccc', padding: '2px 4px' }}>{f(itm.commercial_name || itm.description)}</td>
                      <td style={{ border: '1px solid #ccc', padding: '2px 4px' }}>{f(itm.manufacturer) || 'ОТСУТСТВУЕТ'}</td>
                      <td style={{ border: '1px solid #ccc', padding: '2px 4px' }}>{f(itm.trademark) || 'ОТСУТСТВУЕТ'}</td>
                      <td style={{ border: '1px solid #ccc', padding: '2px 4px' }}>{f(itm.model_name) || 'ОТСУТСТВУЕТ'}</td>
                      <td style={{ border: '1px solid #ccc', padding: '2px 4px', textAlign: 'right' }}>
                        {itm.additional_unit_qty != null ? num(itm.additional_unit_qty, 0) : (itm.package_count ?? '')}
                      </td>
                      <td style={{ border: '1px solid #ccc', padding: '2px 4px' }}>{f(itm.additional_unit) || 'ШТ'}</td>
                      <td style={{ border: '1px solid #ccc', padding: '2px 4px' }}>{f(itm.article_number) || 'ОТСУТСТВУЕТ'}</td>
                      <td style={{ border: '1px solid #ccc', padding: '2px 4px' }}>{f(itm.serial_number) || 'ОТСУТСТВУЮТ'}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { margin: 0; padding: 0; }
          .dt-sheet { page-break-after: always; border-width: 1px !important; }
          .dt-sheet:last-child { page-break-after: auto; }
        }
        @page { size: A4 portrait; margin: 8mm; }
      `}</style>
    </AppLayout>
  );
};

export default DeclarationViewPage;
