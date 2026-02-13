import { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import {
  Box, Button, TextField, Typography, Link, Snackbar, Alert,
  Tabs, Tab, IconButton, Tooltip, useTheme, alpha, Fade, Collapse,
} from '@mui/material';
import {
  DarkMode as DarkModeIcon,
  LightMode as LightModeIcon,
  Inventory2 as BoxIcon,
  Speed as SpeedIcon,
  Security as ShieldIcon,
  AutoAwesome as AiIcon,
  TrendingUp as GrowthIcon,
  Public as GlobalIcon,
} from '@mui/icons-material';
import { login } from '../api/auth';
import client from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { ThemeToggleContext } from '../index';

/* ───── Types ───── */
interface LoginForm { email: string; password: string; }
interface RegisterForm {
  email: string; password: string; password_confirm: string;
  full_name: string; phone: string; company_name: string;
}

/* ───── Feature cards ───── */
const FEATURES = [
  { icon: <AiIcon />,     title: 'AI-классификация', desc: 'Автоматический подбор кода ТН ВЭД по документам' },
  { icon: <SpeedIcon />,  title: 'Быстрое оформление', desc: 'Декларация за минуты вместо часов' },
  { icon: <ShieldIcon />, title: 'Контроль рисков', desc: 'Проверка требований, лицензий, сертификатов' },
  { icon: <GlobalIcon />, title: '18 000+ кодов ТН ВЭД', desc: 'Полный справочник ЕАЭС в одном месте' },
  { icon: <GrowthIcon />, title: 'Аналитика', desc: 'Dashboard с метриками по вашим операциям' },
  { icon: <BoxIcon />,    title: 'Умный парсинг', desc: 'Загрузите инвойс — система заполнит форму' },
];

/* ───── Component ───── */
const AuthPage = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const { reload } = useAuth();
  const themeCtx = useContext(ThemeToggleContext);

  const isDark = theme.palette.mode === 'dark';
  const [tab, setTab] = useState(0); // 0 = login, 1 = register
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Login form
  const loginForm = useForm<LoginForm>();
  // Register form
  const regForm = useForm<RegisterForm>();
  const regPassword = regForm.watch('password');

  const onLogin = async (data: LoginForm) => {
    try {
      setError(null);
      await login(data.email, data.password);
      reload();
      navigate('/dashboard');
    } catch (err: any) {
      setError(err instanceof Error ? err.message : 'Неверный email или пароль');
    }
  };

  const onRegister = async (data: RegisterForm) => {
    try {
      setError(null);
      const resp = await client.post('/auth/register-public', {
        email: data.email,
        password: data.password,
        full_name: data.full_name,
        phone: data.phone || null,
        company_name: data.company_name || null,
      });
      if (resp.data.access_token) {
        localStorage.setItem('token', resp.data.access_token);
        reload();
        navigate('/dashboard');
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Ошибка регистрации');
    }
  };

  /* ───── Styles ───── */
  const gradientBg = isDark
    ? 'linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)'
    : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';

  const cardBg = isDark ? alpha('#1e293b', 0.95) : alpha('#ffffff', 0.97);
  const inputSx = { mb: 1.5 };

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: { xs: 'column', md: 'row' } }}>

      {/* ───── LEFT PANEL (hero) ───── */}
      <Box sx={{
        flex: { md: '0 0 52%' },
        background: gradientBg,
        color: 'white',
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
        position: 'relative', overflow: 'hidden',
        px: { xs: 3, md: 8 }, py: { xs: 5, md: 8 },
        minHeight: { xs: 'auto', md: '100vh' },
      }}>
        {/* Decorative circles */}
        <Box sx={{
          position: 'absolute', width: 400, height: 400, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%)',
          top: -100, right: -100, pointerEvents: 'none',
        }} />
        <Box sx={{
          position: 'absolute', width: 300, height: 300, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%)',
          bottom: -80, left: -60, pointerEvents: 'none',
        }} />

        {/* Logo + name */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 5, position: 'relative', zIndex: 1 }}>
          <Box sx={{
            width: 56, height: 56, borderRadius: 3,
            background: 'rgba(255,255,255,0.2)', backdropFilter: 'blur(10px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            border: '1px solid rgba(255,255,255,0.25)',
          }}>
            <Typography sx={{ fontWeight: 800, fontSize: 22 }}>DB</Typography>
          </Box>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 800, letterSpacing: '-0.5px', lineHeight: 1.2 }}>
              Digital Broker
            </Typography>
            <Typography variant="body2" sx={{ opacity: 0.8, fontSize: 13 }}>
              Платформа таможенного оформления
            </Typography>
          </Box>
        </Box>

        {/* Headline */}
        <Typography variant="h3" sx={{
          fontWeight: 800, mb: 2, lineHeight: 1.15,
          fontSize: { xs: '2rem', md: '2.8rem' },
          position: 'relative', zIndex: 1,
        }}>
          Таможня без&nbsp;бумаг.
          <br />
          Декларации за&nbsp;минуты.
        </Typography>

        <Typography variant="body1" sx={{
          mb: 5, opacity: 0.85, maxWidth: 480, lineHeight: 1.7, fontSize: 16,
          position: 'relative', zIndex: 1,
        }}>
          AI‑система классифицирует товары, заполняет формы и контролирует риски.
          Загрузите документ — получите готовую декларацию.
        </Typography>

        {/* Feature grid */}
        <Box sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
          gap: 2, position: 'relative', zIndex: 1,
        }}>
          {FEATURES.map((f, i) => (
            <Fade in key={i} timeout={600 + i * 150}>
              <Box sx={{
                display: 'flex', gap: 1.5, alignItems: 'flex-start',
                p: 2, borderRadius: 2,
                background: 'rgba(255,255,255,0.08)',
                backdropFilter: 'blur(8px)',
                border: '1px solid rgba(255,255,255,0.1)',
                transition: 'background 0.3s',
                '&:hover': { background: 'rgba(255,255,255,0.14)' },
              }}>
                <Box sx={{ color: 'rgba(255,255,255,0.9)', mt: 0.3 }}>{f.icon}</Box>
                <Box>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.3 }}>{f.title}</Typography>
                  <Typography variant="caption" sx={{ opacity: 0.75, lineHeight: 1.4 }}>{f.desc}</Typography>
                </Box>
              </Box>
            </Fade>
          ))}
        </Box>

        {/* Stats strip */}
        <Box sx={{
          display: 'flex', gap: 4, mt: 5, pt: 3,
          borderTop: '1px solid rgba(255,255,255,0.15)',
          position: 'relative', zIndex: 1,
        }}>
          {[
            { n: '18 000+', l: 'Кодов ТН ВЭД' },
            { n: '6', l: 'Микросервисов' },
            { n: '< 2 мин', l: 'На декларацию' },
          ].map((s, i) => (
            <Box key={i}>
              <Typography sx={{ fontWeight: 800, fontSize: 20 }}>{s.n}</Typography>
              <Typography variant="caption" sx={{ opacity: 0.7 }}>{s.l}</Typography>
            </Box>
          ))}
        </Box>
      </Box>

      {/* ───── RIGHT PANEL (auth forms) ───── */}
      <Box sx={{
        flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
        bgcolor: isDark ? 'background.default' : '#f8fafc',
        px: { xs: 3, md: 6 }, py: 4,
        position: 'relative',
      }}>
        {/* Theme toggle */}
        <Box sx={{ position: 'absolute', top: 16, right: 16 }}>
          <Tooltip title={isDark ? 'Светлая тема' : 'Тёмная тема'}>
            <IconButton onClick={themeCtx.toggleTheme} size="small">
              {isDark ? <LightModeIcon /> : <DarkModeIcon />}
            </IconButton>
          </Tooltip>
        </Box>

        <Box sx={{
          width: '100%', maxWidth: 420,
          bgcolor: cardBg, borderRadius: 3, p: 4,
          boxShadow: isDark
            ? '0 8px 32px rgba(0,0,0,0.4)'
            : '0 8px 32px rgba(0,0,0,0.08)',
          border: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`,
        }}>
          {/* Tabs: Login / Register */}
          <Tabs
            value={tab}
            onChange={(_, v) => { setTab(v); setError(null); }}
            variant="fullWidth"
            sx={{
              mb: 3,
              '& .MuiTab-root': { fontWeight: 600, textTransform: 'none', fontSize: 15 },
              '& .MuiTabs-indicator': { height: 3, borderRadius: 2 },
            }}
          >
            <Tab label="Вход" />
            <Tab label="Регистрация" />
          </Tabs>

          {/* ── Login form ── */}
          <Collapse in={tab === 0} timeout={300}>
            {tab === 0 && (
              <form onSubmit={loginForm.handleSubmit(onLogin)}>
                <TextField
                  {...loginForm.register('email', {
                    required: 'Email обязателен',
                    pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: 'Неверный формат email' },
                  })}
                  label="Email"
                  type="email"
                  fullWidth
                  sx={inputSx}
                  error={!!loginForm.formState.errors.email}
                  helperText={loginForm.formState.errors.email?.message}
                  autoComplete="email"
                />
                <TextField
                  {...loginForm.register('password', {
                    required: 'Пароль обязателен',
                    minLength: { value: 6, message: 'Минимум 6 символов' },
                  })}
                  label="Пароль"
                  type="password"
                  fullWidth
                  sx={inputSx}
                  error={!!loginForm.formState.errors.password}
                  helperText={loginForm.formState.errors.password?.message}
                  autoComplete="current-password"
                />
                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  size="large"
                  disabled={loginForm.formState.isSubmitting}
                  sx={{ mt: 1, py: 1.5, fontSize: 16, fontWeight: 700, borderRadius: 2 }}
                >
                  {loginForm.formState.isSubmitting ? 'Вход...' : 'Войти'}
                </Button>
                <Typography variant="body2" sx={{ textAlign: 'center', mt: 2, color: 'text.secondary' }}>
                  Нет аккаунта?{' '}
                  <Link component="button" type="button" underline="hover" onClick={() => setTab(1)} sx={{ fontWeight: 600 }}>
                    Зарегистрируйтесь
                  </Link>
                </Typography>
              </form>
            )}
          </Collapse>

          {/* ── Register form ── */}
          <Collapse in={tab === 1} timeout={300}>
            {tab === 1 && (
              <form onSubmit={regForm.handleSubmit(onRegister)}>
                <TextField
                  {...regForm.register('full_name', { required: 'ФИО обязательно' })}
                  label="ФИО"
                  fullWidth
                  size="small"
                  sx={inputSx}
                  error={!!regForm.formState.errors.full_name}
                  helperText={regForm.formState.errors.full_name?.message}
                />
                <TextField
                  {...regForm.register('email', {
                    required: 'Email обязателен',
                    pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: 'Неверный формат email' },
                  })}
                  label="Email"
                  type="email"
                  fullWidth
                  size="small"
                  sx={inputSx}
                  error={!!regForm.formState.errors.email}
                  helperText={regForm.formState.errors.email?.message}
                />
                <TextField
                  {...regForm.register('phone')}
                  label="Телефон"
                  fullWidth
                  size="small"
                  sx={inputSx}
                  placeholder="+7 (999) 123-45-67"
                />
                <TextField
                  {...regForm.register('company_name')}
                  label="Компания (необязательно)"
                  fullWidth
                  size="small"
                  sx={inputSx}
                />
                <TextField
                  {...regForm.register('password', {
                    required: 'Пароль обязателен',
                    minLength: { value: 6, message: 'Минимум 6 символов' },
                  })}
                  label="Пароль"
                  type="password"
                  fullWidth
                  size="small"
                  sx={inputSx}
                  error={!!regForm.formState.errors.password}
                  helperText={regForm.formState.errors.password?.message}
                />
                <TextField
                  {...regForm.register('password_confirm', {
                    required: 'Подтвердите пароль',
                    validate: (v) => v === regPassword || 'Пароли не совпадают',
                  })}
                  label="Подтверждение пароля"
                  type="password"
                  fullWidth
                  size="small"
                  sx={inputSx}
                  error={!!regForm.formState.errors.password_confirm}
                  helperText={regForm.formState.errors.password_confirm?.message}
                />
                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  size="large"
                  disabled={regForm.formState.isSubmitting}
                  sx={{ mt: 1, py: 1.4, fontSize: 15, fontWeight: 700, borderRadius: 2 }}
                >
                  {regForm.formState.isSubmitting ? 'Регистрация...' : 'Создать аккаунт'}
                </Button>
                <Typography variant="body2" sx={{ textAlign: 'center', mt: 2, color: 'text.secondary' }}>
                  Уже есть аккаунт?{' '}
                  <Link component="button" type="button" underline="hover" onClick={() => setTab(0)} sx={{ fontWeight: 600 }}>
                    Войти
                  </Link>
                </Typography>
              </form>
            )}
          </Collapse>
        </Box>

        {/* Footer */}
        <Typography variant="caption" sx={{ mt: 3, color: 'text.disabled', textAlign: 'center' }}>
          Digital Broker v2.0 &mdash; AI‑платформа таможенного оформления
        </Typography>
      </Box>

      {/* Snackbar */}
      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setError(null)} variant="filled">{error}</Alert>
      </Snackbar>
      <Snackbar open={!!success} autoHideDuration={4000} onClose={() => setSuccess(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="success" onClose={() => setSuccess(null)} variant="filled">{success}</Alert>
      </Snackbar>
    </Box>
  );
};

export default AuthPage;
