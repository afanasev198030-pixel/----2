import { Box, Typography } from '@mui/material';
import {
  AccessTime as ClockIcon,
  Inventory2Outlined as PackageIcon,
  VerifiedUser as SignedIcon,
  GppBad as UnsignedIcon,
  AutoAwesome as AiIcon,
  HourglassEmpty as ProcessingIcon,
  ErrorOutline as ErrorIcon,
  Warning as WarningIcon,
  ChevronRight as ChevronRightIcon,
  LocationOn as LocationIcon,
  Telegram as TelegramIcon,
  Email as EmailIcon,
  Edit as ManualIcon,
} from '@mui/icons-material';
import { Declaration } from '../types';
import dayjs from 'dayjs';

interface DeclarationCardProps {
  declaration: Declaration;
  onClick: (id: string) => void;
}

function timeAgo(dateStr?: string): string {
  if (!dateStr) return '';
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'только что';
  if (diffMins < 60) return `${diffMins} мин назад`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}ч назад`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}д назад`;
}

const processingConfig: Record<string, { label: string; color: string; bg: string; borderColor: string; icon: React.ReactNode }> = {
  not_started: { label: 'Не обработано', color: '#64748b', bg: '#f8fafc', borderColor: '#e2e8f0', icon: null },
  processing: { label: 'В обработке', color: '#2563eb', bg: '#eff6ff', borderColor: '#bfdbfe', icon: <ProcessingIcon sx={{ fontSize: 13 }} /> },
  auto_filled: { label: 'Автозаполнено', color: '#7c3aed', bg: '#f5f3ff', borderColor: '#ddd6fe', icon: <AiIcon sx={{ fontSize: 13 }} /> },
  processing_error: { label: 'Ошибка', color: '#dc2626', bg: '#fef2f2', borderColor: '#fecaca', icon: <ErrorIcon sx={{ fontSize: 13 }} /> },
};

const statusBorderColors: Record<string, string> = {
  new: '#bfdbfe',
  requires_attention: '#fde68a',
  ready_to_send: '#a7f3d0',
  sent: '#e2e8f0',
};

const statusAccentColors: Record<string, string> = {
  new: '#3b82f6',
  requires_attention: '#f59e0b',
  ready_to_send: '#10b981',
  sent: '#94a3b8',
};

const SourceIcon = ({ source }: { source?: string }) => {
  const sx = { fontSize: 12, color: '#94a3b8' };
  if (source === 'telegram') return <TelegramIcon sx={sx} />;
  if (source === 'email') return <EmailIcon sx={sx} />;
  return <ManualIcon sx={sx} />;
};

