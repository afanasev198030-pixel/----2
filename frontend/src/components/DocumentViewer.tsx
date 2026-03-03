import { useState } from 'react';
import {
  Box, Typography, List, ListItemButton, ListItemText, ListItemIcon,
  IconButton, Chip, Paper, Drawer, Tooltip, Divider, Button,
} from '@mui/material';
import {
  PictureAsPdf as PdfIcon,
  Description as DocIcon,
  Close as CloseIcon,
  OpenInNew as OpenIcon,
  ChevronRight as ExpandIcon,
} from '@mui/icons-material';
import { Document as DocType } from '../types';

interface DocumentViewerProps {
  documents: DocType[];
  open: boolean;
  onClose: () => void;
}

const DOC_TYPE_LABELS: Record<string, string> = {
  invoice: 'Инвойс',
  contract: 'Контракт',
  specification: 'Спецификация',
  packing_list: 'Упаковочный лист',
  transport_doc: 'Транспортный документ',
  certificate_origin: 'Сертификат происхождения',
  license: 'Лицензия',
  permit: 'Разрешение',
  other: 'Другой',
};

const getFileUrl = (fileKey: string): string => {
  const base = window.location.port === '3000'
    ? `${window.location.protocol}//${window.location.hostname}:80`
    : '';
  return `${base}/api/v1/files/download/${fileKey}`;
};

const DocumentViewer = ({ documents, open, onClose }: DocumentViewerProps) => {
  const [selectedDoc, setSelectedDoc] = useState<DocType | null>(null);

  const isPdf = (doc: DocType) =>
    doc.mime_type?.includes('pdf') || doc.original_filename?.toLowerCase().endsWith('.pdf');

  const isImage = (doc: DocType) =>
    doc.mime_type?.startsWith('image/') ||
    /\.(jpg|jpeg|png|gif|webp)$/i.test(doc.original_filename || '');

  if (!open) return null;

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: '100%', md: '55%' }, maxWidth: 900 } }}
    >
      <Box sx={{ display: 'flex', height: '100%' }}>
        {/* Document list */}
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
            {documents.map((doc) => (
              <ListItemButton
                key={doc.id}
                selected={selectedDoc?.id === doc.id}
                onClick={() => setSelectedDoc(doc)}
              >
                <ListItemIcon sx={{ minWidth: 32 }}>
                  {isPdf(doc) ? <PdfIcon color="error" fontSize="small" /> : <DocIcon fontSize="small" />}
                </ListItemIcon>
                <ListItemText
                  primary={doc.original_filename || 'Без имени'}
                  secondary={DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
                  primaryTypographyProps={{ variant: 'body2', noWrap: true }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
              </ListItemButton>
            ))}
            {documents.length === 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ p: 2 }}>
                Нет прикреплённых документов
              </Typography>
            )}
          </List>
        </Paper>

        {/* Preview area */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', bgcolor: 'grey.50' }}>
          {selectedDoc ? (
            <>
              <Box sx={{ p: 1, display: 'flex', alignItems: 'center', gap: 1, borderBottom: 1, borderColor: 'divider' }}>
                <Typography variant="body2" noWrap sx={{ flex: 1 }}>
                  {selectedDoc.original_filename}
                </Typography>
                <Chip label={DOC_TYPE_LABELS[selectedDoc.doc_type] || selectedDoc.doc_type} size="small" />
                <Tooltip title="Открыть в новой вкладке">
                  <IconButton
                    size="small"
                    onClick={() => window.open(getFileUrl(selectedDoc.file_key), '_blank')}
                  >
                    <OpenIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
              <Box sx={{ flex: 1, overflow: 'hidden' }}>
                {isPdf(selectedDoc) ? (
                  <iframe
                    src={getFileUrl(selectedDoc.file_key)}
                    title={selectedDoc.original_filename}
                    style={{ width: '100%', height: '100%', border: 'none' }}
                  />
                ) : isImage(selectedDoc) ? (
                  <Box sx={{ p: 2, textAlign: 'center', overflow: 'auto', height: '100%' }}>
                    <img
                      src={getFileUrl(selectedDoc.file_key)}
                      alt={selectedDoc.original_filename}
                      style={{ maxWidth: '100%', maxHeight: '90vh' }}
                    />
                  </Box>
                ) : (
                  <Box sx={{ p: 4, textAlign: 'center' }}>
                    <DocIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
                    <Typography color="text.secondary">
                      Предпросмотр недоступен для данного формата
                    </Typography>
                    <Button
                      variant="outlined"
                      sx={{ mt: 2 }}
                      onClick={() => window.open(getFileUrl(selectedDoc.file_key), '_blank')}
                    >
                      Скачать файл
                    </Button>
                  </Box>
                )}
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
    </Drawer>
  );
};

export default DocumentViewer;
