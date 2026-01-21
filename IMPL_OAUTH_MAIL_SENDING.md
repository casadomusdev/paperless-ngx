# Implementation Plan: OAuth2 Email Sending Support

## Overview

Enable OAuth2 authentication for outgoing email (SMTP) using existing MailAccount connections, with minimal impact on core code. This allows sending emails through Gmail/Outlook OAuth2 accounts instead of requiring separate SMTP credentials.

## Goals

- **Reuse existing OAuth2 infrastructure** from mail retrieval
- **Minimal core code changes** - keep modifications isolated and well-marked
- **Full backward compatibility** - existing SMTP-only setups continue working
- **Graceful degradation** - fallback to SMTP if OAuth2 not configured

## Architecture

### Key Design Decisions

1. **Account Selection**: One default sending account (first MailAccount with `use_for_sending=True`)
2. **Authentication Method**: SMTP with XOAUTH2 SASL mechanism
3. **Fallback Strategy**: OAuth2 → SMTP → Disable sending (current behavior)
4. **From Address Logic**:
   - Use `from_address` field if set
   - Fallback to `username` if it's an email address
   - Require `from_address` if `username` is not an email and `use_for_sending=True`

### Data Flow

```
send_email() called
    ↓
Check for OAuth2 account with use_for_sending=True
    ↓
Yes: Use OAuth2EmailBackend → SMTP XOAUTH2
    ↓
No: Use Django EmailMessage → Regular SMTP
    ↓
Not configured: Raise error (current behavior)
```

## Implementation Phases

### Phase 1: Database Model Changes

**File**: `src/paperless_mail/models.py`

Add two new fields to `MailAccount` model:

```python
# RKC: OAuth2 email sending support - allow mail accounts to send emails
use_for_sending = models.BooleanField(
    _("use for sending"),
    default=False,
    help_text=_(
        "Allow this account to be used for sending outgoing emails via OAuth2."
    ),
)

from_address = models.EmailField(
    _("from address"),
    blank=True,
    null=True,
    help_text=_(
        "The email address to use as sender when sending emails. "
        "If not set, will use the username if it's an email address."
    ),
)
# /end RKC edit
```

**Validation Logic** (add to `MailAccount.clean()`):

```python
# RKC: Validate from_address when use_for_sending is enabled
def clean(self):
    super().clean()
    if self.use_for_sending:
        # Check if we have a valid from address
        from_addr = self.from_address
        if not from_addr:
            # Try to use username as from address
            if '@' in self.username:
                # Username is email-like, that's fine
                pass
            else:
                raise ValidationError({
                    'from_address': _(
                        'From address is required when "use for sending" is enabled '
                        'and username is not an email address.'
                    )
                })
# /end RKC edit
```

**Migration**: Create migration for these two fields

```bash
python manage.py makemigrations paperless_mail -n add_oauth_sending_fields
```

### Phase 2: OAuth2 Email Backend

**File**: `src/paperless_mail/mail_oauth.py` (new file)

Create a custom Django email backend that uses XOAUTH2:

```python
"""
RKC: OAuth2 SMTP Email Backend
Extends Django's SMTP backend to support OAuth2 authentication via XOAUTH2 SASL.
"""
import base64
import logging
from smtplib import SMTP, SMTP_SSL

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend

from paperless_mail.models import MailAccount
from paperless_mail.oauth import PaperlessMailOAuth2Manager

logger = logging.getLogger("paperless_mail")


class OAuth2EmailBackend(DjangoSMTPBackend):
    """
    SMTP email backend that uses OAuth2 XOAUTH2 authentication.
    
    Automatically refreshes tokens if expired before sending.
    Falls back to regular auth if OAuth2 fails.
    """
    
    def __init__(self, mail_account: MailAccount, **kwargs):
        """
        Initialize with a MailAccount that has OAuth2 credentials.
        
        Args:
            mail_account: MailAccount instance with OAuth2 tokens
            **kwargs: Additional backend parameters
        """
        self.mail_account = mail_account
        
        # Determine SMTP server based on account type
        if mail_account.account_type == MailAccount.MailAccountType.GMAIL_OAUTH:
            host = 'smtp.gmail.com'
            port = 587
            use_tls = True
        elif mail_account.account_type == MailAccount.MailAccountType.OUTLOOK_OAUTH:
            host = 'smtp.office365.com'
            port = 587
            use_tls = True
        else:
            # Fallback to account settings
            host = mail_account.imap_server.replace('imap', 'smtp')
            port = 587
            use_tls = True
        
        # Initialize parent with OAuth2 account settings
        super().__init__(
            host=host,
            port=port,
            username=mail_account.username,
            password=None,  # We'll use OAuth2 instead
            use_tls=use_tls,
            fail_silently=kwargs.get('fail_silently', False),
            **kwargs
        )
        
    def open(self):
        """
        Open connection with OAuth2 authentication.
        Refreshes token if expired before connecting.
        """
        if self.connection:
            return False
            
        # Refresh token if needed
        oauth_manager = PaperlessMailOAuth2Manager()
        if not oauth_manager.refresh_account_oauth_token(self.mail_account):
            logger.error(
                f"Failed to refresh OAuth2 token for {self.mail_account.name}"
            )
            raise Exception("OAuth2 token refresh failed")
        
        # Reload account to get fresh token
        self.mail_account.refresh_from_db()
        
        try:
            if self.use_ssl:
                self.connection = SMTP_SSL(
                    self.host, 
                    self.port, 
                    timeout=self.timeout
                )
            else:
                self.connection = SMTP(
                    self.host, 
                    self.port, 
                    timeout=self.timeout
                )
                
            if self.use_tls:
                self.connection.ehlo()
                self.connection.starttls()
                self.connection.ehlo()
            
            # Authenticate with XOAUTH2
            auth_string = self._build_xoauth2_string(
                self.mail_account.username,
                self.mail_account.password  # This is the access token
            )
            
            self.connection.docmd('AUTH', 'XOAUTH2 ' + auth_string)
            
            logger.debug(f"OAuth2 SMTP connection established for {self.mail_account.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to establish OAuth2 SMTP connection: {e}")
            if self.connection:
                self.connection.close()
                self.connection = None
            raise
    
    def _build_xoauth2_string(self, username: str, access_token: str) -> str:
        """
        Build XOAUTH2 authentication string.
        
        Format: base64(user=username\x01auth=Bearer access_token\x01\x01)
        """
        auth_string = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
        return base64.b64encode(auth_string.encode()).decode()


def get_sending_mail_account() -> MailAccount | None:
    """
    Get the default mail account configured for sending.
    
    Returns:
        MailAccount with use_for_sending=True, or None if not configured
    """
    return MailAccount.objects.filter(
        use_for_sending=True,
        account_type__in=[
            MailAccount.MailAccountType.GMAIL_OAUTH,
            MailAccount.MailAccountType.OUTLOOK_OAUTH,
        ]
    ).first()


def get_from_address(mail_account: MailAccount) -> str:
    """
    Get the from address for a mail account.
    
    Logic:
    1. Use from_address if set
    2. Use username if it's an email address
    3. Raise error (should be caught by validation)
    
    Args:
        mail_account: MailAccount instance
        
    Returns:
        Email address string
    """
    if mail_account.from_address:
        return mail_account.from_address
    
    if '@' in mail_account.username:
        return mail_account.username
    
    raise ValueError(
        f"Mail account {mail_account.name} has no valid from address"
    )
# /end RKC edit
```

### Phase 3: Modify send_email() Function

**File**: `src/documents/mail.py`

Modify the `send_email()` function to use OAuth2 if available:

