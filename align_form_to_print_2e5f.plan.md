# Plan: Align Editable Declaration Form with Printed Form Structure

**File:** [`frontend/src/pages/DeclarationFormPage.tsx`](frontend/src/pages/DeclarationFormPage.tsx)

**Reference:** [`frontend/src/pages/DeclarationViewPage.tsx`](frontend/src/pages/DeclarationViewPage.tsx) (printed form)

## Problem

### A. Data display bugs (critical)

Counterparty fields (2, 8, 9) show **raw UUIDs** instead of human-readable names. Field 14 shows only INN/KPP numbers without the declarant name. Source labels are incomplete.

- **Field 2** (`sender_counterparty_id`): Shows `285820ad-443b-...` instead of company name + country + address
- **Field 8** (`receiver_counterparty_id`): Shows `871a724b-82b9-...` instead of company name
- **Field 9** (`financial_counterparty_id`): Shows `871a724b-82b9-...` instead of company name
- **Field 14** (`declarant_inn_kpp`): Only shows INN/KPP + OGRN, missing declarant company name + address + phone
- **Source labels**: Missing translations for `conformity_declaration`, `sanitary`, `veterinary`, `phytosanitary` and other doc types — they display raw English strings under field values

**Root cause:** `getFieldValue` default branch returns `f(d[field])` — the raw DB value. For `_counterparty_id` fields this is a foreign key UUID. The component never loads counterparty objects from the API. `DeclarationViewPage` solves this correctly via `client.get('/counterparties/{id}')`.

### B. Form structure mismatches

The current editable form uses a flat CSS Grid (12 columns x 25 rows) with 56 cells in a single `CELLS` array. This doesn't match the printed form's structure:

- Item blocks (31-46): Flat grid cells for `items[0]` only vs. nested flex layout per item, all items shown
- Field 47 (payments): Plain text "Пошлина: X | НДС: Y" vs. editable table with Вид/Основа/Ставка/Сумма/СП
- Field 49 (warehouse): Missing
- Section C: Missing
- Fields 51-53: Missing
- DT2 additional sheets: Missing (groups of 3 items)
- Row proportions: 12-col grid approximation vs. exact percentage widths

## Architecture Change

Replace the single CSS Grid with a sectioned layout:

```
DeclarationFormPage
  |-- AppLayout (header + breadcrumbs)
  |-- DeclHeader (toolbar)
  |-- SummaryStrip (metrics)
  |-- Main area (flex row)
  |     |-- Form scroll area
  |     |     |-- Form card (white, rounded)
  |     |     |     |-- Title bar "ДЕКЛАРАЦИЯ НА ТОВАРЫ"
  |     |     |     |-- HeaderRows (fields 1-30) — flex rows
  |     |     |     |-- EditableItemBlock (item 0, fields 31-46)
  |     |     |     |-- PaymentSection (field 47 table + 48 + 49 + B)
  |     |     |     |-- SectionC
  |     |     |     |-- TransitRow (fields 51, 52, 53)
  |     |     |     |-- FooterRow (D + 54)
  |     |     |     |-- StatusBar
  |     |     |
  |     |     |-- [For each DT2 sheet] Additional sheet card
  |     |     |     |-- DT2 header (type, sender, receiver, forms)
  |     |     |     |-- EditableItemBlock x 3 (or fewer)
  |     |     |     |-- PaymentSection (per-sheet)
  |     |
  |     |-- SourceDrawer (right sidebar, unchanged)
  |
  |-- BottomBar (unchanged)
```

## Step-by-step Plan

### Step 0: Fix counterparty data display and source labels (CRITICAL)

**0a. Load counterparty data.**

Add React Query calls for each counterparty ID, like `DeclarationViewPage` does:

```tsx
import { getCounterparty, Counterparty } from '../api/counterparties';

// Inside DeclarationFormPage component:
const { data: sender } = useQuery({
  queryKey: ['counterparty', decl?.sender_counterparty_id],
  queryFn: () => getCounterparty(decl!.sender_counterparty_id!),
  enabled: !!decl?.sender_counterparty_id,
});
const { data: receiver } = useQuery({ ... });
const { data: declarantCp } = useQuery({ ... decl?.declarant_counterparty_id ... });
const { data: financial } = useQuery({ ... decl?.financial_counterparty_id ... });
```

