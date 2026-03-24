/**
 * Просмотр ДТС-1 в официальной форме (Решение ЕЭК №160, форма ДТС-1).
 * Макет соответствует официальной форме clcd_19102018_160.
 */
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  CircularProgress,
  Typography,
  Alert,
  IconButton,
  Tooltip,
  Chip,
} from '@mui/material';
import {
  Print as PrintIcon, Edit as EditIcon, ArrowBack as BackIcon,
  PictureAsPdf as PdfIcon, Description as FileTextIcon,
  CheckCircle as CheckCircleIcon, Warning as WarningIcon,
  AccessTime as ClockIcon, Send as SendIcon,
  VerifiedUser as SignIcon,
} from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import StatusChip from '../components/StatusChip';
import client from '../api/client';
import { Counterparty, CustomsValueDeclaration, CustomsValueItem } from '../types';
import dayjs from 'dayjs';

const f = (v: any) => (v != null && v !== '' ? String(v) : '');
const num = (v: any, d = 2) =>
  v != null
    ? Number(v).toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d })
    : '';
const ddmm = (d: string | null | undefined) => {
  if (!d) return '';
  try {
    const dt = new Date(d);
    return dt.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' });
  } catch {
    return String(d).slice(0, 10);
  }
};

const FORM: React.CSSProperties = {
  fontFamily: '"Times New Roman", serif',
  fontSize: 10,
  lineHeight: 1.25,
  border: '2px solid #000',
  background: '#fff',
  width: '100%',
  maxWidth: 900,
  margin: '0 auto',
  boxSizing: 'border-box',
};

const bR = '1px solid #000';
const bB = '1px solid #000';
const bT = '2px solid #000';

const G = ({
  w,
  h,
  label,
  br,
  bb,
  bt,
  bold,
  center,
  children,
  style,
}: {
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
}) => (
  <div
    style={{
      width: w,
      minHeight: h || 18,
      padding: '2px 4px',
      borderRight: br ? bR : undefined,
      borderBottom: bb ? bB : undefined,
      borderTop: bt ? bT : undefined,
      fontWeight: bold ? 700 : 400,
      textAlign: center ? 'center' : 'left',
      fontSize: 10,
      lineHeight: 1.25,
      overflow: 'hidden',
      boxSizing: 'border-box',
      ...style,
    }}
  >
    {label != null && label !== '' && (
      <span style={{ fontSize: 8, color: '#444', fontWeight: 700 }}>{label} </span>
    )}
    {children}
  </div>
);

const Row = ({
  children,
  thick,
  h,
}: {
  children: React.ReactNode;
  thick?: boolean;
  h?: number;
}) => (
  <div
    style={{
      display: 'flex',
      borderBottom: thick ? bT : bB,
      minHeight: h || 18,
    }}
  >
    {children}
  </div>
);

const DtsViewPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [decl, setDecl] = useState<any>(null);
  const [dts, setDts] = useState<CustomsValueDeclaration | null>(null);
  const [sender, setSender] = useState<Counterparty | null>(null);
  const [receiver, setReceiver] = useState<Counterparty | null>(null);
  const [declarant, setDeclarant] = useState<Counterparty | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      if (!id) return;
      try {
        const [declResp, dtsResp] = await Promise.all([
          client.get(`/declarations/${id}`),
          client.get(`/declarations/${id}/dts/`).catch(() => ({ data: null })),
        ]);
        const d = declResp.data;
        setDecl(d);
        setDts(dtsResp.data);

        const loadCp = async (cpId: string) => {
          try {
            return (await client.get(`/counterparties/${cpId}`)).data;
          } catch {
            return null;
          }
        };
        if (d?.sender_counterparty_id) setSender(await loadCp(d.sender_counterparty_id));
        if (d?.receiver_counterparty_id) setReceiver(await loadCp(d.receiver_counterparty_id));
        if (d?.declarant_counterparty_id) setDeclarant(await loadCp(d.declarant_counterparty_id));
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  if (loading) {
    return (
      <AppLayout noPadding>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
          <CircularProgress />
        </Box>
      </AppLayout>
    );
  }

  if (!decl) {
    return (
      <AppLayout noPadding>
        <Typography sx={{ py: 4, px: 3 }}>Декларация не найдена</Typography>
      </AppLayout>
    );
  }

  if (!dts) {
    return (
      <AppLayout noPadding>
        <Box sx={{ maxWidth: 600, mx: 'auto', mt: 6, textAlign: 'center' }}>
          <Box sx={{ width: 56, height: 56, borderRadius: '50%', bgcolor: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', mx: 'auto', mb: 2 }}>
            <FileTextIcon sx={{ fontSize: 28, color: '#cbd5e1' }} />
          </Box>
          <Typography sx={{ fontSize: 16, fontWeight: 600, color: '#0f172a', mb: 0.5 }}>ДТС не сформирована</Typography>
          <Typography sx={{ fontSize: 13, color: '#64748b', mb: 3 }}>Перейдите в редактирование декларации и нажмите «Сформировать ДТС»</Typography>
          <Button variant="contained" startIcon={<BackIcon />} onClick={() => navigate(`/declarations/${id}/edit`)}
            sx={{ bgcolor: '#0f172a', '&:hover': { bgcolor: '#1e293b' } }}>
            К редактированию
          </Button>
        </Box>
      </AppLayout>
    );
  }

  const cpLine = (cp: Counterparty | null) =>
    cp ? `${f(cp.name)} ${f(cp.country_code)} ${f(cp.address)}`.trim() || '—' : '—';
  const cpShort = (cp: Counterparty | null) =>
    cp ? `${f(cp.tax_number || cp.registration_number)} ${f(cp.name)}` : '—';

  const items = dts.items || [];
  const sheets: CustomsValueItem[][] = [];
  for (let i = 0; i < items.length; i += 3) {
    sheets.push(items.slice(i, i + 3));
  }
  if (sheets.length === 0) sheets.push([]);

  const invStr = decl.invoice_number
    ? `${f(decl.invoice_number)} ОТ ${ddmm(decl.invoice_date)}`
    : f(decl.number_internal);
  const cntrStr = decl.contract_number
    ? `${f(decl.contract_number)} ОТ ${ddmm(decl.contract_date)}`
    : '';

  return (
    <AppLayout noPadding>
      {/* Sticky Header */}
      <Box
        className="no-print"
        sx={{
          position: 'sticky', top: 56, zIndex: 40,
          bgcolor: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(8px)',
          borderBottom: '1px solid #e2e8f0',
          px: 2.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          height: 52,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Tooltip title="К декларации">
            <IconButton onClick={() => navigate(`/declarations/${id}`)} size="small"
              sx={{ bgcolor: '#f1f5f9', '&:hover': { bgcolor: '#e2e8f0' } }}>
              <BackIcon sx={{ fontSize: 18, color: '#64748b' }} />
            </IconButton>
          </Tooltip>
          <Box sx={{ width: 1, height: 20, bgcolor: '#e2e8f0' }} />
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography sx={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>
                ДТС-1
              </Typography>
              <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>·</Typography>
              <Typography sx={{ fontSize: 12, color: '#64748b' }}>
                {decl.number_internal || decl.id?.slice(0, 8)}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <ClockIcon sx={{ fontSize: 12, color: '#94a3b8' }} />
              <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>
                {dts.updated_at ? dayjs(dts.updated_at).format('DD.MM.YYYY HH:mm') : 'Сформирована'}
              </Typography>
            </Box>
          </Box>
        </Box>

        <Chip
          size="small"
          label={`Метод 1 · ${items.length} товаров`}
          sx={{ bgcolor: '#f5f3ff', color: '#7c3aed', border: '1px solid #ddd6fe', fontWeight: 500, fontSize: 11 }}
        />

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Button size="small" onClick={() => navigate(`/declarations/${id}/view`)} variant="outlined"
            sx={{ fontSize: 11, color: '#64748b', borderColor: '#e2e8f0' }}>
            К ДТ
          </Button>
          <Button size="small" onClick={() => navigate(`/declarations/${id}/edit`)} variant="outlined"
            startIcon={<EditIcon sx={{ fontSize: 14 }} />}
            sx={{ fontSize: 11, color: '#64748b', borderColor: '#e2e8f0' }}>
            Редактировать
          </Button>
          <Button size="small" variant="outlined"
            startIcon={<PrintIcon sx={{ fontSize: 14 }} />}
            onClick={() => window.print()}
            sx={{ fontSize: 11, color: '#64748b', borderColor: '#e2e8f0' }}>
            Печать
          </Button>
        </Box>
      </Box>

      {/* Form content */}
      <Box sx={{ p: 3, bgcolor: '#f8f8fa' }}>

      {/* ═══════ ЛИСТ 1 — Официальная форма ДТС-1 ═══════ */}
      <div className="dts-sheet" style={FORM}>
        <Row thick>
          <G w="100%" center bold h={28}>
            Ф О Р М А
            <br />
            декларации таможенной стоимости ДТС-1
          </G>
        </Row>

        <Row h={50}>
          <G w="15%" label="1" br bb>
            Продавец
          </G>
          <G w="85%">
            {cpLine(sender)}
          </G>
        </Row>

        <Row h={50}>
          <G w="15%" label="2" br bb>
            (а) Покупатель
          </G>
          <G w="85%">
            {cpShort(receiver)}
            {receiver?.address ? `, ${receiver.address}` : ''}
          </G>
        </Row>

        <Row h={50}>
          <G w="15%" label="2" br bb>
            (б) Декларант
          </G>
          <G w="85%">
            {cpShort(declarant || receiver)}
            {decl ? ` ${f(decl.declarant_inn_kpp)} ${f(decl.declarant_ogrn)}` : ''}
          </G>
        </Row>

        <Row h={24}>
          <G w="15%" label="3" br>
            Условия поставки
          </G>
          <G w="40%">
            {f(decl.incoterms_code)} {f(decl.delivery_place)}
          </G>
          <G w="15%" label="4" br>
            Номер и дата счёта
          </G>
          <G w="30%">
            {invStr}
          </G>
        </Row>

        <Row h={24}>
          <G w="15%" label="5" br>
            Номер и дата контракта
          </G>
          <G w="85%">
            {cntrStr}
          </G>
        </Row>

        <Row h={22}>
          <G w="15%" label="6" br>
            Документы к графам 7–9
          </G>
          <G w="85%">
            {f(dts.additional_docs)}
          </G>
        </Row>

        {/* Графа 7 */}
        <Row h={20}>
          <G w="55%" label="7" br>
            (а) Взаимосвязь продавца и покупателя?
          </G>
          <G w="22%" center>
            {dts.related_parties ? 'X ДА' : 'X НЕТ'}
          </G>
          <G w="23%">
            (б) Повлияла на цену? {(dts.related_price_impact ? 'X ДА' : 'X НЕТ')}
          </G>
        </Row>
        <Row h={20}>
          <G w="55%" br style={{ paddingLeft: 24 }} />
          <G w="45%">
            (в) Проверочная величина? {dts.related_verification ? 'X ДА' : 'X НЕТ'}
          </G>
        </Row>

        {/* Графа 8 */}
        <Row h={20}>
          <G w="55%" label="8" br>
            (а) Ограничения в отношении прав покупателя?
          </G>
          <G w="45%">
            {dts.restrictions ? 'X ДА' : 'X НЕТ'} (б) Цена зависит от условий?{' '}
            {dts.price_conditions ? 'X ДА' : 'X НЕТ'}
          </G>
        </Row>

        {/* Графа 9 */}
        <Row h={20}>
          <G w="55%" label="9" br>
            (а) Лицензионные платежи?
          </G>
          <G w="45%">
            {dts.ip_license_payments ? 'X ДА' : 'X НЕТ'} (б) {dts.sale_depends_on_income ? 'X ДА' : 'X НЕТ'}{' '}
            (в) {dts.income_to_seller ? 'X ДА' : 'X НЕТ'}
          </G>
        </Row>

        <Row h={24}>
          <G w="15%" label="10" br>
            (а) Добавочных листов
          </G>
          <G w="15%">
            {Math.max(0, Math.ceil(items.length / 3) - 1)}
          </G>
          <G w="20%" label="10" br>
            (б) Заполнивший
          </G>
          <G w="50%">
            {ddmm(dts.filler_date)} {f(dts.filler_name)} {f(dts.filler_document)} {f(dts.filler_contacts)}{' '}
            {f(dts.filler_position)}
          </G>
        </Row>

        <div
          style={{
            padding: '4px 8px',
            textAlign: 'center',
            background: '#f5f5f5',
            fontSize: 10,
            fontWeight: 700,
          }}
        >
          ДТ {f(decl.number_internal)} — ДТС-1, метод 1
        </div>
      </div>

      {/* ═══════ ЛИСТ 2+ — Расчёт по товарам (до 3 на лист) ═══════ */}
      {sheets.map((sheetItems, sheetIdx) => (
        <div
          key={sheetIdx}
          className="dts-sheet"
          style={{ ...FORM, marginTop: 24 }}
        >
          <Row thick>
            <G w="70%" bold center br>
              Метод 1 — Форма ДТС-1
            </G>
            <G w="30%" center>
              Лист № {sheetIdx + 2}
            </G>
          </Row>

          <Row h={20}>
            <G w="28%" br>
              ДЛЯ ОТМЕТОК ТАМОЖЕННОГО ОРГАНА / Код ТН ВЭД ЕАЭС
            </G>
            <G w="24%" br>
              Товар №{sheetIdx * 3 + 1}
            </G>
            <G w="24%" br>
              Товар №{sheetIdx * 3 + 2}
            </G>
            <G w="24%">
              Товар №{sheetIdx * 3 + 3}
            </G>
          </Row>
          <Row h={18}>
            <G w="28%" br />
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2} bold>
                {sheetItems[i]?.hs_code || ''}
              </G>
            ))}
          </Row>

          {/* Основа для расчёта */}
          <Row h={22}>
            <G w="28%" label="11" br>
              (а) Цена в валюте счёта
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i]
                  ? `${f(decl.currency_code)} ${num(sheetItems[i].invoice_price_foreign)}`
                  : ''}
              </G>
            ))}
          </Row>
          <Row h={30}>
            <G w="28%" br style={{ paddingLeft: 14 }}>
              в нац. валюте
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? (
                  <>
                    {num(sheetItems[i].invoice_price_national)}
                    <br />
                    <span style={{ fontSize: 8, color: '#555' }}>
                      (курс {f(decl.currency_code)} {num(decl.exchange_rate, 4)})
                    </span>
                  </>
                ) : ''}
              </G>
            ))}
          </Row>
          <Row h={22}>
            <G w="28%" label="11" br>
              (б) Косвенные платежи
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? num(sheetItems[i].indirect_payments) : ''}
              </G>
            ))}
          </Row>
          <Row h={22}>
            <G w="28%" label="12" br>
              Итого графа 11
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2} bold>
                {sheetItems[i] ? num(sheetItems[i].base_total) : ''}
              </G>
            ))}
          </Row>

          {/* Начисления 13–19 */}
          <Row h={18}>
            <G w="28%" label="13" br>
              (а) Вознаграждение агентам
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? num(sheetItems[i].broker_commission) : ''}
              </G>
            ))}
          </Row>
          <Row h={18}>
            <G w="28%" br style={{ paddingLeft: 14 }}>
              (б) Тара и упаковка
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? num(sheetItems[i].packaging_cost) : ''}
              </G>
            ))}
          </Row>
          <Row h={18}>
            <G w="28%" label="14" br>
              Сырьё, инструменты и т.д.
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i]
                  ? num(
                      (Number(sheetItems[i].raw_materials) || 0) +
                        (Number(sheetItems[i].tools_molds) || 0) +
                        (Number(sheetItems[i].consumed_materials) || 0) +
                        (Number(sheetItems[i].design_engineering) || 0),
                    )
                  : ''}
              </G>
            ))}
          </Row>
          <Row h={18}>
            <G w="28%" label="15" br>
              Лицензионные платежи
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? num(sheetItems[i].license_payments) : ''}
              </G>
            ))}
          </Row>
          <Row h={18}>
            <G w="28%" label="16" br>
              Часть дохода продавцу
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? num(sheetItems[i].seller_income) : ''}
              </G>
            ))}
          </Row>
          <Row h={22}>
            <G w="28%" label="17" br>
              Расходы на перевозку до {f(dts.transport_destination) || '________'}
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? num(sheetItems[i].transport_cost) : ''}
              </G>
            ))}
          </Row>
          {dts.transport_carrier_name && (
            <Row h={16}>
              <G w="28%" br style={{ fontSize: 8 }}>
                Перевозчик: {f(dts.transport_carrier_name)}
              </G>
              <G w="88%" />
            </Row>
          )}
          <Row h={18}>
            <G w="28%" label="18" br>
              Погрузка/разгрузка
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? num(sheetItems[i].loading_unloading) : ''}
              </G>
            ))}
          </Row>
          <Row h={18}>
            <G w="28%" label="19" br>
              Страхование
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? num(sheetItems[i].insurance_cost) : ''}
              </G>
            ))}
          </Row>
          <Row h={22}>
            <G w="28%" label="20" br>
              Итого начислений
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2} bold>
                {sheetItems[i] ? num(sheetItems[i].additions_total) : ''}
              </G>
            ))}
          </Row>

          {/* Вычеты 21–24 */}
          <Row h={18}>
            <G w="28%" label="21" br>
              Строительство после ввоза
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? num(sheetItems[i].construction_after_import) : ''}
              </G>
            ))}
          </Row>
          <Row h={18}>
            <G w="28%" label="22" br>
              Перевозка по ЕАЭС
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? num(sheetItems[i].inland_transport) : ''}
              </G>
            ))}
          </Row>
          <Row h={18}>
            <G w="28%" label="23" br>
              Пошлины, налоги
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2}>
                {sheetItems[i] ? num(sheetItems[i].duties_taxes) : ''}
              </G>
            ))}
          </Row>
          <Row h={22}>
            <G w="28%" label="24" br>
              Итого вычетов
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2} bold>
                {sheetItems[i] ? num(sheetItems[i].deductions_total) : ''}
              </G>
            ))}
          </Row>

          {/* Графа 25 */}
          <Row thick h={28}>
            <G w="28%" label="25" br>
              (а) ТС в руб.
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2} bold>
                {sheetItems[i] ? num(sheetItems[i].customs_value_national) : ''}
              </G>
            ))}
          </Row>
          <Row h={22}>
            <G w="28%" br>
              (б) ТС в USD (курс {num(dts.usd_exchange_rate, 4)})
            </G>
            {[0, 1, 2].map((i) => (
              <G key={i} w="24%" br={i < 2} bold>
                {sheetItems[i] ? num(sheetItems[i].customs_value_usd) : ''}
              </G>
            ))}
          </Row>

          {/* Таблица пересчёта валют (раздел *) */}
          {(() => {
            const allConv = sheetItems.flatMap(
              (si) => (si?.currency_conversions as Array<{
                item_no?: number; graph?: string; currency_code?: string;
                amount_foreign?: number; exchange_rate?: number;
              }>) || [],
            );
            if (allConv.length === 0) return null;
            return (
              <>
                <Row h={16}>
                  <G w="100%" style={{ fontSize: 8, fontWeight: 700, background: '#fafafa' }}>
                    * Пересчёт сумм в иностранной валюте
                  </G>
                </Row>
                <Row h={14}>
                  <G w="28%" br bold style={{ fontSize: 8 }}>Товар / Графа</G>
                  <G w="44%" br bold style={{ fontSize: 8 }}>Код валюты, сумма</G>
                  <G w="28%" bold style={{ fontSize: 8 }}>Курс пересчёта</G>
                </Row>
                {allConv.map((c, ci) => (
                  <Row key={ci} h={14}>
                    <G w="28%" br style={{ fontSize: 9 }}>{c.item_no} / {c.graph}</G>
                    <G w="44%" br style={{ fontSize: 9 }}>
                      {c.currency_code} {num(c.amount_foreign)}
                    </G>
                    <G w="28%" style={{ fontSize: 9 }}>{num(c.exchange_rate, 4)}</G>
                  </Row>
                ))}
              </>
            );
          })()}

          {dts.additional_data && (
            <Row h={40}>
              <G w="100%">
                Дополнительные данные: {f(dts.additional_data)}
              </G>
            </Row>
          )}

          <div
            style={{
              padding: '4px 8px',
              textAlign: 'center',
              background: '#f5f5f5',
              fontSize: 10,
              fontWeight: 700,
            }}
          >
            Лист {sheetIdx + 2} — Товары №{sheetIdx * 3 + 1}–{sheetIdx * 3 + sheetItems.length}
          </div>
        </div>
      ))}

      </Box>

      {/* Bottom Bar */}
      <Box
        className="no-print"
        sx={{
          position: 'sticky', bottom: 0, zIndex: 40,
          bgcolor: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(8px)',
          borderTop: '1px solid #e2e8f0',
          px: 2.5, py: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          height: 46,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, fontSize: 11, color: '#7c3aed', bgcolor: '#f5f3ff', px: 1.25, py: 0.5, borderRadius: '8px' }}>
            <FileTextIcon sx={{ fontSize: 14 }} />
            <Typography sx={{ fontSize: 11 }}>ДТС-1, Метод 1</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, fontSize: 11, color: '#64748b', bgcolor: '#f8fafc', px: 1.25, py: 0.5, borderRadius: '8px' }}>
            <CheckCircleIcon sx={{ fontSize: 14 }} />
            <Typography sx={{ fontSize: 11 }}>{items.length} товаров</Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Button size="small" variant="outlined"
            startIcon={<SignIcon sx={{ fontSize: 14 }} />}
            sx={{ fontSize: 11, color: '#64748b', borderColor: '#e2e8f0' }}>
            ЭЦП
          </Button>
          <Button size="small" variant="contained"
            startIcon={<SendIcon sx={{ fontSize: 14 }} />}
            sx={{ fontSize: 11, fontWeight: 500, bgcolor: '#059669', '&:hover': { bgcolor: '#047857' } }}>
            Подписать и отправить
          </Button>
        </Box>
      </Box>

      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { margin: 0; padding: 0; }
          .dts-sheet { page-break-after: always; border-width: 1px !important; }
          .dts-sheet:last-child { page-break-after: auto; }
        }
        @page { size: A4 portrait; margin: 10mm; }
      `}</style>
    </AppLayout>
  );
};

export default DtsViewPage;
