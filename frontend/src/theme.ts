import { createTheme } from '@mui/material/styles';

const commonTypography = {
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  h4: { fontWeight: 700, fontSize: '1.5rem', letterSpacing: '-0.02em' },
  h5: { fontWeight: 600, fontSize: '1.25rem', letterSpacing: '-0.01em' },
  h6: { fontWeight: 600, fontSize: '1rem', letterSpacing: '-0.01em' },
  subtitle1: { fontWeight: 600, fontSize: '0.875rem' },
  subtitle2: { fontWeight: 600, fontSize: '0.8125rem' },
  body1: { fontSize: '0.875rem' },
  body2: { fontSize: '0.8125rem' },
  caption: { fontSize: '0.6875rem', fontWeight: 500 },
};

const lightComponents = {
  MuiButton: {
    styleOverrides: {
      root: {
        textTransform: 'none' as const,
        fontWeight: 600,
        borderRadius: 10,
        fontSize: '0.8125rem',
      },
      contained: {
        boxShadow: 'none',
        '&:hover': {
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        },
      },
      outlined: {
        borderColor: '#e2e8f0',
        '&:hover': {
          borderColor: '#cbd5e1',
          backgroundColor: '#f8fafc',
        },
      },
      sizeSmall: {
        fontSize: '0.75rem',
        padding: '4px 12px',
        borderRadius: 8,
      },
    },
  },
  MuiCard: {
    styleOverrides: {
      root: {
        borderRadius: 14,
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        border: '1px solid #e2e8f0',
        transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
        '&:hover': {
          boxShadow: '0 4px 12px rgba(0,0,0,0.06)',
          borderColor: '#cbd5e1',
        },
      },
    },
  },
  MuiPaper: {
    styleOverrides: {
      root: {
        borderRadius: 12,
      },
      elevation1: {
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      },
    },
  },
  MuiTableHead: {
    styleOverrides: {
      root: {
        '& .MuiTableCell-head': {
          fontSize: 11,
          fontWeight: 600,
          textTransform: 'uppercase' as const,
          letterSpacing: '0.04em',
          color: '#64748b',
          backgroundColor: '#f8fafc',
          borderBottom: '1px solid #e2e8f0',
          whiteSpace: 'nowrap' as const,
          padding: '10px 16px',
        },
      },
    },
  },
  MuiTableRow: {
    styleOverrides: {
      root: {
        '&:hover': {
          backgroundColor: '#f8fafc !important',
        },
        transition: 'background-color 0.15s ease',
      },
    },
  },
  MuiTableCell: {
    styleOverrides: {
      root: {
        borderBottom: '1px solid #f1f5f9',
        padding: '12px 16px',
        fontSize: '0.8125rem',
      },
    },
  },
  MuiChip: {
    styleOverrides: {
      root: {
        fontWeight: 500,
        fontSize: 11,
        height: 24,
        borderRadius: 8,
      },
      sizeSmall: {
        height: 22,
        fontSize: 10,
      },
    },
  },
  MuiAppBar: {
    styleOverrides: {
      root: {
        boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
      },
    },
  },
  MuiDialog: {
    styleOverrides: {
      paper: {
        borderRadius: 16,
        boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
      },
    },
  },
  MuiTooltip: {
    styleOverrides: {
      tooltip: {
        fontSize: '0.75rem',
        borderRadius: 8,
        backgroundColor: '#1e293b',
      },
    },
  },
  MuiTextField: {
    styleOverrides: {
      root: {
        '& .MuiOutlinedInput-root': {
          borderRadius: 10,
          fontSize: '0.875rem',
        },
      },
    },
  },
};

export const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#0f172a',
      dark: '#020617',
      light: '#e2e8f0',
    },
    secondary: {
      main: '#6366f1',
      light: '#eef2ff',
    },
    success: {
      main: '#059669',
      light: '#ecfdf5',
      dark: '#065f46',
    },
    warning: {
      main: '#d97706',
      light: '#fffbeb',
      dark: '#92400e',
    },
    error: {
      main: '#dc2626',
      light: '#fef2f2',
      dark: '#991b1b',
    },
    info: {
      main: '#2563eb',
      light: '#eff6ff',
      dark: '#1e40af',
    },
    background: {
      default: '#f5f6f8',
      paper: '#ffffff',
    },
    text: {
      primary: '#0f172a',
      secondary: '#64748b',
    },
    divider: '#e2e8f0',
  },
  typography: commonTypography,
  shape: {
    borderRadius: 10,
  },
  components: lightComponents,
});

export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#e2e8f0', dark: '#f8fafc', light: '#334155' },
    secondary: { main: '#818cf8', light: '#1e1b4b' },
    success: { main: '#34d399', light: '#064e3b', dark: '#6ee7b7' },
    warning: { main: '#fbbf24', light: '#451a03', dark: '#fcd34d' },
    error: { main: '#f87171', light: '#450a0a', dark: '#fca5a5' },
    info: { main: '#60a5fa', light: '#172554', dark: '#93c5fd' },
    background: { default: '#0f172a', paper: '#1e293b' },
    text: { primary: '#e2e8f0', secondary: '#94a3b8' },
    divider: '#334155',
  },
  typography: commonTypography,
  shape: { borderRadius: 10 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 600, borderRadius: 10, fontSize: '0.8125rem' },
        contained: {
          boxShadow: 'none',
          '&:hover': { boxShadow: '0 1px 3px rgba(0,0,0,0.3)' },
        },
        sizeSmall: { fontSize: '0.75rem', padding: '4px 12px', borderRadius: 8 },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
          border: '1px solid #334155',
          transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
          '&:hover': { boxShadow: '0 4px 12px rgba(0,0,0,0.3)', borderColor: '#475569' },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { borderRadius: 12 },
        elevation1: { boxShadow: '0 1px 3px rgba(0,0,0,0.2)' },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-head': {
            fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
            letterSpacing: '0.04em', color: '#94a3b8',
            backgroundColor: '#1e293b', borderBottom: '1px solid #334155',
            whiteSpace: 'nowrap', padding: '10px 16px',
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
        root: { borderBottom: '1px solid #1e293b', padding: '12px 16px', fontSize: '0.8125rem' },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 500, fontSize: 11, height: 24, borderRadius: 8 },
        sizeSmall: { height: 22, fontSize: 10 },
      },
    },
    MuiAppBar: {
      styleOverrides: { root: { boxShadow: '0 1px 2px rgba(0,0,0,0.3)' } },
    },
    MuiDialog: {
      styleOverrides: {
        paper: { borderRadius: 16, boxShadow: '0 8px 30px rgba(0,0,0,0.4)' },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: { fontSize: '0.75rem', borderRadius: 8, backgroundColor: '#334155' },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': { borderRadius: 10, fontSize: '0.875rem' },
        },
      },
    },
  },
});

export default lightTheme;
