# Microsoft Graph API Mail Integration - Implementation Checklist

**Goal:** Implement Microsoft Graph API for both sending AND receiving emails with Outlook OAuth accounts, while maintaining IMAP/SMTP for Gmail OAuth and traditional accounts.

**Problem:** Microsoft rejects OAuth requests mixing Graph API scopes (`Mail.Send`) with Exchange legacy scopes (`IMAP.AccessAsUser.All`), causing 400 Bad Request errors.

**Solution:** Use pure Graph API scopes for Outlook OAuth accounts for both sending and receiving.

---

## Phase 1: Graph API Mail Retrieval Backend

### Core Implementation
- [ ] Create `src/paperless_mail/mail_graph_retrieval.py`
- [ ] Implement `OutlookGraphMailRetriever` class
  - [ ] `__init__(mail_account)` - Initialize with OAuth token
  - [ ] `fetch_messages(rule)` - GET /me/messages with filters
  - [ ] `get_message_details(message_id)` - GET /me/messages/{id}
  - [ ] `download_attachment(message_id, attachment_id)` - GET attachments
  - [ ] `_build_filter_query(rule)` - Convert MailRule to OData $filter
  - [ ] `_refresh_token_if_needed()` - Auto-refresh expired tokens

### Message Adapter
- [ ] Implement `GraphMailMessage` class
  - [ ] `uid` property - Returns Graph message ID
  - [ ] `subject` property - Returns email subject
  - [ ] `from_values` property - Compatible with imap_tools format
  - [ ] `date` property - Parse receivedDateTime to datetime
  - [ ] `to` property - List of recipient addresses
  - [ ] `cc` property - List of CC addresses
  - [ ] `text` property - Plain text body
  - [ ] `html` property - HTML body
  - [ ] `get_attachments()` method - Fetch and return attachments
  - [ ] `headers` property - Email headers compatible format

### Mail Actions via Graph API
- [ ] Implement `GraphMailAction` base class
- [ ] Implement `MarkReadGraphAction` - PATCH isRead: true
- [ ] Implement `DeleteGraphAction` - DELETE /me/messages/{id}
- [ ] Implement `FlagGraphAction` - PATCH flag property
- [ ] Implement `MoveGraphAction` - POST /me/messages/{id}/move
  - [ ] Implement folder lookup/caching logic
- [ ] Implement `TagGraphAction` - PATCH categories property

### Error Handling
- [ ] Implement Graph API error parser
- [ ] Add retry logic with exponential backoff
- [ ] Handle 401 (token expired) with auto-refresh
- [ ] Handle 429 (rate limit) with retry-after
- [ ] Add comprehensive logging for all API calls

---

## Phase 2: Mail Processing Integration

### Retriever Factory
- [ ] Update `src/paperless_mail/mail.py`
- [ ] Add `_should_use_graph_api(account)` helper function
- [ ] Create `get_mail_retriever(account)` factory function
- [ ] Wrap existing IMAP logic in `IMAPRetriever` class (for consistency)

### Update Mail Processing Tasks
- [ ] Modify `_process_mailbox()` to use retriever factory
- [ ] Update `_process_message()` to work with both message types
- [ ] Abstract attachment handling to work with both protocols
- [ ] Update `apply_mail_action()` to route to appropriate action handler
- [ ] Ensure ProcessedMail UID tracking works with Graph message IDs

### Message UID Compatibility
- [ ] Update ProcessedMail.uid field handling
- [ ] Implement UID format: `graph:{message-id}` vs `imap:{uid}`
- [ ] Add migration note to handle existing IMAP UIDs
- [ ] Update duplicate detection to handle both formats

---

## Phase 3: OAuth Scope Updates

### Update OAuth Configuration
- [x] Modify `src/paperless_mail/oauth.py`
- [x] Change `get_outlook_authorization_url()` scopes
  - [x] Remove: `https://outlook.office.com/IMAP.AccessAsUser.All`
  - [x] Remove: `https://outlook.office.com/SMTP.Send`
  - [x] Add: `https://graph.microsoft.com/User.Read` (required for /me endpoint in test function)
  - [x] Add: `https://graph.microsoft.com/Mail.Read`
  - [x] Add: `https://graph.microsoft.com/Mail.Send`
  - [x] Add: `https://graph.microsoft.com/Mail.Send.Shared` (for shared mailbox support)
  - [x] Keep: `offline_access`
- [x] Update RKC comments to reflect v1.1.0 Graph API integration
- [x] **Bug Fix**: Fixed empty from_email string handling in mail_graph.py
  - [x] Check for non-empty string before setting "from" field
  - [x] Prevents "ErrorSendAsDenied" when from field is empty or contains only whitespace
- [x] **Bug Fix**: Fixed test function 403 error
  - [x] Added User.Read scope for /me endpoint access
  - [x] Prevents "Insufficient privileges" error when testing connection
- [ ] Test OAuth authorization flow with new scopes (requires user re-authorization)

---

## Phase 4: Testing & Validation

### Unit Tests
- [ ] Create `src/paperless_mail/tests/test_graph_retrieval.py`
  - [ ] Mock Graph API responses
  - [ ] Test `OutlookGraphMailRetriever.fetch_messages()`
  - [ ] Test `GraphMailMessage` adapter properties
  - [ ] Test attachment download logic
  - [ ] Test error handling and retries

