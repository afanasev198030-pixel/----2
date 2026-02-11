import { useState } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import {
  Card, CardContent, TextField, Button, Typography, Box,
  Snackbar, Alert, Link,
} from '@mui/material';
import client from '../api/client';
import { useAuth } from '../contexts/AuthContext';

interface RegisterForm {
  email: string;
  password: string;
  password_confirm: string;
  full_name: string;
  phone: string;
  company_name: string;
}

const RegisterPage = () => {
  const navigate = useNavigate();
  const { reload } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>();

  const password = watch('password');

  const onSubmit = async (data: RegisterForm) => {
    try {
      setError(null);
      const resp = await client.post('/auth/register-public', {
        email: data.email,
        password: data.password,
        full_name: data.full_name,
        phone: data.phone || null,
        company_name: data.company_name || null,
      });
      if (resp.data.access_token) {
        localStorage.setItem('token', resp.data.access_token);
        reload();
        navigate('/dashboard');
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Ошибка регистрации';
      setError(msg);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#f5f7fa' }}>
      <Box sx={{ width: '100%', maxWidth: 460, mx: 2 }}>
        <Card sx={{ borderRadius: 3, boxShadow: '0 8px 32px rgba(0,0,0,0.1)' }}>
          <CardContent sx={{ p: 5 }}>
            <Box sx={{ textAlign: 'center', mb: 3 }}>
              <Box sx={{ width: 64, height: 64, borderRadius: 3, background: 'linear-gradient(135deg, #1976d2, #0d47a1)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', mb: 2 }}>
                <Typography variant="h5" sx={{ color: 'white', fontWeight: 700 }}>ТД</Typography>
              </Box>
              <Typography variant="h5" fontWeight={700} gutterBottom>
                Регистрация
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Создайте аккаунт для работы с таможенными декларациями
              </Typography>
            </Box>
            <form onSubmit={handleSubmit(onSubmit)}>
              <TextField
                {...register('full_name', { required: 'ФИО обязательно' })}
                label="ФИО"
                fullWidth
                margin="dense"
                size="small"
                error={!!errors.full_name}
                helperText={errors.full_name?.message}
              />
              <TextField
                {...register('email', {
                  required: 'Email обязателен',
                  pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: 'Неверный формат email' },
                })}
                label="Email"
                type="email"
                fullWidth
                margin="dense"
                size="small"
                error={!!errors.email}
                helperText={errors.email?.message}
              />
              <TextField
                {...register('phone')}
                label="Телефон"
                fullWidth
                margin="dense"
                size="small"
                placeholder="+7 (999) 123-45-67"
              />
              <TextField
                {...register('company_name')}
                label="Название компании (необязательно)"
                fullWidth
                margin="dense"
                size="small"
                placeholder="ООО «Моя компания»"
              />
              <TextField
                {...register('password', {
                  required: 'Пароль обязателен',
                  minLength: { value: 6, message: 'Минимум 6 символов' },
                })}
                label="Пароль"
                type="password"
                fullWidth
                margin="dense"
                size="small"
                error={!!errors.password}
                helperText={errors.password?.message}
              />
              <TextField
                {...register('password_confirm', {
                  required: 'Подтвердите пароль',
                  validate: (v) => v === password || 'Пароли не совпадают',
                })}
                label="Подтверждение пароля"
                type="password"
                fullWidth
                margin="dense"
                size="small"
                error={!!errors.password_confirm}
                helperText={errors.password_confirm?.message}
              />
              <Button
                type="submit"
                variant="contained"
                fullWidth
                size="large"
                sx={{ mt: 2, mb: 1, py: 1.5, fontSize: 16, fontWeight: 600, borderRadius: 2 }}
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Регистрация...' : 'Зарегистрироваться'}
              </Button>
            </form>
            <Box sx={{ textAlign: 'center', mt: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Уже есть аккаунт?{' '}
                <Link component={RouterLink} to="/login" underline="hover">
                  Войти
                </Link>
              </Typography>
            </Box>
          </CardContent>
        </Card>
      </Box>
      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>
      </Snackbar>
    </Box>
  );
};

export default RegisterPage;
