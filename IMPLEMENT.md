# SMTP Email Sending Refactor Implementation

## GOAL

Refactor the OAuth2-specific email sending feature (v1.0.18) into a general "SMTP Email Sending via Mail Accounts" feature that supports both OAuth2 XOAUTH2 authentication and traditional SMTP password-based authentication.

## ANALYSIS

Current implementation (v1.0.18) has:
- `use_for_sending` and `from_address` fields on MailAccount
- OAuth2EmailBackend that only supports OAuth2 authentication
- Hardcoded SMTP server settings based on account_type
- No enforcement of "only one sending account" rule
- No support for traditional SMTP authentication

Target implementation (v1.1.0) will have:
- Additional SMTP configuration fields (server, port, security, username, password)
- Support for both OAuth2 and traditional SMTP authentication  
- Enforcement of "only one sending account" rule
- Flexible SMTP server configuration for all account types
- Clean UI separation between IMAP (receiving) and SMTP (sending)
- Environment variables as fallback when no mail account configured

## IMPLEMENTATION

### Phase 1: Database Schema Changes
- Add SMTP configuration fields to MailAccount model
- Create migration 0031_add_smtp_fields.py
- Set reasonable defaults based on account type

### Phase 2: Only One Sending Account Enforcement
- Override save() method in MailAccount model
- Automatically disable other sending accounts when one is enabled
- Return information about the change via serializer

### Phase 3: Support Traditional SMTP Authentication
- Refactor OAuth2EmailBackend to MailAccountEmailBackend
- Support both OAuth2 XOAUTH2 and traditional password auth
- Select authentication method based on account_type

### Phase 4: Frontend UI Refactor
- Reorganize mail account edit dialog into IMAP/SMTP sections
- Add SMTP configuration fields (conditional on account type)
- Add warning dialog when changing sending account
- Show current sending account in UI

### Phase 5: Update EMAIL_ENABLED Checks
- Already completed in v1.0.18 bug fixes
- Verify all checks include mail account fallback

### Phase 6: Documentation
- Update RKC_CUSTOMIZATIONS.md with v1.1.0 entry
- Update this IMPLEMENT.md with completion status
- Provide migration guide for existing users

## STATUS

✅ Planning complete
✅ Backend implementation complete (Phases 1-3)
⏳ Frontend implementation pending (Phase 4)
⏳ Documentation pending (Phase 6)

## COMPLETED WORK

### Phase 1: Database Schema Changes ✅
- Added SMTP configuration fields to MailAccount model:
  - smtp_server, smtp_port, smtp_security
  - smtp_username, smtp_password (for traditional auth)
- Created migration 0031_add_smtp_fields.py
- Updated model validation in clean() method
- Added _set_default_smtp_config() helper method

### Phase 2: Only One Sending Account Enforcement ✅
- Overrode save() method to automatically disable other sending accounts
- Added _sending_account_changed_from attribute for API response
- Updated MailAccountSerializer with sending_account_info field
- Backend ensures only one account can have use_for_sending=True

### Phase 3: Support Traditional SMTP Authentication ✅
- Renamed OAuth2EmailBackend → MailAccountEmailBackend
- Added support for both OAuth2 XOAUTH2 and traditional password auth
- Created _is_oauth_account() helper method
- Split open() into _open_oauth() and _open_traditional()
- Updated get_sending_mail_account() to return ANY account type
- Updated send_email() in documents/mail.py to use new backend
- Updated serializers with all new SMTP fields

### Phase 5: EMAIL_ENABLED Checks ✅
- Already handled in v1.0.18 bug fixes
- documents/signals/handlers.py includes get_sending_mail_account() fallback

## NEXT STEPS

See TODO.md for detailed frontend implementation checklist and remaining work.