**0b. Update `getFieldValue` to format counterparty fields.**

Add a `counterparties` parameter and handle `_counterparty_id` fields:

```tsx
const cpLine = (cp?: Counterparty) =>
  cp ? `${cp.name || ''} ${cp.country_code || ''} ${cp.address || ''}`.trim() : '';

// In getFieldValue switch:
case 'sender_counterparty_id': return cpLine(cps.sender);
case 'receiver_counterparty_id': return cpLine(cps.receiver);
case 'financial_counterparty_id': return cpLine(cps.financial);
case 'declarant_inn_kpp': {
  const name = cpLine(cps.declarant) || cpLine(cps.receiver);
  const ids = `${f(d.declarant_inn_kpp)} ${f(d.declarant_ogrn)}`.trim();
  const phone = f(d.declarant_phone);
  return [name, ids, phone].filter(Boolean).join('\n');
}
```

**0c. Add missing source labels to `SOURCE_LABELS`.**

```tsx
const SOURCE_LABELS: Record<string, string> = {
  // ... existing entries ...
  conformity_declaration: 'Декларация соответствия',
  sanitary: 'Санитарный серт.',
  veterinary: 'Ветеринарный серт.',
  phytosanitary: 'Фитосанитарный серт.',
  certificate_origin: 'Сертификат происхождения',
  tech_description: 'Тех. описание',
  specification: 'Спецификация',
  application_statement: 'Заявление',
  license: 'Лицензия',
  permit: 'Разрешение',
};
```

### Step 1: Refactor `FormCell` to support flex layout

Modify `FormCell` to accept an optional `sxOverride` prop. When inside a flex container, the parent controls sizing via `width`. Remove the hardcoded `gridColumn`/`gridRow` from `FormCell`'s own sx — instead, apply them conditionally only when `cell.col` and `cell.row` are present.

```tsx
// FormCell sx changes:
sx={{
  // Only apply grid positioning if col/row defined
  ...(cell.col && cell.row ? { gridColumn: cell.col, gridRow: cell.row } : {}),
  // Allow parent override for width/height
  ...sxOverride,
  // ... rest of styles (border, hover, etc.)
}}
```

### Step 2: Split `CELLS` into `HEADER_CELLS` (fields 1-30)

