import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container, Typography, Paper, Table, TableHead, TableRow, TableCell, TableBody,
  Chip, TextField, Box, IconButton, Pagination, MenuItem, Select, FormControl, InputLabel,
  Tooltip,
} from '@mui/material';
import { Edit as EditIcon, Block as BlockIcon, CheckCircle as ActiveIcon } from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import { getUsers, UsersListResponse } from '../api/users';
import { useAuth } from '../contexts/AuthContext';
import dayjs from 'dayjs';

const ROLE_LABELS: Record<string, string> = {
  client: 'Клиент',
  ved_specialist: 'Специалист ВЭД',
  head: 'Руководитель',
  accountant: 'Бухгалтер',
  lawyer: 'Юрист',
  broker: 'Брокер',
  admin: 'Администратор',
};

const AdminUsersPage = () => {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [data, setData] = useState<UsersListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAdmin) { navigate('/dashboard'); return; }
    const load = async () => {
      setLoading(true);
      try {
        const params: any = { page, per_page: 20 };
        if (search) params.search = search;
        if (roleFilter) params.role = roleFilter;
        const resp = await getUsers(params);
        setData(resp);
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    };
    load();
  }, [page, search, roleFilter, isAdmin]);

  return (
    <AppLayout breadcrumbs={[{ label: 'Администрирование' }, { label: 'Пользователи' }]}>
      <Container maxWidth="lg" sx={{ py: 3 }}>
        <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>Пользователи</Typography>

        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <TextField
            size="small"
            label="Поиск (email, ФИО)"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            sx={{ width: 300 }}
          />
          <FormControl size="small" sx={{ width: 200 }}>
            <InputLabel>Роль</InputLabel>
            <Select value={roleFilter} label="Роль" onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}>
              <MenuItem value="">Все</MenuItem>
              {Object.entries(ROLE_LABELS).map(([k, v]) => (
                <MenuItem key={k} value={k}>{v}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        <Paper variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Email</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>ФИО</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Телефон</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Роль</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Telegram</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Статус</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Регистрация</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.items?.map((user) => (
                <TableRow key={user.id} hover sx={{ cursor: 'pointer' }} onClick={() => navigate(`/admin/users/${user.id}`)}>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>{user.full_name || '—'}</TableCell>
                  <TableCell>{user.phone || '—'}</TableCell>
                  <TableCell>
                    <Chip
                      label={ROLE_LABELS[user.role] || user.role}
                      size="small"
                      color={user.role === 'admin' ? 'error' : user.role === 'client' ? 'primary' : 'default'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    {user.telegram_id ? (
                      <Chip label="Привязан" size="small" color="info" variant="outlined" />
                    ) : (
                      <Typography variant="caption" color="text.secondary">—</Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {user.is_active
                      ? <Chip label="Активен" size="small" color="success" icon={<ActiveIcon />} />
                      : <Chip label="Деактивирован" size="small" color="default" icon={<BlockIcon />} />}
                  </TableCell>
                  <TableCell>{dayjs(user.created_at).format('DD.MM.YYYY HH:mm')}</TableCell>
                  <TableCell>
                    <Tooltip title="Редактировать">
                      <IconButton size="small" onClick={(e) => { e.stopPropagation(); navigate(`/admin/users/${user.id}`); }}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {!loading && (!data?.items || data.items.length === 0) && (
                <TableRow><TableCell colSpan={8} align="center">Нет пользователей</TableCell></TableRow>
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

export default AdminUsersPage;
