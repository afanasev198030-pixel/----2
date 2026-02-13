import { useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
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
  IconButton,
  Chip,
  Card,
  CardContent,
  Skeleton,
  Tooltip,
  Divider,
  Grid,
} from '@mui/material';
import {
  Add as AddIcon,
  Business as BusinessIcon,
  Phone as PhoneIcon,
  Email as EmailIcon,
  Description as DescriptionIcon,
  CalendarToday as CalendarIcon,
  WorkOutline as WorkIcon,
  CallMade as ImportIcon,
  CallReceived as ExportIcon,
  OpenInNew as OpenIcon,
} from '@mui/icons-material';
import { getBrokerClient } from '../api/broker';
import { getDeclarations } from '../api/declarations';
import AppLayout from '../components/AppLayout';
import StatusChip from '../components/StatusChip';
import { Declaration } from '../types';
import dayjs from 'dayjs';

const tariffLabels: Record<string, { label: string; bg: string; color: string }> = {
  basic: { label: 'Базовый', bg: '#f5f5f5', color: '#616161' },
  standard: { label: 'Стандарт', bg: '#e3f2fd', color: '#1565c0' },
  premium: { label: 'Премиум', bg: '#f3e5f5', color: '#7b1fa2' },
};

const ClientDetailPage = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();

  const { data: client, isLoading: clientLoading } = useQuery({
    queryKey: ['broker-client', id],
    queryFn: () => getBrokerClient(id!),
    enabled: !!id,
  });

  const { data: declarationsData, isLoading: declLoading } = useQuery({
    queryKey: ['declarations', 1, 50, client?.client_company_id],
    queryFn: () => getDeclarations({ page: 1, page_size: 50, company_id: client?.client_company_id }),
    enabled: !!client?.client_company_id,
  });

  const declarations = useMemo(() => {
    return declarationsData?.items || [];
  }, [declarationsData]);

  const metrics = useMemo(() => {
    return {
      total: declarations.length,
      inProgress: declarations.filter((d: Declaration) =>
        ['draft', 'checking_lvl1', 'checking_lvl2', 'final_check'].includes(d.status)
      ).length,
      released: declarations.filter((d: Declaration) => d.status === 'released').length,
      rejected: declarations.filter((d: Declaration) => d.status === 'rejected').length,
    };
  }, [declarations]);

  const tariff = tariffLabels[client?.tariff_plan || 'basic'] || tariffLabels.basic;

  const clientName = client?.client_company?.name || 'Клиент';

  const handleCreateDeclaration = () => {
    // Navigate to declarations page — the company_id will be pre-set
    navigate('/declarations', { state: { company_id: client?.client_company_id } });
  };

  return (
    <AppLayout breadcrumbs={[{ label: 'Клиенты', path: '/clients' }, { label: clientName }]}>
      {/* Header + Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box>
              {clientLoading ? (
                <Skeleton width={250} height={32} />
              ) : (
                <Typography variant="h5" fontWeight={700}>
                  {client?.client_company?.name || 'Клиент'}
                </Typography>
              )}
            </Box>
          </Box>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateDeclaration}
            sx={{ fontWeight: 600, borderRadius: 2, px: 3, textTransform: 'none' }}
          >
            Создать декларацию
          </Button>
        </Box>

        {/* Client Info + Metrics */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3, mb: 3 }}>
          {/* Client Info Card */}
          <Paper sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.08)', overflow: 'hidden' }}>
            <Box sx={{ p: 2.5 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>Информация о компании</Typography>
            </Box>
            <Divider />
            <Box sx={{ p: 2.5 }}>
              {clientLoading ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} width="80%" height={24} />
                  ))}
                </Box>
              ) : (
                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <BusinessIcon fontSize="small" color="action" />
                      <Typography variant="body2" color="text.secondary">Название</Typography>
                    </Box>
                    <Typography variant="body1" fontWeight={500} sx={{ ml: 4 }}>
                      {client?.client_company?.name || '—'}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>ИНН</Typography>
                    <Typography variant="body1" fontWeight={500} sx={{ fontFamily: 'monospace' }}>
                      {client?.client_company?.inn || '—'}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>КПП</Typography>
                    <Typography variant="body1" fontWeight={500} sx={{ fontFamily: 'monospace' }}>
                      {client?.client_company?.kpp || '—'}
                    </Typography>
                  </Grid>
                  {client?.client_company?.address && (
                    <Grid item xs={12}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>Адрес</Typography>
                      <Tooltip title={client.client_company.address} placement="top" arrow>
                        <Typography variant="body1" noWrap sx={{ maxWidth: 400 }}>{client.client_company.address}</Typography>
                      </Tooltip>
                    </Grid>
                  )}
                  {client?.client_company?.contact_email && (
                    <Grid item xs={6}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <EmailIcon fontSize="small" color="action" />
                        <Typography variant="body2">{client.client_company.contact_email}</Typography>
                      </Box>
                    </Grid>
                  )}
                  {client?.client_company?.contact_phone && (
                    <Grid item xs={6}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <PhoneIcon fontSize="small" color="action" />
                        <Typography variant="body2">{client.client_company.contact_phone}</Typography>
                      </Box>
                    </Grid>
                  )}
                  <Grid item xs={12}>
                    <Divider sx={{ my: 1 }} />
                  </Grid>
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                      <DescriptionIcon fontSize="small" color="action" />
                      <Typography variant="body2" color="text.secondary">Контракт</Typography>
                    </Box>
                    <Typography variant="body1" fontWeight={500} sx={{ ml: 4 }}>
                      {client?.contract_number || '—'}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                      <CalendarIcon fontSize="small" color="action" />
                      <Typography variant="body2" color="text.secondary">Дата контракта</Typography>
                    </Box>
                    <Typography variant="body1" fontWeight={500} sx={{ ml: 4 }}>
                      {client?.contract_date || '—'}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Тариф</Typography>
                    <Chip label={tariff.label} size="small" sx={{ bgcolor: tariff.bg, color: tariff.color, fontWeight: 500 }} />
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Статус</Typography>
                    <Chip
                      label={client?.is_active ? 'Активен' : 'Неактивен'}
                      size="small"
                      sx={{
                        bgcolor: client?.is_active ? '#e8f5e9' : '#ffebee',
                        color: client?.is_active ? '#1b5e20' : '#c62828',
                        fontWeight: 500,
                      }}
                    />
                  </Grid>
                </Grid>
              )}
            </Box>
          </Paper>

          {/* Metrics */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, alignContent: 'start' }}>
            <Card sx={{ transition: 'all 0.2s', '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 } }}>
              <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                <Typography variant="h4" color="info.main" fontWeight={700}>
                  {declLoading ? <Skeleton width={30} /> : metrics.total}
                </Typography>
                <Typography variant="body2" color="text.secondary" mt={0.5}>Всего деклараций</Typography>
              </CardContent>
            </Card>
            <Card sx={{ transition: 'all 0.2s', '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 } }}>
              <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                <Typography variant="h4" color="warning.main" fontWeight={700}>
                  {declLoading ? <Skeleton width={30} /> : metrics.inProgress}
                </Typography>
                <Typography variant="body2" color="text.secondary" mt={0.5}>В работе</Typography>
              </CardContent>
            </Card>
            <Card sx={{ transition: 'all 0.2s', '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 } }}>
              <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                <Typography variant="h4" color="success.main" fontWeight={700}>
                  {declLoading ? <Skeleton width={30} /> : metrics.released}
                </Typography>
                <Typography variant="body2" color="text.secondary" mt={0.5}>Выпущено</Typography>
              </CardContent>
            </Card>
            <Card sx={{ transition: 'all 0.2s', '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 } }}>
              <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                <Typography variant="h4" color="error.main" fontWeight={700}>
                  {declLoading ? <Skeleton width={30} /> : metrics.rejected}
                </Typography>
                <Typography variant="body2" color="text.secondary" mt={0.5}>Отклонено</Typography>
              </CardContent>
            </Card>
          </Box>
        </Box>

        {/* Declarations Table */}
        <Paper sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.08)', overflow: 'hidden' }}>
          <Box sx={{ p: 2.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6" fontWeight={600}>Декларации клиента</Typography>
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={handleCreateDeclaration}
              size="small"
              sx={{ textTransform: 'none', borderRadius: 2 }}
            >
              Создать декларацию
            </Button>
          </Box>
          <Divider />
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Номер ДТ</TableCell>
                  <TableCell>Дата</TableCell>
                  <TableCell>Направление</TableCell>
                  <TableCell>Статус</TableCell>
                  <TableCell align="right">Стоимость</TableCell>
                  <TableCell align="center">Действия</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {declLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell><Skeleton variant="text" width={120} /></TableCell>
                      <TableCell><Skeleton variant="text" width={80} /></TableCell>
                      <TableCell><Skeleton variant="text" width={70} /></TableCell>
                      <TableCell><Skeleton variant="text" width={100} /></TableCell>
                      <TableCell><Skeleton variant="text" width={90} /></TableCell>
                      <TableCell><Skeleton variant="text" width={40} /></TableCell>
                    </TableRow>
                  ))
                ) : declarations.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 8 }}>
                      <WorkIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                      <Typography variant="h6" color="text.secondary" gutterBottom>
                        Нет деклараций
                      </Typography>
                      <Typography variant="body2" color="text.disabled" sx={{ mb: 3 }}>
                        Создайте первую декларацию для этого клиента
                      </Typography>
                      <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={handleCreateDeclaration}
                      >
                        Создать декларацию
                      </Button>
                    </TableCell>
                  </TableRow>
                ) : (
                  declarations.map((decl: Declaration) => (
                    <TableRow
                      key={decl.id}
                      hover
                      sx={{ cursor: 'pointer', '&:last-child td': { borderBottom: 0 } }}
                      onClick={() => navigate(`/declarations/${decl.id}/edit`)}
                    >
                      <TableCell>
                        <Typography variant="body2" fontWeight={600} color="primary.main">
                          {decl.number_internal || 'Не присвоен'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{dayjs(decl.created_at).format('DD.MM.YYYY')}</Typography>
                        <Typography variant="caption" color="text.secondary">{dayjs(decl.created_at).format('HH:mm')}</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          icon={decl.type_code?.startsWith('IM') ? <ImportIcon sx={{ fontSize: '14px !important' }} /> : <ExportIcon sx={{ fontSize: '14px !important' }} />}
                          label={decl.type_code?.startsWith('IM') ? 'Импорт' : 'Экспорт'}
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
                        <Typography variant="body2" fontWeight={500}>
                          {decl.total_invoice_value
                            ? `${decl.currency_code || '₽'} ${Number(decl.total_invoice_value).toLocaleString('ru-RU', { minimumFractionDigits: 2 })}`
                            : '—'}
                        </Typography>
                      </TableCell>
                      <TableCell align="center">
                        <Tooltip title="Открыть">
                          <IconButton
                            size="small"
                            onClick={(e) => { e.stopPropagation(); navigate(`/declarations/${decl.id}/edit`); }}
                            sx={{ borderRadius: 1.5, '&:hover': { bgcolor: 'primary.light', color: 'primary.main' } }}
                          >
                            <OpenIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
    </AppLayout>
  );
};

export default ClientDetailPage;
