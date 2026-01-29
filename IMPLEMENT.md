# IMPLEMENT.md Content for Graph API Mail Implementation

```markdown
# Microsoft Graph API Mail Integration for Outlook OAuth Accounts

## GOAL

Implement Microsoft Graph API for both sending AND receiving emails with Outlook OAuth accounts, while maintaining IMAP/SMTP support for Gmail OAuth and traditional accounts.

**User Request:**
> "we need to keep imap for non-oauth and google accounts. let's make the TODO.md and IMPLEMENT.md anew for this new task"

**Problem Statement:**
Microsoft doesn't allow mixing Graph API scopes with Exchange legacy protocol scopes in the same OAuth request. The current implementation attempts to use:
- `https://outlook.office.com/IMAP.AccessAsUser.All` (Exchange legacy)
- `https://graph.microsoft.com/Mail.Send` (Graph API)

This combination causes a 400 Bad Request error during OAuth authorization.

**Solution:**
Implement provider-specific mail handling with complete Graph API integration for Outlook OAuth accounts only.

## ANALYSIS

### Current Architecture

**Mail Receiving:**
- All accounts (Gmail OAuth, Outlook OAuth, Traditional) use IMAP via `imap_tools` library
- OAuth tokens used for IMAP XOAUTH2 authentication
- Mail processing in `src/paperless_mail/mail.py`

**Mail Sending (v1.1.0):**
- Outlook OAuth → Graph API (`OutlookGraphEmailBackend`)
- Gmail OAuth → SMTP with XOAUTH2 (`_MailAccountSMTPBackend`)
- Traditional → SMTP with username/password (`_MailAccountSMTPBackend`)

### Microsoft Scope Restrictions

**Cannot Mix:**
```python
# ❌ This causes 400 Bad Request
scope=[
    "https://outlook.office.com/IMAP.AccessAsUser.All",  # Exchange legacy
    "https://graph.microsoft.com/Mail.Send",              # Graph API
]
```

**Must Use Consistent Scope Type:**
```python
# ✅ Option 1: Full Graph API (Outlook OAuth only)
scope=[
    "offline_access",
    "https://graph.microsoft.com/Mail.Read",    # Receiving
    "https://graph.microsoft.com/Mail.Send",    # Sending
]

# ✅ Option 2: Full Exchange legacy (Gmail + Traditional)
scope=[
    "offline_access",
    "https://outlook.office.com/IMAP.AccessAsUser.All",  # Receiving
    # (Gmail uses https://mail.google.com/)
]
```

### Provider-Specific Strategy

| Account Type | Receiving | Sending | Scopes |
|--------------|-----------|---------|--------|
| **Gmail OAuth** | IMAP (imap_tools) | SMTP XOAUTH2 | `https://mail.google.com/` |
| **Outlook OAuth** | Graph API (NEW) | Graph API (existing) | `Mail.Read`, `Mail.Send` |
| **Traditional IMAP** | IMAP (imap_tools) | SMTP password | N/A |

### Technical Challenges

1. **Mail Processing Abstraction**
   - Current code tightly coupled to `imap_tools.MailMessage` objects
   - Need adapter pattern to support both IMAP and Graph API sources

2. **Scheduled Tasks**
   - `process_mail_accounts()` uses IMAP connection pooling
   - Need conditional logic to route Outlook OAuth to Graph API

3. **OAuth Token Management**
   - Graph API uses different endpoint than IMAP
   - Token refresh logic already supports both (good!)

4. **Mail Action Processing**
   - Post-consumption actions (MARK_READ, FLAG, TAG, MOVE, DELETE) use IMAP
   - Need Graph API equivalents for Outlook OAuth accounts

## IMPLEMENTATION

### Phase 1: Graph API Mail Retrieval Backend

**New File:** `src/paperless_mail/mail_graph_retrieval.py`

**Purpose:** Fetch emails from Outlook using Microsoft Graph API

**Key Classes:**
- `OutlookGraphMailRetriever` - Fetches messages from Graph API
- `GraphMailMessage` - Adapter converting Graph API JSON to Common format
- `GraphMailAction` - Base class for post-consumption actions via Graph API

**Core Methods:**
```python
class OutlookGraphMailRetriever:
    def __init__(self, mail_account: MailAccount):
        self.mail_account = mail_account
        self.access_token = mail_account.password  # OAuth token
    
    def fetch_messages(self, rule: MailRule) -> list[GraphMailMessage]:
        """
        Fetch messages matching rule criteria via Graph API.
        
        Endpoint: GET https://graph.microsoft.com/v1.0/me/messages
        Filters: $filter, $select, $orderby, $top
        """
        pass
    
    def mark_message_read(self, message_id: str):
        """PATCH /me/messages/{id} with isRead: true"""
        pass
    
    def delete_message(self, message_id: str):
        """DELETE /me/messages/{id}"""
        pass
    
    def download_attachment(self, message_id: str, attachment_id: str):
        """GET /me/messages/{id}/attachments/{attachmentId}/$value"""
        pass
```

