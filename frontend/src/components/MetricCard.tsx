import { ReactNode } from 'react';
import { Box, Typography } from '@mui/material';
import { TrendingUp, TrendingDown, TrendingFlat } from '@mui/icons-material';

interface MetricCardProps {
  icon: ReactNode;
  label: string;
  value: number;
  accentColor: string;
  iconBg: string;
  trend?: 'up' | 'down' | 'neutral';
  trendLabel?: string;
  onClick?: () => void;
}

const trendColors = {
  up: '#059669',
  down: '#dc2626',
  neutral: '#94a3b8',
};

const TrendIcon = ({ trend }: { trend: 'up' | 'down' | 'neutral' }) => {
  const sx = { fontSize: 14, color: trendColors[trend] };
  if (trend === 'up') return <TrendingUp sx={sx} />;
  if (trend === 'down') return <TrendingDown sx={sx} />;
  return <TrendingFlat sx={sx} />;
};

const MetricCard = ({ icon, label, value, accentColor, iconBg, trend, trendLabel, onClick }: MetricCardProps) => (
  <Box
    onClick={onClick}
    sx={{
      position: 'relative',
      overflow: 'hidden',
      borderRadius: '14px',
      border: '1px solid',
      borderColor: accentColor,
      bgcolor: 'background.paper',
      p: 2,
      transition: 'box-shadow 0.2s ease',
      cursor: onClick ? 'pointer' : 'default',
      '&:hover': onClick ? {
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      } : {},
    }}
  >
    <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
      <Box>
        <Typography
          sx={{ fontSize: 11, color: 'text.secondary', fontWeight: 500, mb: 0.5 }}
        >
          {label}
        </Typography>
        <Typography
          sx={{
            fontSize: 26,
            fontWeight: 700,
            color: 'text.primary',
            lineHeight: 1.1,
            fontVariantNumeric: 'tabular-nums',
            letterSpacing: '-0.02em',
          }}
        >
          {value}
        </Typography>
        {trendLabel && trend && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.75 }}>
            <TrendIcon trend={trend} />
            <Typography
              sx={{
                fontSize: 10,
                fontWeight: 500,
                color: trendColors[trend],
              }}
            >
              {trendLabel}
            </Typography>
          </Box>
        )}
      </Box>
      <Box
        sx={{
          width: 36,
          height: 36,
          borderRadius: '10px',
          bgcolor: iconBg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {icon}
      </Box>
    </Box>
  </Box>
);

export default MetricCard;
