# IMPLEMENT.md

## GOAL

Enhance the manual "Send Email" dialog in the document detail screen to have full feature parity with workflow email actions. Specifically:

1. Add CC, BCC, From override fields to the dialog
2. Upgrade the backend `email_documents()` view to support these fields plus recipient verification, success/failure tags, and system notes — identical to what `email_action()` does for workflows
3. Pre-fill all relevant dialog fields from document custom field values using the existing `PAPERLESS_MAIL_*_FIELD` naming scheme plus 4 new env vars
4. No pre-fill occurs if: env var is not set/`""`, configured CF name doesn't exist, CF not assigned to doc, or doc has no value for that CF
5. Bulk editor (multiple documentIds): skip CF pre-fill entirely

## ANALYSIS

The `send_email()` function in `documents/mail.py` already fully supports Graph API, OAuth2 SMTP, from_email, CC, BCC, and HTML. The backend `email_documents()` view simply doesn't pass these through — it only passes To, Subject, Body.

The workflow's `email_action()` in `signals/handlers.py` is the reference implementation: it validates addresses, verifies recipient domains, applies success/failure tags, and creates notes. The `email_documents()` endpoint needs to be upgraded to match.

On the frontend, the dialog component needs new From/CC/BCC fields and an `ngOnInit()` pre-fill step that uses the `mail_cf_field_names` dict (passed from the backend via UiSettings) to look up the CF by name → by id → by instance → by value.

The existing `PAPERLESS_MAIL_FROM_FIELD` and `PAPERLESS_MAIL_SUBJECT_FIELD` settings reuse directly. Four new settings with empty-string defaults are added:
- `PAPERLESS_MAIL_TO_FIELD` → `settings.MAIL_TO_FIELD`
- `PAPERLESS_MAIL_CC_FIELD` → `settings.MAIL_CC_FIELD`
- `PAPERLESS_MAIL_BCC_FIELD` → `settings.MAIL_BCC_FIELD`
- `PAPERLESS_MAIL_BODY_FIELD` → `settings.MAIL_BODY_FIELD`

## IMPLEMENTATION

### Phase 1: Backend — Settings, Serializer, Views

**settings.py**: Add 4 new env vars `MAIL_TO_FIELD`, `MAIL_CC_FIELD`, `MAIL_BCC_FIELD`, `MAIL_BODY_FIELD`, all defaulting to `""`.

**serialisers.py / EmailSerializer**: Add optional `from_address`, `cc`, `bcc` CharField fields with validators mirroring `validate_addresses`.

**views.py / email_documents()**: Extract from/cc/bcc from validated data. Validate all address lists. Run recipient domain verification if `MAIL_VERIFY_RECIPIENT != "none"`. Call `send_email()` with extended params. Apply success/failure tags and create notes matching workflow behavior.

**views.py / UiSettingsView.get()**: Inject `mail_cf_field_names` dict into ui_settings response.

### Phase 2: Frontend — UiSettings, Service, Dialog, DocumentDetail

**ui-settings.ts**: Add `MAIL_CF_FIELD_NAMES` key and SETTINGS entry with type `'object'` and default `{}`.

**document.service.ts / emailDocuments()**: Add optional `fromEmail?`, `cc?`, `bcc?` params; include in request body.

**email-document-dialog.component.ts**: Implement `OnInit`. Add `@Input() customFields` and `@Input() customFieldInstances`. Add `emailFrom`, `emailCc`, `emailBcc` fields. Add `ngOnInit()` with 4-guard pre-fill logic. Pass new fields to service call. Reset them after send.

**email-document-dialog.component.html**: Add From, CC, BCC input form fields before the existing ones (From) and after To (CC/BCC).

**document-detail.component.ts / openEmailDocument()**: Pass `this.customFields` and `this.document.custom_fields ?? []` to modal instance.

### Phase 3: Documentation

**docs/rkc/mail-system.md**: Add section on enhanced manual send dialog, CF pre-fill behavior, and new env vars.

**RKC_CUSTOMIZATIONS.md**: Document the 4 new env vars.
