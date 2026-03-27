import { useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Button, Paper, TextField, Grid, IconButton,
  Dialog, DialogTitle, DialogContent, DialogActions, Alert,
  List, ListItem, ListItemText, ListItemIcon, Checkbox, Chip, Skeleton,
} from '@mui/material';
import {
  Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon,
  ChecklistRtl as ChecklistIcon, DragIndicator,
} from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import client from '../api/client';

interface ChecklistItem {
  label: string;
  field?: string;
  critical?: boolean;
}

interface ChecklistData {
  id: string;
  name: string;
  description: string;
  declaration_type: string;
  items: ChecklistItem[];
  is_active: boolean;
  created_at: string;
}

const AdminChecklistPage = () => {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editCl, setEditCl] = useState<ChecklistData | null>(null);
  const [form, setForm] = useState({ name: '', description: '', declaration_type: 'IM40', is_active: true });
  const [clItems, setClItems] = useState<ChecklistItem[]>([]);
  const [newItemLabel, setNewItemLabel] = useState('');

  const { data: checklists = [], isLoading } = useQuery({
    queryKey: ['checklists'],
    queryFn: async () => { const r = await client.get('/knowledge/checklists', { params: { active_only: false } }); return r.data; },
  });

  const openCreate = useCallback(() => {
    setEditCl(null);
    setForm({ name: '', description: '', declaration_type: 'IM40', is_active: true });
    setClItems([
      { label: 'Номер инвойса заполнен', field: 'invoice_number', critical: true },
      { label: 'Валюта и сумма указаны', field: 'currency_code', critical: true },
      { label: 'Код ТН ВЭД 10 знаков', field: '_hs', critical: true },
      { label: 'Вес брутто/нетто указан', field: '_weights', critical: true },
      { label: 'Отправитель указан', field: 'sender_counterparty_id', critical: true },
      { label: 'Получатель указан', field: 'receiver_counterparty_id', critical: true },
    ]);
    setDialogOpen(true);
  }, []);

  const openEdit = useCallback((cl: ChecklistData) => {
    setEditCl(cl);
    setForm({ name: cl.name, description: cl.description, declaration_type: cl.declaration_type, is_active: cl.is_active });
    setClItems(cl.items || []);
    setDialogOpen(true);
  }, []);

  const handleSave = useCallback(async () => {
    const payload = { ...form, items: clItems };
    if (editCl) {
      await client.put(`/knowledge/checklists/${editCl.id}`, payload);
    } else {
      await client.post('/knowledge/checklists', payload);
    }
    queryClient.invalidateQueries({ queryKey: ['checklists'] });
    setDialogOpen(false);
  }, [form, clItems, editCl, queryClient]);

  const handleDelete = useCallback(async (id: string) => {
    if (!window.confirm('Удалить чек-лист?')) return;
    await client.delete(`/knowledge/checklists/${id}`);
    queryClient.invalidateQueries({ queryKey: ['checklists'] });
  }, [queryClient]);

  const addItem = useCallback(() => {
    if (!newItemLabel.trim()) return;
    setClItems(prev => [...prev, { label: newItemLabel.trim(), critical: false }]);
    setNewItemLabel('');
  }, [newItemLabel]);

  const removeItem = useCallback((idx: number) => {
    setClItems(prev => prev.filter((_, i) => i !== idx));
  }, []);

  const toggleCritical = useCallback((idx: number) => {
    setClItems(prev => prev.map((item, i) => i === idx ? { ...item, critical: !item.critical } : item));
  }, []);

  return (
    <AppLayout breadcrumbs={[{ label: 'Админ', path: '/admin/users' }, { label: 'Чек-листы' }]}>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h5" fontWeight={700} sx={{ color: '#0f172a' }}>
            <ChecklistIcon sx={{ mr: 1, verticalAlign: 'bottom', color: '#2563eb' }} />
            Чек-листы ({checklists.length})
          </Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>Новый чек-лист</Button>
        </Box>

        <Alert severity="info" sx={{ mb: 2, boxShadow: 'none', border: '1px solid rgba(226,232,240,0.9)' }}>
          Чек-листы — шаблоны проверок перед отправкой декларации. Декларант видит список пунктов и отмечает выполненные.
          Пример пунктов: «Проверить соответствие веса в инвойсе и packing list», «Убедиться что сертификат происхождения приложен».
          Критичные пункты блокируют отправку если не отмечены.
        </Alert>

        {isLoading ? (
          <Grid container spacing={2}>{[1,2].map(i => <Grid item xs={12} md={6} key={i}><Skeleton variant="rectangular" height={200} /></Grid>)}</Grid>
        ) : checklists.length === 0 ? (
          <Alert severity="info">Нет чек-листов. Создайте первый.</Alert>
        ) : (
          <Grid container spacing={2}>
            {checklists.map((cl: ChecklistData) => (
              <Grid item xs={12} md={6} key={cl.id}>
                <Paper variant="outlined" sx={{ p: 2, boxShadow: 'none' }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="subtitle1" fontWeight={600} sx={{ color: '#0f172a' }}>{cl.name}</Typography>
                    <Box>
                      <Chip label={cl.declaration_type} size="small" variant="outlined" sx={{ mr: 1, borderColor: 'rgba(148,163,184,0.55)', color: '#64748b', fontWeight: 600 }} />
                      <Chip label={cl.is_active ? 'Активен' : 'Неактивен'} size="small" color={cl.is_active ? 'success' : 'default'} variant={cl.is_active ? 'filled' : 'outlined'} sx={cl.is_active ? {} : { borderColor: 'rgba(148,163,184,0.55)', color: '#64748b' }} />
                    </Box>
                  </Box>
                  {cl.description && <Typography variant="body2" sx={{ mb: 1, color: '#64748b' }}>{cl.description}</Typography>}
                  <List dense disablePadding>
                    {(cl.items || []).map((item: ChecklistItem, idx: number) => (
                      <ListItem key={idx} disablePadding sx={{ py: 0.25 }}>
                        <ListItemIcon sx={{ minWidth: 28 }}>
                          <Checkbox size="small" disabled checked={false} />
                        </ListItemIcon>
                        <ListItemText
                          primary={item.label}
                          primaryTypographyProps={{ variant: 'body2', sx: { color: item.critical ? '#dc2626' : '#0f172a' } }}
                        />
                      </ListItem>
                    ))}
                  </List>
                  <Box sx={{ mt: 1, display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                    <IconButton size="small" onClick={() => openEdit(cl)}><EditIcon fontSize="small" /></IconButton>
                    <IconButton size="small" color="error" onClick={() => handleDelete(cl.id)}><DeleteIcon fontSize="small" /></IconButton>
                  </Box>
                </Paper>
              </Grid>
            ))}
          </Grid>
        )}
      </Box>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editCl ? 'Редактировать чек-лист' : 'Новый чек-лист'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={8}><TextField fullWidth label="Название" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} size="small" /></Grid>
            <Grid item xs={4}><TextField fullWidth label="Тип ДТ" value={form.declaration_type} onChange={e => setForm({ ...form, declaration_type: e.target.value })} size="small" /></Grid>
            <Grid item xs={12}><TextField fullWidth label="Описание" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} size="small" multiline rows={2} /></Grid>
          </Grid>
          <Typography variant="subtitle2" sx={{ mt: 2, mb: 1, color: '#0f172a', fontWeight: 600 }}>Пункты чек-листа ({clItems.length})</Typography>
          <List dense>
            {clItems.map((item, idx) => (
              <ListItem key={idx} secondaryAction={
                <IconButton size="small" onClick={() => removeItem(idx)}><DeleteIcon fontSize="small" /></IconButton>
              }>
                <ListItemIcon sx={{ minWidth: 28 }}>
                  <Checkbox size="small" checked={item.critical || false} onChange={() => toggleCritical(idx)} />
                </ListItemIcon>
                <ListItemText primary={item.label} secondary={item.critical ? 'Критичный' : undefined} />
              </ListItem>
            ))}
          </List>
          <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
            <TextField size="small" fullWidth placeholder="Новый пункт..." value={newItemLabel}
              onChange={e => setNewItemLabel(e.target.value)} onKeyDown={e => e.key === 'Enter' && addItem()} />
            <Button size="small" onClick={addItem} disabled={!newItemLabel.trim()}>Добавить</Button>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleSave} disabled={!form.name.trim()}>
            {editCl ? 'Сохранить' : 'Создать'}
          </Button>
        </DialogActions>
      </Dialog>
    </AppLayout>
  );
};

export default AdminChecklistPage;
