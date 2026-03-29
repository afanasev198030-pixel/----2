import { useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Button, Paper, Chip, Divider, Snackbar,
  CircularProgress,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  WarningAmber as WarningAmberIcon,
  ErrorOutline as ErrorOutlineIcon,
  Send as SendIcon,
  FindInPage as FindInPageIcon,
  Assignment as AssignmentIcon,
  Description as DescriptionIcon,
  Code as CodeIcon,
  VerifiedUser as VerifiedUserIcon,
  AutoAwesome as AutoAwesomeIcon,
  FolderOpen as FolderOpenIcon,
  History as HistoryIcon,
  FactCheck as FactCheckIcon,
  ChevronRight as ChevronRightIcon,
  Visibility as VisibilityIcon,
  Edit as EditIcon,
  EditNote as EditNoteIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import StatusChip from '../components/StatusChip';
import DocumentViewer from '../components/DocumentViewer';
import HSCodeSuggestions from '../components/HSCodeSuggestions';
import { getDeclaration, getPreSendCheck, getDeclarationLogs, patchEvidenceMap } from '../api/declarations';
import { getItems, updateItem } from '../api/items';
import { getDocuments } from '../api/documents';
import client from '../api/client';
import {
  Declaration, DeclarationItem, Document as DocType,
  PreSendResult, PreSendCheck, AiIssue, DeclarationLogEntry,
  FieldEvidence, DocumentType,
} from '../types';

const REQUIRED_DOC_TYPES: DocumentType[] = ['contract', 'invoice', 'transport_doc', 'packing_list'];
const DOC_TYPE_LABELS: Record<string, string> = {
  contract: 'Контракт',
  invoice: 'Инвойс',
  packing_list: 'Упаковочный лист',
  transport_doc: 'Транспортный документ',
  transport_invoice: 'Транспортный инвойс',
  specification: 'Спецификация',
  certificate_origin: 'Сертификат происхождения',
  license: 'Лицензия',
  permit: 'Разрешение',
  other: 'Другое',
};

const DeclarationStatusPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [snackMsg, setSnackMsg] = useState('');
  const [docViewerOpen, setDocViewerOpen] = useState(false);

  const { data: decl, isLoading: declLoading } = useQuery({
    queryKey: ['declaration', id],
    queryFn: () => getDeclaration(id!),
    enabled: !!id,
  });

  const { data: preSend } = useQuery<PreSendResult>({
    queryKey: ['pre-send-check', id],
    queryFn: () => getPreSendCheck(id!),
    enabled: !!id,
  });

  const { data: itemsData } = useQuery({
    queryKey: ['declaration-items', id],
    queryFn: () => getItems(id!),
    enabled: !!id,
  });

  const { data: docsData } = useQuery({
    queryKey: ['declaration-docs', id],
    queryFn: () => getDocuments({ declaration_id: id! }),
    enabled: !!id,
  });

  const { data: logs = [] } = useQuery<DeclarationLogEntry[]>({
    queryKey: ['declaration-logs', id],
    queryFn: () => getDeclarationLogs(id!),
    enabled: !!id,
  });

  const items: DeclarationItem[] = useMemo(() => {
    if (Array.isArray(itemsData)) return itemsData;
    return (itemsData as any)?.items || [];
  }, [itemsData]);

  const docs: DocType[] = useMemo(() => {
    if (!docsData) return [];
    return Array.isArray(docsData) ? docsData : [];
  }, [docsData]);

  const blockingChecks = useMemo(() => preSend?.checks.filter((c: PreSendCheck) => c.blocking) || [], [preSend]);
  const warningChecks = useMemo(() => preSend?.checks.filter((c: PreSendCheck) => !c.blocking) || [], [preSend]);

  const aiIssues: AiIssue[] = decl?.ai_issues || [];
  const unresolvedAiIssues = aiIssues.filter(i => !i.resolved);

  const handleHsSelect = useCallback(async (itemId: string, code: string, _name: string) => {
    if (!id) return;
    try {
      await updateItem(id, itemId, { hs_code: code });
      queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
      setSnackMsg(`Код ${code} применён`);
    } catch { setSnackMsg('Ошибка при сохранении кода'); }
  }, [id, queryClient]);

  const handleExportPdf = async () => {
    try {
      const r = await client.get(`/declarations/${id}/export-pdf`, { responseType: 'blob' });
      const u = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
      const a = document.createElement('a'); a.href = u; a.download = `DT_${(id || '').slice(0, 8)}.pdf`; a.click();
      setSnackMsg('PDF скачан');
    } catch { setSnackMsg('Ошибка PDF'); }
  };

  const handleExportXml = async () => {
    try {
      const r = await client.get(`/integration/export-xml/${id}`, { responseType: 'blob', baseURL: '/api/v1' });
      const u = window.URL.createObjectURL(new Blob([r.data], { type: 'application/xml' }));
      const a = document.createElement('a'); a.href = u; a.download = `DT_${(id || '').slice(0, 8)}.xml`; a.click();
      setSnackMsg('XML скачан');
    } catch { setSnackMsg('Ошибка XML'); }
  };

  const handleEvidenceChange = async (field: string, patch: Partial<FieldEvidence>) => {
    if (!id) return;
    await patchEvidenceMap(id, { [field]: patch });
  };

  if (declLoading || !decl) {
    return (
      <AppLayout breadcrumbs={[{ label: 'Декларации', path: '/declarations' }, { label: 'Статус' }]}>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>
      </AppLayout>
    );
  }

  const isReady = preSend?.passed ?? false;
  const hasBlocking = blockingChecks.length > 0;

  const requiredDocTypes = REQUIRED_DOC_TYPES;
  const uploadedDocTypes = new Set(docs.map(d => d.doc_type));
  const requiredPresent = requiredDocTypes.filter(t => uploadedDocTypes.has(t)).length;
  const optionalDocs = docs.filter(d => !(requiredDocTypes as readonly string[]).includes(d.doc_type));

  const heroColor = isReady ? '#059669' : hasBlocking ? '#dc2626' : '#d97706';
  const heroBg = isReady ? 'rgba(236,253,245,0.8)' : hasBlocking ? 'rgba(254,242,242,0.8)' : 'rgba(255,251,235,0.8)';
  const heroBorder = isReady ? 'rgba(167,243,208,0.6)' : hasBlocking ? 'rgba(254,202,202,0.6)' : 'rgba(253,230,138,0.6)';
  const heroIcon = isReady
    ? <CheckCircleIcon sx={{ fontSize: 28, color: '#059669' }} />
    : hasBlocking
    ? <ErrorOutlineIcon sx={{ fontSize: 28, color: '#dc2626' }} />
    : <WarningAmberIcon sx={{ fontSize: 28, color: '#d97706' }} />;
  const heroTitle = isReady ? 'Декларация готова к отправке' : hasBlocking ? 'Есть блокирующие проблемы' : 'Требуется внимание';
  const heroDesc = isReady
    ? `Система завершила проверку. ${warningChecks.length > 0 ? `Обнаружено ${warningChecks.length} рекомендаций для проверки.` : 'Все проверки пройдены.'}`
    : hasBlocking
    ? `Обнаружено ${blockingChecks.length} блокирующих проблем. Устраните их перед отправкой.`
    : `Обнаружено ${warningChecks.length} предупреждений. Рекомендуется проверить.`;

  const statusChips: { text: string; ok: boolean }[] = [
    { text: `Обязательные поля`, ok: !blockingChecks.some(c => c.code === 'MISSING_REQUIRED_FIELD' || c.code === 'MISSING_SENDER' || c.code === 'MISSING_RECEIVER') },
    { text: `Документы: ${requiredPresent}/${requiredDocTypes.length}`, ok: requiredPresent >= requiredDocTypes.length },
    { text: `Критических ошибок: ${blockingChecks.length}`, ok: blockingChecks.length === 0 },
    { text: `Предупреждений: ${warningChecks.length + unresolvedAiIssues.length}`, ok: warningChecks.length === 0 && unresolvedAiIssues.length === 0 },
  ];

  const summaryFields = [
    { label: 'Тип процедуры', value: decl.type_code || '—' },
    { label: 'Инвойс', value: decl.invoice_number || '—' },
    { label: 'Контракт', value: decl.contract_number || '—' },
    { label: 'Условия поставки', value: decl.incoterms_code || '—' },
    { label: 'Валюта', value: decl.currency_code || '—' },
    { label: 'Сумма', value: decl.total_invoice_value ? Number(decl.total_invoice_value).toLocaleString('ru-RU', { minimumFractionDigits: 2 }) : '—' },
    { label: 'Товарных позиций', value: String(decl.total_items_count || items.length || 0) },
    { label: 'Вес брутто', value: decl.total_gross_weight ? `${Number(decl.total_gross_weight).toLocaleString('ru-RU')} кг` : '—' },
    { label: 'Страна отправления', value: decl.country_dispatch_code || '—' },
    { label: 'Страна назначения', value: decl.country_destination_code || '—' },
    { label: 'Таможенный пост', value: decl.customs_office_code || '—' },
  ];

  return (
    <AppLayout breadcrumbs={[{ label: 'Декларации', path: '/declarations' }, { label: 'Статус декларации' }]}>
      {/* Toolbar */}
      <Box sx={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        mb: 2.5, flexWrap: 'wrap', gap: 1,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Typography sx={{ fontSize: 15, fontWeight: 600 }}>
            {decl.number_internal || decl.id.slice(0, 13)}
          </Typography>
          <Typography sx={{ color: '#94a3b8' }}>·</Typography>
          <Typography sx={{ fontSize: 13, color: '#64748b' }}>{decl.type_code || 'IM40'}</Typography>
          <StatusChip status={decl.status} />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Button variant="outlined" size="small"
            startIcon={<DescriptionIcon sx={{ fontSize: '14px !important' }} />}
            onClick={handleExportPdf}
            sx={{ color: '#64748b', borderColor: 'rgba(226,232,240,1)', fontSize: 12, borderRadius: '10px' }}>
            PDF
          </Button>
          <Button variant="outlined" size="small"
            startIcon={<CodeIcon sx={{ fontSize: '14px !important' }} />}
            onClick={handleExportXml}
            sx={{ color: '#64748b', borderColor: 'rgba(226,232,240,1)', fontSize: 12, borderRadius: '10px' }}>
            XML
          </Button>
          <Button variant="outlined" size="small"
            startIcon={<VerifiedUserIcon sx={{ fontSize: '14px !important' }} />}
            onClick={() => setSnackMsg('ЭЦП: будет в следующей версии')}
            sx={{ color: '#64748b', borderColor: 'rgba(226,232,240,1)', fontSize: 12, borderRadius: '10px' }}>
            Подписать ЭЦП
          </Button>
          <Button variant="contained" size="small"
            startIcon={<SendIcon sx={{ fontSize: '14px !important' }} />}
            onClick={() => setSnackMsg('ФТС: будет в следующей версии')}
            sx={{ bgcolor: '#059669', '&:hover': { bgcolor: '#047857' }, fontSize: 12, fontWeight: 500, borderRadius: '10px', boxShadow: 'none' }}>
            Подписать и отправить
          </Button>
        </Box>
      </Box>

      {/* Hero Status */}
      <Paper sx={{
        position: 'relative', overflow: 'hidden', borderRadius: 4,
        border: '1px solid', borderColor: heroBorder,
        background: `linear-gradient(135deg, ${heroBg}, white, ${heroBg.replace('0.8', '0.4')})`,
        p: 3, mb: 2.5,
      }}>
        <Box sx={{
          position: 'absolute', top: 0, right: 0, width: 256, height: 256,
          bgcolor: heroBorder.replace('0.6', '0.15'), borderRadius: '50%',
          transform: 'translate(33%, -50%)', filter: 'blur(48px)',
        }} />

        <Box sx={{ position: 'relative', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, flex: 1 }}>
            <Box sx={{
              p: 1.5, borderRadius: 4, bgcolor: heroBorder.replace('0.6', '0.5'),
              border: `1px solid ${heroBorder}`, display: 'flex', flexShrink: 0,
            }}>
              {heroIcon}
            </Box>
            <Box>
              <Typography sx={{ fontSize: 20, fontWeight: 600, color: '#0f172a', mb: 0.5 }}>{heroTitle}</Typography>
              <Typography sx={{ fontSize: 13, color: '#64748b', mb: 2 }}>{heroDesc}</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                {statusChips.map((chip) => (
                  <Chip key={chip.text}
                    icon={chip.ok
                      ? <CheckCircleIcon sx={{ fontSize: '13px !important' }} />
                      : <WarningAmberIcon sx={{ fontSize: '13px !important' }} />}
                    label={chip.text} size="small"
                    sx={{
                      bgcolor: chip.ok ? 'rgba(236,253,245,1)' : 'rgba(255,251,235,1)',
                      color: chip.ok ? '#047857' : '#b45309',
                      border: `1px solid ${chip.ok ? 'rgba(167,243,208,0.6)' : 'rgba(253,230,138,0.6)'}`,
                      fontSize: 11, fontWeight: 400,
                      '& .MuiChip-icon': { color: chip.ok ? '#047857' : '#b45309' },
                    }}
                  />
                ))}
              </Box>
            </Box>
          </Box>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, ml: 3, flexShrink: 0 }}>
            <Button variant="contained" startIcon={<SendIcon sx={{ fontSize: '16px !important' }} />}
              onClick={() => setSnackMsg('ФТС: будет в следующей версии')}
              sx={{ bgcolor: '#059669', '&:hover': { bgcolor: '#047857' }, fontSize: 13, fontWeight: 500, px: 2.5, py: 1, boxShadow: '0 1px 3px rgba(5,150,105,0.2)', borderRadius: '10px' }}>
              Подписать и отправить
            </Button>
            <Button variant="outlined" size="small"
              startIcon={<FindInPageIcon sx={{ fontSize: '14px !important' }} />}
              onClick={() => navigate(`/declarations/${id}/form`)}
              sx={{ color: '#475569', borderColor: 'rgba(226,232,240,1)', bgcolor: 'rgba(255,255,255,0.6)', '&:hover': { bgcolor: 'rgba(255,255,255,0.8)' }, fontSize: 12, borderRadius: '10px' }}>
              Редактировать декларацию
            </Button>
            <Button variant="outlined" size="small"
              startIcon={<AssignmentIcon sx={{ fontSize: '14px !important' }} />}
              onClick={() => navigate(`/declarations/${id}/dts-view`)}
              sx={{ color: '#6d28d9', borderColor: 'rgba(221,214,254,0.6)', bgcolor: 'rgba(245,243,255,0.4)', '&:hover': { bgcolor: 'rgba(245,243,255,0.8)' }, fontSize: 12, borderRadius: '10px' }}>
              Открыть ДТС
            </Button>
          </Box>
        </Box>

        {decl.ai_confidence != null && (
          <Box sx={{ mt: 2, pt: 1.5, borderTop: `1px solid ${heroBorder.replace('0.6', '0.4')}`, display: 'flex', alignItems: 'center', gap: 1, color: '#94a3b8', fontSize: 11 }}>
            <AutoAwesomeIcon sx={{ fontSize: 13, color: '#8b5cf6' }} />
            <Typography sx={{ fontSize: 11, color: 'inherit' }}>
              AI уверенность: {Math.round((decl.ai_confidence || 0) * 100)}%
              {decl.processing_status === 'auto_filled' && ' · Автозаполнение завершено'}
            </Typography>
          </Box>
        )}
      </Paper>

      {/* Grid: Issues + Summary */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '3fr 2fr' }, gap: 2.5, mb: 2.5 }}>
        {/* Issues Panel */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="h6">Что требует внимания</Typography>
            {(blockingChecks.length + warningChecks.length + unresolvedAiIssues.length) > 0 && (
              <Chip label={blockingChecks.length + warningChecks.length + unresolvedAiIssues.length} size="small"
                sx={{ bgcolor: 'rgba(255,251,235,1)', color: '#d97706', border: '1px solid rgba(253,230,138,0.6)', fontSize: 11, height: 20 }} />
            )}
          </Box>

          {/* Blocking */}
          <IssueSection dot="#dc2626" title="Блокирующие" count={blockingChecks.length > 0 ? blockingChecks.length : undefined}>
            {blockingChecks.length === 0 ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, p: 1.5, borderRadius: 3, bgcolor: 'rgba(236,253,245,0.5)', border: '1px solid rgba(167,243,208,0.5)', color: '#047857', fontSize: 12 }}>
                <CheckCircleIcon sx={{ fontSize: 16 }} />
                <Typography sx={{ fontSize: 12, color: 'inherit' }}>Критических проблем не обнаружено</Typography>
              </Box>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {blockingChecks.map((check, i) => (
                  <IssueCard key={`b-${i}`} title={check.message} description={check.field ? `Поле: ${check.field}` : check.code}
                    accentColor="#dc2626"
                    actions={[
                      { label: 'Исправить', onClick: () => navigate(`/declarations/${id}/form`), primary: true },
                    ]}
                  />
                ))}
              </Box>
            )}
          </IssueSection>

          {/* Warnings */}
          <IssueSection dot="#f59e0b" title="Рекомендуется проверить" count={(warningChecks.length + unresolvedAiIssues.length) || undefined}>
            {warningChecks.length === 0 && unresolvedAiIssues.length === 0 ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, p: 1.5, borderRadius: 3, bgcolor: 'rgba(236,253,245,0.5)', border: '1px solid rgba(167,243,208,0.5)', color: '#047857', fontSize: 12 }}>
                <CheckCircleIcon sx={{ fontSize: 16 }} />
                <Typography sx={{ fontSize: 12, color: 'inherit' }}>Предупреждений нет</Typography>
              </Box>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {warningChecks.map((check, i) => (
                  <IssueCard key={`w-${i}`} title={check.message} description={check.field ? `Поле: ${check.field}` : check.code}
                    accentColor="#fbbf24"
                    actions={[
                      { label: 'Проверить', onClick: () => navigate(`/declarations/${id}/form`) },
                    ]}
                  />
                ))}
                {unresolvedAiIssues.map((issue, i) => (
                  <IssueCard key={`ai-${i}`}
                    title={issue.message}
                    description={`${issue.severity === 'error' ? 'Ошибка' : 'Предупреждение'}${issue.field ? ` · Поле: ${issue.field}` : ''}`}
                    accentColor="#fbbf24"
                    actions={[
                      { label: 'Подробнее', onClick: () => navigate(`/declarations/${id}/form`) },
                    ]}
                  />
                ))}
              </Box>
            )}
          </IssueSection>

          {/* Info */}
          <IssueSection dot="#94a3b8" title="Информация">
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
              <InfoRow icon={<EditNoteIcon sx={{ fontSize: 14 }} />}
                text={`Товарных позиций: ${items.length}`} />
              <InfoRow icon={<RefreshIcon sx={{ fontSize: 14 }} />}
                text={`Документов загружено: ${docs.length}`} />
              <InfoRow icon={<DescriptionIcon sx={{ fontSize: 14 }} />}
                text={`Событий в журнале: ${logs.length}`} />
              {decl.processing_status && (
                <InfoRow icon={<AutoAwesomeIcon sx={{ fontSize: 14 }} />}
                  text={`Статус обработки: ${decl.processing_status === 'auto_filled' ? 'Автозаполнено' : decl.processing_status === 'processing' ? 'В обработке' : decl.processing_status === 'processing_error' ? 'Ошибка обработки' : 'Не обработано'}`} />
              )}
            </Box>
          </IssueSection>
        </Box>

        {/* Declaration Summary */}
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6">Краткая сводка</Typography>
            <Button size="small"
              startIcon={<FindInPageIcon sx={{ fontSize: '13px !important' }} />}
              onClick={() => navigate(`/declarations/${id}/form`)}
              sx={{ color: '#94a3b8', fontSize: 11, '&:hover': { color: '#475569' } }}>
              Открыть декларацию
            </Button>
          </Box>
          <Paper sx={{ overflow: 'hidden', borderRadius: '14px', border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
            {summaryFields.map((f, i) => (
              <Box key={i}>
                <Box sx={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  px: 2, py: 1.25,
                  '&:hover': { bgcolor: 'rgba(248,250,252,0.5)' },
                  transition: 'background 0.15s',
                }}>
                  <Typography sx={{ fontSize: 12, color: '#94a3b8' }}>{f.label}</Typography>
                  <Typography sx={{ fontSize: 12, fontWeight: 500, color: '#1e293b' }}>{f.value}</Typography>
                </Box>
                {i < summaryFields.length - 1 && <Divider sx={{ borderColor: 'rgba(241,245,249,1)' }} />}
              </Box>
            ))}
          </Paper>
        </Box>
      </Box>

      {/* Items & HS Codes */}
      {items.length > 0 && (
        <Paper sx={{ p: 2.5, mb: 2.5, borderRadius: '14px', border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6">Товарные позиции</Typography>
            <Chip label={`${items.length} шт`} size="small" sx={{ bgcolor: '#f1f5f9', fontWeight: 600, fontSize: 11 }} />
          </Box>

          {items.map((item, idx) => (
            <Paper
              key={item.id}
              variant="outlined"
              sx={{
                p: 2, mb: idx < items.length - 1 ? 1.5 : 0,
                borderRadius: '10px', borderColor: 'rgba(226,232,240,0.8)',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1 }}>
                <Box sx={{ flex: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                    <Chip
                      label={`№ ${item.item_no ?? idx + 1}`}
                      size="small"
                      sx={{ bgcolor: '#e2e8f0', fontWeight: 700, fontSize: 11, height: 22 }}
                    />
                    {item.hs_code ? (
                      <Chip
                        label={item.hs_code}
                        size="small"
                        sx={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 12, bgcolor: '#e0f2fe', color: '#0369a1', height: 22 }}
                      />
                    ) : (
                      <Chip
                        label="Код не указан"
                        size="small"
                        color="warning"
                        variant="outlined"
                        sx={{ fontSize: 11, height: 22 }}
                      />
                    )}
                  </Box>
                  <Typography sx={{ fontSize: 13, color: '#334155', mt: 0.5 }}>
                    {item.description || '—'}
                  </Typography>
                </Box>

                <Box sx={{ textAlign: 'right', minWidth: 100 }}>
                  {item.country_origin_code && (
                    <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>
                      Страна: {item.country_origin_code}
                    </Typography>
                  )}
                  {item.unit_price != null && (
                    <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>
                      Цена: {item.unit_price}
                    </Typography>
                  )}
                </Box>
              </Box>

              <HSCodeSuggestions
                description={item.description || ''}
                currentCode={item.hs_code || ''}
                onSelect={(code, name) => handleHsSelect(item.id, code, name)}
                countryOrigin={item.country_origin_code}
                unitPrice={item.unit_price ?? undefined}
                declarationId={id}
              />
            </Paper>
          ))}
        </Paper>
      )}

      {/* Documents Summary */}
      <Paper sx={{ p: 2.5, mb: 2.5, borderRadius: '14px', border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6">Документы</Typography>
          <Button size="small"
            startIcon={<FolderOpenIcon sx={{ fontSize: '13px !important' }} />}
            onClick={() => setDocViewerOpen(true)}
            sx={{ color: '#94a3b8', fontSize: 11, '&:hover': { color: '#475569' } }}>
            Открыть документы
          </Button>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5, mb: 2 }}>
          <MetricInline label="Загружено" value={String(docs.length)} />
          <MetricInline label="Обязательные" value={`${requiredPresent}/${requiredDocTypes.length}`} success={requiredPresent >= requiredDocTypes.length} />
          <MetricInline label="Дополнительные" value={String(optionalDocs.length)} />
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {requiredDocTypes.map((dt) => {
            const present = uploadedDocTypes.has(dt);
            return (
              <Chip key={dt}
                icon={present
                  ? <CheckCircleIcon sx={{ fontSize: 14 }} />
                  : <WarningAmberIcon sx={{ fontSize: 14 }} />}
                label={DOC_TYPE_LABELS[dt] || dt}
                size="small"
                sx={{
                  bgcolor: present ? 'rgba(236,253,245,1)' : 'rgba(254,242,242,1)',
                  color: present ? '#059669' : '#dc2626',
                  border: `1px solid ${present ? 'rgba(167,243,208,0.6)' : 'rgba(254,202,202,0.6)'}`,
                  fontSize: 11, height: 28,
                  '& .MuiChip-icon': { color: present ? '#059669' : '#dc2626' },
                }}
              />
            );
          })}
          {optionalDocs.map((d, i) => (
            <Chip key={`opt-${i}`}
              icon={<DescriptionIcon sx={{ fontSize: 14 }} />}
              label={DOC_TYPE_LABELS[d.doc_type] || d.doc_type}
              size="small"
              sx={{
                bgcolor: 'rgba(248,250,252,1)', color: '#94a3b8',
                border: '1px solid rgba(226,232,240,0.6)', fontSize: 11, height: 28,
                '& .MuiChip-icon': { color: '#94a3b8' },
              }}
            />
          ))}
        </Box>
      </Paper>

      {/* Secondary Nav */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 1.5, mb: 3 }}>
        <NavCard icon={<FindInPageIcon sx={{ fontSize: 18 }} />}
          label="Редактировать декларацию"
          desc={`${items.length} позиций · Форма редактирования`}
          onClick={() => navigate(`/declarations/${id}/form`)} />
        <NavCard icon={<VisibilityIcon sx={{ fontSize: 18 }} />}
          label="Просмотр ДТ"
          desc="Печатная форма декларации"
          onClick={() => navigate(`/declarations/${id}/view`)} />
        <NavCard icon={<FolderOpenIcon sx={{ fontSize: 18 }} />}
          label="Документы"
          desc={`${docs.length} документов загружено`}
          onClick={() => setDocViewerOpen(true)} />
        <NavCard icon={<HistoryIcon sx={{ fontSize: 18 }} />}
          label="История изменений"
          desc={`${logs.length} событий`}
          onClick={() => navigate(`/declarations/${id}/form`)} />
      </Box>

      {/* Document Viewer modal */}
      <DocumentViewer
        documents={docs}
        open={docViewerOpen}
        onClose={() => setDocViewerOpen(false)}
        evidenceMap={decl.evidence_map}
        onEvidenceChange={handleEvidenceChange}
      />

      <Snackbar open={!!snackMsg} autoHideDuration={4000} onClose={() => setSnackMsg('')} message={snackMsg} />
    </AppLayout>
  );
};

/* ---- Sub-components ---- */

function IssueSection({ dot, title, count, children }: { dot: string; title: string; count?: number; children: React.ReactNode }) {
  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: dot }} />
        <Typography sx={{ fontSize: 11, fontWeight: 500, color: '#64748b' }}>{title}</Typography>
        {count !== undefined && (
          <Chip label={count} size="small" sx={{
            height: 18, fontSize: 10,
            bgcolor: dot === '#dc2626' ? 'rgba(254,242,242,1)' : dot === '#f59e0b' ? 'rgba(255,251,235,1)' : 'rgba(248,250,252,1)',
            color: dot === '#dc2626' ? '#dc2626' : dot === '#f59e0b' ? '#d97706' : '#64748b',
            border: '1px solid',
            borderColor: dot === '#dc2626' ? 'rgba(254,202,202,0.6)' : dot === '#f59e0b' ? 'rgba(253,230,138,0.6)' : 'rgba(226,232,240,0.6)',
          }} />
        )}
      </Box>
      {children}
    </Box>
  );
}

