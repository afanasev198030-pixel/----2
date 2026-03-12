import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Paper, Box, Typography, Button, Grid, Divider, Alert,
  Checkbox, FormControlLabel, TextField, CircularProgress,
  Accordion, AccordionSummary, AccordionDetails, Chip,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Calculate as CalcIcon,
  AutoAwesome as AiIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import {
  getDts,
  generateDts,
  updateDts,
  updateDtsItem,
  recalculateDts,
  deleteDts,
} from '../api/customsValue';
import { Declaration, DeclarationItem, CustomsValueDeclaration } from '../types';
import DtsItemCard from './DtsItemCard';

interface DtsPanelProps {
  declaration: Declaration;
  items: DeclarationItem[];
}

const num = (v?: number | null) =>
  v != null ? Number(v).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';

const DtsPanel = ({ declaration, items }: DtsPanelProps) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const declId = declaration.id;
  const [error, setError] = useState('');

  const { data: dts, isLoading, isError, refetch } = useQuery({
    queryKey: ['dts', declId],
    queryFn: () => getDts(declId),
    enabled: !!declId,
    retry: false,
  });

  const generateMut = useMutation({
    mutationFn: () => generateDts(declId),
    onSuccess: () => { refetch(); setError(''); },
    onError: (e: any) => setError(e?.response?.data?.detail || 'Ошибка генерации ДТС'),
  });

  const updateHeaderMut = useMutation({
    mutationFn: (data: Partial<CustomsValueDeclaration>) => updateDts(declId, data),
    onSuccess: () => refetch(),
  });

  const updateItemMut = useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: Record<string, number> }) =>
      updateDtsItem(declId, itemId, data),
    onSuccess: () => refetch(),
  });

  const recalcMut = useMutation({
    mutationFn: () => recalculateDts(declId),
    onSuccess: () => { refetch(); setError(''); },
    onError: () => setError('Ошибка пересчёта'),
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteDts(declId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['dts', declId] });
      refetch();
    },
  });

  const handleCheckbox = useCallback((field: string, checked: boolean) => {
    updateHeaderMut.mutate({ [field]: checked } as any);
  }, [updateHeaderMut]);

  const handleTextField = useCallback((field: string, value: string) => {
    updateHeaderMut.mutate({ [field]: value } as any);
  }, [updateHeaderMut]);

  const handleItemChange = useCallback((itemId: string, field: string, value: number) => {
    updateItemMut.mutate({ itemId, data: { [field]: value } });
  }, [updateItemMut]);

  const itemDescMap = useMemo(() => {
    const m: Record<string, string> = {};
    items.forEach((it) => { m[it.id] = it.description || it.commercial_name || ''; });
    return m;
  }, [items]);

  const totalCV = useMemo(() => {
    if (!dts?.items?.length) return 0;
    return dts.items.reduce((s, i) => s + (Number(i.customs_value_national) || 0), 0);
  }, [dts]);

  if (isLoading) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <CircularProgress size={24} />
        <Typography variant="body2" sx={{ mt: 1 }}>Загрузка ДТС...</Typography>
      </Paper>
    );
  }

  if (isError || !dts) {
    return (
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <AiIcon color="primary" />
          <Typography variant="subtitle1" fontWeight={700}>
            Декларация таможенной стоимости (ДТС-1)
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          ДТС ещё не сформирована. Нажмите кнопку для автоматической генерации из данных декларации.
        </Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Button
          variant="contained"
          startIcon={<CalcIcon />}
          onClick={() => generateMut.mutate()}
          disabled={generateMut.isPending || items.length === 0}
        >
          {generateMut.isPending ? 'Генерация...' : 'Сформировать ДТС'}
        </Button>
        {items.length === 0 && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            Нет товарных позиций. Сначала загрузите документы.
          </Alert>
        )}
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AiIcon color="primary" />
          <Typography variant="subtitle1" fontWeight={700}>
            Декларация таможенной стоимости (ДТС-1)
          </Typography>
          <Chip label="Метод 1" size="small" variant="outlined" />
        </Box>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button
            size="small" variant="contained"
            onClick={() => navigate(`/declarations/${declId}/dts-view`)}
          >
            Просмотр формы ДТС
          </Button>
          <Button
            size="small" variant="outlined" startIcon={<CalcIcon />}
            onClick={() => recalcMut.mutate()}
            disabled={recalcMut.isPending}
          >
            Пересчитать
          </Button>
          <Button
            size="small" variant="outlined" color="error" startIcon={<DeleteIcon />}
            onClick={() => { if (window.confirm('Удалить ДТС?')) deleteMut.mutate(); }}
          >
            Удалить
          </Button>
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* ===== Первый лист — общие сведения ===== */}
      <Accordion defaultExpanded disableGutters sx={{ mb: 2, '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle2" fontWeight={600}>Лист 1 — Общие сведения</Typography>
        </AccordionSummary>
        <AccordionDetails>
          {/* Read-only counterparty info from DT */}
          <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            Данные из декларации на товары (зеркало граф ДТ)
          </Typography>
          <Grid container spacing={1} sx={{ mb: 2 }}>
            <Grid item xs={12} md={4}>
              <TextField size="small" fullWidth label="Условия поставки (3)" value={declaration.incoterms_code || ''} InputProps={{ readOnly: true }} InputLabelProps={{ shrink: true }}
                sx={{ '& .MuiInputBase-root': { bgcolor: 'action.hover' } }} />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField size="small" fullWidth label="Перевозчик (17)"
                defaultValue={dts.transport_carrier_name || ''}
                onBlur={(e) => handleTextField('transport_carrier_name', e.target.value)}
                placeholder="Т/П АУЕЖАЙ-КАРАГАНДА"
                InputLabelProps={{ shrink: true }} />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField size="small" fullWidth label="Перевозка до (17)"
                defaultValue={dts.transport_destination || ''}
                onBlur={(e) => handleTextField('transport_destination', e.target.value)}
                placeholder={declaration.delivery_place || 'граница ЕАЭС'}
                InputLabelProps={{ shrink: true }} />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField size="small" fullWidth label="Валюта" value={declaration.currency_code || ''} InputProps={{ readOnly: true }} InputLabelProps={{ shrink: true }}
                sx={{ '& .MuiInputBase-root': { bgcolor: 'action.hover' } }} />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField size="small" fullWidth label="Курс ЦБ" value={declaration.exchange_rate || ''} InputProps={{ readOnly: true }} InputLabelProps={{ shrink: true }}
                sx={{ '& .MuiInputBase-root': { bgcolor: 'action.hover' } }} />
            </Grid>
          </Grid>

          <Divider sx={{ my: 1.5 }} />

          {/* Графа 7 — взаимосвязь */}
          <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            Графа 7 — Взаимосвязь продавца и покупателя
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
            <FormControlLabel control={
              <Checkbox size="small" checked={dts.related_parties}
                onChange={(_, v) => handleCheckbox('related_parties', v)} />
            } label="(a) Есть взаимосвязь?" />
            <FormControlLabel control={
              <Checkbox size="small" checked={dts.related_price_impact}
                onChange={(_, v) => handleCheckbox('related_price_impact', v)} />
            } label="(б) Повлияла на цену?" />
            <FormControlLabel control={
              <Checkbox size="small" checked={dts.related_verification}
                onChange={(_, v) => handleCheckbox('related_verification', v)} />
            } label="(в) Есть проверочная величина?" />
          </Box>

          {/* Графа 8 — ограничения */}
          <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            Графа 8 — Ограничения / условия
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
            <FormControlLabel control={
              <Checkbox size="small" checked={dts.restrictions}
                onChange={(_, v) => handleCheckbox('restrictions', v)} />
            } label="(а) Есть ограничения?" />
            <FormControlLabel control={
              <Checkbox size="small" checked={dts.price_conditions}
                onChange={(_, v) => handleCheckbox('price_conditions', v)} />
            } label="(б) Цена зависит от условий?" />
          </Box>

          {/* Графа 9 — ИС */}
          <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            Графа 9 — Интеллектуальная собственность
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
            <FormControlLabel control={
              <Checkbox size="small" checked={dts.ip_license_payments}
                onChange={(_, v) => handleCheckbox('ip_license_payments', v)} />
            } label="(а) Есть лицензионные платежи?" />
            <FormControlLabel control={
              <Checkbox size="small" checked={dts.sale_depends_on_income}
                onChange={(_, v) => handleCheckbox('sale_depends_on_income', v)} />
            } label="(б) Продажа зависит от дохода?" />
            <FormControlLabel control={
              <Checkbox size="small" checked={dts.income_to_seller}
                onChange={(_, v) => handleCheckbox('income_to_seller', v)} />
            } label="(в) Часть дохода продавцу?" />
          </Box>

          <Divider sx={{ my: 1.5 }} />

          {/* Графа 6 — документы */}
          <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            Графа 6 — Документы к графам 7–9
          </Typography>
          <TextField
            size="small" fullWidth multiline rows={2}
            label="Реквизиты дополнительных документов"
            value={dts.additional_docs || ''}
            onBlur={(e) => handleTextField('additional_docs', e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ mb: 2 }}
          />

          {/* Графа 10б — заполнивший */}
          <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            Графа 10б — Сведения о заполнившем
          </Typography>
          <Grid container spacing={1}>
            <Grid item xs={6} md={3}>
              <TextField size="small" fullWidth label="ФИО"
                defaultValue={dts.filler_name || ''}
                onBlur={(e) => handleTextField('filler_name', e.target.value)}
                InputLabelProps={{ shrink: true }} />
            </Grid>
            <Grid item xs={6} md={3}>
              <TextField size="small" fullWidth label="Дата" type="date"
                defaultValue={dts.filler_date || ''}
                onBlur={(e) => handleTextField('filler_date', e.target.value)}
                InputLabelProps={{ shrink: true }} />
            </Grid>
            <Grid item xs={6} md={3}>
              <TextField size="small" fullWidth label="Документ"
                defaultValue={dts.filler_document || ''}
                onBlur={(e) => handleTextField('filler_document', e.target.value)}
                InputLabelProps={{ shrink: true }} />
            </Grid>
            <Grid item xs={6} md={3}>
              <TextField size="small" fullWidth label="Контакты"
                defaultValue={dts.filler_contacts || ''}
                onBlur={(e) => handleTextField('filler_contacts', e.target.value)}
                InputLabelProps={{ shrink: true }} />
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>

      {/* ===== Второй лист — расчёт по товарам ===== */}
      <Accordion defaultExpanded disableGutters sx={{ mb: 2, '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle2" fontWeight={600}>
              Лист 2 — Расчёт по товарам ({dts.items.length})
            </Typography>
            <Chip
              label={`Итого ТС: ${num(totalCV)} ₽`}
              size="small" color="success" variant="filled"
              sx={{ fontWeight: 700 }}
            />
          </Box>
        </AccordionSummary>
        <AccordionDetails sx={{ pt: 0 }}>
          {dts.items.length === 0 && (
            <Alert severity="info">Нет позиций ДТС</Alert>
          )}
          {dts.items.map((cvi) => (
            <DtsItemCard
              key={cvi.id}
              item={cvi}
              description={itemDescMap[cvi.declaration_item_id]}
              currencyCode={declaration.currency_code || undefined}
              exchangeRate={declaration.exchange_rate != null ? Number(declaration.exchange_rate) : undefined}
              onChange={handleItemChange}
            />
          ))}
        </AccordionDetails>
      </Accordion>

      {/* Дополнительные данные */}
      <Accordion disableGutters sx={{ '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle2" fontWeight={600}>Дополнительные данные</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <TextField
            size="small" fullWidth multiline rows={3}
            label="Дополнительные данные ДТС"
            defaultValue={dts.additional_data || ''}
            onBlur={(e) => handleTextField('additional_data', e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
        </AccordionDetails>
      </Accordion>
    </Paper>
  );
};

export default DtsPanel;
