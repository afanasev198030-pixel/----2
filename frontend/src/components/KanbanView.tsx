import { Box, Paper, Typography, Chip, Card, CardContent } from '@mui/material';
import StatusChip from './StatusChip';
import { Declaration } from '../types';
import dayjs from 'dayjs';

interface KanbanViewProps {
  declarations: Declaration[];
  onClickDeclaration: (id: string) => void;
}

const COLUMNS = [
  { key: 'draft', label: 'Черновик', color: '#9e9e9e', statuses: ['draft'] },
  { key: 'checking', label: 'На проверке', color: '#ff9800', statuses: ['checking_lvl1', 'checking_lvl2', 'final_check'] },
  { key: 'signed', label: 'Подписано', color: '#2196f3', statuses: ['signed', 'sent'] },
  { key: 'released', label: 'Выпущено', color: '#4caf50', statuses: ['released', 'registered'] },
  { key: 'rejected', label: 'Отклонено', color: '#f44336', statuses: ['rejected', 'docs_requested', 'inspection'] },
];

const KanbanView = ({ declarations, onClickDeclaration }: KanbanViewProps) => {
  return (
    <Box sx={{ display: 'flex', gap: 2, overflowX: 'auto', pb: 2, minHeight: 400 }}>
      {COLUMNS.map((col) => {
        const items = declarations.filter(d => col.statuses.includes(d.status));
        return (
          <Box key={col.key} sx={{ minWidth: 250, flex: '1 0 250px' }}>
            <Paper sx={{ bgcolor: col.color + '15', borderTop: `3px solid ${col.color}`, borderRadius: 2, p: 1.5, minHeight: 350 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                <Typography variant="subtitle2" fontWeight={700}>{col.label}</Typography>
                <Chip label={items.length} size="small" sx={{ bgcolor: col.color, color: 'white', fontWeight: 700, height: 22 }} />
              </Box>
              {items.length === 0 && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 4 }}>
                  Нет деклараций
                </Typography>
              )}
              {items.map((decl) => (
                <Card key={decl.id} sx={{ mb: 1, cursor: 'pointer', '&:hover': { boxShadow: 3 }, transition: 'box-shadow 0.2s' }}
                  onClick={() => onClickDeclaration(decl.id)}>
                  <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography variant="body2" fontWeight={600} color="primary.main">
                        {decl.type_code || 'IM40'}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {dayjs(decl.created_at).format('DD.MM')}
                      </Typography>
                    </Box>
                    {decl.total_invoice_value && (
                      <Typography variant="body2">
                        {decl.currency_code} {Number(decl.total_invoice_value).toLocaleString('ru-RU')}
                      </Typography>
                    )}
                    <StatusChip status={decl.status} />
                  </CardContent>
                </Card>
              ))}
            </Paper>
          </Box>
        );
      })}
    </Box>
  );
};

export default KanbanView;
