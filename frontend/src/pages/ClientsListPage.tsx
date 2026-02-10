import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Chip,
  TextField,
  InputAdornment,
  Skeleton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tooltip,
  Avatar,
  Snackbar,
  Alert,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Add as AddIcon,
  Search as SearchIcon,
  People as PeopleIcon,
  Edit as EditIcon,
  Visibility as ViewIcon,
  Dashboard as DashboardIcon,
  Description as DeclarationsIcon,
  Settings as SettingsIcon,
  Logout as LogoutIcon,
} from '@mui/icons-material';
import { getBrokerClients, createBrokerClient, BrokerClient, CreateBrokerClientData } from '../api/broker';
import { logout, getMe } from '../api/auth';

const tariffLabels: Record<string, { label: string; bg: string; color: string }> = {
  basic: { label: 'Базовый', bg: '#f5f5f5', color: '#616161' },
  standard: { label: 'Стандарт', bg: '#e3f2fd', color: '#1565c0' },
  premium: { label: 'Премиум', bg: '#f3e5f5', color: '#7b1fa2' },
};

const ClientsListPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  // Form state
  const [formData, setFormData] = useState<CreateBrokerClientData>({
    client_company_name: '',
    client_company_inn: '',
    client_company_kpp: '',
    client_company_address: '',
    contract_number: '',
    contract_date: '',
    tariff_plan: 'standard',
  });

  const { data: meData } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
  });

  const { data: clients, isLoading } = useQuery({
    queryKey: ['broker-clients'],
    queryFn: getBrokerClients,
  });

  const createMutation = useMutation({
    mutationFn: createBrokerClient,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['broker-clients'] });
      setDialogOpen(false);
      resetForm();
      setSnackbar({ open: true, message: 'Клиент успешно добавлен', severity: 'success' });
    },
    onError: (err: any) => {
      console.error('Create client error:', err?.response?.data || err);
      setSnackbar({
        open: true,
        message: err?.response?.data?.detail || 'Ошибка при создании клиента',
        severity: 'error',
      });
    },
  });

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const resetForm = () => {
    setFormData({
      client_company_name: '',
      client_company_inn: '',
      client_company_kpp: '',
      client_company_address: '',
      contract_number: '',
      contract_date: '',
      tariff_plan: 'standard',
    });
  };

  const handleCreate = () => {
    if (!formData.client_company_name.trim() || !formData.client_company_inn.trim()) return;
    createMutation.mutate(formData);
  };

  const filteredClients = useMemo(() => {
    if (!clients) return [];
    if (!searchQuery.trim()) return clients;
    const query = searchQuery.toLowerCase().trim();
    return clients.filter((c: BrokerClient) => {
      const nameMatch = c.client_company?.name?.toLowerCase().includes(query);
      const innMatch = c.client_company?.inn?.toLowerCase().includes(query);
      const contractMatch = c.contract_number?.toLowerCase().includes(query);
      return nameMatch || innMatch || contractMatch;
    });
  }, [clients, searchQuery]);

  const navItems = [
    { label: 'Dashboard', path: '/dashboard', icon: <DashboardIcon fontSize="small" /> },
    { label: 'Клиенты', path: '/clients', icon: <PeopleIcon fontSize="small" /> },
    { label: 'Декларации', path: '/declarations', icon: <DeclarationsIcon fontSize="small" /> },
    { label: 'Настройки', path: '/settings', icon: <SettingsIcon fontSize="small" /> },
  ];

  const getInitials = (name: string) => {
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#f5f7fa' }}>
      {/* Header */}
      <AppBar position="sticky" elevation={0} sx={{ bgcolor: 'primary.main' }}>
        <Toolbar sx={{ px: { xs: 2, md: 4 } }}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 2,
              background: 'rgba(255,255,255,0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mr: 2,
            }}
          >
            <Typography sx={{ color: 'white', fontWeight: 700, fontSize: 14 }}>ТД</Typography>
          </Box>
          <Typography variant="h6" sx={{ fontWeight: 700, mr: 4 }}>
            Клиенты
          </Typography>

          <Box sx={{ display: 'flex', gap: 0.5, flexGrow: 1 }}>
            {navItems.map((item) => (
              <Button
                key={item.path}
                startIcon={item.icon}
                onClick={() => navigate(item.path)}
                sx={{
                  color: 'white',
                  textTransform: 'none',
                  fontWeight: item.path === '/clients' ? 700 : 400,
                  bgcolor: item.path === '/clients' ? 'rgba(255,255,255,0.15)' : 'transparent',
                  borderRadius: 2,
                  px: 2,
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' },
                }}
              >
                {item.label}
              </Button>
            ))}
          </Box>

          <Tooltip title={meData?.full_name || 'Пользователь'}>
            <IconButton color="inherit" sx={{ ml: 1 }}>
              <Avatar sx={{ width: 36, height: 36, bgcolor: 'rgba(255,255,255,0.2)', fontSize: 14, fontWeight: 600 }}>
                {meData?.full_name ? getInitials(meData.full_name) : 'А'}
              </Avatar>
            </IconButton>
          </Tooltip>
          <Tooltip title="Выйти">
            <IconButton color="inherit" onClick={handleLogout} sx={{ ml: 0.5 }}>
              <LogoutIcon />
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>

      <Box sx={{ px: { xs: 2, md: 4 }, py: 3, maxWidth: 1400, mx: 'auto' }}>
        {/* Toolbar */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, gap: 2, flexWrap: 'wrap' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexGrow: 1 }}>
            <IconButton onClick={() => navigate('/dashboard')} sx={{ bgcolor: 'white', boxShadow: 1 }}>
              <ArrowBackIcon />
            </IconButton>
            <TextField
              size="small"
              placeholder="Поиск по названию, ИНН, контракту..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              sx={{
                width: { xs: '100%', sm: 400 },
                '& .MuiOutlinedInput-root': { borderRadius: 2, bgcolor: 'white' },
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon color="action" />
                  </InputAdornment>
                ),
              }}
            />
          </Box>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setDialogOpen(true)}
            sx={{ fontWeight: 600, borderRadius: 2, px: 3, textTransform: 'none' }}
          >
            Добавить клиента
          </Button>
        </Box>

        {/* Table */}
        <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.08)', overflow: 'hidden' }}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Название</TableCell>
                <TableCell>ИНН</TableCell>
                <TableCell>КПП</TableCell>
                <TableCell>Контракт</TableCell>
                <TableCell>Тариф</TableCell>
                <TableCell>Статус</TableCell>
                <TableCell align="center">Действия</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton width={150} /></TableCell>
                    <TableCell><Skeleton width={100} /></TableCell>
                    <TableCell><Skeleton width={80} /></TableCell>
                    <TableCell><Skeleton width={120} /></TableCell>
                    <TableCell><Skeleton width={80} /></TableCell>
                    <TableCell><Skeleton width={80} /></TableCell>
                    <TableCell><Skeleton width={60} /></TableCell>
                  </TableRow>
                ))
              ) : filteredClients.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 8 }}>
                    <PeopleIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary" gutterBottom>
                      {searchQuery ? 'Клиенты не найдены' : 'Нет клиентов'}
                    </Typography>
                    <Typography variant="body2" color="text.disabled" sx={{ mb: 3 }}>
                      {searchQuery
                        ? 'Попробуйте изменить параметры поиска'
                        : 'Добавьте первого клиента для начала работы'}
                    </Typography>
                    {!searchQuery && (
                      <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialogOpen(true)}>
                        Добавить клиента
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ) : (
                filteredClients.map((client: BrokerClient) => {
                  const tariff = tariffLabels[client.tariff_plan] || tariffLabels.basic;
                  return (
                    <TableRow
                      key={client.id}
                      hover
                      sx={{ cursor: 'pointer', '&:last-child td': { borderBottom: 0 } }}
                      onClick={() => navigate(`/clients/${client.id}`)}
                    >
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {client.client_company?.name || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                          {client.client_company?.inn || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {client.client_company?.kpp || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {client.contract_number || '—'}
                        </Typography>
                        {client.contract_date && (
                          <Typography variant="caption" color="text.secondary">
                            от {client.contract_date}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={tariff.label}
                          size="small"
                          sx={{ bgcolor: tariff.bg, color: tariff.color, fontWeight: 500, fontSize: 11 }}
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={client.is_active ? 'Активен' : 'Неактивен'}
                          size="small"
                          sx={{
                            bgcolor: client.is_active ? '#e8f5e9' : '#ffebee',
                            color: client.is_active ? '#1b5e20' : '#c62828',
                            fontWeight: 500,
                            fontSize: 11,
                          }}
                        />
                      </TableCell>
                      <TableCell align="center">
                        <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                          <Tooltip title="Просмотр">
                            <IconButton
                              size="small"
                              onClick={(e) => { e.stopPropagation(); navigate(`/clients/${client.id}`); }}
                              sx={{ borderRadius: 1.5, '&:hover': { bgcolor: 'primary.light', color: 'primary.main' } }}
                            >
                              <ViewIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>

      {/* Create Client Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => { setDialogOpen(false); resetForm(); }}
        PaperProps={{ sx: { borderRadius: 3, minWidth: 500 } }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 600 }}>Добавить клиента</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <TextField
              label="Название компании"
              value={formData.client_company_name}
              onChange={(e) => setFormData({ ...formData, client_company_name: e.target.value })}
              fullWidth
              required
              autoFocus
            />
            <Box sx={{ display: 'flex', gap: 2 }}>
              <TextField
                label="ИНН"
                value={formData.client_company_inn}
                onChange={(e) => setFormData({ ...formData, client_company_inn: e.target.value })}
                fullWidth
                required
                inputProps={{ maxLength: 12 }}
              />
              <TextField
                label="КПП"
                value={formData.client_company_kpp}
                onChange={(e) => setFormData({ ...formData, client_company_kpp: e.target.value })}
                fullWidth
                inputProps={{ maxLength: 9 }}
              />
            </Box>
            <TextField
              label="Адрес"
              value={formData.client_company_address}
              onChange={(e) => setFormData({ ...formData, client_company_address: e.target.value })}
              fullWidth
              multiline
              rows={2}
            />
            <Box sx={{ display: 'flex', gap: 2 }}>
              <TextField
                label="Номер контракта"
                value={formData.contract_number}
                onChange={(e) => setFormData({ ...formData, contract_number: e.target.value })}
                fullWidth
              />
              <TextField
                label="Дата контракта"
                type="date"
                value={formData.contract_date}
                onChange={(e) => setFormData({ ...formData, contract_date: e.target.value })}
                fullWidth
                InputLabelProps={{ shrink: true }}
              />
            </Box>
            <FormControl fullWidth>
              <InputLabel>Тарифный план</InputLabel>
              <Select
                value={formData.tariff_plan}
                onChange={(e) => setFormData({ ...formData, tariff_plan: e.target.value as 'basic' | 'standard' | 'premium' })}
                label="Тарифный план"
              >
                <MenuItem value="basic">Базовый</MenuItem>
                <MenuItem value="standard">Стандарт</MenuItem>
                <MenuItem value="premium">Премиум</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => { setDialogOpen(false); resetForm(); }} sx={{ color: 'text.secondary' }}>
            Отмена
          </Button>
          <Button
            onClick={handleCreate}
            variant="contained"
            disabled={createMutation.isPending || !formData.client_company_name.trim() || !formData.client_company_inn.trim()}
            sx={{ px: 4 }}
          >
            {createMutation.isPending ? 'Создание...' : 'Добавить'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          sx={{ borderRadius: 2 }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ClientsListPage;
