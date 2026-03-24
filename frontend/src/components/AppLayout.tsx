import { ReactNode, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  AppBar, Toolbar, Typography, Button, Box, Avatar, IconButton,
  Tooltip, Breadcrumbs, Link,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  People as PeopleIcon,
  Description as DeclarationsIcon,
  Settings as SettingsIcon,
  Logout as LogoutIcon,
  NavigateNext as NavNextIcon,
  Notifications as NotificationsIcon,
  GridView as GridViewIcon,
} from '@mui/icons-material';
import { getMe, logout } from '../api/auth';
import { useAuth } from '../contexts/AuthContext';

import {
  AdminPanelSettings as AdminIcon,
  History as AuditIcon,
  Psychology as StrategyIcon,
  MenuBook as BookIcon,
  ChecklistRtl as ChecklistIcon,
  AttachMoney as CostIcon,
  BugReport as BugReportIcon,
} from '@mui/icons-material';

interface AppLayoutProps {
  children: ReactNode;
  breadcrumbs?: Array<{ label: string; path?: string }>;
  noPadding?: boolean;
}

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/dashboard', icon: <DashboardIcon sx={{ fontSize: 16 }} />, adminOnly: false },
  { label: 'Клиенты', path: '/clients', icon: <PeopleIcon sx={{ fontSize: 16 }} />, adminOnly: false },
  { label: 'Декларации', path: '/declarations', icon: <DeclarationsIcon sx={{ fontSize: 16 }} />, adminOnly: false },
  { label: 'Настройки', path: '/settings', icon: <SettingsIcon sx={{ fontSize: 16 }} />, adminOnly: true },
];

const ADMIN_NAV_ITEMS = [
  { label: 'AI-стратегии', path: '/admin/strategies', icon: <StrategyIcon sx={{ fontSize: 16 }} /> },
  { label: 'Пользователи', path: '/admin/users', icon: <PeopleIcon sx={{ fontSize: 16 }} /> },
  { label: 'Аудит', path: '/admin/audit', icon: <AuditIcon sx={{ fontSize: 16 }} /> },
  { label: 'База знаний', path: '/admin/knowledge', icon: <BookIcon sx={{ fontSize: 16 }} /> },
  { label: 'Чек-листы', path: '/admin/checklists', icon: <ChecklistIcon sx={{ fontSize: 16 }} /> },
  { label: 'AI-затраты', path: '/admin/ai-costs', icon: <CostIcon sx={{ fontSize: 16 }} /> },
  { label: 'Дебаг парсинга', path: '/admin/parse-debug', icon: <BugReportIcon sx={{ fontSize: 16 }} /> },
];

