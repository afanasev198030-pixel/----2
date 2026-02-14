import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Paper, Typography, TextField, Button, Box, Alert,
  Chip, Divider, IconButton, InputAdornment, CircularProgress,
  Card, CardContent, Grid, LinearProgress,
} from '@mui/material';
import AppLayout from '../components/AppLayout';
import {
  Visibility, VisibilityOff, Save as SaveIcon,
  CheckCircle as CheckIcon, Error as ErrorIcon,
  Settings as SettingsIcon, SmartToy as AiIcon,
  Storage as StorageIcon, School as TrainIcon,
  Terminal as ConsoleIcon, Refresh as RefreshIcon,
  CloudUpload as UploadIcon, PlayArrow as PlayIcon,
} from '@mui/icons-material';
import client from '../api/client';

interface ServiceStatus {
  name: string;
  port: number;
  status: string;
  detail: string;
}

interface SystemSettings {
  openai_api_key_set: boolean;
  openai_model: string;
  chromadb_status: string;
  rag_available: boolean;
  ai_status: string;
  ai_message: string;
  services: ServiceStatus[];
  db_stats: Record<string, number>;
}

interface TrainingStats {
  db: { hs_codes_pg: number; feedback_pg: number };
  ai: {
    chromadb_connected: boolean;
    openai_configured: boolean;
    collections: Record<string, number>;
    feedback_count: number;
    last_optimize_time: number | null;
    optimized_models: { hs_classifier: boolean; invoice_extractor: boolean };
    log: Array<{ ts: number; event: string; detail: string; level: string }>;
    error?: string;
  };
}

