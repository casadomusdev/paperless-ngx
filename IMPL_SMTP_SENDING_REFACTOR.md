# SMTP Email Sending via Mail Accounts - Refactor Implementation Plan

## Goal

Refactor the OAuth2-specific email sending feature (v1.0.18) into a general "SMTP Email Sending via Mail Accounts" feature that supports both OAuth2 XOAUTH2 authentication and traditional SMTP password-based authentication. This makes email sending configuration more flexible and user-friendly while maintaining backwards compatibility with environment variable configuration.

## Context

The current implementation (v1.0.18) added OAuth2 email sending support to Mail Accounts with:
- `use_for_sending` checkbox
- `from_address` text field
- OAuth2 XOAUTH2 SASL authentication via custom EmailBackend

However, the feature has limitations:
1. Only supports OAuth2 authentication (not traditional SMTP)
2. SMTP server details are hardcoded based on account type
3. UI doesn't prevent multiple accounts from being enabled as sending accounts
4. No warning when switching sending accounts
5. Mail actions in workflow UI were blocked when env vars not set (fixed in v1.0.18+)

## Requirements

1. **Support both authentication methods**: OAuth2 XOAUTH2 and traditional username/password SMTP
2. **One sending account rule**: Only one mail account can have `use_for_sending=True` at a time
3. **Account selection overrides env vars**: When a mail account is selected for sending, it takes precedence over `EMAIL_HOST` etc.
4. **Env vars remain as fallback**: Keep environment variable configuration for unattended deployments and security-conscious users
5. **UI transparency**: Show current sending account configuration in the UI
6. **Warning on change**: Alert users when changing which account is used for sending
7. **Flexible SMTP configuration**: Allow custom SMTP server, port, security settings for all account types

## Architecture Overview

### Data Flow (After Refactor)

```
Email Sending Request
        ↓
   Check for Mail Account with use_for_sending=True
        ↓
   ┌────────────┴────────────┐
   │                         │
Account Found          No Account Found
   │                         │
   ↓                         ↓
Get SMTP Config      Use env vars (EMAIL_HOST, etc.)
from MailAccount            ↓
   │                  Django's default EmailBackend
   ↓
Check account_type
   │
   ├──→ OAuth: Use OAuth2EmailBackend
   │           (XOAUTH2 SASL)
   │
   └──→ Traditional: Use CustomSMTPBackend
               (password auth)
```

### Only One Sending Account Enforcement

```
User enables use_for_sending on Account B
        ↓
Backend receives save request
        ↓
Check if another account has use_for_sending=True
        ↓
   ┌────────────┴────────────┐
   │                         │
Account A found        No other account
   │                         │
   ↓                         ↓
Set Account A's      Save Account B
use_for_sending=False       ↓
   │                    Return info about
   ↓                    the change
Save Account B
   ↓
Return info: "Account B is now the sending account (was: Account A)"
```

## Implementation Plan

### Phase 1: Database Schema Changes

**Goal**: Add SMTP configuration fields to MailAccount model

**Files to modify**:
- `src/paperless_mail/models.py`
- Create new migration file

**Changes**:

1. **Add new fields to MailAccount model**:
   ```python
   # SMTP Sending Configuration
   use_for_sending = models.BooleanField(default=False, help_text="Use this account for sending emails")
   from_address = models.EmailField(blank=True, null=True, help_text="Email address to use in From field")
   
   # SMTP Server Configuration (for both OAuth and traditional)
   smtp_server = models.CharField(max_length=256, blank=True, null=True, help_text="SMTP server hostname")
   smtp_port = models.IntegerField(blank=True, null=True, help_text="SMTP server port")
   smtp_security = models.CharField(
       max_length=10,
       choices=[
           ('SSL', 'SSL'),
           ('STARTTLS', 'STARTTLS'),
           ('NONE', 'None'),
       ],
       blank=True,
       null=True,
       help_text="SMTP security protocol"
   )
   
   # Traditional SMTP Authentication
   smtp_username = models.CharField(max_length=256, blank=True, null=True, help_text="SMTP username (if different from IMAP username)")
   smtp_password = models.CharField(max_length=256, blank=True, null=True, help_text="SMTP password (for traditional auth only)")
   ```

2. **Update model validation** in `clean()` method:
   - If `use_for_sending=True`, require `from_address` (unless username is an email)
   - If `use_for_sending=True` and `account_type != 'oauth'`, require SMTP credentials
   - If `use_for_sending=True`, set reasonable defaults for `smtp_server`, `smtp_port`, `smtp_security` based on account type if not provided

