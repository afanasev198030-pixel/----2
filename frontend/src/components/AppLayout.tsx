import { ReactNode, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  AppBar, Toolbar, Typography, Button, Box, Avatar, IconButton,
  Tooltip, Breadcrumbs, Link, Chip,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  People as PeopleIcon,
  Description as DeclarationsIcon,
  Settings as SettingsIcon,
  Logout as LogoutIcon,
  NavigateNext as NavNextIcon,
  Home as HomeIcon,
} from '@mui/icons-material';
import { getMe, logout } from '../api/auth';

interface AppLayoutProps {
  children: ReactNode;
  breadcrumbs?: Array<{ label: string; path?: string }>;
  noPadding?: boolean;
}

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/dashboard', icon: <DashboardIcon fontSize="small" /> },
  { label: 'Клиенты', path: '/clients', icon: <PeopleIcon fontSize="small" /> },
  { label: 'Декларации', path: '/declarations', icon: <DeclarationsIcon fontSize="small" /> },
  { label: 'Настройки', path: '/settings', icon: <SettingsIcon fontSize="small" /> },
];

const AppLayout = ({ children, breadcrumbs, noPadding }: AppLayoutProps) => {
  const navigate = useNavigate();
  const location = useLocation();

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
    <Box sx={{ minHeight: '100vh', bgcolor: '#f5f7fa' }}>
      <AppBar position="sticky" elevation={0} sx={{ bgcolor: 'primary.main' }}>
        <Toolbar sx={{ px: { xs: 2, md: 4 }, minHeight: { xs: 56 } }}>
          <Box
            onClick={() => navigate('/dashboard')}
            sx={{
              width: 36, height: 36, borderRadius: 2,
              background: 'rgba(255,255,255,0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              mr: 1.5, cursor: 'pointer',
            }}
          >
            <Typography sx={{ color: 'white', fontWeight: 700, fontSize: 14 }}>ТД</Typography>
          </Box>
          <Typography
            variant="subtitle1"
            onClick={() => navigate('/dashboard')}
            sx={{ fontWeight: 700, mr: 3, cursor: 'pointer', display: { xs: 'none', md: 'block' } }}
          >
            Панель брокера
          </Typography>

          <Box sx={{ display: 'flex', gap: 0.5, flexGrow: 1 }}>
            {NAV_ITEMS.map((item) => (
              <Button
                key={item.path}
                startIcon={item.icon}
                onClick={() => navigate(item.path)}
                size="small"
                sx={{
                  color: 'white',
                  textTransform: 'none',
                  fontWeight: isActive(item.path) ? 700 : 400,
                  bgcolor: isActive(item.path) ? 'rgba(255,255,255,0.15)' : 'transparent',
                  borderRadius: 2,
                  px: 1.5,
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' },
                }}
              >
                {item.label}
              </Button>
            ))}
          </Box>

          <Chip
            label={me?.full_name || 'Пользователь'}
            avatar={<Avatar sx={{ bgcolor: 'rgba(255,255,255,0.3) !important', color: 'white !important', fontSize: 12, fontWeight: 600 }}>{initials}</Avatar>}
            sx={{ color: 'white', bgcolor: 'rgba(255,255,255,0.1)', fontWeight: 500, mr: 0.5, display: { xs: 'none', sm: 'flex' } }}
            size="small"
          />
          <Tooltip title="Выйти">
            <IconButton color="inherit" onClick={handleLogout} size="small">
              <LogoutIcon fontSize="small" />
            </IconButton>
          </Tooltip>
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
      <Box sx={noPadding ? {} : { px: { xs: 2, md: 4 }, py: 2, maxWidth: 1400, mx: 'auto' }}>
        {children}
      </Box>
    </Box>
  );
};

export default AppLayout;
