import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
import {
  CheckCircleOutline as CheckIcon,
  Send as SendIcon,
  Edit as EditIcon,
  Warning as WarningIcon,
  AutoAwesome as AiIcon,
  HourglassEmpty as ProcessingIcon,
  ErrorOutline as ErrorIcon,
  VerifiedUser as SignedIcon,
  GppBad as UnsignedIcon,
} from '@mui/icons-material';

type ChipVariant = 'status' | 'processing' | 'signature';

interface StatusChipProps {
  status: string;
  variant?: ChipVariant;
  size?: 'small' | 'medium';
}

interface ChipConfig {
  label: string;
  bg: string;
  color: string;
  borderColor: string;
  icon?: React.ReactElement;
}

const statusConfig: Record<string, ChipConfig> = {
  new: {
    label: 'Новая',
    bg: '#eff6ff',
    color: '#2563eb',
    borderColor: '#bfdbfe',
    icon: <EditIcon sx={{ fontSize: 13 }} />,
  },
  requires_attention: {
    label: 'Требует внимания',
    bg: '#fffbeb',
    color: '#d97706',
    borderColor: '#fde68a',
    icon: <WarningIcon sx={{ fontSize: 13 }} />,
  },
  ready_to_send: {
    label: 'Готово к отправке',
    bg: '#ecfdf5',
    color: '#059669',
    borderColor: '#a7f3d0',
    icon: <CheckIcon sx={{ fontSize: 13 }} />,
  },
  sent: {
    label: 'Отправлена',
    bg: '#f8fafc',
    color: '#64748b',
    borderColor: '#e2e8f0',
    icon: <SendIcon sx={{ fontSize: 13 }} />,
  },
};

const processingConfig: Record<string, ChipConfig> = {
  not_started: {
    label: 'Не обработано',
    bg: '#f8fafc',
    color: '#64748b',
    borderColor: '#e2e8f0',
  },
  processing: {
    label: 'В обработке',
    bg: '#eff6ff',
    color: '#2563eb',
    borderColor: '#bfdbfe',
    icon: <ProcessingIcon sx={{ fontSize: 13 }} />,
  },
  auto_filled: {
    label: 'Автозаполнено',
    bg: '#f5f3ff',
    color: '#7c3aed',
    borderColor: '#ddd6fe',
    icon: <AiIcon sx={{ fontSize: 13 }} />,
  },
  processing_error: {
    label: 'Ошибка обработки',
    bg: '#fef2f2',
    color: '#dc2626',
    borderColor: '#fecaca',
    icon: <ErrorIcon sx={{ fontSize: 13 }} />,
  },
};

const signatureConfig: Record<string, ChipConfig> = {
  unsigned: {
    label: 'Не подписана',
    bg: '#f8fafc',
    color: '#94a3b8',
    borderColor: '#e2e8f0',
    icon: <UnsignedIcon sx={{ fontSize: 13 }} />,
  },
  signed: {
    label: 'Подписана',
    bg: '#ecfdf5',
    color: '#059669',
    borderColor: '#a7f3d0',
    icon: <SignedIcon sx={{ fontSize: 13 }} />,
  },
};

const configMap: Record<ChipVariant, Record<string, ChipConfig>> = {
  status: statusConfig,
  processing: processingConfig,
  signature: signatureConfig,
};

const StatusChip = ({ status, variant = 'status', size = 'small' }: StatusChipProps) => {
  const configs = configMap[variant];
  const config = configs[status] || { label: status, bg: '#f8fafc', color: '#64748b', borderColor: '#e2e8f0' };

  return (
    <Chip
      label={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {config.icon}
          {config.label}
        </Box>
      }
      size={size}
      sx={{
        backgroundColor: config.bg,
        color: config.color,
        border: `1px solid ${config.borderColor}`,
        fontWeight: 500,
        fontSize: size === 'small' ? 10 : 11,
        borderRadius: '8px',
        height: size === 'small' ? 22 : 26,
        px: 0.25,
        '& .MuiChip-label': {
          px: 1,
        },
      }}
    />
  );
};

export default StatusChip;
