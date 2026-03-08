import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Box, Typography, Paper, Chip, Alert, Tooltip,
  List, ListItem, ListItemText, ListItemIcon, Divider, Collapse,
} from '@mui/material';
import {
  Psychology as AiIcon,
  CheckCircle as OkIcon,
  Warning as WarnIcon,
  Error as ErrIcon,
  History as HistoryIcon,
  Source as SourceIcon,
  TrendingUp as ConfidenceIcon,
} from '@mui/icons-material';
import client from '../api/client';

interface AiExplainPanelProps {
  declaration: any;
  items: any[];
}

const SEVERITY_ICON: Record<string, any> = {
  error: <ErrIcon fontSize="small" color="error" />,
  warning: <WarnIcon fontSize="small" color="warning" />,
  info: <OkIcon fontSize="small" color="info" />,
};

const SOURCE_LABELS: Record<string, string> = {
  invoice: 'Инвойс',
  contract: 'Контракт',
  packing_list: 'Упаковочный лист',
  transport_doc: 'Транспортный док.',
  transport_invoice: 'Транспортный инвойс',
  application_statement: 'Заявка / поручение',
  specification: 'Спецификация',
  tech_description: 'Тех. описание',
  techop: 'Тех. описание',
  ai: 'AI',
  history: 'История',
  manual: 'Вручную',
  precedent: 'Прецедент',
};

export default function AiExplainPanel({ declaration, items }: AiExplainPanelProps) {
  const issues = declaration?.ai_issues || [];
  const evidenceMap = declaration?.evidence_map || {};
  const confidence = declaration?.ai_confidence;

  const { data: hsHistory = [] } = useQuery({
    queryKey: ['hs-history-panel'],
    queryFn: () => client.get('/hs-history', { params: { limit: 10 } }).then(r => r.data),
    staleTime: 60_000,
  });

  const blockingIssues = useMemo(() => issues.filter((i: any) => i.blocking), [issues]);
  const warningIssues = useMemo(() => issues.filter((i: any) => !i.blocking), [issues]);

  const evidenceFields = useMemo(() => {
    return Object.entries(evidenceMap).map(([field, info]: [string, any]) => ({
      field,
      source: info?.source || 'unknown',
      confidence: info?.confidence,
      rawValue: info?.raw_value,
    }));
  }, [evidenceMap]);

  const hasContent = issues.length > 0 || evidenceFields.length > 0 || confidence || hsHistory.length > 0;

  if (!hasContent) return null;

  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <AiIcon color="primary" fontSize="small" />
        <Typography variant="subtitle2" fontWeight={700}>Источники AI и история ТН ВЭД</Typography>
        {confidence && (
          <Chip
            icon={<ConfidenceIcon />}
            label={`${Math.round(Number(confidence) * 100)}%`}
            size="small"
            color={Number(confidence) > 0.8 ? 'success' : Number(confidence) > 0.5 ? 'warning' : 'error'}
          />
        )}
      </Box>

      {/* Blocking issues */}
      {blockingIssues.length > 0 && (
        <Alert severity="error" sx={{ mb: 1, py: 0.5 }}>
          <Typography variant="caption" fontWeight={700}>
            {blockingIssues.length} блокирующих проблем — отправка невозможна
          </Typography>
          {blockingIssues.map((issue: any, i: number) => (
            <Typography key={i} variant="caption" display="block" sx={{ ml: 1 }}>
              {issue.field && <Chip label={issue.field} size="small" sx={{ mr: 0.5, height: 16, fontSize: 10 }} />}
              {issue.message}
            </Typography>
          ))}
        </Alert>
      )}

      {/* Warning issues */}
      {warningIssues.length > 0 && (
        <Alert severity="warning" sx={{ mb: 1, py: 0.5 }}>
          <Typography variant="caption" fontWeight={700}>
            {warningIssues.length} предупреждений
          </Typography>
          {warningIssues.slice(0, 5).map((issue: any, i: number) => (
            <Typography key={i} variant="caption" display="block" sx={{ ml: 1 }}>
              {issue.message}
            </Typography>
          ))}
        </Alert>
      )}

      {/* Evidence map */}
      {evidenceFields.length > 0 && (
        <Box sx={{ mb: 1 }}>
          <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ mb: 0.5, display: 'block' }}>
            <SourceIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'text-bottom' }} />
            Источники данных
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {evidenceFields.slice(0, 12).map((ev) => (
              <Tooltip key={ev.field} title={ev.rawValue ? `Исходное: ${ev.rawValue}` : ev.field}>
                <Chip
                  label={`${ev.field}: ${SOURCE_LABELS[ev.source] || ev.source}${ev.confidence ? ` ${Math.round(ev.confidence * 100)}%` : ''}`}
                  size="small"
                  variant="outlined"
                  sx={{ fontSize: 10, height: 22 }}
                />
              </Tooltip>
            ))}
          </Box>
        </Box>
      )}

      {/* HS code history */}
      {hsHistory.length > 0 && (
        <Box>
          <Divider sx={{ my: 1 }} />
          <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ mb: 0.5, display: 'block' }}>
            <HistoryIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'text-bottom' }} />
            История кодов ТН ВЭД ({hsHistory.length})
          </Typography>
          <List dense disablePadding>
            {hsHistory.slice(0, 5).map((h: any) => (
              <ListItem key={h.id} disablePadding sx={{ py: 0.3 }}>
                <ListItemIcon sx={{ minWidth: 28 }}>
                  <Chip label={h.usage_count} size="small" sx={{ fontSize: 10, height: 18, minWidth: 24 }}
                    color={h.usage_count > 3 ? 'success' : 'default'} />
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                      <Typography variant="caption" fontFamily="monospace" fontWeight={700}>{h.hs_code}</Typography>
                      {h.counterparty_name && (
                        <Typography variant="caption" color="text.secondary">({h.counterparty_name})</Typography>
                      )}
                    </Box>
                  }
                  secondary={<Typography variant="caption" color="text.secondary" noWrap>{h.description}</Typography>}
                />
              </ListItem>
            ))}
          </List>
        </Box>
      )}
    </Paper>
  );
}
