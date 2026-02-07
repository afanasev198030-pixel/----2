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
  TableCell,
  TableRow,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  Description as FileIcon,
  CheckCircle as CheckIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  AutoAwesome as AiIcon,
} from '@mui/icons-material';
import { parseInvoice, parsePackingList } from '../api/ai';

interface DocumentUploadPanelProps {
  declarationId: string;
  onParsedData?: (data: any, sourceType: string) => void;
}

const DocumentUploadPanel = ({ declarationId, onParsedData }: DocumentUploadPanelProps) => {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parsedResult, setParsedResult] = useState<any>(null);
  const [parsedType, setParsedType] = useState<string>('');
  const [showPreview, setShowPreview] = useState(false);
  const [expanded, setExpanded] = useState(true);

  const handleFileUpload = useCallback(async (file: File, docType: 'invoice' | 'packing-list') => {
    setIsUploading(true);
    setError(null);
    setParsedResult(null);

    try {
      let result;
      if (docType === 'invoice') {
        result = await parseInvoice(file);
        setParsedType('invoice');
      } else {
        result = await parsePackingList(file);
        setParsedType('packing_list');
      }
      setParsedResult(result);
      setShowPreview(true);
    } catch (err: any) {
      console.error('Upload error:', err);
      setError(err?.response?.data?.detail || err?.message || 'Ошибка распознавания документа');
    } finally {
      setIsUploading(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, docType: 'invoice' | 'packing-list') => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file, docType);
  }, [handleFileUpload]);

  const handleApply = () => {
    if (parsedResult && onParsedData) {
      onParsedData(parsedResult, parsedType);
    }
    setShowPreview(false);
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
              Загрузить документ для распознавания (AI)
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

            {isUploading ? (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 4, gap: 2 }}>
                <CircularProgress size={24} />
                <Typography color="text.secondary">Распознавание документа...</Typography>
              </Box>
            ) : (
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {/* Invoice upload */}
                <Box
                  sx={{
                    flex: 1,
                    minWidth: 200,
                    border: '2px dashed',
                    borderColor: 'primary.light',
                    borderRadius: 2,
                    p: 2,
                    textAlign: 'center',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    '&:hover': {
                      borderColor: 'primary.main',
                      bgcolor: '#f8fbff',
                    },
                  }}
                  onDrop={(e) => handleDrop(e, 'invoice')}
                  onDragOver={(e) => e.preventDefault()}
                >
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    style={{ display: 'none' }}
                    id="upload-invoice"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileUpload(file, 'invoice');
                      e.target.value = '';
                    }}
                  />
                  <label htmlFor="upload-invoice" style={{ cursor: 'pointer' }}>
                    <FileIcon sx={{ fontSize: 36, color: 'primary.main', mb: 1 }} />
                    <Typography variant="body2" fontWeight={600} color="primary.main">
                      Инвойс (Invoice)
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      PDF или изображение
                    </Typography>
                    <Button
                      component="span"
                      size="small"
                      variant="outlined"
                      startIcon={<UploadIcon />}
                      sx={{ mt: 1 }}
                    >
                      Выбрать файл
                    </Button>
                  </label>
                </Box>

                {/* Packing list upload */}
                <Box
                  sx={{
                    flex: 1,
                    minWidth: 200,
                    border: '2px dashed',
                    borderColor: 'success.light',
                    borderRadius: 2,
                    p: 2,
                    textAlign: 'center',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    '&:hover': {
                      borderColor: 'success.main',
                      bgcolor: '#f5fbf5',
                    },
                  }}
                  onDrop={(e) => handleDrop(e, 'packing-list')}
                  onDragOver={(e) => e.preventDefault()}
                >
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    style={{ display: 'none' }}
                    id="upload-packing"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileUpload(file, 'packing-list');
                      e.target.value = '';
                    }}
                  />
                  <label htmlFor="upload-packing" style={{ cursor: 'pointer' }}>
                    <FileIcon sx={{ fontSize: 36, color: 'success.main', mb: 1 }} />
                    <Typography variant="body2" fontWeight={600} color="success.main">
                      Упаковочный лист
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      PDF или изображение
                    </Typography>
                    <Button
                      component="span"
                      size="small"
                      variant="outlined"
                      color="success"
                      startIcon={<UploadIcon />}
                      sx={{ mt: 1 }}
                    >
                      Выбрать файл
                    </Button>
                  </label>
                </Box>
              </Box>
            )}

            {parsedResult && !showPreview && (
              <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <CheckIcon color="success" fontSize="small" />
                <Typography variant="body2" color="success.main">
                  Документ распознан
                </Typography>
                <Button size="small" onClick={() => setShowPreview(true)}>
                  Просмотреть результат
                </Button>
              </Box>
            )}
          </Box>
        </Collapse>
      </Paper>

      {/* Preview dialog */}
      <Dialog
        open={showPreview && !!parsedResult}
        onClose={() => setShowPreview(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{ sx: { borderRadius: 3 } }}
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AiIcon color="primary" />
          Результат распознавания
          {parsedResult?.confidence != null && (
            <Chip
              label={`Точность: ${Math.round((parsedResult.confidence || 0) * 100)}%`}
              size="small"
              color={parsedResult.confidence > 0.7 ? 'success' : parsedResult.confidence > 0.4 ? 'warning' : 'error'}
            />
          )}
        </DialogTitle>
        <DialogContent>
          {parsedType === 'invoice' && parsedResult && (
            <Table size="small">
              <TableBody>
                {parsedResult.invoice_number && (
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600, width: 200 }}>Номер инвойса</TableCell>
                    <TableCell>{parsedResult.invoice_number}</TableCell>
                  </TableRow>
                )}
                {parsedResult.invoice_date && (
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Дата</TableCell>
                    <TableCell>{parsedResult.invoice_date}</TableCell>
                  </TableRow>
                )}
                {parsedResult.seller?.name && (
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Продавец</TableCell>
                    <TableCell>
                      {parsedResult.seller.name}
                      {parsedResult.seller.country_code && ` (${parsedResult.seller.country_code})`}
                    </TableCell>
                  </TableRow>
                )}
                {parsedResult.buyer?.name && (
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Покупатель</TableCell>
                    <TableCell>{parsedResult.buyer.name}</TableCell>
                  </TableRow>
                )}
                {parsedResult.currency && (
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Валюта</TableCell>
                    <TableCell>{parsedResult.currency}</TableCell>
                  </TableRow>
                )}
                {parsedResult.total_amount != null && (
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Общая сумма</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: 'primary.main' }}>
                      {parsedResult.currency} {Number(parsedResult.total_amount).toLocaleString('ru-RU', { minimumFractionDigits: 2 })}
                    </TableCell>
                  </TableRow>
                )}
                {parsedResult.items?.length > 0 && (
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Товары</TableCell>
                    <TableCell>
                      {parsedResult.items.map((item: any, i: number) => (
                        <Box key={i} sx={{ mb: 0.5 }}>
                          <Typography variant="body2">
                            {i + 1}. {item.description_raw}
                            {item.quantity && ` — ${item.quantity} ${item.unit || 'шт.'}`}
                            {item.unit_price && ` × ${item.unit_price}`}
                            {item.line_total && ` = ${item.line_total}`}
                          </Typography>
                        </Box>
                      ))}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}

          {parsedType === 'packing_list' && parsedResult && (
            <Table size="small">
              <TableBody>
                {parsedResult.total_packages != null && (
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600, width: 200 }}>Кол-во мест</TableCell>
                    <TableCell>{parsedResult.total_packages}</TableCell>
                  </TableRow>
                )}
                {parsedResult.package_type && (
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Тип упаковки</TableCell>
                    <TableCell>{parsedResult.package_type}</TableCell>
                  </TableRow>
                )}
                {parsedResult.total_gross_weight != null && (
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Вес брутто (кг)</TableCell>
                    <TableCell>{parsedResult.total_gross_weight}</TableCell>
                  </TableRow>
                )}
                {parsedResult.total_net_weight != null && (
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Вес нетто (кг)</TableCell>
                    <TableCell>{parsedResult.total_net_weight}</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}

          {parsedResult?.raw_text && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="caption" color="text.secondary">
                Распознанный текст (для отладки):
              </Typography>
              <Box sx={{ bgcolor: '#f5f5f5', p: 1, borderRadius: 1, maxHeight: 150, overflow: 'auto', mt: 0.5 }}>
                <Typography variant="caption" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
                  {parsedResult.raw_text.slice(0, 1000)}
                </Typography>
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setShowPreview(false)} color="inherit">
            Закрыть
          </Button>
          <Button onClick={handleApply} variant="contained" startIcon={<CheckIcon />}>
            Применить к декларации
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default DocumentUploadPanel;
