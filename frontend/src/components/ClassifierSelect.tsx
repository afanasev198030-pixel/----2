import { useState, useEffect } from 'react';
import { Autocomplete, TextField, CircularProgress } from '@mui/material';
import { getClassifiers, Classifier } from '../api/classifiers';

interface ClassifierSelectProps {
  classifierType: string;
  value: string;
  onChange: (code: string, item?: Classifier) => void;
  label: string;
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
  const [options, setOptions] = useState<Classifier[]>([]);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    getClassifiers(classifierType, inputValue || undefined)
      .then((data) => { if (active) setOptions(data.slice(0, 50)); })
      .catch(() => {})
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [classifierType, inputValue]);

  const selected = options.find((o) => o.code === value) || null;

  return (
    <Autocomplete
      size={size}
      disabled={disabled}
      options={options}
      value={selected}
      inputValue={inputValue}
      onInputChange={(_, v) => setInputValue(v)}
      onChange={(_, item) => onChange(item?.code || '', item || undefined)}
      getOptionLabel={(o) => `${o.code} — ${o.name_ru || o.name_en || ''}`}
      isOptionEqualToValue={(o, v) => o.code === v.code}
      loading={loading}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          required={required}
          error={error}
          helperText={helperText}
          InputProps={{
            ...params.InputProps,
            endAdornment: (
              <>
                {loading && <CircularProgress size={16} />}
                {params.InputProps.endAdornment}
              </>
            ),
          }}
        />
      )}
    />
  );
};

export default ClassifierSelect;
