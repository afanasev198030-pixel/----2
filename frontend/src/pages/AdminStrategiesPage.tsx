import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Button, Paper, TextField, IconButton, Switch, Chip,
  Dialog, DialogTitle, DialogContent, DialogActions, Alert, Tooltip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  FormControlLabel,
} from '@mui/material';
import {
  Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon,
  Psychology as AiIcon,
} from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import {
  getStrategies, createStrategy, updateStrategy, deleteStrategy,
  AiStrategy, StrategyCreate,
} from '../api/strategies';

const EMPTY_FORM: StrategyCreate = {
  name: '',
  rule_text: '',
  description: '',
  priority: 0,
  is_active: true,
};

const AdminStrategiesPage = () => {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<StrategyCreate>(EMPTY_FORM);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const { data: strategies = [], isLoading, error } = useQuery({
    queryKey: ['ai-strategies'],
    queryFn: getStrategies,
  });

  const createMut = useMutation({
    mutationFn: createStrategy,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['ai-strategies'] }); handleClose(); },
  });

  const updateMut = useMutation({
    mutationFn: (vars: { id: string; data: Partial<StrategyCreate> }) =>
      updateStrategy(vars.id, vars.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['ai-strategies'] }); handleClose(); },
  });

  const deleteMut = useMutation({
    mutationFn: deleteStrategy,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['ai-strategies'] }); setDeleteConfirm(null); },
  });

  const handleClose = () => {
    setDialogOpen(false);
    setEditId(null);
    setForm(EMPTY_FORM);
  };

  const handleEdit = (s: AiStrategy) => {
    setEditId(s.id);
    setForm({
      name: s.name,
      rule_text: s.rule_text,
      description: s.description || '',
      priority: s.priority,
      is_active: s.is_active,
    });
    setDialogOpen(true);
  };

  const handleSave = () => {
    if (editId) {
      updateMut.mutate({ id: editId, data: form });
    } else {
      createMut.mutate(form);
    }
  };

  const toggleActive = (s: AiStrategy) => {
    updateMut.mutate({ id: s.id, data: { is_active: !s.is_active } });
  };

  return (
    <AppLayout title="AI-стратегии">
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <AiIcon color="primary" />
            <Typography variant="h5">AI-стратегии заполнения</Typography>
          </Box>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => { setForm(EMPTY_FORM); setDialogOpen(true); }}
          >
            Новая стратегия
          </Button>
        </Box>

        <Alert severity="info" sx={{ mb: 2 }}>
          Стратегии задают бизнес-правила для AI: условия и инструкции, которые влияют на автозаполнение декларации.
          Например: «Если поставщик ZED Group — ставить EXW и пост Шереметьево».
        </Alert>

        {error && <Alert severity="error" sx={{ mb: 2 }}>Ошибка загрузки стратегий</Alert>}

        <TableContainer component={Paper} variant="outlined">
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Название</TableCell>
                <TableCell>Правило</TableCell>
                <TableCell align="center">Приоритет</TableCell>
                <TableCell align="center">Активна</TableCell>
                <TableCell align="right">Действия</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                <TableRow><TableCell colSpan={5} align="center">Загрузка...</TableCell></TableRow>
              ) : strategies.length === 0 ? (
                <TableRow><TableCell colSpan={5} align="center">Нет стратегий. Создайте первую.</TableCell></TableRow>
              ) : (
                strategies.map((s) => (
                  <TableRow key={s.id} sx={{ opacity: s.is_active ? 1 : 0.5 }}>
                    <TableCell>
                      <Typography variant="subtitle2">{s.name}</Typography>
                      {s.description && (
                        <Typography variant="caption" color="text.secondary">{s.description}</Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {s.rule_text}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Chip label={s.priority} size="small" color={s.priority > 5 ? 'warning' : 'default'} />
                    </TableCell>
                    <TableCell align="center">
                      <Switch checked={s.is_active} onChange={() => toggleActive(s)} size="small" />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Редактировать">
                        <IconButton size="small" onClick={() => handleEdit(s)}><EditIcon fontSize="small" /></IconButton>
                      </Tooltip>
                      <Tooltip title="Удалить">
                        <IconButton size="small" color="error" onClick={() => setDeleteConfirm(s.id)}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Create / Edit Dialog */}
        <Dialog open={dialogOpen} onClose={handleClose} maxWidth="md" fullWidth>
          <DialogTitle>{editId ? 'Редактирование стратегии' : 'Новая AI-стратегия'}</DialogTitle>
          <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
            <TextField
              label="Название"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
              required
            />
            <TextField
              label="Описание"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              multiline
              rows={2}
            />
            <TextField
              label="Правило для AI"
              value={form.rule_text}
              onChange={(e) => setForm({ ...form, rule_text: e.target.value })}
              fullWidth
              required
              multiline
              rows={4}
              placeholder='Если поставщик содержит "ZED Group", установить условия поставки EXW и таможенный пост Шереметьево.'
            />
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <TextField
                label="Приоритет"
                type="number"
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 0 })}
                sx={{ width: 120 }}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={form.is_active}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  />
                }
                label="Активна"
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleClose}>Отмена</Button>
            <Button
              variant="contained"
              onClick={handleSave}
              disabled={!form.name || !form.rule_text || createMut.isPending || updateMut.isPending}
            >
              {editId ? 'Сохранить' : 'Создать'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Delete confirmation */}
        <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
          <DialogTitle>Удалить стратегию?</DialogTitle>
          <DialogContent>
            <Typography>Это действие нельзя отменить. Стратегия будет удалена из системы.</Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteConfirm(null)}>Отмена</Button>
            <Button
              color="error"
              variant="contained"
              onClick={() => deleteConfirm && deleteMut.mutate(deleteConfirm)}
              disabled={deleteMut.isPending}
            >
              Удалить
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </AppLayout>
  );
};

export default AdminStrategiesPage;
