import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Button,
  Container,
  Stepper,
  Step,
  StepLabel,
  StepButton,
  Paper,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Card,
  CardContent,
  IconButton,
  Chip,
  Checkbox,
  FormControlLabel,
  List,
  ListItem,
  Alert,
  LinearProgress,
  Tooltip,
  Breadcrumbs,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Divider,
} from '@mui/material';
import {
  ArrowBack,
  Save,
  AutoAwesome as AiIcon,
  Badge,
  People,
  Public,
  LocalShipping,
  Inventory,
  Payment,
  CheckCircle,
  CheckCircleOutline,
  RadioButtonUnchecked,
  FiberManualRecord,
} from '@mui/icons-material';
import dayjs from 'dayjs';
import {
  getDeclaration,
  updateDeclaration,
  changeStatus,
} from '../api/declarations';
import { classifyHS, HSSuggestion } from '../api/ai';
import { getItems, createItem, updateItem, deleteItem } from '../api/items';
import { getCountries, getCurrencies } from '../api/classifiers';
import StatusChip from '../components/StatusChip';
import DocumentUploadPanel from '../components/DocumentUploadPanel';
import { Declaration, DeclarationItem } from '../types';

const steps = [
  { label: 'Идентификация', icon: Badge },
  { label: 'Стороны', icon: People },
  { label: 'Страны', icon: Public },
  { label: 'Транспорт', icon: LocalShipping },
  { label: 'Товары', icon: Inventory },
  { label: 'Платежи', icon: Payment },
  { label: 'Завершение', icon: CheckCircle },
];

const DeclarationEditPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeStep, setActiveStep] = useState(0);
  const [saveTimeout, setSaveTimeout] = useState<NodeJS.Timeout | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<{ id: string; item_no: number } | null>(null);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const { data: declaration, isLoading } = useQuery({
    queryKey: ['declaration', id],
    queryFn: () => getDeclaration(id!),
    enabled: !!id,
  });

  const { data: items = [] } = useQuery({
    queryKey: ['declaration-items', id],
    queryFn: () => getItems(id!),
    enabled: !!id,
  });

  const { data: countries = [] } = useQuery({
    queryKey: ['countries'],
    queryFn: getCountries,
  });

  const { data: currencies = [] } = useQuery({
    queryKey: ['currencies'],
    queryFn: getCurrencies,
  });

  const { register, control, handleSubmit, watch, setValue, reset, formState } = useForm<Declaration>({
    defaultValues: declaration,
  });

  useEffect(() => {
    if (declaration) {
      reset(declaration);
      setFormKey(k => k + 1);
    }
  }, [declaration, reset]);

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Declaration> }) =>
      updateDeclaration(id, data),
    onSuccess: () => {
      setIsSaving(false);
      setLastSavedAt(new Date());
      setSnackbarOpen(true);
      queryClient.invalidateQueries({ queryKey: ['declaration', id] });
    },
    onError: () => {
      setIsSaving(false);
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      changeStatus(id, status as any),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['declaration', id] });
    },
  });

  const debouncedSave = useCallback(
    (data: Partial<Declaration>) => {
      if (saveTimeout) {
        clearTimeout(saveTimeout);
      }
      setIsSaving(true);
      const timeout = setTimeout(() => {
        if (id) {
          updateMutation.mutate({ id, data });
        }
      }, 2000);
      setSaveTimeout(timeout);
    },
    [id, updateMutation, saveTimeout]
  );

  useEffect(() => {
    const subscription = watch((data) => {
      debouncedSave(data as Partial<Declaration>);
    });
    return () => {
      subscription.unsubscribe();
      if (saveTimeout) {
        clearTimeout(saveTimeout);
      }
    };
  }, [watch, debouncedSave, saveTimeout]);

  const onSubmit = async (data: Declaration) => {
    if (id) {
      await updateMutation.mutateAsync({ id, data });
    }
  };

  const handleSave = () => {
    handleSubmit(onSubmit)();
  };

  const handleStatusChange = () => {
    if (id) {
      statusMutation.mutate({ id, status: 'checking_lvl1' });
    }
  };

  const handleDeleteItem = (itemId: string, itemNo: number) => {
    setItemToDelete({ id: itemId, item_no: itemNo });
    setDeleteDialogOpen(true);
  };

  const confirmDeleteItem = () => {
    if (id && itemToDelete) {
      deleteItem(id, itemToDelete.id).then(() => {
        queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
        setDeleteDialogOpen(false);
        setItemToDelete(null);
      });
    }
  };

  // Check step completion
  const getStepCompletion = useCallback((step: number): 'complete' | 'partial' | 'empty' => {
    if (!declaration) return 'empty';
    const formValues = watch();

    switch (step) {
      case 0: // Идентификация
        const hasIdFields = !!(formValues.type_code && formValues.number_internal);
        const hasCounts = !!(formValues.forms_count && formValues.specifications_count && formValues.total_items_count);
        if (hasIdFields && hasCounts) return 'complete';
        if (hasIdFields || hasCounts) return 'partial';
        return 'empty';

      case 1: // Стороны
        const hasParties = !!(formValues.sender_counterparty_id || formValues.receiver_counterparty_id || formValues.declarant_counterparty_id);
        const hasFinancial = !!(formValues.financial_counterparty_id && formValues.total_invoice_value && formValues.currency_code);
        if (hasParties && hasFinancial) return 'complete';
        if (hasParties || hasFinancial) return 'partial';
        return 'empty';

      case 2: // Страны
        const hasCountries = !!(formValues.country_dispatch_code || formValues.country_origin_code || formValues.country_destination_code);
        return hasCountries ? (formValues.country_dispatch_code && formValues.country_origin_code && formValues.country_destination_code ? 'complete' : 'partial') : 'empty';

      case 3: // Транспорт
        const hasTransport = !!(formValues.transport_at_border || formValues.transport_on_border || formValues.incoterms_code || formValues.exchange_rate);
        return hasTransport ? 'partial' : 'empty';

      case 4: // Товары
        return items.length > 0 ? (items.every(item => item.hs_code && item.commercial_name) ? 'complete' : 'partial') : 'empty';

      case 5: // Платежи
        return formValues.warehouse_name ? 'partial' : 'empty';

      case 6: // Завершение
        return formValues.place_and_date ? 'partial' : 'empty';

      default:
        return 'empty';
    }
  }, [declaration, watch, items]);

  const stepCompletion = useMemo(() => {
    return steps.map((_, idx) => getStepCompletion(idx));
  }, [getStepCompletion]);

  if (isLoading || !declaration) {
    return <div>Загрузка...</div>;
  }

  const renderStepContent = () => {
    switch (activeStep) {
      case 0:
        return (
          <Box>
            <Typography variant="h6" gutterBottom sx={{ mb: 3 }}>
              Идентификация декларации
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <FormControl fullWidth>
                  <InputLabel>Тип декларации</InputLabel>
                  <Select value={watch('type_code') || ''} onChange={(e) => setValue('type_code' as any, e.target.value)} label="Тип декларации">
                    <MenuItem value="IM40">IM40 - Импорт</MenuItem>
                    <MenuItem value="EX10">EX10 - Экспорт</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="Внутренний номер декларации для учёта в системе (графа 7)">
                  <TextField
                    {...register('number_internal')}
                    label="Внутренний номер"
                    placeholder="Например: COMP-2026-001"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12}>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Количественные показатели
                </Typography>
              </Grid>
              <Grid item xs={12} md={4}>
                <Tooltip title="Количество форм ДТ (графа 3)">
                  <TextField
                    {...register('forms_count', { valueAsNumber: true })}
                    label="Количество форм"
                    type="number"
                    placeholder="0"
                    inputProps={{ min: 0 }}
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={4}>
                <Tooltip title="Количество спецификаций (графа 4)">
                  <TextField
                    {...register('specifications_count', { valueAsNumber: true })}
                    label="Количество спецификаций"
                    type="number"
                    placeholder="0"
                    inputProps={{ min: 0 }}
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={4}>
                <Tooltip title="Общее количество товарных позиций (графа 5)">
                  <TextField
                    {...register('total_items_count', { valueAsNumber: true })}
                    label="Количество товаров"
                    type="number"
                    placeholder="0"
                    inputProps={{ min: 0 }}
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="Общее количество мест/упаковок (графа 6)">
                  <TextField
                    {...register('total_packages_count', { valueAsNumber: true })}
                    label="Количество мест"
                    type="number"
                    placeholder="0"
                    inputProps={{ min: 0 }}
                    fullWidth
                  />
                </Tooltip>
              </Grid>
            </Grid>
          </Box>
        );

      case 1:
        return (
          <Box>
            <Typography variant="h6" gutterBottom sx={{ mb: 3 }}>
              Стороны сделки
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Контрагенты
                </Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="UUID контрагента-отправителя (графа 2)">
                  <TextField
                    {...register('sender_counterparty_id')}
                    label="Отправитель (ID)"
                    placeholder="UUID контрагента-отправителя"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="UUID контрагента-получателя (графа 8)">
                  <TextField
                    {...register('receiver_counterparty_id')}
                    label="Получатель (ID)"
                    placeholder="UUID контрагента-получателя"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="UUID финансового контрагента (графа 9)">
                  <TextField
                    {...register('financial_counterparty_id')}
                    label="Финансовый контрагент (ID)"
                    placeholder="UUID финансового контрагента"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="UUID декларанта (графа 14)">
                  <TextField
                    {...register('declarant_counterparty_id')}
                    label="Декларант (ID)"
                    placeholder="UUID декларанта"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12}>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Финансовая информация
                </Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="Сумма счета-фактуры в валюте сделки (графа 22)">
                  <TextField
                    {...register('total_invoice_value', { valueAsNumber: true })}
                    label="Сумма счета"
                    type="number"
                    placeholder="0.00"
                    inputProps={{ min: 0, step: 0.01 }}
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={6}>
                <FormControl fullWidth>
                  <InputLabel>Валюта</InputLabel>
                  <Select value={watch('currency_code') || ''} onChange={(e) => setValue('currency_code' as any, e.target.value)} label="Валюта">
                    {currencies.map((curr) => (
                      <MenuItem key={curr.id} value={curr.code}>
                        {curr.code} - {curr.name_ru}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          </Box>
        );

      case 2:
        return (
          <Box>
            <Typography variant="h6" gutterBottom sx={{ mb: 3 }}>
              Страны
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <FormControl fullWidth>
                  <Tooltip title="Страна отправления товара (графа 15)">
                    <InputLabel>Страна отправления</InputLabel>
                  </Tooltip>
                  <Select value={watch('country_dispatch_code') || ''} onChange={(e) => setValue('country_dispatch_code' as any, e.target.value)} label="Страна отправления">
                    {countries.map((country) => (
                      <MenuItem key={country.id} value={country.code}>
                        {country.code} - {country.name_ru}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={4}>
                <FormControl fullWidth>
                  <Tooltip title="Страна происхождения товара (графа 16)">
                    <InputLabel>Страна происхождения</InputLabel>
                  </Tooltip>
                  <Select value={watch('country_origin_code') || ''} onChange={(e) => setValue('country_origin_code' as any, e.target.value)} label="Страна происхождения">
                    {countries.map((country) => (
                      <MenuItem key={country.id} value={country.code}>
                        {country.code} - {country.name_ru}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={4}>
                <FormControl fullWidth>
                  <Tooltip title="Страна назначения товара (графа 17)">
                    <InputLabel>Страна назначения</InputLabel>
                  </Tooltip>
                  <Select value={watch('country_destination_code') || ''} onChange={(e) => setValue('country_destination_code' as any, e.target.value)} label="Страна назначения">
                    {countries.map((country) => (
                      <MenuItem key={country.id} value={country.code}>
                        {country.code} - {country.name_ru}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          </Box>
        );

      case 3:
        return (
          <Box>
            <Typography variant="h6" gutterBottom sx={{ mb: 3 }}>
              Транспортное средство
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Транспорт на границе
                </Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="Транспортное средство на границе (графа 18)">
                  <TextField
                    {...register('transport_at_border')}
                    label="Транспорт на границе"
                    placeholder="Номер ТС, марка"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="Транспортное средство внутри страны (графа 21)">
                  <TextField
                    {...register('transport_on_border')}
                    label="Транспорт на границе (внутр.)"
                    placeholder="Номер ТС, марка"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="Информация о контейнерах (графа 19)">
                  <TextField
                    {...register('container_info')}
                    label="Информация о контейнере"
                    placeholder="Номер контейнера"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={6}>
                <FormControl fullWidth>
                  <Tooltip title="Условия поставки по Инкотермс (графа 20)">
                    <InputLabel>Инкотермс</InputLabel>
                  </Tooltip>
                  <Select value={watch('incoterms_code') || ''} onChange={(e) => setValue('incoterms_code' as any, e.target.value)} label="Инкотермс">
                    <MenuItem value="EXW">EXW</MenuItem>
                    <MenuItem value="FCA">FCA</MenuItem>
                    <MenuItem value="CPT">CPT</MenuItem>
                    <MenuItem value="CIP">CIP</MenuItem>
                    <MenuItem value="DAP">DAP</MenuItem>
                    <MenuItem value="DPU">DPU</MenuItem>
                    <MenuItem value="DDP">DDP</MenuItem>
                    <MenuItem value="FAS">FAS</MenuItem>
                    <MenuItem value="FOB">FOB</MenuItem>
                    <MenuItem value="CFR">CFR</MenuItem>
                    <MenuItem value="CIF">CIF</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12}>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Финансовая информация
                </Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="Курс валюты ЦБ РФ на дату подачи (графа 23)">
                  <TextField
                    {...register('exchange_rate', { valueAsNumber: true })}
                    label="Курс валюты"
                    type="number"
                    placeholder="Курс ЦБ РФ на дату подачи"
                    inputProps={{ min: 0, step: 0.000001 }}
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="Код характера сделки (графа 24): 01 - купля-продажа">
                  <TextField
                    {...register('deal_nature_code')}
                    label="Код характера сделки"
                    placeholder="01 - купля-продажа"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12}>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Типы транспорта
                </Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="Тип транспорта на границе (графа 25)">
                  <TextField
                    {...register('transport_type_border')}
                    label="Тип транспорта на границе"
                    placeholder="Код типа транспорта"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="Тип транспорта внутри страны (графа 26)">
                  <TextField
                    {...register('transport_type_inland')}
                    label="Тип транспорта внутри"
                    placeholder="Код типа транспорта"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12}>
                <Tooltip title="Место погрузки товара (графа 27)">
                  <TextField
                    {...register('loading_place')}
                    label="Место погрузки"
                    placeholder="Адрес места погрузки"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
            </Grid>
          </Box>
        );

      case 4:
        return (
          <Box>
            <Typography variant="h6" gutterBottom sx={{ mb: 3 }}>
              Товарные позиции
            </Typography>
            <Button
              variant="contained"
              onClick={() => {
                const newItem: Partial<DeclarationItem> = {
                  item_no: items.length + 1,
                  description: '',
                  commercial_name: '',
                };
                if (id) {
                  createItem(id, newItem).then(() => {
                    queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
                  });
                }
              }}
              sx={{ mb: 2 }}
            >
              Добавить позицию
            </Button>
            {items.map((item, index) => (
              <Card key={item.id} sx={{ mb: 2 }}>
                <CardContent>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={2}>
                      <TextField
                        label="№"
                        value={item.item_no}
                        size="small"
                        fullWidth
                        disabled
                      />
                    </Grid>
                    <Grid item xs={12} md={4}>
                      <TextField
                        label="Код ТН ВЭД"
                        defaultValue={item.hs_code}
                        size="small"
                        fullWidth
                        placeholder="10-значный код ТН ВЭД"
                        onBlur={(e) => {
                          if (id && item.id) {
                            updateItem(id, item.id, { hs_code: e.target.value });
                            queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
                          }
                        }}
                        InputProps={{
                          endAdornment: item.hs_code ? (
                            <Tooltip title="Код заполнен">
                              <Chip label="OK" size="small" color="success" sx={{ height: 20, fontSize: 10 }} />
                            </Tooltip>
                          ) : null,
                        }}
                      />
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <TextField
                        label="Наименование"
                        defaultValue={item.commercial_name}
                        size="small"
                        fullWidth
                        placeholder="Коммерческое наименование товара"
                        onBlur={(e) => {
                          if (id && item.id) {
                            updateItem(id, item.id, { commercial_name: e.target.value });
                            queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
                          }
                        }}
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <TextField
                        label="Описание товара (введите для AI-подсказки кода ТН ВЭД)"
                        defaultValue={item.description}
                        size="small"
                        fullWidth
                        multiline
                        rows={2}
                        placeholder="Подробное описание товара для определения кода ТН ВЭД"
                        onBlur={async (e) => {
                          const desc = e.target.value;
                          if (id && item.id) {
                            updateItem(id, item.id, { description: desc });
                            queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
                          }
                          // AI подсказка ТН ВЭД
                          if (desc && desc.length > 3) {
                            try {
                              const suggestions = await classifyHS(desc);
                              if (suggestions.length > 0) {
                                const el = document.getElementById(`hs-hints-${item.id}`);
                                if (el) {
                                  el.innerHTML = suggestions.map((s: HSSuggestion) => {
                                    const color = s.confidence > 0.8 ? '#2e7d32' : s.confidence > 0.6 ? '#ed6c02' : '#d32f2f';
                                    return `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer" onclick="document.getElementById('hs-apply-${item.id}-${s.hs_code}')?.click()">
                                      <span style="font-weight:600;color:${color}">${s.hs_code}</span>
                                      <span style="font-size:12px;color:#546e7a">${s.name_ru}</span>
                                      <span style="font-size:11px;color:${color};margin-left:auto">${Math.round(s.confidence * 100)}%</span>
                                    </div>`;
                                  }).join('');
                                  el.style.display = 'block';
                                }
                              }
                            } catch (err) {
                              // AI service might be unavailable
                            }
                          }
                        }}
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <Box id={`hs-hints-${item.id}`} sx={{ display: 'none', bgcolor: '#f5f7fa', borderRadius: 1, p: 1.5, mb: 1 }}>
                      </Box>
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <TextField
                        label="Брутто (кг)"
                        type="number"
                        defaultValue={item.gross_weight || ''}
                        size="small"
                        fullWidth
                        placeholder="0"
                        inputProps={{ min: 0, step: 0.001 }}
                        onBlur={(e) => {
                          if (id && item.id) {
                            updateItem(id, item.id, { gross_weight: parseFloat(e.target.value) || 0 });
                            queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
                          }
                        }}
                      />
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <TextField
                        label="Нетто (кг)"
                        type="number"
                        defaultValue={item.net_weight || ''}
                        size="small"
                        fullWidth
                        placeholder="0"
                        inputProps={{ min: 0, step: 0.001 }}
                        onBlur={(e) => {
                          if (id && item.id) {
                            updateItem(id, item.id, { net_weight: parseFloat(e.target.value) || 0 });
                            queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
                          }
                        }}
                      />
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <TextField
                        label="Цена за единицу"
                        type="number"
                        defaultValue={item.unit_price || ''}
                        size="small"
                        fullWidth
                        placeholder="0.00"
                        inputProps={{ min: 0, step: 0.01 }}
                        onBlur={(e) => {
                          if (id && item.id) {
                            updateItem(id, item.id, { unit_price: parseFloat(e.target.value) || 0 });
                            queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
                          }
                        }}
                      />
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <IconButton
                        color="error"
                        onClick={() => handleDeleteItem(item.id, item.item_no)}
                      >
                        Удалить
                      </IconButton>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            ))}
          </Box>
        );

      case 5:
        return (
          <Box>
            <Typography variant="h6" gutterBottom sx={{ mb: 3 }}>
              Платежи и склад
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <Typography variant="body1" color="text.secondary">
                  Расчёт платежей будет доступен после интеграции
                </Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Tooltip title="Склад временного хранения (графа 49)">
                  <TextField
                    {...register('warehouse_name')}
                    label="СВХ (Склад временного хранения)"
                    placeholder="Наименование СВХ"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
            </Grid>
          </Box>
        );

      case 6:
        return (
          <Box>
            <Typography variant="h6" gutterBottom sx={{ mb: 3 }}>
              Завершение
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <Tooltip title="Место и дата составления декларации (графа 54)">
                  <TextField
                    {...register('place_and_date')}
                    label="Место и дата"
                    placeholder="Например: Москва, 06.02.2026"
                    fullWidth
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={12}>
                <Divider sx={{ my: 2 }} />
                <Typography variant="h6" gutterBottom>
                  Чек-лист
                </Typography>
                <List>
                  <ListItem>
                    <FormControlLabel control={<Checkbox defaultChecked />} label="Все поля заполнены" />
                  </ListItem>
                  <ListItem>
                    <FormControlLabel control={<Checkbox defaultChecked />} label="Документы прикреплены" />
                  </ListItem>
                  <ListItem>
                    <FormControlLabel control={<Checkbox />} label="Проверка завершена" />
                  </ListItem>
                </List>
              </Grid>
            </Grid>
          </Box>
        );

      default:
        return null;
    }
  };

  const progress = ((activeStep + 1) / steps.length) * 100;

  return (
    <Box>
      <AppBar position="static">
        <Toolbar>
          <IconButton edge="start" color="inherit" onClick={() => navigate('/declarations')}>
            <ArrowBack />
          </IconButton>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, ml: 2 }}>
            {declaration.number_internal || `Декларация ${declaration.id.slice(0, 8)}`}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {isSaving ? (
              <Typography variant="body2" color="inherit">
                Сохранение...
              </Typography>
            ) : lastSavedAt ? (
              <Typography variant="body2" color="inherit">
                Сохранено в {dayjs(lastSavedAt).format('HH:mm')}
              </Typography>
            ) : null}
            <StatusChip status={declaration.status} />
            <Button
              color="inherit"
              startIcon={<Save />}
              onClick={handleSave}
            >
              Сохранить
            </Button>
            <Button
              color="inherit"
              onClick={handleStatusChange}
              disabled={statusMutation.isPending}
            >
              На проверку
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ mt: 2, mb: 4 }}>
        {/* Breadcrumbs */}
        <Breadcrumbs sx={{ mb: 2 }}>
          <Link to="/declarations" style={{ textDecoration: 'none', color: 'inherit' }}>
            Декларации
          </Link>
          <Typography color="text.primary">
            {declaration.number_internal || `Декларация ${declaration.id.slice(0, 8)}`}
          </Typography>
          <Typography color="text.primary">
            {steps[activeStep].label}
          </Typography>
        </Breadcrumbs>

        {/* Progress indicator */}
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Шаг {activeStep + 1} из {steps.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {Math.round(progress)}%
            </Typography>
          </Box>
          <LinearProgress variant="determinate" value={progress} sx={{ height: 8, borderRadius: 1 }} />
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={12} md={3}>
            <Paper sx={{ p: 2 }}>
              <Stepper activeStep={activeStep} orientation="vertical" nonLinear>
                {steps.map((step, index) => {
                  const Icon = step.icon;
                  const completion = stepCompletion[index];
                  const isActive = activeStep === index;
                  return (
                    <Step key={step.label} completed={completion === 'complete'}>
                      <StepButton onClick={() => setActiveStep(index)}>
                        <StepLabel
                          StepIconComponent={({ active, completed }) => (
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                                p: 0.5,
                                borderRadius: 1,
                                bgcolor: isActive ? 'action.selected' : 'transparent',
                              }}
                            >
                              <Icon
                                sx={{
                                  fontSize: 20,
                                  color: isActive ? 'primary.main' : 'text.secondary',
                                }}
                              />
                              {completion === 'complete' ? (
                                <CheckCircleOutline sx={{ color: 'success.main', fontSize: 18 }} />
                              ) : completion === 'partial' ? (
                                <FiberManualRecord sx={{ color: 'warning.main', fontSize: 12 }} />
                              ) : (
                                <RadioButtonUnchecked sx={{ color: 'text.disabled', fontSize: 18 }} />
                              )}
                            </Box>
                          )}
                        >
                          {step.label}
                        </StepLabel>
                      </StepButton>
                    </Step>
                  );
                })}
              </Stepper>
            </Paper>
          </Grid>
          <Grid item xs={12} md={9}>
            {/* Document Upload Panel */}
            <DocumentUploadPanel
              declarationId={id || ''}
              onParsedData={async (data, sourceType) => {
                if (!id) return;
                const updates: any = {};
                let filledFields: string[] = [];

                if (sourceType === 'invoice') {
                  // 1. Номер инвойса → графа 7
                  if (data.invoice_number) {
                    updates.number_internal = data.invoice_number;
                    filledFields.push('Номер: ' + data.invoice_number);
                  }
                  // 2. Валюта → графа 22
                  if (data.currency) {
                    updates.currency_code = data.currency;
                    filledFields.push('Валюта: ' + data.currency);
                  }
                  // 3. Сумма → графа 22
                  if (data.total_amount != null && data.total_amount > 0) {
                    updates.total_invoice_value = data.total_amount;
                    filledFields.push('Сумма: ' + data.total_amount);
                  }
                  // 4. Страна происхождения (из текста "Страна происхождения Китай")
                  if (data.country_origin) {
                    updates.country_origin_code = data.country_origin;
                    updates.country_dispatch_code = data.country_origin; // обычно совпадает
                    filledFields.push('Страна происхождения: ' + data.country_origin);
                  } else if (data.seller?.country_code) {
                    updates.country_dispatch_code = data.seller.country_code;
                    updates.country_origin_code = data.seller.country_code;
                    filledFields.push('Страна (из адреса): ' + data.seller.country_code);
                  }
                  // 5. Страна назначения
                  if (data.country_destination) {
                    updates.country_destination_code = data.country_destination;
                    filledFields.push('Страна назначения: ' + data.country_destination);
                  }
                  // 6. Incoterms
                  if (data.incoterms) {
                    updates.incoterms_code = data.incoterms;
                    filledFields.push('Incoterms: ' + data.incoterms);
                  }
                  // 7. Количество товаров → графа 5
                  if (data.items?.length > 0) {
                    updates.total_items_count = data.items.length;
                    filledFields.push('Товаров: ' + data.items.length);
                  }
                  // 8. Общее кол-во штук из items → для информации
                  const totalQty = data.items?.reduce((sum: number, it: any) => sum + (it.quantity || 0), 0);
                  if (totalQty > 0) {
                    filledFields.push('Общее кол-во: ' + totalQty);
                  }

                  // Сохраняем декларацию
                  if (Object.keys(updates).length > 0) {
                    try {
                      await updateDeclaration(id, updates);
                    } catch (e) {
                      console.error('Update declaration error:', e);
                    }
                  }

                  // 6. Товарные позиции + автоклассификация ТН ВЭД
                  if (data.items && data.items.length > 0) {
                    for (const item of data.items) {
                      try {
                        // Автоклассификация ТН ВЭД по описанию
                        let hsCode = '';
                        if (item.description_raw) {
                          try {
                            const hsSuggestions = await classifyHS(item.description_raw, data.country_origin, item.unit_price);
                            if (hsSuggestions.length > 0 && hsSuggestions[0].confidence >= 0.5) {
                              hsCode = hsSuggestions[0].hs_code;
                              // Дополнить до 10 знаков нулями если код короче
                              while (hsCode.length < 10) hsCode = hsCode + '0';
                              filledFields.push('ТН ВЭД: ' + hsCode + ' (' + Math.round(hsSuggestions[0].confidence * 100) + '% AI)');
                            }
                          } catch (e) {
                            console.error('HS classify error:', e);
                          }
                        }

                        await createItem(id, {
                          item_no: item.line_no || 1,
                          commercial_name: (item.description_raw || '').slice(0, 100),
                          description: item.description_raw || '',
                          hs_code: hsCode || undefined,
                          unit_price: item.unit_price && item.unit_price > 0 ? item.unit_price : undefined,
                          additional_unit_qty: item.quantity && item.quantity > 0 ? item.quantity : undefined,
                          additional_unit: item.unit || 'pcs',
                          gross_weight: item.gross_weight || undefined,
                          net_weight: item.net_weight || undefined,
                          customs_value_rub: item.line_total && item.line_total > 0 ? item.line_total : undefined,
                        });
                        filledFields.push('Товар: ' + (item.description_raw || '').slice(0, 30));
                      } catch (e) {
                        console.error('Create item error:', e);
                      }
                    }
                    // Обновить общее количество товаров
                    const totalQty = data.items.reduce((sum: number, it: any) => sum + (it.quantity || 0), 0);
                    if (totalQty > 0) {
                      updates.total_items_count = data.items.length;
                      // Если есть только 1 позиция — записать количество
                      try {
                        await updateDeclaration(id, { total_items_count: data.items.length });
                      } catch (e) {}
                    }
                  }
                  // 7. Сумма — пробуем из items если total_amount не парсился
                  if (!data.total_amount && data.items?.length > 0) {
                    const calcTotal = data.items.reduce((sum: number, it: any) => sum + (it.line_total || 0), 0);
                    if (calcTotal > 0) {
                      try {
                        await updateDeclaration(id, { total_invoice_value: calcTotal });
                        filledFields.push('Сумма (расчёт): ' + calcTotal);
                      } catch (e) {}
                    }
                  }

                } else if (sourceType === 'packing_list') {
                  // Упаковочный лист → графы 6, 35, 38
                  if (data.total_packages != null && data.total_packages > 0) {
                    updates.total_packages_count = data.total_packages;
                    filledFields.push('Мест: ' + data.total_packages);
                  }
                  if (data.total_gross_weight != null && data.total_gross_weight > 0) {
                    updates.total_gross_weight = data.total_gross_weight;
                    filledFields.push('Брутто: ' + data.total_gross_weight + ' кг');
                  }
                  if (data.total_net_weight != null && data.total_net_weight > 0) {
                    updates.total_net_weight = data.total_net_weight;
                    filledFields.push('Нетто: ' + data.total_net_weight + ' кг');
                  }
                  if (Object.keys(updates).length > 0) {
                    try {
                      await updateDeclaration(id, updates);
                    } catch (e) {
                      console.error('Update declaration error:', e);
                    }
                  }
                }

                // Перезагрузить данные формы
                if (filledFields.length > 0) {
                  console.log('AI заполнил:', filledFields.join(', '));
                  // Подождать чтобы БД обновилась
                  await new Promise(r => setTimeout(r, 300));
                  // Получить свежие данные
                  try {
                    const fresh = await getDeclaration(id!);
                    if (fresh) {
                      reset(fresh);
                      setFormKey(k => k + 1); // Force re-render form
                      console.log('Форма обновлена:', fresh.number_internal, fresh.currency_code, fresh.country_dispatch_code);
                    }
                  } catch (e) {
                    console.error('Refetch error:', e);
                  }
                  await queryClient.invalidateQueries({ queryKey: ['declaration', id] });
                  await queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
                  setSnackbarOpen(true);
                  setLastSavedAt(new Date());
                }
              }}
            />
            <Paper sx={{ p: 3 }}>
              <form key={formKey} onSubmit={handleSubmit(onSubmit)}>{renderStepContent()}</form>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
                <Button
                  disabled={activeStep === 0}
                  onClick={() => setActiveStep(activeStep - 1)}
                >
                  Назад
                </Button>
                <Button
                  variant="contained"
                  onClick={() => {
                    if (activeStep === steps.length - 1) {
                      handleSave();
                    } else {
                      setActiveStep(activeStep + 1);
                    }
                  }}
                >
                  {activeStep === steps.length - 1 ? 'Завершить' : 'Далее'}
                </Button>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Container>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
      >
        <DialogTitle>Подтверждение удаления</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Вы уверены, что хотите удалить позицию №{itemToDelete?.item_no}? Это действие нельзя отменить.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Отмена</Button>
          <Button onClick={confirmDeleteItem} color="error" variant="contained">
            Удалить
          </Button>
        </DialogActions>
      </Dialog>

      {/* Save confirmation snackbar */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={3000}
        onClose={() => setSnackbarOpen(false)}
        message="Изменения сохранены"
      />
    </Box>
  );
};

export default DeclarationEditPage;
