# TODO.md

## Phase 1: Backend — Settings, Serializer, Views

- [x] Add 4 new env vars to `settings.py`: `MAIL_TO_FIELD`, `MAIL_CC_FIELD`, `MAIL_BCC_FIELD`, `MAIL_BODY_FIELD`
- [x] Add `from_address`, `cc`, `bcc` fields + validators to `EmailSerializer` in `serialisers.py`
- [x] Upgrade `email_documents()` in `views.py`: from/cc/bcc, address validation, recipient verification, tags, notes
- [x] Add `mail_cf_field_names` dict to `UiSettingsView.get()` in `views.py`

## Phase 2: Frontend — UiSettings, Service, Dialog, DocumentDetail

- [x] Add `MAIL_CF_FIELD_NAMES` key and SETTINGS entry to `ui-settings.ts`
- [x] Add optional `fromEmail?`, `cc?`, `bcc?` to `emailDocuments()` in `document.service.ts`
- [x] Add `emailFrom`, `emailCc`, `emailBcc` fields + `ngOnInit()` pre-fill logic to dialog component TS
- [x] Add From, CC, BCC input fields to dialog template HTML
- [x] Pass `customFields` + `customFieldInstances` to modal in `document-detail.component.ts`

## Phase 3: Documentation

- [x] Update `docs/rkc/mail-system.md` with enhanced manual send dialog section
- [x] Update `RKC_CUSTOMIZATIONS.md` with new env vars

## Future Improvements

- Consider subject pre-fill for bulk email (use a static default or prompt)
- Optionally allow the user to toggle CF pre-fill via a UI checkbox in the dialog
- Consider adding a `Reply-To` header field — the backend `send_email()` would need to attach it via `EmailMessage.extra_headers`
- Consider persistent dialog defaults (last used From/CC/BCC saved to user settings)