const SettingsPage = () => {
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('gpt-4o');
  const [showKey, setShowKey] = useState(false);
  const [provider, setProvider] = useState('deepseek');
  const [baseUrl, setBaseUrl] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'warning' | 'info'; text: string } | null>(null);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [trainingStats, setTrainingStats] = useState<TrainingStats | null>(null);
  const [loadingTnved, setLoadingTnved] = useState(false);
  const [indexingRag, setIndexingRag] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [aiDebug, setAiDebug] = useState<any>(null);
  const [debugLoading, setDebugLoading] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const loadAiDebug = useCallback(async () => {
    setDebugLoading(true);
    try {
      const resp = await client.get('/ai/health/detailed');
      setAiDebug(resp.data);
    } catch { /* ai-service may be down */ }
    finally { setDebugLoading(false); }
  }, []);

  useEffect(() => { loadSettings(); loadTrainingStats(); loadAiDebug(); }, []);

  const loadSettings = async () => {
    try {
      const resp = await client.get('/settings/');
      setSettings(resp.data);
      setModel(resp.data.openai_model || 'gpt-4o');
      setProvider(resp.data.llm_provider || 'deepseek');
    } catch (e) {
      console.error('Failed to load settings:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadTrainingStats = useCallback(async () => {
    try {
      const resp = await client.get('/settings/training-stats');
      setTrainingStats(resp.data);
    } catch (e) {
      console.error('Failed to load training stats:', e);
    }
  }, []);

  const handleSaveKey = async () => {
    if (!apiKey.trim()) { setMessage({ type: 'error', text: 'Введите API ключ' }); return; }
    if (!apiKey.startsWith('sk-')) { setMessage({ type: 'error', text: 'API ключ должен начинаться с "sk-"' }); return; }
    setSaving(true);
    setMessage(null);
    try {
      const resp = await client.post('/settings/openai-key', {
        key: 'openai_api_key',
        value: apiKey,
        provider: provider,
        base_url: provider === 'deepseek' ? 'https://api.deepseek.com'
                 : provider === 'custom' ? baseUrl
                 : undefined,
      });
      if (resp.data.status === 'saved') {
        const check = resp.data.ai_check || {};
        if (check.status === 'ok') setMessage({ type: 'success', text: 'OpenAI API ключ сохранён, проверен и применён.' });
        else if (check.status === 'no_balance') setMessage({ type: 'error', text: 'Ключ сохранён, но на счету OpenAI нет средств.' });
        else if (check.status === 'invalid') setMessage({ type: 'error', text: 'Неверный API ключ.' });
        else setMessage({ type: 'warning', text: `Ключ сохранён. ${check.message || ''}` });
        setApiKey('');
        await loadSettings();
        await loadTrainingStats();
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || 'Ошибка сохранения' });
    } finally { setSaving(false); }
  };

  const handleSaveModel = async () => {
    try {
      await client.post('/settings/openai-model', { key: 'openai_model', value: model });
      setMessage({ type: 'success', text: `Модель изменена на ${model}` });
      await loadSettings();
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || 'Ошибка' });
    }
  };

  const handleLoadTnved = async () => {
    setLoadingTnved(true);
    try {
      const resp = await client.post('/settings/load-tnved');
      setMessage({ type: 'success', text: `ТН ВЭД: ${resp.data.message || `загружено ${resp.data.loaded || resp.data.count} кодов`}` });
      await loadSettings();
      await loadTrainingStats();
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || 'Ошибка загрузки ТН ВЭД' });
    } finally { setLoadingTnved(false); }
  };

  const handleInitRag = async () => {
    setIndexingRag(true);
    try {
      const resp = await client.post('/settings/init-rag');
      setMessage({ type: 'success', text: `RAG: ${resp.data.codes_sent || 0} кодов отправлено в ChromaDB` });
      await loadTrainingStats();
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || 'Ошибка индексации' });
    } finally { setIndexingRag(false); }
  };

  const handleOptimize = async () => {
    setOptimizing(true);
    try {
      const resp = await client.post('/ai/optimize');
      if (resp.data.status === 'not_enough_data') {
        setMessage({ type: 'warning', text: `Недостаточно данных: ${resp.data.feedback_count}/${resp.data.min_required} примеров` });
      } else {
        setMessage({ type: 'success', text: `Оптимизация: ${resp.data.status}, примеров: ${resp.data.examples}` });
      }
      await loadTrainingStats();
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || 'Ошибка оптимизации' });
    } finally { setOptimizing(false); }
  };

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [trainingStats?.ai?.log?.length]);

  if (loading) {
    return <AppLayout breadcrumbs={[{ label: 'Настройки' }]}><Box sx={{ textAlign: 'center', py: 4 }}><CircularProgress /></Box></AppLayout>;
  }

  const aiStats = trainingStats?.ai;
  const dbStats = trainingStats?.db;
  const collections = aiStats?.collections || {};
  const logEntries = aiStats?.log || [];

  const fmtTime = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <AppLayout breadcrumbs={[{ label: 'Настройки' }]}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
        <SettingsIcon color="primary" />
        <Typography variant="h5" fontWeight={600}>Настройки системы</Typography>
      </Box>

      {message && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>{message.text}</Alert>
      )}

      {/* Services Dashboard */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6" fontWeight={600}>Статус сервисов</Typography>
          <Chip
            label={`${settings?.services?.filter(s => s.status === 'ok').length || 0}/${settings?.services?.length || 0} работают`}
            color={settings?.services?.every(s => s.status === 'ok') ? 'success' : 'warning'} size="small"
          />
        </Box>
        <Grid container spacing={1.5}>
          {(settings?.services || []).map((svc) => (
            <Grid item xs={6} md={3} key={svc.name}>
              <Card variant="outlined" sx={{
                borderColor: svc.status === 'ok' ? 'success.light' : 'error.light',
                bgcolor: svc.status === 'ok' ? '#f9fdf9' : '#fef9f9',
              }}>
                <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                    {svc.status === 'ok' ? <CheckIcon sx={{ fontSize: 16, color: 'success.main' }} /> : <ErrorIcon sx={{ fontSize: 16, color: 'error.main' }} />}
                    <Typography variant="body2" fontWeight={700}>{svc.name}</Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary">:{svc.port} — {svc.detail}</Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Paper>

      {/* DB Stats */}
      {settings?.db_stats && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>База данных</Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            {settings.db_stats.hs_codes != null && <Chip label={`ТН ВЭД: ${settings.db_stats.hs_codes.toLocaleString()}`} size="small" variant="outlined" />}
            {settings.db_stats.classifiers != null && <Chip label={`Справочники: ${settings.db_stats.classifiers}`} size="small" variant="outlined" />}
            {settings.db_stats.declarations != null && <Chip label={`Декларации: ${settings.db_stats.declarations}`} size="small" variant="outlined" />}
            {settings.db_stats.users != null && <Chip label={`Пользователи: ${settings.db_stats.users}`} size="small" variant="outlined" />}
            {settings.db_stats.counterparties != null && <Chip label={`Контрагенты: ${settings.db_stats.counterparties}`} size="small" variant="outlined" />}
          </Box>
        </Paper>
      )}

      {/* AI Status Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6} md={3}>
          <Card variant="outlined">
            <CardContent sx={{ textAlign: 'center', py: 2 }}>
              <AiIcon sx={{ fontSize: 36, color: settings?.openai_api_key_set ? 'success.main' : 'grey.400' }} />
              <Typography variant="subtitle2" sx={{ mt: 0.5 }}>OpenAI</Typography>
              <Chip size="small" icon={settings?.openai_api_key_set ? <CheckIcon /> : <ErrorIcon />}
                label={settings?.openai_api_key_set ? 'Подключён' : 'Не настроен'}
                color={settings?.openai_api_key_set ? 'success' : 'error'} sx={{ mt: 0.5 }} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card variant="outlined">
            <CardContent sx={{ textAlign: 'center', py: 2 }}>
              <StorageIcon sx={{ fontSize: 36, color: aiStats?.chromadb_connected ? 'success.main' : 'grey.400' }} />
              <Typography variant="subtitle2" sx={{ mt: 0.5 }}>ChromaDB</Typography>
              <Chip size="small"
                label={aiStats?.chromadb_connected ? `${collections.hs_codes || 0} кодов` : 'disconnected'}
                color={aiStats?.chromadb_connected ? 'success' : 'warning'} sx={{ mt: 0.5 }} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card variant="outlined">
            <CardContent sx={{ textAlign: 'center', py: 2 }}>
              <TrainIcon sx={{ fontSize: 36, color: (aiStats?.feedback_count || 0) > 0 ? 'info.main' : 'grey.400' }} />
              <Typography variant="subtitle2" sx={{ mt: 0.5 }}>Обучение</Typography>
              <Chip size="small"
                label={`${aiStats?.feedback_count || 0} feedback / ${collections.precedents || 0} прец.`}
                color="info" sx={{ mt: 0.5 }} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card variant="outlined">
            <CardContent sx={{ textAlign: 'center', py: 2 }}>
              <AiIcon sx={{ fontSize: 36, color: 'primary.main' }} />
              <Typography variant="subtitle2" sx={{ mt: 0.5 }}>Модель</Typography>
              <Chip size="small" label={settings?.openai_model || 'gpt-4o'} color="primary" sx={{ mt: 0.5 }} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {settings?.ai_message && (
        <Alert severity={settings.ai_status === 'active' ? 'success' : settings.ai_status === 'no_key' ? 'warning' : 'info'} sx={{ mb: 3 }}>
          <Typography variant="body2" fontWeight={600}>{settings.ai_message}</Typography>
        </Alert>
      )}

      {/* AI Service Debug Panel */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6" fontWeight={600} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ConsoleIcon fontSize="small" /> AI Service Debug
          </Typography>
          <Button size="small" startIcon={debugLoading ? <CircularProgress size={14} /> : <RefreshIcon />} onClick={loadAiDebug} disabled={debugLoading}>
            Обновить
          </Button>
        </Box>

        {aiDebug ? (
          <>
            <Grid container spacing={1.5} sx={{ mb: 2 }}>
              {/* DSPy */}
              <Grid item xs={6} md={3}>
                <Card variant="outlined" sx={{ borderColor: aiDebug.dspy?.available ? 'success.light' : 'error.light' }}>
                  <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                    <Typography variant="body2" fontWeight={700}>DSPy</Typography>
                    <Chip size="small" label={aiDebug.dspy?.available ? 'Installed' : 'Not installed'} color={aiDebug.dspy?.available ? 'success' : 'error'} sx={{ mr: 0.5, mt: 0.5 }} />
                    {aiDebug.dspy?.available && (
                      <Chip size="small" label={aiDebug.dspy?.configured ? 'Configured' : 'Not configured'} color={aiDebug.dspy?.configured ? 'success' : 'warning'} sx={{ mt: 0.5 }} />
                    )}
                    <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                      Demos: {aiDebug.dspy?.demos_count || 0} few-shot
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              {/* RAG */}
              <Grid item xs={6} md={3}>
                <Card variant="outlined" sx={{ borderColor: (aiDebug.rag?.hs_codes || 0) > 0 ? 'success.light' : 'warning.light' }}>
                  <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                    <Typography variant="body2" fontWeight={700}>RAG ChromaDB</Typography>
                    <Typography variant="caption" display="block">ТН ВЭД: {(aiDebug.rag?.hs_codes || 0).toLocaleString()}</Typography>
                    <Typography variant="caption" display="block">Правила СУР: {aiDebug.rag?.risk_rules || 0}</Typography>
                    <Typography variant="caption" display="block">Прецеденты: {aiDebug.rag?.precedents || 0}</Typography>
                    <Typography variant="caption" display="block" color="text.secondary">Embed: {aiDebug.embed_provider || 'onnx'}</Typography>
                  </CardContent>
                </Card>
              </Grid>

              {/* LLM */}
              <Grid item xs={6} md={3}>
                <Card variant="outlined" sx={{ borderColor: aiDebug.llm_configured ? 'success.light' : 'error.light' }}>
                  <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                    <Typography variant="body2" fontWeight={700}>LLM</Typography>
                    <Chip size="small" label={aiDebug.llm_configured ? 'Connected' : 'No key'} color={aiDebug.llm_configured ? 'success' : 'error'} sx={{ mt: 0.5 }} />
                    <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>{aiDebug.llm_provider || '?'} / {aiDebug.llm_model || '?'}</Typography>
                  </CardContent>
                </Card>
              </Grid>

              {/* Last Parse */}
              <Grid item xs={6} md={3}>
                <Card variant="outlined" sx={{ borderColor: aiDebug.last_parse?.status === 'complete' ? 'success.light' : 'grey.300' }}>
                  <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                    <Typography variant="body2" fontWeight={700}>Последний парсинг</Typography>
                    {aiDebug.last_parse?.request_id ? (
                      <>
                        <Typography variant="caption" display="block">ID: {aiDebug.last_parse.request_id}</Typography>
                        <Typography variant="caption" display="block">Позиций: {aiDebug.last_parse.items_count}, conf: {(aiDebug.last_parse.confidence * 100).toFixed(0)}%</Typography>
                        <Typography variant="caption" display="block" color="text.secondary">
                          {aiDebug.last_parse.timestamp ? new Date(aiDebug.last_parse.timestamp * 1000).toLocaleTimeString('ru-RU') : ''}
                        </Typography>
                      </>
                    ) : (
                      <Typography variant="caption" color="text.secondary">Нет данных</Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            {/* Last parse items preview */}
            {aiDebug.last_parse?.items_preview?.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" fontWeight={700}>Позиции последнего парсинга:</Typography>
                {aiDebug.last_parse.items_preview.map((it: any, i: number) => (
                  <Typography key={i} variant="caption" display="block" sx={{ fontFamily: 'monospace', ml: 1 }}>
                    {i + 1}. [{it.hs || '???'}] {it.desc || '—'}
                  </Typography>
                ))}
              </Box>
            )}

            {/* Training Log */}
            {aiDebug.training_log?.length > 0 && (
              <>
                <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>Лог ai-service (последние 30)</Typography>
                <Box sx={{
                  bgcolor: '#1e1e1e', color: '#d4d4d4', borderRadius: 1, p: 1.5,
                  fontFamily: 'monospace', fontSize: 11, lineHeight: 1.5,
                  maxHeight: 200, overflowY: 'auto', whiteSpace: 'pre-wrap',
                }}>
                  {aiDebug.training_log.map((entry: any, i: number) => {
                    const color = entry.level === 'error' ? '#f44' : entry.level === 'warning' ? '#fa0' : '#4f4';
                    const ts = entry.ts ? new Date(entry.ts * 1000).toLocaleTimeString('ru-RU') : '';
                    return (
                      <Box key={i}>
                        <span style={{ color: '#888' }}>[{ts}]</span>{' '}
                        <span style={{ color }}>{entry.event}</span>{' '}
                        <span style={{ color: '#aaa' }}>{entry.detail}</span>
                      </Box>
                    );
                  })}
                  <div ref={logEndRef} />
                </Box>
              </>
            )}
          </>
        ) : (
          <Typography variant="body2" color="text.secondary">AI-service недоступен</Typography>
        )}
      </Paper>

      {/* === AI CONSOLE === */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <ConsoleIcon color="primary" />
          <Typography variant="h6" fontWeight={600}>AI Консоль</Typography>
          <Box sx={{ flex: 1 }} />
          <Button size="small" startIcon={<RefreshIcon />} onClick={loadTrainingStats}>Обновить</Button>
        </Box>

        <Divider sx={{ mb: 2 }} />

        {/* Knowledge Base */}
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>База знаний ТН ВЭД</Typography>
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={6} md={3}>
            <Box sx={{ textAlign: 'center', p: 1, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <Typography variant="h5" fontWeight={700} color="primary.main">{(dbStats?.hs_codes_pg || 0).toLocaleString()}</Typography>
              <Typography variant="caption" color="text.secondary">в PostgreSQL</Typography>
            </Box>
          </Grid>
          <Grid item xs={6} md={3}>
            <Box sx={{ textAlign: 'center', p: 1, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <Typography variant="h5" fontWeight={700} color="success.main">{(collections.hs_codes || 0).toLocaleString()}</Typography>
              <Typography variant="caption" color="text.secondary">в ChromaDB (RAG)</Typography>
            </Box>
          </Grid>
          <Grid item xs={6} md={3}>
            <Button variant="contained" size="small" fullWidth startIcon={loadingTnved ? <CircularProgress size={16} color="inherit" /> : <UploadIcon />}
              onClick={handleLoadTnved} disabled={loadingTnved}>
              {loadingTnved ? 'Загрузка...' : 'Загрузить ТН ВЭД'}
            </Button>
          </Grid>
          <Grid item xs={6} md={3}>
            <Button variant="outlined" size="small" fullWidth startIcon={indexingRag ? <CircularProgress size={16} /> : <StorageIcon />}
              onClick={handleInitRag} disabled={indexingRag || (dbStats?.hs_codes_pg || 0) === 0}>
              {indexingRag ? 'Индексация...' : 'Индексировать RAG'}
            </Button>
          </Grid>
        </Grid>
        {(loadingTnved || indexingRag) && <LinearProgress sx={{ mb: 2 }} />}

        <Divider sx={{ my: 2 }} />

        {/* Training */}
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>Обучение модели</Typography>
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={4} md={2}>
            <Box sx={{ textAlign: 'center', p: 1, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <Typography variant="h6" fontWeight={700}>{aiStats?.feedback_count || 0}</Typography>
              <Typography variant="caption" color="text.secondary">feedback</Typography>
            </Box>
          </Grid>
          <Grid item xs={4} md={2}>
            <Box sx={{ textAlign: 'center', p: 1, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <Typography variant="h6" fontWeight={700}>{collections.precedents || 0}</Typography>
              <Typography variant="caption" color="text.secondary">прецедентов</Typography>
            </Box>
          </Grid>
          <Grid item xs={4} md={2}>
            <Box sx={{ textAlign: 'center', p: 1, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <Typography variant="h6" fontWeight={700}>{collections.risk_rules || 0}</Typography>
              <Typography variant="caption" color="text.secondary">правил СУР</Typography>
            </Box>
          </Grid>
          <Grid item xs={6} md={3}>
            <Box sx={{ p: 1, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <Typography variant="caption" color="text.secondary">Оптимизация</Typography>
              <Typography variant="body2" fontWeight={600}>
                {aiStats?.optimized_models?.hs_classifier
                  ? 'HS классификатор обучен'
                  : 'Не проводилась'}
              </Typography>
              {aiStats?.last_optimize_time && (
                <Typography variant="caption" color="text.secondary">
                  {new Date(aiStats.last_optimize_time * 1000).toLocaleString('ru-RU')}
                </Typography>
              )}
            </Box>
          </Grid>
          <Grid item xs={6} md={3}>
            <Button variant="outlined" size="small" fullWidth color="secondary"
              startIcon={optimizing ? <CircularProgress size={16} /> : <PlayIcon />}
              onClick={handleOptimize} disabled={optimizing}>
              {optimizing ? 'Оптимизация...' : 'Запустить оптимизацию'}
            </Button>
          </Grid>
        </Grid>

        <Divider sx={{ my: 2 }} />

        {/* Log Console */}
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>Лог обучения</Typography>
        <Box sx={{
          bgcolor: '#1e1e1e', color: '#d4d4d4', borderRadius: 1, p: 1.5,
          fontFamily: 'monospace', fontSize: 12, lineHeight: 1.6,
          maxHeight: 260, overflowY: 'auto', whiteSpace: 'pre-wrap',
        }}>
          {logEntries.length === 0 && (
            <Box sx={{ color: '#666' }}>Нет событий. Загрузите ТН ВЭД и индексируйте RAG для начала.</Box>
          )}
          {logEntries.map((entry, i) => {
            const color = entry.level === 'error' ? '#f44' : entry.level === 'warning' ? '#fa0' : '#4f4';
            return (
              <Box key={i}>
                <span style={{ color: '#888' }}>[{fmtTime(entry.ts)}]</span>{' '}
                <span style={{ color }}>{entry.event}</span>{' '}
                <span style={{ color: '#aaa' }}>{entry.detail}</span>
              </Box>
            );
          })}
          <div ref={logEndRef} />
        </Box>
      </Paper>

      {/* LLM Provider */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <AiIcon color="primary" fontSize="small" /> LLM Провайдер
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          DeepSeek рекомендуется — дешевле и быстрее OpenAI. Ключ можно получить на{' '}
          <a href="https://platform.deepseek.com/api_keys" target="_blank" rel="noopener noreferrer">platform.deepseek.com</a>.
        </Typography>

        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <TextField
            select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            size="small"
            sx={{ minWidth: 200 }}
            SelectProps={{ native: true }}
            label="Провайдер"
          >
            <option value="deepseek">DeepSeek (рекомендуется)</option>
            <option value="openai">OpenAI</option>
            <option value="custom">Custom (свой URL)</option>
          </TextField>
        </Box>

        {/* Show base URL for custom provider */}
        {provider === 'custom' && (
          <TextField
            fullWidth label="Base URL" placeholder="https://api.example.com/v1"
            value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
            size="small" sx={{ mb: 2 }}
          />
        )}

        {/* API Key (same for all providers) */}
        {settings?.openai_api_key_set && (
          <Alert severity="success" sx={{ mb: 2 }}>API ключ установлен. Для замены введите новый ниже.</Alert>
        )}
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
          <TextField
            fullWidth label="API Key"
            placeholder={provider === 'deepseek' ? 'sk-...' : 'sk-...'}
            value={apiKey} onChange={(e) => setApiKey(e.target.value)}
            type={showKey ? 'text' : 'password'} size="small"
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton onClick={() => setShowKey(!showKey)} edge="end" size="small">
                    {showKey ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
          <Button variant="contained"
            startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveIcon />}
            onClick={handleSaveKey} disabled={saving || !apiKey.trim()} sx={{ minWidth: 140 }}>
            Сохранить
          </Button>
        </Box>
      </Paper>

      {/* Model Selection */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>Модель LLM</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField select value={model} onChange={(e) => setModel(e.target.value)} size="small" sx={{ minWidth: 200 }} SelectProps={{ native: true }}>
            <option value="deepseek-chat">DeepSeek V3 (рекомендуется)</option>
            <option value="deepseek-reasoner">DeepSeek R1 (рассуждения)</option>
            <option value="gpt-4o">GPT-4o</option>
            <option value="gpt-4o-mini">GPT-4o Mini</option>
          </TextField>
          <Button variant="outlined" onClick={handleSaveModel}>Применить</Button>
        </Box>
      </Paper>
    </AppLayout>
  );
};

export default SettingsPage;
