"""
RKC: Microsoft Graph API Mail Retrieval Backend (v1.1.0)
Implements email receiving for Outlook OAuth accounts using Microsoft Graph API instead of IMAP.
This complements the Graph API sending functionality and avoids scope mixing issues.
"""
import base64
import logging
from datetime import datetime
from typing import Any

import httpx
from django.utils.timezone import is_naive
from django.utils.timezone import make_aware

from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.oauth import PaperlessMailOAuth2Manager

logger = logging.getLogger("paperless_mail")


class GraphMailMessage:
    """
    Adapter that presents Graph API message in a format compatible with imap_tools.MailMessage.
    Allows existing mail processing code to work with both IMAP and Graph API sources.
    """
    
    def __init__(self, graph_json: dict, retriever: 'OutlookGraphMailRetriever'):
        """
        Initialize Graph API message wrapper.
        
        Args:
            graph_json: Raw message data from Graph API
            retriever: Reference to retriever for fetching attachments
        """
        self._data = graph_json
        self._retriever = retriever
        self._attachments = None
        self._from_values = None
    
    @property
    def uid(self) -> str:
        """8-character hash UID for display and duplicate detection"""
        # RKC: Generate shortened 8-character display ID using SHA256 hash
        # This provides a consistent, short identifier for UI display while
        # maintaining uniqueness. Full Graph ID stored separately for API calls.
        import hashlib
        full_id = self._data['id']
        hash_digest = hashlib.sha256(full_id.encode()).hexdigest()
        return hash_digest[:8]  # 8-character hash
    
    @property
    def graph_message_id(self) -> str:
        """Full Graph API message ID for API operations"""
        # RKC: Return full Graph message ID for batch post-action processing
        # This is required by the Microsoft Graph API for all mail operations
        return self._data['id']
    
    @property
    def subject(self) -> str:
        """Email subject"""
        return self._data.get('subject', '')
    
    @property
    def from_(self) -> str:
        """Sender email address as string"""
        sender = self._data.get('from', {}).get('emailAddress', {})
        email = sender.get('address', '')
        name = sender.get('name', '')
        
        if name and name != email:
            return f"{name} <{email}>"
        return email
    
    @property
    def from_values(self):
        """Compatible with imap_tools.MailMessage.from_values"""
        if self._from_values is None:
            sender = self._data.get('from', {}).get('emailAddress', {})
            self._from_values = type('FromValues', (object,), {
                'email': sender.get('address', ''),
                'name': sender.get('name', ''),
            })()
        return self._from_values
    
    @property
    def date(self) -> datetime:
        """Parse receivedDateTime to datetime object"""
        date_str = self._data.get('receivedDateTime')
        if date_str:
            # Graph API returns ISO 8601 format: "2024-01-29T12:34:56Z"
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if is_naive(dt):
                dt = make_aware(dt)
            return dt
        return datetime.now()
    
    @property
    def to(self) -> list[str]:
        """List of recipient email addresses"""
        recipients = self._data.get('toRecipients', [])
        return [r.get('emailAddress', {}).get('address', '') for r in recipients]
    
    @property
    def cc(self) -> list[str]:
        """List of CC email addresses"""
        recipients = self._data.get('ccRecipients', [])
        return [r.get('emailAddress', {}).get('address', '') for r in recipients]
    
    @property
    def text(self) -> str:
        """Plain text body"""
        body = self._data.get('body', {})
        if body.get('contentType') == 'text':
            return body.get('content', '')
        # If HTML only, strip tags (basic)
        return ''
    
    @property
    def html(self) -> str:
        """HTML body"""
        body = self._data.get('body', {})
        if body.get('contentType') == 'html':
            return body.get('content', '')
        return ''
    
    @property
    def attachments(self) -> list['GraphMailAttachment']:
        """Fetch and return attachments"""
        if self._attachments is None:
            self._attachments = self._retriever.get_attachments(self._data['id'])
        return self._attachments
    
    @property
    def obj(self):
        """
        Compatibility property for .eml processing.
        Graph API doesn't provide raw MIME, so we create a minimal email object.
        """
        from email.message import EmailMessage
        
        msg = EmailMessage()
        msg['Subject'] = self.subject
        msg['From'] = self.from_
        msg['To'] = ', '.join(self.to)
        if self.cc:
            msg['Cc'] = ', '.join(self.cc)
        msg['Date'] = self.date.strftime('%a, %d %b %Y %H:%M:%S %z')
        
        # Set body content
        if self.html:
            msg.set_content(self.text if self.text else '')
            msg.add_alternative(self.html, subtype='html')
        else:
            msg.set_content(self.text if self.text else '')
        
        return msg
    
    @property
    def headers(self) -> dict:
        """Email headers (limited from Graph API)"""
        return {
            'subject': self.subject,
            'from': self.from_,
            'to': ', '.join(self.to),
            'date': self.date.isoformat(),
        }


