import { useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Button, Paper, TextField, Grid, Chip, IconButton,
  Dialog, DialogTitle, DialogContent, DialogActions, Alert, Tabs, Tab,
  Card, CardContent, CardActions, Tooltip, Skeleton,
} from '@mui/material';
import {
  Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon,
  Publish as PublishIcon, Unpublished as UnpublishIcon,
  Search as SearchIcon, MenuBook as BookIcon,
} from '@mui/icons-material';
import AppLayout from '../components/AppLayout';
import client from '../api/client';

interface Article {
  id: string;
  title: string;
  content: string;
  category: string;
  tags: string[];
  hs_codes: string[];
  is_published: boolean;
  created_at: string;
  updated_at: string;
}

const CATEGORIES = ['general', 'classification', 'electronics', 'chemicals', 'textiles', 'food', 'vehicles', 'other'];

const AdminKnowledgePage = () => {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editArticle, setEditArticle] = useState<Article | null>(null);
  const [form, setForm] = useState({ title: '', content: '', category: 'general', tags: '', hs_codes: '', is_published: false });

  const { data: articles = [], isLoading } = useQuery({
    queryKey: ['knowledge-articles', search, category],
    queryFn: async () => {
      const resp = await client.get('/knowledge/articles', { params: { q: search, category } });
      return resp.data;
    },
  });

  const openCreate = useCallback(() => {
    setEditArticle(null);
    setForm({ title: '', content: '', category: 'general', tags: '', hs_codes: '', is_published: false });
    setDialogOpen(true);
  }, []);

  const openEdit = useCallback((a: Article) => {
    setEditArticle(a);
    setForm({
      title: a.title, content: a.content, category: a.category,
      tags: (a.tags || []).join(', '), hs_codes: (a.hs_codes || []).join(', '),
      is_published: a.is_published,
    });
    setDialogOpen(true);
  }, []);

  const handleSave = useCallback(async () => {
    const payload = {
      title: form.title, content: form.content, category: form.category,
      tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
      hs_codes: form.hs_codes.split(',').map(t => t.trim()).filter(Boolean),
      is_published: form.is_published,
    };
    if (editArticle) {
      await client.put(`/knowledge/articles/${editArticle.id}`, payload);
    } else {
      await client.post('/knowledge/articles', payload);
    }
    queryClient.invalidateQueries({ queryKey: ['knowledge-articles'] });
    setDialogOpen(false);
  }, [form, editArticle, queryClient]);

  const handleDelete = useCallback(async (id: string) => {
    if (!window.confirm('Удалить статью?')) return;
    await client.delete(`/knowledge/articles/${id}`);
    queryClient.invalidateQueries({ queryKey: ['knowledge-articles'] });
  }, [queryClient]);

  const togglePublish = useCallback(async (a: Article) => {
    await client.put(`/knowledge/articles/${a.id}`, { is_published: !a.is_published });
    queryClient.invalidateQueries({ queryKey: ['knowledge-articles'] });
  }, [queryClient]);

  return (
    <AppLayout breadcrumbs={[{ label: 'Админ', path: '/admin/users' }, { label: 'База знаний' }]}>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h5" fontWeight={700} sx={{ color: '#0f172a' }}>
            <BookIcon sx={{ mr: 1, verticalAlign: 'bottom', color: '#2563eb' }} />
            База знаний ({articles.length})
          </Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>Новая статья</Button>
        </Box>

        <Alert severity="info" sx={{ mb: 2, boxShadow: 'none', border: '1px solid rgba(226,232,240,0.9)' }}>
          Статьи базы знаний помогают AI точнее классифицировать товары. Напишите экспертные заметки, например:
          «Электронные платы для кондиционеров классифицируются в 8537, а не в 8415» — и AI будет учитывать
          это при подборе кодов ТН ВЭД. Привяжите коды ТН ВЭД к статье для точного попадания.
        </Alert>

        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={8}>
            <TextField size="small" fullWidth placeholder="Поиск по статьям..." value={search}
              onChange={e => setSearch(e.target.value)}
              InputProps={{ startAdornment: <SearchIcon sx={{ mr: 1, color: '#64748b' }} /> }} />
          </Grid>
          <Grid item xs={4}>
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
              <Chip label="Все" size="small" variant={!category ? 'filled' : 'outlined'} onClick={() => setCategory('')} />
              {CATEGORIES.map(c => (
                <Chip key={c} label={c} size="small" variant={category === c ? 'filled' : 'outlined'} onClick={() => setCategory(c)} />
              ))}
            </Box>
          </Grid>
        </Grid>

        {isLoading ? (
          <Grid container spacing={2}>{[1,2,3].map(i => <Grid item xs={12} md={4} key={i}><Skeleton variant="rectangular" height={180} /></Grid>)}</Grid>
        ) : articles.length === 0 ? (
          <Alert severity="info">Нет статей. Создайте первую.</Alert>
        ) : (
          <Grid container spacing={2}>
            {articles.map((a: Article) => (
              <Grid item xs={12} md={4} key={a.id}>
                <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column', boxShadow: 'none' }}>
                  <CardContent sx={{ flex: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Chip label={a.category} size="small" color="primary" variant="outlined" sx={{ borderColor: 'rgba(37,99,235,0.35)', fontWeight: 500 }} />
                      <Chip label={a.is_published ? 'Опубликовано' : 'Черновик'} size="small"
                        color={a.is_published ? 'success' : 'default'}
                        variant={a.is_published ? 'filled' : 'outlined'}
                        sx={a.is_published ? {} : { borderColor: 'rgba(148,163,184,0.55)', color: '#64748b' }} />
                    </Box>
                    <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1, color: '#0f172a' }}>{a.title}</Typography>
                    <Typography variant="body2" sx={{ overflow: 'hidden', maxHeight: 60, color: '#64748b' }}>
                      {a.content.slice(0, 150)}...
                    </Typography>
                    {a.hs_codes?.length > 0 && (
                      <Box sx={{ mt: 1, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {a.hs_codes.slice(0, 3).map((c: string) => <Chip key={c} label={c} size="small" variant="outlined" sx={{ borderColor: 'rgba(148,163,184,0.55)', color: '#64748b' }} />)}
                      </Box>
                    )}
                  </CardContent>
                  <CardActions sx={{ justifyContent: 'flex-end' }}>
                    <Tooltip title={a.is_published ? 'Снять с публикации' : 'Опубликовать'}>
                      <IconButton size="small" onClick={() => togglePublish(a)}>
                        {a.is_published ? <UnpublishIcon fontSize="small" /> : <PublishIcon fontSize="small" />}
                      </IconButton>
                    </Tooltip>
                    <IconButton size="small" onClick={() => openEdit(a)}><EditIcon fontSize="small" /></IconButton>
                    <IconButton size="small" color="error" onClick={() => handleDelete(a.id)}><DeleteIcon fontSize="small" /></IconButton>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </Box>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>{editArticle ? 'Редактировать статью' : 'Новая статья'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={8}><TextField fullWidth label="Заголовок" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} size="small" /></Grid>
            <Grid item xs={4}><TextField fullWidth label="Категория" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} size="small" select SelectProps={{ native: true }}>
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </TextField></Grid>
            <Grid item xs={12}>
              <TextField fullWidth label="Содержание (Markdown)" value={form.content} onChange={e => setForm({ ...form, content: e.target.value })}
                multiline rows={12} size="small" />
            </Grid>
            <Grid item xs={6}><TextField fullWidth label="Теги (через запятую)" value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })} size="small" /></Grid>
            <Grid item xs={6}><TextField fullWidth label="Коды ТН ВЭД (через запятую)" value={form.hs_codes} onChange={e => setForm({ ...form, hs_codes: e.target.value })} size="small" /></Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleSave} disabled={!form.title.trim()}>
            {editArticle ? 'Сохранить' : 'Создать'}
          </Button>
        </DialogActions>
      </Dialog>
    </AppLayout>
  );
};

export default AdminKnowledgePage;