Remove fields 31-54 from the `CELLS` array. Keep only fields 1-30 (the ones that appear on all sheets and aren't per-item). These will still render in a CSS grid, but with corrected proportions.

Adjust the remaining `HEADER_CELLS` proportions to match DeclarationViewPage:
- Row 1: type_code (27%) + reg_number (58%) + A (15%) — matches `G w="27%"` + title
- Row 2-3: sender (50%), forms/specs (25%), items/packages/ref (25%)
- Row 4: receiver (50%), financial (25%), empty (25%)
- Row 5: hidden(50%) + field 10 (12%) + 11 (13%) + 12 (18%) + 13 (7%)
- Row 6: declarant (50%), field 15 (14%), 15a/b (11%), 17a/b (11%), empty (14%)
- Row 7: hidden(50%) + field 16 (25%) + 17 (25%)
- Row 8: field 18 (42%) + 19 (8%) + 20 (50%)
- Row 9: field 21 (50%) + 22 (22%) + 23 (14%) + 24 (14%)
- Row 10: field 25 (12%) + 26 (12%) + 27 (26%) + 28 (50%)
- Row 11: field 29 (25%) + 30 (75%)

Implementation: Switch from CSS Grid to flex rows (`display: 'flex'`) for the header section. Each row is a `Box` with `display: 'flex'` and `borderBottom`. Cells get `width` as a percentage.

### Step 3: Create `EditableItemBlock` component

New sub-component within `DeclarationFormPage.tsx`, mirroring DeclarationViewPage's `ItemBlock` structure:

```tsx
function EditableItemBlock({ item, itemIndex, paymentItem, itemDocs, selectedField, ... }: {
  item: DeclarationItem;
  itemIndex: number;
  paymentItem?: PaymentResult['items'][0];
  itemDocs?: DocType[];
  selectedField: string | null;
  editingField: string | null;
  onFieldSelect: (cellId: string) => void;
  onStartEdit: (cellId: string) => void;
  onOpenSourceChange: (cellId: string) => void;
  onSaveEdit: (cellId: string, val: string) => void;
  onCancelEdit: () => void;
}) { ... }
```

Layout structure (matching DeclarationViewPage's `ItemBlock`):
```
Row 1: [31: 57%] [32-43: 43% nested]
  32-43 nested:
    [32: 35% | 33: 65%]
    [34: 35% | 35: 40% | 36: 25%]
    [37: 35% | 38: 40% | 39: 25%]
    [40: 100%]
    [41: 35% | 42: 40% | 43: 25%]
Row 2: [44: 57%] [45-46: 43% nested]
  45-46 nested:
    [45: 100%]
    [46: 100%]
```

Each sub-cell is a `FormCell` with `sxOverride={{ width: 'XX%' }}`.

Cell IDs use format `item-{itemIndex}-{field}` (e.g. `item-0-description`, `item-2-hs_code`).

### Step 4: Create `EditablePaymentTable` component

New sub-component rendering field 47 as an editable table:

```tsx
function EditablePaymentTable({ payments, items, onCellEdit }: {
  payments: PaymentResult | null;
  items: DeclarationItem[];
  onCellEdit: (paymentType: string, column: string, value: string) => void;
}) { ... }
```

Table structure (matching DeclarationViewPage's `PaymentRows`):
| Вид  | Основа начисления | Ставка | Сумма | СП |
|------|-------------------|--------|-------|-----|
| 1010 | {customs_value}   | —      | {fee} | ИУ |
| 2010 | {customs_value}   | {rate}%| {duty}| ИУ |
| 5010 | {vat_base}        | {rate}%| {vat} | ИУ |
| **Всего:** |            |        |{total}|    |

Each cell is individually editable. Use MUI `<Box component="table">` with `sx` styling matching the current design language (hover highlights, subtle borders) rather than the plain `style` of the printed form.

### Step 5: Build `PaymentSection` (field 47 + 48 + 49 + B)

Layout matching DeclarationViewPage:
```
[Field 47: 50% — EditablePaymentTable] [Right: 50%]
                                          [48: отсрочка платежей]
                                          [49: реквизиты склада]  ← NEW
                                          [B: подробности подсчёта]
```

Add field 49 (warehouse_requisites) as a new editable cell. It already exists in the `Declaration` type and DB model.

### Step 6: Add Section C and fields 51-53

After PaymentSection:

```tsx
{/* Section C */}
<Box sx={{ borderBottom: '1px solid ...', textAlign: 'center', py: 0.75 }}>
  <FormCell cell={sectionC} sxOverride={{ width: '100%' }} />
</Box>

{/* Fields 51 / 52 / 53 */}
<Box sx={{ display: 'flex', borderBottom: '1px solid ...' }}>
  <FormCell cell={field51} sxOverride={{ width: '33%' }} />
  <FormCell cell={field52} sxOverride={{ width: '33%' }} />
  <FormCell cell={field53} sxOverride={{ width: '34%' }} />
</Box>
```

New cell definitions:
- `{ id: 'f49', num: '49', label: 'Реквизиты склада', field: 'warehouse_requisites' }`
- `{ id: 'fC', num: 'C', label: 'Секция C', field: 'section_c', computed: true }`
- `{ id: 'f51', num: '51', label: 'Таможенные органы транзита', field: 'transit_offices' }`
- `{ id: 'f52', num: '52', label: 'Гарантия', field: 'guarantee_info' }`
- `{ id: 'f53', num: '53', label: 'Таможенный орган назначения', field: 'destination_office_code' }`

### Step 7: DT2 additional sheets

For `items.slice(1)`, generate visual "additional sheet" containers grouped by 3 items:

```tsx
{dt2Sheets.map((sheetItems, sheetIdx) => (
  <Box key={sheetIdx} sx={{ mt: 3, bgcolor: 'white', borderRadius: 4, boxShadow: '...', overflow: 'hidden' }}>
    {/* DT2 header */}
    <Box sx={{ borderBottom: '...', px: 3, py: 1.75, display: 'flex', ... }}>
      <Typography>ДОБАВОЧНЫЙ ЛИСТ {sheetIdx + 2}/{totalForms}</Typography>
    </Box>
    {/* Simplified sender/receiver row */}
    <Box sx={{ display: 'flex', borderBottom: '...' }}>
      <FormCell ... field2 ... />
      <FormCell ... field8 ... />
      <FormCell ... field3 ... />
    </Box>
    {/* Item blocks */}
    {sheetItems.map((itm, slotIdx) => (
      <EditableItemBlock key={itm.id} item={itm} itemIndex={...} ... />
    ))}
    {/* Payment summary for sheet */}
    <EditablePaymentTable ... />
  </Box>
))}
```

### Step 8: Update cell selection for item-scoped fields

Current: `selectedField` stores cell ID (e.g. `'f31'`), cell found via `CELLS.find(c => c.id === selectedField)`.

New: `selectedField` stores composite ID. Introduce lookup across:
1. `HEADER_CELLS` (declaration-level fields 1-30)
2. Item cells (generated dynamically, format `item-{idx}-{field}`)
3. Footer cells (49, 51-53, D, 54)

Add helper:
```tsx
function findCellDef(cellId: string): { cell: CellDef; itemIndex?: number } | null {
  // Check header cells
  const hc = HEADER_CELLS.find(c => c.id === cellId);
  if (hc) return { cell: hc };
  // Check item cells
  const itemMatch = cellId.match(/^item-(\d+)-(.+)$/);
  if (itemMatch) {
    const idx = parseInt(itemMatch[1]);
    const field = itemMatch[2];
    return { cell: { id: cellId, num: ITEM_FIELD_NUMS[field], label: ITEM_FIELD_LABELS[field], field, section: 'Товары' }, itemIndex: idx };
  }
  // Check footer cells
  const fc = FOOTER_CELLS.find(c => c.id === cellId);
  if (fc) return { cell: fc };
  return null;
}
```

### Step 9: Update save handlers for item-level fields

Add import:
```tsx
import { updateItem } from '../api/items';
```

Update `handleSaveEdit`:
```tsx
const handleSaveEdit = useCallback(async (cellId: string, newValue: string) => {
  const result = findCellDef(cellId);
  if (!result || !id) return;
  
  if (result.itemIndex != null) {
    // Item-level field — update via updateItem API
    const item = items[result.itemIndex];
    await updateItem(id, item.id, { [result.cell.field]: newValue || null });
    queryClient.invalidateQueries({ queryKey: ['declaration-items', id] });
  } else {
    // Declaration-level field
    await updateDeclaration(id, { [result.cell.field]: newValue || null });
    queryClient.invalidateQueries({ queryKey: ['declaration', id] });
  }
  // ... evidence_map, auto-save status
}, [id, items, queryClient]);
```

### Step 10: Update metrics to include all cells

Currently `metrics` iterates over `CELLS`. Update to iterate over:
- `HEADER_CELLS` (declaration-level)
- All item cells (for each item, for each ITEM_FIELDS entry)
- `FOOTER_CELLS`

## What Stays Unchanged

- **SourceDrawer** (`SourceDrawerContent`): All source inspection, source change flow, history, document preview — unchanged.
- **DeclHeader**: Toolbar with Документы button, PDF/XML export — unchanged.
- **SummaryStrip**: Metrics display — unchanged (just data source updated).
- **BottomBar**: ECP and Send buttons — unchanged.
- **Styling**: All colors, shadows, border radii, hover effects, state indicators — unchanged.
- **DocumentViewer**: Document viewer dialog — unchanged.

## Estimated Impact

- ~30 lines: counterparty loading + formatting (Step 0)
- ~400 lines: `CELLS`-based grid rendering replaced with ~500 lines of sectioned layout
- ~200 lines new: `EditableItemBlock`, `EditablePaymentTable`
- ~50 lines: cell selection refactoring
- ~30 lines: new cell definitions (49, C, 51-53)
- Net increase: ~410 lines (file grows from ~1110 to ~1520 lines)