function IssueCard({ title, description, accentColor, actions }: {
  title: string; description: string; accentColor: string;
  actions: { label: string; onClick: () => void; primary?: boolean }[];
}) {
  return (
    <Paper sx={{ position: 'relative', overflow: 'hidden', borderRadius: 3, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
      <Box sx={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, bgcolor: accentColor, borderRadius: '3px 0 0 3px' }} />
      <Box sx={{ pl: 2, pr: 1.5, py: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.25 }}>
          <Box sx={{ p: 0.75, borderRadius: 2, bgcolor: 'rgba(255,251,235,1)', display: 'flex', mt: 0.25, flexShrink: 0 }}>
            <WarningAmberIcon sx={{ fontSize: 14, color: '#f59e0b' }} />
          </Box>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography sx={{ fontSize: 12, fontWeight: 500, color: '#1e293b', mb: 0.25 }}>{title}</Typography>
            <Typography sx={{ fontSize: 11, color: '#94a3b8', mb: 1.25 }}>{description}</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
              {actions.map((a, i) => (
                <Button key={i} variant={a.primary ? 'contained' : 'outlined'} size="small"
                  onClick={a.onClick}
                  sx={{
                    fontSize: 11, px: 1.25, py: 0.375, minHeight: 0, borderRadius: '8px',
                    ...(a.primary
                      ? { bgcolor: '#1e293b', '&:hover': { bgcolor: '#0f172a' }, boxShadow: 'none' }
                      : { color: '#475569', borderColor: 'rgba(226,232,240,1)', '&:hover': { bgcolor: 'rgba(248,250,252,1)' } }),
                  }}>
                  {a.label}
                </Button>
              ))}
            </Box>
          </Box>
        </Box>
      </Box>
    </Paper>
  );
}

function InfoRow({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <Box sx={{
      display: 'flex', alignItems: 'center', gap: 1.25,
      px: 1.5, py: 1, borderRadius: 2,
      '&:hover': { bgcolor: 'rgba(248,250,252,1)' },
      color: '#64748b', fontSize: 12, transition: 'background 0.15s',
    }}>
      <Box sx={{ color: '#94a3b8', display: 'flex' }}>{icon}</Box>
      <Typography sx={{ fontSize: 12, color: 'inherit' }}>{text}</Typography>
    </Box>
  );
}

function MetricInline({ label, value, success }: { label: string; value: string; success?: boolean }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>{label}:</Typography>
      <Typography sx={{ fontSize: 12, fontWeight: 500, color: success ? '#059669' : '#334155' }}>{value}</Typography>
    </Box>
  );
}

