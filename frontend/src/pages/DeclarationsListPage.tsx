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
  WorkOutline as WorkIcon,
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
  Description as DescriptionIcon,
  WarningAmber as WarningAmberIcon,
  CheckCircle as CheckCircleIcon,
  Send as SendFilledIcon,
} from '@mui/icons-material';
import { getDeclarations, getDeclaration, createDeclaration, deleteDeclaration } from '../api/declarations';
import { getMe } from '../api/auth';
import client from '../api/client';
import AppLayout from '../components/AppLayout';
import StatusChip from '../components/StatusChip';
import KanbanView from '../components/KanbanView';
import { Declaration } from '../types';
import dayjs from 'dayjs';
import 'dayjs/locale/ru';
dayjs.locale('ru');

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
    queryFn: () => getDeclarations({ page, per_page: perPage }),
  });

  const createMutation = useMutation({
    mutationFn: createDeclaration,
    onSuccess: (newDecl) => {
      queryClient.invalidateQueries({ queryKey: ['declarations'] });
      setCreateDialogOpen(false);
      navigate(`/declarations/${newDecl.id}/form-legacy`);
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

  const metrics = useMemo(() => {
    const allItems = data?.items || [];
    return {
      total: allItems.length,
      newCount: allItems.filter((d: Declaration) => d.status === 'new').length,
      checking: allItems.filter((d: Declaration) => d.status === 'requires_attention').length,
      released: allItems.filter((d: Declaration) => d.status === 'ready_to_send').length,
      sent: allItems.filter((d: Declaration) => d.status === 'sent').length,
    };
  }, [data?.items]);

  const isMetricActive = (statuses: string[] | null) => {
    if (statusFilter === null && statuses === null) return true;
    if (statusFilter === null || statuses === null) return false;
    return JSON.stringify(statusFilter.sort()) === JSON.stringify(statuses.sort());
  };

  return (
    <AppLayout breadcrumbs={[{ label: 'Декларации' }]}>
      {/* Page title */}
      <Box sx={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', mb: 2.5 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>Декларации</Typography>
          <Typography sx={{ fontSize: 13, color: '#94a3b8', mt: 0.25 }}>
            {dayjs().format('dddd, D MMMM YYYY')} · {metrics.total} деклараций в работе
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={(_, v) => v && setViewMode(v)}
            size="small"
            sx={{
              '& .MuiToggleButton-root': {
                border: '1px solid rgba(226,232,240,0.6)',
                borderRadius: '10px !important',
                px: 1.5,
                py: 0.5,
                '&.Mui-selected': { bgcolor: 'rgba(241,245,249,1)', color: '#0f172a' },
              },
            }}
          >
            <ToggleButton value="table"><TableViewIcon fontSize="small" /></ToggleButton>
            <ToggleButton value="kanban"><KanbanIcon fontSize="small" /></ToggleButton>
          </ToggleButtonGroup>
          <Button
            size="small"
            onClick={handleExportCSV}
            startIcon={<FileDownloadIcon sx={{ fontSize: '16px !important' }} />}
            sx={{
              textTransform: 'none',
              borderRadius: '10px',
              border: '1px solid rgba(226,232,240,0.6)',
              color: '#475569',
              px: 1.5,
              '&:hover': { bgcolor: 'rgba(248,250,252,0.8)' },
            }}
          >
            Excel
          </Button>
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon sx={{ fontSize: '16px !important' }} />}
            onClick={() => setCreateDialogOpen(true)}
            sx={{
              fontWeight: 500,
              borderRadius: '10px',
              px: 2,
              py: 0.875,
              textTransform: 'none',
              fontSize: 14,
              boxShadow: 'none',
              '&:hover': { boxShadow: '0 2px 8px rgba(0,0,0,0.12)' },
            }}
          >
            Создать декларацию
          </Button>
        </Box>
      </Box>

      {/* Search + Filters */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          placeholder="Поиск по ID, номеру, ТН ВЭД..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          sx={{
            width: { xs: '100%', sm: 360 },
            '& .MuiOutlinedInput-root': {
              borderRadius: '10px',
              bgcolor: 'rgba(248,250,252,0.8)',
              border: '1px solid rgba(226,232,240,0.6)',
              fontSize: 13,
              '& fieldset': { border: 'none' },
              '&:hover': { borderColor: 'rgba(203,213,225,0.8)' },
              '&.Mui-focused': { borderColor: 'rgba(148,163,184,0.6)', bgcolor: 'white', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' },
            },
          }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
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
          sx={{ width: 160, '& .MuiOutlinedInput-root': { borderRadius: '10px', bgcolor: 'white', fontSize: 13 } }}
        />
        <TextField
          size="small"
          type="date"
          label="По дату"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
          InputLabelProps={{ shrink: true }}
          sx={{ width: 160, '& .MuiOutlinedInput-root': { borderRadius: '10px', bgcolor: 'white', fontSize: 13 } }}
        />
        {(dateFrom || dateTo || statusFilter) && (
          <Button
            size="small"
            onClick={() => { setDateFrom(''); setDateTo(''); setStatusFilter(null); setSearchQuery(''); setPage(1); }}
            sx={{ textTransform: 'none', borderRadius: '10px', fontSize: 13, color: '#64748b' }}
          >
            Сбросить
          </Button>
        )}
      </Box>

      {/* Quick Filter Chips */}
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
              variant={isActive ? 'filled' : 'outlined'}
              color={isActive ? 'primary' : 'default'}
              onClick={() => { setStatusFilter(chip.value); setPage(1); }}
              sx={{
                fontWeight: isActive ? 600 : 400,
                fontSize: 13,
                borderRadius: '8px',
                height: 30,
                border: isActive ? undefined : '1px solid rgba(226,232,240,0.8)',
              }}
            />
          );
        })}
      </Box>

      {/* Metrics */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 2, mb: 3 }}>
        {[
          {
            label: 'Новые',
            value: metrics.newCount,
            statuses: ['new'] as string[],
            icon: <DescriptionIcon sx={{ fontSize: 18 }} />,
            iconBg: 'rgba(239,246,255,1)',
            iconColor: '#2563eb',
            borderColor: 'rgba(191,219,254,0.8)',
          },
          {
            label: 'Требуют внимания',
            value: metrics.checking,
            statuses: ['requires_attention'] as string[],
            icon: <WarningAmberIcon sx={{ fontSize: 18 }} />,
            iconBg: 'rgba(255,251,235,1)',
            iconColor: '#d97706',
            borderColor: 'rgba(253,230,138,0.8)',
          },
          {
            label: 'Готово к отправке',
            value: metrics.released,
            statuses: ['ready_to_send'] as string[],
            icon: <CheckCircleIcon sx={{ fontSize: 18 }} />,
            iconBg: 'rgba(236,253,245,1)',
            iconColor: '#059669',
            borderColor: 'rgba(167,243,208,0.8)',
          },
          {
            label: 'Отправлено',
            value: metrics.sent,
            statuses: ['sent'] as string[],
            icon: <SendFilledIcon sx={{ fontSize: 18 }} />,
            iconBg: 'rgba(241,245,249,1)',
            iconColor: '#64748b',
            borderColor: 'rgba(226,232,240,0.6)',
          },
        ].map((m) => (
          <Paper
            key={m.label}
            onClick={() => handleMetricClick(m.statuses)}
            sx={{
              p: 2,
              cursor: 'pointer',
              borderRadius: '14px',
              border: '1px solid',
              borderColor: isMetricActive(m.statuses) ? m.borderColor : 'rgba(226,232,240,0.8)',
              boxShadow: isMetricActive(m.statuses) ? `0 0 0 1px ${m.borderColor}` : 'none',
              transition: 'all 0.15s',
              '&:hover': { boxShadow: '0 1px 4px rgba(0,0,0,0.05)' },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
              <Box>
                <Typography sx={{ fontSize: 13, fontWeight: 500, color: '#64748b', mb: 0.5 }}>{m.label}</Typography>
                <Typography
                  sx={{
                    fontSize: 26,
                    fontWeight: 700,
                    color: '#0f172a',
                    fontVariantNumeric: 'tabular-nums',
                    letterSpacing: '-0.02em',
                    lineHeight: 1.1,
                  }}
                >
                  {m.value}
                </Typography>
              </Box>
              <Box
                sx={{
                  width: 36,
                  height: 36,
                  borderRadius: '10px',
                  bgcolor: m.iconBg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: m.iconColor,
                }}
              >
                {m.icon}
              </Box>
            </Box>
          </Paper>
        ))}
      </Box>

        {viewMode === 'kanban' ? (
          <KanbanView declarations={filteredAndSortedItems} onClickDeclaration={(id) => navigate(`/declarations/${id}/edit`)} />
        ) : (
        <>
        {/* Table */}
        <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.08)', overflowX: 'auto' }}>
          <Table sx={{ minWidth: 700 }}>
            {selectedIds.size > 0 && (
              <Box sx={{ p: 1, bgcolor: '#e3f2fd', display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body2">Выбрано: {selectedIds.size}</Typography>
                <Button size="small" color="error" variant="contained" onClick={handleBulkDelete}>Удалить выбранные</Button>
                <Button size="small" onClick={() => setSelectedIds(new Set())}>Снять выделение</Button>
              </Box>
            )}
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox" sx={{ width: 40, display: { xs: 'none', md: 'table-cell' } }}>
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
                <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>
                  <TableSortLabel
                    active={sortField === 'created_at'}
                    direction={sortField === 'created_at' ? sortOrder : 'asc'}
                    onClick={() => handleSort('created_at')}
                  >
                    Дата
                  </TableSortLabel>
                </TableCell>
                <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>
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
                  <TableCell align="right" sx={{ display: { xs: 'none', md: 'table-cell' } }}>
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
                    <TableCell padding="checkbox" sx={{ display: { xs: 'none', md: 'table-cell' } }}><Skeleton variant="rectangular" width={18} height={18} sx={{ borderRadius: 0.5 }} /></TableCell>
                    <TableCell><Skeleton variant="text" width={120} /></TableCell>
                    <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}><Skeleton variant="text" width={80} /></TableCell>
                    <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}><Skeleton variant="text" width={70} /></TableCell>
                    <TableCell><Skeleton variant="text" width={100} /></TableCell>
                    {hasAnyValue && <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}><Skeleton variant="text" width={90} /></TableCell>}
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
                          : !meData?.company_id
                            ? 'Ваш аккаунт не привязан к компании. Обратитесь к администратору для привязки.'
                            : 'Создайте первую декларацию — загрузите PDF-документы и AI заполнит все данные'}
                      </Typography>
                      {!searchQuery && !statusFilter && meData?.company_id && (
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
                    <TableCell padding="checkbox" onClick={(e) => e.stopPropagation()} sx={{ display: { xs: 'none', md: 'table-cell' } }}>
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

                    <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>
                      <Typography variant="body2">{dayjs(declaration.created_at).format('DD.MM.YYYY')}</Typography>
                      <Typography variant="caption" color="text.secondary">{dayjs(declaration.created_at).format('HH:mm')}</Typography>
                    </TableCell>

                    <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>
                      <Chip
                        icon={declaration.type_code?.startsWith('IM') ? <ImportIcon sx={{ fontSize: '14px !important' }} /> : <ExportIcon sx={{ fontSize: '14px !important' }} />}
                        label={declaration.type_code?.startsWith('IM') ? 'Импорт' : 'Экспорт'}
                        size="small"
                        sx={{
                          bgcolor: declaration.type_code?.startsWith('IM') ? '#e3f2fd' : '#fff3e0',
                          color: declaration.type_code?.startsWith('IM') ? '#1565c0' : '#e65100',
                          fontWeight: 500,
                          fontSize: 12,
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
                      <TableCell align="right" sx={{ display: { xs: 'none', md: 'table-cell' } }}>
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