3. **Create migration**:
   - File: `src/paperless_mail/migrations/0031_add_smtp_fields.py`
   - Add new fields with appropriate defaults
   - For existing accounts with `use_for_sending=True`, populate `smtp_server`, `smtp_port`, `smtp_security` with current hardcoded defaults

**Default SMTP configurations by account type**:
- Gmail OAuth: `smtp.gmail.com:587` (STARTTLS)
- Office365 OAuth: `smtp.office365.com:587` (STARTTLS)
- Custom: User must provide

**Testing considerations**:
- Test migration on existing databases with OAuth sending accounts
- Verify model validation works for all account types

---

### Phase 2: Backend - "Only One Sending Account" Enforcement

**Goal**: Ensure only one mail account can be designated as the sending account at any time

**Files to modify**:
- `src/paperless_mail/models.py` (save method)
- `src/paperless_mail/serialisers.py` (validation)
- `src/paperless_mail/views.py` (API response)

**Changes**:

1. **Add `save()` override to MailAccount model**:
   ```python
   def save(self, *args, **kwargs):
       if self.use_for_sending:
           # Find other accounts with use_for_sending=True
           other_accounts = MailAccount.objects.filter(
               use_for_sending=True
           ).exclude(pk=self.pk)
           
           if other_accounts.exists():
               # Store for response info
               previous_account = other_accounts.first()
               # Disable sending on all other accounts
               other_accounts.update(use_for_sending=False)
               # Track what changed for API response
               self._sending_account_changed_from = previous_account
       
       super().save(*args, **kwargs)
   ```

2. **Update serializer to return change info**:
   ```python
   class MailAccountSerializer(serializers.ModelSerializer):
       sending_account_info = serializers.SerializerMethodField()
       
       def get_sending_account_info(self, obj):
           if hasattr(obj, '_sending_account_changed_from'):
               return {
                   'changed': True,
                   'previous_account': obj._sending_account_changed_from.name,
                   'previous_account_id': obj._sending_account_changed_from.id,
               }
           return None
   ```

3. **Add helper function to get current sending account**:
   ```python
   def get_current_sending_account():
       """Returns the current sending account or None if using env vars"""
       return MailAccount.objects.filter(use_for_sending=True).first()
   ```

4. **Update `get_sending_mail_account()` in mail_oauth.py**:
   - Currently only returns OAuth accounts
   - Should return ANY account with `use_for_sending=True`

**Testing considerations**:
- Test enabling sending on Account B when Account A is already enabled
- Test saving account without changing sending status
- Test with no accounts having sending enabled (should fall back to env vars)

---

### Phase 3: Backend - Support Traditional SMTP Authentication

**Goal**: Extend email backend to support both OAuth2 and traditional password-based authentication

**Files to modify**:
- `src/paperless_mail/mail_oauth.py` (rename/refactor)
- `src/documents/signals/handlers.py` (update email sending logic)
- `src/documents/mail.py` (if needed)

**Changes**:

1. **Create new unified email backend** in `mail_oauth.py` (or rename to `mail_backends.py`):
   ```python
   class MailAccountEmailBackend(SMTPEmailBackend):
       """
       Custom email backend that uses MailAccount configuration
       Supports both OAuth2 XOAUTH2 and traditional authentication
       """
       
       def __init__(self, *args, **kwargs):
           # Get the sending account
           self.mail_account = get_sending_mail_account()
           
           if not self.mail_account:
               # Fall back to env var configuration
               super().__init__(*args, **kwargs)
               return
           
           # Override settings with account configuration
           kwargs['host'] = self.mail_account.smtp_server
           kwargs['port'] = self.mail_account.smtp_port
           kwargs['username'] = self.mail_account.smtp_username or self.mail_account.username
           
           # Set security protocol
           if self.mail_account.smtp_security == 'SSL':
               kwargs['use_ssl'] = True
               kwargs['use_tls'] = False
           elif self.mail_account.smtp_security == 'STARTTLS':
               kwargs['use_ssl'] = False
               kwargs['use_tls'] = True
           else:
               kwargs['use_ssl'] = False
               kwargs['use_tls'] = False
           
           # Set password (only for non-OAuth)
           if self.mail_account.account_type != 'oauth':
               kwargs['password'] = self.mail_account.smtp_password
           
           super().__init__(*args, **kwargs)
       
       def open(self):
           """Override to add OAuth2 authentication if needed"""
           if self.mail_account and self.mail_account.account_type == 'oauth':
               # Use OAuth2 XOAUTH2 authentication
               if self.connection:
                   return False
               
               # ... (existing OAuth2EmailBackend logic) ...
               
               return True
           else:
               # Use standard SMTP authentication
               return super().open()
   ```

