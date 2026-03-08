import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import {
  Box, Typography, Button, Container, LinearProgress,
  Stepper, Step, StepLabel, Paper, TextField, Grid,
  IconButton, Chip, Alert, Snackbar, Divider,
  Accordion, AccordionSummary, AccordionDetails,
} from '@mui/material';
import {
  Save, AutoAwesome as AiIcon,
  Visibility as ViewIcon, Delete as DeleteIcon,
  Description as DocsIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import {
  getDeclaration, updateDeclaration,
} from '../api/declarations';
import { getItems, deleteItem } from '../api/items';
import { getDocuments } from '../api/documents';
import { calculatePayments, PaymentResult } from '../api/calc';
import client from '../api/client';
import StatusChip from '../components/StatusChip';
import DocumentUploadPanel from '../components/DocumentUploadPanel';
import DocumentViewer from '../components/DocumentViewer';
import ClassifierSelect from '../components/ClassifierSelect';
import HSCodeSuggestions from '../components/HSCodeSuggestions';
import RequirementsPanel from '../components/RequirementsPanel';
import RiskPanel from '../components/RiskPanel';
import DeclarationChecklist from '../components/DeclarationChecklist';
import HistoryPanel from '../components/HistoryPanel';
import CounterpartyLookup from '../components/CounterpartyLookup';
import AiExplainPanel from '../components/AiExplainPanel';
import DeclarationStatusTimeline from '../components/DeclarationStatusTimeline';
import NextActionsPanel from '../components/NextActionsPanel';
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
      'currency_code', 'country_dispatch_code', 'country_origin_code',
      'country_destination_code', 'incoterms_code', 'deal_nature_code',
      'transport_type_border', 'trading_country_code',
      'sender_counterparty_id', 'receiver_counterparty_id'
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
    return (docsData as any)?.items || (Array.isArray(docsData) ? docsData : []);
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
    const numFields = ['total_invoice_value','exchange_rate','total_customs_value','total_gross_weight','total_net_weight','spot_amount'];
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
    const numFields = ['total_invoice_value','exchange_rate','total_customs_value','total_gross_weight','total_net_weight','spot_amount'];
    for (const f of numFields) {
      if (typeof copy[f] === 'string') {
        const val = copy[f].replace(/\s/g, '').replace(',', '.');
        copy[f] = val === '' ? null : Number(val);
      }
    }
    return copy;
  };

  const handleSave = useCallback(async () => {
    if (!id) return;
    try {
      const data = sanitizeData(getValues());
      const saved = await updateDeclaration(id, data);
      pauseAutoSave(1500);
      reset(normalizeDecl(saved));
      queryClient.setQueryData(['declaration', id], saved);
      if (!getValues().goods_location && saved.goods_location) {
        setValue('goods_location', saved.goods_location, { shouldDirty: false });
      }
      if (!getValues().declarant_inn_kpp && saved.declarant_inn_kpp) {
        setValue('declarant_inn_kpp', saved.declarant_inn_kpp, { shouldDirty: false });
      }
      setSnackMsg('Сохранено');
    } catch (e: any) {
      setSnackMsg('Ошибка: ' + (e?.response?.data?.detail || e.message));
    }
  }, [id, getValues, queryClient, setValue]);

  useEffect(() => {
    if (!id || !loadedRef.current) return;
    // Only auto-save drafts
    if (decl?.status !== 'draft') return;
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
        const data = sanitizeData(getValues());
        const saved = await updateDeclaration(id, data);
        pauseAutoSave(1500);
        reset(normalizeDecl(saved));
        queryClient.setQueryData(['declaration', id], saved);
        if (!getValues().goods_location && saved.goods_location) {
          setValue('goods_location', saved.goods_location, { shouldDirty: false });
        }
        if (!getValues().declarant_inn_kpp && saved.declarant_inn_kpp) {
          setValue('declarant_inn_kpp', saved.declarant_inn_kpp, { shouldDirty: false });
        }
        setAutoSaveStatus('saved');
        setTimeout(() => setAutoSaveStatus('idle'), 2000);
      } catch {
        setAutoSaveStatus('idle');
      }
    }, 3000);

    return () => { if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current); };
  }, [watchedValues, isDirty, activeStep, decl?.status, id, getValues, pauseAutoSave, queryClient, reset, setValue]); // eslint-disable-line

  const handleFinish = useCallback(async () => {
    await handleSave();
    setActiveStep(2);
  }, [handleSave]);

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
      setActiveStep(1);
    } catch (e: any) {
      setSnackMsg('Ошибка: ' + (e?.response?.data?.detail || e.message));
    }
  }, [id, pauseAutoSave, reset, queryClient, refetchItems]);

  if (!decl) return <Container sx={{ py: 4 }}><Typography>Загрузка...</Typography></Container>;

  const totals = payments?.totals;
  const num = (v: any, d = 2) => v ? Number(v).toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—';

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
        {docs.length > 0 && (
          <Button startIcon={<DocsIcon />} onClick={() => setDocViewerOpen(true)} sx={{ ml: 1 }} variant="outlined" color="secondary">
            Документы ({docs.length})
          </Button>
        )}
      </Box>

      <DocumentViewer documents={docs} open={docViewerOpen} onClose={() => setDocViewerOpen(false)} />

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
              if (!watchedValues.country_origin_code) missing.push('Страна происхождения (16)');
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
                <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>Основные данные декларации</Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Тип (1)" {...register('type_code')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Номер (7)" {...register('number_internal')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="currency" value={watchedValues.currency_code || ''} onChange={(c) => updateField('currency_code', c)} label="Валюта (22)" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label={`Сумма инвойса (22) ${watchedValues.currency_code || ''}`} {...register('total_invoice_value')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={watchedValues.country_dispatch_code || ''} onChange={(c) => updateField('country_dispatch_code', c)} label="Страна отпр. (15)" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={watchedValues.country_origin_code || ''} onChange={(c) => updateField('country_origin_code', c)} label="Происхождение (16)" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={watchedValues.country_destination_code || ''} onChange={(c) => updateField('country_destination_code', c)} label="Назначение (17)" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="incoterms" value={watchedValues.incoterms_code || ''} onChange={(c) => updateField('incoterms_code', c)} label="Incoterms (20)" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Город поставки (20)" {...register('delivery_place')} InputLabelProps={{ shrink: true }} placeholder="SHIJIAZHUANG" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Рейс/транспорт (21)" {...register('transport_on_border_id')} InputLabelProps={{ shrink: true }} placeholder="1:U3-9222" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Курс (23)" {...register('exchange_rate')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="deal_nature" value={watchedValues.deal_nature_code || ''} onChange={(c) => updateField('deal_nature_code', c)} label="Хар. сделки (24)" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="transport_type" value={watchedValues.transport_type_border || ''} onChange={(c) => updateField('transport_type_border', c)} label="Транспорт (25)" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Орган въезда (29)" {...register('entry_customs_code')} InputLabelProps={{ shrink: true }} placeholder="10005020" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={watchedValues.trading_country_code || ''} onChange={(c) => updateField('trading_country_code', c)} label="Торг. страна (11)" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Мест (6)" type="number" {...register('total_packages_count')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Брутто, кг (35)" {...register('total_gross_weight')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Нетто, кг (38)" {...register('total_net_weight')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={12} md={6}><TextField size="small" fullWidth label="Местонахождение товаров / СВХ (30)" {...register('goods_location')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="ИНН/КПП декларанта (14)" {...register('declarant_inn_kpp')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Тамож. пост (29)" {...register('customs_office_code')} InputLabelProps={{ shrink: true }} placeholder="10005030" /></Grid>
                </Grid>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>Участники сделки</Typography>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <CounterpartyLookup type="seller" value={watchedValues.sender_counterparty_id || ''} label="Отправитель (графа 2)"
                      onChange={(cId) => updateField('sender_counterparty_id', cId || '')} />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <CounterpartyLookup type="buyer" value={watchedValues.receiver_counterparty_id || ''} label="Получатель (графа 8)"
                      onChange={(cId) => updateField('receiver_counterparty_id', cId || '')} />
                  </Grid>
                </Grid>
                <Button variant="contained" size="small" onClick={handleSave} startIcon={<Save />} sx={{ mt: 2 }}>Сохранить</Button>
              </Paper>

              {/* Items */}
              <Paper sx={{ p: 2, mb: 2 }}>
                <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>Товарные позиции ({items.length})</Typography>
                {items.length === 0 && <Alert severity="warning">Нет товарных позиций. Загрузите документы на шаге 1.</Alert>}
                {items.map((item: DeclarationItem, idx: number) => (
                  <Paper key={item.id} variant="outlined" sx={{ p: 2, mb: 2, borderColor: !item.hs_code ? 'error.main' : 'divider' }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle2" fontWeight={700}>Позиция #{item.item_no || idx + 1}</Typography>
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                        {item.hs_code ? <Chip label={`ТН ВЭД: ${item.hs_code}`} color="success" size="small" sx={{ fontFamily: 'monospace', fontWeight: 700 }} />
                          : <Chip label="Код не указан" color="error" size="small" />}
                        <IconButton size="small" onClick={() => { deleteItem(id!, item.id).then(() => refetchItems()); }}><DeleteIcon fontSize="small" /></IconButton>
                      </Box>
                    </Box>
                    <Grid container spacing={1}>
                      <Grid item xs={3}><Typography variant="caption" color="text.secondary">Описание (31)</Typography><Typography variant="body2" fontWeight={600} sx={{ wordBreak: 'break-word' }}>{item.commercial_name || item.description || '—'}</Typography></Grid>
                      <Grid item xs={1}><Typography variant="caption" color="text.secondary">Страна</Typography><Typography variant="body2">{item.country_origin_code || '—'}</Typography></Grid>
                      <Grid item xs={1.5}><Typography variant="caption" color="text.secondary">Кол-во</Typography><Typography variant="body2" noWrap>{item.additional_unit_qty ? Number(item.additional_unit_qty).toLocaleString('ru-RU') : '—'}<br /><Typography component="span" variant="caption" color="text.secondary">{item.additional_unit || 'pcs'}</Typography></Typography></Grid>
                      <Grid item xs={1.5}><Typography variant="caption" color="text.secondary">Цена ({watchedValues.currency_code || '?'})</Typography><Typography variant="body2">{item.unit_price ? Number(item.unit_price).toLocaleString('ru-RU', { minimumFractionDigits: 2 }) : '—'}</Typography></Grid>
                      <Grid item xs={2}><Typography variant="caption" color="text.secondary">Сумма ({watchedValues.currency_code || '?'})</Typography><Typography variant="body2">{item.unit_price && item.additional_unit_qty ? (Number(item.unit_price) * Number(item.additional_unit_qty)).toLocaleString('ru-RU', { minimumFractionDigits: 2 }) : '—'}</Typography></Grid>
                      <Grid item xs={2}><Typography variant="caption" color="text.secondary">Тамож. стоимость (руб)</Typography><Typography variant="body2" fontWeight={600} color="primary.main">{item.customs_value_rub ? Number(item.customs_value_rub).toLocaleString('ru-RU', { minimumFractionDigits: 2 }) : '—'}</Typography></Grid>
                    </Grid>
                    {!item.hs_code && <Alert severity="warning" sx={{ mt: 1 }} icon={<AiIcon />}>Нажмите "Подобрать" или введите код вручную.</Alert>}
                    <Box sx={{ mt: 1, display: 'flex', gap: 2, alignItems: 'flex-start' }}>
                      <TextField size="small" label="Код ТН ВЭД (33)" value={item.hs_code || ''} sx={{ width: 200 }}
                        inputProps={{ style: { fontFamily: 'monospace', fontWeight: 700, fontSize: 16 } }}
                        error={!item.hs_code || (item.hs_code?.length || 0) < 10}
                        onChange={(e) => { const v = e.target.value.replace(/\D/g, '').slice(0, 10); client.put(`/declarations/${id}/items/${item.id}`, { hs_code: v }).then(() => refetchItems()); }} />
                      <HSCodeSuggestions description={item.description || item.commercial_name || ''} currentCode={item.hs_code || ''} declarationId={id}
                        onSelect={(code, name) => { client.put(`/declarations/${id}/items/${item.id}`, { hs_code: code }).then(() => { refetchItems(); setSnackMsg(`ТН ВЭД: ${code}`); }); }} />
                    </Box>
                    {item.hs_code && item.hs_code.length >= 4 && (
                      <RequirementsPanel hsCode={item.hs_code} description={item.description || item.commercial_name || ''} />
                    )}
                  </Paper>
                ))}
              </Paper>

              {/* Payments */}
              {totals && (
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>Расчёт платежей (графа 47)</Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography variant="body2" color="text.secondary">Таможенная стоимость ({watchedValues.currency_code || '?'} {watchedValues.total_invoice_value ? num(watchedValues.total_invoice_value) : '—'} × курс {watchedValues.exchange_rate ? num(watchedValues.exchange_rate, 4) : '—'})</Typography>
                      <Typography variant="body2" fontWeight={700}>{num(totals.total_customs_value)} руб</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography variant="body2" color="text.secondary">Ввозная пошлина ({payments?.items?.[0]?.duty?.rate || 0}%)</Typography>
                      <Typography variant="body2">{num(totals.total_duty)} руб</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography variant="body2" color="text.secondary">НДС ({payments?.items?.[0]?.vat?.rate || 20}%)</Typography>
                      <Typography variant="body2">{num(totals.total_vat)} руб</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography variant="body2" color="text.secondary">Таможенный сбор</Typography>
                      <Typography variant="body2">{num(totals.customs_fee)} руб</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', pt: 1, mt: 0.5, borderTop: '2px solid', borderColor: 'divider' }}>
                      <Typography variant="subtitle1" fontWeight={700}>ИТОГО к уплате</Typography>
                      <Typography variant="h6" color="primary.main" fontWeight={700}>{num(totals.grand_total)} руб</Typography>
                    </Box>
                  </Box>
                </Paper>
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
              }}>Сформировать XML</Button>
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
