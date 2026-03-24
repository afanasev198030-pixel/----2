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

const statusConfig: Record<string, { label: string; bg: string; color: string; icon?: React.ReactElement }> = {
  new: {
    label: 'Новая',
    bg: '#f5f5f5',
    color: '#616161',
    icon: <EditIcon sx={{ fontSize: 14 }} />,
  },
  requires_attention: {
    label: 'Требует внимания',
    bg: '#fff3e0',
    color: '#e65100',
    icon: <WarningIcon sx={{ fontSize: 14 }} />,
  },
  ready_to_send: {
    label: 'Готово к отправке',
    bg: '#e8f5e9',
    color: '#1b5e20',
    icon: <CheckIcon sx={{ fontSize: 14 }} />,
  },
  sent: {
    label: 'Отправлена',
    bg: '#e1f5fe',
    color: '#0277bd',
    icon: <SendIcon sx={{ fontSize: 14 }} />,
  },
};

const StatusChip = ({ status }: StatusChipProps) => {
  const config = statusConfig[status] || { label: status, bg: '#f5f5f5', color: '#616161' };

  return (
    <Chip
      label={config.label}
      icon={config.icon}
      size="small"
      sx={{
        backgroundColor: config.bg,
        color: config.color,
        fontWeight: 500,
        fontSize: 12,
        borderRadius: '16px',
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
