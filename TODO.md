# SMTP Email Sending Refactor - TODO

## Completed ✅

### Backend (Phases 1-3)
- [x] Phase 1: Database schema changes
  - [x] Added SMTP fields to MailAccount model
  - [x] Created migration 0031_add_smtp_fields.py
  - [x] Updated model validation
  - [x] Added "only one sending account" enforcement in save()
  
- [x] Phase 2: Backend enforcement
  - [x] save() method automatically disables other sending accounts
  - [x] Serializer returns sending_account_changed_from info
  - [x] Updated clean() validation for SMTP requirements

- [x] Phase 3: Traditional SMTP support
  - [x] Refactored OAuth2EmailBackend → MailAccountEmailBackend
  - [x] Support both OAuth2 XOAUTH2 and traditional password auth
  - [x] Updated get_sending_mail_account() to support all account types
  - [x] Updated send_email() to use new backend
  - [x] Updated serializers with all new fields

## Remaining Work ⏳

###  Phase 4: Frontend UI Refactor ✅ COMPLETE

#### TypeScript Data Models ✅
- [x] Update `src-ui/src/app/data/mail-account.ts`
  - [x] Add smtp_server field
  - [x] Add smtp_port field
  - [x] Add smtp_security field
  - [x] Add smtp_username field
  - [x] Add smtp_password field
  - [x] Add sending_account_info field

#### Mail Account Edit Dialog ✅
- [x] Update `mail-account-edit-dialog.component.html`
  - [x] Reorganize into "Receiving (IMAP)" and "Sending (SMTP)" sections
  - [x] Add SMTP server field
  - [x] Add SMTP port field  
  - [x] Add SMTP security dropdown (SSL/STARTTLS/NONE)
  - [x] Add SMTP username field (conditional on non-OAuth)
  - [x] Add SMTP password field (conditional on non-OAuth)
  - [x] Add info box for OAuth accounts explaining XOAUTH2
  - [x] Add warning when changing sending account

- [x] Update `mail-account-edit-dialog.component.ts`
  - [x] Add form controls for new SMTP fields
  - [x] Add logic to show/hide SMTP auth fields based on account_type
  - [x] Add onSendingToggle() method
  - [x] Add setDefaultSmtpConfig() method
  - [x] Add save() warning dialog for sending account changes
  - [x] Added smtpSecurityOptions getter
  - [x] Added isTraditionalAccount getter

#### Mail Account List View (OPTIONAL - Future Enhancement)
- [ ] Add badge/indicator for account with use_for_sending=True
- [ ] Show "Current sending account: [Name]" info message

### Phase 5: Verify EMAIL_ENABLED Checks ✅ COMPLETE
- [x] Search for all EMAIL_ENABLED references
- [x] Verify all include get_sending_mail_account() fallback
- [x] Already done in documents/signals/handlers.py (v1.0.18)

### Phase 6: Documentation ✅ COMPLETE
- [x] Update RKC_CUSTOMIZATIONS.md with v1.1.0 entry
- [x] Update IMPLEMENT.md with completion status
- [x] Create migration guide from v1.0.18 (included in RKC_CUSTOMIZATIONS.md)
- [ ] Update MS365_OAUTH_SETUP.md if needed (OPTIONAL)
- [ ] Update IMPL_OAUTH_MAIL_SENDING.md (mark as superseded) (OPTIONAL)

### Phase 7: Testing (User Responsibility)
- [ ] Test OAuth2 account with sending enabled
- [ ] Test traditional SMTP account with sending enabled
- [ ] Test fallback to environment variables
- [ ] Test "only one sending account" enforcement
- [ ] Test workflow email actions
- [ ] Test sending account change warning
- [ ] Test default SMTP config for Gmail/Outlook OAuth

## Notes

### Default SMTP Configurations
- Gmail OAuth: smtp.gmail.com:587 (STARTTLS)
- Outlook OAuth: smtp.office365.com:587 (STARTTLS)
- Traditional IMAP: User must configure manually

### Backward Compatibility
- Existing v1.0.18 OAuth sending accounts will work after migration
- Migration automatically populates smtp_server, smtp_port, smtp_security with defaults
- Environment variable configuration still works as fallback

### Security Considerations
- smtp_password uses ObfuscatedPasswordField (same as main password)
- Passwords not exposed in API responses
- Only one sending account can be enabled at a time

## Timeline
- Backend: ✅ Complete (2026-01-28)
- Frontend: ⏳ In Progress
- Testing: ⏳ Pending
- Documentation: ⏳ Pending
