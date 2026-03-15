import { useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Button, CircularProgress, Alert,
  Accordion, AccordionSummary, AccordionDetails,
  Chip, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Tabs, Tab, Divider, LinearProgress,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  CloudUpload as UploadIcon,
  BugReport as BugIcon,
  CheckCircle as CheckIcon,
  TextSnippet as OcrIcon,
  Psychology as LlmIcon,
  Summarize as CompileIcon,
  Settings as PostProcessIcon,
  VerifiedUser as ValidationIcon,
} from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import {
  parseDebug, ParseDebugResponse, ParseDebugDocument,
  ParseDebugClassifyExtract, ParseDebugCompilation,
} from '../api/ai';

const DOC_TYPE_LABELS: Record<string, string> = {
  invoice: 'Товарный инвойс',
  transport_invoice: 'Транспортный инвойс',
  packing_list: 'Упаковочный лист',
  contract: 'Контракт',
  transport_doc: 'Транспортный документ',
  specification: 'Спецификация',
  tech_description: 'Техописание',
  application_statement: 'Заявка на перевозку',
  reference_gtd: 'Эталонная ГТД',
  svh_doc: 'Документ СВХ',
  payment_order: 'Платёжное поручение',
  origin_certificate: 'Сертификат происхождения',
  other: 'Не определён',
};

function JsonBlock({ data, maxHeight = 400 }: { data: any; maxHeight?: number }) {
  return (
    <Box
      component="pre"
      sx={{
        bgcolor: 'grey.900', color: 'grey.100', p: 1.5, borderRadius: 1,
        overflow: 'auto', maxHeight, fontSize: '0.75rem', fontFamily: 'monospace',
        whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0,
      }}
    >
      {typeof data === 'string' ? data : JSON.stringify(data, null, 2)}
    </Box>
  );
}

function OcrStage({ ocr }: { ocr: ParseDebugDocument['stages']['ocr'] }) {
  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 1.5, flexWrap: 'wrap' }}>
        <Chip label={`Метод: ${ocr.method}`} size="small" color="primary" variant="outlined" />
        <Chip label={`${ocr.chars} символов`} size="small" variant="outlined" />
        <Chip label={`${ocr.pages} стр.`} size="small" variant="outlined" />
        <Chip label={`${ocr.duration_ms} мс`} size="small" variant="outlined" />
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
        OCR-текст:
      </Typography>
      <Box
        component="pre"
        sx={{
          bgcolor: 'grey.50', p: 1.5, borderRadius: 1, border: '1px solid',
          borderColor: 'grey.300', overflow: 'auto', maxHeight: 300,
          fontSize: '0.75rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap',
          wordBreak: 'break-word', m: 0,
        }}
      >
        {ocr.text || '(пусто)'}
      </Box>
    </Box>
  );
}

function ClassifyExtractStage({ data }: { data: ParseDebugClassifyExtract }) {
  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 1.5, flexWrap: 'wrap' }}>
        <Chip
          label={DOC_TYPE_LABELS[data.doc_type] || data.doc_type}
          size="small" color="primary"
        />
        <Chip
          label={`Уверенность: ${Math.round(data.doc_type_confidence * 100)}%`}
          size="small"
          color={data.doc_type_confidence >= 0.8 ? 'success' : data.doc_type_confidence >= 0.5 ? 'warning' : 'error'}
          variant="outlined"
        />
        {data.model && <Chip label={`Модель: ${data.model}`} size="small" variant="outlined" />}
        {data.duration_ms != null && <Chip label={`${data.duration_ms} мс`} size="small" variant="outlined" />}
        {data.tokens && (
          <Chip
            label={`Токены: ${data.tokens.prompt} + ${data.tokens.completion}`}
            size="small" variant="outlined"
          />
        )}
      </Box>

      <Accordion defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="body2">Извлечённые данные</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <JsonBlock data={data.extracted} maxHeight={400} />
        </AccordionDetails>
      </Accordion>

      {data.prompt_system && (
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="body2">System prompt</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <JsonBlock data={data.prompt_system} maxHeight={200} />
          </AccordionDetails>
        </Accordion>
      )}
      {data.prompt_user && (
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="body2">User prompt</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <JsonBlock data={data.prompt_user} maxHeight={400} />
          </AccordionDetails>
        </Accordion>
      )}
      {data.raw_response && (
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="body2">Raw LLM response</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <JsonBlock data={data.raw_response} maxHeight={400} />
          </AccordionDetails>
        </Accordion>
      )}
    </Box>
  );
}

