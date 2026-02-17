# PDF Editor Superuser Restriction

Optionally restrict PDF editor access to superusers only to prevent accidental file modifications by regular users.

## Environment Variable

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER` | Boolean | `false` | When enabled, only superusers can access the PDF editor |

## Behavior

- **When disabled (default)**: All users can access PDF editor (original Paperless-ngx behavior)
- **When enabled**: Only superusers can access PDF editor
  - Backend validates `user.is_superuser` before allowing PDF edit operations
  - Frontend hides PDF Editor button for non-superusers
  - Returns `HttpResponseForbidden` with clear error message when unauthorized
  - Superusers can edit ANY document's PDF regardless of ownership

## Security Model

Defense in depth:
- **Backend**: Rejects unauthorized requests with 403 Forbidden (even if frontend bypass is attempted)
- **Frontend**: Hides PDF Editor button entirely for non-superusers (clean UX — no confusing disabled options)

## Files Modified

### Backend
- `src/paperless/settings.py` — Environment variable configuration
- `src/documents/views.py` — Permission check in `BulkEditView.post()` + UI settings exposure

**Backend Code** (`BulkEditView.post()`):
```python
# RKC: Optional restriction of PDF editor to superusers to prevent accidental file modifications
if (
    method == bulk_edit.edit_pdf
    and settings.PDF_EDITOR_RESTRICT_TO_SUPERUSER
    and not user.is_superuser
):
    return HttpResponseForbidden("PDF editor is restricted to administrators")
# /end RKC edit
```

### Frontend
- `src-ui/src/app/data/ui-settings.ts` — Settings key definition
- `src-ui/src/app/components/document-detail/document-detail.component.ts` — Superuser and restriction setting getters
- `src-ui/src/app/components/document-detail/document-detail.component.html` — Conditional button rendering

**Frontend Getters** (`document-detail.component.ts`):
```typescript
// RKC: Check if user is superuser to restrict PDF editor access to admins only
get userIsSuperuser(): boolean {
  return this.permissionsService.isSuperUser()
}

// RKC: Check if PDF editor restriction is enabled via environment variable
get pdfEditorRestrictToSuperuser(): boolean {
  return this.settings.get(SETTINGS_KEYS.PDF_EDITOR_RESTRICT_TO_SUPERUSER)
}
// /end RKC edit
```

**Template Condition** (`document-detail.component.html`):
```html
<!-- RKC: Optionally hide PDF Editor menu item for non-superusers -->
<button *ngIf="!pdfEditorRestrictToSuperuser || userIsSuperuser" ngbDropdownItem (click)="editPdf()"
  [disabled]="!userCanEdit || originalContentRenderType !== ContentRenderType.PDF">
  <i-bs name="pencil"></i-bs>&nbsp;<ng-container i18n>PDF Editor</ng-container>
</button>
<!-- /end RKC edit -->
```

## Testing

### Manual Tests
- Login as regular user → PDF Editor button should not appear (when restriction enabled)
- Login as superuser → PDF Editor button should appear
- Attempt direct API call as regular user → Should receive 403 Forbidden
- Verify superuser can edit ANY document's PDF regardless of ownership

### Expected Results
- Non-superusers: No PDF editor UI element visible, API returns `403 Forbidden`
- Superusers: Full PDF editor access including UI and API for ALL documents

## Version History

- **v1.0.0**: Initial PDF editor superuser restriction
- **v1.0.7**: Fixed ownership restriction — superusers can now edit ANY document's PDF
- **v1.0.8**: Made restriction optional via `PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER` env var (default: false)
