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
  draft: {
    label: 'Черновик',
    bg: '#f5f5f5',
    color: '#616161',
    icon: <EditIcon sx={{ fontSize: 14 }} />,
  },
  checking_lvl1: {
    label: 'Проверка ур.1',
    bg: '#e3f2fd',
    color: '#1565c0',
    icon: <ClockIcon sx={{ fontSize: 14 }} />,
  },
  checking_lvl2: {
    label: 'Проверка ур.2',
    bg: '#e3f2fd',
    color: '#1565c0',
    icon: <ClockIcon sx={{ fontSize: 14 }} />,
  },
  final_check: {
    label: 'Фин. проверка',
    bg: '#fff3e0',
    color: '#e65100',
    icon: <SearchIcon sx={{ fontSize: 14 }} />,
  },
  signed: {
    label: 'Подписана',
    bg: '#f3e5f5',
    color: '#7b1fa2',
    icon: <VerifiedIcon sx={{ fontSize: 14 }} />,
  },
  sent: {
    label: 'Отправлена',
    bg: '#e1f5fe',
    color: '#0277bd',
    icon: <SendIcon sx={{ fontSize: 14 }} />,
  },
  registered: {
    label: 'Зарегистрирована',
    bg: '#e0f2f1',
    color: '#00695c',
    icon: <CheckIcon sx={{ fontSize: 14 }} />,
  },
  released: {
    label: 'Выпущена',
    bg: '#e8f5e9',
    color: '#1b5e20',
    icon: <CheckIcon sx={{ fontSize: 14 }} />,
  },
  rejected: {
    label: 'Отклонена',
    bg: '#ffebee',
    color: '#c62828',
    icon: <ErrorIcon sx={{ fontSize: 14 }} />,
  },
  docs_requested: {
    label: 'Запрос документов',
    bg: '#fff8e1',
    color: '#f57f17',
    icon: <WarningIcon sx={{ fontSize: 14 }} />,
  },
  inspection: {
    label: 'Досмотр',
    bg: '#fbe9e7',
    color: '#bf360c',
    icon: <SearchIcon sx={{ fontSize: 14 }} />,
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
