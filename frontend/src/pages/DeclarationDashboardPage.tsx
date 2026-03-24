import { useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Button, IconButton, Tooltip, Paper,
  Chip, CircularProgress, Snackbar, Alert, Collapse,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  AccessTime as ClockIcon,
  CheckCircle as CheckCircleIcon,
  CheckCircleOutline as CheckOutlineIcon,
  Warning as WarningIcon,
  Send as SendIcon,
  PictureAsPdf as PdfIcon,
  Code as XmlIcon,
  VerifiedUser as SignIcon,
  Search as SearchIcon,
  Folder as FolderIcon,
  History as HistoryIcon,
  Checklist as ChecklistIcon,
  ChevronRight as ChevronRightIcon,
  AutoAwesome as AiIcon,
  ErrorOutline as ErrorIcon,
  Info as InfoIcon,
  Edit as EditIcon,
  Refresh as RefreshIcon,
  Description as FileTextIcon,
  Visibility as EyeIcon,
  SwapHoriz as SwapIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import {
  getDeclaration, getPreSendCheck, getDeclarationLogs,
  getDeclarationStatusHistory, signDeclaration, sendDeclaration,
} from '../api/declarations';
import { getItems } from '../api/items';
import { getDocuments } from '../api/documents';
import { Declaration, PreSendCheck, DeclarationItem, Document as DocType } from '../types';
import StatusChip from '../components/StatusChip';
import AppLayout from '../components/AppLayout';
import dayjs from 'dayjs';
import { useState } from 'react';

const DOC_TYPE_LABELS: Record<string, string> = {
  contract: 'Контракт',
  invoice: 'Инвойс',
  packing_list: 'Упаковочный лист',
  transport_doc: 'Транспортный документ',
  transport_invoice: 'Транспортная накладная',
  specification: 'Спецификация',
  tech_description: 'Тех. описание',
  certificate_origin: 'Сертификат происхождения',
  license: 'Лицензия',
  permit: 'Разрешение',
  other: 'Прочее',
};

const REQUIRED_DOC_TYPES = ['contract', 'invoice', 'packing_list', 'transport_doc'];

const DeclarationDashboardPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false, message: '', severity: 'success',
  });
  const [historyOpen, setHistoryOpen] = useState(false);

  const { data: decl, isLoading } = useQuery({
    queryKey: ['declaration', id],
    queryFn: () => getDeclaration(id!),
    enabled: !!id,
  });

  const { data: items } = useQuery({
    queryKey: ['items', id],
    queryFn: () => getItems(id!),
    enabled: !!id,
  });

  const { data: docs } = useQuery({
    queryKey: ['documents', id],
    queryFn: () => getDocuments({ declaration_id: id! }),
    enabled: !!id,
  });

  const { data: preSendResult } = useQuery({
    queryKey: ['pre-send', id],
    queryFn: () => getPreSendCheck(id!),
    enabled: !!id,
  });

  const { data: statusHistory } = useQuery({
    queryKey: ['status-history', id],
    queryFn: () => getDeclarationStatusHistory(id!),
    enabled: !!id,
  });

  const { data: logs } = useQuery({
    queryKey: ['logs', id],
    queryFn: () => getDeclarationLogs(id!),
    enabled: !!id,
  });

  const signMutation = useMutation({
    mutationFn: () => signDeclaration(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['declaration', id] });
      setSnackbar({ open: true, message: 'Декларация подписана', severity: 'success' });
    },
    onError: () => setSnackbar({ open: true, message: 'Ошибка при подписании', severity: 'error' }),
  });

  const sendMutation = useMutation({
    mutationFn: () => sendDeclaration(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['declaration', id] });
      setSnackbar({ open: true, message: 'Декларация отправлена', severity: 'success' });
    },
    onError: () => setSnackbar({ open: true, message: 'Ошибка при отправке', severity: 'error' }),
  });

  const blockingChecks = useMemo(
    () => (preSendResult?.checks || []).filter((c: PreSendCheck) => c.blocking),
    [preSendResult],
  );
  const warningChecks = useMemo(
    () => (preSendResult?.checks || []).filter((c: PreSendCheck) => !c.blocking && c.severity === 'warning'),
    [preSendResult],
  );
  const infoChecks = useMemo(
    () => (preSendResult?.checks || []).filter((c: PreSendCheck) => !c.blocking && c.severity !== 'warning'),
    [preSendResult],
  );

  const aiIssues = useMemo(
    () => (decl?.ai_issues || []).filter(i => !i.resolved),
    [decl],
  );

  const docsList = useMemo(() => docs || [], [docs]);
  const requiredDocCount = useMemo(
    () => REQUIRED_DOC_TYPES.filter(t => docsList.some((d: DocType) => d.doc_type === t)).length,
    [docsList],
  );

  const summaryFields = useMemo(() => {
    if (!decl) return [];
    const itemsArr = items || [];
    return [
      { label: 'Тип процедуры', value: decl.type_code || '—' },
      { label: 'Инвойс', value: decl.invoice_number ? `${decl.invoice_number}${decl.invoice_date ? ` от ${dayjs(decl.invoice_date).format('DD.MM.YY')}` : ''}` : '—' },
      { label: 'Контракт', value: decl.contract_number ? `${decl.contract_number}${decl.contract_date ? ` от ${dayjs(decl.contract_date).format('DD.MM.YY')}` : ''}` : '—' },
      { label: 'Условия поставки', value: decl.incoterms_code || '—' },
      { label: 'Валюта', value: decl.currency_code || '—' },
      { label: 'Сумма', value: decl.total_invoice_value != null ? Number(decl.total_invoice_value).toLocaleString('ru-RU', { minimumFractionDigits: 2 }) : '—' },
      { label: 'Товарных позиций', value: String(itemsArr.length || decl.total_items_count || 0) },
      { label: 'Вес брутто', value: decl.total_gross_weight ? `${Number(decl.total_gross_weight).toLocaleString('ru-RU')} кг` : '—' },
      { label: 'Страна отправления', value: decl.country_dispatch_code || '—' },
      { label: 'Страна назначения', value: decl.country_destination_code || '—' },
      { label: 'Таможня', value: decl.customs_office_code || '—' },
    ];
  }, [decl, items]);

  if (isLoading || !decl) {
    return (
      <AppLayout>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
          <CircularProgress />
        </Box>
      </AppLayout>
    );
  }

  const isReady = decl.status === 'ready_to_send';
  const isSent = decl.status === 'sent';
  const heroColor = isReady || isSent ? '#059669' : decl.status === 'requires_attention' ? '#d97706' : '#2563eb';
  const heroBg = isReady || isSent ? '#ecfdf5' : decl.status === 'requires_attention' ? '#fffbeb' : '#eff6ff';
  const heroBorder = isReady || isSent ? '#a7f3d0' : decl.status === 'requires_attention' ? '#fde68a' : '#bfdbfe';

  return (
    <AppLayout noPadding>
      {/* Sticky top header */}
      <Box
        sx={{
          position: 'sticky',
          top: 56,
          zIndex: 40,
          bgcolor: 'rgba(255,255,255,0.95)',
          backdropFilter: 'blur(8px)',
          borderBottom: '1px solid #e2e8f0',
          px: 3,
          py: 1.25,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          minHeight: 52,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Tooltip title="К списку деклараций">
            <IconButton onClick={() => navigate('/declarations')} size="small" sx={{ bgcolor: '#f1f5f9', '&:hover': { bgcolor: '#e2e8f0' } }}>
              <ArrowBackIcon sx={{ fontSize: 18, color: '#64748b' }} />
            </IconButton>
          </Tooltip>
          <Box sx={{ width: 1, height: 20, bgcolor: '#e2e8f0' }} />
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography sx={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>
                {decl.number_internal || decl.id.slice(0, 8).toUpperCase()}
              </Typography>
              <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>·</Typography>
              <Typography sx={{ fontSize: 12, color: '#64748b' }}>
                {decl.type_code || 'IM40'}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <ClockIcon sx={{ fontSize: 12, color: '#94a3b8' }} />
              <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>
                Обновлено {dayjs(decl.updated_at || decl.created_at).format('DD.MM.YYYY HH:mm')}
              </Typography>
            </Box>
          </Box>
        </Box>

        <StatusChip status={decl.status} size="medium" />

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Button size="small" startIcon={<PdfIcon sx={{ fontSize: 14 }} />} sx={{ color: '#64748b', borderColor: '#e2e8f0', fontSize: 12 }} variant="outlined">
            PDF
          </Button>
          <Button size="small" startIcon={<XmlIcon sx={{ fontSize: 14 }} />} sx={{ color: '#64748b', borderColor: '#e2e8f0', fontSize: 12 }} variant="outlined">
            XML
          </Button>
          <Button size="small" startIcon={<SignIcon sx={{ fontSize: 14 }} />} sx={{ color: '#64748b', borderColor: '#e2e8f0', fontSize: 12 }} variant="outlined"
            onClick={() => signMutation.mutate()} disabled={signMutation.isPending}>
            ЭЦП
          </Button>
          <Button
            size="small"
            variant="contained"
            startIcon={<SendIcon sx={{ fontSize: 14 }} />}
            onClick={() => sendMutation.mutate()}
            disabled={sendMutation.isPending}
            sx={{ bgcolor: '#059669', fontSize: 12, fontWeight: 500, '&:hover': { bgcolor: '#047857' } }}
          >
            Подписать и отправить
          </Button>
        </Box>
      </Box>

      {/* Main content */}
      <Box sx={{ maxWidth: 1200, mx: 'auto', px: 3, py: 3 }}>
        {/* Hero Status */}
        <Paper
          elevation={0}
          sx={{
            position: 'relative',
            overflow: 'hidden',
            borderRadius: '16px',
            border: `1px solid ${heroBorder}60`,
            bgcolor: heroBg,
            p: 3,
            mb: 2.5,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
              <Box sx={{ p: 1.5, borderRadius: '16px', bgcolor: `${heroBorder}40`, border: `1px solid ${heroBorder}60` }}>
                {isReady || isSent ? <CheckCircleIcon sx={{ fontSize: 28, color: heroColor }} /> :
                  decl.status === 'requires_attention' ? <WarningIcon sx={{ fontSize: 28, color: heroColor }} /> :
                  <EditIcon sx={{ fontSize: 28, color: heroColor }} />}
              </Box>
              <Box>
                <Typography sx={{ fontSize: 20, fontWeight: 600, color: '#0f172a', mb: 0.5 }}>
                  {isReady ? 'Декларация готова к отправке' :
                    isSent ? 'Декларация отправлена' :
                    decl.status === 'requires_attention' ? 'Декларация требует внимания' :
                    'Декларация в работе'}
                </Typography>
                <Typography sx={{ fontSize: 13, color: '#64748b', mb: 2 }}>
                  {blockingChecks.length === 0 && warningChecks.length === 0
                    ? 'Все проверки пройдены успешно'
                    : `Обнаружено ${blockingChecks.length} блокирующих и ${warningChecks.length} предупреждений`}
                </Typography>

                <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                  {blockingChecks.length === 0 && (
                    <StatusPill icon={<CheckOutlineIcon sx={{ fontSize: 13 }} />} text="Критических ошибок: 0" variant="success" />
                  )}
                  {preSendResult?.passed && (
                    <StatusPill icon={<CheckOutlineIcon sx={{ fontSize: 13 }} />} text="Pre-send проверка пройдена" variant="success" />
                  )}
                  {warningChecks.length > 0 && (
                    <StatusPill icon={<WarningIcon sx={{ fontSize: 13 }} />} text={`Предупреждений: ${warningChecks.length}`} variant="warning" />
                  )}
                  {aiIssues.length > 0 && (
                    <StatusPill icon={<WarningIcon sx={{ fontSize: 13 }} />} text={`AI-замечаний: ${aiIssues.length}`} variant="warning" />
                  )}
                </Box>
              </Box>
            </Box>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, flexShrink: 0, ml: 3 }}>
              <Button
                variant="contained"
                startIcon={<SendIcon sx={{ fontSize: 16 }} />}
                onClick={() => sendMutation.mutate()}
                disabled={sendMutation.isPending}
                sx={{ bgcolor: '#059669', fontWeight: 500, fontSize: 13, px: 2.5, '&:hover': { bgcolor: '#047857' } }}
              >
                Подписать и отправить
              </Button>
              <Button
                variant="outlined"
                startIcon={<SearchIcon sx={{ fontSize: 16 }} />}
                onClick={() => navigate(`/declarations/${id}/view`)}
                sx={{ borderColor: '#e2e8f0', color: '#64748b', fontSize: 12, bgcolor: 'rgba(255,255,255,0.6)' }}
              >
                Открыть декларацию
              </Button>
              <Button
                variant="outlined"
                startIcon={<FileTextIcon sx={{ fontSize: 16 }} />}
                onClick={() => navigate(`/declarations/${id}/dts-view`)}
                sx={{ borderColor: '#ddd6fe', color: '#7c3aed', fontSize: 12, bgcolor: 'rgba(245,243,255,0.4)' }}
              >
                ДТС
              </Button>
            </Box>
          </Box>

          {decl.ai_confidence != null && (
            <Box sx={{ mt: 2, pt: 1.5, borderTop: `1px solid ${heroBorder}40`, display: 'flex', alignItems: 'center', gap: 1 }}>
              <AiIcon sx={{ fontSize: 14, color: '#8b5cf6' }} />
              <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>
                AI уверенность: {Math.round(decl.ai_confidence * 100)}%
                {decl.evidence_map && ` · ${Object.keys(decl.evidence_map).length} полей с источниками`}
              </Typography>
            </Box>
          )}
        </Paper>

        {/* Grid: Issues + Summary */}
        <Box sx={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: 2.5, mb: 2.5 }}>
          {/* Issues Panel */}
          <Box>
            <Typography sx={{ fontSize: 14, fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
              Что требует внимания
              {(blockingChecks.length + warningChecks.length + aiIssues.length) > 0 && (
                <Chip
                  label={blockingChecks.length + warningChecks.length + aiIssues.length}
                  size="small"
                  sx={{ height: 20, fontSize: 10, bgcolor: '#fffbeb', color: '#d97706', border: '1px solid #fde68a' }}
                />
              )}
            </Typography>

            {/* Blocking */}
            <Box sx={{ mb: 2 }}>
              <SectionLabel color="#10b981" label="Блокирующие" />
              {blockingChecks.length === 0 ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, p: 1.5, borderRadius: '12px', bgcolor: '#ecfdf5', border: '1px solid #a7f3d080', fontSize: 12, color: '#059669' }}>
                  <CheckCircleIcon sx={{ fontSize: 16 }} />
                  Критических проблем не обнаружено
                </Box>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {blockingChecks.map((c: PreSendCheck, i: number) => (
                    <IssueCard key={i} variant="error" title={c.message} field={c.field} />
                  ))}
                </Box>
              )}
            </Box>

            {/* Warnings */}
            {(warningChecks.length > 0 || aiIssues.length > 0) && (
              <Box sx={{ mb: 2 }}>
                <SectionLabel color="#f59e0b" label="Рекомендуется проверить" count={warningChecks.length + aiIssues.length} />
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {warningChecks.map((c: PreSendCheck, i: number) => (
                    <IssueCard key={`w-${i}`} variant="warning" title={c.message} field={c.field} />
                  ))}
                  {aiIssues.map((issue, i) => (
                    <IssueCard key={`ai-${i}`} variant="warning" title={issue.message} field={issue.field} />
                  ))}
                </Box>
              </Box>
            )}

            {/* Info */}
            {infoChecks.length > 0 && (
              <Box>
                <SectionLabel color="#94a3b8" label="Информация" />
                <Box>
                  {infoChecks.map((c: PreSendCheck, i: number) => (
                    <InfoRow key={i} text={c.message} />
                  ))}
                </Box>
              </Box>
            )}
          </Box>

          {/* Declaration Summary */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography sx={{ fontSize: 14, fontWeight: 600 }}>Краткая сводка</Typography>
              <Button
                size="small"
                startIcon={<SearchIcon sx={{ fontSize: 14 }} />}
                onClick={() => navigate(`/declarations/${id}/view`)}
                sx={{ fontSize: 11, color: '#94a3b8' }}
              >
                Открыть
              </Button>
            </Box>
            <Paper elevation={0} sx={{ borderRadius: '16px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
              {summaryFields.map((f, i) => (
                <Box
                  key={i}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    px: 2,
                    py: 1.25,
                    borderBottom: i < summaryFields.length - 1 ? '1px solid #f1f5f9' : 'none',
                    '&:hover': { bgcolor: '#fafbfc' },
                    transition: 'background-color 0.15s',
                  }}
                >
                  <Typography sx={{ fontSize: 12, color: '#94a3b8' }}>{f.label}</Typography>
                  <Typography sx={{ fontSize: 12, fontWeight: 500, color: '#1e293b' }}>{f.value}</Typography>
                </Box>
              ))}
            </Paper>
          </Box>
        </Box>

        {/* Documents Summary */}
        <Paper elevation={0} sx={{ borderRadius: '16px', border: '1px solid #e2e8f0', p: 2.5, mb: 2.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography sx={{ fontSize: 14, fontWeight: 600 }}>Документы</Typography>
            <Button
              size="small"
              startIcon={<FolderIcon sx={{ fontSize: 14 }} />}
              onClick={() => navigate(`/declarations/${id}/edit`)}
              sx={{ fontSize: 11, color: '#94a3b8' }}
            >
              Управление документами
            </Button>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 3, mb: 2 }}>
            <MetricPill label="Загружено" value={String(docsList.length)} />
            <MetricPill label="Обязательные" value={`${requiredDocCount}/${REQUIRED_DOC_TYPES.length}`} success />
            <MetricPill label="AI-замечания" value={String(aiIssues.filter(i => i.source === 'document').length)} />
          </Box>

          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {docsList.map((d: DocType) => (
              <DocChip key={d.id} name={DOC_TYPE_LABELS[d.doc_type] || d.doc_type} status="ok" />
            ))}
            {REQUIRED_DOC_TYPES.filter(t => !docsList.some((d: DocType) => d.doc_type === t)).map(t => (
              <DocChip key={t} name={DOC_TYPE_LABELS[t] || t} status="missing" />
            ))}
          </Box>
        </Paper>

        {/* Secondary Nav */}
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1.5, mb: 2.5 }}>
          <NavCard
            icon={<SearchIcon sx={{ fontSize: 18 }} />}
            label="Открыть полную декларацию"
            desc={`${Object.keys(decl.evidence_map || {}).length} полей`}
            onClick={() => navigate(`/declarations/${id}/view`)}
          />
          <NavCard
            icon={<FolderIcon sx={{ fontSize: 18 }} />}
            label="Документы"
            desc={`${docsList.length} документов`}
            onClick={() => navigate(`/declarations/${id}/edit`)}
          />
          <NavCard
            icon={<HistoryIcon sx={{ fontSize: 18 }} />}
            label="История изменений"
            desc={`${(logs || []).length} событий`}
            onClick={() => setHistoryOpen(!historyOpen)}
          />
          <NavCard
            icon={<ChecklistIcon sx={{ fontSize: 18 }} />}
            label="Редактирование"
            desc="Форма декларации"
            onClick={() => navigate(`/declarations/${id}/edit`)}
          />
        </Box>

        {/* Expandable history */}
        <Collapse in={historyOpen}>
          <Paper elevation={0} sx={{ borderRadius: '16px', border: '1px solid #e2e8f0', p: 2.5, mb: 2.5 }}>
            <Typography sx={{ fontSize: 14, fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
              <HistoryIcon sx={{ fontSize: 16 }} />
              История и статусы
            </Typography>

            {statusHistory && statusHistory.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography sx={{ fontSize: 11, fontWeight: 500, color: '#94a3b8', mb: 1 }}>Статусы</Typography>
                {statusHistory.map((entry, i) => (
                  <Box key={entry.id} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 0.75, pl: 1, borderLeft: '2px solid #e2e8f0' }}>
                    <StatusChip status={entry.status_code} />
                    <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>
                      {entry.created_at ? dayjs(entry.created_at).format('DD.MM.YYYY HH:mm') : ''}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}

            {logs && logs.length > 0 && (
              <Box>
                <Typography sx={{ fontSize: 11, fontWeight: 500, color: '#94a3b8', mb: 1 }}>Логи действий</Typography>
                {logs.slice(0, 10).map((log) => (
                  <Box key={log.id} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 0.5, fontSize: 12, color: '#64748b' }}>
                    <Typography sx={{ fontSize: 11, color: '#94a3b8', minWidth: 110 }}>
                      {log.created_at ? dayjs(log.created_at).format('DD.MM HH:mm') : ''}
                    </Typography>
                    <Typography sx={{ fontSize: 12 }}>{log.action}</Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Paper>
        </Collapse>
      </Box>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setSnackbar(prev => ({ ...prev, open: false }))} severity={snackbar.severity} variant="filled" sx={{ borderRadius: '10px' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </AppLayout>
  );
};

function StatusPill({ icon, text, variant }: { icon: React.ReactNode; text: string; variant: 'success' | 'warning' }) {
  const colors = variant === 'success'
    ? { bg: '#ecfdf5', border: '#a7f3d060', color: '#059669' }
    : { bg: '#fffbeb', border: '#fde68a', color: '#b45309' };
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.75,
      px: 1.25, py: 0.5, borderRadius: '20px',
      border: `1px solid ${colors.border}`, bgcolor: colors.bg,
      fontSize: 11, color: colors.color,
    }}>
      {icon}{text}
    </Box>
  );
}

function SectionLabel({ color, label, count }: { color: string; label: string; count?: number }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
      <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: color }} />
      <Typography sx={{ fontSize: 11, fontWeight: 500, color: '#64748b' }}>{label}</Typography>
      {count != null && count > 0 && (
        <Chip label={count} size="small" sx={{ height: 18, fontSize: 10, bgcolor: '#fffbeb', color: '#d97706', border: '1px solid #fde68a' }} />
      )}
    </Box>
  );
}

