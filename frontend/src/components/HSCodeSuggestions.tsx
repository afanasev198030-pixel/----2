import { useState } from 'react';
import { Box, Typography, Chip, LinearProgress, Button, Paper } from '@mui/material';
import { AutoAwesome as AiIcon } from '@mui/icons-material';
import { classifyHS, HSSuggestion } from '../api/ai';

interface HSCodeSuggestionsProps {
  description: string;
  currentCode: string;
  onSelect: (code: string, name: string) => void;
  countryOrigin?: string;
  unitPrice?: number;
  declarationId?: string;
}

const HSCodeSuggestions = ({ description, currentCode, onSelect, countryOrigin, unitPrice, declarationId }: HSCodeSuggestionsProps) => {
  const [suggestions, setSuggestions] = useState<HSSuggestion[]>([]);
  const [loading, setLoading] = useState(false);

  const handleClassify = async () => {
    if (!description || description.length < 3) return;
    setLoading(true);
    try {
      const result = await classifyHS(description, countryOrigin, unitPrice, declarationId);
      setSuggestions(result);
    } catch (e) {
      console.error('HS classify error:', e);
    } finally {
      setLoading(false);
    }
  };

  const confidenceColor = (c: number): 'success' | 'warning' | 'error' => {
    if (c >= 0.8) return 'success';
    if (c >= 0.5) return 'warning';
    return 'error';
  };

  return (
    <Box sx={{ mt: 1 }}>
      <Button
        size="small"
        startIcon={<AiIcon />}
        onClick={handleClassify}
        disabled={loading || !description || description.length < 3}
        variant="text"
        sx={{ textTransform: 'none', fontSize: 12 }}
      >
        {loading ? 'Классификация...' : 'Подобрать код ТН ВЭД'}
      </Button>
      {loading && <LinearProgress sx={{ mt: 0.5 }} />}
      {suggestions.length > 0 && (
        <Paper variant="outlined" sx={{ mt: 1, p: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            Предложения AI:
          </Typography>
          {suggestions.map((s, i) => (
            <Box
              key={i}
              onClick={() => onSelect(s.hs_code, s.name_ru)}
              sx={{
                display: 'flex', alignItems: 'center', gap: 1, py: 0.5, px: 1,
                cursor: 'pointer', borderRadius: 1,
                bgcolor: s.hs_code === currentCode ? '#e8f5e9' : 'transparent',
                '&:hover': { bgcolor: '#f5f5f5' },
              }}
            >
              <Typography variant="body2" fontWeight={700} fontFamily="monospace">{s.hs_code}</Typography>
              <Typography variant="caption" sx={{ flex: 1 }}>{s.name_ru}</Typography>
              <Chip label={`${Math.round(s.confidence * 100)}%`} size="small" color={confidenceColor(s.confidence)} />
            </Box>
          ))}
        </Paper>
      )}
    </Box>
  );
};

export default HSCodeSuggestions;
