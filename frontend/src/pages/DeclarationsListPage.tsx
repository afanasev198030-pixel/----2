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
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
  FormControl,
  InputLabel,
  Chip,
  Card,
  CardContent,
  TextField,
  InputAdornment,
  Avatar,
  Tooltip,
  Skeleton,
  TablePagination,
  TableSortLabel,
} from '@mui/material';
import {
  AccountCircle,
  Add as AddIcon,
  Search as SearchIcon,
  WorkOutline as WorkIcon,
  SendOutlined as SendIcon,
  ErrorOutline as ErrorIcon,
  CheckCircleOutline as CheckIcon,
  OpenInNew as OpenIcon,
  ContentCopy as CopyIcon,
  Print as PrintIcon,
  MoreVert as MoreVertIcon,
  TrendingUp as TrendingUpIcon,
  CallMade as ImportIcon,
  CallReceived as ExportIcon,
  Delete as DeleteIcon,
  PictureAsPdf as PdfIcon,
} from '@mui/icons-material';
import { getDeclarations, createDeclaration, deleteDeclaration } from '../api/declarations';
import { logout, getMe } from '../api/auth';
import StatusChip from '../components/StatusChip';
import { Declaration } from '../types';
import dayjs from 'dayjs';

type SortField = 'number_internal' | 'created_at' | 'type_code' | 'status' | 'total_invoice_value';
type SortOrder = 'asc' | 'desc';

const DeclarationsListPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newTypeCode, setNewTypeCode] = useState<'IM40' | 'EX10'>('IM40');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string[] | null>(null);
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [rowActionMenuAnchor, setRowActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [rowActionDeclarationId, setRowActionDeclarationId] = useState<string | null>(null);

  const { data: meData } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
  });

  const { data, isLoading } = useQuery({
    queryKey: ['declarations', page, perPage],
    queryFn: () => getDeclarations({ page, page_size: perPage }),
  });

  const createMutation = useMutation({
    mutationFn: createDeclaration,
    onSuccess: (newDecl) => {
      queryClient.invalidateQueries({ queryKey: ['declarations'] });
      setCreateDialogOpen(false);
      navigate(`/declarations/${newDecl.id}/edit`);
    },
    onError: (err: any) => {
      console.error('Create declaration error:', err?.response?.data || err);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDeclaration,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['declarations'] });
      setRowActionMenuAnchor(null);
      setRowActionDeclarationId(null);
    },
    onError: (err: any) => {
      console.error('Delete declaration error:', err?.response?.data || err);
    },
  });

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleCreate = () => {
    if (!meData?.company_id) return;
    createMutation.mutate({ type_code: newTypeCode, company_id: meData.company_id });
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const handleRowActionClick = (e: React.MouseEvent<HTMLElement>, declarationId: string) => {
    e.stopPropagation();
    setRowActionMenuAnchor(e.currentTarget);
    setRowActionDeclarationId(declarationId);
  };

  const handleRowActionClose = () => {
    setRowActionMenuAnchor(null);
    setRowActionDeclarationId(null);
  };

  const handleDuplicate = () => {
    if (!rowActionDeclarationId) return;
    // TODO: Implement duplicate functionality
    console.log('Duplicate declaration:', rowActionDeclarationId);
    handleRowActionClose();
  };

  const handleDelete = () => {
    if (!rowActionDeclarationId) return;
    if (window.confirm('Вы уверены, что хотите удалить эту декларацию?')) {
      deleteMutation.mutate(rowActionDeclarationId);
    }
  };

  const handleExportPdf = () => {
    if (!rowActionDeclarationId) return;
    // TODO: Implement PDF export functionality
    console.log('Export PDF for declaration:', rowActionDeclarationId);
    handleRowActionClose();
  };

  const handleMetricClick = (statuses: string[] | null) => {
    setStatusFilter(statuses);
    setPage(1);
  };

  // Client-side filtering and sorting
  const filteredAndSortedItems = useMemo(() => {
    if (!data?.items) return [];

    let filtered = [...data.items];

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filtered = filtered.filter((decl: Declaration) => {
        const numberMatch = decl.number_internal?.toLowerCase().includes(query);
        const idMatch = decl.id.toLowerCase().includes(query);
        const typeMatch = decl.type_code?.toLowerCase().includes(query);
        const statusMatch = decl.status.toLowerCase().includes(query);
        return numberMatch || idMatch || typeMatch || statusMatch;
      });
    }

    // Apply status filter
    if (statusFilter) {
      filtered = filtered.filter((decl: Declaration) => statusFilter.includes(decl.status));
    }

    // Apply sorting
    filtered.sort((a: Declaration, b: Declaration) => {
      let aValue: any;
      let bValue: any;

      switch (sortField) {
        case 'number_internal':
          aValue = a.number_internal || a.id;
          bValue = b.number_internal || b.id;
          break;
        case 'created_at':
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
          break;
        case 'type_code':
          aValue = a.type_code || '';
          bValue = b.type_code || '';
          break;
        case 'status':
          aValue = a.status;
          bValue = b.status;
          break;
        case 'total_invoice_value':
          aValue = a.total_invoice_value ?? 0;
          bValue = b.total_invoice_value ?? 0;
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [data?.items, searchQuery, statusFilter, sortField, sortOrder]);

  // Check if all values in "Стоимость" column are empty
  const hasAnyValue = useMemo(() => {
    return filteredAndSortedItems.some((decl: Declaration) => decl.total_invoice_value != null);
  }, [filteredAndSortedItems]);

  // Calculate metrics from filtered items
  const metrics = useMemo(() => {
    const allItems = data?.items || [];
    return {
      total: allItems.length,
      checking: allItems.filter((d: Declaration) => ['checking_lvl1', 'checking_lvl2', 'final_check'].includes(d.status)).length,
      released: allItems.filter((d: Declaration) => d.status === 'released').length,
      attention: allItems.filter((d: Declaration) => ['rejected', 'docs_requested'].includes(d.status)).length,
    };
  }, [data?.items]);

  const getInitials = (name: string) => {
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  const isMetricActive = (statuses: string[] | null) => {
    if (statusFilter === null && statuses === null) return true;
    if (statusFilter === null || statuses === null) return false;
    return JSON.stringify(statusFilter.sort()) === JSON.stringify(statuses.sort());
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* Header */}
      <AppBar position="sticky" elevation={0} sx={{ bgcolor: 'primary.main' }}>
        <Toolbar sx={{ px: { xs: 2, md: 4 } }}>
          <Typography variant="h6" sx={{ flexGrow: 0, mr: 4, fontWeight: 700 }}>
            Таможенные декларации
          </Typography>

          <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', maxWidth: 500, mx: 'auto' }}>
            <TextField
              size="small"
              placeholder="Поиск по номеру, ИНН, контрагенту..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              sx={{
                width: '100%',
                '& .MuiOutlinedInput-root': {
                  bgcolor: 'rgba(255,255,255,0.15)',
                  borderRadius: 2,
                  color: 'white',
                  '& fieldset': { border: 'none' },
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.25)' },
                  '&.Mui-focused': { bgcolor: 'rgba(255,255,255,0.25)' },
                },
                '& .MuiInputAdornment-root': { color: 'rgba(255,255,255,0.7)' },
                '& input::placeholder': { color: 'rgba(255,255,255,0.7)', opacity: 1 },
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
            />
          </Box>

          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setCreateDialogOpen(true)}
            sx={{
              ml: 2,
              bgcolor: 'white',
              color: 'primary.main',
              fontWeight: 600,
              '&:hover': { bgcolor: 'rgba(255,255,255,0.9)' },
              boxShadow: 'none',
            }}
          >
            Создать
          </Button>

          <Tooltip title={meData?.full_name || 'Пользователь'}>
            <IconButton color="inherit" onClick={(e) => setAnchorEl(e.currentTarget)} sx={{ ml: 1 }}>
              <Avatar sx={{ width: 36, height: 36, bgcolor: 'rgba(255,255,255,0.2)', fontSize: 14, fontWeight: 600 }}>
                {meData?.full_name ? getInitials(meData.full_name) : 'А'}
              </Avatar>
            </IconButton>
          </Tooltip>
          <Menu anchorEl={anchorEl} open={!!anchorEl} onClose={() => setAnchorEl(null)}>
            <MenuItem disabled sx={{ opacity: '1 !important' }}>
              <Typography variant="body2" fontWeight={600}>{meData?.full_name || 'Пользователь'}</Typography>
            </MenuItem>
            <MenuItem disabled sx={{ opacity: '0.7 !important' }}>
              <Typography variant="caption">{meData?.email}</Typography>
            </MenuItem>
            <MenuItem onClick={() => { setAnchorEl(null); navigate('/settings'); }}>Настройки</MenuItem>
            <MenuItem onClick={handleLogout}>Выйти</MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      <Box sx={{ px: { xs: 2, md: 4 }, py: 3, maxWidth: 1400, mx: 'auto' }}>
        {/* Metrics */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 2, mb: 3 }}>
          <Card
            onClick={() => handleMetricClick(null)}
            sx={{
              cursor: 'pointer',
              transition: 'all 0.2s',
              border: isMetricActive(null) ? '2px solid' : '2px solid transparent',
              borderColor: isMetricActive(null) ? 'primary.main' : 'transparent',
              '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 },
            }}
          >
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="h4" color="info.main" fontWeight={700}>{metrics.total}</Typography>
                  <Typography variant="body2" color="text.secondary" mt={0.5}>Всего деклараций</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <WorkIcon color="info" />
                </Box>
              </Box>
            </CardContent>
          </Card>

          <Card
            onClick={() => handleMetricClick(['checking_lvl1', 'checking_lvl2', 'final_check'])}
            sx={{
              cursor: 'pointer',
              transition: 'all 0.2s',
              border: isMetricActive(['checking_lvl1', 'checking_lvl2', 'final_check']) ? '2px solid' : '2px solid transparent',
              borderColor: isMetricActive(['checking_lvl1', 'checking_lvl2', 'final_check']) ? 'warning.main' : 'transparent',
              '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 },
            }}
          >
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="h4" color="warning.main" fontWeight={700}>
                    {metrics.checking}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" mt={0.5}>На проверке</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <SendIcon color="warning" />
                </Box>
              </Box>
            </CardContent>
          </Card>

          <Card
            onClick={() => handleMetricClick(['released'])}
            sx={{
              cursor: 'pointer',
              transition: 'all 0.2s',
              border: isMetricActive(['released']) ? '2px solid' : '2px solid transparent',
              borderColor: isMetricActive(['released']) ? 'success.main' : 'transparent',
              '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 },
            }}
          >
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="h4" color="success.main" fontWeight={700}>
                    {metrics.released}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" mt={0.5}>Выпущены</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <CheckIcon color="success" />
                </Box>
              </Box>
            </CardContent>
          </Card>

          <Card
            onClick={() => handleMetricClick(['rejected', 'docs_requested'])}
            sx={{
              cursor: 'pointer',
              transition: 'all 0.2s',
              border: isMetricActive(['rejected', 'docs_requested']) ? '2px solid' : '2px solid transparent',
              borderColor: isMetricActive(['rejected', 'docs_requested']) ? 'error.main' : 'transparent',
              '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 },
            }}
          >
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="h4" color="error.main" fontWeight={700}>
                    {metrics.attention}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" mt={0.5}>Требуют внимания</Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: 'linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <ErrorIcon color="error" />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Table */}
        <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.08)', overflow: 'hidden' }}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>
                  <TableSortLabel
                    active={sortField === 'number_internal'}
                    direction={sortField === 'number_internal' ? sortOrder : 'asc'}
                    onClick={() => handleSort('number_internal')}
                  >
                    Номер ДТ
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === 'created_at'}
                    direction={sortField === 'created_at' ? sortOrder : 'asc'}
                    onClick={() => handleSort('created_at')}
                  >
                    Дата
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === 'type_code'}
                    direction={sortField === 'type_code' ? sortOrder : 'asc'}
                    onClick={() => handleSort('type_code')}
                  >
                    Направление
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === 'status'}
                    direction={sortField === 'status' ? sortOrder : 'asc'}
                    onClick={() => handleSort('status')}
                  >
                    Статус
                  </TableSortLabel>
                </TableCell>
                {hasAnyValue && (
                  <TableCell align="right">
                    <TableSortLabel
                      active={sortField === 'total_invoice_value'}
                      direction={sortField === 'total_invoice_value' ? sortOrder : 'asc'}
                      onClick={() => handleSort('total_invoice_value')}
                    >
                      Стоимость
                    </TableSortLabel>
                  </TableCell>
                )}
                <TableCell align="center">Действия</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton width={120} /></TableCell>
                    <TableCell><Skeleton width={80} /></TableCell>
                    <TableCell><Skeleton width={70} /></TableCell>
                    <TableCell><Skeleton width={120} /></TableCell>
                    {hasAnyValue && <TableCell><Skeleton width={100} /></TableCell>}
                    <TableCell><Skeleton width={80} /></TableCell>
                  </TableRow>
                ))
              ) : filteredAndSortedItems.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={hasAnyValue ? 6 : 5} align="center" sx={{ py: 8 }}>
                    <Box sx={{ textAlign: 'center' }}>
                      <WorkIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                      <Typography variant="h6" color="text.secondary" gutterBottom>
                        {searchQuery || statusFilter ? 'Нет деклараций по фильтрам' : 'Нет деклараций'}
                      </Typography>
                      <Typography variant="body2" color="text.disabled" sx={{ mb: 3 }}>
                        {searchQuery || statusFilter
                          ? 'Попробуйте изменить параметры поиска'
                          : 'Создайте первую декларацию — загрузите PDF-документы и AI заполнит все данные'}
                      </Typography>
                      {!searchQuery && !statusFilter && (
                        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateDialogOpen(true)}>
                          Создать декларацию
                        </Button>
                      )}
                    </Box>
                  </TableCell>
                </TableRow>
              ) : (
                filteredAndSortedItems.map((declaration: Declaration) => (
                  <TableRow
                    key={declaration.id}
                    hover
                    sx={{ cursor: 'pointer', '&:last-child td': { borderBottom: 0 } }}
                    onClick={() => navigate(`/declarations/${declaration.id}/edit`)}
                  >
                    <TableCell>
                      {declaration.number_internal ? (
                        <Typography sx={{ fontWeight: 600, color: 'primary.main', '&:hover': { textDecoration: 'underline' } }}>
                          {declaration.number_internal}
                        </Typography>
                      ) : (
                        <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                          Не присвоен
                        </Typography>
                      )}
                    </TableCell>

                    <TableCell>
                      <Typography variant="body2">{dayjs(declaration.created_at).format('DD.MM.YYYY')}</Typography>
                      <Typography variant="caption" color="text.secondary">{dayjs(declaration.created_at).format('HH:mm')}</Typography>
                    </TableCell>

                    <TableCell>
                      <Chip
                        icon={declaration.type_code?.startsWith('IM') ? <ImportIcon sx={{ fontSize: '14px !important' }} /> : <ExportIcon sx={{ fontSize: '14px !important' }} />}
                        label={declaration.type_code?.startsWith('IM') ? 'Импорт' : 'Экспорт'}
                        size="small"
                        sx={{
                          bgcolor: declaration.type_code?.startsWith('IM') ? '#e3f2fd' : '#fff3e0',
                          color: declaration.type_code?.startsWith('IM') ? '#1565c0' : '#e65100',
                          fontWeight: 500,
                          fontSize: 11,
                          textTransform: 'uppercase',
                          letterSpacing: 0.5,
                          '& .MuiChip-icon': {
                            color: declaration.type_code?.startsWith('IM') ? '#1565c0' : '#e65100',
                          },
                        }}
                      />
                    </TableCell>

                    <TableCell>
                      <StatusChip status={declaration.status} />
                    </TableCell>

                    {hasAnyValue && (
                      <TableCell align="right">
                        <Typography variant="body2" fontWeight={500}>
                          {declaration.total_invoice_value
                            ? `${declaration.currency_code || '₽'} ${Number(declaration.total_invoice_value).toLocaleString('ru-RU', { minimumFractionDigits: 2 })}`
                            : 'Не указана'}
                        </Typography>
                      </TableCell>
                    )}

                    <TableCell align="center">
                      <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                        <Tooltip title="Редактировать">
                          <IconButton
                            size="small"
                            onClick={(e) => { e.stopPropagation(); navigate(`/declarations/${declaration.id}/edit`); }}
                            sx={{ borderRadius: 1.5, '&:hover': { bgcolor: 'primary.light', color: 'primary.main' } }}
                          >
                            <OpenIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Ещё">
                          <IconButton
                            size="small"
                            onClick={(e) => handleRowActionClick(e, declaration.id)}
                            sx={{ borderRadius: 1.5, '&:hover': { bgcolor: 'primary.light', color: 'primary.main' } }}
                          >
                            <MoreVertIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Pagination */}
        {data && (
          <TablePagination
            component="div"
            count={data.total}
            page={page - 1}
            onPageChange={(_, newPage) => setPage(newPage + 1)}
            rowsPerPage={perPage}
            onRowsPerPageChange={(e) => {
              setPerPage(Number(e.target.value));
              setPage(1);
            }}
            rowsPerPageOptions={[10, 20, 50]}
            labelRowsPerPage="Строк на странице:"
            labelDisplayedRows={({ from, to, count }) => `${from}-${to} из ${count !== -1 ? count : `более чем ${to}`}`}
            sx={{ mt: 2, display: 'flex', justifyContent: 'center' }}
          />
        )}

        {/* Row Action Menu */}
        <Menu
          anchorEl={rowActionMenuAnchor}
          open={!!rowActionMenuAnchor}
          onClose={handleRowActionClose}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <MenuItem onClick={() => { handleRowActionClose(); if (rowActionDeclarationId) navigate(`/declarations/${rowActionDeclarationId}/view`); }}>
            <PdfIcon fontSize="small" sx={{ mr: 1 }} />
            Просмотр ДТ
          </MenuItem>
          <MenuItem onClick={handleDuplicate}>
            <CopyIcon fontSize="small" sx={{ mr: 1 }} />
            Дублировать
          </MenuItem>
          <MenuItem onClick={handleExportPdf}>
            <PrintIcon fontSize="small" sx={{ mr: 1 }} />
            Экспорт PDF
          </MenuItem>
          <MenuItem onClick={handleDelete} sx={{ color: 'error.main' }}>
            <DeleteIcon fontSize="small" sx={{ mr: 1 }} />
            Удалить
          </MenuItem>
        </Menu>
      </Box>

      {/* Create dialog */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} PaperProps={{ sx: { borderRadius: 3, minWidth: 400 } }}>
        <DialogTitle sx={{ fontWeight: 600 }}>Создать декларацию</DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel>Тип декларации</InputLabel>
            <Select
              value={newTypeCode}
              onChange={(e) => setNewTypeCode(e.target.value as 'IM40' | 'EX10')}
              label="Тип декларации"
            >
              <MenuItem value="IM40">Импорт (IM40) — выпуск для внутреннего потребления</MenuItem>
              <MenuItem value="EX10">Экспорт (EX10)</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setCreateDialogOpen(false)} sx={{ color: 'text.secondary' }}>Отмена</Button>
          <Button onClick={handleCreate} variant="contained" disabled={createMutation.isPending} sx={{ px: 4 }}>
            Создать
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DeclarationsListPage;