function IssueCard({ variant, title, field }: { variant: 'error' | 'warning'; title: string; field?: string }) {
  const borderColor = variant === 'error' ? '#fecaca' : '#fde68a70';
  const accentColor = variant === 'error' ? '#ef4444' : '#f59e0b';
  const iconBg = variant === 'error' ? '#fef2f2' : '#fffbeb';
  const iconColor = variant === 'error' ? '#ef4444' : '#f59e0b';

  return (
    <Paper
      elevation={0}
      sx={{
        position: 'relative', borderRadius: '12px', border: `1px solid ${borderColor}`,
        overflow: 'hidden',
      }}
    >
      <Box sx={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, bgcolor: accentColor, borderRadius: '12px 0 0 12px' }} />
      <Box sx={{ pl: 2, pr: 1.5, py: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.25 }}>
          <Box sx={{ p: 0.75, borderRadius: '8px', bgcolor: iconBg, flexShrink: 0, mt: 0.25 }}>
            {variant === 'error' ? <ErrorIcon sx={{ fontSize: 14, color: iconColor }} /> : <WarningIcon sx={{ fontSize: 14, color: iconColor }} />}
          </Box>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography sx={{ fontSize: 12, fontWeight: 500, color: '#1e293b', mb: 0.25 }}>{title}</Typography>
            {field && <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>Поле: {field}</Typography>}
          </Box>
        </Box>
      </Box>
    </Paper>
  );
}