class GraphMailAttachment:
    """
    Adapter for Graph API attachments, compatible with imap_tools.MailAttachment.
    """
    
    def __init__(self, attachment_data: dict):
        """
        Initialize attachment from Graph API data.
        
        Args:
            attachment_data: Attachment object from Graph API
        """
        self._data = attachment_data
        self._payload = None
    
    @property
    def filename(self) -> str:
        """Attachment filename"""
        return self._data.get('name', 'untitled')
    
    @property
    def content_type(self) -> str:
        """MIME content type"""
        return self._data.get('contentType', 'application/octet-stream')
    
    @property
    def content_disposition(self) -> str:
        """
        Content disposition (attachment or inline).
        Graph API uses 'isInline' property.
        """
        is_inline = self._data.get('isInline', False)
        return 'inline' if is_inline else 'attachment'
    
    @property
    def payload(self) -> bytes:
        """Attachment content as bytes"""
        if self._payload is None:
            # contentBytes is base64-encoded
            content_b64 = self._data.get('contentBytes', '')
            if content_b64:
                self._payload = base64.b64decode(content_b64)
            else:
                self._payload = b''
        return self._payload
    
    @property
    def size(self) -> int:
        """Attachment size in bytes"""
        return self._data.get('size', 0)


class OutlookGraphMailRetriever:
    """
    Fetches emails from Outlook using Microsoft Graph API.
    Compatible interface with IMAP retrieval for seamless integration.
    """
    
    GRAPH_BASE = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, mail_account: MailAccount):
        """
        Initialize Graph API mail retriever.
        
        Args:
            mail_account: MailAccount instance with OAuth credentials
        """
        self.mail_account = mail_account
        self.access_token = mail_account.password  # OAuth access token
        
        if mail_account.account_type != MailAccount.MailAccountType.OUTLOOK_OAUTH:
            raise ValueError(
                f"OutlookGraphMailRetriever requires OUTLOOK_OAUTH account type, "
                f"got {mail_account.account_type}"
            )
    
    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for Graph API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def _build_filter_query(self, rule: MailRule) -> str:
        """
        Build OData $filter query from MailRule criteria.
        
        Args:
            rule: MailRule with filter criteria
            
        Returns:
            OData filter string
        """
        filters = []
        
        # Filter by sender
        if rule.filter_from:
            filters.append(f"from/emailAddress/address eq '{rule.filter_from}'")
        
        # Filter by recipient
        if rule.filter_to:
            # Note: toRecipients is a collection, need to use 'any' operator
            filters.append(
                f"toRecipients/any(r:r/emailAddress/address eq '{rule.filter_to}')"
            )
        
        # Filter by subject
        if rule.filter_subject:
            # Use 'contains' for partial matching (like IMAP)
            filters.append(f"contains(subject, '{rule.filter_subject}')")
        
        # Filter by body
        if rule.filter_body:
            filters.append(f"contains(body/content, '{rule.filter_body}')")
        
        # Maximum age filter
        if rule.maximum_age > 0:
            from datetime import date, timedelta
            max_date = date.today() - timedelta(days=rule.maximum_age)
            filters.append(f"receivedDateTime ge {max_date.isoformat()}T00:00:00Z")
        
        # Combine all filters with 'and'
        if filters:
            return ' and '.join(filters)
        return ''
    
    def fetch_messages(self, rule: MailRule) -> list[GraphMailMessage]:
        """
        Fetch messages matching rule criteria via Graph API.
        
        Args:
            rule: MailRule with filter criteria
            
        Returns:
            List of GraphMailMessage objects
        """
        logger.info(f"[Graph API] Fetching messages for rule: {rule.name}")
        
        # Build query parameters
        params = {
            '$select': 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,hasAttachments,body,isRead',
            '$orderby': 'receivedDateTime desc',
            '$top': 100,  # Limit per request
        }
        
        # Add filter if criteria specified
        filter_query = self._build_filter_query(rule)
        if filter_query:
            params['$filter'] = filter_query
            logger.debug(f"[Graph API] Filter: {filter_query}")
        
        # Note: Graph API doesn't support folder selection like IMAP
        # All messages are in the default mailbox unless using mailFolders endpoint
        # For now, we'll fetch from the default message collection
        # TODO: Implement folder support using /me/mailFolders/{folderId}/messages
        
        endpoint = f"{self.GRAPH_BASE}/me/messages"
        
        messages = []
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    endpoint,
                    headers=self._get_headers(),
                    params=params,
                )
                response.raise_for_status()
            
            data = response.json()
            message_list = data.get('value', [])
            
            logger.info(f"[Graph API] Retrieved {len(message_list)} messages")
            
            # Wrap each message in adapter
            for msg_data in message_list:
                messages.append(GraphMailMessage(msg_data, self))
            
            # TODO: Handle pagination with @odata.nextLink
            if '@odata.nextLink' in data:
                logger.debug("[Graph API] More messages available (pagination not implemented)")
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Token expired, try to refresh
                logger.warning("[Graph API] Access token expired, attempting refresh")
                oauth_manager = PaperlessMailOAuth2Manager()
                if oauth_manager.refresh_account_oauth_token(self.mail_account):
                    self.mail_account.refresh_from_db()
                    self.access_token = self.mail_account.password
                    # Retry the request
                    return self.fetch_messages(rule)
                else:
                    logger.error("[Graph API] Failed to refresh token")
                    raise
            else:
                logger.error(
                    f"[Graph API] HTTP {e.response.status_code}: {e.response.text[:200]}"
                )
                raise
        except Exception as e:
            logger.exception(f"[Graph API] Error fetching messages: {e}")
            raise
        
        return messages
    
    def get_attachments(self, message_id: str) -> list[GraphMailAttachment]:
        """
        Fetch attachments for a specific message.
        
        Args:
            message_id: Graph API message ID (without 'graph:' prefix)
            
        Returns:
            List of GraphMailAttachment objects
        """
        # Remove 'graph:' prefix if present
        if message_id.startswith('graph:'):
            message_id = message_id[6:]
        
        endpoint = f"{self.GRAPH_BASE}/me/messages/{message_id}/attachments"
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    endpoint,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
            
            data = response.json()
            attachments_data = data.get('value', [])
            
            logger.debug(f"[Graph API] Found {len(attachments_data)} attachments for message {message_id}")
            
            # Convert to attachment objects
            attachments = []
            for att_data in attachments_data:
                # Only process file attachments (not item attachments)
                if att_data.get('@odata.type') == '#microsoft.graph.fileAttachment':
                    attachments.append(GraphMailAttachment(att_data))
            
            return attachments
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[Graph API] Error fetching attachments: {e.response.status_code}"
            )
            return []
        except Exception as e:
            logger.exception(f"[Graph API] Error fetching attachments: {e}")
            return []
    
    def mark_message_read(self, message_uid: str):
        """
        Mark message as read via Graph API.
        
        Args:
            message_uid: Message UID (with or without 'graph:' prefix)
        """
        # Remove 'graph:' prefix if present
        if message_uid.startswith('graph:'):
            message_id = message_uid[6:]
        else:
            message_id = message_uid
        
        endpoint = f"{self.GRAPH_BASE}/me/messages/{message_id}"
        payload = {"isRead": True}
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.patch(
                    endpoint,
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
            
            logger.debug(f"[Graph API] Marked message {message_id} as read")
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[Graph API] Error marking message read: {e.response.status_code}"
            )
            raise
    
    def delete_message(self, message_uid: str):
        """
        Delete message via Graph API.
        
        Args:
            message_uid: Message UID (with or without 'graph:' prefix)
        """
        # Remove 'graph:' prefix if present
        if message_uid.startswith('graph:'):
            message_id = message_uid[6:]
        else:
            message_id = message_uid
        
        endpoint = f"{self.GRAPH_BASE}/me/messages/{message_id}"
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.delete(
                    endpoint,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
            
            logger.debug(f"[Graph API] Deleted message {message_id}")
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[Graph API] Error deleting message: {e.response.status_code}"
            )
            raise
    
    def flag_message(self, message_uid: str):
        """
        Flag message as important via Graph API.
        
        Args:
            message_uid: Message UID (with or without 'graph:' prefix)
        """
        # Remove 'graph:' prefix if present
        if message_uid.startswith('graph:'):
            message_id = message_uid[6:]
        else:
            message_id = message_uid
        
        endpoint = f"{self.GRAPH_BASE}/me/messages/{message_id}"
        payload = {
            "flag": {
                "flagStatus": "flagged"
            }
        }
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.patch(
                    endpoint,
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
            
            logger.debug(f"[Graph API] Flagged message {message_id}")
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[Graph API] Error flagging message: {e.response.status_code}"
            )
            raise
    
    def move_message(self, message_uid: str, destination_folder: str):
        """
        Move message to different folder via Graph API.
        
        Args:
            message_uid: Message UID (with or without 'graph:' prefix)
            destination_folder: Folder name or ID
        """
        # Remove 'graph:' prefix if present
        if message_uid.startswith('graph:'):
            message_id = message_uid[6:]
        else:
            message_id = message_uid
        
        # First, resolve folder name to folder ID
        folder_id = self._get_folder_id(destination_folder)
        if not folder_id:
            logger.error(f"[Graph API] Folder '{destination_folder}' not found")
            raise ValueError(f"Folder '{destination_folder}' not found")
        
        endpoint = f"{self.GRAPH_BASE}/me/messages/{message_id}/move"
        payload = {"destinationId": folder_id}
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    endpoint,
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
            
            logger.debug(f"[Graph API] Moved message {message_id} to {destination_folder}")
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[Graph API] Error moving message: {e.response.status_code}"
            )
            raise
    
    def tag_message(self, message_uid: str, category: str):
        """
        Tag message with category via Graph API.
        
        Args:
            message_uid: Message UID (with or without 'graph:' prefix)
            category: Category/tag name
        """
        # Remove 'graph:' prefix if present
        if message_uid.startswith('graph:'):
            message_id = message_uid[6:]
        else:
            message_id = message_uid
        
        endpoint = f"{self.GRAPH_BASE}/me/messages/{message_id}"
        payload = {
            "categories": [category]
        }
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.patch(
                    endpoint,
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
            
            logger.debug(f"[Graph API] Tagged message {message_id} with '{category}'")
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[Graph API] Error tagging message: {e.response.status_code}"
            )
            raise
    
    def _get_folder_id(self, folder_name: str) -> str | None:
        """
        Get folder ID from folder name.
        
        Args:
            folder_name: Folder display name
            
        Returns:
            Folder ID or None if not found
        """
        # Check well-known folder names first
        well_known = {
            'inbox': 'inbox',
            'drafts': 'drafts',
            'sentitems': 'sentitems',
            'deleteditems': 'deleteditems',
        }
        
        folder_lower = folder_name.lower().replace(' ', '')
        if folder_lower in well_known:
            return well_known[folder_lower]
        
        # Search for folder by name
        endpoint = f"{self.GRAPH_BASE}/me/mailFolders"
        params = {
            '$filter': f"displayName eq '{folder_name}'",
            '$select': 'id,displayName',
        }
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    endpoint,
                    headers=self._get_headers(),
                    params=params,
                )
                response.raise_for_status()
            
            data = response.json()
            folders = data.get('value', [])
            
            if folders:
                return folders[0]['id']
            
            logger.warning(f"[Graph API] Folder '{folder_name}' not found")
            return None
            
        except Exception as e:
            logger.error(f"[Graph API] Error finding folder: {e}")
            return None


