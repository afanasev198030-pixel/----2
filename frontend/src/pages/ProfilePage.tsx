import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Paper, Typography, TextField, Button, Box, Snackbar } from '@mui/material';
import { Save as SaveIcon, Lock as LockIcon } from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import { getMe } from '../api/auth';
import client from '../api/client';

const ProfilePage = () => {
  const { data: me, refetch } = useQuery({ queryKey: ['me'], queryFn: getMe });
  const [fullName, setFullName] = useState('');
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' as 'success' | 'error' });

  // Init name from me data
  useEffect(() => {
    if (me?.full_name && !fullName) setFullName(me.full_name);
  }, [me?.full_name]);

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

  return (
    <AppLayout breadcrumbs={[{ label: 'Профиль' }]}>
      <Typography variant="h5" fontWeight={700} gutterBottom>Профиль</Typography>
      <Paper sx={{ p: 3, mb: 3, maxWidth: 600 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>Личные данные</Typography>
        <TextField fullWidth label="Email" value={me?.email || ''} disabled size="small" sx={{ mb: 2 }} />
        <TextField fullWidth label="Роль" value={me?.role || ''} disabled size="small" sx={{ mb: 2 }} />
        <TextField fullWidth label="Имя" value={fullName || me?.full_name || ''} onChange={(e) => setFullName(e.target.value)} size="small" sx={{ mb: 2 }} />
        <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSaveName} size="small">Сохранить имя</Button>
      </Paper>
      <Paper sx={{ p: 3, maxWidth: 600 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>Смена пароля</Typography>
        <TextField fullWidth label="Текущий пароль" type="password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} size="small" sx={{ mb: 2 }} />
        <TextField fullWidth label="Новый пароль" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} size="small" sx={{ mb: 2 }} />
        <Button variant="outlined" startIcon={<LockIcon />} onClick={handleChangePassword} size="small">Изменить пароль</Button>
      </Paper>
      <Snackbar open={snack.open} autoHideDuration={3000} onClose={() => setSnack({ ...snack, open: false })} message={snack.msg} />
    </AppLayout>
  );
};

export default ProfilePage;
