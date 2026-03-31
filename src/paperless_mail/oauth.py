import asyncio
import logging
import secrets
import threading
import time
from datetime import timedelta

import httpx
from django.conf import settings
from django.utils import timezone
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.clients.microsoft import MicrosoftGraphOAuth2
from httpx_oauth.oauth2 import OAuth2Token
from httpx_oauth.oauth2 import RefreshTokenError

from paperless_mail.models import MailAccount

# RKC: Process-level token cache for app-only (client_credentials) tokens (v1.2.10)
# Keyed by (client_id, tenant_id).  Stores (access_token, expiry_timestamp).
# Access token lifetime is 3600s; we refresh 5 minutes early to avoid races.
_app_token_cache: dict[tuple[str, str], tuple[str, float]] = {}
_app_token_lock = threading.Lock()
# /end RKC edit


class PaperlessMailOAuth2Manager:
    def __init__(self, state: str | None = None):
        self._gmail_client = None
        self._outlook_client = None
        self.state = state if state is not None else secrets.token_urlsafe(32)

    @property
    def gmail_client(self) -> GoogleOAuth2:
        if self._gmail_client is None:
            self._gmail_client = GoogleOAuth2(
                settings.GMAIL_OAUTH_CLIENT_ID,
                settings.GMAIL_OAUTH_CLIENT_SECRET,
            )
        return self._gmail_client

    @property
    def outlook_client(self) -> MicrosoftGraphOAuth2:
        if self._outlook_client is None:
            self._outlook_client = MicrosoftGraphOAuth2(
                settings.OUTLOOK_OAUTH_CLIENT_ID,
                settings.OUTLOOK_OAUTH_CLIENT_SECRET,
            )
        return self._outlook_client

    @property
    def oauth_callback_url(self) -> str:
        return f"{settings.OAUTH_CALLBACK_BASE_URL if settings.OAUTH_CALLBACK_BASE_URL is not None else settings.PAPERLESS_URL}{settings.BASE_URL}api/oauth/callback/"

    @property
    def oauth_redirect_url(self) -> str:
        return f"{'http://localhost:4200/' if settings.DEBUG else settings.BASE_URL}mail"  # e.g. "http://localhost:4200/mail" or "/mail"

    def get_gmail_authorization_url(self) -> str:
        return asyncio.run(
            self.gmail_client.get_authorization_url(
                redirect_uri=self.oauth_callback_url,
                scope=["https://mail.google.com/"],
                extras_params={"prompt": "consent", "access_type": "offline"},
                state=self.state,
            ),
        )

    def get_outlook_authorization_url(self) -> str:
        # RKC: v1.1.0 - Use pure Graph API scopes for both send and receive
        # Microsoft rejects mixed Exchange legacy (IMAP) and Graph API scopes
        # Bypasses Microsoft 365 Security Defaults restrictions on SMTP/IMAP AUTH
        # Multi-mailbox support: Added shared mailbox scopes for delegated permissions
        return asyncio.run(
            self.outlook_client.get_authorization_url(
                redirect_uri=self.oauth_callback_url,
                scope=[
                    "offline_access",
                    "https://graph.microsoft.com/User.Read",             # Required for /me endpoint (test function)
                    "https://graph.microsoft.com/Mail.Read",             # Mail receiving via Graph API
                    "https://graph.microsoft.com/Mail.Read.Shared",      # Read mail from shared mailboxes
                    "https://graph.microsoft.com/Mail.ReadWrite.Shared", # Modify mail in shared mailboxes (post-processing)
                    "https://graph.microsoft.com/Mail.Send",             # Mail sending via Graph API
                    "https://graph.microsoft.com/Mail.Send.Shared",      # Send from shared mailboxes
                ],
                state=self.state,
            ),
        )
        # /end RKC edit

    def get_gmail_access_token(self, code: str) -> OAuth2Token:
        return asyncio.run(
            self.gmail_client.get_access_token(
                code=code,
                redirect_uri=self.oauth_callback_url,
            ),
        )

    def get_outlook_access_token(self, code: str) -> OAuth2Token:
        return asyncio.run(
            self.outlook_client.get_access_token(
                code=code,
                redirect_uri=self.oauth_callback_url,
            ),
        )

    def refresh_account_oauth_token(self, account: MailAccount) -> bool:
        """
        Refreshes the oauth token for the given mail account.
        """
        logger = logging.getLogger("paperless_mail")
        logger.debug(f"Attempting to refresh oauth token for account {account}")
        try:
            result: OAuth2Token
            if account.account_type == MailAccount.MailAccountType.GMAIL_OAUTH:
                result = asyncio.run(
                    self.gmail_client.refresh_token(
                        refresh_token=account.refresh_token,
                    ),
                )
            elif account.account_type == MailAccount.MailAccountType.OUTLOOK_OAUTH:
                result = asyncio.run(
                    self.outlook_client.refresh_token(
                        refresh_token=account.refresh_token,
                    ),
                )
            if "refresh_token" in result:
                # Outlook returns a new refresh token on refresh, Gmail does not
                account.refresh_token = result["refresh_token"]
            account.password = result["access_token"]
            account.expiration = timezone.now() + timedelta(
                seconds=result["expires_in"],
            )
            account.save()
            logger.debug(f"Successfully refreshed oauth token for account {account}")
            return True
        except RefreshTokenError as e:
            logger.error(f"Failed to refresh oauth token for account {account}: {e}")
            return False

    def validate_state(self, state: str) -> bool:
        return settings.DEBUG or (len(state) > 0 and state == self.state)

    # RKC: App-only (client_credentials) token for personal mailbox sending (v1.2.10)
    def get_outlook_app_access_token(self) -> str:
        """
        Returns a valid Microsoft Graph API access token obtained via the
        client_credentials (app-only) flow.

        This token allows calling /users/{any-user}/sendMail for ANY licensed
        mailbox in the tenant without per-user Exchange delegation.  Requires
        the Mail.Send APPLICATION permission granted with admin consent in the
        Azure App Registration.

        Tokens are cached in-process and refreshed automatically 5 minutes
        before expiry.  Thread-safe via a module-level lock.

        Returns:
            Access token string

        Raises:
            ValueError: If PAPERLESS_OUTLOOK_OAUTH_TENANT_ID is not configured
            Exception:  If the token request to Azure AD fails
        """
        logger = logging.getLogger("paperless_mail")

        tenant_id = getattr(settings, "OUTLOOK_OAUTH_TENANT_ID", None)
        client_id = settings.OUTLOOK_OAUTH_CLIENT_ID
        client_secret = settings.OUTLOOK_OAUTH_CLIENT_SECRET

        if not tenant_id:
            raise ValueError(
                "[Graph API] PAPERLESS_OUTLOOK_OAUTH_TENANT_ID must be set when "
                "PAPERLESS_OUTLOOK_OAUTH_USE_APP_SEND=true"
            )

        cache_key = (client_id, tenant_id)
        now = time.time()

        with _app_token_lock:
            cached = _app_token_cache.get(cache_key)
            if cached:
                token, expiry = cached
                # Use cached token if it won't expire within 5 minutes
                if now < expiry - 300:
                    logger.debug("[Graph API] Using cached app-only access token")
                    return token

            # Fetch a fresh token from Azure AD
            token_url = (
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            )
            payload = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
            }

            logger.debug(
                f"[Graph API] Fetching app-only access token for tenant {tenant_id}"
            )

            try:
                with httpx.Client(timeout=15.0) as client:
                    response = client.post(token_url, data=payload)

                if response.status_code != 200:
                    try:
                        err = response.json()
                        detail = f"{err.get('error', '?')}: {err.get('error_description', response.text[:200])}"
                    except Exception:
                        detail = response.text[:200]
                    raise Exception(
                        f"[Graph API] App-only token request failed "
                        f"({response.status_code}): {detail}"
                    )

                data = response.json()
                access_token = data["access_token"]
                expires_in = int(data.get("expires_in", 3600))
                expiry_ts = now + expires_in

                _app_token_cache[cache_key] = (access_token, expiry_ts)
                logger.debug(
                    f"[Graph API] App-only token obtained, expires in {expires_in}s"
                )
                return access_token

            except httpx.HTTPError as e:
                raise Exception(
                    f"[Graph API] HTTP error fetching app-only token: {e}"
                ) from e
    # /end RKC edit