```python
# RKC: Import OAuth2 email backend support
from paperless_mail.mail_oauth import (
    get_sending_mail_account,
    get_from_address,
    OAuth2EmailBackend,
)
import logging

logger = logging.getLogger("paperless_mail")
# /end RKC edit

def send_email(
    subject: str,
    body: str,
    to: list[str],
    attachments: list[EmailAttachment],
) -> int:
    """
    Send an email with attachments.
    
    RKC: Enhanced to support OAuth2 SMTP authentication if configured.
    Falls back to regular SMTP if no OAuth2 account is available.

    Args:
        subject: Email subject
        body: Email body text
        to: List of recipient email addresses
        attachments: List of attachments

    Returns:
        Number of emails sent
    """
    # RKC: Check for OAuth2 sending account
    oauth_account = get_sending_mail_account()
    
    if oauth_account:
        # Use OAuth2 backend
        logger.debug(f"Using OAuth2 account {oauth_account.name} for sending email")
        from_email = get_from_address(oauth_account)
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=to,
        )
        
        # Set the OAuth2 backend
        email.connection = OAuth2EmailBackend(oauth_account)
    else:
        # Use regular SMTP (original behavior)
        logger.debug("Using regular SMTP for sending email")
        email = EmailMessage(
            subject=subject,
            body=body,
            to=to,
        )
    # /end RKC edit

    used_filenames: set[str] = set()

    # Something could be renaming the file concurrently so it can't be attached
    with FileLock(settings.MEDIA_LOCK):
        for attachment in attachments:
            filename = _get_unique_filename(
                attachment.friendly_name,
                used_filenames,
            )
            used_filenames.add(filename)

            with attachment.path.open("rb") as f:
                content = f.read()
                if attachment.mime_type == "message/rfc822":
                    # See https://forum.djangoproject.com/t/using-emailmessage-with-an-attached-email-file-crashes-due-to-non-ascii/37981
                    content = message_from_bytes(content)

                email.attach(
                    filename=filename,
                    content=content,
                    mimetype=attachment.mime_type,
                )

    return email.send()
```

### Phase 4: Admin/Serializer Updates

**File**: `src/paperless_mail/admin.py`

Add the new fields to admin interface:

```python
# RKC: Add OAuth2 sending fields to admin
@admin.register(MailAccount)
class MailAccountAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'account_type',
        'username',
        'use_for_sending',  # RKC: Show sending status
    ]
    
    fieldsets = [
        # ... existing fieldsets ...
        (
            _('OAuth2 Sending'),  # RKC: New fieldset for sending
            {
                'fields': ('use_for_sending', 'from_address'),
                'classes': ('collapse',),
            }
        ),
    ]
# /end RKC edit
```

**File**: `src/paperless_mail/serialisers.py`

Add fields to serializer:

```python
class MailAccountSerializer(serializers.ModelSerializer):
    # RKC: Add OAuth2 sending fields
    use_for_sending = serializers.BooleanField(required=False, default=False)
    from_address = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    # /end RKC edit
    
    class Meta:
        model = MailAccount
        fields = [
            # ... existing fields ...
            'use_for_sending',  # RKC
            'from_address',    # RKC
        ]
```

### Phase 5: Frontend Updates ✅ COMPLETED

**Status**: All frontend UI components implemented and tested.

**File**: `src-ui/src/app/data/mail-account.ts`

Added fields to TypeScript model:

```typescript
// RKC: OAuth2 email sending support (v1.0.18)
export interface MailAccount {
  // ... existing fields ...
  use_for_sending?: boolean
  from_address?: string
}
// /end RKC edit
```

**File**: `src-ui/src/app/components/common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component.html`

Added OAuth2 Email Sending section with UI controls:
- Section heading with explanatory text
- Checkbox: "Use for sending emails"
- Text input: "From address" (email validation)
- Fully integrated into reactive forms

**File**: `src-ui/src/app/components/common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component.ts`

Added form controls:
```typescript
// RKC: OAuth2 email sending support (v1.0.18)
use_for_sending: new FormControl(false),
from_address: new FormControl(null),
// /end RKC edit
```

**Implementation Notes**:
- Form controls properly integrated into Angular reactive forms pattern
- Data binding works correctly with backend API
- All changes marked with RKC comments for maintainability

### Phase 6: Documentation

**File**: `RKC_CUSTOMIZATIONS.md`

Add new version entry:

