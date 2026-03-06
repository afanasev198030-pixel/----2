import { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  CircularProgress,
  Alert,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableHead,
  TableCell,
  TableRow,
  IconButton,
  Collapse,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  Description as FileIcon,
  CheckCircle as CheckIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  AutoAwesome as AiIcon,
  Warning as WarningIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
} from '@mui/icons-material';
import { parseSmartDocument, ParseSmartResult, classifyHS, HSSuggestion } from '../api/ai';
import client from '../api/client';

interface DocumentUploadPanelProps {
  declarationId?: string;
  onParsedData?: (data: ParseSmartResult) => void | Promise<void>;
  onCreateDeclaration?: (data: ParseSmartResult) => void | Promise<void>;
}

const DocumentUploadPanel = ({ declarationId, onParsedData, onCreateDeclaration }: DocumentUploadPanelProps) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressStep, setProgressStep] = useState('');
  const [progressDetail, setProgressDetail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ParseSmartResult | null>(null);
  const [editableResult, setEditableResult] = useState<ParseSmartResult | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [hsOptions, setHsOptions] = useState<Record<number, HSSuggestion[]>>({});
  const [hsOptionsLoading, setHsOptionsLoading] = useState<Record<number, boolean>>({});
  const [expandedHsRows, setExpandedHsRows] = useState<Record<number, boolean>>({});

  const handleFilesSelected = useCallback((newFiles: FileList | File[]) => {
    const fileArray = Array.from(newFiles).filter(
      (f) => f.type === 'application/pdf' || f.type.startsWith('image/') || f.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' || f.type === 'application/vnd.ms-excel' || f.name.endsWith('.xlsx') || f.name.endsWith('.xls')
    );
    setSelectedFiles((prev) => [...prev, ...fileArray]);
    setError(null);
  }, []);

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.dataTransfer.files.length > 0) {
        handleFilesSelected(e.dataTransfer.files);
      }
    },
    [handleFilesSelected]
  );

  const handleProcess = useCallback(async () => {
    if (selectedFiles.length === 0) return;

    setIsProcessing(true);
    setError(null);
    setResult(null);
    setEditableResult(null);
    setApplyError(null);
    setHsOptions({});
    setHsOptionsLoading({});
    setExpandedHsRows({});
    setProgress(5);
    setProgressStep('upload');
    setProgressDetail('Загрузка файлов на сервер...');
    setElapsedTime(0);

    // Timer
    const startTime = Date.now();
    const timer = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    try {
      // Start parse (this returns immediately with request_id or blocks)
      const parsePromise = parseSmartDocument(selectedFiles, declarationId);

      // Poll progress every 2 seconds
      let requestId = '';
      const pollInterval = setInterval(async () => {
        if (!requestId) return;
        try {
          const resp = await client.get(`/ai/parse-progress/${requestId}`);
          const p = resp.data;
          if (p.progress > 0) setProgress(p.progress);
          if (p.step) setProgressStep(p.step);
          if (p.detail) setProgressDetail(p.detail);
        } catch (e) { /* ignore poll errors */ }
      }, 2000);

      // Simulate initial progress while waiting
      setProgress(10);
      setProgressDetail('Отправка файлов...');
      setTimeout(() => { setProgress(15); setProgressDetail('Сервер обрабатывает документы...'); }, 3000);
      setTimeout(() => { setProgress(20); setProgressStep('parsing'); setProgressDetail('OCR распознавание текста...'); }, 6000);
      setTimeout(() => { setProgress(30); setProgressDetail('AI анализирует документы...'); }, 12000);
      setTimeout(() => { setProgress(45); setProgressDetail('Извлечение данных из инвойса...'); }, 20000);
      setTimeout(() => { setProgress(55); setProgressDetail('Обработка контракта и упаковочного листа...'); }, 35000);
      setTimeout(() => { setProgress(65); setProgressDetail('Классификация ТН ВЭД...'); }, 50000);
      setTimeout(() => { setProgress(75); setProgressDetail('Оценка рисков СУР...'); }, 70000);
      setTimeout(() => { setProgress(85); setProgressDetail('Поиск прецедентов...'); }, 90000);

      const parsed = await parsePromise;

      clearInterval(pollInterval);
      if (parsed.request_id) requestId = parsed.request_id;

      const hasItems = (parsed.items || []).length > 0;
      const itemsWithHs = (parsed.items || []).filter((it: any) => it.hs_code && it.hs_code.length >= 6).length;
      const totalItems = (parsed.items || []).length;

      setProgress(100);
      setProgressStep('complete');
      setResult(parsed);
      setEditableResult({
        ...parsed,
        items: (parsed.items || []).map((it: any) => ({ ...it })),
      });

      if (!hasItems) {
        setProgressDetail('Документы распознаны, но позиции не найдены. Проверьте API-ключ в Настройках.');
        setError('AI не смог извлечь позиции. Возможно, API-ключ LLM невалидный или истёк. Перейдите в Настройки и проверьте ключ.');
      } else if (itemsWithHs === 0 && totalItems > 0) {
        setProgressDetail(`Найдено ${totalItems} позиций, но коды ТН ВЭД не определены.`);
        setError(`Коды ТН ВЭД не определены для ${totalItems} позиций. Вероятная причина: API-ключ LLM невалидный. Проверьте ключ в Настройках.`);
      } else if (itemsWithHs < totalItems) {
        setProgressDetail(`Готово! ${itemsWithHs} из ${totalItems} позиций с кодами ТН ВЭД.`);
      } else {
        setProgressDetail('Готово! Данные распознаны.');
      }

      setTimeout(() => setShowPreview(true), 500);

    } catch (err: any) {
      console.error('Smart parse error:', err);
      const msg = err?.response?.data?.detail || err?.message || 'Ошибка';
      if (msg.includes('401') || msg.includes('Authentication') || msg.includes('auth')) {
        setError('API-ключ LLM невалидный или истёк. Перейдите в Настройки и обновите ключ.');
      } else if (msg.includes('timeout') || msg.includes('Network Error')) {
        setError('Таймаут: обработка заняла слишком много времени. Попробуйте загрузить меньше файлов или проверьте API-ключ в Настройках.');
      } else {
        setError(msg);
      }
    } finally {
      clearInterval(timer);
      setIsProcessing(false);
    }
  }, [selectedFiles, declarationId]);

  const handleApply = useCallback(async () => {
    const payload = editableResult || result;
    if (!payload || !onParsedData) return;
    setApplyError(null);
    setIsApplying(true);
    try {
      await Promise.resolve(onParsedData(payload));
      setShowPreview(false);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Ошибка применения данных';
      setApplyError(msg);
    } finally {
      setIsApplying(false);
    }
  }, [editableResult, result, onParsedData]);

  const handleCreateDeclaration = useCallback(async () => {
    const payload = editableResult || result;
    if (!payload || !onCreateDeclaration) return;
    setApplyError(null);
    setIsApplying(true);
    try {
      await Promise.resolve(onCreateDeclaration(payload));
      setShowPreview(false);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Ошибка создания декларации';
      setApplyError(msg);
    } finally {
      setIsApplying(false);
    }
  }, [editableResult, result, onCreateDeclaration]);

  const loadSimilarCodes = useCallback(
    async (index: number, item: ParseSmartResult['items'][number]) => {
      const description = item.description || item.commercial_name || '';
      if (!description || description.length < 3) return;
      setHsOptionsLoading((prev) => ({ ...prev, [index]: true }));
      try {
        const suggestions = await classifyHS(description, editableResult?.country_origin, undefined, declarationId);
        setHsOptions((prev) => ({ ...prev, [index]: suggestions.slice(0, 8) }));
        setExpandedHsRows((prev) => ({ ...prev, [index]: true }));
      } catch (e: any) {
        const msg = e?.response?.data?.detail || e?.message || 'Ошибка подбора кода';
        setApplyError(msg);
      } finally {
        setHsOptionsLoading((prev) => ({ ...prev, [index]: false }));
      }
    },
    [editableResult?.country_origin, declarationId]
  );

  const selectHsCode = useCallback((index: number, option: HSSuggestion) => {
    setEditableResult((prev) => {
      if (!prev) return prev;
      const items = [...(prev.items || [])];
      if (!items[index]) return prev;
      items[index] = {
        ...items[index],
        hs_code: option.hs_code,
        hs_code_name: option.name_ru,
        hs_confidence: option.confidence,
      };
      return { ...prev, items };
    });
  }, []);

  useEffect(() => {
    if (!showPreview || !editableResult?.items?.length) return;

    // 1) seed options from backend candidates (already computed during parse-smart)
    setHsOptions((prev) => {
      let changed = false;
      const next = { ...prev };
      editableResult.items.forEach((item, i) => {
        if (next[i]?.length) return;
        const seeded = (item.hs_candidates || []).filter((x) => !!x?.hs_code);
        if (seeded.length) {
          next[i] = seeded.slice(0, 8);
          changed = true;
        }
      });
      return changed ? next : prev;
    });

    // 2) auto-load similar codes for first rows so the user sees it immediately
    const maxAutoRows = Math.min(editableResult.items.length, 6);
    for (let i = 0; i < maxAutoRows; i += 1) {
      const item = editableResult.items[i];
      const description = item?.description || item?.commercial_name || '';
      if (!description || description.length < 3) continue;
      if (hsOptions[i]?.length || hsOptionsLoading[i]) continue;
      void loadSimilarCodes(i, item);
    }
  }, [showPreview, editableResult, hsOptions, hsOptionsLoading, loadSimilarCodes]);

  const confidenceColor = (c: number) => {
    if (c >= 0.8) return 'success';
    if (c >= 0.5) return 'warning';
    return 'error';
  };

  return (
    <>
      <Paper
        sx={{
          mb: 2,
          overflow: 'hidden',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 2,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 2,
            py: 1,
            bgcolor: '#f0f7ff',
            cursor: 'pointer',
          }}
          onClick={() => setExpanded(!expanded)}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <AiIcon sx={{ color: 'primary.main', fontSize: 20 }} />
            <Typography variant="subtitle2" fontWeight={600} color="primary.main">
              Загрузить документы для автозаполнения (AI)
            </Typography>
          </Box>
          <IconButton size="small">
            {expanded ? <CollapseIcon /> : <ExpandIcon />}
          </IconButton>
        </Box>

        <Collapse in={expanded}>
          <Box sx={{ p: 2 }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}

            {isProcessing ? (
              <Box sx={{ py: 3 }}>
                {/* Progress header */}
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <CircularProgress size={20} />
                    <Typography variant="subtitle2" color="primary.main" fontWeight={600}>
                      {progressStep === 'upload' ? 'Загрузка' :
                       progressStep === 'parsing' ? 'Распознавание' :
                       progressStep === 'compiling' ? 'Компиляция' :
                       progressStep === 'classifying' ? 'Классификация ТН ВЭД' :
                       progressStep === 'risks' ? 'Оценка рисков' :
                       progressStep === 'precedents' ? 'Поиск прецедентов' :
                       progressStep === 'complete' ? 'Готово!' :
                       'Обработка'}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Typography variant="caption" color="text.secondary">
                      {Math.floor(elapsedTime / 60)}:{(elapsedTime % 60).toString().padStart(2, '0')}
                    </Typography>
                    <Typography variant="body2" fontWeight={600} color="primary.main">
                      {progress}%
                    </Typography>
                  </Box>
                </Box>

                {/* Progress bar */}
                <LinearProgress
                  variant="determinate"
                  value={progress}
                  sx={{ borderRadius: 1, height: 8, mb: 1 }}
                />

                {/* Detail text */}
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  {progressDetail}
                </Typography>

                {/* Steps indicator */}
                <Box sx={{ display: 'flex', gap: 0.5, mt: 2, flexWrap: 'wrap' }}>
                  {['Загрузка', 'OCR', 'Инвойс', 'Контракт', 'PL', 'ТН ВЭД', 'Риски', 'Готово'].map((s, i) => {
                    const stepPct = [5, 15, 30, 45, 55, 70, 85, 100];
                    const done = progress >= stepPct[i];
                    const active = progress >= stepPct[i] - 10 && progress < stepPct[i];
                    return (
                      <Chip
                        key={s}
                        label={s}
                        size="small"
                        color={done ? 'success' : active ? 'primary' : 'default'}
                        variant={done ? 'filled' : 'outlined'}
                        sx={{ fontSize: 10 }}
                      />
                    );
                  })}
                </Box>
              </Box>
            ) : (
              <>
                {/* Drop zone */}
                <Box
                  onDragEnter={() => setIsDragOver(true)}
                  onDragLeave={() => setIsDragOver(false)}
                  onDrop={(e) => { e.preventDefault(); setIsDragOver(false); if (e.dataTransfer.files.length) handleFilesSelected(e.dataTransfer.files); }}
                  onDragOver={(e) => e.preventDefault()}
                  sx={{
                    border: '2px dashed',
                    borderColor: isDragOver ? 'success.main' : selectedFiles.length > 0 ? 'success.light' : 'primary.light',
                    bgcolor: isDragOver ? '#e8f5e9' : 'transparent',
                    borderRadius: 2,
                    p: 3,
                    textAlign: 'center',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    transform: isDragOver ? 'scale(1.02)' : 'none',
                    '&:hover': {
                      borderColor: 'primary.main',
                      bgcolor: '#f8fbff',
                    },
                    '&:active': {
                      bgcolor: '#e8f0fe',
                    },
                  }}
                >
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png,.xlsx,.xls"
                    multiple
                    style={{ display: 'none' }}
                    id="upload-smart"
                    onChange={(e) => {
                      if (e.target.files) handleFilesSelected(e.target.files);
                      e.target.value = '';
                    }}
                  />
                  <label htmlFor="upload-smart" style={{ cursor: 'pointer' }}>
                    <UploadIcon sx={{ fontSize: 40, color: 'primary.main', mb: 1 }} />
                    <Typography variant="body1" fontWeight={600} color="primary.main">
                      Перетащите файлы сюда
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      Invoice, Contract, Packing List, AWB, Specification (PDF, Excel)
                    </Typography>
                    <Button component="span" size="small" variant="outlined" startIcon={<AddIcon />}>
                      Выбрать файлы
                    </Button>
                  </label>
                </Box>

                {/* Selected files list */}
                {selectedFiles.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                      Выбрано файлов: {selectedFiles.length}
                    </Typography>
                    <List dense sx={{ bgcolor: '#fafafa', borderRadius: 1 }}>
                      {selectedFiles.map((file, i) => (
                        <ListItem
                          key={i}
                          secondaryAction={
                            <IconButton edge="end" size="small" onClick={() => handleRemoveFile(i)}>
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          }
                        >
                          <ListItemIcon sx={{ minWidth: 32 }}>
                            <FileIcon fontSize="small" color="primary" />
                          </ListItemIcon>
                          <ListItemText
                            primary={file.name}
                            secondary={`${(file.size / 1024).toFixed(0)} KB`}
                            primaryTypographyProps={{ variant: 'body2' }}
                            secondaryTypographyProps={{ variant: 'caption' }}
                          />
                        </ListItem>
                      ))}
                    </List>

                    <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                      <Button
                        variant="contained"
                        startIcon={<AiIcon />}
                        onClick={handleProcess}
                        disabled={selectedFiles.length === 0}
                      >
                        Распознать документы
                      </Button>
                      <Button
                        variant="outlined"
                        color="inherit"
                        onClick={() => setSelectedFiles([])}
                      >
                        Очистить
                      </Button>
                    </Box>
                  </Box>
                )}
              </>
            )}

            {result && !showPreview && (
              <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <CheckIcon color="success" fontSize="small" />
                <Typography variant="body2" color="success.main">
                  Документы распознаны
                </Typography>
                <Button size="small" onClick={() => setShowPreview(true)}>
                  Просмотреть результат
                </Button>
              </Box>
            )}
          </Box>
        </Collapse>
      </Paper>

      {/* Preview Dialog */}
      <Dialog
        open={showPreview && !!(editableResult || result)}
        onClose={() => { if (!isApplying) setShowPreview(false); }}
        maxWidth="lg"
        fullWidth
        PaperProps={{ sx: { borderRadius: 3 } }}
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AiIcon color="primary" />
          Результат распознавания
          {(editableResult || result)?.confidence != null && (
            <Chip
              label={`Точность: ${Math.round((((editableResult || result)?.confidence || 0) * 100))}%`}
              size="small"
              color={confidenceColor((editableResult || result)?.confidence || 0)}
            />
          )}
          {(editableResult || result)?.risk_score != null && ((editableResult || result)?.risk_score || 0) > 0 && (
            <Chip
              icon={<WarningIcon />}
              label={`Риск: ${(editableResult || result)?.risk_score}`}
              size="small"
              color={((editableResult || result)?.risk_score || 0) > 50 ? 'error' : ((editableResult || result)?.risk_score || 0) > 25 ? 'warning' : 'default'}
            />
          )}
        </DialogTitle>

        <DialogContent dividers>
          {(editableResult || result) && (
            <>
              {applyError && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setApplyError(null)}>
                  {applyError}
                </Alert>
              )}
              {/* General info */}
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Общие данные
              </Typography>
              <Table size="small" sx={{ mb: 3 }}>
                <TableBody>
                  {(editableResult || result)?.invoice_number && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600, width: 220 }}>Номер инвойса</TableCell>
                      <TableCell>{(editableResult || result)?.invoice_number}</TableCell>
                    </TableRow>
                  )}
                  {(editableResult || result)?.invoice_date && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Дата</TableCell>
                      <TableCell>{(editableResult || result)?.invoice_date}</TableCell>
                    </TableRow>
                  )}
                  {(editableResult || result)?.seller?.name && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Продавец (графа 2)</TableCell>
                      <TableCell>
                        {(editableResult || result)?.seller?.name}
                        {(editableResult || result)?.seller?.country_code && ` [${(editableResult || result)?.seller?.country_code}]`}
                      </TableCell>
                    </TableRow>
                  )}
                  {(editableResult || result)?.buyer?.name && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Покупатель (графа 8)</TableCell>
                      <TableCell>
                        {(editableResult || result)?.buyer?.name}
                        {(editableResult || result)?.buyer?.country_code && ` [${(editableResult || result)?.buyer?.country_code}]`}
                      </TableCell>
                    </TableRow>
                  )}
                  {(editableResult || result)?.currency && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Валюта (графа 22)</TableCell>
                      <TableCell>{(editableResult || result)?.currency}</TableCell>
                    </TableRow>
                  )}
                  {(editableResult || result)?.total_amount != null && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Сумма (графа 22)</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: 'primary.main' }}>
                        {(editableResult || result)?.currency || ''} {Number((editableResult || result)?.total_amount).toLocaleString('ru-RU', { minimumFractionDigits: 2 })}
                      </TableCell>
                    </TableRow>
                  )}
                  {(editableResult || result)?.incoterms && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Incoterms (графа 20)</TableCell>
                      <TableCell>{(editableResult || result)?.incoterms}</TableCell>
                    </TableRow>
                  )}
                  {(editableResult || result)?.contract_number && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Контракт</TableCell>
                      <TableCell>{(editableResult || result)?.contract_number}</TableCell>
                    </TableRow>
                  )}
                  {(editableResult || result)?.total_gross_weight != null && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Вес брутто (графа 35)</TableCell>
                      <TableCell>{(editableResult || result)?.total_gross_weight} кг</TableCell>
                    </TableRow>
                  )}
                  {(editableResult || result)?.total_net_weight != null && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Вес нетто (графа 38)</TableCell>
                      <TableCell>{(editableResult || result)?.total_net_weight} кг</TableCell>
                    </TableRow>
                  )}
                  {(editableResult || result)?.total_packages != null && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Кол-во мест (графа 6)</TableCell>
                      <TableCell>{(editableResult || result)?.total_packages}</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>

              {/* Items */}
              {(editableResult || result)?.items && ((editableResult || result)?.items?.length || 0) > 0 && (
                <>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Товарные позиции ({(editableResult || result)?.items?.length})
                  </Typography>
                  <Alert severity="info" sx={{ mb: 1 }}>
                    Для выбора альтернативного кода нажмите "Похожие коды" в колонке "Выбор кода", затем кликните по нужному варианту.
                  </Alert>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600 }}>№</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Описание (графа 31)</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>ТН ВЭД (графа 33)</TableCell>
                        <TableCell sx={{ fontWeight: 600, minWidth: 260 }}>Выбор кода</TableCell>
                        <TableCell sx={{ fontWeight: 600 }} align="right">Кол-во</TableCell>
                        <TableCell sx={{ fontWeight: 600 }} align="right">Цена</TableCell>
                        <TableCell sx={{ fontWeight: 600 }} align="right">Сумма</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(editableResult || result)!.items.map((item, i) => (
                        <TableRow key={i}>
                          <TableCell>{item.line_no}</TableCell>
                          <TableCell>
                            {item.description || item.commercial_name}
                          </TableCell>
                          <TableCell>
                            {item.hs_code ? (
                              <Box>
                                <Typography variant="body2" fontWeight={600}>
                                  {item.hs_code}
                                </Typography>
                                {item.hs_code_name && (
                                  <Typography variant="caption" color="text.secondary">
                                    {item.hs_code_name}
                                  </Typography>
                                )}
                                {item.hs_confidence != null && (
                                  <Chip
                                    label={`${Math.round(item.hs_confidence * 100)}%`}
                                    size="small"
                                    color={confidenceColor(item.hs_confidence)}
                                    sx={{ ml: 0.5 }}
                                  />
                                )}
                              </Box>
                            ) : (
                              <Typography variant="caption" color="text.secondary">—</Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                              <Button
                                size="small"
                                variant="outlined"
                                onClick={() => loadSimilarCodes(i, item)}
                                disabled={!!hsOptionsLoading[i] || !(item.description || item.commercial_name)}
                              >
                                {hsOptionsLoading[i] ? 'Поиск...' : 'Похожие коды'}
                              </Button>
                              {!!hsOptions[i]?.length && (
                                <Chip size="small" color="info" label={`Вариантов: ${hsOptions[i].length}`} />
                              )}
                            </Box>
                            {!!hsOptions[i]?.length && (
                              <Box sx={{ mt: 0.5 }}>
                                <Button
                                  size="small"
                                  color="inherit"
                                  onClick={() => setExpandedHsRows((prev) => ({ ...prev, [i]: !prev[i] }))}
                                >
                                  {expandedHsRows[i] ? 'Скрыть список' : 'Показать список'}
                                </Button>
                                <Collapse in={!!expandedHsRows[i]}>
                                  <Paper variant="outlined" sx={{ p: 0.75, mt: 0.5, maxHeight: 180, overflow: 'auto' }}>
                                    {hsOptions[i].map((opt, k) => (
                                      <Box
                                        key={`${opt.hs_code}-${k}`}
                                        onClick={() => selectHsCode(i, opt)}
                                        sx={{
                                          display: 'flex',
                                          alignItems: 'center',
                                          gap: 0.75,
                                          px: 0.75,
                                          py: 0.5,
                                          borderRadius: 1,
                                          cursor: 'pointer',
                                          bgcolor: item.hs_code === opt.hs_code ? '#e8f5e9' : 'transparent',
                                          '&:hover': { bgcolor: '#f5f5f5' },
                                        }}
                                      >
                                        <Typography variant="caption" fontFamily="monospace" fontWeight={700}>
                                          {opt.hs_code}
                                        </Typography>
                                        <Typography variant="caption" sx={{ flex: 1 }}>
                                          {opt.name_ru}
                                        </Typography>
                                        <Chip
                                          label={`${Math.round((opt.confidence || 0) * 100)}%`}
                                          size="small"
                                          color={confidenceColor(opt.confidence || 0)}
                                        />
                                      </Box>
                                    ))}
                                  </Paper>
                                </Collapse>
                              </Box>
                            )}
                          </TableCell>
                          <TableCell align="right">
                            {item.quantity}
                            {item.unit && ` ${item.unit}`}
                          </TableCell>
                          <TableCell align="right">{item.unit_price?.toLocaleString('ru-RU')}</TableCell>
                          <TableCell align="right">{item.line_total?.toLocaleString('ru-RU')}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </>
              )}
            </>
          )}
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}>
          <Button onClick={() => setShowPreview(false)} color="inherit" disabled={isApplying}>
            Закрыть
          </Button>
          {declarationId && onParsedData && (
            <Button onClick={handleApply} variant="contained" startIcon={isApplying ? <CircularProgress size={16} color="inherit" /> : <CheckIcon />} disabled={isApplying}>
              {isApplying ? 'Применение...' : 'Применить к декларации'}
            </Button>
          )}
          {!declarationId && onCreateDeclaration && (
            <Button onClick={handleCreateDeclaration} variant="contained" color="success" startIcon={isApplying ? <CircularProgress size={16} color="inherit" /> : <AddIcon />} disabled={isApplying}>
              {isApplying ? 'Создание...' : 'Создать декларацию из документов'}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </>
  );
};

export default DocumentUploadPanel;
