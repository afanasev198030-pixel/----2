import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import {
  Box, Button, Container, Typography, Grid, Stack, Divider,
  TextField, Popover, Alert, CircularProgress, ClickAwayListener, Dialog, IconButton, useTheme, useMediaQuery, InputAdornment,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import { styled, keyframes } from '@mui/material/styles';
import { login } from '../api/auth';
import client from '../api/client';
import { useAuth } from '../contexts/AuthContext';

// ── Animations ───────────────────────────────────────────────────────
const fadeInUp = keyframes`
  from { opacity: 0; transform: translateY(40px); }
  to   { opacity: 1; transform: translateY(0); }
`;
const fadeIn = keyframes`
  from { opacity: 0; }
  to   { opacity: 1; }
`;
const pulse = keyframes`
  0%, 100% { transform: scale(1); opacity: 0.6; }
  50% { transform: scale(1.05); opacity: 0.9; }
`;
const float = keyframes`
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-12px); }
`;
const shimmer = keyframes`
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
`;

// ── Colors ───────────────────────────────────────────────────────────
const C = {
  bgDark: '#0B1120',
  bgCard: '#131C2E',
  bgCardHover: '#1A2740',
  accent: '#00D4FF',
  accent2: '#7B61FF',
  accent3: '#00E676',
  orange: '#FF6B35',
  yellow: '#FFD600',
  red: '#FF5252',
  textWhite: '#F0F4F8',
  textGray: '#94A3B8',
  border: 'rgba(0,212,255,0.12)',
};

// ── Styled ───────────────────────────────────────────────────────────
const Page = styled(Box)({
  background: C.bgDark,
  color: C.textWhite,
  minHeight: '100vh',
  overflow: 'hidden',
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  '@media (prefers-reduced-motion: reduce)': {
    '&, & *': { animation: 'none !important' },
  },
});

const GlowOrb = styled(Box)<{ color: string; size: number; top: string; left: string; delay?: number }>(
  ({ color, size, top, left, delay = 0 }) => ({
    position: 'absolute',
    width: size,
    height: size,
    borderRadius: '50%',
    background: `radial-gradient(circle, ${color}22 0%, transparent 70%)`,
    top,
    left,
    animation: `${pulse} ${6 + delay}s ease-in-out infinite`,
    animationDelay: `${delay}s`,
    pointerEvents: 'none',
    zIndex: 0,
  })
);

const Section = styled(Box)({
  position: 'relative',
  padding: '100px 0',
  '&:nth-of-type(even)': {
    background: 'linear-gradient(180deg, rgba(19,28,46,0.5) 0%, rgba(11,17,32,1) 100%)',
  },
});

const GlassCard = styled(Box)({
  background: 'rgba(19,28,46,0.7)',
  backdropFilter: 'blur(20px)',
  border: `1px solid ${C.border}`,
  borderRadius: 16,
  padding: 32,
  transition: 'all 0.3s ease',
  '&:hover': {
    borderColor: 'rgba(0,212,255,0.3)',
    transform: 'translateY(-4px)',
    boxShadow: `0 20px 60px rgba(0,212,255,0.08)`,
  },
});

const AccentBadge = styled(Box)<{ bg?: string }>(({ bg = C.accent }) => ({
  display: 'inline-block',
  padding: '6px 18px',
  borderRadius: 20,
  background: bg,
  color: C.bgDark,
  fontWeight: 700,
  fontSize: 13,
  letterSpacing: 1,
  textTransform: 'uppercase',
  marginBottom: 16,
}));

const FlowStep = styled(Box)<{ accentColor: string }>(({ accentColor }) => ({
  position: 'relative',
  textAlign: 'center',
  padding: 24,
  '& .step-num': {
    width: 56,
    height: 56,
    borderRadius: '50%',
    background: accentColor,
    color: C.bgDark,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 800,
    fontSize: 22,
    margin: '0 auto 16px',
    boxShadow: `0 0 30px ${accentColor}44`,
  },
}));

const CtaButton = styled(Button)({
  background: `linear-gradient(135deg, ${C.accent} 0%, ${C.accent2} 100%)`,
  color: '#fff',
  fontWeight: 700,
  fontSize: 18,
  padding: '16px 48px',
  borderRadius: 12,
  textTransform: 'none',
  boxShadow: `0 8px 32px ${C.accent}44`,
  transition: 'all 0.3s ease',
  '&:hover': {
    transform: 'translateY(-2px) scale(1.02)',
    boxShadow: `0 12px 40px ${C.accent}66`,
  },
});

const SecondaryBtn = styled(Button)({
  border: `2px solid ${C.accent}`,
  color: C.accent,
  fontWeight: 600,
  fontSize: 16,
  padding: '14px 40px',
  borderRadius: 12,
  textTransform: 'none',
  transition: 'all 0.3s ease',
  '&:hover': {
    background: `${C.accent}11`,
    borderColor: C.accent,
    transform: 'translateY(-2px)',
  },
});

const MetricBar = styled(Box)<{ pct: number; barColor: string }>(({ pct, barColor }) => ({
  height: 8,
  borderRadius: 4,
  background: 'rgba(255,255,255,0.06)',
  position: 'relative',
  overflow: 'hidden',
  '&::after': {
    content: '""',
    position: 'absolute',
    left: 0,
    top: 0,
    height: '100%',
    width: `${pct}%`,
    borderRadius: 4,
    background: `linear-gradient(90deg, ${barColor}, ${barColor}cc)`,
    transition: 'width 1.5s ease',
  },
}));

// ── Intersection Observer hook ──────────────────────────────────────
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
        transform: 'translateY(40px)',
        transition: `all 0.8s cubic-bezier(0.16,1,0.3,1) ${delay}s`,
      }}
    >
      {children}
    </Box>
  );
}

