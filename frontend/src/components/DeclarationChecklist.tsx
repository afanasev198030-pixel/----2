import { useQuery } from '@tanstack/react-query';
import { Box, Typography, Checkbox, FormControlLabel, Paper, LinearProgress, Chip, Alert, Button } from '@mui/material';
import { CheckCircle, RadioButtonUnchecked, Warning } from '@mui/icons-material';
import { getPreSendCheck } from '../api/declarations';
import { PreSendResult } from '../types';

interface ChecklistProps {
  declaration: any;
  items: any[];
  formValues?: any;  // live form values (react-hook-form watch)
}

const CHECKS = [
  { key: 'type_code', label: '1. Тип декларации (графа 1)', field: 'type_code', critical: true },
  { key: 'sender', label: '2. Отправитель (графа 2)', field: 'sender_counterparty_id', critical: true },
  { key: 'receiver', label: '8. Получатель (графа 8)', field: 'receiver_counterparty_id', critical: true },
  { key: 'countries', label: '15-17. Страны (графы 15-17)', field: 'country_dispatch_code', critical: true },
  { key: 'incoterms', label: '20. Условия поставки (графа 20)', field: 'incoterms_code', critical: false },
  { key: 'currency', label: '22. Валюта и сумма (графа 22)', field: '_currency', critical: true },
  { key: 'items', label: '31-33. Товарные позиции заполнены', field: '_items', critical: true },
  { key: 'hs_code', label: '33. Код ТН ВЭД указан (10 знаков)', field: '_hs', critical: true },
  { key: 'weights', label: '35, 38. Вес брутто/нетто указан', field: '_weights', critical: true },
  { key: 'price', label: '42. Цена товара указана', field: '_price', critical: true },
];