# RKC: Graph API-specific mail actions for batch processing (v1.1.0)
class GraphMailAction:
    """Base class for Graph API mail actions"""
    
    def __init__(self, retriever: OutlookGraphMailRetriever):
        self.retriever = retriever
    
    def execute(self, message_uid: str, parameter: str = None):
        """Execute the action on the given message"""
        raise NotImplementedError


class MarkReadGraphAction(GraphMailAction):
    """Mark message as read via Graph API"""
    
    def execute(self, message_uid: str, parameter: str = None):
        self.retriever.mark_message_read(message_uid)


class DeleteGraphAction(GraphMailAction):
    """Delete message via Graph API"""
    
    def execute(self, message_uid: str, parameter: str = None):
        self.retriever.delete_message(message_uid)


class FlagGraphAction(GraphMailAction):
    """Flag message via Graph API"""
    
    def execute(self, message_uid: str, parameter: str = None):
        self.retriever.flag_message(message_uid)


class MoveGraphAction(GraphMailAction):
    """Move message to folder via Graph API"""
    
    def execute(self, message_uid: str, parameter: str = None):
        if not parameter:
            raise ValueError("Move action requires destination folder parameter")
        self.retriever.move_message(message_uid, parameter)


class TagGraphAction(GraphMailAction):
    """Tag message with category via Graph API"""
    
    def execute(self, message_uid: str, parameter: str = None):
        if not parameter:
            raise ValueError("Tag action requires category parameter")
        # Handle Apple Mail color tags - convert to Graph categories
        if "apple:" in parameter.lower():
            _, color = parameter.split(":")
            category = f"Apple {color.strip().capitalize()}"
        else:
            category = parameter
        
        self.retriever.tag_message(message_uid, category)


class ProcessAllGraphAction(GraphMailAction):
    """Process all action - no post-processing"""
    
    def execute(self, message_uid: str, parameter: str = None):
        # No action - just process without marking
        pass
# /end RKC edit
