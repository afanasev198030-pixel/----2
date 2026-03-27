import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import {
  Box, Typography, Button, Container, LinearProgress,
  Stepper, Step, StepLabel, Paper, TextField, Grid,
  Alert, Snackbar, Divider,
  Accordion, AccordionSummary, AccordionDetails,
} from '@mui/material';
import {
  Save, AutoAwesome as AiIcon,
  Visibility as ViewIcon,
  Description as DocsIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import {
  getDeclaration, updateDeclaration, patchEvidenceMap, openDeclaration,
} from '../api/declarations';
import { getItems } from '../api/items';
import { getDocuments } from '../api/documents';
import { calculatePayments, PaymentResult } from '../api/calc';
import client from '../api/client';
import StatusChip from '../components/StatusChip';
import DocumentUploadPanel from '../components/DocumentUploadPanel';
import DocumentViewer from '../components/DocumentViewer';
import ClassifierSelect from '../components/ClassifierSelect';
import RiskPanel from '../components/RiskPanel';
import ItemEditCard from '../components/ItemEditCard';
import DeclarationChecklist from '../components/DeclarationChecklist';
import HistoryPanel from '../components/HistoryPanel';
import CounterpartyLookup from '../components/CounterpartyLookup';
import AiExplainPanel from '../components/AiExplainPanel';
import DeclarationStatusTimeline from '../components/DeclarationStatusTimeline';
import NextActionsPanel from '../components/NextActionsPanel';
import ConfidenceBadge from '../components/ConfidenceBadge';
import DtsPanel from '../components/DtsPanel';
import { Declaration, DeclarationItem, Document as DocType } from '../types';

const STEPS = ['Загрузка документов', 'Проверка данных', 'Готово'];

const DeclarationEditPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeStep, setActiveStep] = useState(0);
  const [snackMsg, setSnackMsg] = useState('');
  const [riskScore, setRiskScore] = useState(0);
  const [riskFlags, setRiskFlags] = useState<any>(null);
  const [payments, setPayments] = useState<PaymentResult | null>(null);
  const [docViewerOpen, setDocViewerOpen] = useState(false);
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const autoSaveTimer = useRef<NodeJS.Timeout | null>(null);
  const autoSavePausedUntilRef = useRef(0);

  // react-hook-form — single source of truth for form state
  const { register, reset, setValue, getValues, watch, formState: { isDirty } } = useForm<any>({
    defaultValues: {},
  });

  // Watch classifier fields so ClassifierSelect stays in sync
  const watchedValues = watch();

  // Explicitly register custom fields so watch() tracks them properly
  useEffect(() => {
    const customFields = [
      'currency_code', 'country_dispatch_code', 'country_origin_name',
      'country_destination_code', 'incoterms_code', 'deal_nature_code',
      'deal_specifics_code', 'transport_type_border', 'trading_country_code',
      'special_ref_code', 'sender_counterparty_id', 'receiver_counterparty_id'
    ];
    customFields.forEach(f => register(f));
  }, [register]);

  const { data: decl } = useQuery({
    queryKey: ['declaration', id],
    queryFn: () => getDeclaration(id!),
    enabled: !!id,
    staleTime: 30_000, // don't refetch for 30s
  });

  const { data: itemsData, refetch: refetchItems } = useQuery({
    queryKey: ['declaration-items', id],
    queryFn: () => getItems(id!),
    enabled: !!id,
    staleTime: 10_000,
  });

  const { data: docsData } = useQuery({
    queryKey: ['declaration-docs', id],
    queryFn: () => getDocuments({ declaration_id: id! }),
    enabled: !!id,
    staleTime: 15_000,
  });

  const docs: DocType[] = useMemo(() => {
    if (!docsData) return [];
    return Array.isArray(docsData) ? docsData : [];
  }, [docsData]);

  const items: DeclarationItem[] = useMemo(() => {
    if (Array.isArray(itemsData)) return itemsData;
    return (itemsData as any)?.items || [];
  }, [itemsData]);

  const formProgress = useMemo(() => {
    if (!watchedValues) return 0;
    const fields = ['type_code', 'currency_code', 'total_invoice_value', 'country_dispatch_code',
      'country_destination_code', 'incoterms_code', 'deal_nature_code', 'transport_type_border',
      'total_gross_weight', 'total_net_weight', 'total_packages_count', 'customs_office_code'];
    const filled = fields.filter(f => watchedValues[f] !== null && watchedValues[f] !== undefined && watchedValues[f] !== '').length;
    return Math.round((filled / fields.length) * 100);
  }, [watchedValues]);

  // Convert Decimal strings ("870.000") to numbers for form fields
  const normalizeDecl = (d: any) => {
    if (!d) return d;
    const numFields = ['total_invoice_value','exchange_rate','total_customs_value','total_gross_weight','total_net_weight','spot_amount','freight_amount'];
    const copy = { ...d };
    for (const f of numFields) {
      if (copy[f] !== null && copy[f] !== undefined) {
        const num = Number(copy[f]);
        copy[f] = Number.isNaN(num) ? copy[f] : num;
      }
    }
    return copy;
  };

  // Init form ONCE when declaration loads
  const loadedRef = useRef<string>('');
  const initialStepRef = useRef(false);

  const pauseAutoSave = useCallback((ms = 0) => {
    if (autoSaveTimer.current) {
      clearTimeout(autoSaveTimer.current);
      autoSaveTimer.current = null;
    }
    autoSavePausedUntilRef.current = Date.now() + ms;
    setAutoSaveStatus('idle');
  }, []);

  useEffect(() => {
    if (decl && decl.id !== loadedRef.current) {
      reset(normalizeDecl(decl));
      loadedRef.current = decl.id;
      autoSavePausedUntilRef.current = Date.now() + 1500;
      // Auto-step to review if data already exists
      if (!initialStepRef.current && (decl.currency_code || decl.total_invoice_value)) {
        setActiveStep(1);
        initialStepRef.current = true;
      }
    }
  }, [decl, reset]);

  const openedRef = useRef(false);
  useEffect(() => {
    if (decl && decl.status === 'new' && !openedRef.current) {
      openedRef.current = true;
      openDeclaration(decl.id)
        .then(() => queryClient.invalidateQueries({ queryKey: ['declaration', id] }))
        .catch(() => {});
    }
  }, [decl, id, queryClient]);

  // Auto-step if items loaded later
  useEffect(() => {
    if (!initialStepRef.current && items.length > 0) {
      setActiveStep(1);
      initialStepRef.current = true;
    }
  }, [items.length]);

  // Calculate payments when items change
  useEffect(() => {
    if (items.length > 0 && decl) {
      const payItems = items.map((i: any) => ({
        item_no: i.item_no, hs_code: i.hs_code || '',
        unit_price: i.unit_price ? Number(i.unit_price) : 0,
        quantity: i.additional_unit_qty ? Number(i.additional_unit_qty) : 1,
        customs_value_rub: i.customs_value_rub ? Number(i.customs_value_rub) : 0,
      }));
      calculatePayments(payItems, decl.currency_code || 'USD', decl.exchange_rate ? Number(decl.exchange_rate) : undefined)
        .then(setPayments)
        .catch(() => {});
    }
  }, [items, decl?.currency_code, decl?.exchange_rate]); // eslint-disable-line

  // Update a classifier field (setValue only, no extra state)
  const updateField = useCallback((field: string, value: string) => {
    setValue(field, value, { shouldDirty: true });
  }, [setValue]);

  const sanitizeData = (d: any) => {
    const copy = { ...d };
    const numFields = ['total_invoice_value','exchange_rate','total_customs_value','total_gross_weight','total_net_weight','spot_amount','freight_amount'];
    for (const f of numFields) {
      if (typeof copy[f] === 'string') {
        const val = copy[f].replace(/\s/g, '').replace(',', '.');
        copy[f] = val === '' ? null : Number(val);
      }
    }
    return copy;
  };

  const syncSavedDeclaration = useCallback((saved: Declaration) => {
    pauseAutoSave(1500);
    reset(normalizeDecl(saved));
    queryClient.setQueryData(['declaration', id], saved);
    if (!getValues().goods_location && saved.goods_location) {
      setValue('goods_location', saved.goods_location, { shouldDirty: false });
    }
    if (!getValues().declarant_inn_kpp && saved.declarant_inn_kpp) {
      setValue('declarant_inn_kpp', saved.declarant_inn_kpp, { shouldDirty: false });
    }
  }, [getValues, id, normalizeDecl, pauseAutoSave, queryClient, reset, setValue]);

  const persistDeclarationDraft = useCallback(async (): Promise<Declaration | null> => {
    if (!id) return null;
    const data = sanitizeData(getValues());
    const saved = await updateDeclaration(id, data);
    syncSavedDeclaration(saved);
    return saved;
  }, [getValues, id, sanitizeData, syncSavedDeclaration]);

  const handleSave = useCallback(async () => {
    try {
      const saved = await persistDeclarationDraft();
      if (!saved) return;
      setSnackMsg('Сохранено');
    } catch (e: any) {
      console.error('Declaration save failed:', e?.response?.data || e);
      setSnackMsg('Ошибка: ' + (e?.response?.data?.detail || e.message));
    }
  }, [persistDeclarationDraft]);

  useEffect(() => {
    if (!id || !loadedRef.current) return;
    if (decl?.status === 'sent') return;
    // Only auto-save on the actual form step, never on upload/result transition.
    if (activeStep !== 1) return;
    // Never auto-save untouched or freshly reset form state.
    if (!isDirty) return;
    if (Date.now() < autoSavePausedUntilRef.current) return;

    // Debounce 3 seconds
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(async () => {
      try {
        setAutoSaveStatus('saving');
        await persistDeclarationDraft();
        setAutoSaveStatus('saved');
        setTimeout(() => setAutoSaveStatus('idle'), 2000);
      } catch (e: any) {
        console.error('Declaration autosave failed:', e?.response?.data || e);
        setAutoSaveStatus('idle');
      }
    }, 3000);

    return () => { if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current); };
  }, [watchedValues, isDirty, activeStep, decl?.status, id, persistDeclarationDraft]); // eslint-disable-line

  const handleFinish = useCallback(async () => {
    await handleSave();
    navigate(`/declarations/${id}/edit`);
  }, [handleSave, navigate, id]);

  const handleApplyParsed = useCallback(async (parsed: any) => {
    if (!id) return;
    try {
      pauseAutoSave(15000);
      await client.post(`/declarations/${id}/apply-parsed`, {
        invoice_number: parsed.invoice_number, invoice_date: parsed.invoice_date,
        seller: parsed.seller ? { name: parsed.seller.name, country_code: parsed.seller.country_code, address: parsed.seller.address, inn: parsed.seller.inn, kpp: parsed.seller.kpp, ogrn: parsed.seller.ogrn, type: 'seller' } : undefined,
        buyer: parsed.buyer ? { name: parsed.buyer.name, country_code: parsed.buyer.country_code, address: parsed.buyer.address, inn: parsed.buyer.inn, kpp: parsed.buyer.kpp, ogrn: parsed.buyer.ogrn, type: 'buyer' } : undefined,
        buyer_matches_declarant: parsed.buyer_matches_declarant,
        currency: parsed.currency, total_amount: parsed.total_amount, incoterms: parsed.incoterms,
        delivery_place: parsed.delivery_place,
        transport_doc_number: parsed.transport_doc_number,
        transport_id: parsed.transport_id,
        transport_country_code: parsed.transport_country_code,
        trading_partner_country: parsed.trading_partner_country,
        country_dispatch: parsed.country_dispatch,
        container: parsed.container,
        country_origin: parsed.country_origin, country_destination: parsed.country_destination || 'RU',
        contract_number: parsed.contract_number, contract_date: parsed.contract_date,
        declarant_inn_kpp: parsed.declarant_inn_kpp,
        responsible_person: parsed.responsible_person,
        responsible_person_matches_declarant: parsed.responsible_person_matches_declarant,
        total_packages: parsed.total_packages,
        total_gross_weight: parsed.total_gross_weight, total_net_weight: parsed.total_net_weight,
        transport_type: parsed.transport_type || '40', deal_nature_code: parsed.deal_nature_code || '01', type_code: parsed.type_code || 'IM40',
        customs_office_code: parsed.customs_office_code,
        goods_location: parsed.goods_location,
        freight_amount: parsed.freight_amount, freight_currency: parsed.freight_currency,
        documents: parsed.documents,
        evidence_map: parsed.evidence_map,
        issues: parsed.issues,
        items: (parsed.items || []).map((item: any, idx: number) => ({
          line_no: item.line_no || idx + 1,
          description: item.description || item.commercial_name || '',
          commercial_name: item.commercial_name || item.description || '',
          quantity: item.quantity, unit: item.unit || 'pcs', unit_price: item.unit_price,
          line_total: item.line_total, hs_code: item.hs_code || '',
          invoice_currency: item.invoice_currency,
          country_origin_code: item.country_origin_code || parsed.country_origin,
          gross_weight: item.gross_weight, net_weight: item.net_weight,
          package_count: item.package_count, package_type: item.package_type,
        })),
        risk_score: parsed.risk_score, risk_flags: parsed.risk_flags, confidence: parsed.confidence,
      });
      if (parsed.risk_score) setRiskScore(parsed.risk_score);
      if (parsed.risk_flags) setRiskFlags(parsed.risk_flags);
      const fresh = await getDeclaration(id);
      pauseAutoSave(15000);
      reset(normalizeDecl(fresh));
      loadedRef.current = fresh.id;
      queryClient.setQueryData(['declaration', id], fresh);
      queryClient.invalidateQueries({ queryKey: ['counterparties'] });
      queryClient.invalidateQueries({ queryKey: ['declaration-docs', id] });
      await refetchItems();
      setSnackMsg('AI заполнил декларацию');
      navigate(`/declarations/${id}/edit`);
    } catch (e: any) {
      setSnackMsg('Ошибка: ' + (e?.response?.data?.detail || e.message));
    }
  }, [id, pauseAutoSave, reset, queryClient, refetchItems]);

  const handleEvidenceChange = useCallback(async (field: string, patch: Record<string, unknown>) => {
    if (!id) return;
    try {
      const res = await patchEvidenceMap(id, { [field]: patch });
      queryClient.setQueryData(['declaration', id], (old: any) =>
        old ? { ...old, evidence_map: res.evidence_map } : old,
      );
      setSnackMsg('Источник обновлён');
    } catch (e: any) {
      setSnackMsg('Ошибка: ' + (e?.response?.data?.detail || e.message));
    }
  }, [id, queryClient]);

  if (!decl) return <Container sx={{ py: 4 }}><Typography>Загрузка...</Typography></Container>;

  const totals = payments?.totals;
  const num = (v: any, d = 2) => v ? Number(v).toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—';

  const ev = decl.evidence_map;
  const lbl = (text: string, field: string) => (
    <>{text}<ConfidenceBadge evidenceMap={ev} fieldName={field} /></>
  );

  return (
    <AppLayout noPadding breadcrumbs={[{ label: 'Декларации', path: '/declarations' }, { label: 'Редактирование' }]}>
      {/* Action toolbar */}
      <Box sx={{ px: { xs: 2, md: 4 }, py: 1, display: 'flex', alignItems: 'center', gap: 1, maxWidth: 1400, mx: 'auto' }}>
        <Typography variant="h6" sx={{ flex: 1 }}>{decl.number_internal || 'Новая декларация'} — {decl.type_code || 'IM40'}</Typography>
        <StatusChip status={decl.status} />
        <Button startIcon={<Save />} onClick={handleSave} sx={{ ml: 2 }}>Сохранить</Button>
        {autoSaveStatus === 'saving' && <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>Сохранение...</Typography>}
        {autoSaveStatus === 'saved' && <Typography variant="caption" color="success.main" sx={{ ml: 1 }}>Сохранено</Typography>}
        <Button startIcon={<ViewIcon />} onClick={() => navigate(`/declarations/${id}/view`)} sx={{ ml: 1 }} variant="outlined">Просмотр ДТ</Button>
        {(docs.length > 0 || decl.evidence_map) && (
          <Button startIcon={<DocsIcon />} onClick={() => setDocViewerOpen(true)} sx={{ ml: 1 }} variant="outlined" color="secondary">
            Документы{docs.length > 0 ? ` (${docs.length})` : ''}
          </Button>
        )}
      </Box>

      <DocumentViewer
        documents={docs}
        open={docViewerOpen}
        onClose={() => setDocViewerOpen(false)}
        evidenceMap={decl.evidence_map}
        onEvidenceChange={handleEvidenceChange}
      />

      <Container maxWidth="lg" sx={{ py: 3 }}>
        <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
          {STEPS.map((label, i) => (
            <Step key={label} completed={i < activeStep} onClick={() => setActiveStep(i)} sx={{ cursor: 'pointer' }}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {activeStep === 1 && (
          <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="caption" color="text.secondary">Заполнение формы</Typography>
              <Typography variant="caption" color="text.secondary" fontWeight={600}>{formProgress}%</Typography>
            </Box>
            <LinearProgress variant="determinate" value={formProgress}
              color={formProgress >= 80 ? 'success' : formProgress >= 50 ? 'warning' : 'error'}
              sx={{ height: 6, borderRadius: 3 }} />
          </Box>
        )}

        {/* STEP 0 */}
        {activeStep === 0 && (
          <Box>
            <DocumentUploadPanel declarationId={id} onParsedData={handleApplyParsed} />
            {items.length === 0 && (
              <Alert severity="info" sx={{ mt: 2 }}>Загрузите PDF-документы. AI автоматически распознает и заполнит декларацию.</Alert>
            )}
            {items.length > 0 && (() => {
              const missing: string[] = [];
              if (!watchedValues.currency_code) missing.push('Валюта (22)');
              if (!watchedValues.total_invoice_value) missing.push('Сумма инвойса (22)');
              if (!watchedValues.country_origin_name) missing.push('Страна происхождения (16)');
              if (!watchedValues.country_dispatch_code) missing.push('Страна отправления (15)');
              if (!watchedValues.incoterms_code) missing.push('Incoterms (20)');
              if (!watchedValues.total_gross_weight) missing.push('Вес брутто (35)');
              if (!watchedValues.total_net_weight) missing.push('Вес нетто (38)');
              if (!watchedValues.total_packages_count) missing.push('Кол-во мест (6)');
              if (!watchedValues.exchange_rate) missing.push('Курс валюты (23)');
              if (!watchedValues.transport_type_border) missing.push('Вид транспорта (25)');
              if (!watchedValues.customs_office_code) missing.push('Таможенный пост (29)');
              if (!watchedValues.goods_location) missing.push('Местонахождение товаров (30)');
              const itemsMissing: string[] = [];
              items.forEach((it: any) => {
                if (!it.hs_code || it.hs_code.length < 10) itemsMissing.push(`Поз. #${it.item_no}: код ТН ВЭД`);
                if (!it.gross_weight) itemsMissing.push(`Поз. #${it.item_no}: вес брутто`);
                if (!it.net_weight) itemsMissing.push(`Поз. #${it.item_no}: вес нетто`);
              });
              return (
                <Box sx={{ mt: 2 }}>
                  {missing.length > 0 && (
                    <Alert severity="warning" sx={{ mb: 1 }}>
                      <strong>Не заполнено ({missing.length}):</strong> {missing.join(', ')}.
                      <br />Загрузите дополнительные документы (контракт, AWB, упак. лист) или заполните вручную на шаге 2.
                    </Alert>
                  )}
                  {itemsMissing.length > 0 && (
                    <Alert severity="info" sx={{ mb: 1 }}>
                      <strong>Товарные позиции:</strong> {itemsMissing.join('; ')}
                    </Alert>
                  )}
                  {missing.length === 0 && itemsMissing.length === 0 && (
                    <Alert severity="success" sx={{ mb: 1 }}>Все основные поля заполнены. Перейдите к проверке.</Alert>
                  )}
                  <Button variant="contained" onClick={() => setActiveStep(1)} sx={{ mt: 1 }}>
                    {missing.length > 0 ? 'Перейти к проверке и ручному заполнению' : 'Данные загружены — перейти к проверке'}
                  </Button>
                </Box>
              );
            })()}
          </Box>
        )}

        {/* STEP 1 */}
        {activeStep === 1 && loadedRef.current && (
          <Grid container spacing={2}>
            <Grid item xs={12} md={8}>
              <Paper sx={{ p: 2, mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2, gap: 1 }}>
                  <Typography variant="subtitle1" fontWeight={600}>Основные данные декларации</Typography>
                  {decl.ai_confidence != null && (
                    <Typography
                      variant="caption"
                      sx={{
                        px: 1, py: 0.25, borderRadius: 1, fontWeight: 700,
                        bgcolor: Number(decl.ai_confidence) >= 0.85 ? '#e8f5e9' : Number(decl.ai_confidence) >= 0.6 ? '#fff3e0' : '#ffebee',
                        color: Number(decl.ai_confidence) >= 0.85 ? '#2e7d32' : Number(decl.ai_confidence) >= 0.6 ? '#ed6c02' : '#d32f2f',
                      }}
                    >
                      AI: {Math.round(Number(decl.ai_confidence) * 100)}%
                    </Typography>
                  )}
                </Box>
                <Grid container spacing={2}>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Тип (1)", "type_code")} {...register('type_code')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Внутр. номер" {...register('number_internal')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="declaration_specifics" value={watchedValues.special_ref_code || ''} onChange={(c) => updateField('special_ref_code', c)} label={lbl("Особенности (7)", "special_ref_code")} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="currency" value={watchedValues.currency_code || ''} onChange={(c) => updateField('currency_code', c)} label={lbl("Валюта (22)", "currency_code")} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Инвойс № (ДТС гр.4)", "invoice_number")} {...register('invoice_number')} InputLabelProps={{ shrink: true }} placeholder="HUAXINAG20251763/25" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Инвойс дата (ДТС гр.4)", "invoice_date")} {...register('invoice_date')} type="date" InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Контракт № (ДТС гр.5)", "contract_number")} {...register('contract_number')} InputLabelProps={{ shrink: true }} placeholder="AG-TIAN-GPB1" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Контракт дата (ДТС гр.5)", "contract_date")} {...register('contract_date')} type="date" InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl(`Сумма инвойса (22) ${watchedValues.currency_code || ''}`, "total_invoice_value")} {...register('total_invoice_value')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={watchedValues.country_dispatch_code || ''} onChange={(c) => updateField('country_dispatch_code', c)} label={lbl("Страна отпр. (15)", "country_dispatch_code")} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={watchedValues.country_origin_name || ''} onChange={(c) => updateField('country_origin_name', c)} label={lbl("Происхождение (16)", "country_origin_name")} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={watchedValues.country_destination_code || ''} onChange={(c) => updateField('country_destination_code', c)} label={lbl("Назначение (17)", "country_destination_code")} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="incoterms" value={watchedValues.incoterms_code || ''} onChange={(c) => updateField('incoterms_code', c)} label={lbl("Incoterms (20)", "incoterms_code")} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Город поставки (20)", "delivery_place")} {...register('delivery_place')} InputLabelProps={{ shrink: true }} placeholder="SHIJIAZHUANG" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("ТС на границе (21)", "border_vehicle_info")} {...register('border_vehicle_info')} InputLabelProps={{ shrink: true }} placeholder="1:U3-9222" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Курс (23)" {...register('exchange_rate')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="deal_nature" value={watchedValues.deal_nature_code || ''} onChange={(c) => updateField('deal_nature_code', c)} label={lbl("Хар. сделки (24.1)", "deal_nature_code")} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Особ. сделки (24.2)", "deal_specifics_code")} {...register('deal_specifics_code')} InputLabelProps={{ shrink: true }} placeholder="01" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="transport_type" value={watchedValues.transport_type_border || ''} onChange={(c) => updateField('transport_type_border', c)} label={lbl("Транспорт (25)", "transport_type_border")} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Орган въезда (29)", "entry_customs_code")} {...register('entry_customs_code')} InputLabelProps={{ shrink: true }} placeholder="10005020" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={watchedValues.trading_country_code || ''} onChange={(c) => updateField('trading_country_code', c)} label={lbl("Торг. страна (11)", "trading_country_code")} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Мест (6)", "total_packages_count")} type="number" {...register('total_packages_count')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Брутто, кг (35)", "total_gross_weight")} {...register('total_gross_weight')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Нетто, кг (38)", "total_net_weight")} {...register('total_net_weight')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={12} md={6}><TextField size="small" fullWidth label={lbl("Местонахождение товаров / СВХ (30)", "goods_location")} {...register('goods_location')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("ИНН/КПП декларанта (14)", "declarant_inn_kpp")} {...register('declarant_inn_kpp')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Тамож. пост (29)", "customs_office_code")} {...register('customs_office_code')} InputLabelProps={{ shrink: true }} placeholder="10005030" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Отсрочка платежей (48)" {...register('payment_deferral')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Реквизиты склада (49)" {...register('warehouse_requisites')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Органы транзита (51)" {...register('transit_offices')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Орган назначения (53)" {...register('destination_office_code')} InputLabelProps={{ shrink: true }} /></Grid>
                </Grid>

                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>Транспорт и контейнер</Typography>
                <Grid container spacing={2} sx={{ mb: 2 }}>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Транспорт при отправлении (18)", "departure_vehicle_info")} {...register('departure_vehicle_info')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Контейнер (19)", "container_info")} {...register('container_info')} InputLabelProps={{ shrink: true }} inputProps={{ maxLength: 1 }} placeholder="0 или 1" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Внутр. транспорт (26)", "transport_type_inland")} {...register('transport_type_inland')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Место погрузки (27)", "loading_place")} {...register('loading_place')} InputLabelProps={{ shrink: true }} /></Grid>
                </Grid>

                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>Финансы и стоимость</Typography>
                <Grid container spacing={2} sx={{ mb: 2 }}>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Тамож. стоимость итого (12)", "total_customs_value")} {...register('total_customs_value')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Транспортные расходы", "freight_amount")} {...register('freight_amount')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Валюта трансп. расходов", "freight_currency")} {...register('freight_currency')} InputLabelProps={{ shrink: true }} inputProps={{ maxLength: 3 }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Гарантийная информация" {...register('guarantee_info')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={12} md={6}><TextField size="small" fullWidth label={lbl("Фин. банковские сведения (28)", "financial_info")} {...register('financial_info')} InputLabelProps={{ shrink: true }} /></Grid>
                </Grid>

                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>Количественные данные</Typography>
                <Grid container spacing={2} sx={{ mb: 2 }}>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Всего наименований (5)", "total_items_count")} type="number" {...register('total_items_count')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Кол-во форм ДТ (3)" type="number" {...register('forms_count')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Спецификаций (4)" type="number" {...register('specifications_count')} InputLabelProps={{ shrink: true }} /></Grid>
                </Grid>

                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>Декларант (дополнительно)</Typography>
                <Grid container spacing={2} sx={{ mb: 2 }}>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="ОГРН декларанта (14)" {...register('declarant_ogrn')} InputLabelProps={{ shrink: true }} inputProps={{ maxLength: 15 }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Телефон декларанта (14)" {...register('declarant_phone')} InputLabelProps={{ shrink: true }} /></Grid>
                </Grid>

                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>Прочие графы</Typography>
                <Grid container spacing={2} sx={{ mb: 2 }}>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Первая страна назначения (17б)", "country_first_destination_code")} {...register('country_first_destination_code')} InputLabelProps={{ shrink: true }} inputProps={{ maxLength: 2 }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Наименование СВХ (30б)", "warehouse_name")} {...register('warehouse_name')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={lbl("Место и дата (54)", "place_and_date")} {...register('place_and_date')} InputLabelProps={{ shrink: true }} /></Grid>
                </Grid>

                {/* --- Блок подписанта и ТП (графа 54, гр. 21, гр. 30) --- */}
                <Typography variant="subtitle2" sx={{ mt: 2, mb: 1, fontWeight: 600 }}>Подписант и таможенный представитель (гр. 54)</Typography>
                <Grid container spacing={1}>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="ФИО подписанта" {...register('signatory_name')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Должность" {...register('signatory_position')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Квалиф. аттестат" {...register('signatory_cert_number')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Доверенность" {...register('signatory_power_of_attorney')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Док. удостоверяющий личность" {...register('signatory_id_doc')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Номер в реестре ТП" {...register('broker_registry_number')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Договор ТП (номер)" {...register('broker_contract_number')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Договор ТП (дата)" {...register('broker_contract_date')} InputLabelProps={{ shrink: true }} type="date" /></Grid>
                </Grid>

                <Typography variant="subtitle2" sx={{ mt: 2, mb: 1, fontWeight: 600 }}>Транспорт на границе (гр. 21) и место товаров (гр. 30)</Typography>
                <Grid container spacing={1}>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Рег. номер ТС на границе (21)" {...register('transport_reg_number')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Страна рег. ТС (18)" {...register('departure_vehicle_country')} InputLabelProps={{ shrink: true }} inputProps={{ maxLength: 2 }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Код места товаров (30)" {...register('goods_location_code')} InputLabelProps={{ shrink: true }} inputProps={{ maxLength: 2 }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Код ТО места (30)" {...register('goods_location_customs_code')} InputLabelProps={{ shrink: true }} inputProps={{ maxLength: 8 }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Зона ТК (30)" {...register('goods_location_zone_id')} InputLabelProps={{ shrink: true }} /></Grid>
                </Grid>

                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>Участники сделки</Typography>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                      <Typography variant="caption" color="text.secondary">Отправитель (графа 2)</Typography>
                      <ConfidenceBadge evidenceMap={ev} fieldName="sender_counterparty_id" />
                    </Box>
                    <CounterpartyLookup type="seller" value={watchedValues.sender_counterparty_id || ''} label="Отправитель"
                      onChange={(cId) => updateField('sender_counterparty_id', cId || '')} />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                      <Typography variant="caption" color="text.secondary">Получатель (графа 8)</Typography>
                      <ConfidenceBadge evidenceMap={ev} fieldName="receiver_counterparty_id" />
                    </Box>
                    <CounterpartyLookup type="buyer" value={watchedValues.receiver_counterparty_id || ''} label="Получатель"
                      onChange={(cId) => updateField('receiver_counterparty_id', cId || '')} />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                      <Typography variant="caption" color="text.secondary">Лицо, отв. за фин. урегулирование (графа 9)</Typography>
                      <ConfidenceBadge evidenceMap={ev} fieldName="financial_counterparty_id" />
                    </Box>
                    <CounterpartyLookup type="buyer" value={watchedValues.financial_counterparty_id || ''} label="Фин. лицо (9)"
                      onChange={(cId) => updateField('financial_counterparty_id', cId || '')} />
                  </Grid>
                </Grid>
                <Button variant="contained" size="small" onClick={handleSave} startIcon={<Save />} sx={{ mt: 2 }}>Сохранить</Button>
              </Paper>

              {/* Items */}
              <Paper sx={{ p: 2, mb: 2 }}>
                <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>Товарные позиции ({items.length})</Typography>
                {items.length === 0 && <Alert severity="warning">Нет товарных позиций. Загрузите документы на шаге 1.</Alert>}
                {items.map((item: DeclarationItem) => (
                  <ItemEditCard
                    key={item.id}
                    item={item}
                    declarationId={id!}
                    currencyCode={watchedValues.currency_code}
                    onSaved={() => refetchItems()}
                    onDeleted={() => refetchItems()}
                  />
                ))}
              </Paper>

              {/* Payments */}
              {totals && (
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>Исчисление платежей (графа 47)</Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography variant="body2" color="text.secondary">Таможенная стоимость ({watchedValues.currency_code || '?'} {watchedValues.total_invoice_value ? num(watchedValues.total_invoice_value) : '—'} × курс {watchedValues.exchange_rate ? num(watchedValues.exchange_rate, 4) : '—'})</Typography>
                      <Typography variant="body2" fontWeight={700}>{num(totals.total_customs_value)} руб</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace' }}>1010 — Таможенный сбор</Typography>
                      <Typography variant="body2">{num(totals.customs_fee)} руб <Typography component="span" variant="caption" color="text.disabled">ИУ</Typography></Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace' }}>2010 — Ввозная пошлина ({payments?.items?.[0]?.duty?.rate || 0}%)</Typography>
                      <Typography variant="body2">{num(totals.total_duty)} руб <Typography component="span" variant="caption" color="text.disabled">ИУ</Typography></Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace' }}>5010 — НДС ({payments?.items?.[0]?.vat?.rate || 22}%)</Typography>
                      <Typography variant="body2">{num(totals.total_vat)} руб <Typography component="span" variant="caption" color="text.disabled">ИУ</Typography></Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', pt: 1, mt: 0.5, borderTop: '2px solid', borderColor: 'divider' }}>
                      <Typography variant="subtitle1" fontWeight={700}>ИТОГО к уплате</Typography>
                      <Typography variant="h6" color="primary.main" fontWeight={700}>{num(totals.grand_total)} руб</Typography>
                    </Box>
                  </Box>
                </Paper>
              )}

              {/* ДТС — Декларация таможенной стоимости */}
              {items.length > 0 && decl && (
                <Box sx={{ mb: 2 }}>
                  <DtsPanel declaration={decl} items={items} />
                </Box>
              )}

              {items.length > 0 && (
                <Accordion disableGutters sx={{ mb: 2, '&:before': { display: 'none' } }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle2" fontWeight={600}>
                      AI-детали и история ТН ВЭД
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails sx={{ pt: 0 }}>
                    <AiExplainPanel declaration={decl} items={items} />
                  </AccordionDetails>
                </Accordion>
              )}
            </Grid>

            {/* Right panel */}
            <Grid item xs={12} md={4}>
              <DeclarationStatusTimeline declaration={decl} />
              <NextActionsPanel
                declaration={decl}
                items={items}
                documentsCount={docs.length}
                onGoToUpload={() => setActiveStep(0)}
                onGoToReview={() => setActiveStep(1)}
                onOpenDocuments={() => setDocViewerOpen(true)}
              />
              {(riskScore > 0 || riskFlags) && <Box sx={{ mb: 2 }}><RiskPanel riskScore={riskScore} risks={riskFlags?.risks || []} source={riskFlags?.source} /></Box>}
              <DeclarationChecklist declaration={decl} items={items} formValues={watchedValues} />
              {id && <HistoryPanel declarationId={id} />}
              <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                <Button variant="outlined" onClick={() => setActiveStep(0)}>Назад</Button>
                <Button variant="contained" onClick={handleFinish} color="success">Завершить</Button>
              </Box>
            </Grid>
          </Grid>
        )}

        {/* STEP 2 */}
        {activeStep === 2 && (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <AiIcon sx={{ fontSize: 60, color: 'success.main', mb: 2 }} />
            <Typography variant="h5" fontWeight={700} gutterBottom>Декларация готова</Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 1 }}>
              {decl.type_code} — {decl.currency_code} {decl.total_invoice_value ? Number(decl.total_invoice_value).toLocaleString('ru-RU') : ''}
            </Typography>
            {totals && <Typography variant="h6" color="primary.main" fontWeight={700} sx={{ mb: 3 }}>Платежи: {num(totals.grand_total)} руб</Typography>}
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Button variant="contained" size="large" startIcon={<ViewIcon />} onClick={() => navigate(`/declarations/${id}/view`)}>Открыть декларацию (ДТ)</Button>
              <Button variant="outlined" onClick={() => setActiveStep(1)}>Редактировать</Button>
              <Button variant="outlined" onClick={() => navigate('/declarations')}>К списку</Button>
            </Box>
            <Divider sx={{ my: 3 }} />
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>Отправка в таможню</Typography>
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Button variant="contained" color="primary" onClick={async () => {
                try { const r = await client.get(`/declarations/${id}/export-pdf`, { responseType: 'blob' }); const u = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' })); const a = document.createElement('a'); a.href = u; a.download = `DT_${(id||'').slice(0,8)}.pdf`; a.click(); setSnackMsg('PDF скачан'); } catch { setSnackMsg('Ошибка PDF'); }
              }}>Скачать PDF</Button>
              <Button variant="outlined" color="secondary" onClick={async () => {
                try {
                  const r = await client.get(`/integration/export-xml/${id}`, { responseType: 'blob', baseURL: '/api/v1' });
                  const u = window.URL.createObjectURL(new Blob([r.data], { type: 'application/xml' }));
                  const a = document.createElement('a'); a.href = u; a.download = `DT_${(id||'').slice(0,8)}.xml`; a.click();
                  setSnackMsg('XML скачан');
                } catch { setSnackMsg('Ошибка XML'); }
              }}>XML декларации (ДТ)</Button>
              <Button variant="outlined" color="secondary" onClick={async () => {
                try {
                  const r = await client.get(`/integration/export-dts-xml/${id}`, { responseType: 'blob', baseURL: '/api/v1' });
                  const u = window.URL.createObjectURL(new Blob([r.data], { type: 'application/xml' }));
                  const a = document.createElement('a'); a.href = u; a.download = `DTS_${(id||'').slice(0,8)}.xml`; a.click();
                  setSnackMsg('XML ДТС скачан');
                } catch { setSnackMsg('Ошибка XML ДТС'); }
              }}>XML стоимости (ДТС)</Button>
              <Button variant="text" color="secondary" size="small" onClick={async () => {
                try {
                  const r = await client.get(`/integration/validate-xml/${id}`, { baseURL: '/api/v1' });
                  const d = r.data;
                  if (d.valid) setSnackMsg('XML валиден — готов к подаче');
                  else setSnackMsg(`XML ошибки: ${(d.errors || []).join('; ')}`);
                } catch { setSnackMsg('Ошибка проверки XML'); }
              }}>Проверить XML</Button>
              <Button variant="outlined" color="secondary" onClick={() => setSnackMsg('ЭЦП: будет в следующей версии')}>Подписать ЭЦП</Button>
              <Button variant="contained" color="secondary" onClick={() => setSnackMsg('ФТС: будет в следующей версии')}>Отправить в таможню</Button>
            </Box>
          </Paper>
        )}
      </Container>
      <Snackbar open={!!snackMsg} autoHideDuration={4000} onClose={() => setSnackMsg('')} message={snackMsg} />
    </AppLayout>
  );
};

export default DeclarationEditPage;
