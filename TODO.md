# TODO: v1.2.0 Dynamic Workflow Email with Custom Field Templates

## Phase 1: Backend Templating
- [x] Add `sanitize` parameter to `get_custom_fields_context()` in `filepath.py`
- [x] Extend `parse_w_workflow_placeholders()` in `workflows.py` with `document=None` param

## Phase 2: Model Changes
- [x] Add `from_address`, `cc`, `bcc`, `error_tag` fields to `WorkflowActionEmail` model
- [x] Create migration `1075_workflowactionemail_dynamic_fields.py`

## Phase 3: send_email Enhancement
- [x] Add `from_email`, `cc`, `bcc`, `is_html` params to `send_email()` in `mail.py`

## Phase 4: Signal Handler Updates
- [x] Template all 6 fields (subject, body, to, from_address, cc, bcc) through Jinja
- [x] HTML auto-detection for body
- [x] Email validation after rendering with error_tag support
- [x] From address priority chain
- [x] Create `WorkflowEmailValidationError` exception

## Phase 5: Serializer Updates
- [x] Add new fields to `WorkflowActionEmailSerializer`

## Phase 6: Frontend UI Updates
- [x] Update TypeScript interface `WorkflowActionEmail`
- [x] Add FormControls in `createActionField()` and `addAction()`
- [x] Add HTML form inputs in template

## Phase 7: Documentation
- [x] Update `RKC_CUSTOMIZATIONS.md` with v1.2.0 entry
- [x] Update `STRUCTURE.md` if needed

## Future Improvements
- Template preview/validation in the UI (render templates with dummy data to show users what the output will look like)
- MS365 Graph API sending support for workflow emails (currently only SMTP)
- Recipient auto-suggestion from correspondent email addresses
- Email delivery status tracking and retry mechanism
- Template library/snippets for common email patterns