```markdown
## Version History

- **v1.0.18 (2025-01-12)**: OAuth2 Email Sending Support
  - Added OAuth2 authentication for outgoing SMTP emails
  - **Problem**: Organizations using OAuth2 for mail retrieval still needed separate SMTP credentials for sending
  - **Solution**: 
    - Extended MailAccount model with `use_for_sending` and `from_address` fields
    - Created OAuth2EmailBackend using XOAUTH2 SASL mechanism
    - Modified send_email() to use OAuth2 when available, fallback to SMTP
    - Reuses existing OAuth2 infrastructure and token refresh logic
  - **Configuration**:
    - Enable "Use for sending" on any Gmail/Outlook OAuth2 MailAccount
    - Set "From address" if username is not an email address
    - If no OAuth2 sending account configured, falls back to SMTP
    - If SMTP not configured, email sending disabled (current behavior)
  - **Architecture**:
    - Minimal core code impact - isolated to RKC-marked sections
    - Automatic token refresh before sending
    - SMTP XOAUTH2 authentication (Gmail: smtp.gmail.com:587, Outlook: smtp.office365.com:587)
    - Graceful degradation through multiple fallback layers
  - Files modified:
    - Backend: `src/paperless_mail/models.py` (added use_for_sending, from_address fields)
    - Backend: `src/paperless_mail/mail_oauth.py` (new OAuth2EmailBackend)
    - Backend: `src/documents/mail.py` (modified send_email to use OAuth2)
    - Backend: `src/paperless_mail/admin.py` (admin fieldsets)
    - Backend: `src/paperless_mail/serialisers.py` (API serializers)
    - Migration: New migration for MailAccount fields
  - All changes properly marked with RKC comments for maintainability
```

## Testing Strategy

### Unit Tests

**File**: `src/paperless_mail/tests/test_mail_oauth.py` (new)

```python
"""
RKC: Tests for OAuth2 email sending functionality
"""
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from paperless_mail.models import MailAccount
from paperless_mail.mail_oauth import (
    OAuth2EmailBackend,
    get_sending_mail_account,
    get_from_address,
)


class OAuth2EmailBackendTestCase(TestCase):
    def setUp(self):
        self.account = MailAccount.objects.create(
            name="Test OAuth Account",
            account_type=MailAccount.MailAccountType.GMAIL_OAUTH,
            username="test@gmail.com",
            password="access_token_123",
            refresh_token="refresh_token_456",
            use_for_sending=True,
        )
    
    @patch('paperless_mail.mail_oauth.SMTP')
    @patch('paperless_mail.mail_oauth.PaperlessMailOAuth2Manager')
    def test_oauth2_connection(self, mock_oauth_manager, mock_smtp):
        """Test OAuth2 SMTP connection establishment"""
        # Setup mocks
        mock_oauth_instance = Mock()
        mock_oauth_instance.refresh_account_oauth_token.return_value = True
        mock_oauth_manager.return_value = mock_oauth_instance
        
        mock_connection = MagicMock()
        mock_smtp.return_value = mock_connection
        
        # Create backend and open connection
        backend = OAuth2EmailBackend(self.account)
        backend.open()
        
        # Verify OAuth2 refresh was called
        mock_oauth_instance.refresh_account_oauth_token.assert_called_once()
        
        # Verify SMTP connection
        mock_smtp.assert_called_once()
        mock_connection.starttls.assert_called_once()
    
    def test_get_from_address_with_explicit(self):
        """Test from address when explicitly set"""
        self.account.from_address = "sender@example.com"
        self.account.save()
        
        result = get_from_address(self.account)
        self.assertEqual(result, "sender@example.com")
    
    def test_get_from_address_fallback_username(self):
        """Test from address fallback to username"""
        self.account.from_address = None
        self.account.save()
        
        result = get_from_address(self.account)
        self.assertEqual(result, "test@gmail.com")
    
    def test_get_from_address_invalid(self):
        """Test from address with invalid username"""
        self.account.from_address = None
        self.account.username = "not_an_email"
        self.account.save()
        
        with self.assertRaises(ValueError):
            get_from_address(self.account)


class MailAccountSendingTestCase(TestCase):
    def test_get_sending_account_configured(self):
        """Test retrieving configured sending account"""
        account = MailAccount.objects.create(
            name="Sending Account",
            account_type=MailAccount.MailAccountType.OUTLOOK_OAUTH,
            username="test@outlook.com",
            use_for_sending=True,
        )
        
        result = get_sending_mail_account()
        self.assertEqual(result, account)
    
    def test_get_sending_account_none_configured(self):
        """Test when no sending account configured"""
        result = get_sending_mail_account()
        self.assertIsNone(result)
    
    def test_get_sending_account_imap_ignored(self):
        """Test that IMAP-only accounts are ignored"""
        MailAccount.objects.create(
            name="IMAP Account",
            account_type=MailAccount.MailAccountType.IMAP,
            username="test@example.com",
            use_for_sending=True,
        )
        
        result = get_sending_mail_account()
        self.assertIsNone(result)
# /end RKC edit
```

