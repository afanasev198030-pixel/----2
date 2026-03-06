import { Tooltip, Typography, Box } from '@mui/material';
import { FieldEvidence } from '../types';

/**
 * Маппинг ключей evidence_map (от AI-сервиса) → поля формы декларации.
 * AI использует короткие имена ("currency"), а модель — полные ("currency_code").
 */
const EVIDENCE_TO_FORM: Record<string, string> = {
  currency: 'currency_code',
  total_amount: 'total_invoice_value',
  incoterms: 'incoterms_code',
  country_origin: 'country_origin_name',
  country_destination: 'country_destination_code',
  country_dispatch: 'country_dispatch_code',
  transport_type: 'transport_type_border',
  transport_id: 'transport_on_border_id',
  trading_partner_country: 'trading_country_code',
  container: 'container_info',
  seller: 'sender_counterparty_id',
  buyer: 'receiver_counterparty_id',
  total_packages: 'total_packages_count',
};

const FORM_TO_EVIDENCE: Record<string, string> = Object.fromEntries(
  Object.entries(EVIDENCE_TO_FORM).map(([k, v]) => [v, k]),
);

const SOURCE_LABELS: Record<string, string> = {
  invoice: 'Инвойс',
  contract: 'Контракт',
  packing_list: 'Упак. лист',
  transport_doc: 'Трансп. документ',
  awb: 'AWB',
  heuristic: 'Эвристика',
  default: 'По умолчанию',
  rules_llm: 'Правила ДТ (AI)',
  aggregated_items: 'Из позиций',
  history: 'История компании',
};

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.85) return '#2e7d32';
  if (confidence >= 0.6) return '#ed6c02';
  return '#d32f2f';
}

function getConfidenceBgColor(confidence: number): string {
  if (confidence >= 0.85) return '#e8f5e9';
  if (confidence >= 0.6) return '#fff3e0';
  return '#ffebee';
}

interface ConfidenceBadgeProps {
  evidenceMap?: Record<string, FieldEvidence>;
  fieldName: string;
}

export function getFieldEvidence(
  evidenceMap: Record<string, FieldEvidence> | undefined,
  fieldName: string,
): FieldEvidence | undefined {
  if (!evidenceMap) return undefined;
  if (evidenceMap[fieldName]) return evidenceMap[fieldName];
  const altKey = FORM_TO_EVIDENCE[fieldName];
  if (altKey && evidenceMap[altKey]) return evidenceMap[altKey];
  return undefined;
}

const ConfidenceBadge = ({ evidenceMap, fieldName }: ConfidenceBadgeProps) => {
  const evidence = getFieldEvidence(evidenceMap, fieldName);
  if (!evidence || evidence.confidence == null) return null;

  const pct = Math.round(evidence.confidence * 100);
  const color = getConfidenceColor(evidence.confidence);
  const bg = getConfidenceBgColor(evidence.confidence);
  const sourceLabel = SOURCE_LABELS[evidence.source || ''] || evidence.source || '—';

  return (
    <Tooltip
      arrow
      title={
        <Box sx={{ fontSize: 12 }}>
          <div><b>Уверенность AI:</b> {pct}%</div>
          <div><b>Источник:</b> {sourceLabel}</div>
          {evidence.note && <div><b>Примечание:</b> {evidence.note}</div>}
          {evidence.value_preview && (
            <div style={{ marginTop: 4, opacity: 0.8 }}>
              <b>Извлечённое значение:</b> {evidence.value_preview}
            </div>
          )}
        </Box>
      }
    >
      <Typography
        component="span"
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          fontSize: 10,
          fontWeight: 700,
          color,
          bgcolor: bg,
          borderRadius: '4px',
          px: 0.5,
          ml: 0.5,
          lineHeight: 1.6,
          cursor: 'help',
          userSelect: 'none',
          verticalAlign: 'middle',
        }}
      >
        {pct}%
      </Typography>
    </Tooltip>
  );
};

export default ConfidenceBadge;
