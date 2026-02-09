import { useState, useEffect } from 'react';
import { Paper, Typography, Box, Chip, Divider, CircularProgress } from '@mui/material';
import { History as HistoryIcon, Edit, Add, AutoAwesome, CheckCircle } from '@mui/icons-material';
import client from '../api/client';
import dayjs from 'dayjs';

interface LogEntry {
  id: string;
  action: string;
  old_value?: any;
  new_value?: any;
  created_at: string;
  user_id?: string;
}

interface HistoryPanelProps {
  declarationId: string;
}

const ACTION_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  create: { label: 'Создана', color: '#4caf50', icon: <Add sx={{ fontSize: 14 }} /> },
  update: { label: 'Обновлена', color: '#2196f3', icon: <Edit sx={{ fontSize: 14 }} /> },
  apply_parsed: { label: 'AI заполнение', color: '#9c27b0', icon: <AutoAwesome sx={{ fontSize: 14 }} /> },
  status_change: { label: 'Смена статуса', color: '#ff9800', icon: <CheckCircle sx={{ fontSize: 14 }} /> },
  duplicate: { label: 'Дублирована', color: '#607d8b', icon: <Add sx={{ fontSize: 14 }} /> },
};

const HistoryPanel = ({ declarationId }: HistoryPanelProps) => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        // Logs are in declaration_logs table, fetch via a simple endpoint
        // For now we use the declaration endpoint which includes logs indirectly
        const resp = await client.get(`/declarations/${declarationId}`);
        // Try to get logs from a dedicated endpoint or from declaration data
        try {
          const logsResp = await client.get(`/declarations/${declarationId}/logs`);
          setLogs(Array.isArray(logsResp.data) ? logsResp.data : []);
        } catch {
          // If no logs endpoint, construct from declaration data
          setLogs([{
            id: '1',
            action: 'create',
            created_at: resp.data.created_at,
            new_value: { type_code: resp.data.type_code },
          }]);
        }
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    };
    if (declarationId) load();
  }, [declarationId]);

  if (loading) return <CircularProgress size={20} />;

  return (
    <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <HistoryIcon fontSize="small" color="action" />
        <Typography variant="subtitle2" fontWeight={600}>История изменений</Typography>
        <Chip label={logs.length} size="small" />
      </Box>

      {logs.length === 0 && (
        <Typography variant="body2" color="text.secondary">Нет записей</Typography>
      )}

      {logs.map((log, idx) => {
        const config = ACTION_CONFIG[log.action] || { label: log.action, color: '#999', icon: <Edit sx={{ fontSize: 14 }} /> };
        return (
          <Box key={log.id || idx} sx={{ display: 'flex', gap: 1.5, mb: 1.5, pb: 1.5, borderBottom: idx < logs.length - 1 ? '1px solid #eee' : 'none' }}>
            <Box sx={{ width: 24, height: 24, borderRadius: '50%', bgcolor: config.color, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', flexShrink: 0 }}>
              {config.icon}
            </Box>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="body2" fontWeight={600}>{config.label}</Typography>
              {log.new_value && typeof log.new_value === 'object' && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  {Object.entries(log.new_value).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join(' | ')}
                </Typography>
              )}
              <Typography variant="caption" color="text.disabled">
                {dayjs(log.created_at).format('DD.MM.YYYY HH:mm')}
              </Typography>
            </Box>
          </Box>
        );
      })}
    </Paper>
  );
};

export default HistoryPanel;
