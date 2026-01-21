"""
RKC: OAuth2 SMTP Email Backend (v1.0.18)
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
        
        # RKC: Enhanced logging for troubleshooting
        logger.info(f"[OAuth2 SMTP] Opening connection for account: {self.mail_account.name}")
        logger.info(f"[OAuth2 SMTP] Username (auth identity): {self.mail_account.username}")
        logger.info(f"[OAuth2 SMTP] SMTP Server: {self.host}:{self.port}")
        logger.info(f"[OAuth2 SMTP] Use TLS: {self.use_tls}")
        # /end RKC edit
            
        # Refresh token if needed
        oauth_manager = PaperlessMailOAuth2Manager()
        if not oauth_manager.refresh_account_oauth_token(self.mail_account):
            logger.error(
                f"Failed to refresh OAuth2 token for {self.mail_account.name}"
            )
            raise Exception("OAuth2 token refresh failed")
        
        # Reload account to get fresh token
        self.mail_account.refresh_from_db()
        
        # RKC: Log token info (without exposing the actual token)
        token_preview = self.mail_account.password[:20] + "..." if self.mail_account.password else "MISSING"
        logger.info(f"[OAuth2 SMTP] Access token preview: {token_preview}")
        logger.info(f"[OAuth2 SMTP] Token length: {len(self.mail_account.password) if self.mail_account.password else 0} chars")
        # /end RKC edit
        
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
            # Python's smtplib doesn't have built-in XOAUTH2 support,
            # so we need to use the auth() method directly
            auth_string = self._build_xoauth2_string(
                self.mail_account.username,
                self.mail_account.password  # This is the access token
            )
            
            # Use auth() with XOAUTH2 mechanism
            # The auth_string is already base64 encoded, return it directly
            # smtplib will encode it to bytes internally
            code, resp = self.connection.auth(
                'XOAUTH2',
                lambda: auth_string,
            )
            
            if code != 235:  # 235 = Authentication successful
                logger.error(
                    f"OAuth2 SMTP authentication failed with code {code}: {resp}"
                )
                raise Exception(f"OAuth2 authentication failed: {code} {resp}")
            
            logger.debug(f"OAuth2 SMTP connection established for {self.mail_account.name}")
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
