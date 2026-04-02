import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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
  Snackbar,
  Alert,
} from '@mui/material';
import {
  Add as AddIcon,
  Search as SearchIcon,
  People as PeopleIcon,
  Visibility as ViewIcon,
  FileDownload as FileDownloadIcon,
} from '@mui/icons-material';
import { getBrokerClients, createBrokerClient, BrokerClient, CreateBrokerClientData } from '../api/broker';
import AppLayout from '../components/AppLayout';

const tariffLabels: Record<string, { label: string; bg: string; color: string }> = {
  basic: { label: 'Базовый', bg: '#f8fafc', color: '#64748b' },
  standard: { label: 'Стандарт', bg: '#eef2ff', color: '#1d4ed8' },
  premium: { label: 'Премиум', bg: '#f5f3ff', color: '#6d28d9' },
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

  const handleExportCSV = () => {
    const items = filteredClients || [];
    const header = 'Название;ИНН;КПП;Контракт;Тариф\n';
    const rows = items.map((c: BrokerClient) =>
      `${c.client_company?.name || ''};${c.client_company?.inn || ''};${c.client_company?.kpp || ''};${c.contract_number || ''};${c.tariff_plan || ''}`
    ).join('\n');
    const bom = '\uFEFF';
    const blob = new Blob([bom + header + rows], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'clients.csv'; a.click();
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

  return (
    <AppLayout breadcrumbs={[{ label: 'Клиенты' }]}>
      {/* Toolbar */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, gap: 2, flexWrap: 'wrap' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexGrow: 1 }}>
          <TextField
              size="small"
              placeholder="Поиск по названию, ИНН, контракту..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              sx={{
                width: { xs: '100%', sm: 400 },
                '& .MuiOutlinedInput-root': {
                  borderRadius: '10px',
                  bgcolor: 'white',
                  boxShadow: 'none',
                },
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
            size="small"
            onClick={handleExportCSV}
            startIcon={<FileDownloadIcon />}
            sx={{ textTransform: 'none', borderRadius: '10px', color: '#64748b' }}
          >
            Excel
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setDialogOpen(true)}
            sx={{
              fontWeight: 600,
              borderRadius: '10px',
              px: 3,
              textTransform: 'none',
              bgcolor: '#2563eb',
              boxShadow: 'none',
              '&:hover': { bgcolor: '#1d4ed8', boxShadow: 'none' },
            }}
          >
            Добавить клиента
          </Button>
        </Box>

        {/* Table */}
        <TableContainer
          component={Paper}
          sx={{
            borderRadius: '14px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            border: '1px solid rgba(226,232,240,0.8)',
            overflowX: 'auto',
          }}
        >
          <Table sx={{ minWidth: 700 }}>
            <TableHead>
              <TableRow>
                <TableCell sx={{ color: '#0f172a', fontWeight: 600, fontSize: '0.75rem', borderBottom: '1px solid rgba(226,232,240,0.8)' }}>
                  Название
                </TableCell>
                <TableCell sx={{ color: '#0f172a', fontWeight: 600, fontSize: '0.75rem', borderBottom: '1px solid rgba(226,232,240,0.8)' }}>
                  ИНН
                </TableCell>
                <TableCell sx={{ color: '#0f172a', fontWeight: 600, fontSize: '0.75rem', borderBottom: '1px solid rgba(226,232,240,0.8)', display: { xs: 'none', md: 'table-cell' } }}>
                  КПП
                </TableCell>
                <TableCell sx={{ color: '#0f172a', fontWeight: 600, fontSize: '0.75rem', borderBottom: '1px solid rgba(226,232,240,0.8)', display: { xs: 'none', md: 'table-cell' } }}>
                  Контракт
                </TableCell>
                <TableCell sx={{ color: '#0f172a', fontWeight: 600, fontSize: '0.75rem', borderBottom: '1px solid rgba(226,232,240,0.8)', display: { xs: 'none', md: 'table-cell' } }}>
                  Тариф
                </TableCell>
                <TableCell sx={{ color: '#0f172a', fontWeight: 600, fontSize: '0.75rem', borderBottom: '1px solid rgba(226,232,240,0.8)', display: { xs: 'none', md: 'table-cell' } }}>
                  Статус
                </TableCell>
                <TableCell
                  align="center"
                  sx={{ color: '#0f172a', fontWeight: 600, fontSize: '0.75rem', borderBottom: '1px solid rgba(226,232,240,0.8)' }}
                >
                  Действия
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton variant="text" width={150} /></TableCell>
                    <TableCell><Skeleton variant="text" width={100} /></TableCell>
                    <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}><Skeleton variant="text" width={80} /></TableCell>
                    <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}><Skeleton variant="text" width={120} /></TableCell>
                    <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}><Skeleton variant="text" width={80} /></TableCell>
                    <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}><Skeleton variant="text" width={80} /></TableCell>
                    <TableCell><Skeleton variant="text" width={60} /></TableCell>
                  </TableRow>
                ))
              ) : filteredClients.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 8 }}>
                    <PeopleIcon sx={{ fontSize: 64, color: '#94a3b8', mb: 2 }} />
                    <Typography variant="h6" gutterBottom sx={{ color: '#0f172a' }}>
                      {searchQuery ? 'Клиенты не найдены' : 'Нет клиентов'}
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 3, color: '#64748b' }}>
                      {searchQuery
                        ? 'Попробуйте изменить параметры поиска'
                        : 'Добавьте первого клиента для начала работы'}
                    </Typography>
                    {!searchQuery && (
                      <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => setDialogOpen(true)}
                        sx={{
                          borderRadius: '10px',
                          textTransform: 'none',
                          bgcolor: '#2563eb',
                          boxShadow: 'none',
                          '&:hover': { bgcolor: '#1d4ed8', boxShadow: 'none' },
                        }}
                      >
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
                        <Tooltip title={client.client_company?.name || '—'} placement="top" arrow>
                          <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: 200, color: '#0f172a' }}>
                            {client.client_company?.name || '—'}
                          </Typography>
                        </Tooltip>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', color: '#64748b' }}>
                          {client.client_company?.inn || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>
                        <Typography variant="body2" sx={{ color: '#64748b' }}>
                          {client.client_company?.kpp || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>
                        <Typography variant="body2" sx={{ color: '#0f172a' }}>
                          {client.contract_number || '—'}
                        </Typography>
                        {client.contract_date && (
                          <Typography variant="caption" sx={{ color: '#64748b' }}>
                            от {client.contract_date}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>
                        <Chip
                          label={tariff.label}
                          size="small"
                          sx={{ bgcolor: tariff.bg, color: tariff.color, fontWeight: 500, fontSize: 11 }}
                        />
                      </TableCell>
                      <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>
                        <Chip
                          label={client.is_active ? 'Активен' : 'Неактивен'}
                          size="small"
                          sx={{
                            bgcolor: client.is_active ? '#ecfdf5' : '#fef2f2',
                            color: client.is_active ? '#166534' : '#b91c1c',
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
                              sx={{
                                borderRadius: '10px',
                                '&:hover': { bgcolor: 'rgba(238,242,255,0.95)', color: '#2563eb' },
                              }}
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

      {/* Create Client Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => { setDialogOpen(false); resetForm(); }}
        PaperProps={{
          sx: {
            borderRadius: '14px',
            minWidth: 500,
            boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            border: '1px solid rgba(226,232,240,0.8)',
          },
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 600, color: '#0f172a' }}>Добавить клиента</DialogTitle>
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
          <Button onClick={() => { setDialogOpen(false); resetForm(); }} sx={{ color: '#64748b', textTransform: 'none' }}>
            Отмена
          </Button>
          <Button
            onClick={handleCreate}
            variant="contained"
            disabled={createMutation.isPending || !formData.client_company_name.trim() || !formData.client_company_inn.trim()}
            sx={{
              px: 4,
              borderRadius: '10px',
              textTransform: 'none',
              bgcolor: '#2563eb',
              boxShadow: 'none',
              '&:hover': { bgcolor: '#1d4ed8', boxShadow: 'none' },
            }}
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
          sx={{ borderRadius: '14px' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </AppLayout>
  );
};

export default ClientsListPage;
