import { Box, Typography } from '@mui/material';
import DeclarationCard from './DeclarationCard';
import { Declaration } from '../types';

interface KanbanViewProps {
  declarations: Declaration[];
  onClickDeclaration: (id: string) => void;
}

const COLUMNS = [
  {
    key: 'new',
    label: 'Новая',
    statuses: ['new'],
    dotColor: '#3b82f6',
    headerBg: 'rgba(239,246,255,0.6)',
    borderColor: 'rgba(191,219,254,0.4)',
    countBg: 'rgba(219,234,254,0.8)',
    countColor: '#1d4ed8',
  },
  {
    key: 'attention',
    label: 'Требует внимания',
    statuses: ['requires_attention'],
    dotColor: '#f59e0b',
    headerBg: 'rgba(255,251,235,0.6)',
    borderColor: 'rgba(253,230,138,0.4)',
    countBg: 'rgba(254,243,199,0.8)',
    countColor: '#b45309',
  },
  {
    key: 'ready',
    label: 'Готово к отправке',
    statuses: ['ready_to_send'],
    dotColor: '#10b981',
    headerBg: 'rgba(236,253,245,0.6)',
    borderColor: 'rgba(167,243,208,0.4)',
    countBg: 'rgba(209,250,229,0.8)',
    countColor: '#047857',
  },
  {
    key: 'sent',
    label: 'Отправлено',
    statuses: ['sent'],
    dotColor: '#94a3b8',
    headerBg: 'rgba(248,250,252,0.8)',
    borderColor: 'rgba(226,232,240,0.4)',
    countBg: '#f1f5f9',
    countColor: '#64748b',
  },
];

const KanbanView = ({ declarations, onClickDeclaration }: KanbanViewProps) => {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 2.5,
        minHeight: 400,
      }}
    >
      {COLUMNS.map((col) => {
        const items = declarations.filter(d => col.statuses.includes(d.status));
        return (
          <Box key={col.key} sx={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            {/* Column header */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                px: 1.5,
                py: 1.25,
                borderRadius: '12px',
                bgcolor: col.headerBg,
                border: '1px solid',
                borderColor: col.borderColor,
                mb: 1.5,
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box
                  sx={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    bgcolor: col.dotColor,
                  }}
                />
                <Typography
                  sx={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: '#334155',
                    letterSpacing: '-0.01em',
                  }}
                >
                  {col.label}
                </Typography>
              </Box>
              <Typography
                sx={{
                  fontSize: 11,
                  fontWeight: 600,
                  px: 1,
                  py: 0.25,
                  borderRadius: '6px',
                  bgcolor: col.countBg,
                  color: col.countColor,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {items.length}
              </Typography>
            </Box>

            {/* Cards */}
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: 1,
                flex: 1,
                overflowY: 'auto',
                maxHeight: 'calc(100vh - 340px)',
                pr: 0.25,
                '&::-webkit-scrollbar': { width: 4 },
                '&::-webkit-scrollbar-thumb': {
                  borderRadius: 2,
                  bgcolor: '#e2e8f0',
                },
              }}
            >
              {items.map((decl) => (
                <DeclarationCard
                  key={decl.id}
                  declaration={decl}
                  onClick={onClickDeclaration}
                />
              ))}
              {items.length === 0 && (
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    py: 6,
                    textAlign: 'center',
                  }}
                >
                  <Box
                    sx={{
                      width: 40,
                      height: 40,
                      borderRadius: '50%',
                      bgcolor: '#f1f5f9',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      mb: 1,
                    }}
                  >
                    <Typography sx={{ color: '#cbd5e1', fontSize: 16 }}>∅</Typography>
                  </Box>
                  <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>
                    Нет деклараций
                  </Typography>
                </Box>
              )}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
};

export default KanbanView;
