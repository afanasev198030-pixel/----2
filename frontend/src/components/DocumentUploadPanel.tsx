import { useState, useCallback } from 'react';
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
import { parseSmartDocument, ParseSmartResult } from '../api/ai';
import client from '../api/client';

interface DocumentUploadPanelProps {
  declarationId?: string;
  onParsedData?: (data: ParseSmartResult) => void;
  onCreateDeclaration?: (data: ParseSmartResult) => void;
}

const DocumentUploadPanel = ({ declarationId, onParsedData, onCreateDeclaration }: DocumentUploadPanelProps) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressStep, setProgressStep] = useState('');
  const [progressDetail, setProgressDetail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ParseSmartResult | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [isDragOver, setIsDragOver] = useState(false);

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
      const parsePromise = parseSmartDocument(selectedFiles);

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

      setProgress(100);
      setProgressStep('complete');
      setProgressDetail('Готово! Данные распознаны.');
      setResult(parsed);

      // Show preview after short delay
      setTimeout(() => setShowPreview(true), 500);

    } catch (err: any) {
      console.error('Smart parse error:', err);
      const msg = err?.response?.data?.detail || err?.message || 'Ошибка';
      if (msg.includes('timeout') || msg.includes('Network Error')) {
        setError('Таймаут: обработка заняла слишком много времени. Попробуйте загрузить меньше файлов или проверьте OpenAI ключ в Настройках.');
      } else {
        setError(msg);
      }
    } finally {
      clearInterval(timer);
      setIsProcessing(false);
    }
  }, [selectedFiles]);

  const handleApply = () => {
    if (result && onParsedData) {
      onParsedData(result);
    }
    setShowPreview(false);
  };

  const handleCreateDeclaration = () => {
    if (result && onCreateDeclaration) {
      onCreateDeclaration(result);
    }
    setShowPreview(false);
  };

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
        open={showPreview && !!result}
        onClose={() => setShowPreview(false)}
        maxWidth="lg"
        fullWidth
        PaperProps={{ sx: { borderRadius: 3 } }}
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AiIcon color="primary" />
          Результат распознавания
          {result?.confidence != null && (
            <Chip
              label={`Точность: ${Math.round((result.confidence || 0) * 100)}%`}
              size="small"
              color={confidenceColor(result.confidence || 0)}
            />
          )}
          {result?.risk_score != null && result.risk_score > 0 && (
            <Chip
              icon={<WarningIcon />}
              label={`Риск: ${result.risk_score}`}
              size="small"
              color={result.risk_score > 50 ? 'error' : result.risk_score > 25 ? 'warning' : 'default'}
            />
          )}
        </DialogTitle>

        <DialogContent dividers>
          {result && (
            <>
              {/* General info */}
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Общие данные
              </Typography>
              <Table size="small" sx={{ mb: 3 }}>
                <TableBody>
                  {result.invoice_number && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600, width: 220 }}>Номер инвойса</TableCell>
                      <TableCell>{result.invoice_number}</TableCell>
                    </TableRow>
                  )}
                  {result.invoice_date && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Дата</TableCell>
                      <TableCell>{result.invoice_date}</TableCell>
                    </TableRow>
                  )}
                  {result.seller?.name && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Продавец (графа 2)</TableCell>
                      <TableCell>
                        {result.seller.name}
                        {result.seller.country_code && ` [${result.seller.country_code}]`}
                      </TableCell>
                    </TableRow>
                  )}
                  {result.buyer?.name && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Покупатель (графа 8)</TableCell>
                      <TableCell>
                        {result.buyer.name}
                        {result.buyer.country_code && ` [${result.buyer.country_code}]`}
                      </TableCell>
                    </TableRow>
                  )}
                  {result.currency && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Валюта (графа 22)</TableCell>
                      <TableCell>{result.currency}</TableCell>
                    </TableRow>
                  )}
                  {result.total_amount != null && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Сумма (графа 22)</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: 'primary.main' }}>
                        {result.currency || ''} {Number(result.total_amount).toLocaleString('ru-RU', { minimumFractionDigits: 2 })}
                      </TableCell>
                    </TableRow>
                  )}
                  {result.incoterms && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Incoterms (графа 20)</TableCell>
                      <TableCell>{result.incoterms}</TableCell>
                    </TableRow>
                  )}
                  {result.contract_number && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Контракт</TableCell>
                      <TableCell>{result.contract_number}</TableCell>
                    </TableRow>
                  )}
                  {result.total_gross_weight != null && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Вес брутто (графа 35)</TableCell>
                      <TableCell>{result.total_gross_weight} кг</TableCell>
                    </TableRow>
                  )}
                  {result.total_net_weight != null && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Вес нетто (графа 38)</TableCell>
                      <TableCell>{result.total_net_weight} кг</TableCell>
                    </TableRow>
                  )}
                  {result.total_packages != null && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Кол-во мест (графа 6)</TableCell>
                      <TableCell>{result.total_packages}</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>

              {/* Items */}
              {result.items && result.items.length > 0 && (
                <>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Товарные позиции ({result.items.length})
                  </Typography>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600 }}>№</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Описание (графа 31)</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>ТН ВЭД (графа 33)</TableCell>
                        <TableCell sx={{ fontWeight: 600 }} align="right">Кол-во</TableCell>
                        <TableCell sx={{ fontWeight: 600 }} align="right">Цена</TableCell>
                        <TableCell sx={{ fontWeight: 600 }} align="right">Сумма</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {result.items.map((item, i) => (
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
          <Button onClick={() => setShowPreview(false)} color="inherit">
            Закрыть
          </Button>
          {declarationId && onParsedData && (
            <Button onClick={handleApply} variant="contained" startIcon={<CheckIcon />}>
              Применить к декларации
            </Button>
          )}
          {!declarationId && onCreateDeclaration && (
            <Button onClick={handleCreateDeclaration} variant="contained" color="success" startIcon={<AddIcon />}>
              Создать декларацию из документов
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </>
  );
};

export default DocumentUploadPanel;
