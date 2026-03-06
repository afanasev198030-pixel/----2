import { useQuery } from '@tanstack/react-query';
import {
  Box, Typography, Paper, Grid, Card, CardContent, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Alert, Skeleton, TextField, MenuItem,
} from '@mui/material';
import {
  AttachMoney as MoneyIcon,
  Token as TokenIcon,
  Speed as SpeedIcon,
  Description as DeclIcon,
} from '@mui/icons-material';
import { useState } from 'react';
import AppLayout from '../components/AppLayout';
import client from '../api/client';

const AdminAiCostsPage = () => {
  const [days, setDays] = useState(30);

  const { data, isLoading, error } = useQuery({
    queryKey: ['ai-costs', days],
    queryFn: () => client.get(`/admin/ai-costs?days=${days}`).then(r => r.data),
    staleTime: 30_000,
  });

  const fmt = (n: number, d = 2) => n?.toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d }) ?? '—';
  const fmtInt = (n: number) => n?.toLocaleString('ru-RU') ?? '—';

  return (
    <AppLayout>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MoneyIcon color="primary" />
            <Typography variant="h5">Unit-экономика AI</Typography>
          </Box>
          <TextField
            select size="small" value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            sx={{ width: 150 }}
          >
            <MenuItem value={7}>7 дней</MenuItem>
            <MenuItem value={30}>30 дней</MenuItem>
            <MenuItem value={90}>90 дней</MenuItem>
            <MenuItem value={365}>Год</MenuItem>
          </TextField>
        </Box>

        <Alert severity="info" sx={{ mb: 2 }}>
          Отслеживание затрат на AI-обработку деклараций. Показывает сколько токенов и денег тратится
          на каждую операцию, какая модель дороже, и какова стоимость обработки одной декларации.
        </Alert>

        {error && <Alert severity="error" sx={{ mb: 2 }}>Ошибка загрузки данных</Alert>}

        {isLoading ? (
          <Grid container spacing={2}>
            {[1,2,3,4].map(i => <Grid item xs={6} md={3} key={i}><Skeleton variant="rectangular" height={100} /></Grid>)}
          </Grid>
        ) : data ? (
          <>
            {/* Summary cards */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center', py: 2 }}>
                    <MoneyIcon sx={{ fontSize: 32, color: 'warning.main', mb: 0.5 }} />
                    <Typography variant="h5" fontWeight={700} color="warning.main">
                      ${fmt(data.totals.cost_usd, 4)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">Общие затраты</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center', py: 2 }}>
                    <DeclIcon sx={{ fontSize: 32, color: 'primary.main', mb: 0.5 }} />
                    <Typography variant="h5" fontWeight={700} color="primary.main">
                      ${fmt(data.unit_economics.cost_per_declaration_usd, 4)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Стоимость 1 декларации ({data.unit_economics.declarations_processed} обработано)
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center', py: 2 }}>
                    <TokenIcon sx={{ fontSize: 32, color: 'info.main', mb: 0.5 }} />
                    <Typography variant="h5" fontWeight={700} color="info.main">
                      {fmtInt(data.totals.total_tokens)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Токенов ({fmtInt(data.totals.calls)} вызовов)
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center', py: 2 }}>
                    <SpeedIcon sx={{ fontSize: 32, color: 'success.main', mb: 0.5 }} />
                    <Typography variant="h5" fontWeight={700} color="success.main">
                      {fmtInt(data.totals.avg_duration_ms)} мс
                    </Typography>
                    <Typography variant="caption" color="text.secondary">Среднее время ответа</Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            {/* By operation */}
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>По операциям</Typography>
                  {data.by_operation.length === 0 ? (
                    <Typography variant="caption" color="text.secondary">Нет данных</Typography>
                  ) : (
                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Операция</TableCell>
                            <TableCell align="right">Вызовов</TableCell>
                            <TableCell align="right">Токенов</TableCell>
                            <TableCell align="right">Стоимость</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {data.by_operation.map((row: any) => (
                            <TableRow key={row.operation}>
                              <TableCell><Chip label={row.operation} size="small" /></TableCell>
                              <TableCell align="right">{fmtInt(row.calls)}</TableCell>
                              <TableCell align="right">{fmtInt(row.tokens)}</TableCell>
                              <TableCell align="right">${fmt(row.cost_usd, 4)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </Paper>
              </Grid>

              <Grid item xs={12} md={6}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>По моделям</Typography>
                  {data.by_model.length === 0 ? (
                    <Typography variant="caption" color="text.secondary">Нет данных</Typography>
                  ) : (
                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Модель</TableCell>
                            <TableCell align="right">Вызовов</TableCell>
                            <TableCell align="right">Токенов</TableCell>
                            <TableCell align="right">Стоимость</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {data.by_model.map((row: any) => (
                            <TableRow key={row.model}>
                              <TableCell><Chip label={row.model} size="small" variant="outlined" /></TableCell>
                              <TableCell align="right">{fmtInt(row.calls)}</TableCell>
                              <TableCell align="right">{fmtInt(row.tokens)}</TableCell>
                              <TableCell align="right">${fmt(row.cost_usd, 4)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </Paper>
              </Grid>
            </Grid>
          </>
        ) : null}
      </Box>
    </AppLayout>
  );
};

export default AdminAiCostsPage;
