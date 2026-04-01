import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Button, Snackbar, IconButton, Divider, CircularProgress,
} from '@mui/material';
import {
  FolderOpen as FolderOpenIcon,
  Description as PdfIcon,
  Code as XmlIcon,
  CheckCircle as CheckIcon,
  WarningAmber as WarningIcon,
  ErrorOutline as ErrorOutlineIcon,
  Edit as EditIcon,
  AutoAwesome as AiIcon,
  ForkRight as ConflictIcon,
  Close as CloseIcon,
  Info as InfoIcon,
  FileUpload as FileUpIcon,
  Send as SendIcon,
  VerifiedUser as ShieldIcon,
  Undo as UndoIcon,
  OpenInNew as ExternalIcon,
  ChevronRight as ChevronRightIcon,
  ChevronLeft as ChevronLeftIcon,
  AccessTime as ClockIcon,
  InsertDriveFile as FileIcon,
} from '@mui/icons-material';
import { Alert } from '@mui/material';
import AppLayout from '../components/AppLayout';
import StatusChip from '../components/StatusChip';
import DocumentViewer from '../components/DocumentViewer';
import HSCodeSuggestions from '../components/HSCodeSuggestions';
import RequirementsPanel from '../components/RequirementsPanel';
import RiskPanel from '../components/RiskPanel';
import AiExplainPanel from '../components/AiExplainPanel';
import { getDeclaration, updateDeclaration, patchEvidenceMap, getDeclarationLogs } from '../api/declarations';
import { getItems, updateItem } from '../api/items';
import { getDocuments } from '../api/documents';
import { getCounterparty } from '../api/counterparties';
import { calculatePayments, PaymentResult } from '../api/calc';
import client from '../api/client';
import { Declaration, DeclarationItem, Document as DocType, EvidenceMapEntry, DeclarationLogEntry, FieldEvidence } from '../types';

/* ================== Types ================== */

type CellState = 'ai' | 'confirmed' | 'review' | 'conflict' | 'manual' | 'empty' | 'default';

interface CellDef {
  id: string;
  num: string;
  label: string;
  field: string;
  section: string;
  col?: string;
  row?: string;
  required?: boolean;
  tall?: boolean;
  computed?: boolean;
}

/* ================== Constants ================== */

const STATE_STYLES: Record<CellState, { stripe: string; dotColor: string; bg: string; badgeBg: string; badgeBorder: string; badgeText: string; badgeLabel: string }> = {
  ai:        { stripe: '#a78bfa70', dotColor: '#8b5cf6', bg: 'transparent',            badgeBg: '#f5f3ff', badgeBorder: 'rgba(196,181,253,0.7)', badgeText: '#7c3aed', badgeLabel: 'AI заполнено' },
  confirmed: { stripe: '#34d39970', dotColor: '#10b981', bg: 'transparent',            badgeBg: '#ecfdf5', badgeBorder: 'rgba(167,243,208,0.7)', badgeText: '#059669', badgeLabel: 'Подтверждено' },
  review:    { stripe: '#fbbf2480', dotColor: '#f59e0b', bg: 'rgba(255,251,235,0.25)', badgeBg: '#fffbeb', badgeBorder: 'rgba(253,230,138,0.7)', badgeText: '#d97706', badgeLabel: 'Требует проверки' },
  conflict:  { stripe: '#fb923c80', dotColor: '#f97316', bg: 'rgba(255,247,237,0.25)', badgeBg: '#fff7ed', badgeBorder: 'rgba(253,186,116,0.7)', badgeText: '#c2410c', badgeLabel: 'Конфликт' },
  manual:    { stripe: '#60a5fa70', dotColor: '#3b82f6', bg: 'transparent',            badgeBg: '#eff6ff', badgeBorder: 'rgba(191,219,254,0.7)', badgeText: '#2563eb', badgeLabel: 'Вручную' },
  empty:     { stripe: '#f8717180', dotColor: '#ef4444', bg: 'rgba(254,242,242,0.15)', badgeBg: '#fef2f2', badgeBorder: 'rgba(254,202,202,0.7)', badgeText: '#dc2626', badgeLabel: 'Не заполнено' },
  default:   { stripe: 'transparent', dotColor: '', bg: 'transparent',                 badgeBg: '#f8fafc', badgeBorder: 'rgba(226,232,240,0.7)', badgeText: '#64748b', badgeLabel: '' },
};

const DOT_ICONS: Record<CellState, React.ReactNode> = {
  ai: <AiIcon sx={{ fontSize: 10, color: '#8b5cf6' }} />,
  confirmed: <CheckIcon sx={{ fontSize: 10, color: '#10b981' }} />,
  review: <WarningIcon sx={{ fontSize: 10, color: '#f59e0b' }} />,
  conflict: <ConflictIcon sx={{ fontSize: 10, color: '#f97316' }} />,
  manual: <EditIcon sx={{ fontSize: 10, color: '#3b82f6' }} />,
  empty: <ErrorOutlineIcon sx={{ fontSize: 10, color: '#ef4444' }} />,
  default: null,
};

const SOURCE_LABELS: Record<string, string> = {
  invoice: 'Инвойс', contract: 'Контракт', packing_list: 'Упаковочный лист',
  packing: 'Упаковочный лист',
  transport_doc: 'Транспортный док.', transport: 'Транспортный док.',
  awb: 'AWB', heuristic: 'Автоматически',
  default: 'По умолчанию', rules_llm: 'Правила ДТ (AI)', aggregated_items: 'Из позиций',
  history: 'История компании', manual: 'Вручную',
  conformity_declaration: 'Декларация соответствия', specification: 'Спецификация',
  certificate_origin: 'Сертификат происхождения', tech_description: 'Тех. описание',
  sanitary: 'Санитарный серт.', veterinary: 'Ветеринарный серт.',
  phytosanitary: 'Фитосанитарный серт.', application_statement: 'Заявление',
  license: 'Лицензия', permit: 'Разрешение', transport_invoice: 'Транспортный счёт',
};

const DOC_TYPE_LABELS: Record<string, string> = {
  contract: 'Контракт', invoice: 'Инвойс', packing_list: 'Упаковочный лист',
  transport_doc: 'Транспортный док.', transport_invoice: 'Транспортный счёт',
  specification: 'Спецификация', tech_description: 'Тех. описание',
  certificate_origin: 'Сертификат происхождения', license: 'Лицензия',
  permit: 'Разрешение', other: 'Другое', application_statement: 'Заявление',
  sanitary: 'Санитарный серт.', veterinary: 'Ветеринарный серт.', phytosanitary: 'Фитосанитарный серт.',
};

const EVIDENCE_TO_FORM: Record<string, string> = {
  currency: 'currency_code', total_amount: 'total_invoice_value', incoterms: 'incoterms_code',
  country_origin: 'country_origin_name', country_destination: 'country_destination_code',
  country_dispatch: 'country_dispatch_code', transport_type: 'transport_type_border',
  transport_id: 'border_vehicle_info', border_vehicle_info: 'border_vehicle_info',
  trading_partner_country: 'trading_country_code',
  container: 'container_info', seller: 'sender_counterparty_id', buyer: 'receiver_counterparty_id',
  total_packages: 'total_packages_count',
  departure_vehicle_info: 'departure_vehicle_info',
  departure_vehicle_country: 'departure_vehicle_country',
  border_vehicle_country: 'border_vehicle_country',
  transport_doc_number: 'transport_doc_number',
  transport_type_inland: 'transport_type_inland',
  deal_nature_code: 'deal_nature_code',
  deal_specifics_code: 'deal_specifics_code',
  exchange_rate: 'exchange_rate',
  delivery_place: 'delivery_place',
  loading_place: 'loading_place',
  customs_office_code: 'customs_office_code',
  goods_location: 'goods_location',
  entry_customs_code: 'entry_customs_code',
  responsible_person: 'financial_counterparty_id',
  financial_responsible: 'financial_counterparty_id',
  declarant: 'declarant_inn_kpp',
  total_gross_weight: 'total_gross_weight',
  total_net_weight: 'total_net_weight',
  total_items_count: 'total_items_count',
  total_customs_value: 'total_customs_value',
  total_sheets: 'forms_count',
  preference_code: 'preference_code',
  type_code: 'type_code',
  invoice_number: 'invoice_number',
  invoice_date: 'invoice_date',
  contract_number: 'contract_number',
  contract_date: 'contract_date',
  freight_amount: 'freight_amount',
  freight_currency: 'freight_currency',
  description: 'description',
  country_origin_code: 'country_origin_code',
  gross_weight: 'gross_weight',
  net_weight: 'net_weight',
  additional_unit_qty: 'additional_unit_qty',
  unit_price: 'unit_price',
  customs_value_rub: 'customs_value_rub',
  statistical_value_usd: 'statistical_value_usd',
  hs_code: 'hs_code',
  procedure_code: 'procedure_code',
};
const FORM_TO_EVIDENCE: Record<string, string> = Object.fromEntries(
  Object.entries(EVIDENCE_TO_FORM).map(([k, v]) => [v, k]),
);

const ITEM_FIELDS = new Set([
  'description', 'item_no', 'hs_code', 'country_origin_code', 'gross_weight',
  'preference_code', 'procedure_code', 'net_weight', 'quota_info', 'prev_doc_ref',
  'additional_unit_qty', 'unit_price', 'mos_method_code', 'customs_value_rub',
  'statistical_value_usd', 'documents_json',
]);

/* ================== Cell definitions ================== */

const HEADER_CELLS: Record<string, CellDef> = {
  f1:  { id: 'f1',  num: '1',   label: 'Декларация',             field: 'type_code',                    section: 'Общие сведения' },
  fA:  { id: 'fA',  num: 'A',   label: 'Регистрационный номер',  field: 'number_internal',              section: 'Общие сведения' },
  f2:  { id: 'f2',  num: '2',   label: 'Отправитель / Экспортёр', field: 'sender_counterparty_id',      section: 'Участники', tall: true },
  f3:  { id: 'f3',  num: '3',   label: 'Формы',                  field: 'forms_count',                  section: 'Общие сведения' },
  f4:  { id: 'f4',  num: '4',   label: 'Отгрузочные спец.',      field: 'specifications_count',         section: 'Общие сведения' },
  f5:  { id: 'f5',  num: '5',   label: 'Всего товаров',          field: 'total_items_count',            section: 'Общие сведения' },
  f6:  { id: 'f6',  num: '6',   label: 'Всего мест',             field: 'total_packages_count',         section: 'Общие сведения' },
  f7:  { id: 'f7',  num: '7',   label: 'Справочный номер',       field: 'special_ref_code',             section: 'Общие сведения' },
  f8:  { id: 'f8',  num: '8',   label: 'Получатель',             field: 'receiver_counterparty_id',     section: 'Участники' },
  f9:  { id: 'f9',  num: '9',   label: 'Лицо, отв. за фин. урегулирование', field: 'financial_counterparty_id', section: 'Участники' },
  f10: { id: 'f10', num: '10',  label: 'Страна первого назн.',   field: 'country_first_destination_code', section: 'Общие сведения' },
  f11: { id: 'f11', num: '11',  label: 'Торговая страна',        field: 'trading_country_code',         section: 'Общие сведения' },
  f12: { id: 'f12', num: '12',  label: 'Общая таможенная стоимость', field: 'total_customs_value',      section: 'Коммерческие данные', computed: true },
  f13: { id: 'f13', num: '13',  label: 'Контролирующий орган',   field: 'customs_office_code',          section: 'Таможня' },
  f14: { id: 'f14', num: '14',  label: 'Декларант',              field: 'declarant_inn_kpp',            section: 'Декларант', tall: true },
  f15: { id: 'f15', num: '15',  label: 'Страна отправления',     field: 'country_dispatch_code',        section: 'Общие сведения', required: true },
  f15a:{ id: 'f15a',num: '15a', label: 'Код страны отпр.',       field: 'country_dispatch_code',        section: 'Общие сведения' },
  f17: { id: 'f17', num: '17',  label: 'Страна назначения',      field: 'country_destination_code',     section: 'Общие сведения', required: true },
  f16: { id: 'f16', num: '16',  label: 'Страна происхождения',   field: 'country_origin_name',          section: 'Общие сведения' },
  f17a:{ id: 'f17a',num: '17a', label: 'Код страны назн.',       field: 'country_destination_code',     section: 'Общие сведения' },
  f18: { id: 'f18', num: '18',  label: 'Транспорт при отправлении', field: 'departure_vehicle_info',    section: 'Транспорт' },
  f19: { id: 'f19', num: '19',  label: 'Контейнер',              field: 'container_info',               section: 'Транспорт' },
  f20: { id: 'f20', num: '20',  label: 'Условия поставки',       field: 'incoterms_code',               section: 'Коммерческие данные', required: true },
  f21: { id: 'f21', num: '21',  label: 'Транспорт на границе',   field: 'border_vehicle_info',          section: 'Транспорт' },
  f22: { id: 'f22', num: '22',  label: 'Валюта и сумма',         field: 'total_invoice_value',          section: 'Коммерческие данные', required: true },
  f23: { id: 'f23', num: '23',  label: 'Курс валюты',            field: 'exchange_rate',                section: 'Коммерческие данные' },
  f24: { id: 'f24', num: '24',  label: 'Характер сделки',        field: 'deal_nature_code',             section: 'Коммерческие данные' },
  f25: { id: 'f25', num: '25',  label: 'Вид транспорта на границе', field: 'transport_type_border',     section: 'Транспорт' },
  f26: { id: 'f26', num: '26',  label: 'Вид транспорта внутри',  field: 'transport_type_inland',        section: 'Транспорт' },
  f27: { id: 'f27', num: '27',  label: 'Место погрузки',         field: 'loading_place',                section: 'Транспорт' },
  f28: { id: 'f28', num: '28',  label: 'Финансовые и банковские данные', field: 'financial_info',       section: 'Коммерческие данные' },
  f29: { id: 'f29', num: '29',  label: 'Орган въезда / выезда',  field: 'entry_customs_code',           section: 'Таможня' },
  f30: { id: 'f30', num: '30',  label: 'Местонахождение товаров', field: 'goods_location',              section: 'Таможня' },
};

