import { useEffect, useState } from 'react';
import {
  Paper, Typography, List, ListItem, ListItemIcon, ListItemText,
  Chip, Box, CircularProgress, Alert,
} from '@mui/material';
import {
  VerifiedUser as ShieldIcon,
  Gavel as GavelIcon,
  Pets as PetsIcon,
  Park as EcoIcon,
  LocalHospital as HealthIcon,
  Lock as LockIcon,
  CheckCircleOutline as CheckIcon,
} from '@mui/icons-material';
import client from '../api/client';

interface HsRequirement {
  id: string;
  hs_code_prefix: string;
  requirement_type: string;
  document_name: string;
  issuing_authority: string | null;
  legal_basis: string | null;
  description: string | null;
}

interface RequirementsPanelProps {
  hsCode: string;
  description: string;
}

const REQUIREMENT_CONFIG: Record<string, { icon: React.ReactElement; color: string; label: string }> = {
  certificate: { icon: <ShieldIcon />, color: '#1976d2', label: 'Сертификат' },
  license: { icon: <GavelIcon />, color: '#ed6c02', label: 'Лицензия' },
  vetcontrol: { icon: <PetsIcon />, color: '#2e7d32', label: 'Ветконтроль' },
  phyto: { icon: <EcoIcon />, color: '#2e7d32', label: 'Фитоконтроль' },
  sanitary: { icon: <HealthIcon />, color: '#ed6c02', label: 'Санитарный' },
  permit: { icon: <LockIcon />, color: '#d32f2f', label: 'Разрешение' },
};

const RequirementsPanel: React.FC<RequirementsPanelProps> = ({ hsCode, description }) => {
  const [requirements, setRequirements] = useState<HsRequirement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hsCode || hsCode.replace(/\D/g, '').length < 4) {
      setRequirements([]);
      return;
    }

    const cleanCode = hsCode.replace(/\D/g, '');
    let cancelled = false;

    const fetchRequirements = async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await client.get('/classifiers/hs-requirements', {
          params: { hs_code: cleanCode },
        });
        if (!cancelled) {
          setRequirements(resp.data || []);
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e?.response?.data?.detail || 'Ошибка загрузки требований');
          setRequirements([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchRequirements();
    return () => { cancelled = true; };
  }, [hsCode]);

  // Don't render anything if hs_code is too short
  if (!hsCode || hsCode.replace(/\D/g, '').length < 4) {
    return null;
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1, ml: 1 }}>
        <CircularProgress size={16} />
        <Typography variant="caption" color="text.secondary">Проверка требований...</Typography>
      </Box>
    );
  }

  if (error) {
    return null; // Silent fail — don't block the UI
  }

  if (requirements.length === 0) {
    return (
      <Alert severity="success" icon={<CheckIcon />} sx={{ mt: 1 }} variant="outlined">
        Разрешительные документы не требуются
      </Alert>
    );
  }

  return (
    <Paper variant="outlined" sx={{ mt: 1, borderColor: 'warning.light', bgcolor: 'warning.50' }}>
      <Box sx={{ px: 2, pt: 1.5, pb: 0.5 }}>
        <Typography variant="caption" fontWeight={700} color="warning.dark">
          Требуются разрешительные документы ({requirements.length})
        </Typography>
      </Box>
      <List dense disablePadding>
        {requirements.map((req) => {
          const config = REQUIREMENT_CONFIG[req.requirement_type] || REQUIREMENT_CONFIG.certificate;
          return (
            <ListItem key={req.id} sx={{ py: 0.5, alignItems: 'flex-start' }}>
              <ListItemIcon sx={{ minWidth: 36, mt: 0.5, color: config.color }}>
                {config.icon}
              </ListItemIcon>
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                    <Typography variant="body2" fontWeight={600} sx={{ lineHeight: 1.3 }}>
                      {req.document_name}
                    </Typography>
                    <Chip
                      label={config.label}
                      size="small"
                      sx={{
                        height: 18,
                        fontSize: 10,
                        bgcolor: config.color,
                        color: '#fff',
                        fontWeight: 700,
                      }}
                    />
                  </Box>
                }
                secondary={
                  <Box component="span" sx={{ display: 'flex', flexDirection: 'column', gap: 0.2 }}>
                    {req.issuing_authority && (
                      <Typography variant="caption" color="text.secondary" component="span">
                        Орган: {req.issuing_authority}
                      </Typography>
                    )}
                    {req.legal_basis && (
                      <Typography variant="caption" color="text.secondary" component="span">
                        Основание: {req.legal_basis}
                      </Typography>
                    )}
                  </Box>
                }
              />
            </ListItem>
          );
        })}
      </List>
    </Paper>
  );
};

export default RequirementsPanel;
