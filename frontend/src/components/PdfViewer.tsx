import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import {
  Box, IconButton, Typography, CircularProgress, Button, Tooltip, Slider,
} from '@mui/material';
import {
  NavigateBefore, NavigateNext, ZoomIn, ZoomOut, FitScreen, Download,
} from '@mui/icons-material';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

interface PdfViewerProps {
  url: string;
}

const MIN_SCALE = 0.5;
const MAX_SCALE = 3.0;
const SCALE_STEP = 0.25;

const PdfViewer = ({ url }: PdfViewerProps) => {
  const [pdfData, setPdfData] = useState<Uint8Array | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [scale, setScale] = useState(1.0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setPdfData(null);
    setCurrentPage(1);
    setNumPages(0);

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.arrayBuffer();
      })
      .then((buf) => setPdfData(new Uint8Array(buf)))
      .catch((e) => setError(e.message || 'Failed to load PDF'))
      .finally(() => setLoading(false));
  }, [url]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const onDocumentLoadSuccess = useCallback(({ numPages: n }: { numPages: number }) => {
    setNumPages(n);
    setCurrentPage(1);
  }, []);

  const fitWidth = useCallback(() => {
    setScale(0);
  }, []);

  const pageWidth = scale === 0 ? (containerWidth > 40 ? containerWidth - 40 : containerWidth) : undefined;

  const fileObj = useMemo(() => {
    if (!pdfData) return null;
    return { data: pdfData.slice() };
  }, [pdfData]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 2 }}>
        <CircularProgress size={28} />
        <Typography variant="body2" color="text.secondary">Загрузка документа...</Typography>
      </Box>
    );
  }

  if (error || !pdfData) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 2, p: 4 }}>
        <Typography color="error" variant="body2">
          Не удалось загрузить документ{error ? `: ${error}` : ''}
        </Typography>
        <Button variant="outlined" startIcon={<Download />} onClick={() => window.open(url, '_blank')}>
          Скачать файл
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Toolbar */}
      <Box sx={{
        display: 'flex', alignItems: 'center', gap: 0.5, px: 1.5, py: 0.5,
        borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper', flexWrap: 'wrap',
      }}>
        <Tooltip title="Предыдущая страница">
          <span>
            <IconButton size="small" disabled={currentPage <= 1} onClick={() => setCurrentPage((p) => p - 1)}>
              <NavigateBefore fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        <Typography variant="caption" sx={{ minWidth: 60, textAlign: 'center', userSelect: 'none' }}>
          {currentPage} / {numPages}
        </Typography>
        <Tooltip title="Следующая страница">
          <span>
            <IconButton size="small" disabled={currentPage >= numPages} onClick={() => setCurrentPage((p) => p + 1)}>
              <NavigateNext fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>

        <Box sx={{ mx: 1, height: 20, borderLeft: 1, borderColor: 'divider' }} />

        <Tooltip title="Уменьшить">
          <span>
            <IconButton size="small" disabled={scale !== 0 && scale <= MIN_SCALE} onClick={() => setScale((s) => {
              const cur = s === 0 ? 1 : s;
              return Math.max(MIN_SCALE, cur - SCALE_STEP);
            })}>
              <ZoomOut fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        <Slider
          value={scale === 0 ? 1 : scale}
          min={MIN_SCALE}
          max={MAX_SCALE}
          step={SCALE_STEP}
          onChange={(_, v) => setScale(v as number)}
          sx={{ width: 100, mx: 1 }}
          size="small"
        />
        <Tooltip title="Увеличить">
          <span>
            <IconButton size="small" disabled={scale !== 0 && scale >= MAX_SCALE} onClick={() => setScale((s) => {
              const cur = s === 0 ? 1 : s;
              return Math.min(MAX_SCALE, cur + SCALE_STEP);
            })}>
              <ZoomIn fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        <Typography variant="caption" sx={{ minWidth: 40, textAlign: 'center', userSelect: 'none' }}>
          {scale === 0 ? 'Авто' : `${Math.round((scale) * 100)}%`}
        </Typography>
        <Tooltip title="По ширине">
          <IconButton size="small" onClick={fitWidth} color={scale === 0 ? 'primary' : 'default'}>
            <FitScreen fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* PDF content */}
      <Box ref={containerRef} sx={{ flex: 1, overflow: 'auto', display: 'flex', justifyContent: 'center', bgcolor: 'grey.200', p: 1 }}>
        <Document
          file={fileObj}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 8 }}>
              <CircularProgress size={24} />
            </Box>
          }
          error={
            <Typography color="error" sx={{ py: 4 }}>Ошибка отображения PDF</Typography>
          }
        >
          <Page
            pageNumber={currentPage}
            scale={scale === 0 ? undefined : scale}
            width={pageWidth}
            loading=""
          />
        </Document>
      </Box>
    </Box>
  );
};

export default PdfViewer;