const DeclarationCard = ({ declaration: d, onClick }: DeclarationCardProps) => {
  const proc = processingConfig[d.processing_status || 'not_started'] || processingConfig.not_started;
  const isNew = d.status === 'new';
  const needsAttention = d.status === 'requires_attention';
  const showSignature = d.status === 'ready_to_send' || d.status === 'sent';
  const isSigned = d.signature_status === 'signed';
  const issueCount = d.ai_issues?.filter(i => !i.resolved)?.length || 0;

  return (
    <Box
      onClick={() => onClick(d.id)}
      sx={{
        position: 'relative',
        width: '100%',
        textAlign: 'left',
        borderRadius: '14px',
        border: '1px solid',
        borderColor: statusBorderColors[d.status] || '#e2e8f0',
        bgcolor: d.status === 'sent' ? '#fafafa' : '#fff',
        transition: 'all 0.2s ease',
        cursor: 'pointer',
        '&:hover': {
          borderColor: '#cbd5e1',
          boxShadow: '0 4px 12px rgba(0,0,0,0.06)',
          '& .card-chevron': { opacity: 1 },
        },
      }}
    >
      {(isNew || needsAttention) && (
        <Box
          sx={{
            position: 'absolute',
            left: 0,
            top: 12,
            bottom: 12,
            width: 3,
            borderRadius: '0 4px 4px 0',
            bgcolor: statusAccentColors[d.status],
          }}
        />
      )}

      <Box sx={{ p: 1.75 }}>
        {/* Top: ID + time */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography sx={{ fontSize: 13, fontWeight: 600, color: '#0f172a', letterSpacing: '-0.01em' }}>
            {d.number_internal || d.id.slice(0, 8).toUpperCase()}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <ClockIcon sx={{ fontSize: 11, color: '#94a3b8' }} />
            <Typography sx={{ fontSize: 10, color: '#94a3b8' }}>
              {timeAgo(d.updated_at || d.created_at)}
            </Typography>
          </Box>
        </Box>

        {/* Client + type */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.25 }}>
          <Typography sx={{ fontSize: 12, color: '#475569' }}>
            {d.type_code || 'IM40'}
          </Typography>
          {d.country_destination_code && (
            <>
              <Typography sx={{ color: '#cbd5e1', fontSize: 10 }}>·</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                <LocationIcon sx={{ fontSize: 11, color: '#94a3b8' }} />
                <Typography sx={{ fontSize: 10, color: '#94a3b8' }}>
                  {d.country_destination_code}
                </Typography>
              </Box>
            </>
          )}
        </Box>

        {/* Badges row */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap', mb: 1.25 }}>
          {proc.label && (
            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.5,
                px: 1,
                py: 0.375,
                borderRadius: '6px',
                fontSize: 10,
                fontWeight: 500,
                color: proc.color,
                bgcolor: proc.bg,
                border: `1px solid ${proc.borderColor}`,
              }}
            >
              {proc.icon}
              {proc.label}
            </Box>
          )}
          {showSignature && (
            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.5,
                px: 1,
                py: 0.375,
                borderRadius: '6px',
                fontSize: 10,
                fontWeight: 500,
                color: isSigned ? '#059669' : '#94a3b8',
                bgcolor: isSigned ? '#ecfdf5' : '#f8fafc',
                border: `1px solid ${isSigned ? '#a7f3d0' : '#e2e8f0'}`,
              }}
            >
              {isSigned ? <SignedIcon sx={{ fontSize: 13 }} /> : <UnsignedIcon sx={{ fontSize: 13 }} />}
              {isSigned ? 'Подписана' : 'Не подписана'}
            </Box>
          )}
        </Box>

        {/* Issues warning */}
        {issueCount > 0 && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.75,
              px: 1,
              py: 0.75,
              borderRadius: '8px',
              bgcolor: '#fffbeb',
              border: '1px solid #fde68a40',
              fontSize: 11,
              fontWeight: 500,
              color: '#b45309',
              mb: 1.25,
            }}
          >
            <WarningIcon sx={{ fontSize: 14, flexShrink: 0 }} />
            {issueCount} {issueCount === 1 ? 'замечание' : issueCount < 5 ? 'замечания' : 'замечаний'}
          </Box>
        )}

        {/* Footer meta */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            pt: 1.25,
            borderTop: '1px solid #f1f5f9',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
            {(d.total_items_count ?? 0) > 0 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <PackageIcon sx={{ fontSize: 13, color: '#94a3b8' }} />
                <Typography sx={{ fontSize: 10, color: '#94a3b8', fontVariantNumeric: 'tabular-nums' }}>
                  {d.total_items_count} {(d.total_items_count || 0) === 1 ? 'товар' : (d.total_items_count || 0) < 5 ? 'товара' : 'товаров'}
                </Typography>
              </Box>
            )}
            {d.total_invoice_value != null && (
              <Typography sx={{ fontSize: 11, fontWeight: 500, color: '#64748b', fontVariantNumeric: 'tabular-nums' }}>
                {d.currency_code || '₽'} {Number(d.total_invoice_value).toLocaleString('ru-RU')}
              </Typography>
            )}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SourceIcon source={undefined} />
            <ChevronRightIcon
              className="card-chevron"
              sx={{ fontSize: 16, color: '#cbd5e1', opacity: 0, transition: 'opacity 0.2s' }}
            />
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default DeclarationCard;
