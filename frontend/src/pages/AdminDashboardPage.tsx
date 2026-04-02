import { useQuery } from '@tanstack/react-query';
import {
  Box, Typography, Grid, Card, CardContent, Chip, Skeleton,
  Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
} from '@mui/material';
import {
  Dashboard as DashboardIcon, Memory as MemoryIcon, Description as DeclIcon,
  ModelTraining as TrainIcon, Storage as StorageIcon, Speed as SpeedIcon,
} from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import client from '../api/client';

const AdminDashboardPage = () => {
  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['admin-settings'],
    queryFn: async () => { const r = await client.get('/settings/'); return r.data; },
    retry: false,
  });

  const { data: training, isLoading: trainingLoading } = useQuery({
    queryKey: ['admin-training'],
    queryFn: async () => { const r = await client.get('/ai/training-stats'); return r.data; },
    retry: false,
  });

  const { data: articles } = useQuery({
    queryKey: ['admin-articles-count'],
    queryFn: async () => { const r = await client.get('/knowledge/articles'); return r.data; },
    retry: false,
  });

  const { data: checklists } = useQuery({
    queryKey: ['admin-checklists-count'],
    queryFn: async () => { const r = await client.get('/knowledge/checklists', { params: { active_only: false } }); return r.data; },
    retry: false,
  });

  const ai = training?.ai || training || {};
  const collections = ai?.collections || {};
  const isLoading = settingsLoading || trainingLoading;

  const services = settings?.services || [];

  return (
    <AppLayout breadcrumbs={[{ label: 'Админ', path: '/admin/users' }, { label: 'Dashboard' }]}>
      <Box sx={{ p: { xs: 1.5, sm: 2, md: 3 } }}>
        <Typography variant="h5" fontWeight={700} sx={{ mb: 3, color: '#0f172a' }}>
          <DashboardIcon sx={{ mr: 1, verticalAlign: 'bottom', color: '#2563eb' }} />
          Admin Dashboard
        </Typography>

        {isLoading ? (
          <Grid container spacing={2}>{[1,2,3,4].map(i => <Grid item xs={6} md={3} key={i}><Skeleton variant="rectangular" height={120} /></Grid>)}</Grid>
        ) : (
          <>
            <Grid container spacing={2} sx={{ mb: 3 }}>
              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center' }}>
                    <MemoryIcon sx={{ fontSize: 36, color: '#2563eb' }} />
                    <Typography variant="subtitle2" sx={{ mt: 0.5 }}>LLM Провайдер</Typography>
                    <Chip label={ai?.llm_provider || settings?.llm_provider || 'N/A'} size="small" color="primary" />
                    <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                      {ai?.llm_model || settings?.openai_model || ''}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center' }}>
                    <StorageIcon sx={{ fontSize: 36, color: '#2563eb' }} />
                    <Typography variant="subtitle2" sx={{ mt: 0.5 }}>ChromaDB</Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {collections.hs_codes || 0} ТН ВЭД
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {collections.precedents || 0} прецедентов
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center' }}>
                    <TrainIcon sx={{ fontSize: 36, color: '#d97706' }} />
                    <Typography variant="subtitle2" sx={{ mt: 0.5 }}>Обучение</Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {ai?.feedback_count || 0} feedback
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {ai?.optimized_models?.hs_classifier ? 'HS модель обучена' : 'Не оптимизировано'}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center' }}>
                    <DeclIcon sx={{ fontSize: 36, color: '#059669' }} />
                    <Typography variant="subtitle2" sx={{ mt: 0.5 }}>База знаний</Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {(articles || []).length} статей
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {(checklists || []).length} чек-листов
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Paper variant="outlined" sx={{ p: 2, boxShadow: 'none' }}>
                  <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1, color: '#0f172a' }}>Сервисы</Typography>
                  <Box sx={{ overflowX: 'auto', width: '100%' }}>
                  <TableContainer sx={{ overflowX: 'auto' }}>
                    <Table size="small" sx={{ minWidth: 320 }}>
                      <TableHead>
                        <TableRow>
                          <TableCell>Сервис</TableCell>
                          <TableCell>Статус</TableCell>
                          <TableCell>Порт</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {services.length > 0 ? services.map((s: any) => (
                          <TableRow key={s.name}>
                            <TableCell>{s.name}</TableCell>
                            <TableCell>
                              <Chip label={s.status === 'ok' ? 'OK' : s.status} size="small"
                                color={s.status === 'ok' ? 'success' : 'error'} />
                            </TableCell>
                            <TableCell>{s.port || '-'}</TableCell>
                          </TableRow>
                        )) : (
                          <TableRow><TableCell colSpan={3}><Typography variant="body2" color="text.secondary">Нет данных</Typography></TableCell></TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </TableContainer>
                  </Box>
                </Paper>
              </Grid>

              <Grid item xs={12} md={6}>
                <Paper variant="outlined" sx={{ p: 2, boxShadow: 'none' }}>
                  <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1, color: '#0f172a' }}>Последние события AI</Typography>
                  <Box sx={{ fontFamily: 'monospace', fontSize: 11, maxHeight: 250, overflowY: 'auto', bgcolor: '#f8fafc', p: 1, borderRadius: 2, border: '1px solid rgba(226,232,240,0.9)', boxShadow: 'none' }}>
                    {(ai?.log || []).slice(-20).reverse().map((entry: any, i: number) => {
                      const color = entry.level === 'error' ? '#dc2626' : entry.level === 'warning' ? '#d97706' : '#64748b';
                      const ts = entry.ts ? new Date(entry.ts * 1000).toLocaleTimeString('ru-RU') : '';
                      return (
                        <div key={i} style={{ marginBottom: 2 }}>
                          <span style={{ color: '#64748b' }}>{ts}</span>{' '}
                          <span style={{ color }}>{entry.event}</span>{' '}
                          <span>{entry.detail}</span>
                        </div>
                      );
                    })}
                    {(!ai?.log || ai.log.length === 0) && <Typography variant="body2" color="text.secondary">Нет событий</Typography>}
                  </Box>
                </Paper>
              </Grid>
            </Grid>
          </>
        )}
      </Box>
    </AppLayout>
  );
};

export default AdminDashboardPage;