**Graph API Message Adapter:**
```python
class GraphMailMessage:
    """
    Adapter that presents Graph API message in common format.
    Allows existing mail processing code to work with both IMAP and Graph.
    """
    def __init__(self, graph_json: dict):
        self._data = graph_json
    
    @property
    def uid(self) -> str:
        """Graph API message ID"""
        return self._data['id']
    
    @property
    def subject(self) -> str:
        return self._data.get('subject', '')
    
    @property
    def from_values(self):
        """Compatible with imap_tools.MailMessage.from_values"""
        sender = self._data.get('from', {}).get('emailAddress', {})
        return type('obj', (object,), {
            'email': sender.get('address', ''),
            'name': sender.get('name', '')
        })
    
    @property
    def date(self) -> datetime:
        """Parse receivedDateTime"""
        pass
    
    def get_attachments(self) -> list:
        """Fetch attachments via Graph API"""
        pass
```

### Phase 2: Update Mail Processing Tasks

**File:** `src/paperless_mail/mail.py`

**Changes Required:**

1. **Add account type detection:**
```python
def _should_use_graph_api(account: MailAccount) -> bool:
    """Check if account should use Graph API instead of IMAP"""
    return account.account_type == MailAccount.MailAccountType.OUTLOOK_OAUTH
```

2. **Create retrieval factory:**
```python
def get_mail_retriever(account: MailAccount):
    """Return appropriate mail retriever for account type"""
    if _should_use_graph_api(account):
        from paperless_mail.mail_graph_retrieval import OutlookGraphMailRetriever
        return OutlookGraphMailRetriever(account)
    else:
        return IMAPRetriever(account)  # Existing IMAP logic wrapped
```

3. **Update `_process_mailbox()` function:**
```python
def _process_mailbox(account: MailAccount, rule: MailRule):
    retriever = get_mail_retriever(account)
    messages = retriever.fetch_messages(rule)
    
    for message in messages:
        # Existing processing logic works with either GraphMailMessage or IMAPMessage
        _process_message(account, rule, message, retriever)
```

4. **Abstract mail actions:**
```python
def apply_action(retriever, message_uid: str, action: MailAction):
    """Apply post-consumption action using appropriate method"""
    if isinstance(retriever, OutlookGraphMailRetriever):
        # Use Graph API methods
        if action == MailAction.MARK_READ:
            retriever.mark_message_read(message_uid)
        elif action == MailAction.DELETE:
            retriever.delete_message(message_uid)
        # ... etc
    else:
        # Use existing IMAP methods
        # ... existing code
```

### Phase 3: Update OAuth Scopes

**File:** `src/paperless_mail/oauth.py`

**Change:**
```python
def get_outlook_authorization_url(self) -> str:
    # RKC: v1.1.0 - Full Graph API for Outlook OAuth (both send and receive)
    return asyncio.run(
        self.outlook_client.get_authorization_url(
            redirect_uri=self.oauth_callback_url,
            scope=[
                "offline_access",
                "https://graph.microsoft.com/Mail.Read",    # Receiving via Graph API
                "https://graph.microsoft.com/Mail.Send",    # Sending via Graph API
            ],
            state=self.state,
        ),
    )
    # /end RKC edit
```

### Phase 4: Graph API Endpoints Reference

**Mail Retrieval:**
- `GET /me/messages` - List messages
  - Filters: `$filter=isRead eq false`, `$select=id,subject,from,receivedDateTime`
  - Pagination: `@odata.nextLink`

- `GET /me/messages/{id}` - Get specific message
  - Include: `$expand=attachments`

- `GET /me/messages/{id}/attachments` - List attachments
- `GET /me/messages/{id}/attachments/{attachmentId}/$value` - Download attachment

**Mail Actions:**
- `PATCH /me/messages/{id}` - Update message properties
  - Body: `{"isRead": true}`
- `DELETE /me/messages/{id}` - Delete message
- `POST /me/messages/{id}/move` - Move to folder
  - Body: `{"destinationId": "folder-id"}`

**Folder Operations (for MOVE action):**
- `GET /me/mailFolders` - List folders
- `GET /me/mailFolders/{id}/childFolders` - List subfolders

### Phase 5: Error Handling & Logging

**Consistent Error Patterns:**
```python
try:
    response = client.get(endpoint, headers=headers)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        # Token expired, refresh and retry
        oauth_manager.refresh_account_oauth_token(account)
        # retry...
    else:
        logger.error(f"[Graph API] HTTP {e.response.status_code}: {e.response.text}")
        raise
```

