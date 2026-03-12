"""
RKC: Microsoft Graph API Email Backend (v1.2.7)
Implements email sending for Outlook OAuth accounts using Microsoft Graph API instead of SMTP.
This bypasses Security Defaults restrictions on SMTP AUTH while providing better error handling.
Sent Items are deposited in the correct mailbox: when sending as a shared mailbox, the
sendMail call is scoped to the shared mailbox user endpoint so the copy lands there, not in
the sending account's Sent Items.
"""
import base64
import logging
from typing import Any

import httpx
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage
from django.utils import timezone

from paperless_mail.models import MailAccount
from paperless_mail.oauth import PaperlessMailOAuth2Manager

logger = logging.getLogger("paperless_mail")


class OutlookGraphEmailBackend(BaseEmailBackend):
    """
    Email backend that uses Microsoft Graph API for sending emails.
    
    This backend is specifically designed for Outlook OAuth accounts and provides:
    - Compatibility with Microsoft 365 Security Defaults
    - Better error messages than SMTP
    - Support for HTML/text content, attachments, CC, BCC, reply-to
    - Automatic OAuth token refresh
    - Shared mailbox Sent Items: when from_email differs from the account username,
      sendMail is called on the shared mailbox's user endpoint so that Graph API
      deposits the Sent Items copy in that shared mailbox (not the sending account).
      Requires Mail.Send.Shared scope and Exchange "Send As" permission.
    
    Uses the Graph API endpoint: POST /v1.0/users/{username}/sendMail
    """
    
    GRAPH_BASE = "https://graph.microsoft.com/v1.0/users"
    
    def __init__(self, mail_account: MailAccount, fail_silently: bool = False, **kwargs):
        """
        Initialize the Graph API email backend.
        
        Args:
            mail_account: MailAccount instance with OAuth credentials
            fail_silently: Whether to suppress exceptions
            **kwargs: Additional parameters (for compatibility)
        """
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.mail_account = mail_account
        
        if mail_account.account_type != MailAccount.MailAccountType.OUTLOOK_OAUTH:
            raise ValueError(
                f"OutlookGraphEmailBackend requires OUTLOOK_OAUTH account type, "
                f"got {mail_account.account_type}"
            )
    
    def send_messages(self, email_messages: list[EmailMessage]) -> int:
        """
        Send one or more EmailMessage objects.
        
        Args:
            email_messages: List of Django EmailMessage objects to send
            
        Returns:
            Number of successfully sent messages
        """
        if not email_messages:
            return 0
        
        # Refresh OAuth token if needed
        oauth_manager = PaperlessMailOAuth2Manager()
        logger.debug(f"[Graph API] Checking token expiration for {self.mail_account.name}")
        
        if not oauth_manager.refresh_account_oauth_token(self.mail_account):
            logger.error(f"Failed to refresh OAuth2 token for {self.mail_account.name}")
            if not self.fail_silently:
                raise Exception("OAuth2 token refresh failed")
            return 0
        
        # Reload account to get fresh token
        self.mail_account.refresh_from_db()
        logger.debug(f"[Graph API] Token ready, expiration: {self.mail_account.expiration}")
        
        # Send each message
        sent_count = 0
        for message in email_messages:
            try:
                self._send_message(message)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send email via Graph API: {e}")
                if not self.fail_silently:
                    raise
        
        return sent_count
    
    def _get_send_endpoint(self, from_email: str | None) -> str:
        """
        Returns the correct Graph API sendMail endpoint for this message.
        
        When from_email differs from the account's own username the call is scoped
        to the shared mailbox user so Graph API stores the Sent Items copy there.
        When from_email is absent or matches the account username the sending
        account's own endpoint is used (normal behaviour).
        
        Args:
            from_email: The From address specified on the outgoing message, or None
            
        Returns:
            Full Graph API sendMail URL
        """
        from_addr = (from_email or "").strip().lower()
        account_addr = (self.mail_account.username or "").strip().lower()
        
        if from_addr and from_addr != account_addr:
            # Sending as a shared mailbox — scope the call to the shared mailbox
            # so Graph API deposits the Sent Items copy there, not in our own Sent Items
            logger.debug(
                f"[Graph API] Shared mailbox send: routing via {from_email.strip()} endpoint "
                f"(account: {self.mail_account.username})"
            )
            return f"{self.GRAPH_BASE}/{from_email.strip()}/sendMail"
        
        return f"{self.GRAPH_BASE}/{self.mail_account.username}/sendMail"

    def _send_message(self, message: EmailMessage) -> None:
        """
        Send a single email message via Graph API.
        
        Args:
            message: Django EmailMessage object
        """
        logger.info(f"[Graph API] Sending email: '{message.subject}' to {message.to}")
        
        # Resolve correct endpoint (own mailbox or shared mailbox context)
        graph_endpoint = self._get_send_endpoint(message.from_email)
        
        # Build Graph API request payload
        payload = self._build_graph_message(message)
        
        # Prepare HTTP request
        headers = {
            "Authorization": f"Bearer {self.mail_account.password}",  # Access token
            "Content-Type": "application/json",
        }
        
        # Send via Graph API
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    graph_endpoint,
                    headers=headers,
                    json=payload,
                )
                
            # Check response
            if response.status_code == 202:
                # 202 Accepted means message queued successfully
                logger.info(f"[Graph API] Email sent successfully: '{message.subject}'")
            elif response.status_code >= 400:
                # Error occurred
                error_detail = self._parse_error_response(response)
                logger.error(
                    f"[Graph API] Failed to send email: {response.status_code} - {error_detail}"
                )
                raise Exception(f"Graph API error ({response.status_code}): {error_detail}")
            else:
                # Unexpected success code
                logger.warning(
                    f"[Graph API] Unexpected response code: {response.status_code}"
                )
                    
        except httpx.HTTPError as e:
            logger.error(f"[Graph API] HTTP error: {e}")
            raise Exception(f"HTTP error sending email: {e}") from e
    
    def _build_graph_message(self, message: EmailMessage) -> dict[str, Any]:
        """
        Convert Django EmailMessage to Graph API message format.
        
        Args:
            message: Django EmailMessage object
            
        Returns:
            Dictionary in Graph API message format
        """
        # Determine content type
        content_type = "HTML" if message.content_subtype == "html" else "Text"
        
        # Build base message structure
        graph_message = {
            "message": {
                "subject": message.subject,
                "body": {
                    "contentType": content_type,
                    "content": message.body,
                },
                "toRecipients": [
                    {"emailAddress": {"address": addr}} for addr in message.to
                ],
            },
            "saveToSentItems": True,
        }
        
        # Add from address if specified (only if not empty)
        if message.from_email and message.from_email.strip():
            graph_message["message"]["from"] = {
                "emailAddress": {"address": message.from_email}
            }
        
        # Add CC recipients
        if message.cc:
            graph_message["message"]["ccRecipients"] = [
                {"emailAddress": {"address": addr}} for addr in message.cc
            ]
        
        # Add BCC recipients
        if message.bcc:
            graph_message["message"]["bccRecipients"] = [
                {"emailAddress": {"address": addr}} for addr in message.bcc
            ]
        
        # Add reply-to
        if message.reply_to:
            graph_message["message"]["replyTo"] = [
                {"emailAddress": {"address": addr}} for addr in message.reply_to
            ]
        
        # Add attachments
        if message.attachments:
            graph_message["message"]["attachments"] = []
            for attachment in message.attachments:
                graph_attachment = self._build_graph_attachment(attachment)
                if graph_attachment:
                    graph_message["message"]["attachments"].append(graph_attachment)
        
        return graph_message
    
    def _build_graph_attachment(self, attachment: tuple) -> dict[str, Any] | None:
        """
        Convert Django email attachment to Graph API attachment format.
        
        Args:
            attachment: Tuple of (filename, content, mimetype) or MIMEBase object
            
        Returns:
            Dictionary in Graph API attachment format, or None if invalid
        """
        try:
            # Django attachments can be tuples or MIMEBase objects
            if isinstance(attachment, tuple):
                filename, content, mimetype = attachment
                
                # Convert content to base64
                if isinstance(content, str):
                    content_bytes = content.encode('utf-8')
                else:
                    content_bytes = content
                
                content_base64 = base64.b64encode(content_bytes).decode('ascii')
                
                return {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": filename,
                    "contentType": mimetype or "application/octet-stream",
                    "contentBytes": content_base64,
                }
            else:
                # MIMEBase object - extract details
                logger.warning("[Graph API] MIMEBase attachment handling not fully implemented")
                return None
                
        except Exception as e:
            logger.error(f"[Graph API] Failed to process attachment: {e}")
            return None
    
    def _parse_error_response(self, response: httpx.Response) -> str:
        """
        Parse Graph API error response for meaningful error message.
        
        Args:
            response: httpx Response object with error
            
        Returns:
            Human-readable error message
        """
        try:
            error_data = response.json()
            if "error" in error_data:
                error_obj = error_data["error"]
                code = error_obj.get("code", "Unknown")
                message = error_obj.get("message", "No details")
                return f"{code}: {message}"
        except Exception:
            pass
        
        # Fallback to response text
        return response.text[:200] if response.text else "Unknown error"
# /end RKC edit
