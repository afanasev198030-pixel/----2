import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Paper, Typography, TextField, Button, Box, Snackbar } from '@mui/material';
import { Save as SaveIcon, Lock as LockIcon, Telegram as TelegramIcon } from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import { getMe } from '../api/auth';
import client from '../api/client';

const ProfilePage = () => {
  const { data: me, refetch } = useQuery({ queryKey: ['me'], queryFn: getMe });
  const [fullName, setFullName] = useState('');
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' as 'success' | 'error' });

  const [telegramToken, setTelegramToken] = useState('');
  const [telegramUsername, setTelegramUsername] = useState('');

  // Init name from me data
  useEffect(() => {
    if (me?.full_name && !fullName) setFullName(me.full_name);
  }, [me?.full_name]);

  // Load telegram config
  useEffect(() => {
    client.get('/settings/').then(resp => {
      setTelegramUsername(resp.data.telegram_bot_username || '');
    }).catch(() => {});
  }, []);

  const handleSaveName = async () => {
    try {
      await client.put('/auth/profile', { full_name: fullName });
      refetch();
      setSnack({ open: true, msg: 'Имя обновлено', severity: 'success' });
    } catch (e: any) {
      setSnack({ open: true, msg: e?.response?.data?.detail || 'Ошибка', severity: 'error' });
    }
  };

  const handleChangePassword = async () => {
    if (!newPassword || newPassword.length < 6) {
      setSnack({ open: true, msg: 'Пароль должен быть не менее 6 символов', severity: 'error' });
      return;
    }
    try {
      await client.put('/auth/profile', { old_password: oldPassword, new_password: newPassword });
      setOldPassword(''); setNewPassword('');
      setSnack({ open: true, msg: 'Пароль изменён', severity: 'success' });
    } catch (e: any) {
      setSnack({ open: true, msg: e?.response?.data?.detail || 'Ошибка', severity: 'error' });
    }
  };

  const handleLinkTelegram = async () => {
    try {
      const resp = await client.post('/telegram/generate-link-token');
      if (resp.data.link_url) {
        window.open(resp.data.link_url, '_blank');
      }
    } catch (e: any) {
      setSnack({ open: true, msg: e?.response?.data?.detail || 'Ошибка генерации ссылки', severity: 'error' });
    }
  };

  const handleSaveTelegramConfig = async () => {
    try {
      await client.post('/settings/telegram-config', {
        bot_token: telegramToken,
        bot_username: telegramUsername
      });
      setSnack({ open: true, msg: 'Настройки Telegram сохранены', severity: 'success' });
    } catch (e: any) {
      setSnack({ open: true, msg: e?.response?.data?.detail || 'Ошибка', severity: 'error' });
    }
  };

  return (
    <AppLayout breadcrumbs={[{ label: 'Профиль' }]}>
      <Typography variant="h5" fontWeight={700} gutterBottom sx={{ color: '#0f172a' }}>Профиль</Typography>
      <Paper sx={{ p: 3, mb: 3, maxWidth: 600, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
        <Typography variant="h6" sx={{ mb: 2, color: '#0f172a' }}>Личные данные</Typography>
        <TextField fullWidth label="Email" value={me?.email || ''} disabled size="small" sx={{ mb: 2 }} />
        <TextField fullWidth label="Роль" value={me?.role || ''} disabled size="small" sx={{ mb: 2 }} />
        <TextField fullWidth label="Имя" value={fullName || me?.full_name || ''} onChange={(e) => setFullName(e.target.value)} size="small" sx={{ mb: 2 }} />
        <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSaveName} size="small">Сохранить имя</Button>
      </Paper>
      <Paper sx={{ p: 3, mb: 3, maxWidth: 600, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
        <Typography variant="h6" sx={{ mb: 2, color: '#0f172a' }}>Интеграции</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          {me?.telegram_id ? (
            <>
              <TelegramIcon color="primary" />
              <Typography sx={{ color: '#0f172a' }}>Telegram привязан (ID: {me.telegram_id})</Typography>
            </>
          ) : (
            <>
              <TelegramIcon color="disabled" />
              <Typography sx={{ color: '#64748b' }}>Telegram не привязан</Typography>
              <Button variant="outlined" onClick={handleLinkTelegram} size="small">
                Привязать Telegram
              </Button>
            </>
          )}
        </Box>
        
        {me?.role === 'admin' && (
          <Box sx={{ mt: 3, pt: 3, borderTop: '1px solid', borderColor: 'rgba(241,245,249,1)' }}>
            <Typography variant="subtitle2" sx={{ mb: 2, color: '#0f172a' }}>Настройки Telegram Бота (Только для администраторов)</Typography>
            <TextField 
              fullWidth 
              label="Токен бота (от @BotFather)" 
              value={telegramToken} 
              onChange={(e) => setTelegramToken(e.target.value)} 
              size="small" 
              sx={{ mb: 2 }} 
              type="password"
              placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
            />
            <TextField 
              fullWidth 
              label="Username бота (без @)" 
              value={telegramUsername} 
              onChange={(e) => setTelegramUsername(e.target.value)} 
              size="small" 
              sx={{ mb: 2 }} 
              placeholder="DigitalBrokerBot"
            />
            <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSaveTelegramConfig} size="small">
              Сохранить настройки бота
            </Button>
          </Box>
        )}
      </Paper>
      <Paper sx={{ p: 3, maxWidth: 600, border: '1px solid rgba(226,232,240,0.8)', boxShadow: 'none' }}>
        <Typography variant="h6" sx={{ mb: 2, color: '#0f172a' }}>Смена пароля</Typography>
        <TextField fullWidth label="Текущий пароль" type="password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} size="small" sx={{ mb: 2 }} />
        <TextField fullWidth label="Новый пароль" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} size="small" sx={{ mb: 2 }} />
        <Button variant="outlined" startIcon={<LockIcon />} onClick={handleChangePassword} size="small">Изменить пароль</Button>
      </Paper>
      <Snackbar open={snack.open} autoHideDuration={3000} onClose={() => setSnack({ ...snack, open: false })} message={snack.msg} />
    </AppLayout>
  );
};

export default ProfilePage;
