import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import {
  Box, Button, Container, Typography, Grid, Stack, Divider,
  TextField, Popover, Alert, CircularProgress, Dialog, IconButton, useTheme, useMediaQuery, InputAdornment,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import SearchIcon from '@mui/icons-material/Search';
import CalculateOutlinedIcon from '@mui/icons-material/CalculateOutlined';
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined';
import ViewKanbanOutlinedIcon from '@mui/icons-material/ViewKanbanOutlined';
import FolderOpenOutlinedIcon from '@mui/icons-material/FolderOpenOutlined';
import BusinessIcon from '@mui/icons-material/Business';
import PublicIcon from '@mui/icons-material/Public';
import LocalShippingIcon from '@mui/icons-material/LocalShipping';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { styled, keyframes } from '@mui/material/styles';
import { login } from '../api/auth';
import client from '../api/client';
import { useAuth } from '../contexts/AuthContext';

const fadeIn = keyframes`
  from { opacity: 0; }
  to   { opacity: 1; }
`;
const float = keyframes`
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
`;

const C = {
  bgPage: '#f8fafc',
  bgWhite: '#ffffff',
  bgSoft: '#eef2ff',
  bgSoftAlt: '#f0fdf4',
  accent: '#2563eb',
  accentDark: '#1d4ed8',
  accent2: '#7c3aed',
  success: '#059669',
  warning: '#d97706',
  danger: '#dc2626',
  text: '#0f172a',
  textSecondary: '#64748b',
  textMuted: '#94a3b8',
  border: '#e2e8f0',
  borderLight: '#f1f5f9',
};

const Page = styled(Box)({
  background: C.bgPage,
  color: C.text,
  minHeight: '100vh',
  overflow: 'hidden',
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  '@media (prefers-reduced-motion: reduce)': {
    '&, & *': { animation: 'none !important' },
  },
});

const Section = styled(Box)({
  position: 'relative',
  padding: '80px 0',
});

const LandingCard = styled(Box)({
  background: C.bgWhite,
  border: `1px solid ${C.border}`,
  borderRadius: 16,
  padding: 32,
  transition: 'all 0.3s ease',
  '&:hover': {
    borderColor: '#cbd5e1',
    boxShadow: '0 4px 24px rgba(0,0,0,0.06)',
    transform: 'translateY(-2px)',
  },
});

const AccentBadge = styled(Box)({
  display: 'inline-block',
  padding: '6px 16px',
  borderRadius: 20,
  background: C.bgSoft,
  color: C.accent,
  fontWeight: 700,
  fontSize: 13,
  letterSpacing: 0.5,
  textTransform: 'uppercase',
  marginBottom: 16,
});

const CtaButton = styled(Button)({
  background: C.accent,
  color: '#fff',
  fontWeight: 700,
  fontSize: 17,
  padding: '14px 40px',
  borderRadius: 12,
  textTransform: 'none',
  boxShadow: '0 4px 16px rgba(37,99,235,0.25)',
  transition: 'all 0.3s ease',
  '&:hover': {
    background: C.accentDark,
    transform: 'translateY(-1px)',
    boxShadow: '0 6px 24px rgba(37,99,235,0.35)',
  },
});

const SecondaryBtn = styled(Button)({
  border: `1.5px solid ${C.accent}`,
  color: C.accent,
  fontWeight: 600,
  fontSize: 16,
  padding: '12px 32px',
  borderRadius: 12,
  textTransform: 'none',
  transition: 'all 0.3s ease',
  '&:hover': {
    background: C.bgSoft,
    borderColor: C.accent,
    transform: 'translateY(-1px)',
  },
});

function useReveal() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          el.style.opacity = '1';
          el.style.transform = 'translateY(0)';
          obs.unobserve(el);
        }
      },
      { threshold: 0.15 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return ref;
}

