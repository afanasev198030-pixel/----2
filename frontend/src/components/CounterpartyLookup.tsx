import { useState, useCallback, useEffect } from 'react';
import {
  Autocomplete, TextField, Box, Typography, Button, Dialog,
  DialogTitle, DialogContent, DialogActions, Grid, Chip,
} from '@mui/material';
import { Add as AddIcon, Business as BusinessIcon } from '@mui/icons-material';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getCounterparties, createCounterparty, Counterparty } from '../api/counterparties';

interface CounterpartyLookupProps {
  type: 'seller' | 'buyer' | 'importer' | 'declarant';
  value?: string | null;
  onChange: (counterpartyId: string | null, counterparty?: Counterparty) => void;
  label?: string;
  initialData?: { name?: string; country_code?: string; tax_number?: string; address?: string };
}

export default function CounterpartyLookup({ type, value, onChange, label, initialData }: CounterpartyLookupProps) {
  const [inputValue, setInputValue] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newCountry, setNewCountry] = useState('');
  const [newTaxNumber, setNewTaxNumber] = useState('');
  const [newAddress, setNewAddress] = useState('');
  const queryClient = useQueryClient();

  const { data: options = [] } = useQuery({
    queryKey: ['counterparties', type],
    queryFn: () => getCounterparties(undefined, type),
    staleTime: 60_000,
  });

  const selected = options.find(o => o.id === value) || null;

  useEffect(() => {
    if (initialData?.name && !value && options.length > 0) {
      const match = options.find(o =>
        o.name.toLowerCase().includes(initialData.name!.toLowerCase().slice(0, 15))
      );
      if (match) {
        onChange(match.id, match);
      }
    }
  }, [initialData?.name, options.length]); // eslint-disable-line

  const handleCreate = useCallback(async () => {
    if (!newName.trim()) return;
    try {
      const created = await createCounterparty({
        type, name: newName.trim(),
        country_code: newCountry.trim().toUpperCase() || undefined,
        tax_number: newTaxNumber.trim() || undefined,
        address: newAddress.trim() || undefined,
      });
      queryClient.invalidateQueries({ queryKey: ['counterparties', type] });
      onChange(created.id, created);
      setDialogOpen(false);
      setNewName(''); setNewCountry(''); setNewTaxNumber(''); setNewAddress('');
    } catch (e) {
      console.error('Failed to create counterparty', e);
    }
  }, [newName, newCountry, newTaxNumber, newAddress, type, onChange, queryClient]);

  const openCreateDialog = useCallback(() => {
    setNewName(initialData?.name || inputValue);
    setNewCountry(initialData?.country_code || '');
    setNewTaxNumber(initialData?.tax_number || '');
    setNewAddress(initialData?.address || '');
    setDialogOpen(true);
  }, [initialData, inputValue]);

  return (
    <>
      <Autocomplete
        size="small"
        options={options}
        value={selected}
        inputValue={inputValue}
        onInputChange={(_, v) => setInputValue(v)}
        onChange={(_, val) => onChange(val?.id || null, val || undefined)}
        getOptionLabel={(o) => o.name || ''}
        isOptionEqualToValue={(o, v) => o.id === v.id}
        filterOptions={(opts, state) => {
          const q = state.inputValue.toLowerCase();
          const filtered = opts.filter(o =>
            o.name.toLowerCase().includes(q) ||
            (o.tax_number || '').includes(q) ||
            (o.country_code || '').toLowerCase().includes(q)
          );
          return filtered;
        }}
        renderOption={(props, option) => (
          <Box component="li" {...props} key={option.id} sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <BusinessIcon fontSize="small" color="action" />
            <Box>
              <Typography variant="body2" fontWeight={500}>{option.name}</Typography>
              <Typography variant="caption" color="text.secondary">
                {[option.country_code, option.tax_number].filter(Boolean).join(' | ')}
              </Typography>
            </Box>
          </Box>
        )}
        renderInput={(params) => (
          <TextField
            {...params}
            label={label || (type === 'seller' ? 'Отправитель (графа 2)' : 'Получатель (графа 8)')}
            InputLabelProps={{ shrink: true }}
            InputProps={{
              ...params.InputProps,
              endAdornment: (
                <>
                  {params.InputProps.endAdornment}
                  <Chip
                    label="+"
                    size="small"
                    onClick={openCreateDialog}
                    sx={{ cursor: 'pointer', ml: 0.5, height: 20, fontSize: 11 }}
                  />
                </>
              ),
            }}
          />
        )}
        noOptionsText={
          <Button size="small" startIcon={<AddIcon />} onClick={openCreateDialog}>
            Создать контрагента
          </Button>
        }
      />

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Новый контрагент ({type === 'seller' ? 'Отправитель' : 'Получатель'})</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={12}>
              <TextField fullWidth label="Наименование" value={newName} onChange={e => setNewName(e.target.value)} size="small" autoFocus />
            </Grid>
            <Grid item xs={4}>
              <TextField fullWidth label="Страна (ISO)" value={newCountry} onChange={e => setNewCountry(e.target.value)} size="small" placeholder="CN" inputProps={{ maxLength: 2 }} />
            </Grid>
            <Grid item xs={8}>
              <TextField fullWidth label="ИНН / Tax ID" value={newTaxNumber} onChange={e => setNewTaxNumber(e.target.value)} size="small" />
            </Grid>
            <Grid item xs={12}>
              <TextField fullWidth label="Адрес" value={newAddress} onChange={e => setNewAddress(e.target.value)} size="small" multiline rows={2} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleCreate} disabled={!newName.trim()}>Создать</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
