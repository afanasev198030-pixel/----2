import { ReactNode, useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  AppBar, Toolbar, Typography, Button, Box, Avatar, IconButton,
  Tooltip, Breadcrumbs, Link, Drawer, List, ListItemButton, ListItemIcon,
  ListItemText, Divider, useTheme, useMediaQuery,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  People as PeopleIcon,
  Description as DeclarationsIcon,
  Settings as SettingsIcon,
  Logout as LogoutIcon,
  NavigateNext as NavNextIcon,
  Home as HomeIcon,
  Notifications as NotificationsIcon,
  Menu as MenuIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { getMe, logout } from '../api/auth';
import { useAuth } from '../contexts/AuthContext';

interface AppLayoutProps {
  children: ReactNode;
  breadcrumbs?: Array<{ label: string; path?: string }>;
  noPadding?: boolean;
}

import {
  AdminPanelSettings as AdminIcon,
  History as AuditIcon,
  Psychology as StrategyIcon,
  MenuBook as BookIcon,
  ChecklistRtl as ChecklistIcon,
  AttachMoney as CostIcon,
  BugReport as BugReportIcon,
} from '@mui/icons-material';

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/dashboard', icon: <DashboardIcon fontSize="small" />, adminOnly: false },
  { label: 'Клиенты', path: '/clients', icon: <PeopleIcon fontSize="small" />, adminOnly: false },
  { label: 'Декларации', path: '/declarations', icon: <DeclarationsIcon fontSize="small" />, adminOnly: false },
  { label: 'Настройки', path: '/settings', icon: <SettingsIcon fontSize="small" />, adminOnly: true },
];

const ADMIN_NAV_ITEMS: Array<{ label: string; path: string; icon: any }> = [
  { label: 'AI-стратегии', path: '/admin/strategies', icon: <StrategyIcon fontSize="small" /> },
  { label: 'Пользователи', path: '/admin/users', icon: <PeopleIcon fontSize="small" /> },
  { label: 'Аудит', path: '/admin/audit', icon: <AuditIcon fontSize="small" /> },
  { label: 'База знаний', path: '/admin/knowledge', icon: <BookIcon fontSize="small" /> },
  { label: 'Чек-листы', path: '/admin/checklists', icon: <ChecklistIcon fontSize="small" /> },
  { label: 'AI-затраты', path: '/admin/ai-costs', icon: <CostIcon fontSize="small" /> },
  { label: 'Дебаг парсинга', path: '/admin/parse-debug', icon: <BugReportIcon fontSize="small" /> },
];

