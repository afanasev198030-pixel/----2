import { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, IconButton, Tooltip } from '@mui/material';
import { ArrowBack as ArrowBackIcon } from '@mui/icons-material';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  backTo?: string;
  actions?: ReactNode;
  statusBadge?: ReactNode;
}

const PageHeader = ({ title, subtitle, backTo, actions, statusBadge }: PageHeaderProps) => {
  const navigate = useNavigate();

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        py: 1.5,
        px: 0,
        minHeight: 48,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        {backTo && (
          <Tooltip title="Назад">
            <IconButton
              onClick={() => navigate(backTo)}
              size="small"
              sx={{
                width: 32,
                height: 32,
                bgcolor: '#f1f5f9',
                '&:hover': { bgcolor: '#e2e8f0' },
              }}
            >
              <ArrowBackIcon sx={{ fontSize: 18, color: '#64748b' }} />
            </IconButton>
          </Tooltip>
        )}
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Typography
              sx={{
                fontSize: 18,
                fontWeight: 700,
                color: 'text.primary',
                letterSpacing: '-0.02em',
              }}
            >
              {title}
            </Typography>
            {statusBadge}
          </Box>
          {subtitle && (
            <Typography sx={{ fontSize: 12, color: 'text.secondary', mt: 0.25 }}>
              {subtitle}
            </Typography>
          )}
        </Box>
      </Box>
      {actions && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {actions}
        </Box>
      )}
    </Box>
  );
};

export default PageHeader;
