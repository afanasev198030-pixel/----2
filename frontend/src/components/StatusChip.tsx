import Chip from '@mui/material/Chip';
import {
  Schedule as ClockIcon,
  CheckCircleOutline as CheckIcon,
  ErrorOutline as ErrorIcon,
  Send as SendIcon,
  Edit as EditIcon,
  Verified as VerifiedIcon,
  Search as SearchIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';

interface StatusChipProps {
  status: string;
}

const statusConfig: Record<string, { label: string; bg: string; color: string; border: string; icon?: React.ReactElement }> = {
  new: {
    label: 'Новая',
    bg: '#f1f5f9',
    color: '#475569',
    border: 'rgba(226,232,240,0.8)',
    icon: <EditIcon sx={{ fontSize: 14 }} />,
  },
  requires_attention: {
    label: 'Требует внимания',
    bg: 'rgba(255,251,235,0.8)',
    color: '#92400e',
    border: 'rgba(253,230,138,0.6)',
    icon: <WarningIcon sx={{ fontSize: 14 }} />,
  },
  ready_to_send: {
    label: 'Готово к отправке',
    bg: 'rgba(236,253,245,0.8)',
    color: '#065f46',
    border: 'rgba(167,243,208,0.6)',
    icon: <CheckIcon sx={{ fontSize: 14 }} />,
  },
  sent: {
    label: 'Отправлена',
    bg: '#eef2ff',
    color: '#3730a3',
    border: 'rgba(199,210,254,0.6)',
    icon: <SendIcon sx={{ fontSize: 14 }} />,
  },
  error: {
    label: 'Ошибка',
    bg: 'rgba(254,242,242,0.8)',
    color: '#991b1b',
    border: 'rgba(254,202,202,0.6)',
    icon: <ErrorIcon sx={{ fontSize: 14 }} />,
  },
  auto_filled: {
    label: 'Заполнена AI',
    bg: '#f5f3ff',
    color: '#5b21b6',
    border: 'rgba(196,181,253,0.5)',
    icon: <VerifiedIcon sx={{ fontSize: 14 }} />,
  },
};

const StatusChip = ({ status }: StatusChipProps) => {
  const config = statusConfig[status] || { label: status, bg: '#f1f5f9', color: '#475569', border: 'rgba(226,232,240,0.8)' };

  return (
    <Chip
      label={config.label}
      icon={config.icon}
      size="small"
      sx={{
        backgroundColor: config.bg,
        color: config.color,
        border: `1px solid ${config.border}`,
        fontWeight: 500,
        fontSize: 13,
        borderRadius: '8px',
        px: 0.5,
        '& .MuiChip-icon': {
          color: config.color,
          ml: '6px',
        },
      }}
    />
  );
};

export default StatusChip;
