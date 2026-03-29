import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Paper, Box, Typography, TextField, Grid, IconButton,
  Chip, Alert, Button, Divider, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
} from '@mui/material';
import {
  Save as SaveIcon,
  Delete as DeleteIcon,
  AutoAwesome as AiIcon,
} from '@mui/icons-material';
import { DeclarationItem } from '../types';
import { updateItem, deleteItem } from '../api/items';
import client from '../api/client';
import HSCodeSuggestions from './HSCodeSuggestions';
import RequirementsPanel from './RequirementsPanel';

interface ItemDocument {
  id: string;
  doc_kind_code: string;
  doc_number?: string;
  doc_date?: string;
  presenting_kind_code?: string;
}

interface ItemEditCardProps {
  item: DeclarationItem;
  declarationId: string;
  currencyCode?: string;
  onSaved: () => void;
  onDeleted: () => void;
}

type ItemFields = {
  commercial_name: string;
  description: string;
  manufacturer: string;
  trademark: string;
  model_name: string;
  article_number: string;
  hs_code: string;
  hs_code_letters: string;
  hs_code_extra: string;
  country_origin_code: string;
  country_origin_pref_code: string;
  gross_weight: string;
  net_weight: string;
  preference_code: string;
  procedure_code: string;
  prev_doc_ref: string;
  additional_unit_qty: string;
  additional_unit: string;
  unit_price: string;
  mos_method_code: string;
  customs_value_rub: string;
  statistical_value_usd: string;
  package_count: string;
  package_type: string;
  package_type_code: string;
  package_marks: string;
  additional_unit_code: string;
};

const toStr = (v: unknown): string =>
  v === null || v === undefined ? '' : String(v);

const initFields = (item: DeclarationItem): ItemFields => ({
  commercial_name: toStr(item.commercial_name),
  description: toStr(item.description),
  manufacturer: toStr(item.manufacturer),
  trademark: toStr(item.trademark),
  model_name: toStr(item.model_name),
  article_number: toStr(item.article_number),
  hs_code: toStr(item.hs_code),
  hs_code_letters: toStr(item.hs_code_letters),
  hs_code_extra: toStr(item.hs_code_extra),
  country_origin_code: toStr(item.country_origin_code),
  country_origin_pref_code: toStr(item.country_origin_pref_code),
  gross_weight: toStr(item.gross_weight),
  net_weight: toStr(item.net_weight),
  preference_code: toStr(item.preference_code),
  procedure_code: toStr(item.procedure_code),
  prev_doc_ref: toStr(item.prev_doc_ref),
  additional_unit_qty: toStr(item.additional_unit_qty),
  additional_unit: toStr(item.additional_unit),
  unit_price: toStr(item.unit_price),
  mos_method_code: toStr(item.mos_method_code),
  customs_value_rub: toStr(item.customs_value_rub),
  statistical_value_usd: toStr(item.statistical_value_usd),
  package_count: toStr(item.package_count),
  package_type: toStr(item.package_type),
  package_type_code: toStr(item.package_type_code),
  package_marks: toStr(item.package_marks),
  additional_unit_code: toStr(item.additional_unit_code),
});

const NUM_FIELDS: (keyof ItemFields)[] = [
  'gross_weight', 'net_weight', 'additional_unit_qty', 'unit_price',
  'customs_value_rub', 'statistical_value_usd',
];

const INT_FIELDS: (keyof ItemFields)[] = ['package_count'];

const sanitize = (fields: ItemFields): Partial<DeclarationItem> => {
  const result: Record<string, unknown> = {};
  for (const [key, val] of Object.entries(fields)) {
    if (NUM_FIELDS.includes(key as keyof ItemFields)) {
      const clean = val.replace(/\s/g, '').replace(',', '.');
      result[key] = clean === '' ? null : Number(clean);
    } else if (INT_FIELDS.includes(key as keyof ItemFields)) {
      result[key] = val === '' ? null : parseInt(val, 10) || null;
    } else {
      result[key] = val === '' ? null : val;
    }
  }
  return result as Partial<DeclarationItem>;
};

