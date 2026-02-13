import { useState, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
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
  Tooltip,
  Skeleton,
  TablePagination,
  TableSortLabel,
  Checkbox,
  Snackbar,
  Alert,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import {
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
  CallMade as ImportIcon,
  CallReceived as ExportIcon,
  Delete as DeleteIcon,
  PictureAsPdf as PdfIcon,
  FileDownload as FileDownloadIcon,
  ViewList as TableViewIcon,
  ViewColumn as KanbanIcon,
} from '@mui/icons-material';
import { getDeclarations, getDeclaration, createDeclaration, deleteDeclaration } from '../api/declarations';
import { getMe } from '../api/auth';
import client from '../api/client';
import AppLayout from '../components/AppLayout';
import StatusChip from '../components/StatusChip';
import KanbanView from '../components/KanbanView';
import { Declaration } from '../types';
import dayjs from 'dayjs';

type SortField = 'number_internal' | 'created_at' | 'type_code' | 'status' | 'total_invoice_value';
type SortOrder = 'asc' | 'desc';

const STATUS_PARAM_MAP: Record<string, string[]> = {
  in_progress: ['draft', 'checking_lvl1', 'checking_lvl2', 'final_check'],
  released: ['released'],
  rejected: ['rejected'],
};

const DeclarationsListPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const initialStatus = searchParams.get('status') || '';
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newTypeCode, setNewTypeCode] = useState<'IM40' | 'EX10'>('IM40');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string[] | null>(
    initialStatus ? (STATUS_PARAM_MAP[initialStatus] || [initialStatus]) : null,
  );
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [rowActionMenuAnchor, setRowActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [rowActionDeclarationId, setRowActionDeclarationId] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [viewMode, setViewMode] = useState<'table' | 'kanban'>('table');
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false, message: '', severity: 'success',
  });

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

  const handleDuplicate = async () => {
    if (!rowActionDeclarationId) return;
    handleRowActionClose();
    try {
      const original = await getDeclaration(rowActionDeclarationId);
      const copy = await createDeclaration({
        type_code: original.type_code,
        company_id: original.company_id,
        currency_code: original.currency_code,
        country_dispatch_code: original.country_dispatch_code,
        country_destination_code: original.country_destination_code,
        country_origin_code: original.country_origin_code,
        incoterms_code: original.incoterms_code,
        deal_nature_code: original.deal_nature_code,
        transport_type_border: original.transport_type_border,
        customs_office_code: original.customs_office_code,
      });
      queryClient.invalidateQueries({ queryKey: ['declarations'] });
      setSnackbar({ open: true, message: 'Декларация успешно дублирована', severity: 'success' });
      navigate(`/declarations/${copy.id}/edit`);
    } catch (err: any) {
      console.error('Duplicate declaration error:', err?.response?.data || err);
      setSnackbar({ open: true, message: 'Ошибка при дублировании декларации', severity: 'error' });
    }
  };

  const handleDelete = () => {
    if (!rowActionDeclarationId) return;
    if (window.confirm('Вы уверены, что хотите удалить эту декларацию?')) {
      deleteMutation.mutate(rowActionDeclarationId);
      handleRowActionClose();
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!window.confirm(`Удалить ${selectedIds.size} деклараций?`)) return;
    const ids = Array.from(selectedIds);
    for (let i = 0; i < ids.length; i++) {
      try { await deleteDeclaration(ids[i]); } catch (e) { console.error(e); }
    }
    setSelectedIds(new Set());
    queryClient.invalidateQueries({ queryKey: ['declarations'] });
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    const allIds = filteredAndSortedItems?.map((d: Declaration) => d.id) || [];
    if (selectedIds.size === allIds.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(allIds));
    }
  };

  const handleExportCSV = () => {
    const items = filteredAndSortedItems || [];
    const header = '№;Тип;Статус;Валюта;Сумма;Дата создания\n';
    const rows = items.map((d: any) =>
      `${d.number_internal || ''};${d.type_code || ''};${d.status};${d.currency_code || ''};${d.total_invoice_value || ''};${d.created_at?.slice(0, 10) || ''}`
    ).join('\n');
    const bom = '\uFEFF';
    const blob = new Blob([bom + header + rows], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'declarations.csv'; a.click();
  };

  const handleExportPdf = async () => {
    if (!rowActionDeclarationId) return;
    const declId = rowActionDeclarationId;
    handleRowActionClose();
    try {
      const resp = await client.get(`/declarations/${declId}/export-pdf`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([resp.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `DT_${declId.slice(0, 8)}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
      setSnackbar({ open: true, message: 'PDF экспортирован', severity: 'success' });
    } catch (err: any) {
      console.error('PDF export error:', err?.response?.data || err);
      setSnackbar({ open: true, message: 'Ошибка при экспорте PDF', severity: 'error' });
    }
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

    // Apply date range filter
    if (dateFrom) {
      filtered = filtered.filter((decl: Declaration) => decl.created_at >= dateFrom);
    }
    if (dateTo) {
      filtered = filtered.filter((decl: Declaration) => decl.created_at.slice(0, 10) <= dateTo);
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
  }, [data?.items, searchQuery, statusFilter, dateFrom, dateTo, sortField, sortOrder]);

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

  const isMetricActive = (statuses: string[] | null) => {
    if (statusFilter === null && statuses === null) return true;
    if (statusFilter === null || statuses === null) return false;
    return JSON.stringify(statusFilter.sort()) === JSON.stringify(statuses.sort());
  };

  return (
    <AppLayout breadcrumbs={[{ label: 'Декларации' }]}>
      {/* Search and Create */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, gap: 2 }}>
        <TextField
          size="small"
          placeholder="Поиск по номеру, ИНН, контрагенту..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          sx={{
            width: { xs: '100%', sm: 400 },
            '& .MuiOutlinedInput-root': { borderRadius: 2, bgcolor: 'white' },
          }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />
        <ToggleButtonGroup value={viewMode} exclusive onChange={(_, v) => v && setViewMode(v)} size="small" sx={{ mr: 'auto', ml: 1 }}>
          <ToggleButton value="table"><TableViewIcon fontSize="small" /></ToggleButton>
          <ToggleButton value="kanban"><KanbanIcon fontSize="small" /></ToggleButton>
        </ToggleButtonGroup>
        <Button
          size="small"
          onClick={handleExportCSV}
          startIcon={<FileDownloadIcon />}
          sx={{ textTransform: 'none', borderRadius: 2 }}
        >
          Excel
        </Button>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setCreateDialogOpen(true)}
          sx={{ fontWeight: 600, borderRadius: 2, px: 3, textTransform: 'none' }}
        >
          Создать
        </Button>
      </Box>

      {/* Date Filters */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          type="date"
          label="С даты"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
          InputLabelProps={{ shrink: true }}
          sx={{ width: 180, '& .MuiOutlinedInput-root': { borderRadius: 2, bgcolor: 'white' } }}
        />
        <TextField
          size="small"
          type="date"
          label="По дату"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
          InputLabelProps={{ shrink: true }}
          sx={{ width: 180, '& .MuiOutlinedInput-root': { borderRadius: 2, bgcolor: 'white' } }}
        />
        {(dateFrom || dateTo || statusFilter) && (
          <Button
            size="small"
            onClick={() => { setDateFrom(''); setDateTo(''); setStatusFilter(null); setSearchQuery(''); setPage(1); }}
            sx={{ textTransform: 'none', borderRadius: 2 }}
          >
            Сбросить фильтры
          </Button>
        )}
      </Box>

      {/* Quick Filter Chips */}
      <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        {[
          { label: 'Все', value: null },
          { label: 'Черновики', value: ['draft'] },
          { label: 'На проверке', value: ['checking_lvl1', 'checking_lvl2', 'final_check'] },
          { label: 'Подписано', value: ['signed'] },
          { label: 'Отправлено', value: ['sent'] },
          { label: 'Выпущено', value: ['released'] },
          { label: 'Отклонено', value: ['rejected'] },
        ].map((chip) => (
          <Chip
            key={chip.label}
            label={chip.label}
            size="small"
            variant={JSON.stringify(statusFilter) === JSON.stringify(chip.value) ? 'filled' : 'outlined'}
            color={JSON.stringify(statusFilter) === JSON.stringify(chip.value) ? 'primary' : 'default'}
            onClick={() => { setStatusFilter(chip.value); setPage(1); }}
            sx={{ fontWeight: JSON.stringify(statusFilter) === JSON.stringify(chip.value) ? 700 : 400 }}
          />
        ))}
      </Box>

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

        {viewMode === 'kanban' ? (
          <KanbanView declarations={filteredAndSortedItems} onClickDeclaration={(id) => navigate(`/declarations/${id}/edit`)} />
        ) : (
        <>
        {/* Table */}
        <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.08)', overflow: 'hidden' }}>
          <Table>
            {selectedIds.size > 0 && (
              <Box sx={{ p: 1, bgcolor: '#e3f2fd', display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body2">Выбрано: {selectedIds.size}</Typography>
                <Button size="small" color="error" variant="contained" onClick={handleBulkDelete}>Удалить выбранные</Button>
                <Button size="small" onClick={() => setSelectedIds(new Set())}>Снять выделение</Button>
              </Box>
            )}
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox" sx={{ width: 40 }}>
                  <Checkbox
                    size="small"
                    checked={filteredAndSortedItems?.length > 0 && selectedIds.size === filteredAndSortedItems?.length}
                    indeterminate={selectedIds.size > 0 && selectedIds.size < (filteredAndSortedItems?.length || 0)}
                    onChange={toggleSelectAll}
                  />
                </TableCell>
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
                    <TableCell padding="checkbox"><Skeleton variant="rectangular" width={18} height={18} sx={{ borderRadius: 0.5 }} /></TableCell>
                    <TableCell><Skeleton variant="text" width={120} /></TableCell>
                    <TableCell><Skeleton variant="text" width={80} /></TableCell>
                    <TableCell><Skeleton variant="text" width={70} /></TableCell>
                    <TableCell><Skeleton variant="text" width={100} /></TableCell>
                    {hasAnyValue && <TableCell><Skeleton variant="text" width={90} /></TableCell>}
                    <TableCell><Skeleton variant="text" width={60} /></TableCell>
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
                    selected={selectedIds.has(declaration.id)}
                    sx={{ cursor: 'pointer', '&:last-child td': { borderBottom: 0 } }}
                    onClick={() => navigate(`/declarations/${declaration.id}/edit`)}
                  >
                    <TableCell padding="checkbox" onClick={(e) => e.stopPropagation()}>
                      <Checkbox size="small" checked={selectedIds.has(declaration.id)} onChange={() => toggleSelect(declaration.id)} />
                    </TableCell>
                    <TableCell>
                      {declaration.number_internal ? (
                        <Tooltip title={declaration.number_internal} placement="top" arrow>
                          <Typography noWrap sx={{ maxWidth: 200, fontWeight: 600, color: 'primary.main', '&:hover': { textDecoration: 'underline' } }}>
                            {declaration.number_internal}
                          </Typography>
                        </Tooltip>
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
        </>
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

      {/* Snackbar notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
          severity={snackbar.severity}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </AppLayout>
  );
};

export default DeclarationsListPage;