2. **Update get_from_address() function**:
   ```python
   def get_from_address():
       account = get_sending_mail_account()
       if account:
           return account.from_address
       return settings.DEFAULT_FROM_EMAIL
   ```

3. **Update email sending calls**:
   - Ensure all email sending uses the new backend
   - Update `send_email()` function in handlers.py to use `MailAccountEmailBackend`

**Testing considerations**:
- Test OAuth2 accounts still work (regression test)
- Test traditional SMTP with various security protocols (SSL, STARTTLS, None)
- Test fallback to env vars when no account configured
- Test From address is correctly set

---

### Phase 4: Frontend UI Refactor

**Goal**: Reorganize UI into clear sections and add sending account management features

**Files to modify**:
- `src-ui/src/app/components/common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component.html`
- `src-ui/src/app/components/common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component.ts`
- `src-ui/src/app/data/mail-account.ts`
- Translation files: `src-ui/src/locale/messages.en_US.xlf`, `messages.de_DE.xlf`

**Changes**:

1. **Reorganize HTML into two main sections**:
   ```html
   <!-- Receiving (IMAP) Section -->
   <h4>Receiving Configuration (IMAP)</h4>
   <div class="receiving-config">
     <!-- Existing IMAP fields: server, port, security, username, password, etc. -->
   </div>
   
   <!-- Sending (SMTP) Section -->
   <h4>Sending Configuration (SMTP)</h4>
   <div class="sending-config">
     <app-input-check
       [(ngModel)]="object.use_for_sending"
       (ngModelChange)="onSendingToggle()"
       i18n-title
       title="Use for sending emails"
       i18n-hint
       hint="Enable this account for sending emails (only one account can be enabled at a time)"
     ></app-input-check>
     
     <div *ngIf="object.use_for_sending">
       <app-input-text
         [(ngModel)]="object.from_address"
         i18n-title
         title="From address"
         i18n-hint
         hint="Email address to use in the 'From' field. For shared mailboxes, enter the shared mailbox address here."
       ></app-input-text>
       
       <app-input-text
         [(ngModel)]="object.smtp_server"
         i18n-title
         title="SMTP Server"
       ></app-input-text>
       
       <app-input-number
         [(ngModel)]="object.smtp_port"
         i18n-title
         title="SMTP Port"
       ></app-input-number>
       
       <app-input-select
         [(ngModel)]="object.smtp_security"
         i18n-title
         title="Security"
         [items]="[
           {id: 'SSL', name: 'SSL'},
           {id: 'STARTTLS', name: 'STARTTLS'},
           {id: 'NONE', name: 'None'}
         ]"
       ></app-input-select>
       
       <!-- Show password fields only for non-OAuth accounts -->
       <div *ngIf="object.account_type !== 'oauth'">
         <app-input-text
           [(ngModel)]="object.smtp_username"
           i18n-title
           title="SMTP Username"
           i18n-hint
           hint="Leave blank to use the same username as IMAP"
         ></app-input-text>
         
         <app-input-text
           [(ngModel)]="object.smtp_password"
           type="password"
           i18n-title
           title="SMTP Password"
         ></app-input-text>
       </div>
       
       <!-- Info box for OAuth accounts -->
       <div *ngIf="object.account_type === 'oauth'" class="alert alert-info">
         <i class="fas fa-info-circle"></i>
         <span i18n>This OAuth account will use XOAUTH2 authentication for SMTP. You can customize the server settings if needed.</span>
       </div>
     </div>
   </div>
   ```

