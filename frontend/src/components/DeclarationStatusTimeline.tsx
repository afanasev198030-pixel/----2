import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Paper, Step, StepLabel, Stepper, Typography } from '@mui/material';
import dayjs from 'dayjs';
import { getDeclarationStatusHistory } from '../api/declarations';
import StatusChip from './StatusChip';
import { Declaration, DeclarationStatus, DeclarationStatusHistoryEntry } from '../types';

const MAIN_FLOW: DeclarationStatus[] = [
  'new',
  'requires_attention',
  'ready_to_send',
  'sent',
];

const STATUS_LABELS: Record<string, string> = {
  new: 'Новая',
  requires_attention: 'Требует внимания',
  ready_to_send: 'Готово к отправке',
  sent: 'Отправлена',
};

const getStatusLabel = (status?: string | null): string => {
  if (!status) return 'Неизвестно';
  return STATUS_LABELS[status] || status;
};

const buildHistoryMap = (history: DeclarationStatusHistoryEntry[]): Map<string, DeclarationStatusHistoryEntry> => {
  const map = new Map<string, DeclarationStatusHistoryEntry>();
  history.forEach((entry) => {
    const statusCode = String(entry.status_code || '');
    if (statusCode && !map.has(statusCode)) {
      map.set(statusCode, entry);
    }
  });
  return map;
};

interface DeclarationStatusTimelineProps {
  declaration: Declaration;
}

export default function DeclarationStatusTimeline({ declaration }: DeclarationStatusTimelineProps) {
  const declarationId = declaration?.id;
  const currentStatus = declaration?.status;

  const { data: history = [], isLoading } = useQuery({
    queryKey: ['declaration-status-history', declarationId],
    queryFn: () => getDeclarationStatusHistory(declarationId),
    enabled: Boolean(declarationId),
    staleTime: 30_000,
  });

  const historyMap = useMemo(() => buildHistoryMap(history), [history]);

  const activeStep = useMemo(() => {
    const currentIndex = MAIN_FLOW.indexOf(currentStatus as DeclarationStatus);
    if (currentIndex >= 0) {
      return currentIndex;
    }

    const historicalIndices = history
      .map((entry) => MAIN_FLOW.indexOf(entry.status_code as DeclarationStatus))
      .filter((index) => index >= 0);

    return historicalIndices.length > 0 ? Math.max(...historicalIndices) : 0;
  }, [currentStatus, history]);

  const lastEvent = history.length > 0 ? history[history.length - 1] : null;

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 1.5 }}>
        <Typography variant="subtitle2" fontWeight={700}>Статус кейса</Typography>
        <StatusChip status={currentStatus} />
      </Box>

      <Stepper activeStep={activeStep} orientation="vertical" sx={{ mb: 0.5 }}>
        {MAIN_FLOW.map((status, index) => {
          const statusEvent = historyMap.get(status);
          const isCurrent = status === currentStatus;
          const isCompleted = index < activeStep || (!!statusEvent && !isCurrent);

          return (
            <Step key={status} completed={isCompleted}>
              <StepLabel
                optional={statusEvent?.created_at ? (
                  <Typography variant="caption" color="text.secondary">
                    {dayjs(statusEvent.created_at).format('DD.MM.YYYY HH:mm')}
                  </Typography>
                ) : undefined}
              >
                <Typography variant="body2" fontWeight={isCurrent ? 700 : 500}>
                  {getStatusLabel(status)}
                </Typography>
              </StepLabel>
            </Step>
          );
        })}
      </Stepper>

      {lastEvent?.status_text && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
          Последнее событие: {lastEvent.status_text}
        </Typography>
      )}

      {isLoading && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          Загружается история статусов...
        </Typography>
      )}
    </Paper>
  );
}