const AppLayout = ({ children, breadcrumbs, noPadding }: AppLayoutProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [drawerOpen, setDrawerOpen] = useState(false);
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

  // Auto-generate breadcrumbs from path if not provided
  const autoBreadcrumbs = useMemo(() => {
    if (breadcrumbs) return breadcrumbs;
    const path = location.pathname;
    const crumbs: Array<{ label: string; path?: string }> = [];
    if (path.startsWith('/declarations') && path.includes('/form')) {
      crumbs.push({ label: 'Декларации', path: '/declarations' });
      const declId = path.split('/')[2];
      if (declId) crumbs.push({ label: 'Статус', path: `/declarations/${declId}/edit` });
      crumbs.push({ label: 'Редактирование формы' });
    } else if (path.startsWith('/declarations') && path.includes('/edit')) {
      crumbs.push({ label: 'Декларации', path: '/declarations' });
      crumbs.push({ label: 'Статус декларации' });
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
      <AppBar position="sticky" elevation={0} sx={{
        bgcolor: '#ffffff',
        borderBottom: '1px solid rgba(226,232,240,0.8)',
        boxShadow: 'none',
      }}>
        <Toolbar sx={{ px: { xs: 2, md: 4 }, minHeight: { xs: 52 } }}>
          {/* Logo / Brand */}
          <Box
            onClick={() => navigate('/dashboard')}
            sx={{
              width: 34, height: 34, borderRadius: '10px',
              bgcolor: '#eef2ff',
              border: '1px solid rgba(199,210,254,0.5)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              mr: 1.5, cursor: 'pointer',
              transition: 'background 0.15s',
              '&:hover': { bgcolor: '#e0e7ff' },
            }}
          >
            <Typography sx={{ color: '#3b82f6', fontWeight: 800, fontSize: 13, letterSpacing: '-0.02em' }}>ТД</Typography>
          </Box>
          <Typography
            variant="subtitle1"
            onClick={() => navigate('/dashboard')}
            sx={{
              fontWeight: 700, mr: 3, cursor: 'pointer',
              color: '#0f172a', fontSize: 15, letterSpacing: '-0.01em',
              display: { xs: 'none', md: 'block' },
            }}
          >
            Панель брокера
          </Typography>

          {/* Hamburger (mobile) */}
          {isMobile && (
            <IconButton onClick={() => setDrawerOpen(true)} sx={{ color: '#475569', mr: 0.5 }}>
              <MenuIcon />
            </IconButton>
          )}

          {/* Main nav (desktop) */}
          {!isMobile && (
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              {NAV_ITEMS.filter(item => !item.adminOnly || isAdmin).map((item) => (
                <Button
                  key={item.path}
                  startIcon={item.icon}
                  onClick={() => navigate(item.path)}
                  size="small"
                  sx={{
                    color: isActive(item.path) ? '#2563eb' : '#475569',
                    textTransform: 'none',
                    fontWeight: isActive(item.path) ? 600 : 500,
                    bgcolor: isActive(item.path) ? '#eef2ff' : 'transparent',
                    borderRadius: '10px',
                    px: 1.5, py: 0.6,
                    fontSize: 13,
                    transition: 'all 0.15s',
                    '&:hover': {
                      bgcolor: isActive(item.path) ? '#e0e7ff' : '#f1f5f9',
                      color: isActive(item.path) ? '#2563eb' : '#1e293b',
                    },
                    '& .MuiButton-startIcon': {
                      color: isActive(item.path) ? '#2563eb' : '#94a3b8',
                    },
                  }}
                >
                  {item.label}
                </Button>
              ))}
            </Box>
          )}

          {/* Admin nav (desktop, icon-only) */}
          {!isMobile && isAdmin && (
            <Box sx={{ display: 'flex', gap: 0.3, ml: 1, pl: 1, borderLeft: '1px solid rgba(226,232,240,0.8)' }}>
              {ADMIN_NAV_ITEMS.map((item) => (
                <Tooltip key={item.path} title={item.label}>
                  <IconButton
                    onClick={() => navigate(item.path)}
                    size="small"
                    sx={{
                      color: isActive(item.path) ? '#2563eb' : '#94a3b8',
                      bgcolor: isActive(item.path) ? '#eef2ff' : 'transparent',
                      transition: 'all 0.15s',
                      '&:hover': { bgcolor: '#f1f5f9', color: '#475569' },
                    }}
                  >
                    {item.icon}
                  </IconButton>
                </Tooltip>
              ))}
            </Box>
          )}

          <Box sx={{ flexGrow: 1 }} />

          {/* Right side: notifications, profile, logout */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
            <Tooltip title="Уведомления">
              <IconButton size="small" onClick={() => navigate('/declarations')} sx={{
                color: '#94a3b8', transition: 'all 0.15s',
                '&:hover': { bgcolor: '#f1f5f9', color: '#475569' },
              }}>
                <NotificationsIcon sx={{ fontSize: 20 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title={me?.full_name || 'Профиль'}>
              <IconButton size="small" onClick={() => navigate('/profile')} sx={{
                ml: 0.25,
                '&:hover': { bgcolor: 'transparent' },
              }}>
                <Avatar sx={{
                  width: 30, height: 30,
                  bgcolor: '#e0e7ff', color: '#3b82f6',
                  fontSize: 11, fontWeight: 700,
                  border: '1.5px solid rgba(199,210,254,0.6)',
                  transition: 'all 0.15s',
                  '&:hover': { bgcolor: '#dbeafe', borderColor: '#93c5fd' },
                }}>{initials}</Avatar>
              </IconButton>
            </Tooltip>
            <Tooltip title="Выйти">
              <IconButton onClick={handleLogout} size="small" sx={{
                color: '#94a3b8', transition: 'all 0.15s',
                '&:hover': { bgcolor: '#f1f5f9', color: '#475569' },
              }}>
                <LogoutIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Breadcrumbs */}
      {autoBreadcrumbs.length > 0 && (
        <Box sx={{ px: { xs: 2, md: 4 }, pt: 1.5, pb: 0, maxWidth: 1400, mx: 'auto' }}>
          <Breadcrumbs separator={<NavNextIcon fontSize="small" />} sx={{ fontSize: 13 }}>
            <Link
              underline="hover"
              color="inherit"
              onClick={() => navigate('/dashboard')}
              sx={{ display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'pointer', fontSize: 13 }}
            >
              <HomeIcon sx={{ fontSize: 16 }} /> Dashboard
            </Link>
            {autoBreadcrumbs.map((crumb, i) => {
              const isLast = i === autoBreadcrumbs.length - 1;
              return isLast ? (
                <Typography key={i} color="text.primary" sx={{ fontSize: 13, fontWeight: 600 }}>
                  {crumb.label}
                </Typography>
              ) : (
                <Link
                  key={i}
                  underline="hover"
                  color="inherit"
                  onClick={() => crumb.path && navigate(crumb.path)}
                  sx={{ cursor: 'pointer', fontSize: 13 }}
                >
                  {crumb.label}
                </Link>
              );
            })}
          </Breadcrumbs>
        </Box>
      )}

      {/* Page content */}
      <Box sx={noPadding ? {} : { px: { xs: 1.5, sm: 2, md: 4 }, py: 2, maxWidth: 1400, mx: 'auto' }}>
        {children}
      </Box>

      {/* Mobile Drawer */}
      <Drawer
        anchor="left"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        PaperProps={{ sx: { width: 280, bgcolor: '#fff' } }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2, py: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{
              width: 34, height: 34, borderRadius: '10px', bgcolor: '#eef2ff',
              border: '1px solid rgba(199,210,254,0.5)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Typography sx={{ color: '#3b82f6', fontWeight: 800, fontSize: 13 }}>ТД</Typography>
            </Box>
            <Typography sx={{ fontWeight: 700, fontSize: 15, color: '#0f172a' }}>Digital Broker</Typography>
          </Box>
          <IconButton size="small" onClick={() => setDrawerOpen(false)} sx={{ color: '#94a3b8' }}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
        <Divider />
        <List sx={{ px: 1, py: 1 }}>
          {NAV_ITEMS.filter(item => !item.adminOnly || isAdmin).map((item) => (
            <ListItemButton
              key={item.path}
              onClick={() => { navigate(item.path); setDrawerOpen(false); }}
              selected={isActive(item.path)}
              sx={{
                borderRadius: '10px', mb: 0.5, py: 1,
                '&.Mui-selected': { bgcolor: '#eef2ff', color: '#2563eb' },
                '&.Mui-selected:hover': { bgcolor: '#e0e7ff' },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36, color: isActive(item.path) ? '#2563eb' : '#94a3b8' }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: 14, fontWeight: isActive(item.path) ? 600 : 500 }} />
            </ListItemButton>
          ))}
        </List>
        {isAdmin && (
          <>
            <Divider sx={{ mx: 2 }} />
            <Typography sx={{ px: 2, pt: 1.5, pb: 0.5, fontSize: 11, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Администрирование
            </Typography>
            <List sx={{ px: 1, pb: 1 }}>
              {ADMIN_NAV_ITEMS.map((item) => (
                <ListItemButton
                  key={item.path}
                  onClick={() => { navigate(item.path); setDrawerOpen(false); }}
                  selected={isActive(item.path)}
                  sx={{
                    borderRadius: '10px', mb: 0.5, py: 0.8,
                    '&.Mui-selected': { bgcolor: '#eef2ff', color: '#2563eb' },
                    '&.Mui-selected:hover': { bgcolor: '#e0e7ff' },
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 36, color: isActive(item.path) ? '#2563eb' : '#94a3b8' }}>
                    {item.icon}
                  </ListItemIcon>
                  <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: 13, fontWeight: isActive(item.path) ? 600 : 500 }} />
                </ListItemButton>
              ))}
            </List>
          </>
        )}
      </Drawer>
    </Box>
  );
};

export default AppLayout;
