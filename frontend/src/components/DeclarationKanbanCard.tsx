import { Card, CardActionArea, Box, Typography, Chip, Stack } from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import InventoryIcon from '@mui/icons-material/Inventory';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import GppBadIcon from '@mui/icons-material/GppBad';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import CallMadeIcon from '@mui/icons-material/CallMade';
import CallReceivedIcon from '@mui/icons-material/CallReceived';
import PlaceIcon from '@mui/icons-material/Place';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import type { Declaration } from '../types';

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  if (diffMs < 0) return 'только что';
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'только что';
  if (diffMins < 60) return `${diffMins} мин назад`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}ч назад`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}д назад`;
}

const PROCESSING_LABELS: Record<string, string> = {
  not_started: 'Не обработано',
  processing: 'В обработке',
  auto_filled: 'Автозаполнено',
  processing_error: 'Ошибка обработки',
};

const processingConfig: Record<string, { icon: React.ReactNode; color: string; bg: string; border: string }> = {
  not_started: { icon: <HelpOutlineIcon sx={{ fontSize: 13 }} />, color: '#64748b', bg: 'rgba(248,250,252,1)', border: 'rgba(226,232,240,0.8)' },
  processing: { icon: <HourglassEmptyIcon sx={{ fontSize: 13 }} />, color: '#2563eb', bg: 'rgba(239,246,255,0.8)', border: 'rgba(191,219,254,0.6)' },
  auto_filled: { icon: <AutoAwesomeIcon sx={{ fontSize: 13 }} />, color: '#7c3aed', bg: 'rgba(245,243,255,0.8)', border: 'rgba(221,214,254,0.6)' },
  processing_error: { icon: <ErrorOutlineIcon sx={{ fontSize: 13 }} />, color: '#dc2626', bg: 'rgba(254,242,242,0.8)', border: 'rgba(254,202,202,0.6)' },
};

interface DeclarationKanbanCardProps {
  declaration: Declaration;
  onClick: (id: string) => void;
}