function Reveal({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const ref = useReveal();
  return (
    <Box
      ref={ref}
      sx={{
        opacity: 0,
        transform: 'translateY(30px)',
        transition: `all 0.7s cubic-bezier(0.16,1,0.3,1) ${delay}s`,
      }}
    >
      {children}
    </Box>
  );
}

function BrowserFrame({ src, alt }: { src: string; alt: string }) {
  return (
    <Box sx={{
      borderRadius: '12px',
      overflow: 'hidden',
      border: `1px solid ${C.border}`,
      boxShadow: '0 8px 40px rgba(0,0,0,0.08)',
    }}>
      <Box sx={{
        height: 32,
        background: '#f1f5f9',
        display: 'flex',
        alignItems: 'center',
        px: 1.5,
        gap: 0.75,
        borderBottom: `1px solid ${C.border}`,
      }}>
        {['#ef4444', '#f59e0b', '#22c55e'].map((color, i) => (
          <Box key={i} sx={{ width: 10, height: 10, borderRadius: '50%', background: color, opacity: 0.7 }} />
        ))}
        <Box sx={{ flex: 1, mx: 1.5, height: 18, borderRadius: 4, background: '#e2e8f0', fontSize: 10, color: C.textMuted, display: 'flex', alignItems: 'center', px: 1 }}>
          digitalbroker.ru
        </Box>
      </Box>
      <Box
        component="img"
        src={src}
        alt={alt}
        sx={{ width: '100%', display: 'block' }}
      />
    </Box>
  );
}

interface LoginForm { email: string; password: string; }
interface RegisterForm {
  full_name: string; email: string; password: string; company_name: string;
}

export default function LandingPage() {
  const navigate = useNavigate();
  const { reload } = useAuth();

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [loginAnchor, setLoginAnchor] = useState<HTMLElement | null>(null);
  const [regAnchor, setRegAnchor] = useState<HTMLElement | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [showLoginPwd, setShowLoginPwd] = useState(false);
  const [showRegPwd, setShowRegPwd] = useState(false);

  const loginForm = useForm<LoginForm>();
  const onLogin = async (data: LoginForm) => {
    try {
      setAuthError(null);
      await login(data.email, data.password);
      await reload();
      navigate('/dashboard');
    } catch (err: any) {
      setAuthError(err instanceof Error ? err.message : 'Неверный email или пароль');
    }
  };

  const regForm = useForm<RegisterForm>();
  const onRegister = async (data: RegisterForm) => {
    try {
      setAuthError(null);
      const resp = await client.post('/auth/register-public', {
        full_name: data.full_name, email: data.email, password: data.password,
        company_name: data.company_name,
      });
      if (resp.data.access_token) {
        localStorage.setItem('token', resp.data.access_token);
        reload();
        navigate('/dashboard');
      }
    } catch (err: any) {
      setAuthError(err?.response?.data?.detail || 'Ошибка регистрации');
    }
  };

  const popoverSx = {
    '& .MuiPaper-root': {
      background: C.bgWhite,
      border: `1px solid ${C.border}`,
      borderRadius: 3,
      p: 3,
      width: 360,
      boxShadow: '0 16px 48px rgba(0,0,0,0.12)',
    },
  };
  const fieldSx = {
    mb: 1.5,
    '& .MuiOutlinedInput-root': {
      borderRadius: 2,
      '& fieldset': { borderColor: C.border },
      '&:hover fieldset': { borderColor: C.accent },
      '&.Mui-focused fieldset': { borderColor: C.accent },
    },
  };

  const features = [
    {
      icon: <DescriptionOutlinedIcon sx={{ fontSize: 28, color: C.accent }} />,
      title: 'Автозаполнение из документов',
      desc: 'Графы декларации заполняются из загруженных документов. Все поля остаются редактируемыми',
      bg: C.bgSoft,
    },
    {
      icon: <SearchIcon sx={{ fontSize: 28, color: C.accent2 }} />,
      title: 'AI-подбор кодов ТН ВЭД',
      desc: 'Классификация товаров по описанию на базе 39 000+ кодов с вариантами и уровнем уверенности',
      bg: '#faf5ff',
    },
    {
      icon: <CalculateOutlinedIcon sx={{ fontSize: 28, color: C.success }} />,
      title: 'Авторасчёт платежей',
      desc: 'Пошлины, НДС, акцизы по актуальным ставкам. Курсы валют ЦБ обновляются автоматически',
      bg: C.bgSoftAlt,
    },
    {
      icon: <ShieldOutlinedIcon sx={{ fontSize: 28, color: C.warning }} />,
      title: 'Контроль рисков',
      desc: 'Проверка полноты и логики данных до подачи. Предупреждения и рекомендации по каждой графе',
      bg: '#fffbeb',
    },
    {
      icon: <ViewKanbanOutlinedIcon sx={{ fontSize: 28, color: '#0891b2' }} />,
      title: 'Управление декларациями',
      desc: 'Канбан-доска и список со статусами, фильтрами и поиском. Вся история изменений по каждой ДТ',
      bg: '#ecfeff',
    },
    {
      icon: <FolderOpenOutlinedIcon sx={{ fontSize: 28, color: '#e11d48' }} />,
      title: 'Работа с документами',
      desc: 'Хранение, предпросмотр и привязка документов к графам декларации. Источник каждого значения прозрачен',
      bg: '#fff1f2',
    },
  ];

  const steps = [
    { n: '1', title: 'Загрузите документы', desc: 'Инвойсы, контракты, упаковочные листы, спецификации, транспортные документы — в формате PDF', color: C.accent },
    { n: '2', title: 'AI извлекает данные', desc: 'Система автоматически распознаёт структуру документов и извлекает значения для заполнения декларации', color: C.accent2 },
    { n: '3', title: 'Подбор кодов ТН ВЭД', desc: 'AI подбирает коды товарной номенклатуры на основе описания товара и базы из 39 000+ кодов', color: C.success },
    { n: '4', title: 'Расчёт платежей', desc: 'Автоматический расчёт пошлин и НДС по актуальным ставкам и курсам валют ЦБ', color: C.warning },
    { n: '5', title: 'Проверка и отправка', desc: 'Контроль полноты и корректности данных, подсветка проблемных мест, формирование готовой ДТ', color: '#0891b2' },
  ];

  const audiences = [
    { icon: <BusinessIcon sx={{ fontSize: 36, color: C.accent }} />, title: 'Таможенные брокеры', lines: ['Обрабатывают больше деклараций с той же командой', 'Снижают себестоимость каждой ДТ'], color: C.accent },
    { icon: <PublicIcon sx={{ fontSize: 36, color: C.accent2 }} />, title: 'Импортёры и экспортёры', lines: ['Быстрее проходят таможню', 'Получают прогноз по платежам заранее'], color: C.accent2 },
    { icon: <LocalShippingIcon sx={{ fontSize: 36, color: C.success }} />, title: 'Логистические компании', lines: ['Автоматизируют оформление для клиентов', 'Делают сервис более технологичным'], color: C.success },
  ];

  const facts = [
    { value: 'Минуты', sub: 'вместо часов на декларацию', color: C.accent },
    { value: '39 000+', sub: 'кодов в базе ТН ВЭД', color: C.accent2 },
    { value: '6 типов', sub: 'документов распознаются', color: C.success },
    { value: 'ЦБ РФ', sub: 'актуальные ставки и курсы', color: C.warning },
  ];

  return (
    <Page>
      {/* NAV */}
      <Box sx={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(12px)',
        borderBottom: `1px solid ${C.border}`,
      }}>
        <Container maxWidth="lg" sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 60 }}>
          <Typography sx={{ fontWeight: 800, fontSize: 20, color: C.accent, letterSpacing: 0.5 }}>
            DIGITAL BROKER
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ minHeight: 44 }}>
            <Button
              onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}
              sx={{ color: C.textSecondary, textTransform: 'none', fontWeight: 600, fontSize: 15, '&:hover': { color: C.accent, background: C.bgSoft } }}
            >
              Возможности
            </Button>
            <Button
              onClick={() => document.getElementById('how')?.scrollIntoView({ behavior: 'smooth' })}
              sx={{ color: C.textSecondary, textTransform: 'none', fontWeight: 600, fontSize: 15, '&:hover': { color: C.accent, background: C.bgSoft } }}
            >
              Как работает
            </Button>
            <Button
              onClick={() => document.getElementById('contacts')?.scrollIntoView({ behavior: 'smooth' })}
              sx={{ color: C.textSecondary, textTransform: 'none', fontWeight: 600, fontSize: 15, '&:hover': { color: C.accent, background: C.bgSoft } }}
            >
              Контакты
            </Button>
            <Button
              data-login-btn
              onClick={(e) => { setLoginAnchor(e.currentTarget); setRegAnchor(null); setAuthError(null); }}
              sx={{ color: C.textSecondary, textTransform: 'none', fontWeight: 600, '&:hover': { color: C.accent } }}
            >
              Войти
            </Button>
            <Button
              data-reg-btn
              variant="contained"
              onClick={(e) => { setRegAnchor(e.currentTarget); setLoginAnchor(null); setAuthError(null); }}
              sx={{
                background: C.accent, color: '#fff', fontWeight: 700,
                textTransform: 'none', borderRadius: '10px', px: 3,
                '&:hover': { background: C.accentDark },
              }}
            >
              Регистрация
            </Button>
          </Stack>
        </Container>
      </Box>

      {/* Login popover / dialog */}
      {isMobile ? (
        <Dialog fullScreen open={!!loginAnchor} onClose={() => setLoginAnchor(null)} PaperProps={{ sx: { background: C.bgWhite } }}>
          <Box sx={{ p: 3, maxWidth: 400, mx: 'auto', mt: 4 }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
              <Typography sx={{ fontWeight: 700, fontSize: 18, color: C.text }}>Вход в систему</Typography>
              <IconButton onClick={() => setLoginAnchor(null)} sx={{ color: C.textMuted }}><CloseIcon /></IconButton>
            </Stack>
            {authError && <Alert severity="error" sx={{ mb: 1.5, fontSize: 13 }}>{authError}</Alert>}
            <form onSubmit={loginForm.handleSubmit(onLogin)}>
              <TextField
                {...loginForm.register('email', { required: 'Email обязателен' })}
                label="Email" type="email" fullWidth size="small" sx={fieldSx}
                error={!!loginForm.formState.errors.email}
                helperText={loginForm.formState.errors.email?.message}
                autoComplete="email"
              />
              <TextField
                {...loginForm.register('password', { required: 'Пароль обязателен' })}
                label="Пароль" type={showLoginPwd ? 'text' : 'password'} fullWidth size="small" sx={fieldSx}
                error={!!loginForm.formState.errors.password}
                helperText={loginForm.formState.errors.password?.message}
                autoComplete="current-password"
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton size="small" onClick={() => setShowLoginPwd((v) => !v)} sx={{ color: C.textMuted }} aria-label={showLoginPwd ? 'Скрыть пароль' : 'Показать пароль'}>
                        {showLoginPwd ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
              <Button type="submit" variant="contained" fullWidth disabled={loginForm.formState.isSubmitting}
                sx={{ mt: 1, py: 1.2, fontWeight: 700, textTransform: 'none', fontSize: 15, background: C.accent, borderRadius: 2, '&:hover': { background: C.accentDark } }}
              >
                {loginForm.formState.isSubmitting ? <CircularProgress size={22} sx={{ color: '#fff' }} /> : 'Войти'}
              </Button>
              <Typography sx={{ textAlign: 'center', mt: 1.5, fontSize: 13, color: C.textSecondary, cursor: 'pointer', '&:hover': { color: C.accent } }}
                onClick={() => { setLoginAnchor(null); setTimeout(() => setRegAnchor(document.querySelector('[data-reg-btn]') as HTMLElement), 100); }}
              >
                Нет аккаунта? Зарегистрируйтесь
              </Typography>
            </form>
          </Box>
        </Dialog>
      ) : (
        <Popover open={!!loginAnchor} anchorEl={loginAnchor} onClose={() => setLoginAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }} sx={popoverSx}
        >
          <Typography sx={{ fontWeight: 700, fontSize: 18, color: C.text, mb: 2 }}>Вход в систему</Typography>
          {authError && <Alert severity="error" sx={{ mb: 1.5, fontSize: 13 }}>{authError}</Alert>}
          <form onSubmit={loginForm.handleSubmit(onLogin)}>
            <TextField
              {...loginForm.register('email', { required: 'Email обязателен' })}
              label="Email" type="email" fullWidth size="small" sx={fieldSx}
              error={!!loginForm.formState.errors.email}
              helperText={loginForm.formState.errors.email?.message}
              autoComplete="email"
            />
            <TextField
              {...loginForm.register('password', { required: 'Пароль обязателен' })}
              label="Пароль" type={showLoginPwd ? 'text' : 'password'} fullWidth size="small" sx={fieldSx}
              error={!!loginForm.formState.errors.password}
              helperText={loginForm.formState.errors.password?.message}
              autoComplete="current-password"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setShowLoginPwd((v) => !v)} sx={{ color: C.textMuted }} aria-label={showLoginPwd ? 'Скрыть пароль' : 'Показать пароль'}>
                      {showLoginPwd ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <Button type="submit" variant="contained" fullWidth disabled={loginForm.formState.isSubmitting}
              sx={{ mt: 1, py: 1.2, fontWeight: 700, textTransform: 'none', fontSize: 15, background: C.accent, borderRadius: 2, '&:hover': { background: C.accentDark } }}
            >
              {loginForm.formState.isSubmitting ? <CircularProgress size={22} sx={{ color: '#fff' }} /> : 'Войти'}
            </Button>
            <Typography sx={{ textAlign: 'center', mt: 1.5, fontSize: 13, color: C.textSecondary, cursor: 'pointer', '&:hover': { color: C.accent } }}
              onClick={() => { setLoginAnchor(null); setTimeout(() => setRegAnchor(document.querySelector('[data-reg-btn]') as HTMLElement), 100); }}
            >
              Нет аккаунта? Зарегистрируйтесь
            </Typography>
          </form>
        </Popover>
      )}

      {/* Register popover / dialog */}
      {isMobile ? (
        <Dialog fullScreen open={!!regAnchor} onClose={() => setRegAnchor(null)} PaperProps={{ sx: { background: C.bgWhite } }}>
          <Box sx={{ p: 3, maxWidth: 400, mx: 'auto', mt: 4 }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
              <Typography sx={{ fontWeight: 700, fontSize: 18, color: C.text }}>Регистрация</Typography>
              <IconButton onClick={() => setRegAnchor(null)} sx={{ color: C.textMuted }}><CloseIcon /></IconButton>
            </Stack>
            {authError && <Alert severity="error" sx={{ mb: 1.5, fontSize: 13 }}>{authError}</Alert>}
            <form onSubmit={regForm.handleSubmit(onRegister)}>
              <TextField {...regForm.register('full_name', { required: 'Имя обязательно' })} label="Имя" fullWidth size="small" sx={fieldSx}
                error={!!regForm.formState.errors.full_name} helperText={regForm.formState.errors.full_name?.message} />
              <TextField {...regForm.register('company_name', { required: 'Название компании обязательно' })} label="Название компании" fullWidth size="small" sx={fieldSx}
                error={!!regForm.formState.errors.company_name} helperText={regForm.formState.errors.company_name?.message} />
              <TextField {...regForm.register('email', { required: 'Email обязателен', pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: 'Неверный формат' }})}
                label="Email" type="email" fullWidth size="small" sx={fieldSx}
                error={!!regForm.formState.errors.email} helperText={regForm.formState.errors.email?.message} />
              <TextField {...regForm.register('password', { required: 'Пароль обязателен', minLength: { value: 6, message: 'Минимум 6 символов' }})}
                label="Пароль" type={showRegPwd ? 'text' : 'password'} fullWidth size="small" sx={fieldSx}
                error={!!regForm.formState.errors.password} helperText={regForm.formState.errors.password?.message}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton size="small" onClick={() => setShowRegPwd((v) => !v)} sx={{ color: C.textMuted }} aria-label={showRegPwd ? 'Скрыть пароль' : 'Показать пароль'}>
                        {showRegPwd ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
              <Button type="submit" variant="contained" fullWidth disabled={regForm.formState.isSubmitting}
                sx={{ mt: 1, py: 1.2, fontWeight: 700, textTransform: 'none', fontSize: 15, background: C.accent, borderRadius: 2, '&:hover': { background: C.accentDark } }}
              >
                {regForm.formState.isSubmitting ? <CircularProgress size={22} sx={{ color: '#fff' }} /> : 'Создать аккаунт'}
              </Button>
              <Typography sx={{ textAlign: 'center', mt: 1.5, fontSize: 13, color: C.textSecondary, cursor: 'pointer', '&:hover': { color: C.accent } }}
                onClick={() => { setRegAnchor(null); }}>Уже есть аккаунт? Войти</Typography>
            </form>
          </Box>
        </Dialog>
      ) : (
        <Popover open={!!regAnchor} anchorEl={regAnchor} onClose={() => setRegAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }} sx={popoverSx}
        >
          <Typography sx={{ fontWeight: 700, fontSize: 18, color: C.text, mb: 2 }}>Регистрация</Typography>
          {authError && <Alert severity="error" sx={{ mb: 1.5, fontSize: 13 }}>{authError}</Alert>}
          <form onSubmit={regForm.handleSubmit(onRegister)}>
            <TextField {...regForm.register('full_name', { required: 'Имя обязательно' })} label="Имя" fullWidth size="small" sx={fieldSx}
              error={!!regForm.formState.errors.full_name} helperText={regForm.formState.errors.full_name?.message} />
            <TextField {...regForm.register('company_name', { required: 'Название компании обязательно' })} label="Название компании" fullWidth size="small" sx={fieldSx}
              error={!!regForm.formState.errors.company_name} helperText={regForm.formState.errors.company_name?.message} />
            <TextField {...regForm.register('email', { required: 'Email обязателен', pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: 'Неверный формат' }})}
              label="Email" type="email" fullWidth size="small" sx={fieldSx}
              error={!!regForm.formState.errors.email} helperText={regForm.formState.errors.email?.message} />
            <TextField {...regForm.register('password', { required: 'Пароль обязателен', minLength: { value: 6, message: 'Минимум 6 символов' }})}
              label="Пароль" type={showRegPwd ? 'text' : 'password'} fullWidth size="small" sx={fieldSx}
              error={!!regForm.formState.errors.password} helperText={regForm.formState.errors.password?.message}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setShowRegPwd((v) => !v)} sx={{ color: C.textMuted }} aria-label={showRegPwd ? 'Скрыть пароль' : 'Показать пароль'}>
                      {showRegPwd ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <Button type="submit" variant="contained" fullWidth disabled={regForm.formState.isSubmitting}
              sx={{ mt: 1, py: 1.2, fontWeight: 700, textTransform: 'none', fontSize: 15, background: C.accent, borderRadius: 2, '&:hover': { background: C.accentDark } }}
            >
              {regForm.formState.isSubmitting ? <CircularProgress size={22} sx={{ color: '#fff' }} /> : 'Создать аккаунт'}
            </Button>
            <Typography sx={{ textAlign: 'center', mt: 1.5, fontSize: 13, color: C.textSecondary, cursor: 'pointer', '&:hover': { color: C.accent } }}
              onClick={() => { setRegAnchor(null); }}>Уже есть аккаунт? Войти</Typography>
          </form>
        </Popover>
      )}

      {/* HERO */}
      <Section sx={{
        pt: '140px', pb: '80px',
        background: `radial-gradient(ellipse at 30% 0%, rgba(37,99,235,0.04), transparent 60%), ${C.bgPage}`,
      }}>
        <Container maxWidth="lg">
          <Grid container spacing={6} alignItems="center">
            <Grid item xs={12} md={6}>
              <AccentBadge>Автоматизация таможенного оформления</AccentBadge>
              <Typography variant="h1" sx={{ fontWeight: 900, fontSize: { xs: 32, md: 48 }, lineHeight: 1.15, mb: 2.5, color: C.text }}>
                Таможенные декларации заполняются автоматически
              </Typography>
              <Typography sx={{ fontSize: { xs: 17, md: 19 }, color: C.textSecondary, mb: 1.5, lineHeight: 1.6 }}>
                Загрузите документы — система извлечёт данные, заполнит графы декларации и предложит коды ТН ВЭД.
              </Typography>
              <Typography sx={{ fontSize: { xs: 15, md: 17 }, color: C.textSecondary, mb: 4, lineHeight: 1.6 }}>
                Все поля остаются редактируемыми.
              </Typography>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                <CtaButton onClick={() => { window.scrollTo({ top: 0, behavior: 'smooth' }); setTimeout(() => setRegAnchor(document.querySelector('[data-reg-btn]') as HTMLElement), 300); }}>
                  Попробовать бесплатно
                </CtaButton>
                <SecondaryBtn onClick={() => document.getElementById('how')?.scrollIntoView({ behavior: 'smooth' })}>
                  Как это работает
                </SecondaryBtn>
              </Stack>

              <Box sx={{ mt: 5, animation: `${fadeIn} 1.5s ease 0.5s both` }}>
                <Stack direction="row" alignItems="center" spacing={2}>
                  {[
                    { label: 'PDF', color: C.textSecondary, bg: C.borderLight },
                    null,
                    { label: 'AI', color: C.accent, bg: C.bgSoft },
                    null,
                    { label: 'ДТ', color: C.success, bg: C.bgSoftAlt },
                  ].map((item, i) =>
                    item ? (
                      <Box key={i} sx={{
                        width: 72, height: 48, borderRadius: '10px',
                        background: item.bg, border: `1px solid ${C.border}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontWeight: 800, fontSize: 16, color: item.color,
                        animation: `${float} 3s ease-in-out infinite`,
                        animationDelay: `${i * 0.3}s`,
                      }}>
                        {item.label}
                      </Box>
                    ) : (
                      <ArrowForwardIcon key={i} sx={{ color: C.textMuted, fontSize: 20 }} />
                    )
                  )}
                </Stack>
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box sx={{ transform: { md: 'perspective(1200px) rotateY(-3deg)' }, transition: 'transform 0.5s ease' }}>
                <BrowserFrame src="/screenshots/declarations.png" alt="Список деклараций" />
              </Box>
            </Grid>
          </Grid>
        </Container>
      </Section>

      {/* PROBLEM */}
      <Section sx={{ background: C.bgWhite }}>
        <Container maxWidth="lg">
          <Reveal>
            <Grid container spacing={6} alignItems="center">
              <Grid item xs={12} md={7}>
                <Typography sx={{ fontWeight: 800, fontSize: { xs: 26, md: 34 }, mb: 1, color: C.text }}>
                  Таможенное оформление сегодня —
                </Typography>
                <Typography sx={{ fontWeight: 800, fontSize: { xs: 26, md: 34 }, color: C.danger, mb: 3 }}>
                  медленно и дорого
                </Typography>
                <Box sx={{ borderLeft: `3px solid ${C.danger}`, pl: 3 }}>
                  {[
                    'На одну декларацию уходит от 2 до 4 часов',
                    'Сотни полей заполняются вручную',
                    'Ошибки в кодах ТН ВЭД приводят к штрафам и простоям',
                    'Справочники сложные и часто обновляются',
                  ].map((t, i) => (
                    <Stack key={i} direction="row" spacing={2} alignItems="flex-start" sx={{ mb: 2 }}>
                      <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: C.danger, mt: '8px', flexShrink: 0 }} />
                      <Typography sx={{ fontSize: 16, color: C.text }}>{t}</Typography>
                    </Stack>
                  ))}
                </Box>
              </Grid>
              <Grid item xs={12} md={5}>
                <LandingCard sx={{ textAlign: 'center', py: 5 }}>
                  <Typography sx={{ fontSize: 48, mb: 1 }}>⏱</Typography>
                  <Typography sx={{ fontSize: 44, fontWeight: 900, color: C.danger }}>2–4 ч</Typography>
                  <Typography sx={{ color: C.textSecondary, fontSize: 15, mt: 1 }}>на одну декларацию</Typography>
                  <Divider sx={{ my: 3, borderColor: C.borderLight }} />
                  <Typography sx={{ fontSize: 44, fontWeight: 900, color: C.warning }}>50+</Typography>
                  <Typography sx={{ color: C.textSecondary, fontSize: 15, mt: 1 }}>полей для заполнения</Typography>
                </LandingCard>
              </Grid>
            </Grid>
          </Reveal>
        </Container>
      </Section>

      {/* HOW IT WORKS */}
      <Section id="how" sx={{ background: C.bgPage }}>
        <Container maxWidth="lg">
          <Reveal>
            <Box sx={{ textAlign: 'center', mb: 7 }}>
              <AccentBadge>Процесс</AccentBadge>
              <Typography sx={{ fontWeight: 800, fontSize: { xs: 26, md: 34 }, color: C.text }}>
                Как это работает
              </Typography>
            </Box>
          </Reveal>
          <Box sx={{ maxWidth: 700, mx: 'auto' }}>
            {steps.map((s, i) => (
              <Reveal key={i} delay={i * 0.08}>
                <Stack direction="row" spacing={3} sx={{ mb: i < steps.length - 1 ? 0 : 0 }}>
                  <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <Box sx={{
                      width: 44, height: 44, borderRadius: '50%',
                      background: s.color, color: '#fff',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 800, fontSize: 18, flexShrink: 0,
                      boxShadow: `0 4px 12px ${s.color}33`,
                    }}>
                      {s.n}
                    </Box>
                    {i < steps.length - 1 && (
                      <Box sx={{ width: 2, flexGrow: 1, minHeight: 40, background: C.border, borderRadius: 1 }} />
                    )}
                  </Box>
                  <Box sx={{ pb: 4 }}>
                    <Typography sx={{ fontWeight: 700, fontSize: 18, mb: 0.5, color: C.text }}>{s.title}</Typography>
                    <Typography sx={{ fontSize: 15, color: C.textSecondary, lineHeight: 1.6 }}>{s.desc}</Typography>
                  </Box>
                </Stack>
              </Reveal>
            ))}
          </Box>
        </Container>
      </Section>

      {/* FEATURES */}
      <Section id="features" sx={{ background: C.bgWhite }}>
        <Container maxWidth="lg">
          <Reveal>
            <Box sx={{ textAlign: 'center', mb: 7 }}>
              <AccentBadge>Возможности</AccentBadge>
              <Typography sx={{ fontWeight: 800, fontSize: { xs: 26, md: 34 }, color: C.text }}>
                Полный набор инструментов для оформления
              </Typography>
            </Box>
          </Reveal>
          <Grid container spacing={3}>
            {features.map((f, i) => (
              <Grid item xs={12} sm={6} md={4} key={i}>
                <Reveal delay={i * 0.06}>
                  <LandingCard sx={{ height: '100%' }}>
                    <Box sx={{
                      width: 52, height: 52, borderRadius: '14px', background: f.bg,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 2,
                    }}>
                      {f.icon}
                    </Box>
                    <Typography sx={{ fontWeight: 700, fontSize: 17, mb: 1, color: C.text }}>{f.title}</Typography>
                    <Typography sx={{ fontSize: 14, color: C.textSecondary, lineHeight: 1.6 }}>{f.desc}</Typography>
                  </LandingCard>
                </Reveal>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Section>

      {/* PRODUCT SHOWCASE */}
      <Section sx={{ background: C.bgPage }}>
        <Container maxWidth="lg">
          <Reveal>
            <Box sx={{ textAlign: 'center', mb: 7 }}>
              <AccentBadge>Продукт</AccentBadge>
              <Typography sx={{ fontWeight: 800, fontSize: { xs: 26, md: 34 }, color: C.text }}>
                Как выглядит система
              </Typography>
            </Box>
          </Reveal>
          <Grid container spacing={4}>
            <Grid item xs={12} md={6}>
              <Reveal delay={0}>
                <Box>
                  <BrowserFrame src="/screenshots/dashboard.png" alt="Дашборд брокера" />
                  <Typography sx={{ textAlign: 'center', mt: 2, fontSize: 14, color: C.textSecondary, fontWeight: 600 }}>
                    Дашборд — обзор активности по клиентам и декларациям
                  </Typography>
                </Box>
              </Reveal>
            </Grid>
            <Grid item xs={12} md={6}>
              <Reveal delay={0.1}>
                <Box>
                  <BrowserFrame src="/screenshots/form.png" alt="Форма редактирования декларации" />
                  <Typography sx={{ textAlign: 'center', mt: 2, fontSize: 14, color: C.textSecondary, fontWeight: 600 }}>
                    Редактирование — форма декларации с автозаполнением
                  </Typography>
                </Box>
              </Reveal>
            </Grid>
          </Grid>
        </Container>
      </Section>

      {/* AUDIENCE */}
      <Section sx={{ background: C.bgWhite }}>
        <Container maxWidth="lg">
          <Reveal>
            <Box sx={{ textAlign: 'center', mb: 7 }}>
              <Typography sx={{ fontWeight: 800, fontSize: { xs: 26, md: 34 }, color: C.text }}>
                Кому подходит Digital Broker
              </Typography>
            </Box>
          </Reveal>
          <Grid container spacing={3}>
            {audiences.map((a, i) => (
              <Grid item xs={12} md={4} key={i}>
                <Reveal delay={i * 0.1}>
                  <LandingCard sx={{ height: '100%', textAlign: 'center' }}>
                    <Box sx={{
                      width: 64, height: 64, borderRadius: '50%', background: `${a.color}10`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      mx: 'auto', mb: 2,
                    }}>
                      {a.icon}
                    </Box>
                    <Typography sx={{ fontWeight: 700, fontSize: 18, color: C.text, mb: 2 }}>{a.title}</Typography>
                    <Divider sx={{ borderColor: C.borderLight, mb: 2 }} />
                    {a.lines.map((l, j) => (
                      <Typography key={j} sx={{ color: C.textSecondary, fontSize: 15, mb: 1, lineHeight: 1.5 }}>{l}</Typography>
                    ))}
                  </LandingCard>
                </Reveal>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Section>

      {/* FACTS */}
      <Section sx={{ background: C.bgPage }}>
        <Container maxWidth="md">
          <Reveal>
            <Box sx={{ textAlign: 'center', mb: 6 }}>
              <AccentBadge>Факты</AccentBadge>
              <Typography sx={{ fontWeight: 800, fontSize: { xs: 26, md: 34 }, color: C.text }}>Что даёт система</Typography>
            </Box>
          </Reveal>
          <Grid container spacing={3}>
            {facts.map((f, i) => (
              <Grid item xs={6} md={3} key={i}>
                <Reveal delay={i * 0.08}>
                  <LandingCard sx={{ textAlign: 'center', py: 3 }}>
                    <Typography sx={{ fontSize: 32, fontWeight: 900, color: f.color, mb: 0.5 }}>{f.value}</Typography>
                    <Typography sx={{ fontSize: 13, color: C.textSecondary }}>{f.sub}</Typography>
                  </LandingCard>
                </Reveal>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Section>

      {/* CTA */}
      <Section sx={{ py: 10, background: C.bgSoft }}>
        <Container maxWidth="md" sx={{ textAlign: 'center' }}>
          <Reveal>
            <Typography sx={{ fontWeight: 800, fontSize: { xs: 26, md: 34 }, mb: 2, color: C.text }}>
              Начните оформлять декларации быстрее
            </Typography>
            <Typography sx={{ fontSize: 17, color: C.textSecondary, mb: 4, maxWidth: 520, mx: 'auto' }}>
              Зарегистрируйтесь и загрузите документы — система покажет результат за несколько минут
            </Typography>
            <CtaButton onClick={() => { window.scrollTo({ top: 0, behavior: 'smooth' }); setTimeout(() => setRegAnchor(document.querySelector('[data-reg-btn]') as HTMLElement), 400); }} sx={{ fontSize: 18, px: 5, py: 1.8 }}>
              Создать аккаунт
            </CtaButton>
          </Reveal>
        </Container>
      </Section>

      {/* CONTACTS + FOOTER */}
      <Box id="contacts" sx={{ background: '#0f172a', color: '#fff', py: 7 }}>
        <Container maxWidth="md">
          <Box sx={{ textAlign: 'center', mb: 5 }}>
            <Typography sx={{ fontWeight: 800, fontSize: 26, color: '#fff' }}>Связаться с нами</Typography>
          </Box>
          <Grid container spacing={2} justifyContent="center">
            {[
              { label: 'Сайт', value: 'digitalbroker.ru' },
              { label: 'Email', value: 'info@digitalbroker.ru' },
              { label: 'Telegram', value: '@digital_broker' },
              { label: 'Обратная связь', value: 'Запросить обратный звонок' },
            ].map((c, i) => (
              <Grid item xs={12} sm={6} key={i}>
                <Box sx={{ py: 2, px: 3, borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)' }}>
                  <Typography sx={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', mb: 0.5, textTransform: 'uppercase', letterSpacing: 1 }}>
                    {c.label}
                  </Typography>
                  <Typography sx={{ fontWeight: 600, color: '#93c5fd' }}>{c.value}</Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
          <Typography sx={{ textAlign: 'center', color: 'rgba(255,255,255,0.4)', mt: 5, fontSize: 13 }}>
            Напишите нам, чтобы получить демо-доступ и рассчитать эффект для вашего бизнеса
          </Typography>
          <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)', my: 4 }} />
          <Typography sx={{ textAlign: 'center', fontWeight: 700, fontSize: 13, color: 'rgba(255,255,255,0.35)' }}>
            DIGITAL BROKER &copy; {new Date().getFullYear()}
          </Typography>
        </Container>
      </Box>
    </Page>
  );
}