const ItemEditCard = ({ item, declarationId, currencyCode, onSaved, onDeleted }: ItemEditCardProps) => {
  const [fields, setFields] = useState<ItemFields>(() => initFields(item));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [driftDismissed, setDriftDismissed] = useState(false);
  const syncRef = useRef(item.updated_at);
  const [itemDocs, setItemDocs] = useState<ItemDocument[]>([]);

  useEffect(() => {
    client.get(`/declarations/${declarationId}/items/${item.id}/item-documents/`)
      .then((r) => setItemDocs(r.data))
      .catch(() => {});
  }, [declarationId, item.id]);

  useEffect(() => {
    if (item.updated_at !== syncRef.current) {
      setFields(initFields(item));
      syncRef.current = item.updated_at;
    }
  }, [item]);

  const isDirty = useCallback(() => {
    const original = initFields(item);
    return (Object.keys(original) as (keyof ItemFields)[]).some(
      (k) => fields[k] !== original[k],
    );
  }, [fields, item]);

  const set = useCallback((field: keyof ItemFields, value: string) => {
    setFields((prev) => ({ ...prev, [field]: value }));
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError('');
    try {
      const data = sanitize(fields);
      await updateItem(declarationId, item.id, data);
      syncRef.current = undefined;
      onSaved();
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  }, [fields, declarationId, item.id, onSaved]);

  const handleDelete = useCallback(async () => {
    try {
      await deleteItem(declarationId, item.id);
      onDeleted();
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Ошибка удаления');
    }
  }, [declarationId, item.id, onDeleted]);

  const handleHsCodeSelect = useCallback((code: string) => {
    setFields((prev) => ({ ...prev, hs_code: code }));
    updateItem(declarationId, item.id, { hs_code: code }).then(() => {
      syncRef.current = undefined;
      onSaved();
    });
  }, [declarationId, item.id, onSaved]);

  const lineTotal =
    fields.unit_price && fields.additional_unit_qty
      ? Number(fields.unit_price) * Number(fields.additional_unit_qty)
      : null;

  const dirty = isDirty();

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2, borderColor: !fields.hs_code ? 'error.main' : 'divider' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="subtitle2" fontWeight={700}>
          Позиция #{item.item_no}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {fields.hs_code
            ? <Chip label={`ТН ВЭД: ${fields.hs_code}`} color="success" size="small" sx={{ fontFamily: 'monospace', fontWeight: 700 }} />
            : <Chip label="Код не указан" color="error" size="small" />}
          <IconButton size="small" onClick={handleDelete}><DeleteIcon fontSize="small" /></IconButton>
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}

      {/* Main fields */}
      <Grid container spacing={1}>
        <Grid item xs={12} md={6}>
          <TextField size="small" fullWidth multiline maxRows={3}
            label="Коммерческое наименование (31)"
            value={fields.commercial_name}
            onChange={(e) => set('commercial_name', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={12} md={6}>
          <TextField size="small" fullWidth multiline maxRows={3}
            label="Описание товара (31)"
            value={fields.description}
            onChange={(e) => set('description', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>

        <Grid item xs={6} md={3}>
          <TextField size="small" fullWidth label="Производитель"
            value={fields.manufacturer}
            onChange={(e) => set('manufacturer', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={6} md={3}>
          <TextField size="small" fullWidth label="Торговая марка"
            value={fields.trademark}
            onChange={(e) => set('trademark', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={6} md={3}>
          <TextField size="small" fullWidth label="Модель"
            value={fields.model_name}
            onChange={(e) => set('model_name', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={6} md={3}>
          <TextField size="small" fullWidth label="Артикул"
            value={fields.article_number}
            onChange={(e) => set('article_number', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>

        <Grid item xs={6} md={2}>
          <TextField size="small" fullWidth
            label="Код ТН ВЭД (33)"
            value={fields.hs_code}
            onChange={(e) => set('hs_code', e.target.value.replace(/\D/g, '').slice(0, 10))}
            error={!fields.hs_code || fields.hs_code.length < 10}
            inputProps={{ style: { fontFamily: 'monospace', fontWeight: 700, fontSize: 14 }, maxLength: 10 }}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={3} md={1}>
          <TextField size="small" fullWidth label="33.2"
            value={fields.hs_code_letters}
            onChange={(e) => set('hs_code_letters', e.target.value)}
            inputProps={{ maxLength: 10 }}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={3} md={1}>
          <TextField size="small" fullWidth label="33.3"
            value={fields.hs_code_extra}
            onChange={(e) => set('hs_code_extra', e.target.value)}
            inputProps={{ maxLength: 4 }}
            InputLabelProps={{ shrink: true }} />
        </Grid>

        <Grid item xs={4} md={1.5}>
          <TextField size="small" fullWidth label="Страна (34)"
            value={fields.country_origin_code}
            onChange={(e) => set('country_origin_code', e.target.value.toUpperCase().slice(0, 2))}
            inputProps={{ maxLength: 2 }}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={4} md={1.5}>
          <TextField size="small" fullWidth label="Преф. (34b)"
            value={fields.country_origin_pref_code}
            onChange={(e) => set('country_origin_pref_code', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>

        <Grid item xs={4} md={2}>
          <TextField size="small" fullWidth label="Брутто, кг (35)"
            value={fields.gross_weight}
            onChange={(e) => set('gross_weight', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={4} md={2}>
          <TextField size="small" fullWidth label="Нетто, кг (38)"
            value={fields.net_weight}
            onChange={(e) => set('net_weight', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>

        <Grid item xs={4} md={1.5}>
          <TextField size="small" fullWidth label="Преференция (36)"
            value={fields.preference_code}
            onChange={(e) => set('preference_code', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={4} md={1.5}>
          <TextField size="small" fullWidth label="Процедура (37)"
            value={fields.procedure_code}
            onChange={(e) => set('procedure_code', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={4} md={3}>
          <TextField size="small" fullWidth label="Пред. документ (40)"
            value={fields.prev_doc_ref}
            onChange={(e) => set('prev_doc_ref', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>

        <Grid item xs={4} md={1.5}>
          <TextField size="small" fullWidth label="Кол-во (41)"
            value={fields.additional_unit_qty}
            onChange={(e) => set('additional_unit_qty', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={4} md={1.5}>
          <TextField size="small" fullWidth label="Ед. изм. (41)"
            value={fields.additional_unit}
            onChange={(e) => set('additional_unit', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={4} md={1.5}>
          <TextField size="small" fullWidth
            label={`Цена (${currencyCode || '?'})`}
            value={fields.unit_price}
            onChange={(e) => set('unit_price', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={4} md={1.5}>
          <TextField size="small" fullWidth label="Метод ТС (43)"
            value={fields.mos_method_code}
            onChange={(e) => set('mos_method_code', e.target.value)}
            inputProps={{ maxLength: 2 }}
            InputLabelProps={{ shrink: true }} />
        </Grid>

        <Grid item xs={4} md={1.5}>
          <TextField size="small" fullWidth label="Тамож. ст-ть руб (45)"
            value={fields.customs_value_rub}
            onChange={(e) => set('customs_value_rub', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={4} md={1.5}>
          <TextField size="small" fullWidth label="Стат. ст-ть USD (46)"
            value={fields.statistical_value_usd}
            onChange={(e) => set('statistical_value_usd', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={3} md={1}>
          <TextField size="small" fullWidth label="Мест"
            value={fields.package_count}
            onChange={(e) => set('package_count', e.target.value.replace(/\D/g, ''))}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={3} md={1.5}>
          <TextField size="small" fullWidth label="Вид упак."
            value={fields.package_type}
            onChange={(e) => set('package_type', e.target.value)}
            InputLabelProps={{ shrink: true }} />
        </Grid>
        <Grid item xs={6} md={1.5}>
          <Box sx={{ pt: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Сумма ({currencyCode || '?'})
            </Typography>
            <Typography variant="body2" fontWeight={600}>
              {lineTotal != null && !isNaN(lineTotal)
                ? lineTotal.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                : '—'}
            </Typography>
          </Box>
        </Grid>
      </Grid>

      {/* HS Code suggestions + Requirements */}
      <Divider sx={{ my: 1.5 }} />
      {!fields.hs_code && (
        <Alert severity="warning" sx={{ mb: 1 }} icon={<AiIcon />}>
          Нажмите «Подобрать» или введите код вручную.
        </Alert>
      )}
      {item.drift_status && !driftDismissed && (
        <Alert severity="warning" sx={{ mb: 1 }}>
          {item.drift_message || `Возможный drift: исторический код ${item.historical_hs_code || '—'} отличается от текущего ${item.hs_code || '—'}.`}
          <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
            <Button
              size="small"
              variant="outlined"
              onClick={() => {
                if (!item.historical_hs_code) return;
                handleHsCodeSelect(item.historical_hs_code);
              }}
            >
              Вернуть {item.historical_hs_code || 'исторический код'}
            </Button>
            <Button
              size="small"
              variant="contained"
              color="warning"
              onClick={() => setDriftDismissed(true)}
            >
              Оставить {fields.hs_code || 'текущий код'}
            </Button>
          </Box>
        </Alert>
      )}
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <HSCodeSuggestions
          description={fields.description || fields.commercial_name || ''}
          currentCode={fields.hs_code}
          declarationId={declarationId}
          onSelect={(code) => handleHsCodeSelect(code)}
        />
        <Button
          variant={dirty ? 'contained' : 'outlined'}
          size="small"
          startIcon={<SaveIcon />}
          onClick={handleSave}
          disabled={saving}
          color={dirty ? 'primary' : 'inherit'}
        >
          {saving ? 'Сохранение...' : dirty ? 'Сохранить позицию' : 'Сохранено'}
        </Button>
      </Box>
      {fields.hs_code && fields.hs_code.length >= 4 && (
        <RequirementsPanel hsCode={fields.hs_code} description={fields.description || fields.commercial_name || ''} />
      )}

      {itemDocs.length > 0 && (
        <>
          <Divider sx={{ my: 1.5 }} />
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            Документы (44)
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, py: 0.5 }}>Код</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 0.5 }}>Номер</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 0.5 }}>Дата</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 0.5 }}>Призн.</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {itemDocs.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell sx={{ py: 0.5, fontFamily: 'monospace' }}>{d.doc_kind_code}</TableCell>
                    <TableCell sx={{ py: 0.5 }}>{d.doc_number || '—'}</TableCell>
                    <TableCell sx={{ py: 0.5 }}>{d.doc_date || '—'}</TableCell>
                    <TableCell sx={{ py: 0.5 }}>{d.presenting_kind_code || '1'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
    </Paper>
  );
};

export default ItemEditCard;