2. **Add TypeScript logic**:
   ```typescript
   currentSendingAccount: MailAccount | null = null;
   showSendingWarning = false;
   
   ngOnInit() {
     super.ngOnInit();
     
     // Load current sending account
     this.mailAccountService.listAll().subscribe(accounts => {
       this.currentSendingAccount = accounts.find(a => a.use_for_sending && a.id !== this.object?.id);
     });
     
     // Set default SMTP values based on account type
     if (this.object.use_for_sending && !this.object.smtp_server) {
       this.setDefaultSmtpConfig();
     }
   }
   
   setDefaultSmtpConfig() {
     if (this.object.account_type === 'oauth') {
       if (this.object.username.includes('@gmail')) {
         this.object.smtp_server = 'smtp.gmail.com';
         this.object.smtp_port = 587;
         this.object.smtp_security = 'STARTTLS';
       } else if (this.object.username.includes('@') && 
                  (this.object.username.includes('outlook') || 
                   this.object.username.includes('office365') ||
                   this.object.username.includes('hotmail'))) {
         this.object.smtp_server = 'smtp.office365.com';
         this.object.smtp_port = 587;
         this.object.smtp_security = 'STARTTLS';
       }
     }
   }
   
   onSendingToggle() {
     if (this.object.use_for_sending && this.currentSendingAccount) {
       this.showSendingWarning = true;
     } else {
       this.showSendingWarning = false;
     }
     
     // Set defaults when enabling
     if (this.object.use_for_sending) {
       this.setDefaultSmtpConfig();
     }
   }
   
   // Show warning dialog before save
   save() {
     if (this.showSendingWarning) {
       const message = this.currentSendingAccount 
         ? `Warning: Setting this option will make this account the only sending account and will disable sending for: "${this.currentSendingAccount.name}"`
         : `Warning: Setting this option will make this account the only sending account and will override the settings configured in environment variables.`;
       
       if (!confirm(message)) {
         return;
       }
     }
     
     super.save();
   }
   ```

3. **Update TypeScript interface** in `mail-account.ts`:
   ```typescript
   export interface MailAccount {
     // ... existing fields ...
     use_for_sending?: boolean
     from_address?: string
     smtp_server?: string
     smtp_port?: number
     smtp_security?: 'SSL' | 'STARTTLS' | 'NONE'
     smtp_username?: string
     smtp_password?: string
   }
   ```

4. **Add display of current sending account**:
   - In mail accounts list view, show badge/indicator for the account with `use_for_sending=True`
   - In admin settings, show info message: "Current sending account: [Account Name]" or "Using environment variables"

5. **Update translations**:
   - Add German translations for all new strings
   - Update English strings for clarity

**Testing considerations**:
- Test OAuth account shows pre-filled SMTP defaults
- Test traditional account shows password fields
- Test warning dialog appears when changing sending account
- Test current sending account is displayed in UI
- Test account badge/indicator in list view

---

### Phase 5: Update All EMAIL_ENABLED Checks

**Goal**: Ensure all places that check EMAIL_ENABLED also consider mail accounts

**Files to check/modify**:
- `src/documents/signals/handlers.py` (already fixed)
- `src/documents/views.py` (already fixed)
- Any other files that reference `settings.EMAIL_ENABLED`

**Changes**:

1. **Search for all EMAIL_ENABLED references**:
   ```bash
   grep -r "EMAIL_ENABLED" src/
   ```

2. **Update each check to include mail account check**:
   ```python
   # Before:
   if settings.EMAIL_ENABLED:
       
   # After:
   from paperless_mail.mail_oauth import get_sending_mail_account
   if settings.EMAIL_ENABLED or get_sending_mail_account() is not None:
   ```

3. **Update email backend configuration**:
   - In `settings.py`, set `EMAIL_BACKEND` to point to new `MailAccountEmailBackend`
   - OR: Dynamically set backend in email sending code

**Testing considerations**:
- Test all email-related features work with mail account configuration
- Test all email-related features still work with env var configuration
- Test graceful handling when neither is configured

---

### Phase 6: Documentation and Migration Guide

**Goal**: Document the new feature and provide migration instructions

**Files to create/modify**:
- `RKC_CUSTOMIZATIONS.md` (add v1.1.0 entry)
- `IMPL_SMTP_SENDING_REFACTOR.md` (this document - mark as complete)
- User-facing documentation (if exists)

**Changes**:

