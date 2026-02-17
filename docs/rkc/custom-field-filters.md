# Custom Field Filter Buttons

Quick filter buttons for custom field values on document detail page and card views, enabling instant filtering by any custom field value.

## Overview

Filter buttons appear next to every custom field value. Clicking a filter button navigates to the document list filtered to show all documents with the same custom field value. Supports all 10 custom field data types including null/empty values.

## Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PAPERLESS_SHOW_CUSTOM_FIELD_NAMES_IN_CARDS` | Boolean | `false` | Show "FieldName: Value" format in card views instead of value-only |

## Document Detail Page Filters (v1.0.6)

### Filter Mechanism

Uses `FILTER_CUSTOM_FIELDS_QUERY` filter type (ID 42) from existing Paperless filter infrastructure:
- Query format: `JSON.stringify(["FieldName", "exact", "value"])`
- Null/empty values converted to empty string for filtering
- Navigation via `DocumentListViewService.quickFilter()`

### Implementation

**TypeScript Method** (`document-detail.component.ts`):
```typescript
// RKC: Filter documents by custom field value
filterByCustomField(fieldInstance: CustomFieldInstance) {
  const field = this.getCustomFieldFromInstance(fieldInstance)
  if (!field) return
  const queryValue = JSON.stringify([field.name, 'exact', fieldInstance.value?.toString() ?? ''])
  const filterRule: FilterRule = { rule_type: FILTER_CUSTOM_FIELDS_QUERY, value: queryValue }
  this.documentListViewService.quickFilter([filterRule])
}
// /end RKC edit
```

**Template Integration**: All 10 custom field input components enhanced with:
```html
[showFilter]="true" (filterDocuments)="filterByCustomField(fieldInstance)"
```

Applied to: `app-input-text` (String), `app-input-date` (Date), `app-input-number` (Integer/Float/Monetary), `app-input-switch` (Boolean), `app-input-url` (Url), `app-input-document-link` (DocumentLink), `app-input-select` (Select), `app-input-longtext` (LongText)

### UX
- Filter icon button displayed to the right of each custom field value
- Tooltip: "Filter documents with this custom field value" (EN) / "Dokumente mit diesem benutzerdefinierten Feldwert filtern" (DE)
- Consistent with existing filter buttons (correspondent, document type, etc.)

## Card View Filters (v1.0.25)

### Features
- Filter buttons on both small and large card views
- Tooltip: "Show all with this value" (EN) / "Alle mit diesem Wert anzeigen" (DE)
- Optional field name display: "FieldName: Value" format via environment variable

### Field Name Display
- **Default (disabled)**: Shows only values for compact display
- **When enabled**: Shows "FieldName: Value" format for better context
- Boolean fields always show names regardless of setting

### Reusable Component
Created `custom-field-display` component with:
- `showFilter` input and `filterClick` event output
- `showFieldName` getter reading from settings service
- Used by both card view components

## Files Modified

### Backend
- `src/paperless/settings.py` — `SHOW_CUSTOM_FIELD_NAMES_IN_CARDS` env var
- `src/documents/views.py` — Exposed setting to frontend

### Frontend — Document Detail
- `src-ui/src/app/components/document-detail/document-detail.component.ts` — `filterByCustomField()` method
- `src-ui/src/app/components/document-detail/document-detail.component.html` — Filter button integration for all field types

### Frontend — Input Components (filter support added)
- `src-ui/src/app/components/common/input/text/` (ts + html)
- `src-ui/src/app/components/common/input/number/` (ts + html)
- `src-ui/src/app/components/common/input/monetary/` (ts + html)
- `src-ui/src/app/components/common/input/check/` (ts + html)
- `src-ui/src/app/components/common/input/url/` (ts + html)
- `src-ui/src/app/components/common/input/document-link/` (ts + html)
- `src-ui/src/app/components/common/input/textarea/` (ts + html)

### Frontend — Card Views
- `src-ui/src/app/components/common/custom-field-display/custom-field-display.component.ts` — Reusable component
- `src-ui/src/app/components/common/custom-field-display/custom-field-display.component.html` — Template
- `src-ui/src/app/components/document-list/document-card-small/` (ts + html)
- `src-ui/src/app/components/document-list/document-card-large/` (ts + html)
- `src-ui/src/app/data/ui-settings.ts` — Settings key

### Translations
- `src-ui/src/locale/messages.en_US.xlf` — English tooltip translations
- `src-ui/src/locale/messages.de_DE.xlf` — German tooltip translations

## Version History

- **v1.0.6**: Custom field filter buttons on document detail page (all 10 data types)
- **v1.0.25**: Filter buttons + optional field names in card views (small + large)