// ── Login/Register forms ─────────────────────────────────────────
interface LoginForm { email: string; password: string; }
interface RegisterForm {
  full_name: string; email: string; password: string;
}

// ── Page Component ──────────────────────────────────────────────────
export default function LandingPage() {
  const navigate = useNavigate();
  const { reload } = useAuth();

  // Popover anchors
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [loginAnchor, setLoginAnchor] = useState<HTMLElement | null>(null);
  const [regAnchor, setRegAnchor] = useState<HTMLElement | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [showLoginPwd, setShowLoginPwd] = useState(false);
  const [showRegPwd, setShowRegPwd] = useState(false);

  // Login form
  const loginForm = useForm<LoginForm>();
  const onLogin = async (data: LoginForm) => {
    try {
      setAuthError(null);
      await login(data.email, data.password);
      reload();
      navigate('/dashboard');
    } catch (err: any) {
      setAuthError(err instanceof Error ? err.message : 'Неверный email или пароль');
    }
  };

  // Register form
  const regForm = useForm<RegisterForm>();
  const onRegister = async (data: RegisterForm) => {
    try {
      setAuthError(null);
      const resp = await client.post('/auth/register-public', {
        full_name: data.full_name, email: data.email, password: data.password,
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
      background: 'rgba(19,28,46,0.97)', backdropFilter: 'blur(20px)',
      border: `1px solid ${C.border}`, borderRadius: 3, p: 3, width: 340,
      boxShadow: '0 16px 48px rgba(0,0,0,0.5)',
    },
  };
  const fieldSx = {
    mb: 1.5,
    '& .MuiOutlinedInput-root': {
      color: C.textWhite, background: 'rgba(255,255,255,0.04)', borderRadius: 2,
      '& fieldset': { borderColor: 'rgba(255,255,255,0.25)' },
      '&:hover fieldset': { borderColor: C.accent },
      '&.Mui-focused fieldset': { borderColor: C.accent },
    },
    '& .MuiInputLabel-root': { color: '#B0BEC5' },
    '& .MuiInputLabel-root.Mui-focused': { color: C.accent },
  };

  return (
    <Page>
      {/* ═══ NAV ═══ */}
      <Box
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 100,
          background: 'rgba(11,17,32,0.85)',
          backdropFilter: 'blur(16px)',
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        <Container maxWidth="lg" sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 64 }}>
          <Typography
            sx={{
              fontWeight: 800,
              fontSize: 20,
              background: `linear-gradient(135deg, ${C.accent}, ${C.accent2})`,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              letterSpacing: 1,
            }}
          >
            DIGITAL BROKER
          </Typography>
          <Stack direction="row" spacing={1.5} alignItems="center" sx={{ minHeight: 44 }}>
            <Button
              onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}
              sx={{ color: C.textGray, textTransform: 'none', fontWeight: 600, fontSize: 15, py: 1.25, '&:hover': { color: C.accent } }}
            >
              Возможности
            </Button>
            <Button
              onClick={() => document.getElementById('how')?.scrollIntoView({ behavior: 'smooth' })}
              sx={{ color: C.textGray, textTransform: 'none', fontWeight: 600, fontSize: 15, py: 1.25, '&:hover': { color: C.accent } }}
            >
              Как работает
            </Button>
            <Button
              onClick={() => document.getElementById('contacts')?.scrollIntoView({ behavior: 'smooth' })}
              sx={{ color: C.textGray, textTransform: 'none', fontWeight: 600, fontSize: 15, py: 1.25, '&:hover': { color: C.accent } }}
            >
              Контакты
            </Button>
            <Button
              data-login-btn
              onClick={(e) => { setLoginAnchor(e.currentTarget); setRegAnchor(null); setAuthError(null); }}
              sx={{ color: C.textGray, textTransform: 'none', fontWeight: 600, '&:hover': { color: C.accent } }}
            >
              Войти
            </Button>
            <Button
              data-reg-btn
              variant="contained"
              onClick={(e) => { setRegAnchor(e.currentTarget); setLoginAnchor(null); setAuthError(null); }}
              sx={{
                background: C.accent, color: C.bgDark, fontWeight: 700,
                textTransform: 'none', borderRadius: 2, px: 3,
                '&:hover': { background: '#33DDFF' },
              }}
            >
              Регистрация
            </Button>
          </Stack>
        </Container>
      </Box>

      {/* ── Login (Dialog on mobile, Popover on desktop) ── */}
      {isMobile ? (
        <Dialog fullScreen open={!!loginAnchor} onClose={() => setLoginAnchor(null)} PaperProps={{ sx: { background: C.bgCard, color: C.textWhite } }}>
          <Box sx={{ p: 2, ...popoverSx, maxWidth: 400, mx: 'auto', mt: 4 }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
              <Typography sx={{ fontWeight: 700, fontSize: 18 }}>Вход в систему</Typography>
              <IconButton onClick={() => setLoginAnchor(null)} sx={{ color: C.textGray }}><CloseIcon /></IconButton>
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
                      <IconButton size="small" onClick={() => setShowLoginPwd((v) => !v)} sx={{ color: C.textGray }} aria-label={showLoginPwd ? 'Скрыть пароль' : 'Показать пароль'}>
                        {showLoginPwd ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
              <Typography component="a" href="/forgot-password" sx={{ fontSize: 12, color: C.accent, display: 'block', mb: 0.5, '&:hover': { textDecoration: 'underline' } }}>Забыли пароль?</Typography>
              <Button type="submit" variant="contained" fullWidth disabled={loginForm.formState.isSubmitting}
                sx={{ mt: 0.5, py: 1.2, fontWeight: 700, textTransform: 'none', fontSize: 15, background: `linear-gradient(135deg, ${C.accent}, ${C.accent2})`, borderRadius: 2, '&:hover': { boxShadow: `0 4px 20px ${C.accent}55` } }}
              >
                {loginForm.formState.isSubmitting ? <CircularProgress size={22} sx={{ color: '#fff' }} /> : 'Войти'}
              </Button>
              <Typography sx={{ textAlign: 'center', mt: 1.5, fontSize: 13, color: C.textGray, cursor: 'pointer', '&:hover': { color: C.accent } }}
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
          <Typography sx={{ fontWeight: 700, fontSize: 18, color: C.textWhite, mb: 2 }}>Вход в систему</Typography>
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
                    <IconButton size="small" onClick={() => setShowLoginPwd((v) => !v)} sx={{ color: C.textGray }} aria-label={showLoginPwd ? 'Скрыть пароль' : 'Показать пароль'}>
                      {showLoginPwd ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <Typography component="a" href="/forgot-password" sx={{ fontSize: 12, color: C.accent, display: 'block', mb: 0.5, '&:hover': { textDecoration: 'underline' } }}>Забыли пароль?</Typography>
            <Button type="submit" variant="contained" fullWidth disabled={loginForm.formState.isSubmitting}
              sx={{ mt: 0.5, py: 1.2, fontWeight: 700, textTransform: 'none', fontSize: 15, background: `linear-gradient(135deg, ${C.accent}, ${C.accent2})`, borderRadius: 2, '&:hover': { boxShadow: `0 4px 20px ${C.accent}55` } }}
            >
              {loginForm.formState.isSubmitting ? <CircularProgress size={22} sx={{ color: '#fff' }} /> : 'Войти'}
            </Button>
            <Typography sx={{ textAlign: 'center', mt: 1.5, fontSize: 13, color: C.textGray, cursor: 'pointer', '&:hover': { color: C.accent } }}
              onClick={() => { setLoginAnchor(null); setTimeout(() => setRegAnchor(document.querySelector('[data-reg-btn]') as HTMLElement), 100); }}
            >
              Нет аккаунта? Зарегистрируйтесь
            </Typography>
          </form>
        </Popover>
      )}

      {/* ── Register (Dialog on mobile, Popover on desktop) ── */}
      {isMobile ? (
        <Dialog fullScreen open={!!regAnchor} onClose={() => setRegAnchor(null)} PaperProps={{ sx: { background: C.bgCard, color: C.textWhite } }}>
          <Box sx={{ p: 2, ...popoverSx, maxWidth: 400, mx: 'auto', mt: 4 }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
              <Typography sx={{ fontWeight: 700, fontSize: 18 }}>Регистрация</Typography>
              <IconButton onClick={() => setRegAnchor(null)} sx={{ color: C.textGray }}><CloseIcon /></IconButton>
            </Stack>
            {authError && <Alert severity="error" sx={{ mb: 1.5, fontSize: 13 }}>{authError}</Alert>}
            <form onSubmit={regForm.handleSubmit(onRegister)}>
              <TextField {...regForm.register('full_name', { required: 'Имя обязательно' })} label="Имя" fullWidth size="small" sx={fieldSx}
                error={!!regForm.formState.errors.full_name} helperText={regForm.formState.errors.full_name?.message} />
              <TextField {...regForm.register('email', { required: 'Email обязателен', pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: 'Неверный формат' }})}
                label="Email" type="email" fullWidth size="small" sx={fieldSx}
                error={!!regForm.formState.errors.email} helperText={regForm.formState.errors.email?.message} />
              <TextField {...regForm.register('password', { required: 'Пароль обязателен', minLength: { value: 6, message: 'Минимум 6 символов' }})}
                label="Пароль" type={showRegPwd ? 'text' : 'password'} fullWidth size="small" sx={fieldSx}
                error={!!regForm.formState.errors.password} helperText={regForm.formState.errors.password?.message}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton size="small" onClick={() => setShowRegPwd((v) => !v)} sx={{ color: C.textGray }} aria-label={showRegPwd ? 'Скрыть пароль' : 'Показать пароль'}>
                        {showRegPwd ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
              <Button type="submit" variant="contained" fullWidth disabled={regForm.formState.isSubmitting}
                sx={{ mt: 0.5, py: 1.2, fontWeight: 700, textTransform: 'none', fontSize: 15, background: `linear-gradient(135deg, ${C.accent}, ${C.accent2})`, borderRadius: 2 }}
              >
                {regForm.formState.isSubmitting ? <CircularProgress size={22} sx={{ color: '#fff' }} /> : 'Создать аккаунт'}
              </Button>
              <Typography sx={{ textAlign: 'center', mt: 1.5, fontSize: 13, color: C.textGray, cursor: 'pointer', '&:hover': { color: C.accent } }}
                onClick={() => { setRegAnchor(null); }}>Уже есть аккаунт? Войти</Typography>
            </form>
          </Box>
        </Dialog>
      ) : (
        <Popover open={!!regAnchor} anchorEl={regAnchor} onClose={() => setRegAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }} sx={popoverSx}
        >
          <Typography sx={{ fontWeight: 700, fontSize: 18, color: C.textWhite, mb: 2 }}>Регистрация</Typography>
          {authError && <Alert severity="error" sx={{ mb: 1.5, fontSize: 13 }}>{authError}</Alert>}
          <form onSubmit={regForm.handleSubmit(onRegister)}>
            <TextField {...regForm.register('full_name', { required: 'Имя обязательно' })} label="Имя" fullWidth size="small" sx={fieldSx}
              error={!!regForm.formState.errors.full_name} helperText={regForm.formState.errors.full_name?.message} />
            <TextField {...regForm.register('email', { required: 'Email обязателен', pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: 'Неверный формат' }})}
              label="Email" type="email" fullWidth size="small" sx={fieldSx}
              error={!!regForm.formState.errors.email} helperText={regForm.formState.errors.email?.message} />
            <TextField {...regForm.register('password', { required: 'Пароль обязателен', minLength: { value: 6, message: 'Минимум 6 символов' }})}
              label="Пароль" type={showRegPwd ? 'text' : 'password'} fullWidth size="small" sx={fieldSx}
              error={!!regForm.formState.errors.password} helperText={regForm.formState.errors.password?.message}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setShowRegPwd((v) => !v)} sx={{ color: C.textGray }} aria-label={showRegPwd ? 'Скрыть пароль' : 'Показать пароль'}>
                      {showRegPwd ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <Button type="submit" variant="contained" fullWidth disabled={regForm.formState.isSubmitting}
              sx={{ mt: 0.5, py: 1.2, fontWeight: 700, textTransform: 'none', fontSize: 15, background: `linear-gradient(135deg, ${C.accent}, ${C.accent2})`, borderRadius: 2 }}
            >
              {regForm.formState.isSubmitting ? <CircularProgress size={22} sx={{ color: '#fff' }} /> : 'Создать аккаунт'}
            </Button>
            <Typography sx={{ textAlign: 'center', mt: 1.5, fontSize: 13, color: C.textGray, cursor: 'pointer', '&:hover': { color: C.accent } }}
              onClick={() => { setRegAnchor(null); }}>Уже есть аккаунт? Войти</Typography>
          </form>
        </Popover>
      )}

      {/* ═══ HERO ═══ */}
      <Section sx={{ pt: '180px', pb: '120px', textAlign: 'center', minHeight: '100vh', display: 'flex', alignItems: 'center' }}>
        <GlowOrb color={C.accent} size={600} top="-10%" left="30%" />
        <GlowOrb color={C.accent2} size={400} top="20%" left="60%" delay={2} />
        <GlowOrb color={C.accent3} size={300} top="60%" left="10%" delay={4} />
        <Container maxWidth="md" sx={{ position: 'relative', zIndex: 1 }}>
          {/* Hero headline: visible immediately, no delay */}
          <Box>
            <AccentBadge>AI-платформа</AccentBadge>
            <Typography
              variant="h1"
              sx={{
                fontWeight: 900,
                fontSize: { xs: 32, md: 64 },
                lineHeight: 1.1,
                mb: 3,
                color: C.textWhite,
              }}
            >
              DIGITAL BROKER
            </Typography>
            <Typography sx={{ fontSize: { xs: 18, md: 22 }, color: C.textGray, mb: 2, maxWidth: 600, mx: 'auto' }}>
              AI-платформа для автоматизации таможенных деклараций
            </Typography>
            <Typography sx={{ fontSize: 16, color: C.textGray, opacity: 0.7, mb: 5 }}>
              От PDF до готовой ДТ за минуты
            </Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} justifyContent="center">
              <CtaButton onClick={() => { window.scrollTo({ top: 0, behavior: 'smooth' }); setTimeout(() => setLoginAnchor(document.querySelector('[data-login-btn]') as HTMLElement), 400); }}>Войти в систему</CtaButton>
              <SecondaryBtn onClick={() => document.getElementById('how')?.scrollIntoView({ behavior: 'smooth' })}>
                Как это работает
              </SecondaryBtn>
            </Stack>
          </Box>

          {/* Flow mini: PDF → AI → ДТ — secondary, can animate */}
          <Box sx={{ mt: 8, animation: `${fadeIn} 1.5s ease 0.5s both` }}>
            <Stack direction="row" alignItems="center" justifyContent="center" spacing={2}>
              {[
                { label: 'PDF', color: C.textWhite, bg: 'rgba(255,255,255,0.06)' },
                null,
                { label: 'AI', color: C.accent, bg: `${C.accent}18` },
                null,
                { label: 'ДТ', color: C.accent3, bg: `${C.accent3}18` },
              ].map((item, i) =>
                item ? (
                  <Box
                    key={i}
                    sx={{
                      width: 80, height: 56, borderRadius: 2,
                      background: item.bg,
                      border: `1px solid ${item.color}33`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 800, fontSize: 18, color: item.color,
                      animation: `${float} 3s ease-in-out infinite`,
                      animationDelay: `${i * 0.3}s`,
                    }}
                  >
                    {item.label}
                  </Box>
                ) : (
                  <Box key={i} sx={{ color: C.accent, fontSize: 24, fontWeight: 700 }}>→</Box>
                )
              )}
            </Stack>
          </Box>
        </Container>
      </Section>

      {/* ═══ PROBLEM ═══ */}
      <Section>
        <Container maxWidth="lg">
          <Reveal>
            <Grid container spacing={6} alignItems="center">
              <Grid item xs={12} md={7}>
                <Typography sx={{ fontWeight: 800, fontSize: { xs: 28, md: 36 }, mb: 1 }}>
                  Таможенное оформление сегодня —
                </Typography>
                <Typography sx={{ fontWeight: 800, fontSize: { xs: 28, md: 36 }, color: C.red, mb: 3 }}>
                  медленно и дорого
                </Typography>
                <Box sx={{ borderLeft: `3px solid ${C.red}`, pl: 3 }}>
                  {[
                    'На одну декларацию уходит от 2 до 4 часов',
                    'Сотни полей заполняются вручную',
                    'Ошибки в кодах ТН ВЭД приводят к штрафам и простоям',
                    'Справочники сложные и часто обновляются',
                  ].map((t, i) => (
                    <Stack key={i} direction="row" spacing={2} alignItems="flex-start" sx={{ mb: 2.5 }}>
                      <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: C.red, mt: '8px', flexShrink: 0 }} />
                      <Typography sx={{ fontSize: 17, color: C.textWhite }}>{t}</Typography>
                    </Stack>
                  ))}
                </Box>
              </Grid>
              <Grid item xs={12} md={5}>
                <GlassCard sx={{ textAlign: 'center', py: 6 }}>
                  <Typography sx={{ fontSize: 64, mb: 1 }}>⏱</Typography>
                  <Typography sx={{ fontSize: 48, fontWeight: 900, color: C.red }}>2–4 ч</Typography>
                  <Typography sx={{ color: C.textGray, fontSize: 15, mt: 1 }}>на одну декларацию</Typography>
                  <Divider sx={{ my: 3, borderColor: 'rgba(255,255,255,0.06)' }} />
                  <Typography sx={{ fontSize: 48, fontWeight: 900, color: C.yellow }}>50+</Typography>
                  <Typography sx={{ color: C.textGray, fontSize: 15, mt: 1 }}>полей для заполнения</Typography>
                </GlassCard>
              </Grid>
            </Grid>
          </Reveal>
        </Container>
      </Section>

      {/* ═══ SOLUTION / HOW IT WORKS (5 шагов) ═══ */}
      <Section id="how">
        <Container maxWidth="lg">
          <Reveal>
            <Box sx={{ textAlign: 'center', mb: 8 }}>
              <AccentBadge bg={C.accent3}>Процесс</AccentBadge>
              <Typography sx={{ fontWeight: 800, fontSize: { xs: 28, md: 36 } }}>
                AI, который берёт рутину на себя
              </Typography>
            </Box>
          </Reveal>
          <Grid container spacing={3}>
            {[
              { n: '1', t: 'Загрузка PDF', d: 'Вы загружаете PDF-документы в систему', c: C.accent },
              { n: '2', t: 'Извлечение данных', d: 'Система автоматически извлекает данные', c: C.accent2 },
              { n: '3', t: 'Подбор кодов', d: 'Подбирает коды ТН ВЭД', c: C.accent3 },
              { n: '4', t: 'Расчёт платежей', d: 'Считает все платежи', c: C.orange },
              { n: '5', t: 'Готовая ДТ', d: 'Формирует декларацию, готовую к подаче', c: C.yellow },
            ].map((s, i) => (
              <Grid item xs={12} sm={6} md={2.4} key={i}>
                <Reveal delay={i * 0.1}>
                  <GlassCard sx={{ textAlign: 'center', height: '100%' }}>
                    <Box
                      sx={{
                        width: 48, height: 48, borderRadius: '50%',
                        background: s.c, color: C.bgDark,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontWeight: 800, fontSize: 20, mx: 'auto', mb: 2,
                        boxShadow: `0 0 24px ${s.c}44`,
                      }}
                    >
                      {s.n}
                    </Box>
                    <Typography sx={{ fontWeight: 700, mb: 1, color: s.c }}>{s.t}</Typography>
                    <Typography sx={{ fontSize: 14, color: C.textGray }}>{s.d}</Typography>
                  </GlassCard>
                </Reveal>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Section>

      {/* ═══ FEATURES ═══ */}
      <Section id="features">
        <Container maxWidth="lg">
          <Box sx={{ textAlign: 'center', mb: 8 }}>
            <Reveal>
              <AccentBadge bg={C.accent2}>Возможности</AccentBadge>
              <Typography sx={{ fontWeight: 800, fontSize: { xs: 28, md: 36 } }}>
                Четыре ключевые фишки
              </Typography>
            </Reveal>
          </Box>
          <Grid container spacing={4}>
            {[
              {
                badge: 'Фишка #1', badgeColor: C.accent,
                title: 'Автозаполнение из PDF',
                bullets: [
                  'Понимает инвойсы, спецификации, сертификаты',
                  'Поддерживает разные форматы документов',
                  'Резко сокращает объём ручного ввода',
                ],
                icon: '📄',
              },
              {
                badge: 'Фишка #2', badgeColor: C.accent2,
                title: 'AI-подбор кодов ТН ВЭД',
                bullets: [
                  'Определяет код по описанию товара',
                  'Актуальная база кодов',
                  'Учитывает похожие кейсы из истории',
                ],
                icon: '🔍',
              },
              {
                badge: 'Фишка #3', badgeColor: C.accent3,
                title: 'Авторасчёт платежей',
                bullets: [
                  'Автоматически считает пошлины, НДС',
                  'Актуальные курсы валют',
                  'Прозрачный итог по декларации',
                ],
                icon: '💰',
              },
              {
                badge: 'Фишка #4', badgeColor: C.yellow,
                title: 'Контроль рисков',
                bullets: [
                  'Проверка полноты и логики данных',
                  'Подсветка проблемных мест',
                  'Подсказки до подачи ДТ',
                ],
                icon: '🛡️',
              },
            ].map((f, i) => (
              <Grid item xs={12} md={6} key={i}>
                <Reveal delay={i * 0.1}>
                  <GlassCard sx={{ height: '100%' }}>
                    <AccentBadge bg={f.badgeColor}>{f.badge}</AccentBadge>
                    <Typography sx={{ fontWeight: 700, fontSize: 22, mb: 2 }}>{f.title}</Typography>
                    {f.bullets.map((b, j) => (
                      <Stack key={j} direction="row" spacing={1.5} alignItems="flex-start" sx={{ mb: 1.5 }}>
                        <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: f.badgeColor, mt: '8px', flexShrink: 0 }} />
                        <Typography sx={{ fontSize: 15, color: C.textGray }}>{b}</Typography>
                      </Stack>
                    ))}
                  </GlassCard>
                </Reveal>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Section>

      {/* ═══ AUDIENCE ═══ */}
      <Section>
        <Container maxWidth="lg">
          <Reveal>
            <Box sx={{ textAlign: 'center', mb: 8 }}>
              <Typography sx={{ fontWeight: 800, fontSize: { xs: 28, md: 36 } }}>
                Кому Цифровой брокер даёт максимум
              </Typography>
            </Box>
          </Reveal>
          <Grid container spacing={4}>
            {[
              {
                title: 'Таможенные брокеры', color: C.accent, icon: '🏢',
                lines: ['Обрабатывают в разы больше деклараций', 'Снижают себестоимость каждой ДТ'],
              },
              {
                title: 'Импортёры и экспортёры', color: C.accent2, icon: '🌍',
                lines: ['Быстрее проходят таможню', 'Получают прогноз по платежам заранее'],
              },
              {
                title: 'Логистические компании', color: C.accent3, icon: '🚛',
                lines: ['Автоматизируют оформление для клиентов', 'Делают сервис более технологичным'],
              },
            ].map((col, i) => (
              <Grid item xs={12} md={4} key={i}>
                <Reveal delay={i * 0.15}>
                  <GlassCard sx={{ height: '100%', textAlign: 'center' }}>
                    <Typography sx={{ fontSize: 48, mb: 2 }}>{col.icon}</Typography>
                    <Typography sx={{ fontWeight: 700, fontSize: 20, color: col.color, mb: 2 }}>{col.title}</Typography>
                    <Divider sx={{ borderColor: `${col.color}33`, mb: 2 }} />
                    {col.lines.map((l, j) => (
                      <Typography key={j} sx={{ color: C.textGray, fontSize: 15, mb: 1 }}>{l}</Typography>
                    ))}
                  </GlassCard>
                </Reveal>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Section>

      {/* ═══ METRICS ═══ */}
      <Section>
        <Container maxWidth="md">
          <Reveal>
            <Box sx={{ textAlign: 'center', mb: 8 }}>
              <AccentBadge>Результаты</AccentBadge>
              <Typography sx={{ fontWeight: 800, fontSize: { xs: 28, md: 36 } }}>Что меняется в цифрах</Typography>
            </Box>
          </Reveal>
          {[
            { label: 'Время на декларацию', sub: 'часы → минуты', pct: 85, color: C.accent },
            { label: 'Количество ошибок', sub: 'резко падает', pct: 90, color: C.accent3 },
            { label: 'Производительность', sub: 'без переработок', pct: 75, color: C.accent2 },
            { label: 'Окупаемость', sub: 'первые месяцы', pct: 70, color: C.orange },
          ].map((m, i) => (
            <Reveal key={i} delay={i * 0.1}>
              <GlassCard sx={{ mb: 2, py: 2.5, px: 4 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                  <Box>
                    <Typography sx={{ fontWeight: 700, fontSize: 16 }}>{m.label}</Typography>
                    <Typography sx={{ fontSize: 13, color: C.textGray }}>{m.sub}</Typography>
                  </Box>
                  <Typography sx={{ fontWeight: 800, fontSize: 20, color: m.color }}>{m.pct}%</Typography>
                </Stack>
                <MetricBar pct={m.pct} barColor={m.color} />
              </GlassCard>
            </Reveal>
          ))}
        </Container>
      </Section>

      {/* ═══ CTA FINAL ═══ */}
      <Section sx={{ py: 12 }}>
        <Container maxWidth="md" sx={{ textAlign: 'center', position: 'relative', zIndex: 1 }}>
          <GlowOrb color={C.accent} size={400} top="-30%" left="20%" />
          <GlowOrb color={C.accent2} size={300} top="10%" left="60%" delay={1} />
          <Reveal>
            <Typography sx={{ fontWeight: 800, fontSize: { xs: 28, md: 36 }, mb: 3 }}>
              Посмотрите, как AI оформит ваши декларации
            </Typography>
            <Stack spacing={2.5} sx={{ maxWidth: 600, mx: 'auto', mb: 5 }}>
              {[
                { n: '1', t: 'Отправьте 3–5 типовых наборов документов', c: C.accent },
                { n: '2', t: 'Мы покажем, как система оформит их автоматически', c: C.accent2 },
                { n: '3', t: 'Вы оцените скорость, удобство и качество результата', c: C.accent3 },
              ].map((s) => (
                <Stack key={s.n} direction="row" spacing={2} alignItems="center">
                  <Box
                    sx={{
                      width: 40, height: 40, borderRadius: '50%',
                      background: s.c, color: C.bgDark,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 800, fontSize: 18, flexShrink: 0,
                    }}
                  >
                    {s.n}
                  </Box>
                  <Typography sx={{ fontSize: 16, textAlign: 'left' }}>{s.t}</Typography>
                </Stack>
              ))}
            </Stack>
            <CtaButton onClick={() => { window.scrollTo({ top: 0, behavior: 'smooth' }); setTimeout(() => setRegAnchor(document.querySelector('[data-reg-btn]') as HTMLElement), 400); }} sx={{ fontSize: 20, px: 6, py: 2 }}>
              Начать бесплатно
            </CtaButton>
          </Reveal>
        </Container>
      </Section>

      {/* ═══ CONTACTS ═══ */}
      <Section id="contacts" sx={{ py: 8, borderTop: `1px solid ${C.border}` }}>
        <Container maxWidth="md">
          <Reveal>
            <Box sx={{ textAlign: 'center', mb: 5 }}>
              <Typography sx={{ fontWeight: 800, fontSize: 28 }}>Связаться и получить демо</Typography>
            </Box>
            <Grid container spacing={2} justifyContent="center">
              {[
                { label: 'Сайт', value: 'digitalbroker.ru' },
                { label: 'Email', value: 'info@digitalbroker.ru' },
                { label: 'Telegram', value: '@digital_broker' },
                { label: 'Обратная связь', value: 'Запросить обратный звонок' },
              ].map((c, i) => (
                <Grid item xs={12} sm={6} key={i}>
                  <GlassCard sx={{ py: 2, px: 3 }}>
                    <Typography sx={{ fontSize: 12, color: C.textGray, mb: 0.5, textTransform: 'uppercase', letterSpacing: 1 }}>
                      {c.label}
                    </Typography>
                    <Typography sx={{ fontWeight: 600, color: C.accent }}>{c.value}</Typography>
                  </GlassCard>
                </Grid>
              ))}
            </Grid>
            <Typography sx={{ textAlign: 'center', color: C.textGray, mt: 4, fontSize: 14 }}>
              Напишите нам, чтобы получить демо-доступ и рассчитать эффект именно для вашего бизнеса
            </Typography>
          </Reveal>
        </Container>
      </Section>

      {/* ═══ FOOTER ═══ */}
      <Box sx={{ py: 3, textAlign: 'center', borderTop: `1px solid ${C.border}` }}>
        <Typography
          sx={{
            fontWeight: 800,
            fontSize: 14,
            background: `linear-gradient(135deg, ${C.accent}, ${C.accent2})`,
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          DIGITAL BROKER © {new Date().getFullYear()}
        </Typography>
      </Box>
    </Page>
  );
}