const FOOTER_CELLS: Record<string, CellDef> = {
  f48: { id: 'f48', num: '48', label: 'Отсрочка платежей',       field: 'payment_deferral',  section: 'Платежи' },
  f49: { id: 'f49', num: '49', label: 'Реквизиты склада',        field: 'warehouse_requisites', section: 'Платежи' },
  fb:  { id: 'fb',  num: 'B',  label: 'Подробности подсчёта',    field: 'calculation_details', section: 'Платежи', computed: true },
  fC:  { id: 'fC',  num: 'C',  label: 'Секция C',               field: 'section_c',         section: 'Таможня', computed: true },
  f51: { id: 'f51', num: '51', label: 'Таможенные органы транзита', field: 'transit_offices', section: 'Таможня' },
  f52: { id: 'f52', num: '52', label: 'Гарантия',                field: 'guarantee_info',    section: 'Таможня' },
  f53: { id: 'f53', num: '53', label: 'Таможенный орган назначения', field: 'destination_office_code', section: 'Таможня' },
  fd:  { id: 'fd',  num: 'D',  label: 'Таможенный контроль',     field: 'customs_control',   section: 'Таможня' },
  fdj: { id: 'fdj', num: 'D/J',label: 'Результат',              field: 'customs_result',    section: 'Таможня' },
  f54: { id: 'f54', num: '54', label: 'Место и дата',            field: 'place_and_date',    section: 'Подпись', tall: true },
};

const ITEM_CELL_DEFS: Array<{ num: string; label: string; field: string }> = [
  { num: '31', label: 'Грузовые места и описание', field: 'description' },
  { num: '32', label: '№ товара',           field: 'item_no' },
  { num: '33', label: 'Код товара (ТН ВЭД)', field: 'hs_code' },
  { num: '34', label: 'Страна происхождения', field: 'country_origin_code' },
  { num: '35', label: 'Вес брутто (кг)',    field: 'gross_weight' },
  { num: '36', label: 'Преференции',        field: 'preference_code' },
  { num: '37', label: 'Процедура',          field: 'procedure_code' },
  { num: '38', label: 'Вес нетто (кг)',     field: 'net_weight' },
  { num: '39', label: 'Квота',             field: 'quota_info' },
  { num: '40', label: 'Общая декл. / Предшеств. документ', field: 'prev_doc_ref' },
  { num: '41', label: 'Дополнительные единицы', field: 'additional_unit_qty' },
  { num: '42', label: 'Цена товара',        field: 'unit_price' },
  { num: '43', label: 'Код МОС',           field: 'mos_method_code' },
  { num: '44', label: 'Доп. сведения / Документы', field: 'documents_json' },
  { num: '45', label: 'Таможенная стоимость', field: 'customs_value_rub' },
  { num: '46', label: 'Статистическая стоимость', field: 'statistical_value_usd' },
];

const ALL_CELLS_FLAT: CellDef[] = [...Object.values(HEADER_CELLS), ...Object.values(FOOTER_CELLS)];

function makeItemCellId(idx: number, field: string) { return `item-${idx}-${field}`; }
function makeItemCell(idx: number, tpl: typeof ITEM_CELL_DEFS[0]): CellDef {
  return { id: makeItemCellId(idx, tpl.field), num: tpl.num, label: tpl.label, field: tpl.field, section: 'Товары' };
}

function findCellDef(cellId: string): { cell: CellDef; itemIndex?: number } | null {
  const h = ALL_CELLS_FLAT.find(c => c.id === cellId);
  if (h) return { cell: h };
  const m = cellId.match(/^item-(\d+)-(.+)$/);
  if (m) {
    const idx = parseInt(m[1]);
    const tpl = ITEM_CELL_DEFS.find(t => t.field === m[2]);
    if (tpl) return { cell: makeItemCell(idx, tpl), itemIndex: idx };
  }
  return null;
}

function getItemFieldValue(item: DeclarationItem, field: string): string {
  const it = item as any;
  switch (field) {
    case 'gross_weight': return numFmt(it.gross_weight, 3);
    case 'net_weight': return numFmt(it.net_weight, 3);
    case 'unit_price': return numFmt(it.unit_price, 4);
    case 'customs_value_rub': return numFmt(it.customs_value_rub);
    case 'statistical_value_usd': return numFmt(it.statistical_value_usd);
    case 'additional_unit_qty':
      return it.additional_unit_qty ? `${numFmt(it.additional_unit_qty, 0)} ${f(it.additional_unit) || 'ШТ'}`.trim() : '';
    case 'documents_json': {
      if (!it.documents_json?.length) return '';
      return it.documents_json.map((dd: any) => {
        const code = dd.doc_kind_code || dd.code || '';
        const num = dd.doc_number || dd.number || '';
        const dt = dd.doc_date || dd.date || '';
        const pk = dd.presenting_kind_code || dd.marker || '';
        return `${code}${pk ? '/' + pk : ''} ${num} ${dt}`;
      }).join('\n');
    }
    default: return f(it[field]);
  }
}

/* ================== Helpers ================== */

interface CpSet { sender?: any; receiver?: any; declarant?: any; financial?: any }
const cpLine = (cp: any) => cp ? `${cp.name || ''} ${cp.country_code || ''} ${cp.address || ''}`.trim() : '';

const f = (v: any) => (v == null ? '' : String(v));
const numFmt = (v: any, d = 2) => v ? Number(v).toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d }) : '';

function getEvidence(evidenceMap: Record<string, EvidenceMapEntry> | undefined, field: string): EvidenceMapEntry | undefined {
  if (!evidenceMap) return undefined;
  if (evidenceMap[field]) return evidenceMap[field];
  const alt = FORM_TO_EVIDENCE[field];
  if (alt && evidenceMap[alt]) return evidenceMap[alt];
  return undefined;
}

function getCellState(field: string, value: string, ev: EvidenceMapEntry | undefined, required?: boolean): CellState {
  if (!value && required) return 'empty';
  if (!ev) return value ? 'default' : (required ? 'empty' : 'default');
  if (ev.source === 'manual') return 'manual';
  const conf = ev.confidence ?? 0;
  if (conf >= 0.85) return 'ai';
  if (conf >= 0.6) return 'review';
  return 'review';
}

function getFieldValue(decl: Declaration, field: string, items: DeclarationItem[], payments: PaymentResult | null, cps: CpSet = {}): string {
  const d = decl as any;
  const item = items[0] as any;

  switch (field) {
    case 'sender_counterparty_id': return cpLine(cps.sender) || 'НЕ УКАЗАН';
    case 'receiver_counterparty_id': return cpLine(cps.receiver) || 'НЕ УКАЗАН';
    case 'financial_counterparty_id': return cpLine(cps.financial) || 'НЕ УКАЗАН';
    case 'declarant_inn_kpp': {
      const name = cpLine(cps.declarant) || cpLine(cps.receiver);
      const ids = `${f(d.declarant_inn_kpp)} ${f(d.declarant_ogrn)}`.trim();
      const phone = f(d.declarant_phone);
      return [name, ids, phone].filter(Boolean).join('\n');
    }
    case 'total_invoice_value': return `${f(d.currency_code)} ${numFmt(d.total_invoice_value)}`.trim();
    case 'deal_nature_code': return d.deal_specifics_code ? `${f(d.deal_nature_code)}/${d.deal_specifics_code}` : f(d.deal_nature_code);
    case 'incoterms_code': return `${f(d.incoterms_code)} ${f(d.delivery_place)}`.trim();
    case 'exchange_rate': return payments ? numFmt(payments.exchange_rate, 4) : numFmt(d.exchange_rate, 4);
    case 'total_items_count': return f(d.total_items_count || items.length);
    case 'total_customs_value': return numFmt(d.total_customs_value);
    case 'specifications_count': return f(d.specifications_count);
    case 'gross_weight': return item ? numFmt(item.gross_weight, 3) : '';
    case 'net_weight': return item ? numFmt(item.net_weight, 3) : '';
    case 'unit_price': return item ? numFmt(item.unit_price) : '';
    case 'customs_value_rub': return item ? numFmt(item.customs_value_rub) : '';
    case 'statistical_value_usd': return item ? numFmt(item.statistical_value_usd) : '';
    case 'additional_unit_qty':
      return item ? `${numFmt(item.additional_unit_qty)} ${f(item.additional_unit_code)}`.trim() : '';
    case 'documents_json': {
      if (!item?.documents_json?.length) return '';
      return item.documents_json.map((dd: any) => `${dd.code} ${dd.number} ${dd.date}`).join('\n');
    }
    case 'payments': {
      if (!payments?.items?.length) return '';
      return payments.items.map((pi: any) =>
        `Пошлина: ${numFmt(pi.duty?.amount)} | НДС: ${numFmt(pi.vat?.amount)}`
      ).join('\n');
    }
    case 'total_payments': {
      if (!payments?.totals) return '';
      return `Итого: ${numFmt(payments.totals.grand_total)} руб.`;
    }
    case 'calculation_details':
    case 'customs_control':
    case 'customs_result':
      return '';
    default: {
      if (ITEM_FIELDS.has(field)) return item ? f(item[field]) : '';
      return f(d[field]);
    }
  }
}

function getSourceString(evidence: EvidenceMapEntry | undefined, docs: DocType[], computed?: boolean): string {
  if (computed || !evidence) return '';
  if (evidence.source === 'manual') return 'Изменено вручную';
  const doc = evidence.document_id ? docs.find(dd => dd.id === evidence.document_id) : null;
  const sourceLabel = SOURCE_LABELS[evidence.source] || evidence.source;
  if (doc) {
    const name = doc.original_filename;
    const truncated = name.length > 22 ? name.slice(0, 22) + '\u2026' : name;
    return `${truncated} \u00b7 ${sourceLabel}`;
  }
  return sourceLabel;
}

/* ================== Main Page ================== */

const DeclarationFormPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [cellOverrides, setCellOverrides] = useState<Record<string, string>>({});
  const [docViewerOpen, setDocViewerOpen] = useState(false);
  const [snackMsg, setSnackMsg] = useState('');
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [forceSourceTab, setForceSourceTab] = useState(false);

  const { data: decl, isLoading } = useQuery({
    queryKey: ['declaration', id], queryFn: () => getDeclaration(id!), enabled: !!id,
  });
  const { data: itemsData } = useQuery({
    queryKey: ['declaration-items', id], queryFn: () => getItems(id!), enabled: !!id,
  });
  const { data: docsData } = useQuery({
    queryKey: ['declaration-docs', id], queryFn: () => getDocuments({ declaration_id: id! }), enabled: !!id,
  });
  const { data: logs = [] } = useQuery<DeclarationLogEntry[]>({
    queryKey: ['declaration-logs', id], queryFn: () => getDeclarationLogs(id!), enabled: !!id,
  });

  const { data: sender } = useQuery({
    queryKey: ['counterparty', decl?.sender_counterparty_id],
    queryFn: () => getCounterparty(decl!.sender_counterparty_id!),
    enabled: !!decl?.sender_counterparty_id,
  });
  const { data: receiver } = useQuery({
    queryKey: ['counterparty', decl?.receiver_counterparty_id],
    queryFn: () => getCounterparty(decl!.receiver_counterparty_id!),
    enabled: !!decl?.receiver_counterparty_id,
  });
  const { data: declarantCp } = useQuery({
    queryKey: ['counterparty', decl?.declarant_counterparty_id],
    queryFn: () => getCounterparty(decl!.declarant_counterparty_id!),
    enabled: !!decl?.declarant_counterparty_id,
  });
  const { data: financial } = useQuery({
    queryKey: ['counterparty', decl?.financial_counterparty_id],
    queryFn: () => getCounterparty(decl!.financial_counterparty_id!),
    enabled: !!decl?.financial_counterparty_id,
  });
  const cps: CpSet = useMemo(() => ({
    sender, receiver, declarant: declarantCp, financial,
  }), [sender, receiver, declarantCp, financial]);

  const [payments, setPayments] = useState<PaymentResult | null>(null);
  const items: DeclarationItem[] = useMemo(() => {
    if (Array.isArray(itemsData)) return itemsData;
    return (itemsData as any)?.items || [];
  }, [itemsData]);
  const docs: DocType[] = useMemo(() => {
    if (!docsData) return [];
    return Array.isArray(docsData) ? docsData : [];
  }, [docsData]);

  useEffect(() => {
    if (items.length > 0 && decl) {
      const payItems = items.map((i: any) => ({
        item_no: i.item_no, hs_code: i.hs_code || '',
        unit_price: i.unit_price ? Number(i.unit_price) : 0,
        quantity: i.additional_unit_qty ? Number(i.additional_unit_qty) : 1,
        customs_value_rub: i.customs_value_rub ? Number(i.customs_value_rub) : 0,
      }));
      calculatePayments(payItems, decl.currency_code || 'USD', decl.exchange_rate ? Number(decl.exchange_rate) : undefined)
        .then(setPayments).catch(() => {});
    }
  }, [items, decl]);

  const evidenceMap = decl?.evidence_map as Record<string, EvidenceMapEntry> | undefined;

  const handleFieldSelect = useCallback((cellId: string) => {
    setSelectedField(prev => prev === cellId ? null : cellId);
    if (editingField && editingField !== cellId) setEditingField(null);
    setForceSourceTab(false);
  }, [editingField]);

  const handleStartEdit = useCallback((cellId: string) => {
    setSelectedField(cellId);
    setEditingField(cellId);
    setForceSourceTab(false);
  }, []);

  const handleOpenSourceChange = useCallback((cellId: string) => {
    setSelectedField(cellId);
    setEditingField(null);
    setForceSourceTab(true);
  }, []);

  const handleSaveEdit = useCallback(async (cellId: string, newValue: string) => {
    setCellOverrides(prev => ({ ...prev, [cellId]: newValue }));
    setEditingField(null);
    const result = findCellDef(cellId);
    if (!result || !id) return;

    const NUMERIC_FIELDS = new Set([
      'total_invoice_value', 'exchange_rate', 'total_customs_value',
      'total_gross_weight', 'total_net_weight', 'freight_amount',
      'unit_price', 'customs_value_rub', 'statistical_value_usd',
      'gross_weight', 'net_weight', 'quantity',
    ]);
    let sanitized: string | number | null = newValue || null;
    if (sanitized && NUMERIC_FIELDS.has(result.cell.field)) {
      const cleaned = String(sanitized).replace(/\s/g, '').replace(',', '.');
      const num = parseFloat(cleaned);
      sanitized = isNaN(num) ? null : num;
    }

    try {
      setAutoSaveStatus('saving');
      if (result.itemIndex != null) {
        const item = items[result.itemIndex];
        if (item) await updateItem(id, item.id, { [result.cell.field]: sanitized });
        queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
      } else {
        await updateDeclaration(id, { [result.cell.field]: sanitized });
        queryClient.invalidateQueries({ queryKey: ['declaration', id] });
      }
      await patchEvidenceMap(id, { [result.cell.field]: { source: 'manual' } as any });
      queryClient.invalidateQueries({ queryKey: ['declaration-logs', id] });
      setAutoSaveStatus('saved');
      setTimeout(() => setAutoSaveStatus('idle'), 2000);
    } catch { setSnackMsg('Ошибка сохранения'); setAutoSaveStatus('idle'); }
  }, [id, items, queryClient]);

  const handleApplyFromSource = useCallback(async (cellId: string, newValue: string, docId: string, docType: string) => {
    setCellOverrides(prev => ({ ...prev, [cellId]: newValue }));
    setEditingField(null);
    setForceSourceTab(false);
    const result = findCellDef(cellId);
    if (!result || !id) return;
    try {
      setAutoSaveStatus('saving');
      if (result.itemIndex != null) {
        const item = items[result.itemIndex];
        if (item) await updateItem(id, item.id, { [result.cell.field]: newValue || null });
        queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
      } else {
        await updateDeclaration(id, { [result.cell.field]: newValue || null });
        queryClient.invalidateQueries({ queryKey: ['declaration', id] });
      }
      await patchEvidenceMap(id, { [result.cell.field]: { source: docType, document_id: docId, confidence: 1.0 } as any });
      queryClient.invalidateQueries({ queryKey: ['declaration-logs', id] });
      setAutoSaveStatus('saved');
      setTimeout(() => setAutoSaveStatus('idle'), 2000);
    } catch { setSnackMsg('Ошибка сохранения'); setAutoSaveStatus('idle'); }
  }, [id, items, queryClient]);

  const handleCancelEdit = useCallback(() => { setEditingField(null); }, []);

  const handleExportPdf = async () => {
    try {
      const r = await client.get(`/declarations/${id}/export-pdf`, { responseType: 'blob' });
      const u = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
      const a = document.createElement('a'); a.href = u; a.download = `DT_${(id || '').slice(0, 8)}.pdf`; a.click();
    } catch { setSnackMsg('Ошибка PDF'); }
  };

  const handleExportXml = async () => {
    try {
      const r = await client.get(`/integration/export-xml/${id}`, { responseType: 'blob', baseURL: '/api/v1' });
      const u = window.URL.createObjectURL(new Blob([r.data], { type: 'application/xml' }));
      const a = document.createElement('a'); a.href = u; a.download = `DT_${(id || '').slice(0, 8)}.xml`; a.click();
    } catch { setSnackMsg('Ошибка XML'); }
  };

  const handleEvidenceChange = useCallback(async (field: string, patch: Partial<FieldEvidence>) => {
    if (!id) return;
    await patchEvidenceMap(id, { [field]: patch });
    queryClient.invalidateQueries({ queryKey: ['declaration', id] });
  }, [id, queryClient]);

  const metrics = useMemo(() => {
    if (!decl) return { filled: 0, total: 0, errors: 0, warnings: 0, manual: 0 };
    let filled = 0, total = 0, errors = 0, warnings = 0, manual = 0;
    const check = (val: string, ev: EvidenceMapEntry | undefined, req?: boolean) => {
      total++;
      const st = getCellState('', val, ev, req);
      if (val) filled++;
      if (st === 'empty') errors++;
      if (st === 'review' || st === 'conflict') warnings++;
      if (st === 'manual') manual++;
    };
    for (const cell of ALL_CELLS_FLAT) {
      check(getFieldValue(decl, cell.field, items, payments, cps), getEvidence(evidenceMap, cell.field), cell.required);
    }
    for (const item of items) {
      for (const tpl of ITEM_CELL_DEFS) {
        check(getItemFieldValue(item, tpl.field), getEvidence(evidenceMap, tpl.field));
      }
    }
    return { filled, total, errors, warnings, manual };
  }, [decl, items, payments, evidenceMap, cps]);

  const selectedCell = useMemo(() => {
    if (!selectedField) return null;
    const result = findCellDef(selectedField);
    return result?.cell ?? null;
  }, [selectedField]);

  const breadcrumbs = useMemo(() => [
    { label: 'Декларации', path: '/declarations' },
    { label: 'Статус', path: `/declarations/${id}/edit` },
    { label: 'Редактирование формы' },
  ], [id]);

  const selectedCellResult = useMemo(() => selectedField ? findCellDef(selectedField) : null, [selectedField]);
  const selectedValue = useMemo(() => {
    if (!selectedCell || !decl) return '';
    if (cellOverrides[selectedCell.id]) return cellOverrides[selectedCell.id];
    if (selectedCellResult?.itemIndex != null) {
      const item = items[selectedCellResult.itemIndex];
      return item ? getItemFieldValue(item, selectedCell.field) : '';
    }
    return getFieldValue(decl, selectedCell.field, items, payments, cps);
  }, [selectedCell, selectedCellResult, decl, items, payments, cps, cellOverrides]);
  const selectedEvidence = selectedCell ? getEvidence(evidenceMap, selectedCell.field) : undefined;
  const selectedState = selectedCell ? getCellState(selectedCell.field, selectedValue, selectedEvidence, selectedCell.required) : 'default';
  const selectedDoc = selectedEvidence?.document_id ? docs.find(d => d.id === selectedEvidence.document_id) : undefined;

  if (isLoading || !decl) {
    return (
      <AppLayout breadcrumbs={breadcrumbs} noPadding>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      </AppLayout>
    );
  }

  const hc = (key: string, sxOv?: Record<string, any>) => {
    const cell = HEADER_CELLS[key];
    const val = cellOverrides[cell.id] ?? getFieldValue(decl, cell.field, items, payments, cps);
    const ev = getEvidence(evidenceMap, cell.field);
    const state = getCellState(cell.field, val, ev, cell.required);
    const sourceStr = getSourceString(ev, docs, cell.computed);
    return { cell, value: val, state, isSelected: selectedField === cell.id, isEditing: editingField === cell.id,
      sourceStr, sxOverride: sxOv, onClick: () => handleFieldSelect(cell.id), onStartEdit: () => handleStartEdit(cell.id),
      onOpenSourceChange: () => handleOpenSourceChange(cell.id), onSaveEdit: handleSaveEdit, onCancelEdit: handleCancelEdit };
  };
  const fc = (key: string, sxOv?: Record<string, any>) => {
    const cell = FOOTER_CELLS[key];
    const val = cellOverrides[cell.id] ?? getFieldValue(decl, cell.field, items, payments, cps);
    const ev = getEvidence(evidenceMap, cell.field);
    const state = getCellState(cell.field, val, ev, cell.required);
    const sourceStr = getSourceString(ev, docs, cell.computed);
    return { cell, value: val, state, isSelected: selectedField === cell.id, isEditing: editingField === cell.id,
      sourceStr, sxOverride: sxOv, onClick: () => handleFieldSelect(cell.id), onStartEdit: () => handleStartEdit(cell.id),
      onOpenSourceChange: () => handleOpenSourceChange(cell.id), onSaveEdit: handleSaveEdit, onCancelEdit: handleCancelEdit };
  };

  const dt2Sheets: DeclarationItem[][] = [];
  for (let i = 1; i < items.length; i += 3) dt2Sheets.push(items.slice(i, i + 3));
  const totalForms = 1 + dt2Sheets.length;

  return (
    <AppLayout breadcrumbs={breadcrumbs} noPadding>
    <Box sx={{ height: 'calc(100vh - 88px)', width: '100%', display: 'flex', flexDirection: 'column', bgcolor: '#f8f8fa', overflow: 'hidden', minWidth: 1280 }}>
      {/* DeclHeader */}
      <Box sx={{
        zIndex: 50, bgcolor: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(8px)',
        borderBottom: '1px solid rgba(226,232,240,0.8)', px: 2.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 48, flexShrink: 0,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
          <Button size="small" startIcon={<FolderOpenIcon sx={{ fontSize: '14px !important' }} />}
            onClick={() => setDocViewerOpen(true)}
            sx={{ fontSize: 13, fontWeight: 500, borderRadius: '8px', px: 1.25, py: 0.75, border: '1px solid rgba(226,232,240,1)', color: '#64748b', textTransform: 'none' }}>
            Документы
            <Box component="span" sx={{ ml: 0.5, px: 0.75, py: 0.25, borderRadius: '10px', bgcolor: 'rgba(241,245,249,1)', fontSize: 10, fontWeight: 600 }}>
              {docs.length}
            </Box>
          </Button>
          <Divider orientation="vertical" sx={{ height: 20 }} />
          <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>Полная декларация</Typography>
          <Typography sx={{ fontSize: 12, color: '#94a3b8' }}>{decl.number_internal || decl.id.slice(0, 13)}</Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <StatusChip status={decl.status} />
          {autoSaveStatus === 'saving' && <Typography sx={{ fontSize: 12, color: '#94a3b8' }}>Сохранение...</Typography>}
          {autoSaveStatus === 'saved' && <Typography sx={{ fontSize: 12, color: '#10b981' }}>Сохранено</Typography>}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Button size="small" startIcon={<PdfIcon sx={{ fontSize: '14px !important' }} />} onClick={handleExportPdf}
            sx={{ fontSize: 13, color: '#64748b', border: '1px solid rgba(226,232,240,1)', borderRadius: '8px', textTransform: 'none', bgcolor: 'white' }}>
            PDF
          </Button>
          <Button size="small" startIcon={<XmlIcon sx={{ fontSize: '14px !important' }} />} onClick={handleExportXml}
            sx={{ fontSize: 13, color: '#64748b', border: '1px solid rgba(226,232,240,1)', borderRadius: '8px', textTransform: 'none', bgcolor: 'white' }}>
            XML
          </Button>
        </Box>
      </Box>

      {/* SummaryStrip */}
      <Box sx={{
        bgcolor: 'white', borderBottom: '1px solid rgba(226,232,240,0.8)', px: 2.5, py: 1,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', minHeight: 40,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <StripMetric icon={<CheckIcon sx={{ fontSize: 12, color: '#10b981' }} />} label="Заполнено" value={`${metrics.filled}/${metrics.total}`} />
          <Box sx={{ height: 16, width: '1px', bgcolor: 'rgba(226,232,240,0.6)' }} />
          <StripMetric icon={<WarningIcon sx={{ fontSize: 12, color: '#ef4444' }} />} label="Ошибки" value={String(metrics.errors)} muted={metrics.errors === 0} />
          <StripMetric icon={<WarningIcon sx={{ fontSize: 12, color: '#f59e0b' }} />} label="Предупреждения" value={String(metrics.warnings)} warn={metrics.warnings > 0} />
          <StripMetric icon={<EditIcon sx={{ fontSize: 12, color: '#3b82f6' }} />} label="Ручные" value={String(metrics.manual)} />
          <Box sx={{ height: 16, width: '1px', bgcolor: 'rgba(226,232,240,0.6)' }} />
          <StripMetric icon={<PdfIcon sx={{ fontSize: 12, color: '#94a3b8' }} />} label="Документы" value={String(docs.length)} />
          <Box sx={{ height: 16, width: '1px', bgcolor: 'rgba(226,232,240,0.6)' }} />
          <StripMetric icon={<XmlIcon sx={{ fontSize: 12, color: '#059669' }} />} label="XML" value="Готов" />
        </Box>
        <Box />
      </Box>

      {/* Main area */}
      <Box sx={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {/* Printed Form */}
        <Box sx={{ flex: 1, overflowY: 'auto', bgcolor: '#f5f6f8', p: 4 }}>
          <Box sx={{
            maxWidth: 1100, mx: 'auto', bgcolor: 'white', borderRadius: 4,
            boxShadow: '0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04)', overflow: 'hidden',
          }}>
            <Box sx={{
              borderBottom: '1px solid #e2e8f0', px: 3, py: 1.75,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              background: 'linear-gradient(to right, rgba(248,250,252,0.8), white)',
            }}>
              <Typography sx={{ fontSize: 15, fontWeight: 600, color: '#334155', letterSpacing: '0.04em' }}>
                ДЕКЛАРАЦИЯ НА ТОВАРЫ
              </Typography>
              <Typography sx={{ fontSize: 12, fontWeight: 500, color: '#94a3b8' }}>
                {decl.number_internal || decl.id.slice(0, 13)}
              </Typography>
            </Box>

            {/* Row 1: Title + 1 + A */}
            <Box sx={{ display: 'flex', borderBottom: '2px solid rgba(226,232,240,0.9)' }}>
              <FormCell {...hc('f1', { width: '27%' })} />
              <FormCell {...hc('fA', { width: '73%' })} />
            </Box>
            {/* Row 2-3: 2 / 3-4 / 5-6-7 */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...hc('f2', { width: '50%', minHeight: 80 })} />
              <Box sx={{ width: '25%', display: 'flex', flexDirection: 'column' }}>
                <FormCell {...hc('f3', { width: '100%' })} />
                <FormCell {...hc('f4', { width: '100%' })} />
              </Box>
              <Box sx={{ width: '25%', display: 'flex', flexDirection: 'column' }}>
                <FormCell {...hc('f5', { width: '100%' })} />
                <FormCell {...hc('f6', { width: '100%' })} />
                <FormCell {...hc('f7', { width: '100%' })} />
              </Box>
            </Box>
            {/* Row 4: 8 / 9 */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...hc('f8', { width: '50%', minHeight: 60 })} />
              <FormCell {...hc('f9', { width: '50%', minHeight: 60 })} />
            </Box>
            {/* Row 5: 10 / 11 / 12 / 13 */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...hc('f10', { width: '12%' })} />
              <FormCell {...hc('f11', { width: '13%' })} />
              <FormCell {...hc('f12', { width: '50%' })} />
              <FormCell {...hc('f13', { width: '25%' })} />
            </Box>
            {/* Row 6: 14 */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...hc('f14', { width: '100%', minHeight: 60 })} />
            </Box>
            {/* Row 7: 15 / 15a / 17 */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...hc('f15', { width: '25%' })} />
              <FormCell {...hc('f15a', { width: '25%' })} />
              <FormCell {...hc('f17', { width: '50%' })} />
            </Box>
            {/* Row 8: 16 / 17a */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...hc('f16', { width: '50%' })} />
              <FormCell {...hc('f17a', { width: '50%' })} />
            </Box>
            {/* Row 9: 18 / 19 / 20 */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...hc('f18', { width: '42%' })} />
              <FormCell {...hc('f19', { width: '8%' })} />
              <FormCell {...hc('f20', { width: '50%' })} />
            </Box>
            {/* Row 10: 21 / 22 / 23 / 24 */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...hc('f21', { width: '50%' })} />
              <FormCell {...hc('f22', { width: '22%' })} />
              <FormCell {...hc('f23', { width: '14%' })} />
              <FormCell {...hc('f24', { width: '14%' })} />
            </Box>
            {/* Row 11: 25 / 26 / 27 / 28 */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...hc('f25', { width: '12%' })} />
              <FormCell {...hc('f26', { width: '12%' })} />
              <FormCell {...hc('f27', { width: '26%' })} />
              <FormCell {...hc('f28', { width: '50%' })} />
            </Box>
            {/* Row 12: 29 / 30 */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...hc('f29', { width: '25%' })} />
              <FormCell {...hc('f30', { width: '75%' })} />
            </Box>

            {/* Item block for first item */}
            {items[0] && (
              <EditableItemBlock item={items[0]} itemIndex={0} paymentItem={payments?.items?.[0]}
                evidenceMap={evidenceMap} docs={docs} cellOverrides={cellOverrides}
                selectedField={selectedField} editingField={editingField}
                onFieldSelect={handleFieldSelect} onStartEdit={handleStartEdit}
                onOpenSourceChange={handleOpenSourceChange} onSaveEdit={handleSaveEdit} onCancelEdit={handleCancelEdit} />
            )}

            {/* Payment section: 47 / 48+49+B */}
            <Box sx={{ display: 'flex' }}>
              <Box sx={{ width: '50%', borderRight: '1px solid rgba(226,232,240,0.7)' }}>
                <Box sx={{ px: 1.25, pt: 0.75 }}>
                  <Typography sx={{ fontSize: 9, color: 'rgba(148,163,184,0.8)', fontWeight: 600 }}>47</Typography>
                  <Typography sx={{ fontSize: 8, color: 'rgba(148,163,184,0.7)' }}>Исчисление платежей</Typography>
                </Box>
                <EditablePaymentTable payments={payments} />
              </Box>
              <Box sx={{ width: '50%', display: 'flex', flexDirection: 'column' }}>
                <FormCell {...fc('f48', { width: '100%' })} />
                <FormCell {...fc('f49', { width: '100%' })} />
                <FormCell {...fc('fb', { width: '100%', flex: 1 })} />
              </Box>
            </Box>

            {/* Section C */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...fc('fC', { width: '100%', minHeight: 28, textAlign: 'center' })} />
            </Box>

            {/* Fields 51 / 52 / 53 */}
            <Box sx={{ display: 'flex' }}>
              <FormCell {...fc('f51', { width: '33%', minHeight: 60 })} />
              <FormCell {...fc('f52', { width: '33%', minHeight: 60 })} />
              <FormCell {...fc('f53', { width: '34%', minHeight: 60 })} />
            </Box>

            {/* Section D + 54 */}
            <Box sx={{ display: 'flex' }}>
              <Box sx={{ width: '50%', display: 'flex', flexDirection: 'column' }}>
                <FormCell {...fc('fd', { width: '100%' })} />
                <FormCell {...fc('fdj', { width: '100%' })} />
              </Box>
              <FormCell {...fc('f54', { width: '50%', minHeight: 80 })} />
            </Box>

            {/* Status bar */}
            <Box sx={{ px: 2, py: 1, bgcolor: 'rgba(236,253,245,0.5)', borderTop: '2px solid rgba(226,232,240,0.9)', textAlign: 'center' }}>
              <Typography sx={{ fontSize: 12, fontWeight: 600, color: '#334155' }}>
                {decl.number_internal || 'ЧЕРНОВИК'} — Статус: {decl.status}
                {decl.customs_office_code && <> | Таможенный орган: {decl.customs_office_code}</>}
              </Typography>
            </Box>
          </Box>

          {/* DT2 additional sheets */}
          {dt2Sheets.map((sheetItems, sheetIdx) => {
            const sheetNumber = sheetIdx + 2;
            const startItemIdx = 1 + sheetIdx * 3;
            return (
              <Box key={sheetIdx} sx={{ mt: 3, bgcolor: 'white', borderRadius: 4, boxShadow: '0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04)', overflow: 'hidden' }}>
                <Box sx={{ borderBottom: '2px solid rgba(226,232,240,0.9)', px: 3, py: 1.75, display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'linear-gradient(to right, rgba(248,250,252,0.8), white)' }}>
                  <Typography sx={{ fontSize: 15, fontWeight: 600, color: '#334155', letterSpacing: '0.04em' }}>
                    ДОБАВОЧНЫЙ ЛИСТ К ДЕКЛАРАЦИИ НА ТОВАРЫ
                  </Typography>
                  <Typography sx={{ fontSize: 12, fontWeight: 500, color: '#94a3b8' }}>
                    Лист {sheetNumber}/{totalForms}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex' }}>
                  <FormCell {...hc('f2', { width: '40%' })} />
                  <FormCell {...hc('f8', { width: '40%' })} />
                  <FormCell {...hc('f3', { width: '20%' })} />
                </Box>
                {sheetItems.map((itm, slotIdx) => {
                  const globalIdx = startItemIdx + slotIdx;
                  return (
                    <EditableItemBlock key={itm.id} item={itm} itemIndex={globalIdx} paymentItem={payments?.items?.[globalIdx]}
                      evidenceMap={evidenceMap} docs={docs} cellOverrides={cellOverrides}
                      selectedField={selectedField} editingField={editingField}
                      onFieldSelect={handleFieldSelect} onStartEdit={handleStartEdit}
                      onOpenSourceChange={handleOpenSourceChange} onSaveEdit={handleSaveEdit} onCancelEdit={handleCancelEdit} />
                  );
                })}
                {sheetItems.length < 3 && Array.from({ length: 3 - sheetItems.length }).map((_, i) => (
                  <Box key={`empty-${i}`} sx={{ borderTop: '1px solid rgba(226,232,240,0.7)', minHeight: 60, position: 'relative' }}>
                    <Box sx={{ position: 'absolute', top: '50%', left: '5%', right: '5%', borderTop: '2px solid rgba(226,232,240,0.5)' }} />
                  </Box>
                ))}
              </Box>
            );
          })}

          {/* ── ДОПОЛНЕНИЕ (лист дополнения к ДТ) ── */}
          {items.length > 0 && (
            <Box sx={{
              mt: 3, bgcolor: 'white', borderRadius: 4,
              boxShadow: '0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04)',
              overflow: 'hidden',
            }}>
              <Box sx={{
                borderBottom: '2px solid rgba(226,232,240,0.9)', px: 3, py: 1.75,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                background: 'linear-gradient(to right, rgba(248,250,252,0.8), white)',
              }}>
                <Typography sx={{ fontSize: 15, fontWeight: 600, color: '#334155', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                  Дополнение на {items.length} л., к ДТ N {decl.number_internal || decl.id.slice(0, 13)}
                </Typography>
              </Box>
              {items.map((itm, idx) => {
                const it = itm as any;
                return (
                  <Box key={itm.id} sx={{ px: 3, py: 2, borderBottom: idx < items.length - 1 ? '1px solid rgba(226,232,240,0.7)' : 'none' }}>
                    <Typography sx={{ fontSize: 13, fontWeight: 600, color: '#1e293b', mb: 1 }}>
                      Товар № {itm.item_no || idx + 1}
                    </Typography>
                    {it.documents_json?.length > 0 && (
                      <Box sx={{ mb: 1.5 }}>
                        <Typography sx={{ fontSize: 11, fontWeight: 600, color: '#475569', mb: 0.5 }}>К ГРАФЕ 44 (Документы)</Typography>
                        <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, '& th, & td': { border: '1px solid rgba(226,232,240,0.7)', p: '3px 6px' } }}>
                          <thead>
                            <tr>
                              <Box component="th" sx={{ fontWeight: 600, textAlign: 'left', color: '#64748b' }}>Код</Box>
                              <Box component="th" sx={{ fontWeight: 600, textAlign: 'left', color: '#64748b' }}>Номер</Box>
                              <Box component="th" sx={{ fontWeight: 600, textAlign: 'left', color: '#64748b' }}>Дата</Box>
                            </tr>
                          </thead>
                          <tbody>
                            {it.documents_json.map((doc: any, di: number) => (
                              <tr key={di}>
                                <Box component="td">{doc.doc_kind_code || doc.code || ''}</Box>
                                <Box component="td">{doc.doc_number || doc.number || ''}</Box>
                                <Box component="td">{doc.doc_date || doc.date || ''}</Box>
                              </tr>
                            ))}
                          </tbody>
                        </Box>
                      </Box>
                    )}
                    <Typography sx={{ fontSize: 11, fontWeight: 600, color: '#475569', mb: 0.5 }}>К ГРАФЕ 31 (Описание и характеристики товара)</Typography>
                    <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, '& th, & td': { border: '1px solid rgba(226,232,240,0.7)', p: '3px 6px' } }}>
                      <thead>
                        <tr>
                          {['Гр.', 'Наименование', 'Производитель', 'Марка', 'Модель', 'Кол-во', 'Ед.изм', 'Артикул', 'Серийные NN'].map(h => (
                            <Box component="th" key={h} sx={{ fontWeight: 600, textAlign: 'left', color: '#64748b', whiteSpace: 'nowrap' }}>{h}</Box>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <Box component="td" sx={{ textAlign: 'center' }}>{itm.item_no || idx + 1}</Box>
                          <Box component="td">{f(it.commercial_name || it.description)}</Box>
                          <Box component="td">{f(it.manufacturer) || 'ОТСУТСТВУЕТ'}</Box>
                          <Box component="td">{f(it.trademark) || 'ОТСУТСТВУЕТ'}</Box>
                          <Box component="td">{f(it.model_name) || 'ОТСУТСТВУЕТ'}</Box>
                          <Box component="td" sx={{ textAlign: 'right' }}>
                            {it.additional_unit_qty ? numFmt(it.additional_unit_qty, 0) : (it.package_count ?? '')}
                          </Box>
                          <Box component="td">{f(it.additional_unit) || 'ШТ'}</Box>
                          <Box component="td">{f(it.article_number) || 'ОТСУТСТВУЕТ'}</Box>
                          <Box component="td">{f(it.serial_number) || 'ОТСУТСТВУЮТ'}</Box>
                        </tr>
                      </tbody>
                    </Box>
                  </Box>
                );
              })}
            </Box>
          )}
        </Box>

        {/* SourceDrawer */}
        {selectedCell && (
          <Box sx={{
            width: 480, flexShrink: 0, bgcolor: '#fafafa', borderLeft: '1px solid rgba(226,232,240,0.8)',
            display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden',
          }}>
            <SourceDrawerContent
              cell={selectedCell} value={selectedValue} state={selectedState}
              evidence={selectedEvidence} sourceDoc={selectedDoc}
              logs={logs} docs={docs}
              forceSourceTab={forceSourceTab}
              onClose={() => { setSelectedField(null); setEditingField(null); setForceSourceTab(false); }}
              onStartEdit={() => handleStartEdit(selectedCell.id)}
              onApplyValue={(v) => handleSaveEdit(selectedCell.id, v)}
              onApplyFromSource={(v, docId, docType) => handleApplyFromSource(selectedCell.id, v, docId, docType)}
              onForceSourceTabClose={() => setForceSourceTab(false)}
              onResetToAi={() => {
                const ev = selectedEvidence;
                if (ev?.raw_value != null) handleSaveEdit(selectedCell.id, String(ev.raw_value));
              }}
              isEditing={editingField === selectedCell.id}
              item={selectedCellResult?.itemIndex != null ? items[selectedCellResult.itemIndex] : undefined}
              declarationId={id}
              onHsSelect={selectedCellResult?.itemIndex != null ? async (code, _name) => {
                const item = items[selectedCellResult.itemIndex!];
                if (!item || !id) return;
                try {
                  await updateItem(id, item.id, { hs_code: code });
                  queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
                  handleSaveEdit(selectedCell.id, code);
                  setSnackMsg(`Код ${code} применён`);
                } catch { setSnackMsg('Ошибка сохранения кода'); }
              } : undefined}
              declaration={decl}
              allItems={items}
            />
          </Box>
        )}
      </Box>

      {/* BottomBar */}
      <Box sx={{
        zIndex: 50, bgcolor: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(8px)',
        borderTop: '1px solid rgba(226,232,240,0.8)', px: 2.5, py: 1,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 46, flexShrink: 0,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <BottomInd icon={<CheckIcon sx={{ fontSize: 12 }} />} text={`${metrics.errors} критических ошибок`} color="#059669" bg="rgba(236,253,245,1)" />
          <BottomInd icon={<WarningIcon sx={{ fontSize: 12 }} />} text={`${metrics.warnings} предупреждения`} color="#d97706" bg="rgba(255,251,235,1)" />
          <BottomInd icon={<EditIcon sx={{ fontSize: 12 }} />} text={`${metrics.manual} ручных изменения`} color="#3b82f6" bg="rgba(239,246,255,1)" />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Button size="small" startIcon={<ShieldIcon sx={{ fontSize: '14px !important' }} />}
            onClick={() => setSnackMsg('ЭЦП: будет в следующей версии')}
            sx={{ fontSize: 13, color: '#64748b', border: '1px solid rgba(226,232,240,1)', borderRadius: '8px', textTransform: 'none', bgcolor: 'white' }}>
            ЭЦП
          </Button>
          <Button size="small" variant="contained" startIcon={<SendIcon sx={{ fontSize: '14px !important' }} />}
            onClick={() => setSnackMsg('ФТС: будет в следующей версии')}
            sx={{ fontSize: 13, fontWeight: 500, bgcolor: '#059669', '&:hover': { bgcolor: '#047857' }, borderRadius: '8px', textTransform: 'none', boxShadow: 'none' }}>
            Подписать и отправить
          </Button>
        </Box>
      </Box>

      <DocumentViewer documents={docs} open={docViewerOpen} onClose={() => setDocViewerOpen(false)}
        evidenceMap={decl.evidence_map as any} onEvidenceChange={handleEvidenceChange} />
      <Snackbar open={!!snackMsg} autoHideDuration={3000} onClose={() => setSnackMsg('')} message={snackMsg} />
    </Box>
    </AppLayout>
  );
};

/* ================== EditableItemBlock ================== */

function EditableItemBlock({ item, itemIndex, paymentItem, evidenceMap, docs, cellOverrides, selectedField, editingField,
  onFieldSelect, onStartEdit, onOpenSourceChange, onSaveEdit, onCancelEdit }: {
  item: DeclarationItem; itemIndex: number; paymentItem?: PaymentResult['items'][0];
  evidenceMap?: Record<string, EvidenceMapEntry>; docs: DocType[]; cellOverrides: Record<string, string>;
  selectedField: string | null; editingField: string | null;
  onFieldSelect: (id: string) => void; onStartEdit: (id: string) => void; onOpenSourceChange: (id: string) => void;
  onSaveEdit: (id: string, val: string) => void; onCancelEdit: () => void;
}) {
  const ic = (field: string, sxOv: Record<string, any>) => {
    const cellId = makeItemCellId(itemIndex, field);
    const tpl = ITEM_CELL_DEFS.find(t => t.field === field)!;
    const cell = makeItemCell(itemIndex, tpl);
    const val = cellOverrides[cellId] ?? getItemFieldValue(item, field);
    const ev = getEvidence(evidenceMap, field);
    const state = getCellState(field, val, ev);
    const sourceStr = getSourceString(ev, docs);
    return { cell, value: val, state, isSelected: selectedField === cellId, isEditing: editingField === cellId,
      sourceStr, sxOverride: sxOv, onClick: () => onFieldSelect(cellId), onStartEdit: () => onStartEdit(cellId),
      onOpenSourceChange: () => onOpenSourceChange(cellId), onSaveEdit, onCancelEdit };
  };

  return (
    <Box sx={{ borderTop: '2px solid rgba(226,232,240,0.9)' }}>
      {/* Row: 31 (57%) | 32-43 (43%) */}
      <Box sx={{ display: 'flex' }}>
        <FormCell {...ic('description', { width: '57%', minHeight: 140 })} />
        <Box sx={{ width: '43%', display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ display: 'flex' }}>
            <FormCell {...ic('item_no', { width: '35%' })} />
            <FormCell {...ic('hs_code', { width: '65%' })} />
          </Box>
          <Box sx={{ display: 'flex' }}>
            <FormCell {...ic('country_origin_code', { width: '35%' })} />
            <FormCell {...ic('gross_weight', { width: '40%' })} />
            <FormCell {...ic('preference_code', { width: '25%' })} />
          </Box>
          <Box sx={{ display: 'flex' }}>
            <FormCell {...ic('procedure_code', { width: '35%' })} />
            <FormCell {...ic('net_weight', { width: '40%' })} />
            <FormCell {...ic('quota_info', { width: '25%' })} />
          </Box>
          <FormCell {...ic('prev_doc_ref', { width: '100%' })} />
          <Box sx={{ display: 'flex' }}>
            <FormCell {...ic('additional_unit_qty', { width: '35%' })} />
            <FormCell {...ic('unit_price', { width: '40%' })} />
            <FormCell {...ic('mos_method_code', { width: '25%' })} />
          </Box>
        </Box>
      </Box>
      {/* Row: 44 (57%) | 45+46 (43%) */}
      <Box sx={{ display: 'flex' }}>
        <FormCell {...ic('documents_json', { width: '57%', minHeight: 60 })} />
        <Box sx={{ width: '43%', display: 'flex', flexDirection: 'column' }}>
          <FormCell {...ic('customs_value_rub', { width: '100%' })} />
          <FormCell {...ic('statistical_value_usd', { width: '100%' })} />
        </Box>
      </Box>
    </Box>
  );
}

/* ================== EditablePaymentTable ================== */

function EditablePaymentTable({ payments }: { payments: PaymentResult | null }) {
  const totals = payments?.totals;
  const firstPi = payments?.items?.[0];
  const thSx = { border: '1px solid rgba(226,232,240,0.6)', p: '3px 6px', fontSize: 10, color: '#64748b', fontWeight: 600 };
  const tdSx = { border: '1px solid rgba(226,232,240,0.6)', p: '3px 6px', fontSize: 11, color: '#1e293b' };
  const tdR = { ...tdSx, textAlign: 'right' as const };
  const tdC = { ...tdSx, textAlign: 'center' as const };

  return (
    <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', m: 0 }}>
      <thead>
        <tr>
          <Box component="th" sx={thSx}>Вид</Box>
          <Box component="th" sx={{ ...thSx, textAlign: 'right' }}>Основа начисления</Box>
          <Box component="th" sx={{ ...thSx, textAlign: 'center' }}>Ставка</Box>
          <Box component="th" sx={{ ...thSx, textAlign: 'right' }}>Сумма</Box>
          <Box component="th" sx={thSx}>СП</Box>
        </tr>
      </thead>
      <tbody>
        <tr>
          <Box component="td" sx={tdSx}>1010</Box>
          <Box component="td" sx={tdR}>{numFmt(totals?.total_customs_value)}</Box>
          <Box component="td" sx={tdC}>—</Box>
          <Box component="td" sx={tdR}>{numFmt(totals?.customs_fee)}</Box>
          <Box component="td" sx={tdSx}>ИУ</Box>
        </tr>
        <tr>
          <Box component="td" sx={tdSx}>2010</Box>
          <Box component="td" sx={tdR}>{numFmt(totals?.total_customs_value)}</Box>
          <Box component="td" sx={tdC}>{firstPi?.duty?.rate || 0}%</Box>
          <Box component="td" sx={tdR}>{numFmt(totals?.total_duty)}</Box>
          <Box component="td" sx={tdSx}>ИУ</Box>
        </tr>
        <tr>
          <Box component="td" sx={tdSx}>5010</Box>
          <Box component="td" sx={tdR}>{numFmt(firstPi?.vat?.base)}</Box>
          <Box component="td" sx={tdC}>{firstPi?.vat?.rate || 20}%</Box>
          <Box component="td" sx={tdR}>{numFmt(totals?.total_vat)}</Box>
          <Box component="td" sx={tdSx}>ИУ</Box>
        </tr>
        <tr>
          <Box component="td" sx={{ ...tdSx, fontWeight: 700, borderTop: '2px solid rgba(226,232,240,0.9)' }} colSpan={3}>Всего:</Box>
          <Box component="td" sx={{ ...tdR, fontWeight: 700, borderTop: '2px solid rgba(226,232,240,0.9)' }}>{numFmt(totals?.grand_total)}</Box>
          <Box component="td" sx={{ ...tdSx, borderTop: '2px solid rgba(226,232,240,0.9)' }} />
        </tr>
      </tbody>
    </Box>
  );
}

/* ================== FormCell ================== */

function FormCell({ cell, value, state, isSelected, isEditing, sourceStr, sxOverride, onClick, onStartEdit, onOpenSourceChange, onSaveEdit, onCancelEdit }: {
  cell: CellDef; value: string; state: CellState; isSelected: boolean; isEditing: boolean; sourceStr: string;
  sxOverride?: Record<string, any>;
  onClick: () => void; onStartEdit: () => void; onOpenSourceChange: () => void;
  onSaveEdit: (id: string, val: string) => void; onCancelEdit: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const [localVal, setLocalVal] = useState(value);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const st = STATE_STYLES[state];

  useEffect(() => { if (isEditing) { setLocalVal(value); setTimeout(() => textareaRef.current?.focus(), 50); } }, [isEditing, value]);

  const isTall = cell.tall;
  const isMultiline = value.includes('\n');

  return (
    <Box
      onClick={isEditing ? undefined : onClick}
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
      sx={{
        position: 'relative', cursor: 'pointer', transition: 'all 0.15s',
        ...(cell.col && cell.row ? { gridColumn: cell.col, gridRow: cell.row } : {}),
        border: '1px solid rgba(226,232,240,0.7)', margin: '-0.5px',
        minHeight: isTall ? 80 : 48, boxSizing: 'border-box',
        bgcolor: isEditing ? 'rgba(239,246,255,0.4)' : isSelected ? 'rgba(239,246,255,0.3)' : hovered && !isSelected ? 'rgba(248,250,252,0.8)' : st.bg,
        outline: isEditing ? '2px solid rgba(59,130,246,0.6)' : isSelected ? '2px solid rgba(96,165,250,0.5)' : 'none',
        outlineOffset: -2, zIndex: isEditing ? 20 : isSelected ? 10 : 0,
        ...sxOverride,
      }}
    >
      {state !== 'default' && (
        <Box sx={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 2.5, bgcolor: st.stripe }} />
      )}

      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.75, px: 1.25, pt: 0.75 }}>
        {cell.num && <Typography sx={{ fontSize: 10, color: 'rgba(148,163,184,0.8)', fontWeight: 600, flexShrink: 0 }}>{cell.num}</Typography>}
        <Typography sx={{ fontSize: 10, color: 'rgba(148,163,184,0.7)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', lineHeight: 1.2 }}>
          {cell.label}
        </Typography>
        {state !== 'default' && !isEditing && (
          <Box sx={{ ml: 'auto', flexShrink: 0 }}>{DOT_ICONS[state]}</Box>
        )}
        {isEditing && (
          <Box sx={{ ml: 'auto', fontSize: 10, fontWeight: 600, color: '#3b82f6', px: 0.75, py: 0.25, borderRadius: '4px', bgcolor: 'rgba(239,246,255,1)', border: '1px solid rgba(191,219,254,0.6)' }}>
            Редактирование
          </Box>
        )}
      </Box>

      <Box sx={{ px: 1.25, pb: sourceStr && !cell.computed && !isEditing ? 0.25 : 1, pt: 0.25 }}>
        {isEditing ? (
          <textarea ref={textareaRef} value={localVal} onChange={e => setLocalVal(e.target.value)}
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', resize: 'none', border: 'none', outline: 'none',
              background: 'rgba(255,255,255,0.8)', fontSize: 13, color: '#0f172a', fontWeight: 500,
              fontFamily: 'inherit', borderRadius: 6, padding: '4px 6px', margin: '-4px -6px',
              minHeight: isTall ? 56 : 22,
            }}
            rows={isTall ? 3 : 1}
          />
        ) : state === 'empty' && !value ? (
          <Typography sx={{ fontSize: 12, color: '#ef4444', fontStyle: 'italic' }}>Не заполнено</Typography>
        ) : isMultiline ? (
          <Box component="pre" sx={{ fontSize: 12, color: '#1e293b', whiteSpace: 'pre-wrap', lineHeight: 1.4, m: 0, fontFamily: 'inherit', fontWeight: 500 }}>
            {value}
          </Box>
        ) : (
          <Typography sx={{ fontSize: 13, color: '#1e293b', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {value}
          </Typography>
        )}
      </Box>

      {!cell.computed && sourceStr && !isEditing && (
        <Typography sx={{ fontSize: 9, color: '#94a3b8', px: 1.25, pb: 0.75, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', lineHeight: 1 }}>
          {sourceStr}
        </Typography>
      )}

      {isEditing && (
        <Box sx={{ position: 'absolute', top: 4, right: 4, display: 'flex', gap: 0.25, zIndex: 30 }}>
          <IconButton size="small" onClick={e => { e.stopPropagation(); onSaveEdit(cell.id, localVal); }}
            sx={{ p: 0.75, borderRadius: '8px', bgcolor: '#22c55e', border: '1px solid #16a34a', '&:hover': { bgcolor: '#16a34a' } }}>
            <CheckIcon sx={{ fontSize: 12, color: 'white' }} />
          </IconButton>
          <IconButton size="small" onClick={e => { e.stopPropagation(); onCancelEdit(); }}
            sx={{ p: 0.75, borderRadius: '8px', bgcolor: 'white', border: '1px solid #e2e8f0', '&:hover': { bgcolor: '#fef2f2' } }}>
            <CloseIcon sx={{ fontSize: 12, color: '#94a3b8' }} />
          </IconButton>
        </Box>
      )}

      {hovered && !isEditing && (
        <Box sx={{ position: 'absolute', top: 4, right: 4, display: 'flex', gap: 0.25, zIndex: 20 }}>
          <IconButton size="small" onClick={e => { e.stopPropagation(); onClick(); }}
            sx={{ p: 0.5, borderRadius: '6px', bgcolor: 'rgba(255,255,255,0.9)', border: '1px solid rgba(226,232,240,0.8)', '&:hover': { bgcolor: 'rgba(239,246,255,1)' } }}>
            <InfoIcon sx={{ fontSize: 12, color: '#64748b' }} />
          </IconButton>
          <IconButton size="small" onClick={e => { e.stopPropagation(); onStartEdit(); }}
            sx={{ p: 0.5, borderRadius: '6px', bgcolor: 'rgba(255,255,255,0.9)', border: '1px solid rgba(226,232,240,0.8)', '&:hover': { bgcolor: 'rgba(245,243,255,1)' } }}>
            <EditIcon sx={{ fontSize: 12, color: '#64748b' }} />
          </IconButton>
          <IconButton size="small" onClick={e => { e.stopPropagation(); onOpenSourceChange(); }}
            sx={{ p: 0.5, borderRadius: '6px', bgcolor: 'rgba(255,255,255,0.9)', border: '1px solid rgba(226,232,240,0.8)', '&:hover': { bgcolor: 'rgba(255,251,235,1)' } }}>
            <FileUpIcon sx={{ fontSize: 12, color: '#64748b' }} />
          </IconButton>
        </Box>
      )}
    </Box>
  );
}

/* ================== SourceDrawerContent ================== */

function SourceDrawerContent({ cell, value, state, evidence, sourceDoc, logs, docs, forceSourceTab, onClose, onStartEdit, onApplyValue, onApplyFromSource, onForceSourceTabClose, isEditing, onResetToAi, item, declarationId, onHsSelect, declaration, allItems }: {
  cell: CellDef; value: string; state: CellState; evidence?: EvidenceMapEntry; sourceDoc?: DocType;
  logs: DeclarationLogEntry[]; docs: DocType[]; forceSourceTab: boolean;
  onClose: () => void; onStartEdit: () => void; onApplyValue: (v: string) => void;
  onApplyFromSource: (value: string, docId: string, docType: string) => void;
  onForceSourceTabClose: () => void; isEditing: boolean; onResetToAi?: () => void;
  item?: DeclarationItem; declarationId?: string; onHsSelect?: (code: string, name: string) => void;
  declaration?: Declaration; allItems?: DeclarationItem[];
}) {
  const st = STATE_STYLES[state];
  const confidence = evidence?.confidence != null ? Math.round(evidence.confidence * 100) : null;
  const confColor = confidence != null ? (confidence >= 90 ? '#059669' : confidence >= 75 ? '#d97706' : '#dc2626') : '#94a3b8';
  const confBarColor = confidence != null ? (confidence >= 90 ? '#22c55e' : confidence >= 75 ? '#f59e0b' : '#ef4444') : '#e2e8f0';
  const confTrackColor = confidence != null ? (confidence >= 90 ? '#bbf7d0' : confidence >= 75 ? '#fde68a' : '#fecaca') : '#f1f5f9';

  const sourceLabel = evidence ? (SOURCE_LABELS[evidence.source] || evidence.source) : '\u2014';
  const sourceFile = sourceDoc?.original_filename || (sourceDoc?.file_key?.split('/').pop()) || null;

  const [sourceMode, setSourceMode] = useState(false);
  const [selectedSourceDoc, setSelectedSourceDoc] = useState<DocType | null>(null);
  const [selectedExtractedField, setSelectedExtractedField] = useState<string | null>(null);

  useEffect(() => {
    setSourceMode(forceSourceTab);
    setSelectedSourceDoc(null);
    setSelectedExtractedField(null);
  }, [cell.id, forceSourceTab]);

  const handleExitSourceMode = () => {
    setSourceMode(false);
    setSelectedSourceDoc(null);
    setSelectedExtractedField(null);
    onForceSourceTabClose();
  };

  const handleApplySelected = () => {
    if (!selectedSourceDoc || !selectedExtractedField) return;
    const val = String((selectedSourceDoc.parsed_data as any)?.[selectedExtractedField] ?? '');
    onApplyFromSource(val, selectedSourceDoc.id, selectedSourceDoc.doc_type);
    handleExitSourceMode();
  };

  const fieldLogs = useMemo(() => {
    return logs.filter(l => {
      const nv = l.new_value as any;
      const ov = l.old_value as any;
      return (nv && cell.field in nv) || (ov && cell.field in ov);
    }).slice(0, 5);
  }, [logs, cell.field]);

  const previewValue = evidence?.raw_value || value || '\u2014';
  const previewPage = evidence?.graph ?? 1;

  return (
    <>
      {/* Header */}
      <Box sx={{ bgcolor: 'white', px: 2.5, py: 1.5, borderBottom: '1px solid rgba(226,232,240,0.6)', flexShrink: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.75 }}>
          <Typography sx={{ fontSize: 11, color: '#94a3b8', fontWeight: 500, letterSpacing: '0.05em' }}>ПОЛЕ ДЕКЛАРАЦИИ</Typography>
          <IconButton size="small" onClick={onClose} sx={{ p: 0.5, color: '#94a3b8' }}><CloseIcon sx={{ fontSize: 16 }} /></IconButton>
        </Box>
        <Typography sx={{ fontSize: 15, fontWeight: 600, color: '#0f172a' }}>Графа {cell.num}. {cell.label}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.75, fontSize: 11, color: '#94a3b8' }}>
          <Typography sx={{ fontSize: 'inherit', color: 'inherit', cursor: 'pointer', '&:hover': { color: '#475569' } }}>Декларация</Typography>
          <ChevronRightIcon sx={{ fontSize: 10 }} />
          <Typography sx={{ fontSize: 'inherit', color: 'inherit', cursor: 'pointer', '&:hover': { color: '#475569' } }}>{cell.section}</Typography>
          <ChevronRightIcon sx={{ fontSize: 10 }} />
          <Typography sx={{ fontSize: 'inherit', color: '#475569', fontWeight: 500 }}>Графа {cell.num}</Typography>
        </Box>
      </Box>

      {/* Scrollable body */}
      <Box sx={{ flex: 1, overflowY: 'auto' }}>
        {sourceMode ? (
          /* ─── Source Change Flow ─── */
          !selectedSourceDoc ? (
            <Box sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <IconButton size="small" onClick={handleExitSourceMode} sx={{ p: 0.5, color: '#64748b' }}>
                  <ChevronLeftIcon sx={{ fontSize: 18 }} />
                </IconButton>
                <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>Выберите документ-источник</Typography>
              </Box>
              {docs.length === 0 && (
                <Typography sx={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', py: 4 }}>Нет загруженных документов</Typography>
              )}
              {docs.map(doc => {
                const fieldCount = doc.parsed_data ? Object.keys(doc.parsed_data).length : 0;
                return (
                  <Box key={doc.id} onClick={() => setSelectedSourceDoc(doc)} sx={{
                    display: 'flex', alignItems: 'center', gap: 1.5, p: 1.5, mb: 1,
                    bgcolor: 'white', borderRadius: 3, border: '1px solid rgba(226,232,240,0.7)', boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                    cursor: 'pointer', transition: 'all 0.15s', '&:hover': { borderColor: '#93c5fd', bgcolor: 'rgba(239,246,255,0.5)' },
                  }}>
                    <Box sx={{ p: 1, bgcolor: 'rgba(241,245,249,1)', borderRadius: 2, display: 'flex' }}>
                      <FileIcon sx={{ fontSize: 20, color: '#64748b' }} />
                    </Box>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography sx={{ fontSize: 13, fontWeight: 500, color: '#1e293b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {doc.original_filename}
                      </Typography>
                      <Typography sx={{ fontSize: 10, color: '#94a3b8', mt: 0.25 }}>
                        {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type} {'\u00b7'} {fieldCount} извлеч. полей
                      </Typography>
                    </Box>
                    <ChevronRightIcon sx={{ fontSize: 16, color: '#cbd5e1' }} />
                  </Box>
                );
              })}
            </Box>
          ) : (
            <Box sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <IconButton size="small" onClick={() => { setSelectedSourceDoc(null); setSelectedExtractedField(null); }} sx={{ p: 0.5, color: '#64748b' }}>
                  <ChevronLeftIcon sx={{ fontSize: 18 }} />
                </IconButton>
                <Box sx={{ minWidth: 0 }}>
                  <Typography sx={{ fontSize: 13, fontWeight: 600, color: '#1e293b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {selectedSourceDoc.original_filename}
                  </Typography>
                  <Typography sx={{ fontSize: 10, color: '#94a3b8' }}>Выберите значение для применения</Typography>
                </Box>
              </Box>
              {Object.keys(selectedSourceDoc.parsed_data || {}).length === 0 && (
                <Typography sx={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', py: 4 }}>Нет извлечённых полей</Typography>
              )}
              {Object.entries(selectedSourceDoc.parsed_data || {}).map(([key, val]) => {
                const isSel = selectedExtractedField === key;
                return (
                  <Box key={key} onClick={() => setSelectedExtractedField(key)} sx={{
                    display: 'flex', alignItems: 'center', gap: 1, p: 1.25, mb: 0.75,
                    bgcolor: isSel ? 'rgba(239,246,255,0.6)' : 'white', borderRadius: 3,
                    border: '1px solid', borderColor: isSel ? '#93c5fd' : 'rgba(226,232,240,0.7)',
                    cursor: 'pointer', transition: 'all 0.15s',
                  }}>
                    <Box sx={{
                      width: 16, height: 16, borderRadius: '50%', flexShrink: 0,
                      border: '2px solid', borderColor: isSel ? '#3b82f6' : '#d1d5db',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {isSel && <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#3b82f6' }} />}
                    </Box>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography sx={{ fontSize: 10, color: '#64748b' }}>{key}</Typography>
                      <Typography sx={{ fontSize: 12, fontWeight: 500, color: '#1e293b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {String(val ?? '')}
                      </Typography>
                    </Box>
                  </Box>
                );
              })}
              {selectedExtractedField && (
                <Button fullWidth variant="contained" size="small" onClick={handleApplySelected}
                  sx={{ mt: 2, bgcolor: '#059669', '&:hover': { bgcolor: '#047857' }, borderRadius: '12px', textTransform: 'none', boxShadow: 'none', fontSize: 12, py: 1 }}>
                  Применить выбранное значение
                </Button>
              )}
            </Box>
          )
        ) : (
          /* ─── Normal Drawer Content ─── */
          <>
            {/* Current value */}
            <Box sx={{ mx: 2, mt: 2 }}>
              <Box sx={{ bgcolor: 'white', borderRadius: 4, border: '1px solid rgba(226,232,240,0.7)', boxShadow: '0 1px 2px rgba(0,0,0,0.04)', overflow: 'hidden' }}>
                <Box sx={{ px: 2, py: 1.75 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography sx={{ fontSize: 10, color: '#94a3b8', fontWeight: 500, letterSpacing: '0.05em' }}>ТЕКУЩЕЕ ЗНАЧЕНИЕ</Typography>
                    {state !== 'default' && (
                      <Box sx={{
                        display: 'inline-flex', alignItems: 'center', gap: 0.5, fontSize: 9, px: 1, py: 0.25,
                        borderRadius: '10px', border: '1px solid', bgcolor: st.badgeBg, borderColor: st.badgeBorder, color: st.badgeText,
                      }}>
                        {DOT_ICONS[state]}{st.badgeLabel}
                      </Box>
                    )}
                  </Box>
                  {state === 'empty' ? (
                    <Typography sx={{ fontSize: 22, color: '#cbd5e1', fontStyle: 'italic', fontWeight: 500 }}>Не заполнено</Typography>
                  ) : (
                    <Typography sx={{ fontSize: 22, fontWeight: 600, color: '#0f172a', letterSpacing: '-0.02em' }}>{value}</Typography>
                  )}
                </Box>
                {confidence != null && (
                  <Box sx={{
                    borderTop: '1px solid', borderColor: state === 'review' ? 'rgba(253,230,138,0.4)' : state === 'empty' ? 'rgba(254,202,202,0.4)' : 'rgba(167,243,208,0.4)',
                    px: 2, py: 1.25, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    bgcolor: state === 'review' ? 'rgba(255,251,235,0.4)' : state === 'empty' ? 'rgba(254,242,242,0.4)' : 'rgba(236,253,245,0.4)',
                  }}>
                    <Typography sx={{ fontSize: 10, color: confColor }}>
                      {state === 'review' ? 'Рекомендуется проверить' : state === 'empty' ? 'Обязательное поле' : 'Значение подтверждено'}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      <Box sx={{ width: 52, height: 5, borderRadius: 3, bgcolor: confTrackColor, overflow: 'hidden' }}>
                        <Box sx={{ height: '100%', width: `${confidence}%`, bgcolor: confBarColor, borderRadius: 3 }} />
                      </Box>
                      <Typography sx={{ fontSize: 10, fontWeight: 600, color: confColor }}>{confidence}%</Typography>
                    </Box>
                  </Box>
                )}
              </Box>
            </Box>

            {/* Main source */}
            {evidence && (
              <Box sx={{ px: 2, pt: 2 }}>
                <DrawerLabel text="ОСНОВНОЙ ИСТОЧНИК" />
                <Box sx={{
                  display: 'flex', alignItems: 'center', gap: 1.5, p: 1.5, bgcolor: 'white',
                  borderRadius: 4, border: '1px solid rgba(226,232,240,0.7)', boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                  cursor: 'pointer', '&:hover': { borderColor: 'rgba(203,213,225,1)' },
                }}>
                  <Box sx={{ p: 1.25, bgcolor: 'rgba(239,246,255,1)', borderRadius: 3, border: '1px solid rgba(191,219,254,0.6)', display: 'flex' }}>
                    <PdfIcon sx={{ fontSize: 20, color: '#3b82f6' }} />
                  </Box>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography sx={{ fontSize: 13, fontWeight: 500, color: '#1e293b' }}>{sourceFile || sourceLabel}</Typography>
                    <Typography sx={{ fontSize: 11, color: '#94a3b8', mt: 0.25 }}>{sourceLabel}</Typography>
                    <Box sx={{
                      display: 'inline-flex', alignItems: 'center', gap: 0.5, mt: 0.75,
                      fontSize: 9, px: 0.75, py: 0.25, borderRadius: '10px',
                      bgcolor: '#f5f3ff', border: '1px solid rgba(196,181,253,0.7)', color: '#7c3aed',
                    }}>
                      <AiIcon sx={{ fontSize: 10 }} />AI извлечено
                    </Box>
                  </Box>
                  <ExternalIcon sx={{ fontSize: 14, color: '#cbd5e1' }} />
                </Box>
              </Box>
            )}

            {/* Document preview with real data */}
            {evidence && (
              <Box sx={{ px: 2, pt: 2 }}>
                <DrawerLabel text="ПРЕДПРОСМОТР ДОКУМЕНТА" />
                <Box sx={{ bgcolor: 'white', borderRadius: 4, border: '1px solid rgba(226,232,240,0.7)', boxShadow: '0 1px 2px rgba(0,0,0,0.04)', overflow: 'hidden' }}>
                  {sourceFile && (
                    <Box sx={{ px: 2, pt: 1.5, pb: 0.5 }}>
                      <Typography sx={{ fontSize: 11, fontWeight: 500, color: '#475569' }}>{sourceFile}</Typography>
                      <Typography sx={{ fontSize: 9, color: '#94a3b8', mt: 0.25 }}>{sourceLabel}</Typography>
                    </Box>
                  )}
                  <Box sx={{ p: 2 }}>
                    <Box sx={{ bgcolor: '#f5f5f2', borderRadius: 3, border: '1px solid rgba(226,232,240,0.5)', p: 2.5, minHeight: 100, position: 'relative' }}>
                      <Box sx={{ mb: 1.5 }}>
                        <Box sx={{ height: 8, bgcolor: 'rgba(148,163,184,0.3)', borderRadius: 1, width: 112, mb: 0.5 }} />
                        <Box sx={{ height: 6, bgcolor: 'rgba(226,232,240,0.4)', borderRadius: 1, width: 80 }} />
                      </Box>
                      <Box sx={{ height: 6, bgcolor: 'rgba(226,232,240,0.3)', borderRadius: 1, width: '90%', mb: 0.75 }} />
                      <Box sx={{
                        position: 'relative', p: 1.5, mx: -0.5, borderRadius: 3,
                        border: '2px solid #fbbf24', bgcolor: 'rgba(255,251,235,0.6)', boxShadow: '0 0 0 3px rgba(251,191,36,0.12)',
                      }}>
                        <Typography sx={{ fontSize: 12, fontWeight: 700, color: '#92400e', textAlign: 'right' }}>{previewValue}</Typography>
                        <Box sx={{
                          position: 'absolute', top: -10, right: -10, width: 20, height: 20, borderRadius: '50%',
                          bgcolor: '#fbbf24', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
                        }}>
                          <AiIcon sx={{ fontSize: 12, color: 'white' }} />
                        </Box>
                      </Box>
                      <Box sx={{ mt: 1.5 }}>
                        <Box sx={{ height: 6, bgcolor: 'rgba(226,232,240,0.3)', borderRadius: 1, width: '70%', mb: 0.5 }} />
                        <Box sx={{ height: 6, bgcolor: 'rgba(226,232,240,0.25)', borderRadius: 1, width: '50%' }} />
                      </Box>
                    </Box>
                  </Box>
                  <Box sx={{ bgcolor: 'rgba(248,250,252,1)', borderTop: '1px solid rgba(226,232,240,0.5)', px: 2, py: 0.75, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Typography sx={{ fontSize: 9, color: '#94a3b8' }}>Страница {previewPage}</Typography>
                    {sourceDoc && (
                      <Typography
                        component="a"
                        href={`/api/v1/files/${sourceDoc.file_key}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        sx={{ fontSize: 10, color: '#2563eb', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 0.5, textDecoration: 'none', '&:hover': { color: '#1d4ed8' } }}
                      >
                        Открыть документ<ExternalIcon sx={{ fontSize: 10 }} />
                      </Typography>
                    )}
                  </Box>
                </Box>
              </Box>
            )}

            {/* HS Code AI Suggestions (field 33) */}
            {cell.field === 'hs_code' && item && onHsSelect && (
              <Box sx={{ px: 2, pt: 2 }}>
                <DrawerLabel text="ПОДБОР КОДА ТН ВЭД" />
                <Box sx={{
                  bgcolor: 'white', borderRadius: 4,
                  border: '1px solid rgba(226,232,240,0.7)',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.04)', p: 1.5,
                }}>
                  <Typography sx={{ fontSize: 12, color: '#64748b', mb: 0.5 }}>
                    Товар: {item.description || '—'}
                  </Typography>
                  <HSCodeSuggestions
                    description={item.description || ''}
                    currentCode={item.hs_code || ''}
                    onSelect={onHsSelect}
                    countryOrigin={item.country_origin_code}
                    unitPrice={item.unit_price ?? undefined}
                    declarationId={declarationId}
                  />
                </Box>
              </Box>
            )}

            {/* HS drift warning (field 33) */}
            {cell.field === 'hs_code' && item && (item as any).drift_status && (
              <Box sx={{ px: 2, pt: 1.5 }}>
                <Alert severity="warning" sx={{ fontSize: 12 }} variant="outlined">
                  Дрейф кода: ранее использовался <b>{(item as any).historical_hs_code}</b>
                  {(item as any).historical_usage_count && ` (${(item as any).historical_usage_count} раз)`}
                  {(item as any).drift_message && ` — ${(item as any).drift_message}`}
                </Alert>
              </Box>
            )}

            {/* Requirements for HS code (field 33) */}
            {cell.field === 'hs_code' && item && (
              <Box sx={{ px: 2, pt: 1.5 }}>
                <DrawerLabel text="ТРЕБОВАНИЯ К ДОКУМЕНТАМ" />
                <RequirementsPanel
                  hsCode={item.hs_code || ''}
                  description={item.description || ''}
                />
              </Box>
            )}

            {/* Risk assessment for item (field 33) */}
            {cell.field === 'hs_code' && item && ((item as any).risk_score || 0) > 0 && (
              <Box sx={{ px: 2, pt: 1.5 }}>
                <DrawerLabel text="ОЦЕНКА РИСКОВ" />
                <RiskPanel
                  riskScore={(item as any).risk_score || 0}
                  risks={((item as any).risk_flags as any)?.risks || []}
                />
              </Box>
            )}

            {/* AI Explain Panel */}
            {declaration && allItems && (
              <Box sx={{ px: 2, pt: 2 }}>
                <AiExplainPanel declaration={declaration} items={allItems} />
              </Box>
            )}

            {/* Correction */}
            <Box sx={{ px: 2, pt: 2 }}>
              <DrawerLabel text="ИСПРАВЛЕНИЕ" />
              {isEditing && (
                <Box sx={{
                  display: 'flex', alignItems: 'center', gap: 1, p: 1.5, bgcolor: 'rgba(239,246,255,0.6)',
                  borderRadius: 3, border: '1px solid rgba(191,219,254,0.5)', mb: 1.5,
                }}>
                  <EditIcon sx={{ fontSize: 14, color: '#3b82f6' }} />
                  <Box>
                    <Typography sx={{ fontSize: 11, fontWeight: 500, color: '#1d4ed8' }}>Режим редактирования</Typography>
                    <Typography sx={{ fontSize: 10, color: 'rgba(59,130,246,0.8)', mt: 0.25 }}>Измените значение на форме и нажмите галочку</Typography>
                  </Box>
                </Box>
              )}
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0.75 }}>
                <ActionCard icon={<EditIcon sx={{ fontSize: 14, color: '#8b5cf6' }} />} label="Изменить вручную"
                  active={isEditing} onClick={onStartEdit} />
                <ActionCard icon={<FileUpIcon sx={{ fontSize: 14, color: '#f59e0b' }} />} label="Изменить источник"
                  onClick={() => setSourceMode(true)} />
              </Box>
            </Box>

            {/* History */}
            {fieldLogs.length > 0 && (
              <Box sx={{ px: 2, pt: 2, pb: 2.5 }}>
                <DrawerLabel text="ИСТОРИЯ ИЗМЕНЕНИЙ" />
                <Box sx={{ bgcolor: 'white', borderRadius: 4, border: '1px solid rgba(226,232,240,0.7)', boxShadow: '0 1px 2px rgba(0,0,0,0.04)', p: 1.75 }}>
                  {fieldLogs.map((log, i) => (
                    <Box key={log.id} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, position: 'relative', pb: i < fieldLogs.length - 1 ? 1.75 : 0 }}>
                      {i < fieldLogs.length - 1 && <Box sx={{ position: 'absolute', left: 5, top: 16, bottom: 0, width: 1, bgcolor: '#e2e8f0' }} />}
                      <Box sx={{ width: 13, height: 13, borderRadius: '50%', bgcolor: log.action === 'update' ? '#a78bfa' : '#94a3b8', flexShrink: 0, mt: 0.25, outline: '2px solid white' }} />
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
                          <Typography sx={{ fontSize: 11, color: '#334155' }}>{log.action === 'update' ? 'Значение изменено' : log.action}</Typography>
                          {log.created_at && (
                            <Typography sx={{ fontSize: 10, color: '#94a3b8', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              <ClockIcon sx={{ fontSize: 10 }} />{new Date(log.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}
          </>
        )}
      </Box>

      {/* Footer */}
      {!sourceMode && (
        <Box sx={{ bgcolor: 'white', borderTop: '1px solid rgba(226,232,240,0.8)', px: 2.5, py: 1.5, flexShrink: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Button fullWidth variant="contained" size="small"
              startIcon={<CheckIcon sx={{ fontSize: '14px !important' }} />}
              onClick={() => onApplyValue(value)}
              sx={{ flex: 1, bgcolor: '#059669', '&:hover': { bgcolor: '#047857' }, fontSize: 12, fontWeight: 500, borderRadius: '12px', textTransform: 'none', boxShadow: 'none', py: 1 }}>
              {state === 'review' ? 'Подтвердить значение' : 'Применить'}
            </Button>
            {state !== 'empty' && evidence?.raw_value != null && (
              <Button size="small" startIcon={<UndoIcon sx={{ fontSize: '12px !important' }} />}
                onClick={onResetToAi}
                sx={{ color: '#64748b', border: '1px solid rgba(226,232,240,1)', borderRadius: '12px', textTransform: 'none', fontSize: 11, bgcolor: 'white', whiteSpace: 'nowrap' }}>
                Сбросить к AI
              </Button>
            )}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 1, color: '#94a3b8', fontSize: 9 }}>
            <ShieldIcon sx={{ fontSize: 12 }} />
            <Typography sx={{ fontSize: 'inherit', color: 'inherit' }}>Все изменения записываются в журнал аудита</Typography>
          </Box>
        </Box>
      )}
    </>
  );
}

/* ================== Small sub-components ================== */

function StripMetric({ icon, label, value, muted, warn }: { icon: React.ReactNode; label: string; value: string; muted?: boolean; warn?: boolean }) {
  const valColor = warn ? '#d97706' : muted ? '#94a3b8' : '#1e293b';
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, fontSize: 11 }}>
      {icon}
      <Typography sx={{ fontSize: 'inherit', color: '#94a3b8' }}>{label}</Typography>
      <Typography sx={{ fontSize: 'inherit', fontWeight: 500, color: valColor }}>{value}</Typography>
    </Box>
  );
}

function BottomInd({ icon, text, color, bg }: { icon: React.ReactNode; text: string; color: string; bg: string }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, fontSize: 12, color, px: 1.25, py: 0.5, borderRadius: '8px', bgcolor: bg }}>
      {icon}<Typography sx={{ fontSize: 'inherit', color: 'inherit' }}>{text}</Typography>
    </Box>
  );
}

function DrawerLabel({ text }: { text: string }) {
  return <Typography sx={{ fontSize: 10, color: '#94a3b8', fontWeight: 500, letterSpacing: '0.05em', mb: 1 }}>{text}</Typography>;
}

function ActionCard({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active?: boolean; onClick: () => void }) {
  return (
    <Box component="button" onClick={onClick}
      sx={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.75, p: 1.5,
        borderRadius: 4, border: '1px solid', cursor: 'pointer', transition: 'all 0.15s',
        bgcolor: active ? 'rgba(239,246,255,0.6)' : 'white',
        borderColor: active ? 'rgba(191,219,254,0.6)' : 'rgba(226,232,240,0.7)',
        boxShadow: '0 1px 2px rgba(0,0,0,0.04)', '&:hover': { boxShadow: '0 1px 3px rgba(0,0,0,0.08)', borderColor: 'rgba(203,213,225,1)' },
      }}>
      {icon}
      <Typography sx={{ fontSize: 10, fontWeight: 500, color: active ? '#2563eb' : '#475569' }}>{label}</Typography>
    </Box>
  );
}

export default DeclarationFormPage;
