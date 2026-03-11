import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  Box, Typography, List, ListItemButton, ListItemText, ListItemIcon,
  IconButton, Chip, Paper, Drawer, Tooltip, Divider, Button,
  Table, TableBody, TableRow, TableCell, Badge,
  Dialog, DialogTitle, DialogContent, DialogActions,
  Select, MenuItem, FormControl, InputLabel, TextField,
} from '@mui/material';
import {
  PictureAsPdf as PdfIcon,
  Description as DocIcon,
  Close as CloseIcon,
  OpenInNew as OpenIcon,
  ChevronRight as ExpandIcon,
  DataObject as DataIcon,
  Link as LinkIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import { Document as DocType, FieldEvidence } from '../types';
import PdfViewer from './PdfViewer';

interface DocumentViewerProps {
  documents: DocType[];
  open: boolean;
  onClose: () => void;
  evidenceMap?: Record<string, FieldEvidence>;
  onEvidenceChange?: (field: string, patch: Partial<FieldEvidence>) => void;
}

const DOC_TYPE_LABELS: Record<string, string> = {
  invoice: 'Инвойс',
  contract: 'Контракт',
  specification: 'Спецификация',
  packing_list: 'Упаковочный лист',
  transport_doc: 'Транспортный документ',
  transport_invoice: 'Транспортный инвойс',
  application_statement: 'Заявка / поручение',
  tech_description: 'Техническое описание',
  certificate_origin: 'Сертификат происхождения',
  license: 'Лицензия',
  permit: 'Разрешение',
  other: 'Другой',
};

const PARSED_FIELD_LABELS: Record<string, string> = {
  invoice_number: 'Номер инвойса',
  invoice_date: 'Дата инвойса',
  seller_name: 'Продавец',
  buyer_name: 'Покупатель',
  currency: 'Валюта',
  total_amount: 'Сумма',
  incoterms: 'Инкотермс',
  contract_number: 'Номер контракта',
  contract_date: 'Дата контракта',
  total_packages: 'Кол-во мест',
  total_gross_weight: 'Вес брутто',
  total_net_weight: 'Вес нетто',
  awb_number: 'Номер AWB',
  vehicle_id: 'Транспорт',
  country_origin: 'Страна происхождения',
  country_destination: 'Страна назначения',
  packing_list_number: 'Номер УП',
  packing_list_date: 'Дата УП',
};

const getApiBase = (): string =>
  window.location.port === '3000'
    ? `${window.location.protocol}//${window.location.hostname}:80`
    : '';

const getFileUrl = (fileKey: string): string =>
  `${getApiBase()}/api/v1/files/download/${fileKey}`;

const getPdfPreviewUrl = (fileKey: string): string =>
  `${getApiBase()}/api/v1/files/pdf-preview/${fileKey}`;

const isOffice = (doc: DocType): boolean =>
  /\.(xlsx?|docx?|odt|ods|pptx?|csv|rtf)$/i.test(doc.original_filename || '') ||
  !!doc.mime_type?.includes('spreadsheet') ||
  !!doc.mime_type?.includes('wordprocessing') ||
  !!doc.mime_type?.includes('presentation');

function flattenParsedData(data: Record<string, unknown> | undefined): Array<{ key: string; label: string; value: string }> {
  if (!data) return [];
  const entries: Array<{ key: string; label: string; value: string }> = [];
  for (const [key, val] of Object.entries(data)) {
    if (val == null || key.startsWith('_')) continue;
    if (typeof val === 'object' && !Array.isArray(val)) {
      for (const [subKey, subVal] of Object.entries(val as Record<string, unknown>)) {
        if (subVal == null || subKey.startsWith('_')) continue;
        const fullKey = `${key}.${subKey}`;
        entries.push({
          key: fullKey,
          label: PARSED_FIELD_LABELS[subKey] || PARSED_FIELD_LABELS[fullKey] || subKey,
          value: String(subVal),
        });
      }
    } else if (Array.isArray(val)) {
      entries.push({ key, label: PARSED_FIELD_LABELS[key] || key, value: `[${val.length} элементов]` });
    } else {
      entries.push({ key, label: PARSED_FIELD_LABELS[key] || key, value: String(val) });
    }
  }
  return entries;
}

const DocumentViewer = ({ documents, open, onClose, evidenceMap, onEvidenceChange }: DocumentViewerProps) => {
  const [selectedDoc, setSelectedDoc] = useState<DocType | null>(null);
  const [showPanel, setShowPanel] = useState<'parsed' | 'evidence' | null>('evidence');
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editSource, setEditSource] = useState('');
  const [editDocId, setEditDocId] = useState('');
  const [editNote, setEditNote] = useState('');

  const handleEditOpen = useCallback((field: string) => {
    if (!evidenceMap) return;
    const info = evidenceMap[field] as any;
    setEditingField(field);
    setEditSource(info?.source || '');
    setEditDocId(info?.document_id || '');
    setEditNote(info?.note || '');
  }, [evidenceMap]);

  const handleEditSave = useCallback(() => {
    if (!editingField || !onEvidenceChange) return;
    onEvidenceChange(editingField, {
      source: editSource || undefined,
      note: editNote || undefined,
    });
    setEditingField(null);
  }, [editingField, editSource, editDocId, editNote, onEvidenceChange]);

  const isPdf = (doc: DocType) =>
    doc.mime_type?.includes('pdf') || doc.original_filename?.toLowerCase().endsWith('.pdf');

  const isImage = (doc: DocType) =>
    doc.mime_type?.startsWith('image/') ||
    /\.(jpg|jpeg|png|gif|webp)$/i.test(doc.original_filename || '');

  // Fields from evidence_map linked to the selected document
  const linkedFields = useMemo(() => {
    if (!selectedDoc || !evidenceMap) return [];
    const docId = selectedDoc.id;
    const docType = selectedDoc.doc_type?.toLowerCase();
    return Object.entries(evidenceMap)
      .filter(([, info]) => {
        if (!info || typeof info !== 'object') return false;
        if ((info as any).document_id === docId) return true;
        const src = (info as any).source?.toLowerCase();
        return src === docType || src === docType?.replace('_doc', '');
      })
      .map(([field, info]: [string, any]) => ({
        field,
        source: info.source,
        confidence: info.confidence,
        value: info.value_preview || info.raw_value,
        graph: info.graph,
      }));
  }, [selectedDoc, evidenceMap]);

  // Count evidence fields per doc for the sidebar badge
  const docEvidenceCounts = useMemo(() => {
    if (!evidenceMap) return new Map<string, number>();
    const counts = new Map<string, number>();
    for (const doc of documents) {
      const docType = doc.doc_type?.toLowerCase();
      let cnt = 0;
      for (const [, info] of Object.entries(evidenceMap)) {
        if (!info || typeof info !== 'object') continue;
        if ((info as any).document_id === doc.id) { cnt++; continue; }
        const src = (info as any).source?.toLowerCase();
        if (src === docType || src === docType?.replace('_doc', '')) cnt++;
      }
      if (cnt > 0) counts.set(doc.id, cnt);
    }
    return counts;
  }, [documents, evidenceMap]);

  const parsedEntries = useMemo(
    () => flattenParsedData(selectedDoc?.parsed_data as Record<string, unknown> | undefined),
    [selectedDoc],
  );

  // Check if the selected doc's file is actually available in storage
  const [fileStatus, setFileStatus] = useState<'checking' | 'ok' | 'missing'>('checking');
  useEffect(() => {
    if (!selectedDoc?.file_key) {
      setFileStatus('missing');
      // Auto-show parsed data when no file preview available
      if (selectedDoc?.parsed_data && Object.keys(selectedDoc.parsed_data).length > 0) {
        setShowPanel('parsed');
      }
      return;
    }
    setFileStatus('checking');
    const base = window.location.port === '3000'
      ? `${window.location.protocol}//${window.location.hostname}:80`
      : '';
    fetch(`${base}/api/v1/files/check/${selectedDoc.file_key}`)
      .then((r) => {
        const ok = r.ok;
        setFileStatus(ok ? 'ok' : 'missing');
        if (!ok && selectedDoc?.parsed_data && Object.keys(selectedDoc.parsed_data).length > 0) {
          setShowPanel('parsed');
        }
      })
      .catch(() => {
        setFileStatus('missing');
        if (selectedDoc?.parsed_data && Object.keys(selectedDoc.parsed_data).length > 0) {
          setShowPanel('parsed');
        }
      });
  }, [selectedDoc?.id, selectedDoc?.file_key]);

  if (!open) return null;

  const noFileMessage = (
    <Box sx={{ p: 4, textAlign: 'center' }}>
      <DocIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
      <Typography color="text.secondary" gutterBottom>
        Файл не найден в хранилище
      </Typography>
      <Typography variant="caption" color="text.secondary">
        Документ содержит только метаданные из AI-парсинга.
        {parsedEntries.length > 0 && ' Нажмите «Данные» для просмотра извлечённой информации.'}
      </Typography>
    </Box>
  );

  const renderPreview = (doc: DocType) => {
    if (fileStatus === 'checking') {
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
          <Typography variant="body2" color="text.secondary">Проверка файла...</Typography>
        </Box>
      );
    }
    if (fileStatus === 'missing') {
      return noFileMessage;
    }
    if (isPdf(doc) || isOffice(doc)) {
      return <PdfViewer url={getPdfPreviewUrl(doc.file_key)} />;
    }
    if (isImage(doc)) {
      return (
        <Box sx={{ p: 2, textAlign: 'center', overflow: 'auto', height: '100%' }}>
          <img
            src={getFileUrl(doc.file_key)}
            alt={doc.original_filename}
            style={{ maxWidth: '100%', maxHeight: '90vh' }}
          />
        </Box>
      );
    }
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <DocIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
        <Typography color="text.secondary">
          Предпросмотр недоступен для данного формата
        </Typography>
        <Button variant="outlined" sx={{ mt: 2 }} onClick={() => window.open(getFileUrl(doc.file_key), '_blank')}>
          Скачать файл
        </Button>
      </Box>
    );
  };

  const renderInfoPanel = () => {
    if (!selectedDoc || !showPanel) return null;

    if (showPanel === 'parsed' && parsedEntries.length > 0) {
      return (
        <Box sx={{ width: 280, minWidth: 280, borderLeft: 1, borderColor: 'divider', overflow: 'auto', bgcolor: 'background.paper' }}>
          <Box sx={{ p: 1.5, borderBottom: 1, borderColor: 'divider' }}>
            <Typography variant="caption" fontWeight={700} color="primary">
              <DataIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'text-bottom' }} />
              Извлечённые данные
            </Typography>
          </Box>
          <Table size="small">
            <TableBody>
              {parsedEntries.map((entry) => (
                <TableRow key={entry.key} sx={{ '&:last-child td': { borderBottom: 0 } }}>
                  <TableCell sx={{ py: 0.5, px: 1, fontSize: 11, color: 'text.secondary', width: '40%', verticalAlign: 'top' }}>
                    {entry.label}
                  </TableCell>
                  <TableCell sx={{ py: 0.5, px: 1, fontSize: 11, wordBreak: 'break-word' }}>
                    {entry.value}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      );
    }

    if (showPanel === 'evidence' && linkedFields.length > 0) {
      return (
        <Box sx={{ width: 280, minWidth: 280, borderLeft: 1, borderColor: 'divider', overflow: 'auto', bgcolor: 'background.paper' }}>
          <Box sx={{ p: 1.5, borderBottom: 1, borderColor: 'divider' }}>
            <Typography variant="caption" fontWeight={700} color="secondary">
              <LinkIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'text-bottom' }} />
              Заполненные поля декларации
            </Typography>
          </Box>
          <List dense disablePadding>
            {linkedFields.map((lf) => (
              <ListItemButton
                key={lf.field}
                sx={{ py: 0.5, px: 1.5 }}
                onClick={onEvidenceChange ? () => handleEditOpen(lf.field) : undefined}
              >
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      {lf.graph && (
                        <Chip label={`Гр.${lf.graph}`} size="small" sx={{ fontSize: 10, height: 18, minWidth: 36 }} color="primary" variant="outlined" />
                      )}
                      <Typography variant="caption" fontWeight={600} sx={{ flex: 1 }}>{lf.field}</Typography>
                      {onEvidenceChange && (
                        <EditIcon sx={{ fontSize: 12, color: 'text.disabled' }} />
                      )}
                    </Box>
                  }
                  secondary={
                    <Box>
                      {lf.value && <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: 10 }}>{lf.value}</Typography>}
                      {lf.confidence != null && (
                        <Typography
                          variant="caption"
                          sx={{
                            fontSize: 10,
                            fontWeight: 700,
                            color: lf.confidence >= 0.85 ? 'success.main' : lf.confidence >= 0.6 ? 'warning.main' : 'error.main',
                          }}
                        >
                          {Math.round(lf.confidence * 100)}%
                        </Typography>
                      )}
                    </Box>
                  }
                />
              </ListItemButton>
            ))}
          </List>
        </Box>
      );
    }

    return null;
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: '100%', md: '70%' }, maxWidth: 1200 } }}
    >
      <Box sx={{ display: 'flex', height: '100%' }}>
        {/* Document list sidebar */}
        <Paper
          elevation={0}
          sx={{
            width: 240,
            minWidth: 240,
            borderRight: 1,
            borderColor: 'divider',
            overflow: 'auto',
          }}
        >
          <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="subtitle2">Документы</Typography>
            <IconButton size="small" onClick={onClose}><CloseIcon fontSize="small" /></IconButton>
          </Box>
          <Divider />
          <List dense>
            {documents.map((doc) => {
              const evCount = docEvidenceCounts.get(doc.id) || 0;
              return (
                <ListItemButton
                  key={doc.id}
                  selected={selectedDoc?.id === doc.id}
                  onClick={() => setSelectedDoc(doc)}
                >
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    {evCount > 0 ? (
                      <Badge badgeContent={evCount} color="primary" max={99}
                        sx={{ '& .MuiBadge-badge': { fontSize: 9, height: 16, minWidth: 16 } }}>
                        {isPdf(doc) ? <PdfIcon color="error" fontSize="small" /> : <DocIcon fontSize="small" />}
                      </Badge>
                    ) : (
                      isPdf(doc) ? <PdfIcon color="error" fontSize="small" /> : <DocIcon fontSize="small" />
                    )}
                  </ListItemIcon>
                  <ListItemText
                    primary={doc.original_filename || 'Без имени'}
                    secondary={DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
                    primaryTypographyProps={{ variant: 'body2', noWrap: true }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                </ListItemButton>
              );
            })}
            {documents.length === 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ p: 2, display: 'block' }}>
                Нет прикреплённых документов
              </Typography>
            )}
          </List>
        </Paper>

        {/* Main content: preview + info panel */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', bgcolor: 'grey.50' }}>
          {selectedDoc ? (
            <>
              {/* Header */}
              <Box sx={{ p: 1, display: 'flex', alignItems: 'center', gap: 1, borderBottom: 1, borderColor: 'divider', flexWrap: 'wrap' }}>
                <Typography variant="body2" noWrap sx={{ flex: 1, minWidth: 100 }}>
                  {selectedDoc.original_filename}
                </Typography>
                <Chip label={DOC_TYPE_LABELS[selectedDoc.doc_type] || selectedDoc.doc_type} size="small" />
                {linkedFields.length > 0 && (
                  <Chip
                    icon={<LinkIcon sx={{ fontSize: 14 }} />}
                    label={`${linkedFields.length} полей`}
                    size="small"
                    color="primary"
                    variant={showPanel === 'evidence' ? 'filled' : 'outlined'}
                    onClick={() => setShowPanel(showPanel === 'evidence' ? null : 'evidence')}
                    sx={{ cursor: 'pointer' }}
                  />
                )}
                {parsedEntries.length > 0 && (
                  <Chip
                    icon={<DataIcon sx={{ fontSize: 14 }} />}
                    label="Данные"
                    size="small"
                    color="secondary"
                    variant={showPanel === 'parsed' ? 'filled' : 'outlined'}
                    onClick={() => setShowPanel(showPanel === 'parsed' ? null : 'parsed')}
                    sx={{ cursor: 'pointer' }}
                  />
                )}
                {selectedDoc.file_key && (
                  <Tooltip title="Открыть в новой вкладке">
                    <IconButton size="small" onClick={() => window.open(getFileUrl(selectedDoc.file_key), '_blank')}>
                      <OpenIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </Box>

              {/* Body: preview + side panel */}
              <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
                <Box sx={{ flex: 1, overflow: 'hidden' }}>
                  {renderPreview(selectedDoc)}
                </Box>
                {renderInfoPanel()}
              </Box>
            </>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <Box sx={{ textAlign: 'center' }}>
                <ExpandIcon sx={{ fontSize: 48, color: 'text.disabled' }} />
                <Typography color="text.secondary">Выберите документ для просмотра</Typography>
              </Box>
            </Box>
          )}
        </Box>
      </Box>

      {/* Evidence edit dialog */}
      <Dialog open={!!editingField} onClose={() => setEditingField(null)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ pb: 1 }}>
          <Typography variant="subtitle2">Изменить источник данных</Typography>
          <Typography variant="caption" color="text.secondary">{editingField}</Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          <FormControl fullWidth size="small" sx={{ mt: 1 }}>
            <InputLabel>Тип источника</InputLabel>
            <Select value={editSource} onChange={(e) => setEditSource(e.target.value)} label="Тип источника">
              {Object.entries(DOC_TYPE_LABELS).map(([val, label]) => (
                <MenuItem key={val} value={val}>{label}</MenuItem>
              ))}
              <MenuItem value="manual">Вручную</MenuItem>
              <MenuItem value="ai">AI</MenuItem>
              <MenuItem value="history">История</MenuItem>
            </Select>
          </FormControl>
          {documents.length > 0 && (
            <FormControl fullWidth size="small" sx={{ mt: 2 }}>
              <InputLabel>Документ</InputLabel>
              <Select value={editDocId} onChange={(e) => setEditDocId(e.target.value)} label="Документ">
                <MenuItem value="">Не указан</MenuItem>
                {documents.map((doc) => (
                  <MenuItem key={doc.id} value={doc.id}>
                    {doc.original_filename || DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
          <TextField
            fullWidth
            size="small"
            label="Примечание"
            value={editNote}
            onChange={(e) => setEditNote(e.target.value)}
            sx={{ mt: 2 }}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditingField(null)} color="inherit">Отмена</Button>
          <Button onClick={handleEditSave} variant="contained" disabled={!onEvidenceChange}>
            Сохранить
          </Button>
        </DialogActions>
      </Dialog>
    </Drawer>
  );
};

export default DocumentViewer;
