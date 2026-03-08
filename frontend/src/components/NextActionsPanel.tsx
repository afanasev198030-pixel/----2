import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button, Chip, Paper, Typography } from '@mui/material';
import type { AlertColor } from '@mui/material';
import { getPreSendCheck } from '../api/declarations';
import { Declaration, DeclarationItem, PreSendCheck } from '../types';

interface ActionCard {
  key: string;
  severity: AlertColor;
  title: string;
  description: string;
  buttonLabel?: string;
  onClick?: () => void;
}

interface NextActionsPanelProps {
  declaration: Declaration;
  items: DeclarationItem[];
  documentsCount: number;
  onGoToUpload: () => void;
  onGoToReview: () => void;
  onOpenDocuments?: () => void;
}

const hasCheckCode = (checks: PreSendCheck[], codes: string[]): boolean => (
  checks.some((check) => codes.includes(check.code))
);

export default function NextActionsPanel({
  declaration,
  items,
  documentsCount,
  onGoToUpload,
  onGoToReview,
  onOpenDocuments,
}: NextActionsPanelProps) {
  const { data: preSend, isLoading } = useQuery({
    queryKey: ['pre-send-check', declaration.id],
    queryFn: () => getPreSendCheck(declaration.id),
    enabled: Boolean(declaration.id),
    refetchOnWindowFocus: false,
  });

  const blockingChecks = preSend?.checks.filter((check) => check.blocking) || [];
  const warningChecks = preSend?.checks.filter((check) => !check.blocking) || [];

  const actions = useMemo<ActionCard[]>(() => {
    const nextActions: ActionCard[] = [];
    const push = (action: ActionCard) => {
      if (!nextActions.some((existing) => existing.key === action.key)) {
        nextActions.push(action);
      }
    };

    const hasDocumentGap = documentsCount === 0 || hasCheckCode(blockingChecks, [
      'NO_DOCUMENTS',
      'MISSING_INVOICE_DOCUMENT',
      'MISSING_CONTRACT_DOCUMENT',
      'MISSING_TRANSPORT_DOCUMENT',
    ]);

    if (hasDocumentGap) {
      push({
        key: 'documents',
        severity: 'error',
        title: 'Соберите полный пакет документов',
        description: documentsCount === 0
          ? 'Сейчас у кейса нет ни одного документа. Без этого AI и pre-send не дадут надёжный результат.'
          : 'В сохранённой версии кейса не хватает обязательных документов для отправки.',
        buttonLabel: 'Загрузить',
        onClick: onGoToUpload,
      });
    }

    const hasCoreDataGap = blockingChecks.some((check) => (
      check.code === 'MISSING_REQUIRED_FIELD'
      || check.code === 'MISSING_SENDER'
      || check.code === 'MISSING_RECEIVER'
    ));

    if (hasCoreDataGap) {
      push({
        key: 'core-fields',
        severity: 'error',
        title: 'Заполните обязательные поля декларации',
        description: 'Не хватает базовых реквизитов сделки: стран, контрагентов, валюты или суммы.',
        buttonLabel: 'Проверить форму',
        onClick: onGoToReview,
      });
    }

    const hasItemGap = hasCheckCode(blockingChecks, ['NO_ITEMS', 'ITEMS_WITHOUT_HS']);
    if (hasItemGap || items.some((item) => !(item.hs_code || '').trim())) {
      push({
        key: 'items',
        severity: 'error',
        title: 'Доведите товарные позиции до отправки',
        description: 'У части товаров отсутствуют позиции или коды ТН ВЭД. Это критично для дальнейшего workflow.',
        buttonLabel: 'Проверить товары',
        onClick: onGoToReview,
      });
    }

    const hasAiOrParsingBlockers = hasCheckCode(blockingChecks, ['BLOCKING_ISSUES', 'AI_BLOCKING_ISSUES']);
    if (hasAiOrParsingBlockers) {
      push({
        key: 'ai-blockers',
        severity: 'warning',
        title: 'Разберите блокирующие AI-проблемы',
        description: 'Есть нерешённые проблемы парсинга или explainability, которые сервер считает блокирующими.',
        buttonLabel: 'Открыть проверку',
        onClick: onGoToReview,
      });
    }

    const hasReconciliationWarning = warningChecks.some((check) => (
      check.code.includes('MISMATCH')
      || check.code === 'HS_HISTORY_DRIFT'
      || check.code === 'TRANSPORT_DOC_NOT_APPLIED'
    ));

    if (hasReconciliationWarning) {
      push({
        key: 'reconciliation',
        severity: 'warning',
        title: 'Сверьте декларацию с документами',
        description: 'Есть расхождения по суммам, валюте, весам, местам или по истории кодов ТН ВЭД.',
        buttonLabel: documentsCount > 0 && onOpenDocuments ? 'Открыть документы' : 'Проверить',
        onClick: documentsCount > 0 && onOpenDocuments ? onOpenDocuments : onGoToReview,
      });
    }

    if ((preSend?.passed ?? false) && declaration.status === 'draft') {
      push({
        key: 'ready',
        severity: 'success',
        title: 'Кейс готов к следующему этапу',
        description: 'По сохранённой версии блокирующих проблем нет. Можно переходить к финальной проверке и отправке.',
        buttonLabel: 'Проверить финально',
        onClick: onGoToReview,
      });
    }

    if (nextActions.length === 0) {
      push({
        key: 'stable',
        severity: 'info',
        title: 'Кейс выглядит стабильно',
        description: 'Сейчас нет явных критичных действий. Проверьте историю и статус перед следующим переходом.',
      });
    }

    return nextActions.slice(0, 4);
  }, [blockingChecks, declaration.status, documentsCount, items, onGoToReview, onGoToUpload, onOpenDocuments, preSend?.passed, warningChecks]);

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 1.5 }}>
        <Typography variant="subtitle2" fontWeight={700}>Что делать дальше</Typography>
        <Chip
          label={preSend?.passed ? 'Готово к следующему шагу' : 'Требует действий'}
          size="small"
          color={preSend?.passed ? 'success' : 'warning'}
        />
      </Box>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 1.5 }}>
        <Chip label={`Документы: ${documentsCount}`} size="small" variant="outlined" />
        <Chip label={`Позиции: ${items.length}`} size="small" variant="outlined" />
        <Chip label={`Блокеры: ${blockingChecks.length}`} size="small" color={blockingChecks.length > 0 ? 'error' : 'default'} />
        <Chip label={`Предупреждения: ${warningChecks.length}`} size="small" color={warningChecks.length > 0 ? 'warning' : 'default'} />
      </Box>

      {isLoading && (
        <Typography variant="caption" color="text.secondary">
          Анализирую сохранённую версию кейса...
        </Typography>
      )}

      {!isLoading && actions.map((action) => (
        <Alert
          key={action.key}
          severity={action.severity}
          sx={{ mb: 1, '&:last-child': { mb: 0 } }}
          action={action.onClick && action.buttonLabel ? (
            <Button color="inherit" size="small" onClick={action.onClick}>
              {action.buttonLabel}
            </Button>
          ) : undefined}
        >
          <Typography variant="body2" fontWeight={700}>
            {action.title}
          </Typography>
          <Typography variant="caption" display="block">
            {action.description}
          </Typography>
        </Alert>
      ))}
    </Paper>
  );
}
