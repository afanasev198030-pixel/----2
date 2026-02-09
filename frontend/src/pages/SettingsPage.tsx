import { useState, useEffect } from 'react';
import {
  Container,
  Paper,
  Typography,
  TextField,
  Button,
  Box,
  Alert,
  Chip,
  Divider,
  IconButton,
  InputAdornment,
  CircularProgress,
  Card,
  CardContent,
  Grid,
} from '@mui/material';
import {
  Visibility,
  VisibilityOff,
  Save as SaveIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Settings as SettingsIcon,
  SmartToy as AiIcon,
  Storage as StorageIcon,
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

const SettingsPage = () => {
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('gpt-4o');
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'warning' | 'info'; text: string } | null>(null);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const resp = await client.get('/settings/');
      setSettings(resp.data);
      setModel(resp.data.openai_model || 'gpt-4o');
    } catch (e) {
      console.error('Failed to load settings:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveKey = async () => {
    if (!apiKey.trim()) {
      setMessage({ type: 'error', text: 'Введите API ключ' });
      return;
    }
    if (!apiKey.startsWith('sk-')) {
      setMessage({ type: 'error', text: 'API ключ должен начинаться с "sk-"' });
      return;
    }

    setSaving(true);
    setMessage(null);
    try {
      const resp = await client.post('/settings/openai-key', {
        key: 'openai_api_key',
        value: apiKey,
      });
      
      if (resp.data.status === 'saved') {
        const check = resp.data.ai_check || {};
        if (check.status === 'ok') {
          setMessage({ type: 'success', text: 'OpenAI API ключ сохранён, проверен и применён. AI работает.' });
        } else if (check.status === 'no_balance') {
          setMessage({ type: 'error', text: 'Ключ сохранён, но на счету OpenAI недостаточно средств. Пополните баланс на platform.openai.com' });
        } else if (check.status === 'invalid') {
          setMessage({ type: 'error', text: 'Неверный API ключ. Проверьте ключ и попробуйте снова.' });
        } else {
          setMessage({ type: 'warning', text: `Ключ сохранён. ${check.message || ''}` });
        }
        setApiKey('');
        await loadSettings();
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || 'Ошибка сохранения' });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveModel = async () => {
    try {
      await client.post('/settings/openai-model', {
        key: 'openai_model',
        value: model,
      });
      setMessage({ type: 'success', text: `Модель изменена на ${model}` });
      await loadSettings();
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || 'Ошибка' });
    }
  };

  if (loading) {
    return (
      <Container maxWidth="md" sx={{ py: 4, textAlign: 'center' }}>
        <CircularProgress />
      </Container>
    );
  }

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
        <SettingsIcon color="primary" />
        <Typography variant="h5" fontWeight={600}>
          Настройки системы
        </Typography>
      </Box>

      {message && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      {/* Services Dashboard */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6" fontWeight={600}>Статус сервисов</Typography>
          <Chip
            label={`${settings?.services?.filter(s => s.status === 'ok').length || 0}/${settings?.services?.length || 0} работают`}
            color={settings?.services?.every(s => s.status === 'ok') ? 'success' : 'warning'}
            size="small"
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
      {settings?.db_stats && Object.keys(settings.db_stats).length > 0 && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>База данных</Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            {settings.db_stats.hs_codes != null && (
              <Chip label={`ТН ВЭД: ${settings.db_stats.hs_codes.toLocaleString()}`} size="small" variant="outlined" />
            )}
            {settings.db_stats.classifiers != null && (
              <Chip label={`Справочники: ${settings.db_stats.classifiers}`} size="small" variant="outlined" />
            )}
            {settings.db_stats.declarations != null && (
              <Chip label={`Декларации: ${settings.db_stats.declarations}`} size="small" variant="outlined" />
            )}
            {settings.db_stats.users != null && (
              <Chip label={`Пользователи: ${settings.db_stats.users}`} size="small" variant="outlined" />
            )}
            {settings.db_stats.counterparties != null && (
              <Chip label={`Контрагенты: ${settings.db_stats.counterparties}`} size="small" variant="outlined" />
            )}
          </Box>
        </Paper>
      )}

      {/* AI Status */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={4}>
          <Card variant="outlined">
            <CardContent sx={{ textAlign: 'center' }}>
              <AiIcon sx={{ fontSize: 40, color: settings?.openai_api_key_set ? 'success.main' : 'grey.400' }} />
              <Typography variant="subtitle2" sx={{ mt: 1 }}>OpenAI</Typography>
              <Chip size="small" icon={settings?.openai_api_key_set ? <CheckIcon /> : <ErrorIcon />}
                label={settings?.openai_api_key_set ? 'Подключён' : 'Не настроен'}
                color={settings?.openai_api_key_set ? 'success' : 'error'} sx={{ mt: 1 }} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card variant="outlined">
            <CardContent sx={{ textAlign: 'center' }}>
              <StorageIcon sx={{ fontSize: 40, color: settings?.rag_available ? 'success.main' : 'grey.400' }} />
              <Typography variant="subtitle2" sx={{ mt: 1 }}>RAG (ChromaDB)</Typography>
              <Chip size="small" icon={settings?.rag_available ? <CheckIcon /> : <ErrorIcon />}
                label={settings?.rag_available ? 'Активен' : settings?.chromadb_status || 'Не активен'}
                color={settings?.rag_available ? 'success' : 'warning'} sx={{ mt: 1 }} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card variant="outlined">
            <CardContent sx={{ textAlign: 'center' }}>
              <AiIcon sx={{ fontSize: 40, color: 'primary.main' }} />
              <Typography variant="subtitle2" sx={{ mt: 1 }}>Модель</Typography>
              <Chip size="small" label={settings?.openai_model || 'gpt-4o'} color="primary" sx={{ mt: 1 }} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* AI Status Message */}
      {settings?.ai_message && (
        <Alert
          severity={settings.ai_status === 'active' ? 'success' : settings.ai_status === 'no_key' ? 'warning' : settings.ai_status === 'no_balance' ? 'error' : 'info'}
          sx={{ mb: 3 }}
        >
          <Typography variant="body2" fontWeight={600}>{settings.ai_message}</Typography>
          {settings.ai_status === 'no_key' && (
            <Typography variant="caption">Без OpenAI ключа система использует regex-парсинг. Код ТН ВЭД подбирается по ключевым словам с точностью ~60%. С GPT-4o точность ~95%.</Typography>
          )}
        </Alert>
      )}

      {/* OpenAI API Key */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <AiIcon color="primary" fontSize="small" />
          OpenAI API Ключ
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Введите ваш OpenAI API ключ для активации AI функций: LLM парсинг документов (GPT-4o),
          RAG классификация ТН ВЭД, анализ рисков СУР. Ключ можно получить на{' '}
          <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer">
            platform.openai.com
          </a>.
        </Typography>

        {settings?.openai_api_key_set && (
          <Alert severity="success" sx={{ mb: 2 }}>
            API ключ установлен. Для замены введите новый ключ ниже.
          </Alert>
        )}

        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
          <TextField
            fullWidth
            label="OpenAI API Key"
            placeholder="sk-..."
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            type={showKey ? 'text' : 'password'}
            size="small"
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
          <Button
            variant="contained"
            startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveIcon />}
            onClick={handleSaveKey}
            disabled={saving || !apiKey.trim()}
            sx={{ minWidth: 140 }}
          >
            Сохранить
          </Button>
        </Box>
      </Paper>

      {/* Model Selection */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>Модель OpenAI</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            size="small"
            sx={{ minWidth: 200 }}
            SelectProps={{ native: true }}
          >
            <option value="gpt-4o">GPT-4o (рекомендуется)</option>
            <option value="gpt-4o-mini">GPT-4o Mini (дешевле)</option>
            <option value="gpt-4-turbo">GPT-4 Turbo</option>
            <option value="gpt-3.5-turbo">GPT-3.5 Turbo (быстрее)</option>
          </TextField>
          <Button variant="outlined" onClick={handleSaveModel}>
            Применить
          </Button>
        </Box>
      </Paper>

      {/* Info */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>Как работает система</Typography>
        <Typography variant="body2" color="text.secondary" component="div">
          <ol style={{ paddingLeft: 20 }}>
            <li><b>Без OpenAI ключа</b> — парсинг документов через regex (базовая точность ~60-70%)</li>
            <li><b>С OpenAI ключом</b> — парсинг через GPT-4o (точность ~95%), RAG классификация ТН ВЭД, AI анализ рисков</li>
            <li><b>ChromaDB (RAG)</b> — векторный поиск по 2500+ кодам ТН ВЭД, автоматически активируется при наличии OpenAI ключа</li>
            <li><b>Обучение</b> — каждая успешная декларация сохраняется как прецедент для будущих подсказок</li>
          </ol>
        </Typography>
      </Paper>
    </Container>
  );
};

export default SettingsPage;
