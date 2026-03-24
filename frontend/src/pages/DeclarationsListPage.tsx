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
  Description as WorkIcon,
  Warning as WarningIcon,
  CheckCircleOutline as CheckIcon,
  Send as SendIcon,
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
  FiberManualRecord as DotIcon,
} from '@mui/icons-material';
import { getDeclarations, getDeclaration, createDeclaration, deleteDeclaration } from '../api/declarations';
import { getMe } from '../api/auth';
import client from '../api/client';
import AppLayout from '../components/AppLayout';
import StatusChip from '../components/StatusChip';
import MetricCard from '../components/MetricCard';
import KanbanView from '../components/KanbanView';
import { Declaration } from '../types';
import dayjs from 'dayjs';

type SortField = 'number_internal' | 'created_at' | 'type_code' | 'status' | 'total_invoice_value';
type SortOrder = 'asc' | 'desc';

const STATUS_PARAM_MAP: Record<string, string[]> = {
  in_progress: ['new', 'requires_attention'],
  ready: ['ready_to_send'],
  sent: ['sent'],
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
  const [viewMode, setViewMode] = useState<'table' | 'kanban'>('kanban');
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false, message: '', severity: 'success',
  });

  const { data: meData } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
  });

  const { data, isLoading } = useQuery({
    queryKey: ['declarations', page, perPage],
    queryFn: () => getDeclarations({ page, per_page: perPage }),
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
    if (!meData?.company_id) {
      setSnackbar({ open: true, message: 'Ваш аккаунт не привязан к компании. Обратитесь к администратору.', severity: 'error' });
      setCreateDialogOpen(false);
      return;
    }
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
        country_origin_name: original.country_origin_name,
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

  const filteredAndSortedItems = useMemo(() => {
    if (!data?.items) return [];
    let filtered = [...data.items];

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

    if (statusFilter) {
      filtered = filtered.filter((decl: Declaration) => statusFilter.includes(decl.status));
    }

    if (dateFrom) {
      filtered = filtered.filter((decl: Declaration) => decl.created_at >= dateFrom);
    }
    if (dateTo) {
      filtered = filtered.filter((decl: Declaration) => decl.created_at.slice(0, 10) <= dateTo);
    }

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

  const hasAnyValue = useMemo(() => {
    return filteredAndSortedItems.some((decl: Declaration) => decl.total_invoice_value != null);
  }, [filteredAndSortedItems]);

  const metrics = useMemo(() => {
    const allItems = data?.items || [];
    return {
      total: allItems.length,
      new: allItems.filter((d: Declaration) => d.status === 'new').length,
      requires_attention: allItems.filter((d: Declaration) => d.status === 'requires_attention').length,
      ready_to_send: allItems.filter((d: Declaration) => d.status === 'ready_to_send').length,
      sent: allItems.filter((d: Declaration) => d.status === 'sent').length,
    };
  }, [data?.items]);

  const todayStr = dayjs().format('dddd, D MMMM YYYY');

  return (
    <AppLayout noPadding>
      <Box sx={{ maxWidth: 1440, mx: 'auto', px: { xs: 2, md: 3 }, pt: 2.5, pb: 3 }}>
        {/* Page title + date + actions */}
        <Box sx={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', mb: 2.5 }}>
          <Box>
            <Typography sx={{ fontSize: 20, fontWeight: 700, color: 'text.primary', letterSpacing: '-0.02em' }}>
              Декларации
            </Typography>
            <Typography sx={{ fontSize: 12, color: 'text.secondary', mt: 0.25 }}>
              {todayStr} · {metrics.total} деклараций в работе
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <DotIcon sx={{ fontSize: 8, color: '#10b981', animation: 'pulse 2s infinite' }} />
              <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>Обновлено только что</Typography>
            </Box>
          </Box>
        </Box>

        {/* KPI Metrics */}
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2, mb: 3 }}>
          <MetricCard
            icon={<WorkIcon sx={{ fontSize: 18, color: '#2563eb' }} />}
            label="Новые"
            value={metrics.new}
            accentColor="rgba(191,219,254,0.8)"
            iconBg="#eff6ff"
            onClick={() => handleMetricClick(['new'])}
          />
          <MetricCard
            icon={<WarningIcon sx={{ fontSize: 18, color: '#d97706' }} />}
            label="Требуют внимания"
            value={metrics.requires_attention}
            accentColor="rgba(253,230,138,0.8)"
            iconBg="#fffbeb"
            onClick={() => handleMetricClick(['requires_attention'])}
          />
          <MetricCard
            icon={<CheckIcon sx={{ fontSize: 18, color: '#059669' }} />}
            label="Готово к отправке"
            value={metrics.ready_to_send}
            accentColor="rgba(167,243,208,0.8)"
            iconBg="#ecfdf5"
            onClick={() => handleMetricClick(['ready_to_send'])}
          />
          <MetricCard
            icon={<SendIcon sx={{ fontSize: 18, color: '#64748b' }} />}
            label="Отправлено"
            value={metrics.sent}
            accentColor="rgba(226,232,240,0.6)"
            iconBg="#f1f5f9"
            onClick={() => handleMetricClick(['sent'])}
          />
        </Box>

        {/* Toolbar: search, filters, view toggle, actions */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2, gap: 1.5, flexWrap: 'wrap' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flex: 1 }}>
            <TextField
              size="small"
              placeholder="Поиск по номеру, типу..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              sx={{
                width: { xs: '100%', sm: 320 },
                '& .MuiOutlinedInput-root': {
                  bgcolor: 'white',
                  borderColor: '#e2e8f0',
                },
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ fontSize: 18, color: '#94a3b8' }} />
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              size="small"
              type="date"
              label="С даты"
              value={dateFrom}
              onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
              InputLabelProps={{ shrink: true }}
              sx={{ width: 150, '& .MuiOutlinedInput-root': { bgcolor: 'white' } }}
            />
            <TextField
              size="small"
              type="date"
              label="По дату"
              value={dateTo}
              onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
              InputLabelProps={{ shrink: true }}
              sx={{ width: 150, '& .MuiOutlinedInput-root': { bgcolor: 'white' } }}
            />
            {(dateFrom || dateTo || statusFilter) && (
              <Button
                size="small"
                onClick={() => { setDateFrom(''); setDateTo(''); setStatusFilter(null); setSearchQuery(''); setPage(1); }}
                sx={{ fontSize: 11, color: 'text.secondary' }}
              >
                Сбросить
              </Button>
            )}
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ToggleButtonGroup
              value={viewMode}
              exclusive
              onChange={(_, v) => v && setViewMode(v)}
              size="small"
              sx={{
                '& .MuiToggleButton-root': {
                  borderColor: '#e2e8f0',
                  px: 1.5,
                  '&.Mui-selected': {
                    bgcolor: '#f1f5f9',
                    color: '#0f172a',
                  },
                },
              }}
            >
              <ToggleButton value="kanban">
                <KanbanIcon sx={{ fontSize: 18 }} />
              </ToggleButton>
              <ToggleButton value="table">
                <TableViewIcon sx={{ fontSize: 18 }} />
              </ToggleButton>
            </ToggleButtonGroup>

            <Tooltip title="Экспорт CSV">
              <IconButton
                size="small"
                onClick={handleExportCSV}
                sx={{
                  bgcolor: 'white',
                  border: '1px solid #e2e8f0',
                  borderRadius: '10px',
                  '&:hover': { bgcolor: '#f8fafc' },
                }}
              >
                <FileDownloadIcon sx={{ fontSize: 18, color: '#64748b' }} />
              </IconButton>
            </Tooltip>

            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setCreateDialogOpen(true)}
              size="small"
              sx={{
                bgcolor: '#0f172a',
                color: 'white',
                fontWeight: 600,
                px: 2.5,
                py: 0.75,
                '&:hover': { bgcolor: '#1e293b' },
              }}
            >
              Создать декларацию
            </Button>
          </Box>
        </Box>

        {/* Status filter chips */}
        <Box sx={{ display: 'flex', gap: 0.75, mb: 2.5, flexWrap: 'wrap' }}>
          {[
            { label: 'Все', value: null },
            { label: 'Новые', value: ['new'] },
            { label: 'Требуют внимания', value: ['requires_attention'] },
            { label: 'Готовы к отправке', value: ['ready_to_send'] },
            { label: 'Отправлено', value: ['sent'] },
          ].map((chip) => {
            const isActive = JSON.stringify(statusFilter) === JSON.stringify(chip.value);
            return (
              <Chip
                key={chip.label}
                label={chip.label}
                size="small"
                onClick={() => { setStatusFilter(chip.value); setPage(1); }}
                sx={{
                  fontWeight: isActive ? 600 : 400,
                  fontSize: 11,
                  bgcolor: isActive ? '#0f172a' : 'white',
                  color: isActive ? 'white' : '#64748b',
                  border: isActive ? 'none' : '1px solid #e2e8f0',
                  '&:hover': {
                    bgcolor: isActive ? '#1e293b' : '#f8fafc',
                  },
                }}
              />
            );
          })}
        </Box>

        {/* Kanban or Table */}
        {viewMode === 'kanban' ? (
          <KanbanView
            declarations={filteredAndSortedItems}
            onClickDeclaration={(id) => navigate(`/declarations/${id}/edit`)}
          />
        ) : (
          <>
            <TableContainer
              component={Paper}
              sx={{
                borderRadius: '12px',
                border: '1px solid #e2e8f0',
                boxShadow: 'none',
                overflow: 'hidden',
              }}
            >
              <Table>
                {selectedIds.size > 0 && (
                  <Box sx={{ p: 1, bgcolor: '#eff6ff', display: 'flex', alignItems: 'center', gap: 2, borderBottom: '1px solid #bfdbfe' }}>
                    <Typography sx={{ fontSize: 12, fontWeight: 500, color: '#1e40af' }}>
                      Выбрано: {selectedIds.size}
                    </Typography>
                    <Button size="small" color="error" variant="contained" onClick={handleBulkDelete} sx={{ fontSize: 11 }}>
                      Удалить выбранные
                    </Button>
                    <Button size="small" onClick={() => setSelectedIds(new Set())} sx={{ fontSize: 11 }}>
                      Снять выделение
                    </Button>
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
                    <TableCell align="center" sx={{ width: 100 }}>Действия</TableCell>
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
                      <TableCell colSpan={hasAnyValue ? 7 : 6} align="center" sx={{ py: 8 }}>
                        <Box sx={{ textAlign: 'center' }}>
                          <Box sx={{ width: 56, height: 56, borderRadius: '50%', bgcolor: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', mx: 'auto', mb: 2 }}>
                            <WorkIcon sx={{ fontSize: 28, color: '#cbd5e1' }} />
                          </Box>
                          <Typography sx={{ fontSize: 15, fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>
                            {searchQuery || statusFilter ? 'Нет деклараций по фильтрам' : 'Нет деклараций'}
                          </Typography>
                          <Typography sx={{ fontSize: 12, color: '#94a3b8', mb: 3 }}>
                            {searchQuery || statusFilter
                              ? 'Попробуйте изменить параметры поиска'
                              : !meData?.company_id
                                ? 'Ваш аккаунт не привязан к компании'
                                : 'Создайте первую декларацию'}
                          </Typography>
                          {!searchQuery && !statusFilter && meData?.company_id && (
                            <Button
                              variant="contained"
                              startIcon={<AddIcon />}
                              onClick={() => setCreateDialogOpen(true)}
                              sx={{ bgcolor: '#0f172a', '&:hover': { bgcolor: '#1e293b' } }}
                            >
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
                            <Typography noWrap sx={{ maxWidth: 200, fontWeight: 600, fontSize: 13, color: '#0f172a' }}>
                              {declaration.number_internal}
                            </Typography>
                          ) : (
                            <Typography sx={{ fontSize: 12, color: '#94a3b8', fontStyle: 'italic' }}>
                              Не присвоен
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          <Typography sx={{ fontSize: 13 }}>{dayjs(declaration.created_at).format('DD.MM.YYYY')}</Typography>
                          <Typography sx={{ fontSize: 11, color: '#94a3b8' }}>{dayjs(declaration.created_at).format('HH:mm')}</Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            icon={declaration.type_code?.startsWith('IM') ? <ImportIcon sx={{ fontSize: '13px !important' }} /> : <ExportIcon sx={{ fontSize: '13px !important' }} />}
                            label={declaration.type_code?.startsWith('IM') ? 'Импорт' : 'Экспорт'}
                            size="small"
                            sx={{
                              bgcolor: declaration.type_code?.startsWith('IM') ? '#eff6ff' : '#fffbeb',
                              color: declaration.type_code?.startsWith('IM') ? '#1e40af' : '#92400e',
                              border: `1px solid ${declaration.type_code?.startsWith('IM') ? '#bfdbfe' : '#fde68a'}`,
                              fontWeight: 500,
                              fontSize: 10,
                              '& .MuiChip-icon': {
                                color: declaration.type_code?.startsWith('IM') ? '#1e40af' : '#92400e',
                              },
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <StatusChip status={declaration.status} />
                        </TableCell>
                        {hasAnyValue && (
                          <TableCell align="right">
                            <Typography sx={{ fontSize: 13, fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>
                              {declaration.total_invoice_value
                                ? `${declaration.currency_code || '₽'} ${Number(declaration.total_invoice_value).toLocaleString('ru-RU', { minimumFractionDigits: 2 })}`
                                : '—'}
                            </Typography>
                          </TableCell>
                        )}
                        <TableCell align="center">
                          <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                            <Tooltip title="Открыть">
                              <IconButton
                                size="small"
                                onClick={(e) => { e.stopPropagation(); navigate(`/declarations/${declaration.id}/edit`); }}
                                sx={{
                                  borderRadius: '8px',
                                  '&:hover': { bgcolor: '#f1f5f9' },
                                }}
                              >
                                <OpenIcon sx={{ fontSize: 16, color: '#64748b' }} />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Ещё">
                              <IconButton
                                size="small"
                                onClick={(e) => handleRowActionClick(e, declaration.id)}
                                sx={{
                                  borderRadius: '8px',
                                  '&:hover': { bgcolor: '#f1f5f9' },
                                }}
                              >
                                <MoreVertIcon sx={{ fontSize: 16, color: '#64748b' }} />
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
                sx={{ mt: 2 }}
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
          slotProps={{
            paper: {
              sx: {
                borderRadius: '12px',
                boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
                border: '1px solid #e2e8f0',
                mt: 0.5,
              },
            },
          }}
        >
          <MenuItem
            onClick={() => { handleRowActionClose(); if (rowActionDeclarationId) navigate(`/declarations/${rowActionDeclarationId}/view`); }}
            sx={{ fontSize: 13, gap: 1.5, py: 1 }}
          >
            <PdfIcon sx={{ fontSize: 16, color: '#64748b' }} />
            Просмотр ДТ
          </MenuItem>
          <MenuItem onClick={handleDuplicate} sx={{ fontSize: 13, gap: 1.5, py: 1 }}>
            <CopyIcon sx={{ fontSize: 16, color: '#64748b' }} />
            Дублировать
          </MenuItem>
          <MenuItem onClick={handleExportPdf} sx={{ fontSize: 13, gap: 1.5, py: 1 }}>
            <PrintIcon sx={{ fontSize: 16, color: '#64748b' }} />
            Экспорт PDF
          </MenuItem>
          <MenuItem onClick={handleDelete} sx={{ fontSize: 13, gap: 1.5, py: 1, color: '#dc2626' }}>
            <DeleteIcon sx={{ fontSize: 16 }} />
            Удалить
          </MenuItem>
        </Menu>

        {/* Create dialog */}
        <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="xs" fullWidth>
          <DialogTitle sx={{ fontWeight: 600, fontSize: 16 }}>Создать декларацию</DialogTitle>
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
            <Button onClick={() => setCreateDialogOpen(false)} sx={{ color: '#64748b' }}>
              Отмена
            </Button>
            <Button
              onClick={handleCreate}
              variant="contained"
              disabled={createMutation.isPending}
              sx={{ bgcolor: '#0f172a', '&:hover': { bgcolor: '#1e293b' }, px: 3 }}
            >
              Создать
            </Button>
          </DialogActions>
        </Dialog>

        {/* Snackbar */}
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
            sx={{ width: '100%', borderRadius: '10px' }}
          >
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Box>
    </AppLayout>
  );
};

export default DeclarationsListPage;
