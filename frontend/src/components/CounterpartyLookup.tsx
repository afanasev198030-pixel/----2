import { useState, useEffect } from 'react';
import { Autocomplete, TextField, CircularProgress, Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions, Grid } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { getCounterparties, createCounterparty, Counterparty } from '../api/counterparties';

interface CounterpartyLookupProps {
  value: string; // counterparty ID
  onChange: (id: string, cp?: Counterparty) => void;
  type: 'seller' | 'buyer' | 'importer' | 'declarant';
  label: string;
  companyId?: string;
  size?: 'small' | 'medium';
}

const CounterpartyLookup = ({ value, onChange, type, label, companyId, size = 'small' }: CounterpartyLookupProps) => {
  const [options, setOptions] = useState<Counterparty[]>([]);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newCp, setNewCp] = useState({ name: '', country_code: '', tax_number: '', address: '' });

  useEffect(() => {
    let active = true;
    setLoading(true);
    getCounterparties(inputValue || undefined, type)
      .then((data) => { if (active) setOptions(data); })
      .catch(() => {})
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [inputValue, type]);

  const selected = options.find((o) => o.id === value) || null;

  const handleCreate = async () => {
    try {
      const cp = await createCounterparty({ ...newCp, type, company_id: companyId || '' });
      onChange(cp.id, cp);
      setDialogOpen(false);
      setNewCp({ name: '', country_code: '', tax_number: '', address: '' });
      // Refresh options
      const updated = await getCounterparties(undefined, type);
      setOptions(updated);
    } catch (e) { console.error(e); }
  };

  return (
    <>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
        <Autocomplete
          size={size}
          fullWidth
          options={options}
          value={selected}
          inputValue={inputValue}
          onInputChange={(_, v) => setInputValue(v)}
          onChange={(_, item) => onChange(item?.id || '', item || undefined)}
          getOptionLabel={(o) => `${o.name}${o.country_code ? ` [${o.country_code}]` : ''}${o.tax_number ? ` (${o.tax_number})` : ''}`}
          isOptionEqualToValue={(o, v) => o.id === v.id}
          loading={loading}
          noOptionsText="Не найдено"
          renderInput={(params) => (
            <TextField {...params} label={label}
              InputProps={{ ...params.InputProps, endAdornment: (<>{loading && <CircularProgress size={16} />}{params.InputProps.endAdornment}</>) }}
            />
          )}
          renderOption={(props, option) => (
            <li {...props} key={option.id}>
              <Box>
                <Typography variant="body2" fontWeight={600}>{option.name}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {option.country_code || ''} {option.tax_number ? `ИНН: ${option.tax_number}` : ''} {option.address ? `| ${option.address.slice(0, 40)}` : ''}
                </Typography>
              </Box>
            </li>
          )}
        />
        <Button size="small" variant="outlined" onClick={() => setDialogOpen(true)} sx={{ minWidth: 40, px: 1 }}>
          <AddIcon fontSize="small" />
        </Button>
      </Box>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Новый контрагент ({type === 'seller' ? 'Продавец' : type === 'buyer' ? 'Покупатель' : type})</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={12}>
              <TextField fullWidth label="Наименование" size="small" required value={newCp.name} onChange={(e) => setNewCp({ ...newCp, name: e.target.value })} />
            </Grid>
            <Grid item xs={6}>
              <TextField fullWidth label="Код страны (ISO)" size="small" value={newCp.country_code} onChange={(e) => setNewCp({ ...newCp, country_code: e.target.value.toUpperCase().slice(0, 2) })} />
            </Grid>
            <Grid item xs={6}>
              <TextField fullWidth label="ИНН / Tax ID" size="small" value={newCp.tax_number} onChange={(e) => setNewCp({ ...newCp, tax_number: e.target.value })} />
            </Grid>
            <Grid item xs={12}>
              <TextField fullWidth label="Адрес" size="small" multiline rows={2} value={newCp.address} onChange={(e) => setNewCp({ ...newCp, address: e.target.value })} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleCreate} disabled={!newCp.name}>Создать</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default CounterpartyLookup;