1. **Update RKC_CUSTOMIZATIONS.md**:
   ```markdown
   ## v1.1.0 - SMTP Email Sending via Mail Accounts
   
   ### Overview
   Extended email sending to support both OAuth2 and traditional SMTP authentication
   through Mail Accounts, with flexible server configuration.
   
   ### Features
   - Configure SMTP sending directly in Mail Accounts (Settings > Mail > Mail Accounts)
   - Support for OAuth2 XOAUTH2 authentication (Gmail, Office365)
   - Support for traditional SMTP password authentication
   - Custom SMTP server, port, and security settings
   - Only one sending account can be enabled at a time
   - Environment variables remain as fallback option
   - UI shows current sending account configuration
   
   ### Migration from v1.0.18
   
   If you have an existing OAuth2 account with `use_for_sending=True`:
   - The migration will automatically populate SMTP server settings
   - Your configuration will continue to work without changes
   - You can now customize SMTP settings if needed
   
   If you use environment variables (`EMAIL_HOST`, etc.):
   - No changes required
   - You can optionally migrate to Mail Account configuration
   - Mail Account settings take precedence over env vars
   
   ### Files Modified
   - Backend: models, serializers, views, email backend
   - Frontend: mail account edit dialog, list display
   - Database: new migration for SMTP fields
   
   ### Configuration
   
   #### Using Mail Accounts (Recommended)
   1. Go to Settings > Mail > Mail Accounts
   2. Create or edit a mail account
   3. In "Sending Configuration (SMTP)" section:
      - Enable "Use for sending emails"
      - Configure From address
      - Configure SMTP settings (or use defaults)
   4. Save
   
   #### Using Environment Variables (Legacy)
   Set in your environment or `.env`:
   ```
   EMAIL_HOST=smtp.example.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=true
   EMAIL_HOST_USER=user@example.com
   EMAIL_HOST_PASSWORD=password
   DEFAULT_FROM_EMAIL=noreply@example.com
   ```
   
   ### API Changes
   
   #### MailAccount Model
   New fields:
   - `smtp_server` (CharField, optional)
   - `smtp_port` (IntegerField, optional)
   - `smtp_security` (CharField: 'SSL', 'STARTTLS', 'NONE', optional)
   - `smtp_username` (CharField, optional)
   - `smtp_password` (CharField, optional)
   
   #### Only One Sending Account
   When setting `use_for_sending=True` on an account, all other accounts
   automatically have `use_for_sending` set to `False`.
   
   ### Testing
   
   Test OAuth2 sending:
   1. Configure Gmail OAuth account with sending enabled
   2. Trigger a workflow with email action
   3. Check email is sent from correct address
   
   Test traditional SMTP sending:
   1. Configure traditional SMTP account with sending enabled
   2. Trigger a workflow with email action
   3. Check email is sent via configured SMTP server
   
   Test fallback to env vars:
   1. Disable sending on all mail accounts
   2. Ensure EMAIL_HOST etc. are set
   3. Trigger email action
   4. Check email is sent via env var configuration
   ```

2. **Create migration guide** for existing users:
   - Document breaking changes (none expected)
   - Document new features
   - Provide screenshots of new UI
   - Document troubleshooting steps

3. **Update IMPL_OAUTH_MAIL_SENDING.md**:
   - Mark as superseded by this refactor
   - Reference this document

**Testing considerations**:
- Review documentation for accuracy
- Test examples in documentation
- Ensure migration guide is complete

---

## Implementation Order

1. **Phase 1**: Database schema changes (blocking for all other phases)
2. **Phase 2**: Backend enforcement (can be done in parallel with Phase 3)
3. **Phase 3**: Backend authentication support (depends on Phase 1)
4. **Phase 4**: Frontend UI (depends on Phases 1-3)
5. **Phase 5**: Update EMAIL_ENABLED checks (can be done anytime)
6. **Phase 6**: Documentation (done last)

## Testing Strategy

### Unit Tests
- Model validation for new fields
- Only one sending account enforcement
- SMTP configuration defaults
- Email backend selection logic

### Integration Tests
- End-to-end email sending with OAuth2
- End-to-end email sending with traditional SMTP
- Fallback to env vars when no account configured
- Workflow email actions with different configurations

### Manual Tests
- UI workflow for enabling sending on different accounts
- Warning dialogs appear correctly
- Current sending account displayed correctly
- SMTP fields pre-filled appropriately for OAuth accounts

## Rollback Plan

If issues arise:
1. All env var configuration still works as before
2. Can disable mail account sending and fall back to env vars
3. Can roll back database migration (though may lose SMTP config data)
4. Frontend changes are additive (no removed functionality)

## Future Enhancements

- Multiple sending accounts with automatic selection based on rules
- Per-correspondent FROM address configuration
- Email sending statistics per account
- Test send button in UI
- Import/export of account configurations
- Encrypted password storage for SMTP passwords

## Version

**Target Version**: v1.1.0  
**Based on**: v1.0.18  
**Status**: Planning Phase
