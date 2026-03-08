import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Alert, Paper, Typography, Box, Chip, CircularProgress } from '@mui/material';
import { History as HistoryIcon, Edit, Add, AutoAwesome, CheckCircle, WarningAmber } from '@mui/icons-material';
import dayjs from 'dayjs';
import { getDeclarationLogs } from '../api/declarations';
import { DeclarationLogEntry } from '../types';

interface HistoryPanelProps {
  declarationId: string;
}

const STATUS_LABELS: Record<string, string> = {
  draft: 'Черновик',
  checking_lvl1: 'Проверка ур. 1',
  checking_lvl2: 'Проверка ур. 2',
  final_check: 'Финальная проверка',
  signed: 'Подписана',
  sent: 'Отправлена',
  registered: 'Зарегистрирована',
  docs_requested: 'Нужны документы',
  inspection: 'Досмотр',
  released: 'Выпущена',
  rejected: 'Отклонена',
};

const ACTION_CONFIG: Record<string, { label: string; color: string; icon: ReactNode }> = {
  create: { label: 'Создана', color: '#4caf50', icon: <Add sx={{ fontSize: 14 }} /> },
  update: { label: 'Обновлена', color: '#2196f3', icon: <Edit sx={{ fontSize: 14 }} /> },
  apply_parsed: { label: 'AI заполнение', color: '#9c27b0', icon: <AutoAwesome sx={{ fontSize: 14 }} /> },
  status_change: { label: 'Смена статуса', color: '#ff9800', icon: <CheckCircle sx={{ fontSize: 14 }} /> },
  duplicate: { label: 'Дублирована', color: '#607d8b', icon: <Add sx={{ fontSize: 14 }} /> },
  pre_send_gate_override: { label: 'Override pre-send', color: '#d32f2f', icon: <WarningAmber sx={{ fontSize: 14 }} /> },
};

const FIELD_LABELS: Record<string, string> = {
  type_code: 'Тип ДТ',
  status: 'Статус',
  currency_code: 'Валюта',
  total_invoice_value: 'Сумма инвойса',
  total_customs_value: 'Тамож. стоимость',
  exchange_rate: 'Курс',
  country_origin_code: 'Страна происх.',
  country_dispatch_code: 'Страна отправл.',
  country_destination_code: 'Страна назнач.',
  incoterms_code: 'Incoterms',
  total_gross_weight: 'Вес брутто',
  total_net_weight: 'Вес нетто',
  total_packages_count: 'Кол-во мест',
  deal_nature_code: 'Хар. сделки',
  transport_type_border: 'Транспорт',
  customs_office_code: 'Тамож. пост',
  delivery_place: 'Город поставки',
  forms_count: 'Кол-во бланков',
  number_internal: 'Номер',
  source: 'Источник',
  confidence: 'Точность AI',
  invoice_number: 'Инвойс №',
  total_amount: 'Сумма',
  items_created: 'Позиций создано',
};

const formatLogValue = (value: Record<string, unknown> | null | undefined): string => {
  if (!value || typeof value !== 'object') return '';
  return Object.entries(value)
    .filter(([_, v]) => v !== null && v !== undefined && v !== '')
    .slice(0, 4)
    .map(([k, v]) => `${FIELD_LABELS[k] || k}: ${v}`)
    .join(' | ');
};

const getStatusLabel = (status?: unknown): string => {
  if (typeof status !== 'string' || !status) return 'Неизвестно';
  return STATUS_LABELS[status] || status;
};

const buildLogSummary = (log: DeclarationLogEntry): string => {
  if (log.action === 'status_change') {
    const fromStatus = getStatusLabel(log.old_value?.status);
    const toStatus = getStatusLabel(log.new_value?.status);
    return `${fromStatus} -> ${toStatus}`;
  }

  if (log.action === 'pre_send_gate_override') {
    const reason = log.old_value?.reason;
    return typeof reason === 'string' && reason ? `Причина: ${reason}` : 'Блокировка pre-send была обойдена';
  }

  return formatLogValue(log.new_value);
};

const HistoryPanel = ({ declarationId }: HistoryPanelProps) => {
  const { data: logs = [], isLoading, isError } = useQuery({
    queryKey: ['declaration-logs', declarationId],
    queryFn: () => getDeclarationLogs(declarationId),
    enabled: Boolean(declarationId),
    staleTime: 15_000,
  });

  const visibleLogs = useMemo(() => logs.slice(0, 10), [logs]);

  if (isLoading) {
    return (
      <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <HistoryIcon fontSize="small" color="action" />
          <Typography variant="subtitle2" fontWeight={600}>История изменений</Typography>
        </Box>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
          <CircularProgress size={20} />
        </Box>
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <HistoryIcon fontSize="small" color="action" />
        <Typography variant="subtitle2" fontWeight={600}>История изменений</Typography>
        <Chip label={logs.length} size="small" />
      </Box>

      {isError && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Не удалось загрузить журнал изменений.
        </Alert>
      )}

      {logs.length === 0 && (
        <Typography variant="body2" color="text.secondary">Нет записей</Typography>
      )}

      {visibleLogs.map((log, idx) => {
        const config = ACTION_CONFIG[log.action] || { label: log.action, color: '#999', icon: <Edit sx={{ fontSize: 14 }} /> };
        return (
          <Box key={log.id || idx} sx={{ display: 'flex', gap: 1.5, mb: 1.5, pb: 1.5, borderBottom: idx < visibleLogs.length - 1 ? '1px solid #eee' : 'none' }}>
            <Box sx={{ width: 24, height: 24, borderRadius: '50%', bgcolor: config.color, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', flexShrink: 0 }}>
              {config.icon}
            </Box>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="body2" fontWeight={600}>{config.label}</Typography>
              {buildLogSummary(log) && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  {buildLogSummary(log)}
                </Typography>
              )}
              <Typography variant="caption" color="text.disabled">
                {log.created_at ? dayjs(log.created_at).format('DD.MM.YYYY HH:mm') : '—'}
              </Typography>
            </Box>
          </Box>
        );
      })}
    </Paper>
  );
};

export default HistoryPanel;
