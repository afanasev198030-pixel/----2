import { useState } from 'react';
import {
  Paper, Box, Typography, TextField, Grid, Divider,
  Accordion, AccordionSummary, AccordionDetails, Chip,
} from '@mui/material';
import { ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import { CustomsValueItem } from '../types';

interface DtsItemCardProps {
  item: CustomsValueItem;
  description?: string;
  onChange: (itemId: string, field: string, value: number) => void;
}

const num = (v?: number | null) =>
  v != null ? Number(v).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';

const ADDITION_FIELDS: { key: keyof CustomsValueItem; label: string; graph: string }[] = [
  { key: 'broker_commission', label: 'Вознагр. агентам/брокерам', graph: '13а' },
  { key: 'packaging_cost', label: 'Тара и упаковка', graph: '13б' },
  { key: 'raw_materials', label: 'Сырьё, детали, полуфабрикаты', graph: '14а' },
  { key: 'tools_molds', label: 'Инструменты, штампы, формы', graph: '14б' },
  { key: 'consumed_materials', label: 'Материалы', graph: '14в' },
  { key: 'design_engineering', label: 'Проектирование, дизайн', graph: '14г' },
  { key: 'license_payments', label: 'Лицензионные платежи', graph: '15' },
  { key: 'seller_income', label: 'Часть дохода продавцу', graph: '16' },
  { key: 'transport_cost', label: 'Расходы на перевозку', graph: '17' },
  { key: 'loading_unloading', label: 'Погрузка/разгрузка', graph: '18' },
  { key: 'insurance_cost', label: 'Страхование', graph: '19' },
];

const DEDUCTION_FIELDS: { key: keyof CustomsValueItem; label: string; graph: string }[] = [
  { key: 'construction_after_import', label: 'Строительство/монтаж после ввоза', graph: '21' },
  { key: 'inland_transport', label: 'Перевозка по территории ЕАЭС', graph: '22' },
  { key: 'duties_taxes', label: 'Пошлины, налоги, сборы', graph: '23' },
];

const DtsItemCard = ({ item, description, onChange }: DtsItemCardProps) => {
  const [expanded, setExpanded] = useState(true);

  const handleChange = (field: string, raw: string) => {
    const value = parseFloat(raw) || 0;
    onChange(item.id, field, value);
  };

  return (
    <Accordion
      expanded={expanded}
      onChange={() => setExpanded(!expanded)}
      disableGutters
      sx={{ mb: 1.5, '&:before': { display: 'none' }, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
          <Chip label={`#${item.item_no}`} size="small" color="primary" variant="outlined" />
          <Typography variant="subtitle2" fontWeight={600} noWrap sx={{ flex: 1 }}>
            {item.hs_code || '—'} {description ? `— ${description.slice(0, 60)}` : ''}
          </Typography>
          <Chip
            label={`ТС: ${num(item.customs_value_national)} ₽`}
            size="small"
            color="success"
            variant="filled"
            sx={{ fontWeight: 700 }}
          />
        </Box>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0 }}>
        {/* Основа (графы 11–12) */}
        <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
          Основа расчёта
        </Typography>
        <Grid container spacing={1} sx={{ mb: 1.5 }}>
          <Grid item xs={6} md={3}>
            <TextField
              size="small" fullWidth label="Цена в валюте счёта (11а.1)"
              value={item.invoice_price_foreign ?? ''}
              onChange={(e) => handleChange('invoice_price_foreign', e.target.value)}
              type="number" InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={6} md={3}>
            <TextField
              size="small" fullWidth label="Цена в нац. валюте (11а.2)"
              value={item.invoice_price_national ?? ''}
              onChange={(e) => handleChange('invoice_price_national', e.target.value)}
              type="number" InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={6} md={3}>
            <TextField
              size="small" fullWidth label="Косвенные платежи (11б)"
              value={item.indirect_payments ?? 0}
              onChange={(e) => handleChange('indirect_payments', e.target.value)}
              type="number" InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={6} md={3}>
            <TextField
              size="small" fullWidth label="Итого основа (12)"
              value={num(item.base_total)}
              InputProps={{ readOnly: true }}
              InputLabelProps={{ shrink: true }}
              sx={{ '& .MuiInputBase-root': { bgcolor: 'action.hover' } }}
            />
          </Grid>
        </Grid>

        <Divider sx={{ my: 1 }} />

        {/* Дополнительные начисления (графы 13–19) */}
        <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
          Дополнительные начисления (графы 13–19)
        </Typography>
        <Grid container spacing={1} sx={{ mb: 1 }}>
          {ADDITION_FIELDS.map(({ key, label, graph }) => (
            <Grid item xs={6} md={3} key={key}>
              <TextField
                size="small" fullWidth label={`${label} (${graph})`}
                value={item[key] ?? 0}
                onChange={(e) => handleChange(key, e.target.value)}
                type="number" InputLabelProps={{ shrink: true }}
              />
            </Grid>
          ))}
          <Grid item xs={6} md={3}>
            <TextField
              size="small" fullWidth label="Итого начислений (20)"
              value={num(item.additions_total)}
              InputProps={{ readOnly: true }}
              InputLabelProps={{ shrink: true }}
              sx={{ '& .MuiInputBase-root': { bgcolor: 'action.hover' } }}
            />
          </Grid>
        </Grid>

        <Divider sx={{ my: 1 }} />

        {/* Вычеты (графы 21–23) */}
        <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
          Вычеты (графы 21–23)
        </Typography>
        <Grid container spacing={1} sx={{ mb: 1 }}>
          {DEDUCTION_FIELDS.map(({ key, label, graph }) => (
            <Grid item xs={6} md={3} key={key}>
              <TextField
                size="small" fullWidth label={`${label} (${graph})`}
                value={item[key] ?? 0}
                onChange={(e) => handleChange(key, e.target.value)}
                type="number" InputLabelProps={{ shrink: true }}
              />
            </Grid>
          ))}
          <Grid item xs={6} md={3}>
            <TextField
              size="small" fullWidth label="Итого вычетов (24)"
              value={num(item.deductions_total)}
              InputProps={{ readOnly: true }}
              InputLabelProps={{ shrink: true }}
              sx={{ '& .MuiInputBase-root': { bgcolor: 'action.hover' } }}
            />
          </Grid>
        </Grid>

        <Divider sx={{ my: 1 }} />

        {/* Итог (графа 25) */}
        <Grid container spacing={1}>
          <Grid item xs={6}>
            <Box sx={{ p: 1.5, bgcolor: 'success.50', borderRadius: 1, border: '1px solid', borderColor: 'success.200' }}>
              <Typography variant="caption" color="text.secondary">Таможенная стоимость, руб (25а)</Typography>
              <Typography variant="h6" fontWeight={700} color="success.dark">
                {num(item.customs_value_national)} ₽
              </Typography>
              <Typography variant="caption" color="text.disabled">= гр.12 + гр.20 – гр.24</Typography>
            </Box>
          </Grid>
          <Grid item xs={6}>
            <Box sx={{ p: 1.5, bgcolor: 'grey.50', borderRadius: 1, border: '1px solid', borderColor: 'grey.300' }}>
              <Typography variant="caption" color="text.secondary">Таможенная стоимость, USD (25б)</Typography>
              <Typography variant="h6" fontWeight={700}>
                ${num(item.customs_value_usd)}
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </AccordionDetails>
    </Accordion>
  );
};

export default DtsItemCard;