function InfoRow({ text }: { text: string }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 1, borderRadius: '8px', '&:hover': { bgcolor: '#f8fafc' }, transition: 'background-color 0.15s', cursor: 'default' }}>
      <InfoIcon sx={{ fontSize: 14, color: '#94a3b8' }} />
      <Typography sx={{ fontSize: 12, color: '#64748b' }}>{text}</Typography>
    </Box>
  );
}

function MetricPill({ label, value, success }: { label: string; value: string; success?: boolean }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>{label}:</Typography>
      <Typography sx={{ fontSize: 12, fontWeight: 500, color: success ? '#059669' : '#1e293b' }}>{value}</Typography>
    </Box>
  );
}

function DocChip({ name, status }: { name: string; status: 'ok' | 'warning' | 'missing' }) {
  const cfg = {
    ok: { bg: '#ecfdf5', border: '#a7f3d060', color: '#059669', icon: <CheckCircleIcon sx={{ fontSize: 14 }} /> },
    warning: { bg: '#fffbeb', border: '#fde68a', color: '#b45309', icon: <WarningIcon sx={{ fontSize: 14 }} /> },
    missing: { bg: '#fef2f2', border: '#fecaca', color: '#dc2626', icon: <ErrorIcon sx={{ fontSize: 14 }} /> },
  }[status];

  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.75,
      px: 1.25, py: 0.75, borderRadius: '8px',
      border: `1px solid ${cfg.border}`, bgcolor: cfg.bg,
      fontSize: 11, color: cfg.color,
    }}>
      {cfg.icon}{name}
    </Box>
  );
}

function NavCard({ icon, label, desc, onClick }: { icon: React.ReactNode; label: string; desc: string; onClick: () => void }) {
  return (
    <Paper
      elevation={0}
      onClick={onClick}
      sx={{
        display: 'flex', alignItems: 'center', gap: 1.5,
        p: 1.75, borderRadius: '12px', border: '1px solid #e2e8f0',
        cursor: 'pointer', transition: 'all 0.2s',
        '&:hover': { bgcolor: '#f8fafc', borderColor: '#cbd5e1' },
      }}
    >
      <Box sx={{ p: 1, borderRadius: '8px', bgcolor: '#f8fafc', color: '#94a3b8' }}>
        {icon}
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{ fontSize: 12, fontWeight: 500, color: '#334155' }}>{label}</Typography>
        <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>{desc}</Typography>
      </Box>
      <ChevronRightIcon sx={{ fontSize: 16, color: '#cbd5e1' }} />
    </Paper>
  );
}

export default DeclarationDashboardPage;
