import { useMemo, useCallback } from 'react';
import { Autocomplete, TextField, CircularProgress } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { getClassifiers, Classifier } from '../api/classifiers';

interface ClassifierSelectProps {
  classifierType: string;
  value: string;
  onChange: (code: string, item?: Classifier) => void;
  label: React.ReactNode;
  size?: 'small' | 'medium';
  required?: boolean;
  disabled?: boolean;
  error?: boolean;
  helperText?: string;
}

const ClassifierSelect = ({
  classifierType, value, onChange, label,
  size = 'small', required, disabled, error, helperText,
}: ClassifierSelectProps) => {
  // Load all options ONCE per classifier type, cache 10 minutes
  const { data: options = [], isLoading } = useQuery({
    queryKey: ['classifiers', classifierType],
    queryFn: () => getClassifiers(classifierType),
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  const selected = useMemo(
    () => options.find((o) => o.code === value) || null,
    [options, value],
  );

  const handleChange = useCallback(
    (_: any, item: Classifier | null) => onChange(item?.code || '', item || undefined),
    [onChange],
  );

  const getLabel = useCallback(
    (o: Classifier) => `${o.code} — ${o.name_ru || o.name_en || ''}`,
    [],
  );

  return (
    <Autocomplete
      size={size}
      disabled={disabled}
      options={options}
      value={selected}
      onChange={handleChange}
      getOptionLabel={getLabel}
      isOptionEqualToValue={(o, v) => o.code === v.code}
      loading={isLoading}
      filterOptions={(opts, { inputValue }) => {
        if (!inputValue) return opts.slice(0, 50);
        const q = inputValue.toLowerCase();
        return opts.filter(
          (o) =>
            o.code.toLowerCase().includes(q) ||
            (o.name_ru || '').toLowerCase().includes(q) ||
            (o.name_en || '').toLowerCase().includes(q),
        ).slice(0, 50);
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          required={required}
          error={error}
          helperText={helperText}
          InputLabelProps={{ shrink: true }}
          slotProps={{
            input: {
              ...params.InputProps,
              endAdornment: (
                <>
                  {isLoading && <CircularProgress size={16} />}
                  {params.InputProps.endAdornment}
                </>
              ),
            },
          }}
        />
      )}
    />
  );
};

export default ClassifierSelect;
