import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container, Typography, Paper, Table, TableHead, TableRow, TableCell, TableBody,
  Chip, TextField, Box, Pagination, MenuItem, Select, FormControl, InputLabel,
} from '@mui/material';
import AppLayout from '../components/AppLayout';
import { getAuditLog, getAuditActions, AuditLogEntry, AuditListResponse } from '../api/users';
import { useAuth } from '../contexts/AuthContext';
import dayjs from 'dayjs';

const ACTION_LABELS: Record<string, string> = {
  login: 'Вход в систему',
  login_failed: 'Неудачный вход',
  register: 'Регистрация',
  create_declaration: 'Создание декларации',
  update_declaration: 'Редактирование декларации',
  apply_parsed: 'AI заполнение',
  upload_document: 'Загрузка документа',
  update_profile: 'Обновление профиля',
  admin_update_user: 'Изменение пользователя',
};

const ACTION_COLORS: Record<string, 'success' | 'error' | 'warning' | 'info' | 'default'> = {
  login: 'success',
  login_failed: 'error',
  register: 'info',
  create_declaration: 'info',
  update_declaration: 'default',
  apply_parsed: 'warning',
};

const AdminAuditPage = () => {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [data, setData] = useState<AuditListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState('');
  const [searchUser, setSearchUser] = useState('');
  const [actions, setActions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAdmin) { navigate('/dashboard'); return; }
    getAuditActions().then(setActions).catch(() => {});
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin) return;
    const load = async () => {
      setLoading(true);
      try {
        const params: any = { page, per_page: 30 };
        if (actionFilter) params.action = actionFilter;
        const resp = await getAuditLog(params);
        setData(resp);
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    };
    load();
  }, [page, actionFilter, isAdmin]);

  // Client-side filter by user email/name (since backend already returns user info)
  const filtered = data?.items?.filter((log) => {
    if (!searchUser) return true;
    const s = searchUser.toLowerCase();
    return (log.user_email || '').toLowerCase().includes(s) || (log.user_name || '').toLowerCase().includes(s);
  }) || [];

  return (
    <AppLayout breadcrumbs={[{ label: 'Администрирование' }, { label: 'Аудит-лог' }]}>
      <Container maxWidth="xl" sx={{ py: 3 }}>
        <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>Аудит-лог действий</Typography>

        <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
          <TextField
            size="small"
            label="Поиск по пользователю"
            value={searchUser}
            onChange={(e) => setSearchUser(e.target.value)}
            sx={{ width: 250 }}
          />
          <FormControl size="small" sx={{ width: 220 }}>
            <InputLabel>Действие</InputLabel>
            <Select value={actionFilter} label="Действие" onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}>
              <MenuItem value="">Все</MenuItem>
              {actions.map((a) => (
                <MenuItem key={a} value={a}>{ACTION_LABELS[a] || a}</MenuItem>
              ))}
            </Select>
          </FormControl>
          {data && (
            <Chip label={`Всего записей: ${data.total}`} variant="outlined" sx={{ alignSelf: 'center' }} />
          )}
        </Box>

        <Paper variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Дата</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Пользователь</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Действие</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Ресурс</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Детали</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>IP</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filtered.map((log) => (
                <TableRow key={log.id} hover>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    {log.created_at ? dayjs(log.created_at).format('DD.MM.YYYY HH:mm:ss') : '—'}
                  </TableCell>
                  <TableCell>
                    <Box>
                      <Typography variant="body2" fontWeight={600}>{log.user_name || '—'}</Typography>
                      <Typography variant="caption" color="text.secondary">{log.user_email || '—'}</Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={ACTION_LABELS[log.action] || log.action}
                      size="small"
                      color={ACTION_COLORS[log.action] || 'default'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    {log.resource_type && (
                      <Typography variant="caption">
                        {log.resource_type}
                        {log.resource_id && ` #${log.resource_id.slice(0, 8)}...`}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {log.details && (
                      <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 200, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {JSON.stringify(log.details).slice(0, 80)}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption">{log.ip_address || '—'}</Typography>
                  </TableCell>
                </TableRow>
              ))}
              {!loading && filtered.length === 0 && (
                <TableRow><TableCell colSpan={6} align="center">Нет записей</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>

        {data && data.pages > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
            <Pagination count={data.pages} page={page} onChange={(_, p) => setPage(p)} />
          </Box>
        )}
      </Container>
    </AppLayout>
  );
};

export default AdminAuditPage;
