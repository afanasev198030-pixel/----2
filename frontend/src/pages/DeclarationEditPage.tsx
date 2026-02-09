import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import {
  Box, AppBar, Toolbar, Typography, Button, Container,
  Stepper, Step, StepLabel, Paper, TextField, Grid,
  IconButton, Chip, Alert, Snackbar, Divider,
} from '@mui/material';
import {
  ArrowBack, Save, AutoAwesome as AiIcon,
  Visibility as ViewIcon, Delete as DeleteIcon,
} from '@mui/icons-material';
import {
  getDeclaration, updateDeclaration,
} from '../api/declarations';
import { getItems, deleteItem } from '../api/items';
import { calculatePayments, PaymentResult } from '../api/calc';
import client from '../api/client';
import StatusChip from '../components/StatusChip';
import DocumentUploadPanel from '../components/DocumentUploadPanel';
import ClassifierSelect from '../components/ClassifierSelect';
import HSCodeSuggestions from '../components/HSCodeSuggestions';
import RiskPanel from '../components/RiskPanel';
import DeclarationChecklist from '../components/DeclarationChecklist';
import HistoryPanel from '../components/HistoryPanel';
import { Declaration, DeclarationItem } from '../types';

const STEPS = ['Загрузка документов', 'Проверка данных', 'Готово'];

const DeclarationEditPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeStep, setActiveStep] = useState(0);
  const [snackMsg, setSnackMsg] = useState('');
  const [riskScore, setRiskScore] = useState(0);
  const [riskFlags, setRiskFlags] = useState<any>(null);
  const [formValues, setFormValues] = useState<any>({});
  const [formReady, setFormReady] = useState(false);
  const [initialStepSet, setInitialStepSet] = useState(false);
  const [payments, setPayments] = useState<PaymentResult | null>(null);

  const { register, reset, setValue, getValues } = useForm<any>();

  const { data: decl, refetch: refetchDecl } = useQuery({
    queryKey: ['declaration', id],
    queryFn: () => getDeclaration(id!),
    enabled: !!id,
  });

  const { data: itemsData, refetch: refetchItems } = useQuery({
    queryKey: ['declaration-items', id],
    queryFn: () => getItems(id!),
    enabled: !!id,
  });

  const items: DeclarationItem[] = Array.isArray(itemsData) ? itemsData : (itemsData as any)?.items || [];

  // Init form ONCE when decl loads
  useEffect(() => {
    if (decl && !formReady) {
      reset(decl);
      setFormValues({ ...decl });
      setFormReady(true);
    }
  }, [decl]); // eslint-disable-line

  // Set initial step ONCE
  useEffect(() => {
    if (formReady && !initialStepSet) {
      if (decl?.currency_code || decl?.total_invoice_value || items.length > 0) {
        setActiveStep(1);
      }
      setInitialStepSet(true);
    }
  }, [formReady, items.length]); // eslint-disable-line

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
  }, [items, decl?.currency_code]); // eslint-disable-line

  const updateField = (field: string, value: string) => {
    setValue(field, value);
    setFormValues((p: any) => ({ ...p, [field]: value }));
  };

  const handleSave = async () => {
    if (!id) return;
    try {
      const data = getValues();
      await updateDeclaration(id, data);
      setSnackMsg('Сохранено');
      // Don't refetch — it resets the form
    } catch (e: any) {
      setSnackMsg('Ошибка: ' + (e?.response?.data?.detail || e.message));
    }
  };

  const handleFinish = async () => {
    await handleSave();
    setActiveStep(2);
  };

  const handleApplyParsed = async (parsed: any) => {
    if (!id) return;
    try {
      await client.post(`/declarations/${id}/apply-parsed`, {
        invoice_number: parsed.invoice_number, invoice_date: parsed.invoice_date,
        seller: parsed.seller ? { name: parsed.seller.name, country_code: parsed.seller.country_code, address: parsed.seller.address, type: 'seller' } : undefined,
        buyer: parsed.buyer ? { name: parsed.buyer.name, country_code: parsed.buyer.country_code, address: parsed.buyer.address, type: 'buyer' } : undefined,
        currency: parsed.currency, total_amount: parsed.total_amount, incoterms: parsed.incoterms,
        country_origin: parsed.country_origin, country_destination: parsed.country_destination || 'RU',
        contract_number: parsed.contract_number, total_packages: parsed.total_packages,
        total_gross_weight: parsed.total_gross_weight, total_net_weight: parsed.total_net_weight,
        transport_type: '40', deal_nature_code: '01', type_code: 'IM40',
        items: (parsed.items || []).map((item: any, idx: number) => ({
          line_no: item.line_no || idx + 1,
          description: item.description || item.commercial_name || '',
          commercial_name: item.commercial_name || item.description || '',
          quantity: item.quantity, unit: item.unit || 'pcs', unit_price: item.unit_price,
          line_total: item.line_total, hs_code: item.hs_code || '',
          country_origin_code: item.country_origin_code || parsed.country_origin,
          gross_weight: item.gross_weight, net_weight: item.net_weight,
        })),
        risk_score: parsed.risk_score, risk_flags: parsed.risk_flags, confidence: parsed.confidence,
      });
      if (parsed.risk_score) setRiskScore(parsed.risk_score);
      if (parsed.risk_flags) setRiskFlags(parsed.risk_flags);
      // Refetch and update form
      const fresh = await getDeclaration(id);
      reset(fresh);
      setFormValues({ ...fresh });
      await refetchItems();
      setSnackMsg('AI заполнил декларацию');
      setActiveStep(1);
    } catch (e: any) {
      setSnackMsg('Ошибка: ' + (e?.response?.data?.detail || e.message));
    }
  };

  if (!decl) return <Container sx={{ py: 4 }}><Typography>Загрузка...</Typography></Container>;

  const totals = payments?.totals;
  const num = (v: any, d = 2) => v ? Number(v).toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—';

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#f5f6fa' }}>
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar>
          <IconButton onClick={() => navigate('/declarations')} sx={{ mr: 1 }}><ArrowBack /></IconButton>
          <Typography variant="h6" sx={{ flex: 1 }}>{decl.number_internal || 'Новая декларация'} — {decl.type_code || 'IM40'}</Typography>
          <StatusChip status={decl.status} />
          <Button startIcon={<Save />} onClick={handleSave} sx={{ ml: 2 }}>Сохранить</Button>
          <Button startIcon={<ViewIcon />} onClick={() => navigate(`/declarations/${id}/view`)} sx={{ ml: 1 }} variant="outlined">Просмотр ДТ</Button>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: 3 }}>
        <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
          {STEPS.map((label, i) => (
            <Step key={label} completed={i < activeStep} onClick={() => setActiveStep(i)} sx={{ cursor: 'pointer' }}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {/* STEP 0 */}
        {activeStep === 0 && (
          <Box>
            <DocumentUploadPanel declarationId={id} onParsedData={handleApplyParsed} />
            <Alert severity="info" sx={{ mt: 2 }}>Загрузите PDF-документы. AI автоматически распознает и заполнит декларацию.</Alert>
            {items.length > 0 && (
              <Button variant="contained" onClick={() => setActiveStep(1)} sx={{ mt: 2 }}>Данные загружены — перейти к проверке</Button>
            )}
          </Box>
        )}

        {/* STEP 1 */}
        {activeStep === 1 && formReady && (
          <Grid container spacing={2}>
            <Grid item xs={12} md={8}>
              <Paper sx={{ p: 2, mb: 2 }}>
                <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>Основные данные декларации</Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Тип (1)" {...register('type_code')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Номер (7)" {...register('number_internal')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="currency" value={formValues.currency_code || ''} onChange={(c) => updateField('currency_code', c)} label="Валюта (22)" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Сумма (22)" type="number" {...register('total_invoice_value')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={formValues.country_dispatch_code || ''} onChange={(c) => updateField('country_dispatch_code', c)} label="Страна отпр. (15)" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={formValues.country_origin_code || ''} onChange={(c) => updateField('country_origin_code', c)} label="Происхождение (16)" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={formValues.country_destination_code || ''} onChange={(c) => updateField('country_destination_code', c)} label="Назначение (17)" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="incoterms" value={formValues.incoterms_code || ''} onChange={(c) => updateField('incoterms_code', c)} label="Incoterms (20)" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Город поставки (20)" {...register('delivery_place')} InputLabelProps={{ shrink: true }} placeholder="SHIJIAZHUANG" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Рейс/транспорт (21)" {...register('transport_on_border_id')} InputLabelProps={{ shrink: true }} placeholder="1:U3-9222" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Курс (23)" type="number" {...register('exchange_rate')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="deal_nature" value={formValues.deal_nature_code || ''} onChange={(c) => updateField('deal_nature_code', c)} label="Хар. сделки (24)" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="transport_type" value={formValues.transport_type_border || ''} onChange={(c) => updateField('transport_type_border', c)} label="Транспорт (25)" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Орган въезда (29)" {...register('entry_customs_code')} InputLabelProps={{ shrink: true }} placeholder="10005020" /></Grid>
                  <Grid item xs={6} md={3}><ClassifierSelect classifierType="country" value={formValues.trading_country_code || ''} onChange={(c) => updateField('trading_country_code', c)} label="Торг. страна (11)" /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Мест (6)" type="number" {...register('total_packages_count')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Брутто, кг (35)" type="number" {...register('total_gross_weight')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Нетто, кг (38)" type="number" {...register('total_net_weight')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={12} md={6}><TextField size="small" fullWidth label="Местонахождение товаров / СВХ (30)" {...register('goods_location')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="ИНН/КПП декларанта (14)" {...register('declarant_inn_kpp')} InputLabelProps={{ shrink: true }} /></Grid>
                  <Grid item xs={6} md={3}><TextField size="small" fullWidth label="Тамож. пост (29)" {...register('customs_office_code')} InputLabelProps={{ shrink: true }} placeholder="10005030" /></Grid>
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
                      <Grid item xs={6}><Typography variant="caption" color="text.secondary">Описание (31)</Typography><Typography variant="body2" fontWeight={600}>{item.commercial_name || item.description || '—'}</Typography></Grid>
                      <Grid item xs={2}><Typography variant="caption" color="text.secondary">Страна</Typography><Typography variant="body2">{item.country_origin_code || '—'}</Typography></Grid>
                      <Grid item xs={2}><Typography variant="caption" color="text.secondary">Цена</Typography><Typography variant="body2">{item.unit_price ? Number(item.unit_price).toFixed(2) : '—'}</Typography></Grid>
                      <Grid item xs={2}><Typography variant="caption" color="text.secondary">Стоимость</Typography><Typography variant="body2" fontWeight={600}>{item.customs_value_rub ? Number(item.customs_value_rub).toLocaleString('ru-RU') : '—'}</Typography></Grid>
                    </Grid>
                    {!item.hs_code && <Alert severity="warning" sx={{ mt: 1 }} icon={<AiIcon />}>Нажмите "Подобрать" или введите код вручную.</Alert>}
                    <Box sx={{ mt: 1, display: 'flex', gap: 2, alignItems: 'flex-start' }}>
                      <TextField size="small" label="Код ТН ВЭД (33)" value={item.hs_code || ''} sx={{ width: 200 }}
                        inputProps={{ style: { fontFamily: 'monospace', fontWeight: 700, fontSize: 16 } }}
                        error={!item.hs_code || (item.hs_code?.length || 0) < 10}
                        onChange={(e) => { const v = e.target.value.replace(/\D/g, '').slice(0, 10); client.put(`/declarations/${id}/items/${item.id}`, { hs_code: v }).then(() => refetchItems()); }} />
                      <HSCodeSuggestions description={item.description || item.commercial_name || ''} currentCode={item.hs_code || ''}
                        onSelect={(code, name) => { client.put(`/declarations/${id}/items/${item.id}`, { hs_code: code }).then(() => { refetchItems(); setSnackMsg(`ТН ВЭД: ${code}`); }); }} />
                    </Box>
                  </Paper>
                ))}
              </Paper>

              {/* Payments */}
              {totals && (
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>Расчёт платежей (графа 47)</Typography>
                  <Grid container spacing={1}>
                    <Grid item xs={3}><Typography variant="caption">Тамож. стоимость</Typography><Typography variant="body2" fontWeight={700}>{num(totals.total_customs_value)} руб</Typography></Grid>
                    <Grid item xs={2}><Typography variant="caption">Пошлина</Typography><Typography variant="body2">{num(totals.total_duty)} руб</Typography></Grid>
                    <Grid item xs={2}><Typography variant="caption">НДС</Typography><Typography variant="body2">{num(totals.total_vat)} руб</Typography></Grid>
                    <Grid item xs={2}><Typography variant="caption">Сбор</Typography><Typography variant="body2">{num(totals.customs_fee)} руб</Typography></Grid>
                    <Grid item xs={3}><Typography variant="caption">ИТОГО</Typography><Typography variant="h6" color="primary.main" fontWeight={700}>{num(totals.grand_total)} руб</Typography></Grid>
                  </Grid>
                </Paper>
              )}
            </Grid>

            {/* Right panel */}
            <Grid item xs={12} md={4}>
              {(riskScore > 0 || riskFlags) && <Box sx={{ mb: 2 }}><RiskPanel riskScore={riskScore} risks={riskFlags?.risks || []} source={riskFlags?.source} /></Box>}
              <DeclarationChecklist declaration={decl} items={items} />
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
              <Button variant="outlined" color="secondary" onClick={() => setSnackMsg('XML: будет в следующей версии')}>Сформировать XML</Button>
              <Button variant="outlined" color="secondary" onClick={() => setSnackMsg('ЭЦП: будет в следующей версии')}>Подписать ЭЦП</Button>
              <Button variant="contained" color="secondary" onClick={() => setSnackMsg('ФТС: будет в следующей версии')}>Отправить в таможню</Button>
            </Box>
          </Paper>
        )}
      </Container>
      <Snackbar open={!!snackMsg} autoHideDuration={4000} onClose={() => setSnackMsg('')} message={snackMsg} />
    </Box>
  );
};

export default DeclarationEditPage;
