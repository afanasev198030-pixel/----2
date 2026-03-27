import { Box, Typography, Chip, Paper, LinearProgress, Alert } from '@mui/material';
import { Warning as WarningIcon, CheckCircle as OkIcon, Error as ErrorIcon } from '@mui/icons-material';

interface Risk {
  rule_code?: string;
  severity: string;
  message: string;
  recommendation?: string;
}

interface RiskPanelProps {
  riskScore: number;
  risks: Risk[];
  source?: string;
}

const RiskPanel = ({ riskScore, risks, source }: RiskPanelProps) => {
  const severity = riskScore <= 25 ? 'low' : riskScore <= 50 ? 'medium' : riskScore <= 75 ? 'high' : 'critical';
  const color = severity === 'low' ? '#059669' : severity === 'medium' ? '#d97706' : severity === 'high' ? '#dc2626' : '#991b1b';
  const label = severity === 'low' ? 'Низкий' : severity === 'medium' ? 'Средний' : severity === 'high' ? 'Высокий' : 'Критический';

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        {severity === 'low' ? <OkIcon sx={{ color }} /> : <WarningIcon sx={{ color }} />}
        <Box sx={{ flex: 1 }}>
          <Typography variant="subtitle2">Оценка рисков СУР</Typography>
          <LinearProgress
            variant="determinate"
            value={riskScore}
            sx={{ height: 8, borderRadius: 4, bgcolor: 'rgba(241,245,249,1)', '& .MuiLinearProgress-bar': { bgcolor: color } }}
          />
        </Box>
        <Chip label={`${riskScore}/100 — ${label}`} sx={{ bgcolor: color, color: '#fff', fontWeight: 700 }} />
      </Box>

      {risks.length === 0 && (
        <Alert severity="success" icon={<OkIcon />}>Серьёзных рисков не обнаружено</Alert>
      )}

      {risks.map((r, i) => (
        <Alert
          key={i}
          severity={r.severity === 'critical' ? 'error' : r.severity === 'high' ? 'warning' : 'info'}
          icon={r.severity === 'critical' ? <ErrorIcon /> : <WarningIcon />}
          sx={{ mb: 1 }}
        >
          <Typography variant="body2" fontWeight={600}>{r.message}</Typography>
          {r.recommendation && (
            <Typography variant="caption" color="text.secondary">{r.recommendation}</Typography>
          )}
        </Alert>
      ))}

      {source && <Typography variant="caption" color="text.secondary">Источник: {source}</Typography>}
    </Paper>
  );
};

export default RiskPanel;
