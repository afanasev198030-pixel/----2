import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Paper, Typography, TextField, Button, Box, Alert,
  Chip, Divider, IconButton, InputAdornment, CircularProgress,
  Card, CardContent, Grid, LinearProgress, List, ListItem,
  ListItemButton, ListItemIcon, ListItemText,
} from '@mui/material';
import AppLayout from '../components/AppLayout';
import {
  Visibility, VisibilityOff, Save as SaveIcon,
  CheckCircle as CheckIcon, Error as ErrorIcon,
  Settings as SettingsIcon, SmartToy as AiIcon,
  Storage as StorageIcon, School as TrainIcon,
  Terminal as ConsoleIcon, Refresh as RefreshIcon,
  CloudUpload as UploadIcon, PlayArrow as PlayIcon,
  People as PeopleIcon, History as AuditIcon,
  MenuBook as BookIcon, ChecklistRtl as ChecklistIcon,
  Dashboard as DashboardIcon, ChevronRight,
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
  const navigate = useNavigate();
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('deepseek-chat');
  const [showKey, setShowKey] = useState(false);
  const [provider, setProvider] = useState('deepseek');
  const [baseUrl, setBaseUrl] = useState('');
  const [projectId, setProjectId] = useState('');
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
  const [parseIssues, setParseIssues] = useState<any>(null);
  const [issuesLoading, setIssuesLoading] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);
  const [availableModels, setAvailableModels] = useState<Array<{id: string, owned_by?: string}>>([]);
  const [modelsLoading, setModelsLoading] = useState(false);

  const loadModels = useCallback(async () => {
    setModelsLoading(true);
    try {
      const resp = await client.get('/ai/models');
      const models = (resp.data?.models || []).filter((m: any) => m.id);
      if (models.length > 0) {
        setAvailableModels(models);
      }
    } catch (e) {
      console.error('Failed to load models from provider:', e);
    } finally { setModelsLoading(false); }
  }, []);

  const loadAiDebug = useCallback(async () => {
    setDebugLoading(true);
    try {
      const resp = await client.get('/ai/health-detailed');
      setAiDebug(resp.data);
    } catch { /* ai-service may be down */ }
    finally { setDebugLoading(false); }
  }, []);

  const loadParseIssues = useCallback(async () => {
    setIssuesLoading(true);
    try {
      const [summaryResp, listResp] = await Promise.all([
        client.get('/settings/parse-issues/summary'),
        client.get('/settings/parse-issues?limit=30'),
      ]);
      setParseIssues({ summary: summaryResp.data, items: listResp.data.items });
    } catch { /* may fail if table not created yet */ }
    finally { setIssuesLoading(false); }
  }, []);

  useEffect(() => { loadSettings(); loadTrainingStats(); loadAiDebug(); loadParseIssues(); loadModels(); }, []);

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
    setSaving(true);
    setMessage(null);
    try {
      const baseUrlMap: Record<string, string | undefined> = {
        deepseek: 'https://api.deepseek.com',
        cloud_ru: 'https://foundation-models.api.cloud.ru/v1',
        proxyapi: baseUrl || 'https://api.proxyapi.ru/openai/v1',
        custom: baseUrl || undefined,
      };
      const resp = await client.post('/settings/openai-key', {
        key: 'openai_api_key',
        value: apiKey,
        provider: provider,
        base_url: baseUrlMap[provider],
        project_id: provider === 'cloud_ru' ? projectId : undefined,
      });
      if (resp.data.status === 'saved') {
        const check = resp.data.ai_check || {};
        if (check.status === 'ok') setMessage({ type: 'success', text: 'API ключ сохранён, проверен и применён.' });
        else if (check.status === 'no_balance') setMessage({ type: 'error', text: 'Ключ сохранён, но на счету нет средств.' });
        else if (check.status === 'invalid') setMessage({ type: 'error', text: 'Неверный API ключ.' });
        else setMessage({ type: 'warning', text: `Ключ сохранён. ${check.message || ''}` });
        setApiKey('');
        await loadSettings();
        await loadTrainingStats();
        await loadModels();
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
      await loadModels();
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
      if (resp.data.status === 'started') {
        setMessage({ type: 'info', text: resp.data.message });
        // Поллинг прогресса каждые 5 сек
        const poll = setInterval(async () => {
          try {
            const st = await client.get('/settings/init-rag/status');
            const d = st.data;
            if (!d.running) {
              clearInterval(poll);
              setIndexingRag(false);
              setMessage({ type: d.errors > 0 ? 'warning' : 'success', text: d.message });
              await loadTrainingStats();
              await loadAiDebug();
            } else {
              setMessage({ type: 'info', text: `RAG: ${d.message} (${d.progress}%)` });
            }
          } catch { clearInterval(poll); setIndexingRag(false); }
        }, 5000);
      } else if (resp.data.status === 'already_running') {
        setMessage({ type: 'info', text: resp.data.message });
        setIndexingRag(false);
      } else {
        setMessage({ type: 'warning', text: resp.data.message || 'Неизвестный статус' });
        setIndexingRag(false);
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || 'Ошибка индексации' });
      setIndexingRag(false);
    }
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
        <Typography variant="h5" fontWeight={600} sx={{ color: '#0f172a' }}>Настройки системы</Typography>
      </Box>

      {message && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>{message.text}</Alert>
      )}

      {/* Services Dashboard */}
      <Paper sx={{ p: 2, mb: 3, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6" fontWeight={600} sx={{ color: '#0f172a' }}>Статус сервисов</Typography>
          <Chip
            label={`${settings?.services?.filter(s => s.status === 'ok').length || 0}/${settings?.services?.length || 0} работают`}
            size="small"
            sx={
              settings?.services?.every(s => s.status === 'ok')
                ? {
                    backgroundColor: 'rgba(236,253,245,0.8)',
                    color: '#065f46',
                    border: '1px solid rgba(167,243,208,0.6)',
                    fontWeight: 500,
                  }
                : {
                    backgroundColor: 'rgba(255,251,235,0.8)',
                    color: '#92400e',
                    border: '1px solid rgba(253,230,138,0.6)',
                    fontWeight: 500,
                  }
            }
          />
        </Box>
        <Grid container spacing={1.5}>
          {(settings?.services || []).map((svc) => (
            <Grid item xs={6} md={3} key={svc.name}>
              <Card variant="outlined" sx={{
                border: '1px solid rgba(226,232,240,0.8)',
                boxShadow: 'none',
                borderColor: svc.status === 'ok' ? 'rgba(167,243,208,0.7)' : 'rgba(254,202,202,0.8)',
                bgcolor: svc.status === 'ok' ? 'rgba(236,253,245,0.5)' : 'rgba(254,242,242,0.6)',
              }}>
                <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                    {svc.status === 'ok' ? <CheckIcon sx={{ fontSize: 16, color: '#059669' }} /> : <ErrorIcon sx={{ fontSize: 16, color: '#dc2626' }} />}
                    <Typography variant="body2" fontWeight={700} sx={{ color: '#0f172a' }}>{svc.name}</Typography>
                  </Box>
                  <Typography variant="caption" sx={{ color: '#64748b' }}>:{svc.port} — {svc.detail}</Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Paper>

      {/* DB Stats */}
      {settings?.db_stats && (
        <Paper sx={{ p: 2, mb: 3, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1, color: '#0f172a' }}>База данных</Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            {settings.db_stats.hs_codes != null && <Chip label={`ТН ВЭД: ${settings.db_stats.hs_codes.toLocaleString()}`} size="small" variant="outlined" sx={{ borderColor: 'rgba(226,232,240,0.8)', color: '#475569', bgcolor: '#f8fafc' }} />}
            {settings.db_stats.classifiers != null && <Chip label={`Справочники: ${settings.db_stats.classifiers}`} size="small" variant="outlined" sx={{ borderColor: 'rgba(226,232,240,0.8)', color: '#475569', bgcolor: '#f8fafc' }} />}
            {settings.db_stats.declarations != null && <Chip label={`Декларации: ${settings.db_stats.declarations}`} size="small" variant="outlined" sx={{ borderColor: 'rgba(226,232,240,0.8)', color: '#475569', bgcolor: '#f8fafc' }} />}
            {settings.db_stats.users != null && <Chip label={`Пользователи: ${settings.db_stats.users}`} size="small" variant="outlined" sx={{ borderColor: 'rgba(226,232,240,0.8)', color: '#475569', bgcolor: '#f8fafc' }} />}
            {settings.db_stats.counterparties != null && <Chip label={`Контрагенты: ${settings.db_stats.counterparties}`} size="small" variant="outlined" sx={{ borderColor: 'rgba(226,232,240,0.8)', color: '#475569', bgcolor: '#f8fafc' }} />}
          </Box>
        </Paper>
      )}

      {/* AI Status Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6} md={3}>
          <Card variant="outlined" sx={{ border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
            <CardContent sx={{ textAlign: 'center', py: 2 }}>
              <AiIcon sx={{ fontSize: 36, color: settings?.openai_api_key_set ? '#059669' : '#94a3b8' }} />
              <Typography variant="subtitle2" sx={{ mt: 0.5, color: '#0f172a' }}>LLM</Typography>
              <Chip size="small" icon={settings?.openai_api_key_set ? <CheckIcon /> : <ErrorIcon />}
                label={settings?.openai_api_key_set ? 'Подключён' : 'Не настроен'}
                sx={{
                  mt: 0.5,
                  ...(settings?.openai_api_key_set
                    ? {
                        backgroundColor: 'rgba(236,253,245,0.8)',
                        color: '#065f46',
                        border: '1px solid rgba(167,243,208,0.6)',
                        fontWeight: 500,
                        '& .MuiChip-icon': { color: '#059669' },
                      }
                    : {
                        backgroundColor: 'rgba(254,242,242,0.8)',
                        color: '#991b1b',
                        border: '1px solid rgba(254,202,202,0.6)',
                        fontWeight: 500,
                        '& .MuiChip-icon': { color: '#dc2626' },
                      }),
                }} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card variant="outlined" sx={{ border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
            <CardContent sx={{ textAlign: 'center', py: 2 }}>
              <StorageIcon sx={{ fontSize: 36, color: aiStats?.chromadb_connected ? '#059669' : '#94a3b8' }} />
              <Typography variant="subtitle2" sx={{ mt: 0.5, color: '#0f172a' }}>ChromaDB</Typography>
              <Chip size="small"
                label={aiStats?.chromadb_connected ? `${collections.hs_codes || 0} кодов` : 'disconnected'}
                sx={{
                  mt: 0.5,
                  ...(aiStats?.chromadb_connected
                    ? {
                        backgroundColor: 'rgba(236,253,245,0.8)',
                        color: '#065f46',
                        border: '1px solid rgba(167,243,208,0.6)',
                        fontWeight: 500,
                      }
                    : {
                        backgroundColor: 'rgba(255,251,235,0.8)',
                        color: '#92400e',
                        border: '1px solid rgba(253,230,138,0.6)',
                        fontWeight: 500,
                      }),
                }} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card variant="outlined" sx={{ border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
            <CardContent sx={{ textAlign: 'center', py: 2 }}>
              <TrainIcon sx={{ fontSize: 36, color: (aiStats?.feedback_count || 0) > 0 ? '#2563eb' : '#94a3b8' }} />
              <Typography variant="subtitle2" sx={{ mt: 0.5, color: '#0f172a' }}>Обучение</Typography>
              <Chip size="small"
                label={`${aiStats?.feedback_count || 0} feedback / ${collections.precedents || 0} прец.`}
                sx={{
                  mt: 0.5,
                  backgroundColor: '#eef2ff',
                  color: '#3730a3',
                  border: '1px solid rgba(199,210,254,0.6)',
                  fontWeight: 500,
                }} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card variant="outlined" sx={{ border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
            <CardContent sx={{ textAlign: 'center', py: 2 }}>
              <AiIcon sx={{ fontSize: 36, color: '#2563eb' }} />
              <Typography variant="subtitle2" sx={{ mt: 0.5, color: '#0f172a' }}>Модель</Typography>
              <Chip size="small" label={settings?.openai_model || 'gpt-4o'} sx={{
                mt: 0.5,
                backgroundColor: '#eef2ff',
                color: '#3730a3',
                border: '1px solid rgba(199,210,254,0.6)',
                fontWeight: 500,
              }} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {settings?.ai_message && (
        <Alert severity={settings.ai_status === 'active' ? 'success' : settings.ai_status === 'no_key' ? 'warning' : 'info'} sx={{ mb: 3 }}>
          <Typography variant="body2" fontWeight={600} sx={{ color: '#0f172a' }}>{settings.ai_message}</Typography>
        </Alert>
      )}

      {/* Parse Issues */}
      {parseIssues && (parseIssues.summary?.total > 0 || parseIssues.items?.length > 0) && (
        <Paper sx={{ p: 2, mb: 3, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6" fontWeight={600} sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#0f172a' }}>
              <ErrorIcon fontSize="small" sx={{ color: '#dc2626' }} /> Проблемы парсинга
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              {parseIssues.summary?.totals?.error > 0 && <Chip label={`${parseIssues.summary.totals.error} errors`} size="small" sx={{ backgroundColor: 'rgba(254,242,242,0.8)', color: '#991b1b', border: '1px solid rgba(254,202,202,0.6)', fontWeight: 500 }} />}
              {parseIssues.summary?.totals?.warning > 0 && <Chip label={`${parseIssues.summary.totals.warning} warnings`} size="small" sx={{ backgroundColor: 'rgba(255,251,235,0.8)', color: '#92400e', border: '1px solid rgba(253,230,138,0.6)', fontWeight: 500 }} />}
              {parseIssues.summary?.totals?.info > 0 && <Chip label={`${parseIssues.summary.totals.info} info`} size="small" sx={{ backgroundColor: '#eef2ff', color: '#3730a3', border: '1px solid rgba(199,210,254,0.6)', fontWeight: 500 }} />}
              <Button size="small" startIcon={issuesLoading ? <CircularProgress size={14} /> : <RefreshIcon />} onClick={loadParseIssues} disabled={issuesLoading}>
                Обновить
              </Button>
            </Box>
          </Box>
          {parseIssues.items?.length > 0 && (
            <Box sx={{
              bgcolor: '#1a1a1a', color: '#e0e0e0', borderRadius: 1, p: 1.5,
              fontFamily: 'monospace', fontSize: 11, lineHeight: 1.5,
              maxHeight: 300, overflowY: 'auto',
            }}>
              {parseIssues.items.map((issue: any, i: number) => {
                const color = issue.severity === 'error' ? '#ef5350' : issue.severity === 'warning' ? '#ffa726' : '#66bb6a';
                const ts = issue.created_at ? new Date(issue.created_at).toLocaleTimeString('ru-RU') : '';
                return (
                  <Box key={i} sx={{ mb: 0.8, pb: 0.8, borderBottom: '1px solid #333' }}>
                    <span style={{ color: '#888' }}>[{ts}]</span>{' '}
                    <span style={{ color, fontWeight: 700 }}>{issue.severity.toUpperCase()}</span>{' '}
                    <span style={{ color: '#4fc3f7' }}>{issue.stage}</span>{' '}
                    <span>{issue.message}</span>
                    {issue.details?.description && (
                      <Box sx={{ ml: 2, color: '#aaa', fontSize: 10 }}>Товар: {issue.details.description}</Box>
                    )}
                    {issue.details?.error && (
                      <Box sx={{ ml: 2, color: '#ef9a9a', fontSize: 10 }}>{issue.details.error.substring(0, 150)}</Box>
                    )}
                  </Box>
                );
              })}
            </Box>
          )}
        </Paper>
      )}

      {/* AI Service Debug Panel */}
      <Paper sx={{ p: 2, mb: 3, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6" fontWeight={600} sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#0f172a' }}>
            <ConsoleIcon fontSize="small" sx={{ color: '#64748b' }} /> AI Service Debug
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
                <Card variant="outlined" sx={{
                  border: '1px solid rgba(226,232,240,0.8)',
                  boxShadow: 'none',
                  borderColor: aiDebug.dspy?.available ? 'rgba(167,243,208,0.7)' : 'rgba(254,202,202,0.8)',
                  bgcolor: aiDebug.dspy?.available ? 'rgba(236,253,245,0.35)' : 'rgba(254,242,242,0.45)',
                }}>
                  <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                    <Typography variant="body2" fontWeight={700} sx={{ color: '#0f172a' }}>DSPy</Typography>
                    <Chip size="small" label={aiDebug.dspy?.available ? 'Installed' : 'Not installed'} sx={{
                      mr: 0.5, mt: 0.5,
                      ...(aiDebug.dspy?.available
                        ? { backgroundColor: 'rgba(236,253,245,0.8)', color: '#065f46', border: '1px solid rgba(167,243,208,0.6)', fontWeight: 500 }
                        : { backgroundColor: 'rgba(254,242,242,0.8)', color: '#991b1b', border: '1px solid rgba(254,202,202,0.6)', fontWeight: 500 }),
                    }} />
                    {aiDebug.dspy?.available && (
                      <Chip size="small" label={aiDebug.dspy?.configured ? 'Configured' : 'Not configured'} sx={{
                        mt: 0.5,
                        ...(aiDebug.dspy?.configured
                          ? { backgroundColor: 'rgba(236,253,245,0.8)', color: '#065f46', border: '1px solid rgba(167,243,208,0.6)', fontWeight: 500 }
                          : { backgroundColor: 'rgba(255,251,235,0.8)', color: '#92400e', border: '1px solid rgba(253,230,138,0.6)', fontWeight: 500 }),
                      }} />
                    )}
                    <Typography variant="caption" display="block" sx={{ mt: 0.5, color: '#64748b' }}>
                      Demos: {aiDebug.dspy?.demos_count || 0} few-shot
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              {/* RAG */}
              <Grid item xs={6} md={3}>
                <Card variant="outlined" sx={{
                  border: '1px solid rgba(226,232,240,0.8)',
                  boxShadow: 'none',
                  borderColor: (aiDebug.rag?.hs_codes || 0) > 0 ? 'rgba(167,243,208,0.7)' : 'rgba(253,230,138,0.7)',
                  bgcolor: (aiDebug.rag?.hs_codes || 0) > 0 ? 'rgba(236,253,245,0.35)' : 'rgba(255,251,235,0.5)',
                }}>
                  <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                    <Typography variant="body2" fontWeight={700} sx={{ color: '#0f172a' }}>RAG ChromaDB</Typography>
                    <Typography variant="caption" display="block" sx={{ color: '#0f172a' }}>ТН ВЭД: {(aiDebug.rag?.hs_codes || 0).toLocaleString()}</Typography>
                    <Typography variant="caption" display="block" sx={{ color: '#0f172a' }}>Правила СУР: {aiDebug.rag?.risk_rules || 0}</Typography>
                    <Typography variant="caption" display="block" sx={{ color: '#0f172a' }}>Прецеденты: {aiDebug.rag?.precedents || 0}</Typography>
                    <Typography variant="caption" display="block" sx={{ color: '#64748b' }}>Embed: {aiDebug.embed_provider || 'onnx'}</Typography>
                  </CardContent>
                </Card>
              </Grid>

              {/* LLM */}
              <Grid item xs={6} md={3}>
                <Card variant="outlined" sx={{
                  border: '1px solid rgba(226,232,240,0.8)',
                  boxShadow: 'none',
                  borderColor: aiDebug.llm_configured ? 'rgba(167,243,208,0.7)' : 'rgba(254,202,202,0.8)',
                  bgcolor: aiDebug.llm_configured ? 'rgba(236,253,245,0.35)' : 'rgba(254,242,242,0.45)',
                }}>
                  <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                    <Typography variant="body2" fontWeight={700} sx={{ color: '#0f172a' }}>LLM</Typography>
                    <Chip size="small" label={aiDebug.llm_configured ? 'Connected' : 'No key'} sx={{
                      mt: 0.5,
                      ...(aiDebug.llm_configured
                        ? { backgroundColor: 'rgba(236,253,245,0.8)', color: '#065f46', border: '1px solid rgba(167,243,208,0.6)', fontWeight: 500 }
                        : { backgroundColor: 'rgba(254,242,242,0.8)', color: '#991b1b', border: '1px solid rgba(254,202,202,0.6)', fontWeight: 500 }),
                    }} />
                    <Typography variant="caption" display="block" sx={{ mt: 0.5, color: '#0f172a' }}>{aiDebug.llm_provider || '?'} / {aiDebug.llm_model || '?'}</Typography>
                  </CardContent>
                </Card>
              </Grid>

              {/* Last Parse */}
              <Grid item xs={6} md={3}>
                <Card variant="outlined" sx={{
                  border: '1px solid rgba(226,232,240,0.8)',
                  boxShadow: 'none',
                  borderColor: aiDebug.last_parse?.status === 'complete' ? 'rgba(167,243,208,0.7)' : 'rgba(226,232,240,0.9)',
                  bgcolor: aiDebug.last_parse?.status === 'complete' ? 'rgba(236,253,245,0.35)' : '#f8fafc',
                }}>
                  <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                    <Typography variant="body2" fontWeight={700} sx={{ color: '#0f172a' }}>Последний парсинг</Typography>
                    {aiDebug.last_parse?.request_id ? (
                      <>
                        <Typography variant="caption" display="block" sx={{ color: '#0f172a' }}>ID: {aiDebug.last_parse.request_id}</Typography>
                        <Typography variant="caption" display="block" sx={{ color: '#0f172a' }}>Позиций: {aiDebug.last_parse.items_count}, conf: {(aiDebug.last_parse.confidence * 100).toFixed(0)}%</Typography>
                        <Typography variant="caption" display="block" sx={{ color: '#64748b' }}>
                          {aiDebug.last_parse.timestamp ? new Date(aiDebug.last_parse.timestamp * 1000).toLocaleTimeString('ru-RU') : ''}
                        </Typography>
                      </>
                    ) : (
                      <Typography variant="caption" sx={{ color: '#64748b' }}>Нет данных</Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            {/* Last parse items preview */}
            {aiDebug.last_parse?.items_preview?.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" fontWeight={700} sx={{ color: '#0f172a' }}>Позиции последнего парсинга:</Typography>
                {aiDebug.last_parse.items_preview.map((it: any, i: number) => (
                  <Typography key={i} variant="caption" display="block" sx={{ fontFamily: 'monospace', ml: 1, color: '#64748b' }}>
                    {i + 1}. [{it.hs || '???'}] {it.desc || '—'}
                  </Typography>
                ))}
              </Box>
            )}

            {/* Training Log */}
            {/* HS Classification Log */}
            {aiDebug.hs_classify_log?.length > 0 && (
              <>
                <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1, color: '#0f172a' }}>Лог классификации ТН ВЭД (промпты)</Typography>
                <Box sx={{
                  bgcolor: '#1a1a2e', color: '#e0e0e0', borderRadius: 1, p: 1.5,
                  fontFamily: 'monospace', fontSize: 11, lineHeight: 1.6,
                  maxHeight: 300, overflowY: 'auto', mb: 2,
                }}>
                  {aiDebug.hs_classify_log.map((entry: any, i: number) => {
                    const ts = entry.ts ? new Date(entry.ts * 1000).toLocaleTimeString('ru-RU') : '';
                    const methodColor = entry.method === 'dspy_rag' ? '#4fc3f7' : entry.method === 'llm_rag' ? '#81c784' : '#ffb74d';
                    return (
                      <Box key={i} sx={{ mb: 1, pb: 1, borderBottom: '1px solid #333' }}>
                        <Box>
                          <span style={{ color: '#888' }}>[{ts}]</span>{' '}
                          <span style={{ color: methodColor, fontWeight: 700 }}>{entry.method}</span>{' '}
                          {entry.model && <span style={{ color: '#888' }}>({entry.model})</span>}
                        </Box>
                        <Box sx={{ ml: 1 }}>
                          <span style={{ color: '#aaa' }}>Товар:</span>{' '}
                          <span style={{ color: '#fff' }}>{entry.description}</span>
                        </Box>
                        <Box sx={{ ml: 1 }}>
                          <span style={{ color: '#aaa' }}>Код:</span>{' '}
                          <span style={{ color: '#4caf50', fontWeight: 700 }}>{entry.hs_code}</span>{' '}
                          <span style={{ color: '#ccc' }}>{entry.name_ru}</span>{' '}
                          <span style={{ color: '#ff9800' }}>({typeof entry.confidence === 'number' ? (entry.confidence * 100).toFixed(0) : entry.confidence}%)</span>
                        </Box>
                        {entry.reasoning && (
                          <Box sx={{ ml: 1 }}>
                            <span style={{ color: '#aaa' }}>Обоснование:</span>{' '}
                            <span style={{ color: '#b0bec5' }}>{entry.reasoning}</span>
                          </Box>
                        )}
                        {entry.prompt_user && (
                          <Box sx={{ ml: 1 }}>
                            <span style={{ color: '#aaa' }}>Промпт:</span>{' '}
                            <span style={{ color: '#78909c', fontSize: 10 }}>{entry.prompt_user}</span>
                          </Box>
                        )}
                        {entry.prompt_system && (
                          <Box sx={{ ml: 1 }}>
                            <span style={{ color: '#aaa' }}>System:</span>{' '}
                            <span style={{ color: '#90caf9', fontSize: 10 }}>{entry.prompt_system}</span>
                          </Box>
                        )}
                        {entry.decision_path && (
                          <Box sx={{ ml: 1 }}>
                            <span style={{ color: '#aaa' }}>Путь решения:</span>{' '}
                            <span style={{ color: '#ffd54f' }}>{entry.decision_path}</span>
                          </Box>
                        )}
                        {entry.rag_candidates != null && (
                          <Box sx={{ ml: 1 }}>
                            <span style={{ color: '#aaa' }}>RAG кандидатов:</span>{' '}
                            <span style={{ color: '#b39ddb' }}>{entry.rag_candidates}</span>
                          </Box>
                        )}
                        {entry.context && (
                          <Box sx={{ ml: 1 }}>
                            <span style={{ color: '#aaa' }}>Контекст:</span>{' '}
                            <span style={{ color: '#78909c' }}>{entry.context}</span>
                          </Box>
                        )}
                      </Box>
                    );
                  })}
                </Box>
              </>
            )}

            {aiDebug.training_log?.length > 0 && (
              <>
                <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1, color: '#0f172a' }}>Лог ai-service (последние 30)</Typography>
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
          <Typography variant="body2" sx={{ color: '#64748b' }}>AI-service недоступен</Typography>
        )}
      </Paper>

      {/* === AI CONSOLE === */}
      <Paper sx={{ p: 3, mb: 3, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <ConsoleIcon color="primary" />
          <Typography variant="h6" fontWeight={600} sx={{ color: '#0f172a' }}>AI Консоль</Typography>
          <Box sx={{ flex: 1 }} />
          <Button size="small" startIcon={<RefreshIcon />} onClick={loadTrainingStats}>Обновить</Button>
        </Box>

        <Divider sx={{ mb: 2, borderColor: 'rgba(241,245,249,1)' }} />

        {/* Knowledge Base */}
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1, color: '#0f172a' }}>База знаний ТН ВЭД</Typography>
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={6} md={3}>
            <Box sx={{ textAlign: 'center', p: 1, bgcolor: '#f8fafc', borderRadius: 1, border: '1px solid rgba(241,245,249,1)' }}>
              <Typography variant="h5" fontWeight={700} sx={{ color: '#2563eb' }}>{(dbStats?.hs_codes_pg || 0).toLocaleString()}</Typography>
              <Typography variant="caption" sx={{ color: '#64748b' }}>в PostgreSQL</Typography>
            </Box>
          </Grid>
          <Grid item xs={6} md={3}>
            <Box sx={{ textAlign: 'center', p: 1, bgcolor: '#f8fafc', borderRadius: 1, border: '1px solid rgba(241,245,249,1)' }}>
              <Typography variant="h5" fontWeight={700} sx={{ color: '#059669' }}>{(collections.hs_codes || 0).toLocaleString()}</Typography>
              <Typography variant="caption" sx={{ color: '#64748b' }}>в ChromaDB (RAG)</Typography>
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

        <Divider sx={{ my: 2, borderColor: 'rgba(241,245,249,1)' }} />

        {/* Training */}
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1, color: '#0f172a' }}>Обучение модели</Typography>
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={4} md={2}>
            <Box sx={{ textAlign: 'center', p: 1, bgcolor: '#f8fafc', borderRadius: 1, border: '1px solid rgba(241,245,249,1)' }}>
              <Typography variant="h6" fontWeight={700} sx={{ color: '#0f172a' }}>{aiStats?.feedback_count || 0}</Typography>
              <Typography variant="caption" sx={{ color: '#64748b' }}>feedback</Typography>
            </Box>
          </Grid>
          <Grid item xs={4} md={2}>
            <Box sx={{ textAlign: 'center', p: 1, bgcolor: '#f8fafc', borderRadius: 1, border: '1px solid rgba(241,245,249,1)' }}>
              <Typography variant="h6" fontWeight={700} sx={{ color: '#0f172a' }}>{collections.precedents || 0}</Typography>
              <Typography variant="caption" sx={{ color: '#64748b' }}>прецедентов</Typography>
            </Box>
          </Grid>
          <Grid item xs={4} md={2}>
            <Box sx={{ textAlign: 'center', p: 1, bgcolor: '#f8fafc', borderRadius: 1, border: '1px solid rgba(241,245,249,1)' }}>
              <Typography variant="h6" fontWeight={700} sx={{ color: '#0f172a' }}>{collections.risk_rules || 0}</Typography>
              <Typography variant="caption" sx={{ color: '#64748b' }}>правил СУР</Typography>
            </Box>
          </Grid>
          <Grid item xs={6} md={3}>
            <Box sx={{ p: 1, bgcolor: '#f8fafc', borderRadius: 1, border: '1px solid rgba(241,245,249,1)' }}>
              <Typography variant="caption" sx={{ color: '#64748b' }}>Оптимизация</Typography>
              <Typography variant="body2" fontWeight={600} sx={{ color: '#0f172a' }}>
                {aiStats?.optimized_models?.hs_classifier
                  ? 'HS классификатор обучен'
                  : 'Не проводилась'}
              </Typography>
              {aiStats?.last_optimize_time && (
                <Typography variant="caption" sx={{ color: '#64748b' }}>
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
            <Button variant="contained" size="small" fullWidth color="primary" component="label"
              startIcon={optimizing ? <CircularProgress size={16} color="inherit" /> : <UploadIcon />}
              disabled={optimizing} sx={{ mt: 1 }}>
              Обучить на ГТД (PDF)
              <input type="file" hidden multiple accept="application/pdf" onChange={async (e) => {
                const files = e.target.files;
                if (!files || files.length === 0) return;
                setOptimizing(true);
                const formData = new FormData();
                for (let i = 0; i < files.length; i++) {
                  formData.append('files', files[i]);
                }
                try {
                  const res = await client.post('/ai/train-from-gtd', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
                  setMessage({ type: 'success', text: `Обучение завершено. Обработано файлов: ${res.data.files_processed}, сохранено прецедентов: ${res.data.precedents_saved}` });
                  await loadTrainingStats();
                } catch (err: any) {
                  setMessage({ type: 'error', text: err?.response?.data?.detail || 'Ошибка при обучении на ГТД' });
                } finally {
                  setOptimizing(false);
                  e.target.value = '';
                }
              }} />
            </Button>
          </Grid>
        </Grid>

        <Divider sx={{ my: 2, borderColor: 'rgba(241,245,249,1)' }} />

        {/* Log Console */}
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1, color: '#0f172a' }}>Лог обучения</Typography>
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
      <Paper sx={{ p: 3, mb: 3, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1, color: '#0f172a' }}>
          <AiIcon color="primary" fontSize="small" /> LLM Провайдер
        </Typography>
        <Typography variant="body2" sx={{ mb: 2, color: '#64748b' }}>
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
            <option value="cloud_ru">Cloud.ru (Foundation Models)</option>
            <option value="anthropic">Anthropic (Claude Opus 4.6)</option>
            <option value="proxyapi">ProxyAPI (прокси для OpenAI/Claude)</option>
            <option value="custom">Custom (свой URL)</option>
          </TextField>
        </Box>

        {provider === 'cloud_ru' && (
          <TextField
            fullWidth label="Project ID" placeholder="ID проекта Cloud.ru"
            value={projectId} onChange={(e) => setProjectId(e.target.value)}
            size="small" sx={{ mb: 2 }}
            helperText="Необязательное поле. ID проекта из личного кабинета Cloud.ru"
          />
        )}

        {provider === 'anthropic' && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <strong>Anthropic Claude Opus 4.6</strong><br />
            API ключ начинается с <code>sk-ant-</code>.<br />
            Рекомендуется для сложных задач таможенного оформления.
          </Alert>
        )}

        {provider === 'proxyapi' && (
          <>
            <Alert severity="info" sx={{ mb: 2 }}>
              <strong>ProxyAPI</strong> — OpenAI-совместимый прокси.<br />
              Позволяет использовать OpenAI, Claude и другие модели через единый ключ.<br />
              После сохранения ключа список моделей загрузится автоматически.
            </Alert>
            <TextField
              fullWidth label="ProxyAPI Base URL" placeholder="https://api.proxyapi.ru/openai/v1"
              value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
              size="small" sx={{ mb: 2 }}
              helperText="URL прокси-сервера (по умолчанию https://api.proxyapi.ru/openai/v1)"
            />
          </>
        )}

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
            placeholder={provider === 'cloud_ru' ? 'Bearer-токен Cloud.ru' : 'sk-...'}
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
      <Paper sx={{ p: 3, mb: 3, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6" sx={{ color: '#0f172a' }}>Модель LLM</Typography>
          {modelsLoading && <CircularProgress size={16} />}
          {availableModels.length > 0 && (
            <Chip label={`${availableModels.length} моделей от провайдера`} size="small" sx={{ backgroundColor: 'rgba(236,253,245,0.8)', color: '#065f46', border: '1px solid rgba(167,243,208,0.6)', fontWeight: 500 }} />
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField select value={model} onChange={(e) => setModel(e.target.value)} size="small" sx={{ minWidth: 300 }} SelectProps={{ native: true }}>
            {availableModels.length > 0 ? (
              <optgroup label={`Доступные модели (${provider})`}>
                {availableModels.map((m) => (
                  <option key={m.id} value={m.id}>{m.id}{m.owned_by ? ` (${m.owned_by})` : ''}</option>
                ))}
              </optgroup>
            ) : (
              <>
                <optgroup label="Anthropic">
                  <option value="claude-3-opus-4-6-202503">Claude Opus 4.6</option>
                  <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
                </optgroup>
                <optgroup label="Cloud.ru">
                  <option value="openai/gpt-oss-120b">GPT-OSS 120B (Cloud.ru)</option>
                </optgroup>
                <optgroup label="OpenAI">
                  <option value="gpt-4.1">GPT-4.1</option>
                  <option value="gpt-4.1-mini">GPT-4.1 Mini</option>
                  <option value="gpt-4.1-nano">GPT-4.1 Nano</option>
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="gpt-4o-mini">GPT-4o Mini</option>
                </optgroup>
                <optgroup label="DeepSeek">
                  <option value="deepseek-chat">DeepSeek V3</option>
                  <option value="deepseek-reasoner">DeepSeek R1</option>
                </optgroup>
              </>
            )}
          </TextField>
          <Button variant="outlined" onClick={handleSaveModel} startIcon={modelsLoading ? <CircularProgress size={14} /> : <RefreshIcon />}>
            Применить
          </Button>
          <Button size="small" onClick={loadModels} disabled={modelsLoading}>
            Обновить список
          </Button>
        </Box>
      </Paper>

      {/* Administration */}
      <Paper sx={{ p: 3, mt: 3, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
        <Typography variant="h6" fontWeight={700} sx={{ mb: 2, color: '#0f172a' }}>Администрирование</Typography>
        <List disablePadding>
          {[
            { label: 'AI-стратегии', desc: 'Бизнес-правила для AI-заполнения деклараций', icon: <AiIcon />, path: '/admin/strategies' },
            { label: 'AI-затраты', desc: 'Unit-экономика: токены, стоимость, затраты на декларацию', icon: <AiIcon />, path: '/admin/ai-costs' },
            { label: 'Пользователи', desc: 'Управление пользователями и ролями', icon: <PeopleIcon />, path: '/admin/users' },
            { label: 'Аудит-лог', desc: 'История действий в системе', icon: <AuditIcon />, path: '/admin/audit' },
            { label: 'База знаний', desc: 'Статьи по классификации товаров', icon: <BookIcon />, path: '/admin/knowledge' },
            { label: 'Чек-листы', desc: 'Шаблоны проверок деклараций', icon: <ChecklistIcon />, path: '/admin/checklists' },
          ].map(item => (
            <ListItem key={item.path} disablePadding divider sx={{ borderColor: 'rgba(241,245,249,1)' }}>
              <ListItemButton onClick={() => navigate(item.path)}>
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText
                  primary={item.label}
                  secondary={item.desc}
                  sx={{ '& .MuiListItemText-primary': { color: '#0f172a' }, '& .MuiListItemText-secondary': { color: '#64748b' } }}
                />
                <ChevronRight sx={{ color: '#94a3b8' }} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Paper>
    </AppLayout>
  );
};

export default SettingsPage;
