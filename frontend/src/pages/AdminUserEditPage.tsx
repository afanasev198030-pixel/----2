import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container, Typography, Paper, Grid, TextField, Button, Box,
  FormControl, InputLabel, Select, MenuItem, Switch, FormControlLabel,
  Table, TableHead, TableRow, TableCell, TableBody, Chip, Divider,
  Alert, Snackbar, Pagination,
} from '@mui/material';
import { Save as SaveIcon, ArrowBack as BackIcon } from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import { getUser, updateUser, getUserAudit, AuditLogEntry } from '../api/users';
import { useAuth } from '../contexts/AuthContext';
import { User } from '../types';
import dayjs from 'dayjs';

const ROLE_OPTIONS = [
  { value: 'client', label: 'Клиент' },
  { value: 'ved_specialist', label: 'Специалист ВЭД' },
  { value: 'head', label: 'Руководитель' },
  { value: 'accountant', label: 'Бухгалтер' },
  { value: 'lawyer', label: 'Юрист' },
  { value: 'broker', label: 'Брокер' },
  { value: 'admin', label: 'Администратор' },
];

const ACTION_LABELS: Record<string, string> = {
  login: 'Вход',
  login_failed: 'Неудачный вход',
  register: 'Регистрация',
  create_declaration: 'Создание декларации',
  update_declaration: 'Редактирование декларации',
  apply_parsed: 'AI заполнение',
  upload_document: 'Загрузка документа',
  update_profile: 'Обновление профиля',
  admin_update_user: 'Изменение админом',
  telegram_message_received: 'Сообщение в Telegram',
  telegram_document_received: 'Документ в Telegram',
  telegram_bot_replied: 'Ответ бота',
};

const AdminUserEditPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  const [user, setUser] = useState<User | null>(null);
  const [form, setForm] = useState({ full_name: '', email: '', phone: '', role: 'client', is_active: true, company_id: '', telegram_id: '' });
  const [audit, setAudit] = useState<AuditLogEntry[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPage, setAuditPage] = useState(1);
  const [auditActionFilter, setAuditActionFilter] = useState('');
  const [snack, setSnack] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isAdmin || !id) { navigate('/dashboard'); return; }
    const load = async () => {
      try {
        const u = await getUser(id);
        setUser(u);
        setForm({
          full_name: u.full_name || '',
          email: u.email,
          phone: u.phone || '',
          role: u.role,
          is_active: u.is_active,
          company_id: u.company_id || '',
          telegram_id: u.telegram_id || '',
        });
      } catch { navigate('/admin/users'); }
    };
    load();
  }, [id, isAdmin]);

  useEffect(() => {
    if (!id) return;
    getUserAudit(id, auditPage, auditActionFilter).then((resp) => {
      setAudit(resp.items);
      setAuditTotal(resp.total);
    }).catch(() => {});
  }, [id, auditPage, auditActionFilter]);

  const handleSave = async () => {
    if (!id) return;
    try {
      setError('');
      const updated = await updateUser(id, {
        full_name: form.full_name,
        email: form.email,
        phone: form.phone || undefined,
        role: form.role,
        is_active: form.is_active,
        telegram_id: form.telegram_id || null,
      } as any);
      setUser(updated);
      setSnack('Пользователь обновлён');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Ошибка сохранения');
    }
  };

  if (!user) return null;

  return (
    <AppLayout breadcrumbs={[{ label: 'Администрирование' }, { label: 'Пользователи', path: '/admin/users' }, { label: user.full_name || user.email }]}>
      <Container maxWidth="lg" sx={{ py: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <Button startIcon={<BackIcon />} onClick={() => navigate('/admin/users')}>Назад</Button>
          <Typography variant="h5" fontWeight={700}>
            {user.full_name || user.email}
          </Typography>
          <Chip label={user.role} size="small" color={user.role === 'admin' ? 'error' : 'primary'} />
        </Box>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>Редактирование</Typography>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <TextField size="small" fullWidth label="ФИО" value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
                </Grid>
                <Grid item xs={12}>
                  <TextField size="small" fullWidth label="Email" value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })} />
                </Grid>
                <Grid item xs={12}>
                  <TextField size="small" fullWidth label="Телефон" value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                </Grid>
                <Grid item xs={12}>
                  <TextField size="small" fullWidth label="Telegram ID" value={form.telegram_id || ''}
                    onChange={(e) => setForm({ ...form, telegram_id: e.target.value })} 
                    helperText="Оставьте пустым для отвязки" />
                </Grid>
                <Grid item xs={6}>
                  <FormControl size="small" fullWidth>
                    <InputLabel>Роль</InputLabel>
                    <Select value={form.role} label="Роль" onChange={(e) => setForm({ ...form, role: e.target.value })}>
                      {ROLE_OPTIONS.map((r) => (
                        <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={6}>
                  <FormControlLabel
                    control={<Switch checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />}
                    label={form.is_active ? 'Активен' : 'Деактивирован'}
                  />
                </Grid>
              </Grid>
              <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSave} sx={{ mt: 2 }}>
                Сохранить
              </Button>
            </Paper>

            <Paper sx={{ p: 3, mt: 2 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>Информация</Typography>
              <Typography variant="body2" color="text.secondary">ID: {user.id}</Typography>
              <Typography variant="body2" color="text.secondary">Компания: {user.company_id || '—'}</Typography>
              <Typography variant="body2" color="text.secondary">Telegram ID: {user.telegram_id || 'Не привязан'}</Typography>
              <Typography variant="body2" color="text.secondary">Дата регистрации: {dayjs(user.created_at).format('DD.MM.YYYY HH:mm')}</Typography>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="subtitle1" fontWeight={600}>
                  Действия пользователя ({auditTotal})
                </Typography>
                <FormControl size="small" sx={{ minWidth: 150 }}>
                  <InputLabel>Фильтр</InputLabel>
                  <Select
                    value={auditActionFilter}
                    label="Фильтр"
                    onChange={(e) => {
                      setAuditActionFilter(e.target.value);
                      setAuditPage(1);
                    }}
                  >
                    <MenuItem value="">Все действия</MenuItem>
                    {Object.entries(ACTION_LABELS).map(([val, lbl]) => (
                      <MenuItem key={val} value={val}>{lbl}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Дата</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Действие</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Детали</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {audit.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{log.created_at ? dayjs(log.created_at).format('DD.MM HH:mm') : '—'}</TableCell>
                      <TableCell>
                        <Chip label={ACTION_LABELS[log.action] || log.action} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>
                        {log.details ? (
                          <Typography variant="caption" sx={{ display: 'block', maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={JSON.stringify(log.details)}>
                            {log.details.text || log.details.filename || JSON.stringify(log.details)}
                          </Typography>
                        ) : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                  {audit.length === 0 && (
                    <TableRow><TableCell colSpan={3} align="center">Нет действий</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
              {auditTotal > 20 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
                  <Pagination size="small" count={Math.ceil(auditTotal / 20)} page={auditPage} onChange={(_, p) => setAuditPage(p)} />
                </Box>
              )}
            </Paper>
          </Grid>
        </Grid>
      </Container>
      <Snackbar open={!!snack} autoHideDuration={3000} onClose={() => setSnack('')}>
        <Alert severity="success">{snack}</Alert>
      </Snackbar>
    </AppLayout>
  );
};

export default AdminUserEditPage;