const DeclarationChecklist = ({ declaration, items, formValues }: ChecklistProps) => {
  // Use formValues (live) with fallback to declaration (server)
  const d = { ...declaration, ...(formValues || {}) };
  const declarationId = declaration?.id;

  const { data: serverChecks, isLoading: serverChecksLoading } = useQuery<PreSendResult>({
    queryKey: ['pre-send-check', declarationId],
    queryFn: () => getPreSendCheck(declarationId),
    enabled: Boolean(declarationId),
    refetchOnWindowFocus: false,
  });

  const results = CHECKS.map((check) => {
    let passed = false;
    if (check.field === '_items') {
      passed = items.length > 0;
    } else if (check.field === '_hs') {
      passed = items.length > 0 && items.every((i: any) => i.hs_code && i.hs_code.length >= 10);
    } else if (check.field === '_currency') {
      passed = !!(d.currency_code && d.total_invoice_value);
    } else if (check.field === '_weights') {
      // Check both item-level AND declaration-level weights
      const hasItemWeights = items.length > 0 && items.every((i: any) => i.gross_weight && i.net_weight);
      const hasDeclWeights = !!(d.total_gross_weight && d.total_net_weight);
      passed = hasItemWeights || hasDeclWeights;
    } else if (check.field === '_price') {
      passed = items.length > 0 && items.every((i: any) => i.unit_price);
    } else {
      passed = !!d[check.field];
    }
    return { ...check, passed };
  });

  const passedCount = results.filter((r) => r.passed).length;
  const totalCount = results.length;
  const allPassed = passedCount === totalCount;
  const criticalFailed = results.filter((r) => !r.passed && r.critical);
  const serverBlocking = (serverChecks?.checks || []).filter((check) => check.blocking);
  const serverWarnings = (serverChecks?.checks || []).filter((check) => !check.blocking);

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="subtitle2" fontWeight={600}>Чек-лист перед отправкой</Typography>
        <Chip
          label={`${passedCount}/${totalCount}`}
          color={allPassed ? 'success' : criticalFailed.length > 0 ? 'error' : 'warning'}
          size="small"
        />
      </Box>
      <LinearProgress
        variant="determinate"
        value={(passedCount / totalCount) * 100}
        color={allPassed ? 'success' : 'warning'}
        sx={{ mb: 2, height: 6, borderRadius: 3 }}
      />
      {results.map((r, idx) => {
        const isFirstFailed = !r.passed && results.slice(0, idx).every((prev) => prev.passed);
        return (
          <FormControlLabel
            key={r.key}
            control={
              <Checkbox
                checked={r.passed}
                icon={<RadioButtonUnchecked fontSize="small" />}
                checkedIcon={<CheckCircle fontSize="small" color="success" />}
                disabled
                size="small"
              />
            }
            label={
              <Typography variant="body2" sx={{
                color: r.passed ? 'text.primary' : r.critical ? 'error.main' : 'warning.main',
                fontWeight: isFirstFailed ? 700 : 400,
              }}>
                {r.label} {r.critical && !r.passed && <Warning sx={{ fontSize: 14, verticalAlign: 'middle', ml: 0.5 }} color="error" />}
              </Typography>
            }
            sx={{
              display: 'block', my: 0, py: 0.3, px: 1, borderRadius: 1,
              bgcolor: isFirstFailed ? '#fff3e0' : 'transparent',
              borderLeft: isFirstFailed ? '3px solid #ff9800' : '3px solid transparent',
            }}
          />
        );
      })}
      {criticalFailed.length > 0 && (
        <Alert severity="error" sx={{ mt: 2 }}>
          Не заполнено {criticalFailed.length} обязательных полей. Декларация не может быть отправлена.
          <Box sx={{ mt: 1, fontSize: 12 }}>
            <b>Рекомендации:</b>
            <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
              {criticalFailed.some(r => r.key === 'sender' || r.key === 'receiver') && (
                <li>Загрузите инвойс (Invoice) — AI определит продавца и покупателя</li>
              )}
              {criticalFailed.some(r => r.key === 'countries') && (
                <li>Укажите страны вручную или загрузите инвойс с адресами</li>
              )}
              {criticalFailed.some(r => r.key === 'currency') && (
                <li>Выберите валюту в поле "Валюта (22)"</li>
              )}
              {criticalFailed.some(r => r.key === 'weights') && (
                <li>Загрузите упаковочный лист (Packing List) для заполнения весов</li>
              )}
              {criticalFailed.some(r => r.key === 'hs_code') && (
                <li>Нажмите "Подобрать код ТН ВЭД" для каждой позиции</li>
              )}
            </ul>
          </Box>
        </Alert>
      )}
      {serverChecksLoading && (
        <Alert severity="info" sx={{ mt: 2 }}>
          Загружается серверная проверка последней сохранённой версии декларации...
        </Alert>
      )}
      {!serverChecksLoading && (serverBlocking.length > 0 || serverWarnings.length > 0) && (
        <Alert severity={serverBlocking.length > 0 ? 'warning' : 'info'} sx={{ mt: 2 }}>
          <Typography variant="body2" fontWeight={700} sx={{ mb: 0.5 }}>
            Серверная проверка последней сохранённой версии
          </Typography>
          {serverBlocking.length > 0 && (
            <Typography variant="body2" sx={{ mb: 0.5 }}>
              Блокирующих проблем: {serverBlocking.length}
            </Typography>
          )}
          {serverWarnings.length > 0 && (
            <Typography variant="body2" sx={{ mb: 0.5 }}>
              Предупреждений: {serverWarnings.length}
            </Typography>
          )}
          <ul style={{ margin: '4px 0 0', paddingLeft: 20 }}>
            {[...serverBlocking, ...serverWarnings].slice(0, 6).map((check, idx) => (
              <li key={`${check.code}-${idx}`}>
                <Typography variant="body2">
                  {check.message}
                </Typography>
              </li>
            ))}
          </ul>
        </Alert>
      )}
      {allPassed && (
        <Alert severity="success" sx={{ mt: 2 }}>
          Все проверки пройдены. Декларация готова к отправке.
        </Alert>
      )}
    </Paper>
  );
};

export default DeclarationChecklist;
