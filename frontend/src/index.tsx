import React, { createContext, useState, useMemo } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { ruRU } from '@mui/material/locale';
import { createTheme } from '@mui/material/styles';
import App from './App';
import { AuthProvider } from './contexts/AuthContext';
import { lightTheme, darkTheme } from './theme';

export const ThemeToggleContext = createContext({
  toggleTheme: () => {},
  mode: 'light' as 'light' | 'dark',
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const savedMode = (localStorage.getItem('theme') as 'light' | 'dark') || 'light';

const Root = () => {
  const [mode, setMode] = useState<'light' | 'dark'>(savedMode);

  const toggleTheme = () => {
    const next = mode === 'light' ? 'dark' : 'light';
    localStorage.setItem('theme', next);
    setMode(next);
  };

  const theme = useMemo(
    () => createTheme(mode === 'light' ? lightTheme : darkTheme, ruRU),
    [mode],
  );

  return (
    <ThemeToggleContext.Provider value={{ toggleTheme, mode }}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ThemeProvider theme={theme}>
            <CssBaseline />
            <AuthProvider>
              <App />
            </AuthProvider>
          </ThemeProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeToggleContext.Provider>
  );
};

const container = document.getElementById('root');
if (!container) {
  throw new Error('Root element not found');
}

const root = createRoot(container);

root.render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
