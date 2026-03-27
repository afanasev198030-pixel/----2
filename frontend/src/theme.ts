import { createTheme } from '@mui/material/styles';

export const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#2563eb',
      dark: '#1d4ed8',
      light: '#eef2ff',
    },
    secondary: {
      main: '#00897b',
    },
    success: {
      main: '#059669',
    },
    warning: {
      main: '#d97706',
    },
    error: {
      main: '#dc2626',
    },
    info: {
      main: '#2563eb',
    },
    background: {
      default: '#f8fafc',
      paper: '#ffffff',
    },
    text: {
      primary: '#0f172a',
      secondary: '#64748b',
    },
  },
  typography: {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    h4: { fontWeight: 700 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 10,
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: 'none',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          border: '1px solid rgba(226,232,240,0.8)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
          transition: 'box-shadow 0.2s',
          '&:hover': {
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 14,
        },
        outlined: {
          border: '1px solid rgba(226,232,240,0.8)',
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-head': {
            fontSize: 12,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            color: '#64748b',
            backgroundColor: '#f8fafc',
            borderBottom: '1px solid rgba(226,232,240,0.8)',
            whiteSpace: 'nowrap',
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: 'rgba(248,250,252,0.8) !important',
          },
          transition: 'background-color 0.15s ease',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(241,245,249,1)',
          padding: '14px 16px',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
          fontSize: 13,
          borderRadius: 8,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: 'none',
        },
      },
    },
  },
});

export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#42a5f5', dark: '#1565c0', light: '#90caf9' },
    secondary: { main: '#26a69a' },
    success: { main: '#66bb6a' },
    warning: { main: '#ffa726' },
    error: { main: '#ef5350' },
    info: { main: '#29b6f6' },
    background: { default: '#0f172a', paper: '#1e293b' },
    text: { primary: '#e2e8f0', secondary: '#94a3b8' },
  },
  typography: {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    h4: { fontWeight: 700 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
  },
  shape: { borderRadius: 8 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 600, borderRadius: 8 },
        contained: {
          boxShadow: '0 2px 4px rgba(66,165,245,0.25)',
          '&:hover': { boxShadow: '0 4px 8px rgba(66,165,245,0.35)' },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          border: '1px solid rgba(255,255,255,0.06)',
          transition: 'transform 0.2s, box-shadow 0.2s',
          '&:hover': { transform: 'translateY(-2px)', boxShadow: '0 4px 12px rgba(0,0,0,0.4)' },
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-head': {
            fontSize: 12, fontWeight: 600, textTransform: 'uppercase',
            letterSpacing: '0.5px', color: '#94a3b8',
            backgroundColor: '#1e293b', borderBottom: '2px solid #334155',
            whiteSpace: 'nowrap',
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': { backgroundColor: 'rgba(255,255,255,0.03) !important' },
          transition: 'background-color 0.15s ease',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { borderBottom: '1px solid #1e293b', padding: '14px 16px' },
      },
    },
    MuiChip: {
      styleOverrides: { root: { fontWeight: 500, fontSize: 12 } },
    },
    MuiAppBar: {
      styleOverrides: {
        root: { boxShadow: '0 1px 3px rgba(0,0,0,0.3)' },
      },
    },
  },
});

export default lightTheme;
