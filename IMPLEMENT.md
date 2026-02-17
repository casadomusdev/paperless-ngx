# Dynamic Workflow Email with Custom Field Templates

## GOAL

Implement v1.2.0 customization: Dynamic email sending via workflow actions using Jinja2 templates with custom field placeholders. All email fields (subject, body, to, from, cc, bcc) support template expressions like `{{ custom_fields["Mail From"].value }}`.

## ANALYSIS

### Existing Infrastructure
- `get_custom_fields_context()` in `filepath.py` builds a `custom_fields` dict for Jinja templates, but sanitizes values with `pathvalidate` (breaks `@` in emails)
- `parse_w_workflow_placeholders()` in `workflows.py` handles Jinja templating for workflow text fields, but doesn't accept a document instance and doesn't include `custom_fields` context
- Both use the shared `_template_environment` singleton from `environment.py` with `get_cf_value` filter already registered
- Upstream bug: `to` field is NOT passed through Jinja templating in `email_action()` handler

### Key Design Decisions
- Add `sanitize` parameter to `get_custom_fields_context()` (default=True for backward compat)
- Add `document` parameter to `parse_w_workflow_placeholders()` to include raw custom fields context
- New model fields: `from_address`, `cc`, `bcc` (text), `error_tag` (FK to Tag)
- HTML auto-detection: check for `<html` or `<body` or `<br` tags in rendered body
- Email validation after rendering: on failure apply `error_tag` to document, abort remaining workflow actions
- From address priority: templated `from_address` → mail account `from_address` → mail account username
- Custom exception `WorkflowEmailValidationError` for clean workflow abort

## IMPLEMENTATION

### Phase 1: Backend Templating
1. Add `sanitize=True` parameter to `get_custom_fields_context()` in `filepath.py`
2. When `sanitize=False`, skip `pathvalidate.sanitize_filename()` calls on names and values
3. Extend `parse_w_workflow_placeholders()` in `workflows.py` to accept optional `document=None`
4. When document is provided, fetch its custom fields and merge raw context into formatting dict

### Phase 2: Model Changes
1. Add `from_address`, `cc`, `bcc` (CharField, blank/null) to `WorkflowActionEmail`
2. Add `error_tag` (ForeignKey to Tag, null/blank) to `WorkflowActionEmail`
3. Create migration `1075_workflowactionemail_dynamic_fields.py`

### Phase 3: send_email Enhancement
1. Add `from_email=None`, `cc=None`, `bcc=None`, `is_html=False` parameters
2. Apply `from_email` override when provided
3. Set `email.content_subtype = 'html'` when `is_html=True`
4. Pass `cc` and `bcc` to EmailMessage constructor

### Phase 4: Signal Handler Updates
1. Template ALL 6 text fields through `parse_w_workflow_placeholders()` (including `to`)
2. Implement HTML auto-detection for rendered body
3. Create `WorkflowEmailValidationError` exception class
4. Add email validation after rendering: validate all addresses in to/cc/bcc
5. On validation failure: apply error_tag to document, log error, return (abort email)
6. Implement from_address priority chain

### Phase 5: Serializer Updates
1. Add new fields to `WorkflowActionEmailSerializer`

### Phase 6: Frontend UI Updates
1. Add `from_address`, `cc`, `bcc`, `error_tag` to TypeScript interface
2. Add FormControls in `createActionField()`
3. Add HTML form fields in template

### Phase 7: Documentation
1. Update `RKC_CUSTOMIZATIONS.md` with v1.2.0 entry
2. Update `STRUCTURE.md`