const AppLayout = ({ children, breadcrumbs, noPadding }: AppLayoutProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAdmin } = useAuth();

  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
    staleTime: 5 * 60 * 1000,
  });

  const isActive = (path: string) => {
    if (path === '/dashboard') return location.pathname === '/' || location.pathname === '/dashboard';
    return location.pathname.startsWith(path);
  };

  const initials = useMemo(() => {
    if (!me?.full_name) return 'А';
    return me.full_name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2);
  }, [me?.full_name]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const autoBreadcrumbs = useMemo(() => {
    if (breadcrumbs) return breadcrumbs;
    const path = location.pathname;
    const crumbs: Array<{ label: string; path?: string }> = [];
    if (path.startsWith('/declarations') && path.includes('/edit')) {
      crumbs.push({ label: 'Декларации', path: '/declarations' });
      crumbs.push({ label: 'Редактирование' });
    } else if (path.startsWith('/declarations') && path.includes('/view')) {
      crumbs.push({ label: 'Декларации', path: '/declarations' });
      crumbs.push({ label: 'Просмотр ДТ' });
    } else if (path.startsWith('/clients/') && path !== '/clients') {
      crumbs.push({ label: 'Клиенты', path: '/clients' });
      crumbs.push({ label: 'Детали клиента' });
    }
    return crumbs;
  }, [breadcrumbs, location.pathname]);

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          bgcolor: 'white',
          borderBottom: '1px solid #e2e8f0',
          color: '#0f172a',
        }}
      >
        <Toolbar sx={{ px: { xs: 2, md: 3 }, minHeight: { xs: 56 }, gap: 1.5 }}>
          {/* Logo */}
          <Box
            onClick={() => navigate('/dashboard')}
            sx={{
              width: 32, height: 32, borderRadius: '10px',
              background: 'linear-gradient(135deg, #1e293b, #0f172a)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', flexShrink: 0,
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            }}
          >
            <GridViewIcon sx={{ fontSize: 16, color: 'white' }} />
          </Box>
          <Box
            onClick={() => navigate('/dashboard')}
            sx={{ cursor: 'pointer', display: 'flex', alignItems: 'baseline', gap: 1, mr: 1 }}
          >
            <Typography sx={{ fontSize: 15, fontWeight: 600, color: '#0f172a', letterSpacing: '-0.01em' }}>
              Customs AI
            </Typography>
            <Box sx={{ width: 1, height: 16, bgcolor: '#e2e8f0' }} />
            <Typography sx={{ fontSize: 12, color: '#94a3b8', display: { xs: 'none', md: 'block' } }}>
              Панель брокера
            </Typography>
          </Box>

          {/* Main nav */}
          <Box sx={{ display: 'flex', gap: 0.25 }}>
            {NAV_ITEMS.filter(item => !item.adminOnly || isAdmin).map((item) => (
              <Button
                key={item.path}
                startIcon={item.icon}
                onClick={() => navigate(item.path)}
                size="small"
                sx={{
                  color: isActive(item.path) ? '#0f172a' : '#64748b',
                  textTransform: 'none',
                  fontWeight: isActive(item.path) ? 600 : 400,
                  fontSize: 12,
                  bgcolor: isActive(item.path) ? '#f1f5f9' : 'transparent',
                  borderRadius: '8px',
                  px: 1.5,
                  '&:hover': { bgcolor: '#f1f5f9' },
                }}
              >
                {item.label}
              </Button>
            ))}
          </Box>

          {/* Admin nav */}
          {isAdmin && (
            <Box sx={{ display: 'flex', gap: 0.25, ml: 0.5, pl: 1, borderLeft: '1px solid #e2e8f0' }}>
              {ADMIN_NAV_ITEMS.map((item) => (
                <Tooltip key={item.path} title={item.label}>
                  <IconButton
                    onClick={() => navigate(item.path)}
                    size="small"
                    sx={{
                      color: isActive(item.path) ? '#7c3aed' : '#94a3b8',
                      bgcolor: isActive(item.path) ? '#f5f3ff' : 'transparent',
                      '&:hover': { bgcolor: '#f5f3ff', color: '#7c3aed' },
                    }}
                  >
                    {item.icon}
                  </IconButton>
                </Tooltip>
              ))}
            </Box>
          )}

          <Box sx={{ flexGrow: 1 }} />

          {/* Right side */}
          <Tooltip title="Уведомления">
            <IconButton
              size="small"
              onClick={() => navigate('/declarations')}
              sx={{
                position: 'relative',
                color: '#94a3b8',
                '&:hover': { bgcolor: '#f1f5f9', color: '#64748b' },
              }}
            >
              <NotificationsIcon sx={{ fontSize: 18 }} />
              <Box sx={{
                position: 'absolute', top: 4, right: 4,
                width: 6, height: 6, borderRadius: '50%',
                bgcolor: '#ef4444', border: '2px solid white',
              }} />
            </IconButton>
          </Tooltip>
          <Tooltip title={me?.full_name || 'Профиль'}>
            <IconButton size="small" onClick={() => navigate('/profile')}>
              <Avatar
                sx={{
                  width: 30, height: 30,
                  bgcolor: '#f1f5f9',
                  color: '#64748b',
                  fontSize: 11,
                  fontWeight: 600,
                  border: '1px solid #e2e8f0',
                }}
              >
                {initials}
              </Avatar>
            </IconButton>
          </Tooltip>
          <Tooltip title="Выйти">
            <IconButton
              onClick={handleLogout}
              size="small"
              sx={{ color: '#94a3b8', '&:hover': { bgcolor: '#fef2f2', color: '#dc2626' } }}
            >
              <LogoutIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>

      {/* Breadcrumbs */}
      {autoBreadcrumbs.length > 0 && (
        <Box sx={{ px: { xs: 2, md: 3 }, pt: 1.5, pb: 0, maxWidth: 1440, mx: 'auto' }}>
          <Breadcrumbs separator={<NavNextIcon sx={{ fontSize: 14 }} />} sx={{ fontSize: 12 }}>
            {autoBreadcrumbs.map((crumb, i) => {
              const isLast = i === autoBreadcrumbs.length - 1;
              return isLast ? (
                <Typography key={i} sx={{ fontSize: 12, fontWeight: 600, color: '#0f172a' }}>
                  {crumb.label}
                </Typography>
              ) : (
                <Link
                  key={i}
                  underline="hover"
                  color="inherit"
                  onClick={() => crumb.path && navigate(crumb.path)}
                  sx={{ cursor: 'pointer', fontSize: 12, color: '#94a3b8' }}
                >
                  {crumb.label}
                </Link>
              );
            })}
          </Breadcrumbs>
        </Box>
      )}

      {/* Page content */}
      <Box sx={noPadding ? {} : { px: { xs: 2, md: 3 }, py: 2, maxWidth: 1440, mx: 'auto' }}>
        {children}
      </Box>
    </Box>
  );
};

export default AppLayout;
