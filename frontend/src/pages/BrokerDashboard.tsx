import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  PieChart, Pie, Cell,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip as ReTooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
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
  Divider,
  Alert,
} from '@mui/material';
import {
  People as PeopleIcon,
  WorkOutline as WorkIcon,
  CheckCircleOutline as CheckIcon,
  ErrorOutline as ErrorIcon,
  ArrowForward as ArrowForwardIcon,
  CallMade as ImportIcon,
  CallReceived as ExportIcon,
} from '@mui/icons-material';
import { getDeclarations } from '../api/declarations';
import { getBrokerClients, BrokerClient } from '../api/broker';
import { getMe } from '../api/auth';
import client from '../api/client';
import AppLayout from '../components/AppLayout';
import StatusChip from '../components/StatusChip';
import { Declaration } from '../types';
import dayjs from 'dayjs';

const BrokerDashboard = () => {
  const navigate = useNavigate();

  const { data: meData } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
  });

  const { data: declarationsData, isLoading: declLoading } = useQuery({
    queryKey: ['declarations', 1, 50],
    queryFn: () => getDeclarations({ page: 1, per_page: 50 }),
  });

  const { data: clientsData, isLoading: clientsLoading } = useQuery({
    queryKey: ['broker-clients'],
    queryFn: getBrokerClients,
  });

  const { data: aiHealth } = useQuery({
    queryKey: ['ai-health'],
    queryFn: () => client.get('/ai/health-detailed').then(r => r.data).catch(() => null),
    staleTime: 60_000,
  });

  const metrics = useMemo(() => {
    const items = declarationsData?.items || [];
    return {
      clients: clientsData?.length || 0,
      inProgress: items.filter((d: Declaration) =>
        ['new', 'requires_attention'].includes(d.status)
      ).length,
      released: items.filter((d: Declaration) => d.status === 'ready_to_send').length,
      rejected: items.filter((d: Declaration) => d.status === 'sent').length,
    };
  }, [declarationsData?.items, clientsData]);

  const recentDeclarations = useMemo(() => {
    const items = declarationsData?.items || [];
    return [...items]
      .sort((a: Declaration, b: Declaration) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 10);
  }, [declarationsData?.items]);

  const statusChartData = useMemo(() => {
    const items = declarationsData?.items || [];
    const counts: Record<string, number> = {};
    items.forEach((d: Declaration) => {
      const label = d.status === 'new' ? 'Новая'
        : d.status === 'requires_attention' ? 'Требует внимания'
        : d.status === 'ready_to_send' ? 'Готово к отправке'
        : d.status === 'sent' ? 'Отправлено'
        : d.status === 'signed' ? 'Подписано'
        : 'Прочее';
      counts[label] = (counts[label] || 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [declarationsData?.items]);

  const monthlyData = useMemo(() => {
    const items = declarationsData?.items || [];
    const months: Record<string, number> = {};
    items.forEach((d: Declaration) => {
      const month = dayjs(d.created_at).format('MMM');
      months[month] = (months[month] || 0) + 1;
    });
    return Object.entries(months).map(([month, count]) => ({ month, count })).slice(-6);
  }, [declarationsData?.items]);

  const COLORS = ['#2563eb', '#059669', '#d97706', '#8b5cf6', '#ec4899'];
  const isEmpty = !declLoading && !clientsLoading && metrics.clients === 0 && recentDeclarations.length === 0;

  return (
    <AppLayout>
      {/* LLM status banner */}
      {aiHealth && !aiHealth.llm_configured && (
        <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={() => navigate('/settings')}>Настройки</Button>}>
          API-ключ LLM не настроен. AI-парсинг и классификация ТН ВЭД не будут работать.
        </Alert>
      )}
      {aiHealth && aiHealth.llm_configured && aiHealth.dspy && !aiHealth.dspy.configured && (
        <Alert severity="warning" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={() => navigate('/settings')}>Настройки</Button>}>
          LLM подключен, но DSPy не сконфигурирован. Классификация ТН ВЭД может не работать. Проверьте API-ключ.
        </Alert>
      )}
      {aiHealth === null && (
        <Alert severity="error" sx={{ mb: 2 }}>
          AI-сервис недоступен. Парсинг документов не будет работать.
        </Alert>
      )}

      {/* Welcome */}
        <Typography variant="h5" fontWeight={700} gutterBottom sx={{ color: '#0f172a' }}>
          Добро пожаловать{meData?.full_name ? `, ${meData.full_name.split(' ')[0]}` : ''}
        </Typography>
        <Typography variant="body2" sx={{ mb: 3, color: '#64748b' }}>
          Обзор активности по клиентам и декларациям
        </Typography>

        {/* Onboarding empty state */}
        {isEmpty && (
          <Card sx={{ mb: { xs: 3, sm: 4 }, p: { xs: 2, sm: 3 }, textAlign: 'center', bgcolor: '#f8fafc', border: '1px dashed rgba(226,232,240,0.8)' }}>
            <Typography variant="h6" fontWeight={700} gutterBottom sx={{ color: '#0f172a' }}>Начните работу</Typography>
            <Typography variant="body2" sx={{ mb: 3, maxWidth: 480, mx: 'auto', color: '#64748b' }}>
              Загрузите первый документ и создайте декларацию — система поможет с заполнением и кодами ТН ВЭД.
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, justifyContent: 'center' }}>
              <Button variant="contained" startIcon={<PeopleIcon />} onClick={() => navigate('/clients')} sx={{ textTransform: 'none' }}>
                Добавить клиента
              </Button>
              <Button variant="outlined" startIcon={<ImportIcon />} onClick={() => navigate('/declarations')} sx={{ textTransform: 'none' }}>
                Создать первую декларацию
              </Button>
            </Box>
          </Card>
        )}

        {/* Metrics */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' }, gap: 2, mb: { xs: 3, sm: 4 } }}>
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
                  <Typography variant="h4" fontWeight={700} sx={{ color: '#2563eb' }}>
                    {clientsLoading ? <Skeleton width={40} /> : metrics.clients}
                  </Typography>
                  <Typography variant="body2" mt={0.5} sx={{ color: '#64748b' }}>Клиентов</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #eef2ff 0%, #dbeafe 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <PeopleIcon sx={{ color: '#2563eb' }} />
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
            onClick={() => navigate('/declarations?status=in_progress')}
          >
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="h4" fontWeight={700} sx={{ color: '#d97706' }}>
                    {declLoading ? <Skeleton width={40} /> : metrics.inProgress}
                  </Typography>
                  <Typography variant="body2" mt={0.5} sx={{ color: '#64748b' }}>В работе</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <WorkIcon sx={{ color: '#d97706' }} />
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
            onClick={() => navigate('/declarations?status=ready')}
          >
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="h4" fontWeight={700} sx={{ color: '#059669' }}>
                    {declLoading ? <Skeleton width={40} /> : metrics.released}
                  </Typography>
                  <Typography variant="body2" mt={0.5} sx={{ color: '#64748b' }}>Готовы к отправке</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #ecfdf5 0%, #a7f3d0 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <CheckIcon sx={{ color: '#059669' }} />
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
            onClick={() => navigate('/declarations?status=sent')}
          >
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="h4" fontWeight={700} sx={{ color: '#dc2626' }}>
                    {declLoading ? <Skeleton width={40} /> : metrics.rejected}
                  </Typography>
                  <Typography variant="body2" mt={0.5} sx={{ color: '#64748b' }}>Отправлены</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #fef2f2 0%, #fecaca 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <ErrorIcon sx={{ color: '#dc2626' }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Two-column layout: Recent Declarations + Clients */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '3fr 2fr' }, gap: { xs: 2, sm: 3 }, minWidth: 0 }}>
          {/* Recent Declarations */}
          <Paper sx={{ borderRadius: '14px', border: '1px solid rgba(226,232,240,0.8)', boxShadow: '0 1px 3px rgba(0,0,0,0.04)', overflow: 'hidden', minWidth: 0, width: '100%' }}>
            <Box sx={{ p: { xs: 2, sm: 2.5 }, display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, justifyContent: 'space-between', alignItems: { xs: 'stretch', sm: 'center' }, gap: { xs: 1, sm: 0 } }}>
              <Typography variant="h6" fontWeight={600} sx={{ fontSize: 15, color: '#0f172a' }}>Последние декларации</Typography>
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
            <TableContainer sx={{ overflowX: 'auto', maxWidth: '100%' }}>
              <Table size="small" sx={{ minWidth: { xs: 520, sm: 'unset' } }}>
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
                        <WorkIcon sx={{ fontSize: 48, color: '#94a3b8', mb: 1 }} />
                        <Typography variant="body2" sx={{ color: '#64748b' }}>
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
                          <Typography variant="body2" fontWeight={500} sx={{ color: '#2563eb' }}>
                            {decl.number_internal || 'Не присвоен'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            icon={decl.type_code?.startsWith('IM') ? <ImportIcon sx={{ fontSize: '14px !important' }} /> : <ExportIcon sx={{ fontSize: '14px !important' }} />}
                            label={decl.type_code?.startsWith('IM') ? 'ИМ' : 'ЭК'}
                            size="small"
                            sx={{
                              bgcolor: decl.type_code?.startsWith('IM') ? '#eef2ff' : '#fef3c7',
                              color: decl.type_code?.startsWith('IM') ? '#2563eb' : '#92400e',
                              fontWeight: 500,
                              fontSize: 11,
                              '& .MuiChip-icon': {
                                color: decl.type_code?.startsWith('IM') ? '#2563eb' : '#92400e',
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
                          <Typography variant="body2" sx={{ color: '#64748b' }}>
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
          <Paper sx={{ borderRadius: '14px', border: '1px solid rgba(226,232,240,0.8)', boxShadow: '0 1px 3px rgba(0,0,0,0.04)', overflow: 'hidden', minWidth: 0, width: '100%' }}>
            <Box sx={{ p: { xs: 2, sm: 2.5 }, display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, justifyContent: 'space-between', alignItems: { xs: 'stretch', sm: 'center' }, gap: { xs: 1, sm: 0 } }}>
              <Typography variant="h6" fontWeight={600} sx={{ fontSize: 15, color: '#0f172a' }}>Клиенты</Typography>
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
            <TableContainer sx={{ overflowX: 'auto', maxWidth: '100%' }}>
              <Table size="small" sx={{ minWidth: { xs: 400, sm: 'unset' } }}>
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
                        <PeopleIcon sx={{ fontSize: 48, color: '#94a3b8', mb: 1 }} />
                        <Typography variant="body2" sx={{ color: '#64748b' }}>
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
                          <Typography variant="body2" sx={{ color: '#64748b' }}>
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
                                c.tariff_plan === 'premium' ? '#f5f3ff' :
                                c.tariff_plan === 'standard' ? '#eef2ff' : '#f8fafc',
                              color:
                                c.tariff_plan === 'premium' ? '#6d28d9' :
                                c.tariff_plan === 'standard' ? '#2563eb' : '#64748b',
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
                              bgcolor: c.is_active ? '#ecfdf5' : '#fef2f2',
                              color: c.is_active ? '#059669' : '#dc2626',
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

        {/* Analytics */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: { xs: 2, sm: 3 }, mt: { xs: 2, sm: 3 }, minWidth: 0 }}>
          <Paper sx={{ p: { xs: 2, sm: 2.5 }, borderRadius: '14px', border: '1px solid rgba(226,232,240,0.8)', boxShadow: '0 1px 3px rgba(0,0,0,0.04)', minWidth: 0, width: '100%', overflow: 'hidden' }}>
            <Typography variant="h6" fontWeight={600} sx={{ mb: 2, fontSize: 15, color: '#0f172a' }}>Статусы деклараций</Typography>
            <Box sx={{ width: '100%', height: { xs: 220, sm: 250 }, minWidth: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={statusChartData} cx="50%" cy="50%" outerRadius="72%" dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                  {statusChartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <ReTooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
            </Box>
          </Paper>
          <Paper sx={{ p: { xs: 2, sm: 2.5 }, borderRadius: '14px', border: '1px solid rgba(226,232,240,0.8)', boxShadow: '0 1px 3px rgba(0,0,0,0.04)', minWidth: 0, width: '100%', overflow: 'hidden' }}>
            <Typography variant="h6" fontWeight={600} sx={{ mb: 2, fontSize: 15, color: '#0f172a' }}>Декларации по месяцам</Typography>
            <Box sx={{ width: '100%', height: { xs: 220, sm: 250 }, minWidth: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={monthlyData} margin={{ top: 8, right: 4, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} width={36} tick={{ fontSize: 11 }} />
                <ReTooltip />
                <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            </Box>
          </Paper>
        </Box>
    </AppLayout>
  );
};

export default BrokerDashboard;