function NavCard({ icon, label, desc, onClick }: { icon: React.ReactNode; label: string; desc: string; onClick: () => void }) {
  return (
    <Paper component="button" onClick={onClick}
      sx={{
        display: 'flex', alignItems: 'center', gap: 1.5,
        p: 1.75, cursor: 'pointer', textAlign: 'left',
        bgcolor: 'white', borderRadius: '14px',
        border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none',
        transition: 'all 0.15s',
        '&:hover': {
          bgcolor: 'rgba(248,250,252,1)', borderColor: 'rgba(203,213,225,0.8)',
          '& .nav-chevron': { color: '#94a3b8' },
          '& .nav-icon': { color: '#475569' },
        },
      }}>
      <Box className="nav-icon" sx={{ p: 1, borderRadius: 2, bgcolor: 'rgba(248,250,252,1)', color: '#94a3b8', display: 'flex', transition: 'color 0.15s' }}>
        {icon}
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{ fontSize: 12, fontWeight: 500, color: '#334155' }}>{label}</Typography>
        <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>{desc}</Typography>
      </Box>
      <ChevronRightIcon className="nav-chevron" sx={{ fontSize: 16, color: '#cbd5e1', transition: 'color 0.15s' }} />
    </Paper>
  );
}

export default DeclarationStatusPage;
