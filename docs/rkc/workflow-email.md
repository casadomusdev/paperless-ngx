# Dynamic Workflow Email Templates

Enhanced workflow email actions with Jinja2 templating support for all 6 email text fields, enabling dynamic emails driven by document custom field values.

## Overview

All 6 email fields support Jinja2 placeholders: `subject`, `body`, `to`, `from_address`, `cc`, `bcc`. Custom field values are accessible via `{{ custom_fields["Field Name"].value }}` syntax.

## New Model Fields

Added to `WorkflowActionEmail`:

| Field | Type | Description |
|-------|------|-------------|
| `from_address` | CharField | Templatable sender address |
| `cc` | CharField | Templatable CC recipients |
| `bcc` | CharField | Templatable BCC recipients |
| `error_tag` | FK to Tag | Tag applied when email validation fails |

**Migration**: `src/documents/migrations/1075_workflowactionemail_dynamic_fields.py`

## Key Features

### Jinja2 Templating
```
To: {{ custom_fields["Mail To"].value }}
Subject: Invoice {{ custom_fields["Invoice Number"].value }} - {{ title }}
Body: Dear {{ correspondent }}, please find attached {{ title }}...
CC: {{ custom_fields["Department CC"].value }}
```

### HTML Auto-Detection
Body content containing HTML tags (`<html`, `<body`, `<br`, `<div`, `<p>`, `<table`) is automatically sent as HTML email. No manual toggle needed.

### Email Validation
All rendered addresses validated with Django's `validate_email` before sending. Invalid addresses trigger error tagging (if `error_tag` configured) instead of crashing the workflow.

### From Address Priority Chain
1. Templated `from_address` (if set and renders to valid email)
2. Mail account `from_address`
3. Mail account username

### Upstream Bug Fix
The `to` field was NOT passed through Jinja2 templating in the original `email_action()` handler — now fixed.

## Custom Fields Context

The `get_custom_fields_context()` function was extended with `sanitize=False` parameter to preserve raw values (e.g., `@` in email addresses) when used in workflow templates.

The `parse_w_workflow_placeholders()` function was extended with `document=None` parameter to include custom field context alongside standard document placeholders.

## Implementation

### Backend — `_render_field()` Helper
Located in `src/documents/signals/handlers.py`, the rewritten `email_action()` uses a `_render_field()` helper that:
1. Renders Jinja2 template with document context
2. Validates rendered email addresses
3. Parses comma-separated address lists
4. Returns validated addresses or triggers error tagging

### Error Handling
When email validation fails:
- If `error_tag` is configured → tag is applied to document via `doc_tag_ids`, email is skipped
- If `PAPERLESS_MAIL_SEND_FAILURE_TAG_ID` is configured → failure tag applied, success tag removed
- If no tags configured → warning logged, email is skipped
- Document processing continues regardless

### Undefined Custom Field Protection
When a Jinja2 template references a custom field that is not set at the time the workflow fires (e.g., the document was just updated but the external pipeline that sets those fields has not yet completed its own PATCH), `_render_field()` raises a `Jinja2 UndefinedError`.

Rather than allowing this to propagate up through `document_updated.send()` and cause an HTTP 500 on the caller's request, `email_action()` catches `UndefinedError` and:
- Logs a `WARNING` with the document title, action ID, and the exact variable that was undefined
- Returns early — the email is skipped for this update event
- The workflow will re-fire on the next `document_updated` signal (e.g., when the pipeline's own PATCH lands), at which point the custom field will be set and the email will send normally

This protection is implemented in `src/documents/signals/handlers.py` as an `except UndefinedError` block around all six `_render_field()` calls in `email_action()`.

## Use Cases

- **Invoice forwarding**: Upload document with custom fields "Mail To" and "Mail Subject", workflow sends email automatically
- **Automated notifications**: Template body with document title, correspondent, dates
- **Departmental routing**: CC/BCC driven by custom field values
- **Error tracking**: Documents with invalid email addresses get tagged for review

## Files Modified

### Backend
- `src/documents/templating/filepath.py` — Added `sanitize=False` parameter to `get_custom_fields_context()`
- `src/documents/templating/workflows.py` — Added `document=None` parameter to `parse_w_workflow_placeholders()`
- `src/documents/models.py` — Added `from_address`, `cc`, `bcc`, `error_tag` fields to `WorkflowActionEmail`
- `src/documents/migrations/1075_workflowactionemail_dynamic_fields.py` — Migration for new fields
- `src/documents/mail.py` — Updated `send_email()` signature with `from_email`, `cc`, `bcc`, `is_html` kwargs
- `src/documents/signals/handlers.py` — Complete rewrite of `email_action()` with `_render_field()` helper
- `src/documents/serialisers.py` — Added new fields to `WorkflowActionEmailSerializer`

### Frontend
- `src-ui/src/app/data/workflow-action.ts` — Added fields to `WorkflowActionEmail` interface
- `src-ui/src/app/components/common/edit-dialog/workflow-edit-dialog/workflow-edit-dialog.component.ts` — FormControls, TagService for error_tag
- `src-ui/src/app/components/common/edit-dialog/workflow-edit-dialog/workflow-edit-dialog.component.html` — New form fields with placeholder hints

## Version History

- **v1.4.1**: Undefined custom field protection — `UndefinedError` caught in `email_action()` so templates referencing unset fields log a warning and skip rather than propagating HTTP 500
- **v1.2.0**: Initial implementation with Jinja2 templating for all 6 fields, HTML auto-detection, validation, error tagging