const DeclarationKanbanCard = ({ declaration, onClick }: DeclarationKanbanCardProps) => {
  const d = declaration;
  const isNew = d.status === 'new';
  const needsAttention = d.status === 'requires_attention';
  const isSent = d.status === 'sent';
  const isReadyOrSent = d.status === 'ready_to_send' || d.status === 'sent';

  const procStatus = d.processing_status || 'not_started';
  const proc = processingConfig[procStatus] || processingConfig.not_started;
  const procLabel = PROCESSING_LABELS[procStatus] || procStatus;

  const sigStatus = d.signature_status || 'unsigned';
  const isSigned = sigStatus === 'signed';

  const issueCount = d.ai_issues?.length || 0;
  const goodsCount = d.total_items_count || 0;
  const isImport = d.type_code?.startsWith('IM');

  const accentColor = isNew ? '#3b82f6' : needsAttention ? '#f59e0b' : undefined;

  const displayId = d.number_internal || d.id.slice(0, 13);
  const displayTime = d.updated_at || d.created_at;

  const formattedValue = d.total_invoice_value
    ? `${d.currency_code || '₽'} ${Number(d.total_invoice_value).toLocaleString('ru-RU', { minimumFractionDigits: 0 })}`
    : null;

  return (
    <Card
      sx={{
        position: 'relative',
        bgcolor: isSent ? 'rgba(248,250,252,0.8)' : 'white',
        border: '1px solid',
        borderColor: isNew
          ? 'rgba(191,219,254,0.5)'
          : needsAttention
          ? 'rgba(253,230,138,0.5)'
          : 'rgba(226,232,240,0.6)',
        borderRadius: '14px',
        boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
        transition: 'all 0.2s',
        '&:hover': {
          borderColor: isNew
            ? 'rgba(147,197,253,0.7)'
            : needsAttention
            ? 'rgba(252,211,77,0.7)'
            : 'rgba(203,213,225,0.8)',
          boxShadow: isSent ? '0 1px 3px rgba(0,0,0,0.04)' : '0 2px 8px rgba(0,0,0,0.06)',
          '& .card-chevron': { opacity: 1 },
        },
        overflow: 'visible',
      }}
    >
      {accentColor && (
        <Box
          sx={{
            position: 'absolute',
            left: 0,
            top: 12,
            bottom: 12,
            width: 3,
            borderRadius: '0 4px 4px 0',
            bgcolor: accentColor,
          }}
        />
      )}

      <CardActionArea
        onClick={() => onClick(d.id)}
        sx={{ p: 1.75, display: 'block', '&:hover': { bgcolor: 'transparent' } }}
      >
        {/* Top: ID + time */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography sx={{ fontSize: 13, fontWeight: 600, letterSpacing: '-0.01em', color: '#0f172a' }}>
            {displayId}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: '#94a3b8' }}>
            <AccessTimeIcon sx={{ fontSize: 11 }} />
            <Typography sx={{ fontSize: 10 }}>{timeAgo(displayTime)}</Typography>
          </Box>
        </Box>

        {/* Type + destination */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.25 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
            {isImport ? (
              <CallReceivedIcon sx={{ fontSize: 12, color: '#1565c0' }} />
            ) : (
              <CallMadeIcon sx={{ fontSize: 12, color: '#e65100' }} />
            )}
            <Typography sx={{ fontSize: 12, color: '#475569', fontWeight: 500 }}>
              {isImport ? 'Импорт' : 'Экспорт'}
            </Typography>
          </Box>
          {d.country_destination_code && (
            <>
              <Typography sx={{ color: '#cbd5e1' }}>·</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25, color: '#94a3b8' }}>
                <PlaceIcon sx={{ fontSize: 11 }} />
                <Typography sx={{ fontSize: 10 }}>{d.country_destination_code}</Typography>
              </Box>
            </>
          )}
        </Box>

        {/* Badges */}
        <Stack direction="row" spacing={0.75} sx={{ mb: 1.25, flexWrap: 'wrap' }}>
          <Chip
            icon={proc.icon as React.ReactElement}
            label={procLabel}
            size="small"
            sx={{
              bgcolor: proc.bg,
              color: proc.color,
              border: `1px solid ${proc.border}`,
              fontSize: 10,
              fontWeight: 500,
              height: 22,
              '& .MuiChip-icon': { color: proc.color, ml: 0.5 },
              '& .MuiChip-label': { px: 0.75 },
            }}
          />
          {isReadyOrSent && (
            <Chip
              icon={
                isSigned ? (
                  <VerifiedUserIcon sx={{ fontSize: '13px !important' }} />
                ) : (
                  <GppBadIcon sx={{ fontSize: '13px !important' }} />
                )
              }
              label={isSigned ? 'Подписана' : 'Не подписана'}
              size="small"
              sx={{
                bgcolor: isSigned ? 'rgba(236,253,245,0.8)' : 'rgba(248,250,252,1)',
                color: isSigned ? '#059669' : '#94a3b8',
                border: '1px solid',
                borderColor: isSigned ? 'rgba(167,243,208,0.6)' : 'rgba(226,232,240,0.8)',
                fontSize: 10,
                fontWeight: 500,
                height: 22,
                '& .MuiChip-icon': {
                  color: isSigned ? '#059669' : '#94a3b8',
                  ml: 0.5,
                },
                '& .MuiChip-label': { px: 0.75 },
              }}
            />
          )}
        </Stack>

        {/* Issues */}
        {issueCount > 0 && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.75,
              px: 1,
              py: 0.75,
              borderRadius: 2,
              bgcolor: 'rgba(255,251,235,0.8)',
              border: '1px solid rgba(253,230,138,0.4)',
              mb: 1.25,
            }}
          >
            <WarningAmberIcon sx={{ fontSize: 14, color: '#d97706' }} />
            <Typography sx={{ fontSize: 11, fontWeight: 500, color: '#b45309' }}>
              {issueCount} {issueCount === 1 ? 'замечание' : issueCount < 5 ? 'замечания' : 'замечаний'}
            </Typography>
          </Box>
        )}

        {/* Footer */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            pt: 1.25,
            borderTop: '1px solid rgba(241,245,249,0.8)',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
            {goodsCount > 0 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: '#94a3b8' }}>
                <InventoryIcon sx={{ fontSize: 13 }} />
                <Typography sx={{ fontSize: 10, fontVariantNumeric: 'tabular-nums' }}>
                  {goodsCount} {goodsCount === 1 ? 'товар' : goodsCount < 5 ? 'товара' : 'товаров'}
                </Typography>
              </Box>
            )}
            {formattedValue && (
              <Typography sx={{ fontSize: 11, fontWeight: 500, color: '#475569', fontVariantNumeric: 'tabular-nums' }}>
                {formattedValue}
              </Typography>
            )}
          </Box>
          <ChevronRightIcon
            className="card-chevron"
            sx={{ fontSize: 16, color: '#cbd5e1', opacity: 0, transition: 'opacity 0.15s' }}
          />
        </Box>
      </CardActionArea>
    </Card>
  );
};

export default DeclarationKanbanCard;
