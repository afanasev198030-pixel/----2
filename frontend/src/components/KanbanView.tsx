import { Box, Typography, Chip } from '@mui/material';
import FiberNewIcon from '@mui/icons-material/FiberNew';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import SendIcon from '@mui/icons-material/Send';
import { Declaration, DeclarationStatus } from '../types';
import DeclarationKanbanCard from './DeclarationKanbanCard';

interface KanbanViewProps {
  declarations: Declaration[];
  onClickDeclaration: (id: string) => void;
}

const COLUMNS: DeclarationStatus[] = ['new', 'requires_attention', 'ready_to_send', 'sent'];

const COLUMN_CONFIG: Record<DeclarationStatus, {
  label: string;
  headerBg: string;
  border: string;
  countBg: string;
  countColor: string;
  icon: React.ReactNode;
}> = {
  new: {
    label: 'Новая',
    headerBg: '#eff6ff',
    border: '#bfdbfe',
    countBg: '#dbeafe',
    countColor: '#1d4ed8',
    icon: <FiberNewIcon sx={{ fontSize: 18, color: '#3b82f6' }} />,
  },
  requires_attention: {
    label: 'Требует внимания',
    headerBg: '#fffbeb',
    border: '#fde68a',
    countBg: '#fef3c7',
    countColor: '#b45309',
    icon: <WarningAmberIcon sx={{ fontSize: 18, color: '#f59e0b' }} />,
  },
  ready_to_send: {
    label: 'Готово к отправке',
    headerBg: '#ecfdf5',
    border: '#a7f3d0',
    countBg: '#d1fae5',
    countColor: '#047857',
    icon: <CheckCircleOutlineIcon sx={{ fontSize: 18, color: '#10b981' }} />,
  },
  sent: {
    label: 'Отправлено',
    headerBg: '#f8fafc',
    border: '#e2e8f0',
    countBg: '#f1f5f9',
    countColor: '#64748b',
    icon: <SendIcon sx={{ fontSize: 16, color: '#94a3b8' }} />,
  },
};

function KanbanColumn({ status, items, onClickDeclaration }: {
  status: DeclarationStatus;
  items: Declaration[];
  onClickDeclaration: (id: string) => void;
}) {
  const cfg = COLUMN_CONFIG[status];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 }}>
      {/* Column header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1.5,
          borderRadius: 3,
          bgcolor: cfg.headerBg,
          border: `1.5px solid ${cfg.border}`,
          mb: 1.5,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {cfg.icon}
          <Typography sx={{ fontSize: 13, fontWeight: 700, color: '#1e293b', letterSpacing: '-0.01em' }}>
            {cfg.label}
          </Typography>
        </Box>
        <Chip
          label={items.length}
          size="small"
          sx={{
            bgcolor: cfg.countBg,
            color: cfg.countColor,
            fontWeight: 700,
            fontSize: 12,
            height: 24,
            minWidth: 30,
            border: `1px solid ${cfg.border}`,
            '& .MuiChip-label': { px: 1 },
          }}
        />
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
          minHeight: 200,
          pr: 0.25,
          '&::-webkit-scrollbar': { width: 4 },
          '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(203,213,225,0.5)', borderRadius: 2 },
        }}
      >
        {items.map((decl) => (
          <DeclarationKanbanCard key={decl.id} declaration={decl} onClick={onClickDeclaration} />
        ))}
        {items.length === 0 && (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 6, color: '#94a3b8' }}>
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                bgcolor: 'rgba(241,245,249,1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                mb: 1,
                fontSize: 16,
                color: '#cbd5e1',
              }}
            >
              ∅
            </Box>
            <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>Нет деклараций</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}

const KanbanView = ({ declarations, onClickDeclaration }: KanbanViewProps) => {
  const grouped = COLUMNS.map((status) => ({
    status,
    items: declarations.filter((d) => d.status === status),
  }));

  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2.5 }}>
      {grouped.map(({ status, items }) => (
        <KanbanColumn key={status} status={status} items={items} onClickDeclaration={onClickDeclaration} />
      ))}
    </Box>
  );
};

export default KanbanView;