function DocumentDebugPanel({ doc }: { doc: ParseDebugDocument }) {
  const [tab, setTab] = useState(0);
  const stages = doc.stages;

  const tabs = [
    { label: 'OCR', icon: <OcrIcon fontSize="small" /> },
    { label: 'LLM: Тип + Извлечение', icon: <LlmIcon fontSize="small" /> },
  ];

  return (
    <Paper variant="outlined" sx={{ mb: 2 }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto">
          {tabs.map((t, i) => (
            <Tab key={i} label={t.label} icon={t.icon} iconPosition="start"
                 sx={{ minHeight: 48, textTransform: 'none' }} />
          ))}
        </Tabs>
      </Box>
      <Box sx={{ p: 2 }}>
        {tab === 0 && stages.ocr && <OcrStage ocr={stages.ocr} />}
        {tab === 1 && stages.classify_and_extract && (
          <ClassifyExtractStage data={stages.classify_and_extract} />
        )}
      </Box>
    </Paper>
  );
}

function CompilationSection({ compilation }: { compilation: ParseDebugCompilation }) {
  if (compilation.error) {
    return <Alert severity="error">{compilation.error}</Alert>;
  }

  return (
    <Box>
      {compilation.llm_compile && (
        <Accordion defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CompileIcon color="primary" fontSize="small" />
              <Typography variant="subtitle1" fontWeight={600}>
                LLM-компиляция
              </Typography>
              <Chip label={`${compilation.llm_compile.duration_ms} мс`} size="small" variant="outlined" />
              <Chip label={`${compilation.llm_compile.items_count} позиций`} size="small" variant="outlined" />
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ mb: 1.5, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {compilation.llm_compile.fields.map((f) => (
                <Chip key={f} label={f} size="small" variant="outlined" />
              ))}
            </Box>
            <JsonBlock data={compilation.llm_compile.result} maxHeight={400} />
          </AccordionDetails>
        </Accordion>
      )}

      {compilation.post_process && (
        <Accordion defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <PostProcessIcon color="secondary" fontSize="small" />
              <Typography variant="subtitle1" fontWeight={600}>
                Python Post-Process
              </Typography>
              <Chip label={`${compilation.post_process.duration_ms} мс`} size="small" variant="outlined" />
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <TableContainer>
              <Table size="small">
                <TableBody>
                  {compilation.post_process.customs_office_code && (
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Таможенный пост (гр.29)</TableCell>
                      <TableCell>
                        <code>{compilation.post_process.customs_office_code}</code>{' '}
                        {compilation.post_process.customs_office_name}
                      </TableCell>
                    </TableRow>
                  )}
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Брутто/Нетто (гр.35/38)</TableCell>
                    <TableCell>
                      {compilation.post_process.total_gross_weight ?? '—'} / {compilation.post_process.total_net_weight ?? '—'} кг
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Листы/Позиции (гр.3/5)</TableCell>
                    <TableCell>
                      {compilation.post_process.total_sheets ?? '—'} / {compilation.post_process.total_items_count ?? '—'}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Сумма инвойса (гр.22)</TableCell>
                    <TableCell>{compilation.post_process.total_amount ?? '—'}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>

            {compilation.post_process.items_preview && compilation.post_process.items_preview.length > 0 && (
              <Accordion sx={{ mt: 1 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="body2">
                    Позиции ({compilation.post_process.items_preview.length})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Описание</TableCell>
                          <TableCell>HS</TableCell>
                          <TableCell>Брутто</TableCell>
                          <TableCell>Нетто</TableCell>
                          <TableCell>Сумма</TableCell>
                          <TableCell>Страна</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {compilation.post_process.items_preview.map((it, i) => (
                          <TableRow key={i}>
                            <TableCell sx={{ maxWidth: 250, wordBreak: 'break-word' }}>
                              {it.description || '—'}
                            </TableCell>
                            <TableCell><code>{it.hs_code || '—'}</code></TableCell>
                            <TableCell>{it.gross_weight ?? '—'}</TableCell>
                            <TableCell>{it.net_weight ?? '—'}</TableCell>
                            <TableCell>{it.line_total ?? '—'}</TableCell>
                            <TableCell>{it.country_origin_code || '—'}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </AccordionDetails>
              </Accordion>
            )}
          </AccordionDetails>
        </Accordion>
      )}

      {compilation.validation && (
        <Accordion defaultExpanded={compilation.validation.issues_count > 0}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <ValidationIcon
                fontSize="small"
                color={compilation.validation.issues_count > 0 ? 'warning' : 'success'}
              />
              <Typography variant="subtitle1" fontWeight={600}>
                Валидация
              </Typography>
              <Chip
                label={compilation.validation.issues_count > 0
                  ? `${compilation.validation.issues_count} проблем(ы)`
                  : 'Ок'}
                size="small"
                color={compilation.validation.issues_count > 0 ? 'warning' : 'success'}
                variant="outlined"
              />
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            {compilation.validation.issues.length > 0 ? (
              compilation.validation.issues.map((issue, i) => (
                <Alert
                  key={i}
                  severity={
                    issue.severity === 'error' ? 'error'
                    : issue.severity === 'warning' ? 'warning'
                    : 'info'
                  }
                  sx={{ mb: 0.5 }}
                >
                  {issue.graph != null && <strong>Гр.{issue.graph}: </strong>}
                  {issue.message}
                </Alert>
              ))
            ) : (
              <Typography variant="body2" color="success.main">
                Проблем не обнаружено
              </Typography>
            )}
          </AccordionDetails>
        </Accordion>
      )}

      {compilation.evidence_map && Object.keys(compilation.evidence_map).length > 0 && (
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="body2">Evidence Map</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Поле</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Графа</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Источник</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Confidence</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Значение</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {Object.entries(compilation.evidence_map).map(([key, val]: [string, any]) => (
                    <TableRow key={key}>
                      <TableCell><code>{key}</code></TableCell>
                      <TableCell>{val.graph ?? '—'}</TableCell>
                      <TableCell><Chip label={val.source} size="small" variant="outlined" /></TableCell>
                      <TableCell>
                        <Chip
                          label={`${Math.round((val.confidence || 0) * 100)}%`}
                          size="small"
                          color={
                            (val.confidence || 0) >= 0.8 ? 'success'
                            : (val.confidence || 0) >= 0.5 ? 'warning'
                            : 'error'
                          }
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem', maxWidth: 300, wordBreak: 'break-word' }}>
                        {(val.value_preview || '—').substring(0, 120)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </AccordionDetails>
        </Accordion>
      )}
    </Box>
  );
}

export default function AdminParseDebugPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ParseDebugResponse | null>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files);
    setFiles(prev => [...prev, ...dropped]);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(prev => [...prev, ...Array.from(e.target.files!)]);
    }
  }, []);

  const handleRun = async () => {
    if (!files.length) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await parseDebug(files);
      setResult(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Parse debug failed');
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setFiles([]);
    setResult(null);
    setError(null);
  };

  return (
    <AppLayout breadcrumbs={[{ label: 'Админ' }, { label: 'Дебаг парсинга' }]}>
      <Box sx={{ maxWidth: 1200, mx: 'auto', py: 3, px: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
          <BugIcon color="primary" />
          <Typography variant="h5" fontWeight={600}>Дебаг парсинга документов (LLM v3)</Typography>
        </Box>

        <Paper
          variant="outlined"
          sx={{
            p: 3, mb: 3, textAlign: 'center',
            border: '2px dashed', borderColor: 'grey.400',
            bgcolor: 'grey.50', cursor: 'pointer',
            '&:hover': { borderColor: 'primary.main', bgcolor: 'primary.50' },
          }}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
        >
          <UploadIcon sx={{ fontSize: 40, color: 'grey.500', mb: 1 }} />
          <Typography variant="body1" color="text.secondary" gutterBottom>
            Перетащите файлы сюда или нажмите для выбора
          </Typography>
          <Typography variant="caption" color="text.secondary">
            PDF, JPG, PNG, XLSX (до 10 файлов)
          </Typography>
          <input
            type="file" multiple
            accept=".pdf,.jpg,.jpeg,.png,.xlsx,.xls"
            style={{ display: 'none' }}
            id="debug-file-input"
            onChange={handleFileSelect}
          />
          <Box sx={{ mt: 1 }}>
            <Button variant="outlined" size="small" component="label" htmlFor="debug-file-input">
              Выбрать файлы
            </Button>
          </Box>
        </Paper>

        {files.length > 0 && (
          <Box sx={{ mb: 2, display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
            {files.map((f, i) => (
              <Chip
                key={i} label={f.name} size="small"
                onDelete={() => setFiles(prev => prev.filter((_, j) => j !== i))}
              />
            ))}
            <Button size="small" onClick={handleClear} color="inherit">Очистить</Button>
            <Box sx={{ flexGrow: 1 }} />
            <Button
              variant="contained" startIcon={<BugIcon />}
              onClick={handleRun} disabled={loading}
            >
              {loading ? 'Парсинг...' : 'Запустить дебаг-парсинг'}
            </Button>
          </Box>
        )}

        {loading && <LinearProgress sx={{ mb: 2 }} />}
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {result && (
          <>
            <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
              <Chip label={`${result.documents.length} документ(ов)`} color="primary" />
              <Chip label={`${result.total_duration_ms} мс`} variant="outlined" />
            </Box>

            {result.documents.map((doc, i) => {
              const ce = doc.stages.classify_and_extract;
              return (
                <Accordion key={i} defaultExpanded={result.documents.length <= 3}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                      <Typography variant="subtitle1" fontWeight={600}>
                        {doc.filename}
                      </Typography>
                      {ce && (
                        <>
                          <Chip
                            label={DOC_TYPE_LABELS[ce.doc_type] || ce.doc_type}
                            size="small" color="info" variant="outlined"
                          />
                          <Chip
                            label={`${Math.round(ce.doc_type_confidence * 100)}%`}
                            size="small"
                            color={ce.doc_type_confidence >= 0.8 ? 'success' : 'warning'}
                            variant="outlined"
                          />
                        </>
                      )}
                      {doc.stages.ocr && (
                        <Chip label={`${doc.stages.ocr.chars} сим.`} size="small" variant="outlined" />
                      )}
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    <DocumentDebugPanel doc={doc} />
                  </AccordionDetails>
                </Accordion>
              );
            })}

            {result.compilation && (
              <>
                <Divider sx={{ my: 3 }} />
                <Typography variant="h6" fontWeight={600} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CompileIcon color="primary" />
                  Компиляция декларации
                </Typography>
                <CompilationSection compilation={result.compilation} />
              </>
            )}
          </>
        )}
      </Box>
    </AppLayout>
  );
}
