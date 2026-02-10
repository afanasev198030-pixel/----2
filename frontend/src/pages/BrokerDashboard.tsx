import { useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
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
  Card,
  CardContent,
  Skeleton,
  Chip,
  Avatar,
  IconButton,
  Tooltip,
  Divider,
} from '@mui/material';
import {
  People as PeopleIcon,
  WorkOutline as WorkIcon,
  CheckCircleOutline as CheckIcon,
  ErrorOutline as ErrorIcon,
  Dashboard as DashboardIcon,
  Description as DeclarationsIcon,
  Settings as SettingsIcon,
  ArrowForward as ArrowForwardIcon,
  Logout as LogoutIcon,
  CallMade as ImportIcon,
  CallReceived as ExportIcon,
} from '@mui/icons-material';
import { getDeclarations } from '../api/declarations';
import { getBrokerClients, BrokerClient } from '../api/broker';
import { logout, getMe } from '../api/auth';
import StatusChip from '../components/StatusChip';
import { Declaration } from '../types';
import dayjs from 'dayjs';

const BrokerDashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const { data: meData } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
  });

  const { data: declarationsData, isLoading: declLoading } = useQuery({
    queryKey: ['declarations', 1, 50],
    queryFn: () => getDeclarations({ page: 1, page_size: 50 }),
  });

  const { data: clientsData, isLoading: clientsLoading } = useQuery({
    queryKey: ['broker-clients'],
    queryFn: getBrokerClients,
  });

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const metrics = useMemo(() => {
    const items = declarationsData?.items || [];
    return {
      clients: clientsData?.length || 0,
      inProgress: items.filter((d: Declaration) =>
        ['draft', 'checking_lvl1', 'checking_lvl2', 'final_check'].includes(d.status)
      ).length,
      released: items.filter((d: Declaration) => d.status === 'released').length,
      rejected: items.filter((d: Declaration) => d.status === 'rejected').length,
    };
  }, [declarationsData?.items, clientsData]);

  const recentDeclarations = useMemo(() => {
    const items = declarationsData?.items || [];
    return [...items]
      .sort((a: Declaration, b: Declaration) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 10);
  }, [declarationsData?.items]);

  const navItems = [
    { label: 'Dashboard', path: '/dashboard', icon: <DashboardIcon fontSize="small" /> },
    { label: 'Клиенты', path: '/clients', icon: <PeopleIcon fontSize="small" /> },
    { label: 'Декларации', path: '/declarations', icon: <DeclarationsIcon fontSize="small" /> },
    { label: 'Настройки', path: '/settings', icon: <SettingsIcon fontSize="small" /> },
  ];

  const isActive = (path: string) => {
    if (path === '/dashboard') return location.pathname === '/' || location.pathname === '/dashboard';
    return location.pathname.startsWith(path);
  };

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
            Панель брокера
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
                  fontWeight: isActive(item.path) ? 700 : 400,
                  bgcolor: isActive(item.path) ? 'rgba(255,255,255,0.15)' : 'transparent',
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
        {/* Welcome */}
        <Typography variant="h5" fontWeight={700} gutterBottom>
          Добро пожаловать{meData?.full_name ? `, ${meData.full_name.split(' ')[0]}` : ''}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Обзор активности по клиентам и декларациям
        </Typography>

        {/* Metrics */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 2, mb: 4 }}>
          <Card
            sx={{
              cursor: 'pointer',
              transition: 'all 0.2s',
              '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 },
            }}
            onClick={() => navigate('/clients')}
          >
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="h4" color="info.main" fontWeight={700}>
                    {clientsLoading ? <Skeleton width={40} /> : metrics.clients}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" mt={0.5}>Клиентов</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <PeopleIcon color="info" />
                </Box>
              </Box>
            </CardContent>
          </Card>

          <Card
            sx={{
              cursor: 'pointer',
              transition: 'all 0.2s',
              '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 },
            }}
            onClick={() => navigate('/declarations')}
          >
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="h4" color="warning.main" fontWeight={700}>
                    {declLoading ? <Skeleton width={40} /> : metrics.inProgress}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" mt={0.5}>В работе</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <WorkIcon color="warning" />
                </Box>
              </Box>
            </CardContent>
          </Card>

          <Card sx={{ transition: 'all 0.2s', '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 } }}>
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="h4" color="success.main" fontWeight={700}>
                    {declLoading ? <Skeleton width={40} /> : metrics.released}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" mt={0.5}>Выпущено</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <CheckIcon color="success" />
                </Box>
              </Box>
            </CardContent>
          </Card>

          <Card sx={{ transition: 'all 0.2s', '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 } }}>
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="h4" color="error.main" fontWeight={700}>
                    {declLoading ? <Skeleton width={40} /> : metrics.rejected}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" mt={0.5}>Отклонено</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <ErrorIcon color="error" />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Two-column layout: Recent Declarations + Clients */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '3fr 2fr' }, gap: 3 }}>
          {/* Recent Declarations */}
          <Paper sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.08)', overflow: 'hidden' }}>
            <Box sx={{ p: 2.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="h6" fontWeight={600}>Последние декларации</Typography>
              <Button
                size="small"
                endIcon={<ArrowForwardIcon />}
                onClick={() => navigate('/declarations')}
                sx={{ textTransform: 'none' }}
              >
                Все декларации
              </Button>
            </Box>
            <Divider />
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>№</TableCell>
                    <TableCell>Тип</TableCell>
                    <TableCell>Статус</TableCell>
                    <TableCell align="right">Сумма</TableCell>
                    <TableCell>Дата</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {declLoading ? (
                    Array.from({ length: 5 }).map((_, i) => (
                      <TableRow key={i}>
                        <TableCell><Skeleton width={100} /></TableCell>
                        <TableCell><Skeleton width={60} /></TableCell>
                        <TableCell><Skeleton width={90} /></TableCell>
                        <TableCell><Skeleton width={80} /></TableCell>
                        <TableCell><Skeleton width={70} /></TableCell>
                      </TableRow>
                    ))
                  ) : recentDeclarations.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} align="center" sx={{ py: 6 }}>
                        <WorkIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                        <Typography variant="body2" color="text.secondary">
                          Нет деклараций
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ) : (
                    recentDeclarations.map((decl: Declaration) => (
                      <TableRow
                        key={decl.id}
                        hover
                        sx={{ cursor: 'pointer', '&:last-child td': { borderBottom: 0 } }}
                        onClick={() => navigate(`/declarations/${decl.id}/edit`)}
                      >
                        <TableCell>
                          <Typography variant="body2" fontWeight={500} color="primary.main">
                            {decl.number_internal || 'Не присвоен'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            icon={decl.type_code?.startsWith('IM') ? <ImportIcon sx={{ fontSize: '14px !important' }} /> : <ExportIcon sx={{ fontSize: '14px !important' }} />}
                            label={decl.type_code?.startsWith('IM') ? 'ИМ' : 'ЭК'}
                            size="small"
                            sx={{
                              bgcolor: decl.type_code?.startsWith('IM') ? '#e3f2fd' : '#fff3e0',
                              color: decl.type_code?.startsWith('IM') ? '#1565c0' : '#e65100',
                              fontWeight: 500,
                              fontSize: 11,
                              '& .MuiChip-icon': {
                                color: decl.type_code?.startsWith('IM') ? '#1565c0' : '#e65100',
                              },
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <StatusChip status={decl.status} />
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2">
                            {decl.total_invoice_value
                              ? `${decl.currency_code || '₽'} ${Number(decl.total_invoice_value).toLocaleString('ru-RU', { minimumFractionDigits: 2 })}`
                              : '—'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" color="text.secondary">
                            {dayjs(decl.created_at).format('DD.MM.YYYY')}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>

          {/* Clients */}
          <Paper sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.08)', overflow: 'hidden' }}>
            <Box sx={{ p: 2.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="h6" fontWeight={600}>Клиенты</Typography>
              <Button
                size="small"
                endIcon={<ArrowForwardIcon />}
                onClick={() => navigate('/clients')}
                sx={{ textTransform: 'none' }}
              >
                Все клиенты
              </Button>
            </Box>
            <Divider />
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Название</TableCell>
                    <TableCell>ИНН</TableCell>
                    <TableCell>Тариф</TableCell>
                    <TableCell>Статус</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {clientsLoading ? (
                    Array.from({ length: 4 }).map((_, i) => (
                      <TableRow key={i}>
                        <TableCell><Skeleton width={120} /></TableCell>
                        <TableCell><Skeleton width={80} /></TableCell>
                        <TableCell><Skeleton width={70} /></TableCell>
                        <TableCell><Skeleton width={70} /></TableCell>
                      </TableRow>
                    ))
                  ) : !clientsData || clientsData.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} align="center" sx={{ py: 6 }}>
                        <PeopleIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                        <Typography variant="body2" color="text.secondary">
                          Нет клиентов
                        </Typography>
                        <Button
                          size="small"
                          sx={{ mt: 1, textTransform: 'none' }}
                          onClick={() => navigate('/clients')}
                        >
                          Добавить клиента
                        </Button>
                      </TableCell>
                    </TableRow>
                  ) : (
                    clientsData.slice(0, 8).map((c: BrokerClient) => (
                      <TableRow
                        key={c.id}
                        hover
                        sx={{ cursor: 'pointer', '&:last-child td': { borderBottom: 0 } }}
                        onClick={() => navigate(`/clients/${c.id}`)}
                      >
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>
                            {c.client_company?.name || '—'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" color="text.secondary">
                            {c.client_company?.inn || '—'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={
                              c.tariff_plan === 'premium' ? 'Премиум' :
                              c.tariff_plan === 'standard' ? 'Стандарт' : 'Базовый'
                            }
                            size="small"
                            sx={{
                              bgcolor:
                                c.tariff_plan === 'premium' ? '#f3e5f5' :
                                c.tariff_plan === 'standard' ? '#e3f2fd' : '#f5f5f5',
                              color:
                                c.tariff_plan === 'premium' ? '#7b1fa2' :
                                c.tariff_plan === 'standard' ? '#1565c0' : '#616161',
                              fontWeight: 500,
                              fontSize: 11,
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={c.is_active ? 'Активен' : 'Неактивен'}
                            size="small"
                            sx={{
                              bgcolor: c.is_active ? '#e8f5e9' : '#ffebee',
                              color: c.is_active ? '#1b5e20' : '#c62828',
                              fontWeight: 500,
                              fontSize: 11,
                            }}
                          />
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Box>
      </Box>
    </Box>
  );
};

export default BrokerDashboard;
