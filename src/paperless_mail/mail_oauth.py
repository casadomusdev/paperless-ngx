"""
RKC: Mail Account SMTP Email Backend (v1.1.0)
Extends Django's SMTP backend to support both OAuth2 XOAUTH2 and traditional SMTP authentication.
Replaces the OAuth2-only implementation from v1.0.18.
"""
import base64
import logging
from smtplib import SMTP, SMTP_SSL

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend

from paperless_mail.models import MailAccount
from paperless_mail.oauth import PaperlessMailOAuth2Manager

logger = logging.getLogger("paperless_mail")


class MailAccountEmailBackend(DjangoSMTPBackend):
    """
    SMTP email backend that uses MailAccount configuration.
    Supports both OAuth2 XOAUTH2 and traditional password authentication.
    
    Automatically refreshes OAuth2 tokens if expired before sending.
    """
    
    def __init__(self, mail_account: MailAccount, **kwargs):
        """
        Initialize with a MailAccount for SMTP configuration.
        
        Args:
            mail_account: MailAccount instance with SMTP settings
            **kwargs: Additional backend parameters
        """
        self.mail_account = mail_account
        
        # Use configured SMTP settings or defaults
        host = mail_account.smtp_server or self._get_default_smtp_server()
        port = mail_account.smtp_port or self._get_default_smtp_port()
        
        # Determine SSL/TLS settings
        security = mail_account.smtp_security or self._get_default_smtp_security()
        use_ssl = (security == 'SSL')
        use_tls = (security == 'STARTTLS')
        
        # For OAuth accounts, we don't use password in the traditional sense
        # For traditional accounts, use smtp_password or fall back to main password
        if self._is_oauth_account():
            password = None  # OAuth2 uses tokens, not passwords
            username = mail_account.username
        else:
            password = mail_account.smtp_password or mail_account.password
            username = mail_account.smtp_username or mail_account.username
        
        # Initialize parent with account settings
        super().__init__(
            host=host,
            port=port,
            username=username,
            password=password,
            use_ssl=use_ssl,
            use_tls=use_tls,
            fail_silently=kwargs.get('fail_silently', False),
            **kwargs
        )
    
    def _is_oauth_account(self) -> bool:
        """Check if this is an OAuth account"""
        return self.mail_account.account_type in [
            MailAccount.MailAccountType.GMAIL_OAUTH,
            MailAccount.MailAccountType.OUTLOOK_OAUTH,
        ]
    
    def _get_default_smtp_server(self) -> str:
        """Get default SMTP server based on account type"""
        if self.mail_account.account_type == MailAccount.MailAccountType.GMAIL_OAUTH:
            return 'smtp.gmail.com'
        elif self.mail_account.account_type == MailAccount.MailAccountType.OUTLOOK_OAUTH:
            return 'smtp.office365.com'
        else:
            # Try to derive from IMAP server
            return self.mail_account.imap_server.replace('imap', 'smtp')
    
    def _get_default_smtp_port(self) -> int:
        """Get default SMTP port based on security setting"""
        security = self.mail_account.smtp_security
        if security == 'SSL':
            return 465
        elif security == 'STARTTLS' or security is None:
            return 587
        else:  # NONE
            return 25
    
    def _get_default_smtp_security(self) -> str:
        """Get default SMTP security protocol"""
        return 'STARTTLS'  # Most common default
        
    def open(self):
        """
        Open SMTP connection with authentication.
        For OAuth2 accounts: Refreshes token and uses XOAUTH2.
        For traditional accounts: Uses standard username/password.
        """
        if self.connection:
            return False
        
        # Check if this is an OAuth account
        if self._is_oauth_account():
            return self._open_oauth()
        else:
            return self._open_traditional()
    
    def _open_oauth(self):
        """Open connection with OAuth2 XOAUTH2 authentication"""
        logger.info(f"[SMTP] Opening OAuth2 connection for account: {self.mail_account.name}")
        logger.debug(f"[SMTP] Username: {self.username}")
        logger.debug(f"[SMTP] Server: {self.host}:{self.port}")
        logger.debug(f"[SMTP] Security: {'SSL' if self.use_ssl else 'STARTTLS' if self.use_tls else 'NONE'}")
            
        # Refresh token if needed
        oauth_manager = PaperlessMailOAuth2Manager()
        if not oauth_manager.refresh_account_oauth_token(self.mail_account):
            logger.error(f"Failed to refresh OAuth2 token for {self.mail_account.name}")
            raise Exception("OAuth2 token refresh failed")
        
        # Reload account to get fresh token
        self.mail_account.refresh_from_db()
        
        try:
            # Establish connection
            if self.use_ssl:
                self.connection = SMTP_SSL(self.host, self.port, timeout=self.timeout)
            else:
                self.connection = SMTP(self.host, self.port, timeout=self.timeout)
                
            if self.use_tls:
                self.connection.ehlo()
                self.connection.starttls()
                self.connection.ehlo()
            
            # Authenticate with XOAUTH2
            auth_string = self._build_xoauth2_string(
                self.mail_account.username,
                self.mail_account.password  # This is the access token
            )
            
            logger.debug(f"[SMTP] Attempting XOAUTH2 authentication")
            code, resp = self.connection.auth('XOAUTH2', lambda: auth_string)
            
            if code != 235:  # 235 = Authentication successful
                logger.error(f"OAuth2 SMTP authentication failed with code {code}: {resp}")
                raise Exception(f"OAuth2 authentication failed: {code} {resp}")
            
            logger.info(f"OAuth2 SMTP connection established for {self.mail_account.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to establish OAuth2 SMTP connection: {e}")
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
                self.connection = None
            raise
    
    def _open_traditional(self):
        """Open connection with traditional username/password authentication"""
        logger.info(f"[SMTP] Opening traditional connection for account: {self.mail_account.name}")
        logger.debug(f"[SMTP] Username: {self.username}")
        logger.debug(f"[SMTP] Server: {self.host}:{self.port}")
        logger.debug(f"[SMTP] Security: {'SSL' if self.use_ssl else 'STARTTLS' if self.use_tls else 'NONE'}")
        
        # Use Django's default SMTP backend open() method for traditional auth
        try:
            result = super().open()
            if result:
                logger.info(f"Traditional SMTP connection established for {self.mail_account.name}")
            return result
        except Exception as e:
            logger.error(f"Failed to establish traditional SMTP connection: {e}")
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
        MailAccount with use_for_sending=True (any type), or None if not configured
    """
    # RKC: v1.1.0 - Now supports ALL account types, not just OAuth
    return MailAccount.objects.filter(use_for_sending=True).first()


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