- [ ] Create `src/paperless_mail/tests/test_mail_adapter.py`
  - [ ] Test GraphMailMessage compatibility with existing code
  - [ ] Test message property conversions
  - [ ] Test date parsing
  - [ ] Test attachment extraction

- [ ] Create `src/paperless_mail/tests/test_graph_actions.py`
  - [ ] Test all mail action classes
  - [ ] Test folder ID lookup for MOVE action
  - [ ] Test error scenarios

### Integration Testing
- [ ] **Manual Test: Outlook OAuth Authorization**
  - [ ] Delete existing Outlook OAuth account
  - [ ] Create new account with Graph API scopes
  - [ ] Verify OAuth authorization succeeds (no 400 error)
  - [ ] Verify scopes shown: "Read your mail", "Send mail as you"

- [ ] **Manual Test: Mail Retrieval**
  - [ ] Configure mail rule for Outlook OAuth account
  - [ ] Send test email to account
  - [ ] Verify email is retrieved via Graph API
  - [ ] Check logs for Graph API endpoint calls
  - [ ] Verify document created correctly

- [ ] **Manual Test: Attachments**
  - [ ] Send email with PDF attachment
  - [ ] Verify attachment downloads via Graph API
  - [ ] Verify document consumed with correct content
  - [ ] Test multiple attachments

- [ ] **Manual Test: Mail Actions**
  - [ ] Test MARK_READ action
  - [ ] Test DELETE action  
  - [ ] Test FLAG action
  - [ ] Test MOVE action (to different folder)
  - [ ] Test TAG action (categories)

- [ ] **Manual Test: Sending**
  - [ ] Verify existing Graph API sending still works
  - [ ] Test sending with attachments
  - [ ] Test HTML email sending

### Backward Compatibility Testing
- [ ] **Test Gmail OAuth Account**
  - [ ] Verify still uses IMAP for receiving
  - [ ] Verify still uses SMTP for sending
  - [ ] No re-authorization required
  - [ ] All existing functionality works

- [ ] **Test Traditional IMAP Account**
  - [ ] Verify still uses IMAP for receiving
  - [ ] Verify still uses SMTP for sending
  - [ ] No configuration changes needed

---

## Phase 5: Documentation Updates

### Code Documentation
- [ ] Add RKC comments to all new code in `mail_graph_retrieval.py`
- [ ] Add RKC comments to modified sections in `mail.py`
- [ ] Add RKC comments to scope changes in `oauth.py`
- [ ] Update docstrings for all new classes and methods
- [ ] Add inline comments explaining Graph API specifics

### User Documentation
- [ ] Update `MS365_OAUTH_SETUP.md`
  - [ ] Document Graph API for both send and receive
  - [ ] Remove IMAP/SMTP troubleshooting sections
  - [ ] Update scope list to Mail.Read + Mail.Send
  - [ ] Add re-authorization instructions for existing users
  - [ ] Document Security Defaults compatibility

- [ ] Update `RKC_CUSTOMIZATIONS.md`
  - [ ] Consolidate v1.1.0 entry with full Graph API integration
  - [ ] Document architecture: Graph API for Outlook, IMAP/SMTP for others
  - [ ] Add migration instructions
  - [ ] List all modified files

- [ ] Create migration guide document
  - [ ] Explain why re-authorization needed
  - [ ] Step-by-step re-authorization process
  - [ ] What to expect on consent screen
  - [ ] Troubleshooting common issues

---

## Phase 6: Deployment & Rollout

### Pre-Deployment Checklist
- [ ] All unit tests passing
- [ ] All integration tests completed manually
- [ ] Documentation complete and reviewed
- [ ] RKC comments present on all changes
- [ ] No performance regressions observed
- [ ] Logging verified at all levels

### Deployment Steps
- [ ] Backup current codebase
- [ ] Deploy code changes
- [ ] Restart Paperless services
- [ ] Monitor logs for errors
- [ ] Test with one Outlook account first

### Post-Deployment
- [ ] Monitor Graph API calls and rate limits
- [ ] Check ProcessedMail table for correct UID formats
- [ ] Verify no errors in celery task logs
- [ ] Collect user feedback on re-authorization process

---

## Future Improvements (Not in Scope)

- [ ] Implement Graph API pagination for large mailboxes
- [ ] Add folder hierarchy caching for better MOVE performance
- [ ] Implement delta queries for incremental sync
- [ ] Add webhook support for real-time mail notifications
- [ ] Optimize attachment downloads with batch requests
- [ ] Consider Graph API for Gmail (future research)

---

## Notes

**Account Type Routing:**
- Gmail OAuth → IMAP + SMTP (unchanged)
- Outlook OAuth → Graph API + Graph API (new)
- Traditional → IMAP + SMTP (unchanged)

**Re-Authorization Required:**
All existing Outlook OAuth users must re-authorize to switch from mixed scopes (IMAP.AccessAsUser.All + SMTP.Send) to pure Graph scopes (Mail.Read + Mail.Send).

**ProcessedMail UID Format:**
- IMAP: Store as `imap:{numeric_uid}`
- Graph: Store as `graph:{message_id_string}`
This allows duplicate detection to work across both protocols.

**Graph API Rate Limits:**
Microsoft Graph has stricter rate limits than IMAP. Implement proper retry logic and respect Retry-After headers to avoid throttling.