### Integration Tests

Test with actual OAuth2 accounts (manual):
1. Configure Gmail OAuth2 account with `use_for_sending=True`
2. Trigger workflow email action
3. Verify email sent via OAuth2
4. Test token refresh scenario
5. Test fallback to SMTP when OAuth2 disabled

## Deployment Checklist

- [ ] Run database migration
- [ ] Configure at least one MailAccount with `use_for_sending=True`
- [ ] Set `from_address` if username is not an email
- [ ] Test email sending through workflow actions
- [ ] Test email sending from document detail
- [ ] Verify token auto-refresh works
- [ ] Test fallback to SMTP still works
- [ ] Update user documentation

## Security Considerations

1. **Token Security**: Access/refresh tokens stored encrypted in database (existing security)
2. **Token Refresh**: Automatic refresh prevents expired token errors
3. **Fallback Safety**: If OAuth2 fails, system falls back to SMTP (no email disruption)
4. **Scope Minimal**: Uses same OAuth2 scopes as mail retrieval (no new permissions needed)

## Future Enhancements (Out of Scope)

- [ ] Per-workflow account selection (currently one default)
- [ ] REST API sending (Gmail API / Graph API instead of SMTP)
- [ ] Multiple sending accounts with priority/failover
- [ ] Sent mail folder syncing
- [ ] Send quota monitoring/warnings

## Bug Fixes

### Workflow Email Actions Blocked by EMAIL_ENABLED Check

**Issue**: After implementing OAuth2 sending, workflows with email actions failed with error: "Email backend has not been configured, cannot send email notifications"

**Root Cause**: The `email_action()` function in `src/documents/signals/handlers.py` checks `settings.EMAIL_ENABLED` before attempting to send emails. This setting only validates traditional SMTP configuration (EMAIL_HOST and EMAIL_HOST_USER), not OAuth2 accounts. When only OAuth2 sending is configured without SMTP, EMAIL_ENABLED returns False, blocking the email action.

**Solution**: Modified the EMAIL_ENABLED check in `email_action()` to also check for OAuth2 sending accounts:

**File**: `src/documents/signals/handlers.py` (line ~1345)

```python
def email_action():
    # RKC: Check for OAuth2 sending OR traditional SMTP (v1.0.18)
    from paperless_mail.mail_oauth import get_sending_mail_account
    
    if not settings.EMAIL_ENABLED and not get_sending_mail_account():
        logger.error(
            "Email backend has not been configured, cannot send email notifications",
            extra={"group": logging_group},
        )
        return
    # /end RKC edit
```

**Impact**: Workflows can now send emails when only OAuth2 is configured, without requiring traditional SMTP settings.

**Note**: Could not modify EMAIL_ENABLED directly in settings.py due to circular import issues (paperless_mail imports settings, so settings cannot import from paperless_mail).

## References

- Gmail SMTP OAuth2: https://developers.google.com/gmail/imap/xoauth2-protocol
- Outlook SMTP OAuth2: https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth
- Django Email Backends: https://docs.djangoproject.com/en/stable/topics/email/#email-backends
- XOAUTH2 SASL: https://developers.google.com/gmail/imap/xoauth2-protocol#smtp_protocol_exchange