**Structured Logging:**
```python
logger.info(f"[Graph API] Fetching messages for rule: {rule.name}")
logger.debug(f"[Graph API] Endpoint: {endpoint}")
logger.debug(f"[Graph API] Filters: {filters}")
logger.info(f"[Graph API] Retrieved {len(messages)} messages")
```

### Phase 6: Testing Strategy

**Unit Tests:**
- Mock Graph API responses
- Test message adapter (GraphMailMessage)
- Test

 action handlers
- Test retriever factory

**Integration Tests:**
- Test with real Outlook OAuth account (manual)
- Verify attachments download correctly
- Test all mail actions (MARK_READ, DELETE, etc.)
- Verify ProcessedMail tracking works

**Backward Compatibility:**
- Gmail OAuth accounts continue using IMAP ✅
- Traditional accounts continue using IMAP ✅
- Existing v1.1.0 accounts need re-authorization

### Phase 7: Migration Path

**For Existing Outlook OAuth Accounts:**

1. **Re-authorization Required**
   - Old scope: `IMAP.AccessAsUser.All` + `SMTP.Send`
   - New scope: `Mail.Read` + `Mail.Send`
   - Users click "Enable OAuth2 Mail" button again

2. **ProcessedMail Compatibility**
   - Graph API message IDs differ from IMAP UIDs
   - Solution: Store both in ProcessedMail.uid field
   - Format: `graph:{message-id}` vs `imap:{uid}`

3. **Gradual Rollout**
   - Phase 1: Implement receiving
   - Phase 2: Test with single account
   - Phase 3: Document and announce
   - Phase 4: Encourage re-authorization

## ARCHITECTURE SUMMARY

### Before (v1.1.0 - Broken)
```
┌──────────────────────────────────────────────┐
│ Account Type    │ Receive   │ Send          │
├──────────────────────────────────────────────┤
│ Gmail OAuth     │ IMAP      │ SMTP          │
│ Outlook OAuth   │ IMAP ❌   │ Graph API ❌  │  <-- Mixed scopes = 400 error
│ Traditional     │ IMAP      │ SMTP          │
└──────────────────────────────────────────────┘
```

### After (v1.1.0 - Fixed)
```
┌──────────────────────────────────────────────┐
│ Account Type    │ Receive   │ Send          │
├──────────────────────────────────────────────┤
│ Gmail OAuth     │ IMAP      │ SMTP          │
│ Outlook OAuth   │ Graph API │ Graph API     │  <-- Pure Graph scopes ✅
│ Traditional     │ IMAP      │ SMTP          │
└──────────────────────────────────────────────┘
```

## FILES TO MODIFY/CREATE

**New Files:**
- `src/paperless_mail/mail_graph_retrieval.py` - Graph API mail retrieval

**Modified Files:**
- `src/paperless_mail/oauth.py` - Update Outlook scopes to Mail.Read + Mail.Send
- `src/paperless_mail/mail.py` - Add retriever factory and account type routing
- `src/paperless_mail/models.py` - Document Graph API message ID format
- `RKC_CUSTOMIZATIONS.md` - Update v1.1.0 entry with Graph API receiving
- `MS365_OAUTH_SETUP.md` - Document Graph API for both send and receive

**Testing Files (Future):**
- `src/paperless_mail/tests/test_graph_retrieval.py`
- `src/paperless_mail/tests/test_mail_adapter.py`

## DEPENDENCIES

**Existing:**
- `httpx` - HTTP client (already used in mail_graph.py)
- `django` - Web framework
- `celery` - Task scheduling

**No New Dependencies Required** ✅

## RISKS & CONSIDERATIONS

1. **Graph API Rate Limiting**
   - Microsoft has stricter rate limits than IMAP
   - Solution: Implement exponential backoff, respect retry-after headers

2. **Message UID Compatibility**
   - IMAP UIDs are integers, Graph IDs are strings
   - Solution: Store as string in ProcessedMail, prefix with protocol type

3. **Folder Structure Differences**
   - IMAP uses hierarchical folder paths
   - Graph uses folder IDs
   - Solution: Cache folder ID mapping for MOVE actions

4. **Attachment Handling**
   - Graph API requires separate requests per attachment
   - Solution: Batch download, use async requests where possible

5. **Re-authorization Friction**
   - All existing Outlook users must re-authorize
   - Solution: Clear documentation, error messages guide users

## SUCCESS CRITERIA

- [ ] Outlook OAuth accounts can authorize without 400 errors
- [ ] Emails retrieved via Graph API process correctly
- [ ] Attachments download and save as documents
- [ ] Mail actions (MARK_READ, DELETE, etc.) work via Graph API
- [ ] Gmail OAuth accounts unaffected (still use IMAP)
- [ ] Traditional accounts unaffected (still use IMAP)
- [ ] No performance degradation
- [ ] Comprehensive logging for troubleshooting
- [ ] All RKC comments properly marking changes
