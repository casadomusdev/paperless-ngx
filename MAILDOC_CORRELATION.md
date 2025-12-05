# Mail-Document Correlation Implementation Plan

## Problem Statement

When Paperless-ngx processes emails to extract attachments as documents, it creates entries in the `paperless_mail_processedmail` table for each email processed. We need to reliably associate documents with their source email to enable queries like "show me all documents from this specific email."

### Why Timestamp Comparison Doesn't Work

Initial consideration was to use timestamp comparison between:
- `ProcessedMail.processed` - When the email processing completed
- `Document.added` - When each document was created

However, this approach is **unreliable** due to asynchronous processing:

#### The Asynchronous Problem

Looking at `src/paperless_mail/mail.py`, the `queue_consumption_tasks()` function uses Celery's `chord()` pattern:

```python
chord(header=consume_tasks, body=mail_action_task).on_error(...).delay()
```

This means:
1. Multiple emails are processed in a loop that queues work asynchronously
2. Each email's attachments are consumed in parallel by Celery workers
3. The `ProcessedMail.processed` timestamp is set AFTER all attachments complete
4. Multiple emails' documents can be created simultaneously

**Real-world timing scenario:**
```
Time T0: Email 1 processing queued (.delay() returns immediately)
Time T1: Email 2 processing queued (.delay() returns immediately)
Time T2: Email 3 processing queued (.delay() returns immediately)
Time T3: Email 1's consume_file tasks start executing
Time T4: Email 2's consume_file tasks start executing
Time T5: Email 1 creates Doc1 (added timestamp)
Time T6: Email 2 creates Doc2 (added timestamp)
Time T7: Email 1's apply_mail_action creates ProcessedMail (processed timestamp)
Time T8: Email 2's apply_mail_action creates ProcessedMail (processed timestamp)
```

**Result:** Document and ProcessedMail entries from different emails are interleaved. Timestamp comparison would incorrectly associate documents with the wrong emails.

### Why Timestamp Might Seem to Work

In limited testing scenarios with:
- Single Celery worker (no parallelism)
- Low email volume (no overlap)
- Synchronous execution mode

Timestamps might appear to work correctly, but this is **fragile and deployment-dependent**, not a reliable solution.

## Solution: Custom Field Correlation

Store the email's UID directly in each document as a custom field value, creating an explicit database relationship rather than relying on timing.

### Design Principles

1. **Minimal Code Changes** - Only 4 small modifications across 3 files for easier maintenance during upgrades
2. **No Timing Changes** - Mail processing flow remains completely unchanged
3. **Consumer-Side Logic** - Custom field handling happens during document consumption
4. **UID-Only Passing** - Simple string UID passed through chain, not complex IDs or objects
5. **RKC Standards** - All changes properly marked with RKC comments per existing guidelines
6. **No Database Migration** - Uses existing CustomField infrastructure

## Implementation Details

### Configuration

#### Environment Variable
**File:** `src/paperless/settings.py`

Add after other PAPERLESS_* configuration:

```python
# RKC: Custom field name for storing email UID correlation
PAPERLESS_MAIL_CORRELATION_FIELD = config.get(
    "PAPERLESS_MAIL_CORRELATION_FIELD",
    default="Mail UID",
)
# /end RKC edit
```

**Purpose:**
- Allows customization of the custom field name
- Default: "Mail UID"
- Can be changed via environment variable to avoid conflicts
- Follows existing Paperless-ngx configuration pattern

### Code Changes

#### Change 1: Add mail_uid to ConsumableDocument Data Model

**File:** `src/documents/data_models.py`
**Location:** Inside `ConsumableDocument` dataclass definition

```python
@dataclasses.dataclass
class ConsumableDocument:
    """
    Encapsulates an incoming document, either from consume folder, API upload
    or mail fetching and certain useful operations on it.
    """

    source: DocumentSource
    original_file: Path
    original_path: Path | None = None
    mailrule_id: int | None = None
    # RKC: Store mail UID for correlation with ProcessedMail table
    mail_uid: str | None = None
    # /end RKC edit
    mime_type: str = dataclasses.field(init=False, default=None)
```

**Why this works:**
- `ConsumableDocument` is a dataclass, not a Django model
- No database table involved, so no migration needed
- Gets serialized and passed to Celery tasks automatically
- Adding optional field doesn't break existing code

#### Change 2: Pass UID When Creating ConsumableDocument

**File:** `src/paperless_mail/mail.py`

**Location 2a:** In `_process_attachments()` method (approximately line 1050)

```python
input_doc = ConsumableDocument(
    source=DocumentSource.MailFetch,
    original_file=temp_filename,
    mailrule_id=rule.pk,
    # RKC: Pass mail UID for document correlation
    mail_uid=message.uid,
    # /end RKC edit
)
```

**Location 2b:** In `_process_eml()` method (approximately line 1150)

```python
input_doc = ConsumableDocument(
    source=DocumentSource.MailFetch,
    original_file=temp_filename,
    mailrule_id=rule.pk,
    # RKC: Pass mail UID for document correlation
    mail_uid=message.uid,
    # /end RKC edit
)
```

**Why here:**
- These are the only two places where `ConsumableDocument` is created for mail processing
- `message.uid` is the IMAP UID that matches `ProcessedMail.uid`
- Simple addition of one parameter, doesn't affect other consumption paths

#### Change 3: Create Custom Field During Consumption

**File:** `src/documents/consumer.py`

**Location 3a:** Add helper function near top of file (after imports, before classes)

```python
# RKC: Helper function to attach mail UID as custom field for correlation with ProcessedMail
def _attach_mail_uid_custom_field(document, mail_uid: str):
    """
    Attaches the mail UID to the document as a custom field.
    Creates the custom field definition if it doesn't exist.
    
    Args:
        document: The Document instance to attach the field to
        mail_uid: The IMAP UID from the source email
    """
    from documents.models import CustomField, CustomFieldInstance
    from django.conf import settings
    
    if not mail_uid:
        return
    
    logger = logging.getLogger("paperless.consumer")
    
    try:
        # Get or create the mail correlation custom field definition
        field_name = settings.PAPERLESS_MAIL_CORRELATION_FIELD
        field, created = CustomField.objects.get_or_create(
            name=field_name,
            defaults={
                'data_type': CustomField.FieldDataType.STRING,
            }
        )
        
        if created:
            logger.info(f"Created mail correlation custom field: {field_name}")
        
        # Set the custom field value for this document
        CustomFieldInstance.objects.update_or_create(
            document=document,
            field=field,
            defaults={
                'value_text': mail_uid,
            }
        )
        
        logger.debug(f"Attached mail UID {mail_uid} to document {document.pk}")
        
    except Exception as e:
        logger.error(f"Failed to attach mail UID custom field: {e}")
        # Don't raise - this is a non-critical enhancement
# /end RKC edit
```

**Location 3b:** Call helper in `ConsumerPlugin.run()` method (after document is saved, approximately line 200)

```python
# Save the document
self.document.save()

# RKC: Attach mail UID custom field if document came from mail
if self.input_doc.mail_uid:
    _attach_mail_uid_custom_field(self.document, self.input_doc.mail_uid)
# /end RKC edit
```

**Why here:**
- Document must exist in database before creating CustomFieldInstance (FK constraint)
- Happens after document save, before task completion
- Non-critical enhancement - failures don't abort consumption
- Uses `update_or_create` to be idempotent (safe if called multiple times)

### Files Modified Summary

| File | Changes | RKC Markers |
|------|---------|-------------|
| `src/paperless/settings.py` | Add env var | 1 block |
| `src/documents/data_models.py` | Add mail_uid field | 1 line |
| `src/paperless_mail/mail.py` | Pass UID in 2 methods | 2 blocks |
| `src/documents/consumer.py` | Add helper + call | 2 blocks |

**Total:** 4 discrete code changes, 6 RKC marker blocks across 4 files

## Database Schema

### No Migration Required

This implementation requires **NO database migration** because:

1. **ConsumableDocument** - Not a Django model, just a Python dataclass
2. **CustomField & CustomFieldInstance** - Tables already exist in Paperless schema
3. **Runtime Creation** - Custom field definition and instances created at runtime:
   - `CustomField` row created with `get_or_create()` on first mail processed
   - `CustomFieldInstance` rows created with `update_or_create()` for each document

### What Gets Created

#### First Mail Processed
One row in `documents_customfield`:
```sql
INSERT INTO documents_customfield (name, data_type, created)
VALUES ('Mail UID', 'string', NOW());
```

#### Each Document from Mail
One row in `documents_customfieldinstance`:
```sql
INSERT INTO documents_customfieldinstance 
    (document_id, field_id, value_text, created)
VALUES (123, 1, '54321', NOW());
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Mail Processing (_handle_message)                        │
│    - Email UID: "12345"                                     │
│    - Has 3 attachments                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Create ConsumableDocument (for each attachment)          │
│    ConsumableDocument(                                      │
│        source=MailFetch,                                    │
│        original_file=path,                                  │
│        mailrule_id=5,                                       │
│        mail_uid="12345"  ← RKC: Added                      │
│    )                                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Queue Celery Tasks (chord)                               │
│    - 3 consume_file tasks queued (in parallel)             │
│    - Each carries mail_uid="12345" in input_doc            │
│    - apply_mail_action queued as callback                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Document Consumption (ConsumerPlugin.run)                │
│    - Parse attachment                                       │
│    - Create Document in database (doc_id=101)              │
│    - Save document                                         │
│    - RKC: Call _attach_mail_uid_custom_field()            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Custom Field Attachment                                  │
│    - Get/create CustomField "Mail UID"                     │
│    - Create CustomFieldInstance:                           │
│      * document_id: 101                                    │
│      * field_id: 1                                         │
│      * value_text: "12345"                                 │
└─────────────────────────────────────────────────────────────┘

Result: 3 documents (IDs 101, 102, 103) all have custom field 
        "Mail UID" = "12345"
```

## Usage Examples

### Finding Documents from Specific Email

```sql
-- Find all documents from email with UID "12345"
SELECT d.id, d.title, d.added, cfi.value_text as mail_uid
FROM documents_document d
JOIN documents_customfieldinstance cfi ON d.id = cfi.document_id
JOIN documents_customfield cf ON cfi.field_id = cf.id
WHERE cf.name = 'Mail UID' 
  AND cfi.value_text = '12345';
```

### Finding Email Details for Document

```sql
-- Get email details for document ID 101
SELECT 
    d.id as document_id,
    d.title,
    d.added,
    pm.uid as mail_uid,
    pm.subject as email_subject,
    pm.received as email_received,
    pm.processed as email_processed,
    pm.status
FROM documents_document d
JOIN documents_customfieldinstance cfi ON d.id = cfi.document_id
JOIN documents_customfield cf ON cfi.field_id = cf.id
JOIN paperless_mail_processedmail pm ON cfi.value_text = pm.uid
WHERE d.id = 101
  AND cf.name = 'Mail UID';
```

### Listing All Mail-Sourced Documents

```sql
-- All documents that came from mail processing
SELECT 
    d.id,
    d.title,
    cfi.value_text as mail_uid,
    pm.subject as email_subject,
    mr.name as mail_rule
FROM documents_document d
JOIN documents_customfieldinstance cfi ON d.id = cfi.document_id
JOIN documents_customfield cf ON cfi.field_id = cf.id
LEFT JOIN paperless_mail_processedmail pm ON cfi.value_text = pm.uid
LEFT JOIN paperless_mail_mailrule mr ON pm.rule_id = mr.id
WHERE cf.name = 'Mail UID'
ORDER BY d.added DESC;
```

### Finding Orphaned Documents

```sql
-- Documents with mail UID but no matching ProcessedMail entry
SELECT d.id, d.title, cfi.value_text as mail_uid
FROM documents_document d
JOIN documents_customfieldinstance cfi ON d.id = cfi.document_id
JOIN documents_customfield cf ON cfi.field_id = cf.id
LEFT JOIN paperless_mail_processedmail pm ON cfi.value_text = pm.uid
WHERE cf.name = 'Mail UID'
  AND pm.id IS NULL;
```

## Testing Plan

### Unit Tests

1. **Custom Field Creation**
   - Test `_attach_mail_uid_custom_field()` with new field name
   - Verify `CustomField` created with correct data_type
   - Test idempotency (calling twice with same data)

2. **UID Passing**
   - Verify `ConsumableDocument` accepts mail_uid parameter
   - Confirm mail_uid survives serialization to Celery task
   - Test with None/empty UID (should skip gracefully)

3. **End-to-End**
   - Process email with multiple attachments
   - Verify all documents have same mail_uid
   - Confirm mail_uid matches ProcessedMail.uid

### Manual Testing

#### Setup
```bash
# Set custom field name (optional)
export PAPERLESS_MAIL_CORRELATION_FIELD="Email Source UID"

# Restart paperless
docker compose restart webserver
```

#### Test 1: Field Auto-Creation
1. Process first email with attachment
2. Check database:
   ```sql
   SELECT * FROM documents_customfield WHERE name = 'Mail UID';
   ```
3. Expected: One row exists with data_type='string'

#### Test 2: Multiple Attachments
1. Send email with 3 PDF attachments
2. Wait for processing to complete
3. Query documents:
   ```sql
   SELECT d.title, cfi.value_text 
   FROM documents_document d
   JOIN documents_customfieldinstance cfi ON d.id = cfi.document_id
   JOIN documents_customfield cf ON cfi.field_id = cf.id
   WHERE cf.name = 'Mail UID'
   ORDER BY d.added DESC
   LIMIT 3;
   ```
4. Expected: All 3 documents have identical mail_uid

#### Test 3: Correlation Lookup
1. Note the mail_uid from Test 2
2. Find ProcessedMail entry:
   ```sql
   SELECT * FROM paperless_mail_processedmail 
   WHERE uid = '<the_mail_uid>';
   ```
3. Expected: One row with matching subject, received date
4. Verify `processed` timestamp exists (processing completed)

#### Test 4: Different Field Name
1. Set environment: `PAPERLESS_MAIL_CORRELATION_FIELD="Source Email"`
2. Restart service
3. Process new email
4. Verify new field created with custom name

#### Test 5: Upgrade Simulation
1. Note all RKC marker locations
2. Create git branch
3. Simulate merge conflict:
   - Modify same lines as RKC changes
   - Attempt merge
4. Resolve conflicts, preserving RKC blocks
5. Verify functionality still works

### Performance Testing

- Process 100 emails with 3 attachments each (300 documents)
- Monitor custom field creation time
- Verify no significant overhead added to consumption
- Expected: < 10ms overhead per document for custom field attachment

## Deployment

### Prerequisites
- Paperless-ngx instance running
- Access to modify source code
- Ability to restart service

### Installation Steps

1. **Apply Code Changes**
   ```bash
   cd /path/to/paperless-ngx
   
   # Edit files with RKC changes
   vim src/paperless/settings.py
   vim src/documents/data_models.py
   vim src/paperless_mail/mail.py
   vim src/documents/consumer.py
   ```

2. **Set Environment Variable (Optional)**
   ```bash
   # Docker Compose: Add to environment section
   PAPERLESS_MAIL_CORRELATION_FIELD: "Mail UID"
   
   # Bare metal: Add to .env or systemd
   export PAPERLESS_MAIL_CORRELATION_FIELD="Mail UID"
   ```

3. **Restart Service**
   ```bash
   # Docker
   docker compose restart webserver
   
   # Systemd
   sudo systemctl restart paperless-webserver
   ```

4. **Verify Installation**
   ```bash
   # Check logs for any errors
   docker compose logs webserver | grep -i "mail uid"
   
   # Process test email
   # Check custom field created
   docker compose exec webserver python manage.py shell
   >>> from documents.models import CustomField
   >>> CustomField.objects.filter(name__icontains='mail')
   ```

### Rollback Procedure

If issues occur:

1. **Remove Code Changes**
   ```bash
   git checkout <previous_commit> -- src/paperless/settings.py
   git checkout <previous_commit> -- src/documents/data_models.py
   git checkout <previous_commit> -- src/paperless_mail/mail.py
   git checkout <previous_commit> -- src/documents/consumer.py
   ```

2. **Restart Service**
   ```bash
   docker compose restart webserver
   ```

3. **Clean Up Custom Field (Optional)**
   ```sql
   -- If you want to remove the custom field entirely
   DELETE FROM documents_customfieldinstance 
   WHERE field_id IN (
       SELECT id FROM documents_customfield 
       WHERE name = 'Mail UID'
   );
   
   DELETE FROM documents_customfield 
   WHERE name = 'Mail UID';
   ```

No migration to undo since none was created.

## Maintenance & Upgrades

### Identifying RKC Changes

All customizations marked with RKC comment blocks:

```python
# RKC: Description of what this change does
[customized code]
# /end RKC edit
```

### Finding All Changes

```bash
# Search all RKC markers
grep -r "RKC:" src/

# Specific to mail correlation
grep -r "RKC:.*mail.*uid" src/ -i
grep -r "PAPERLESS_MAIL_CORRELATION_FIELD" src/

# List affected files
grep -l "RKC:" src/**/*.py
```

Expected output:
- `src/paperless/settings.py`
- `src/documents/data_models.py`
- `src/paperless_mail/mail.py`
- `src/documents/consumer.py`

### Upgrade Process

When upgrading Paperless-ngx:

1. **Before Upgrade**
   ```bash
   # Document current RKC changes
   grep -B2 -A5 "RKC:" src/**/*.py > rkc_changes_backup.txt
   
   # Note file modification dates
   ls -l src/paperless/settings.py
   ls -l src/documents/data_models.py
   ls -l src/paperless_mail/mail.py
   ls -l src/documents/consumer.py
   ```

2. **During Upgrade**
   - Apply upstream changes via git/pull
   - Check for merge conflicts in RKC files
   - Resolve conflicts preserving RKC blocks

3. **After Upgrade**
   ```bash
   # Verify RKC markers still present
   grep -c "RKC:" src/**/*.py
   # Should show 6 matches (6 RKC blocks)
   
   # Run tests
   python manage.py test
   
   # Manual verification
   # Process test email, verify custom field attached
   ```

4. **Conflict Resolution**
   
   If upstream changes conflict with RKC blocks:
   
   ```bash
   # Example: settings.py conflict
   <<<<<<< HEAD
   # RKC: Custom field name for storing email UID correlation
   PAPERLESS_MAIL_CORRELATION_FIELD = config.get(
       "PAPERLESS_MAIL_CORRELATION_FIELD",
       default="Mail UID",
   )
   # /end RKC edit
   =======
   # Upstream added new setting here
   PAPERLESS_NEW_FEATURE = config.get("PAPERLESS_NEW_FEATURE")
   >>>>>>> upstream/main
   ```
   
   Resolution:
   ```python
   # Upstream added new setting here
   PAPERLESS_NEW_FEATURE = config.get("PAPERLESS_NEW_FEATURE")
   
   # RKC: Custom field name for storing email UID correlation
   PAPERLESS_MAIL_CORRELATION_FIELD = config.get(
       "PAPERLESS_MAIL_CORRELATION_FIELD",
       default="Mail UID",
   )
   # /end RKC edit
   ```

### Critical Areas to Monitor

1. **ConsumableDocument Refactoring**
   - If dataclass structure changes significantly
   - If serialization mechanism changes
   - Action: Update mail_uid field to match new pattern

2. **Consumer Plugin Changes**
   - If document save timing changes
   - If plugin architecture refactored
   - Action: Adjust where _attach_mail_uid_custom_field() is called

3. **Mail Processing Changes**
   - If ConsumableDocument creation moves
   - If message.uid becomes unavailable
   - Action: Find new location to pass UID

4. **Custom Field System Changes**
   - If CustomField/CustomFieldInstance models change
   - If field creation API changes
   - Action: Update _attach_mail_uid_custom_field() implementation

## Benefits

### Reliability
- ✅ Works regardless of Celery configuration (single/multiple workers)
- ✅ Works regardless of email processing volume
- ✅ Explicit database relationship, not timing-dependent
- ✅ Survives system restarts, queue backlogs, etc.

### Maintainability
- ✅ Only 4 code changes across 3 files
- ✅ All changes clearly marked with RKC comments
- ✅ No database migration to manage
- ✅ Easy to search and identify during upgrades

### Usability
- ✅ Simple SQL queries to find related documents
- ✅ Visible in UI as custom field
- ✅ Can be filtered/searched like any custom field
- ✅ Configurable field name to avoid conflicts

### Robustness
- ✅ Non-critical - failures don't abort document consumption
- ✅ Idempotent - safe if called multiple times
- ✅ Graceful degradation - missing UID just skips attachment
- ✅ Clear logging for troubleshooting

## Alternatives Considered

### 1. Add ForeignKey to Document model
**Rejected because:**
- Requires database migration
- Changes core schema
- Hard to maintain during upgrades
- Would need to be upstreamed or constantly reapplied

### 2. Create separate correlation table
**Rejected because:**
- Requires database migration
- Adds schema complexity
- CustomField already provides this exact functionality
- More code to maintain

### 3. Store correlation in document notes
**Rejected because:**
- Not queryable efficiently
- Mixes structured and unstructured data
- User-editable (could be deleted)
- No data type enforcement

### 4. Use document tags for correlation
**Rejected because:**
- Tags are for categorization, not correlation
- Would create hundreds/thousands of meaningless tags
- Tag system not designed for unique identifiers
- Pollutes tag namespace

## Security & Privacy Considerations

### Data Exposure
- Mail UID is already stored in ProcessedMail table
- Custom field makes it visible in document UI
- UIDs are not sensitive (just IMAP message numbers)
- No additional data exposure beyond existing system

### Access Control
- Custom fields respect document permissions
- Users can only see custom fields on documents they can access
- No privilege escalation risk
- Same security model as all other custom fields

### Data Retention
- Mail UIDs persist even if ProcessedMail entry deleted
- Orphaned UIDs are harmless (just strings)
- Can be cleaned up manually if desired
- No compliance implications (UIDs are not personal data)

## Future Enhancements

### Potential Improvements
1. **UI Enhancement**: Show mail subject/date in document view from ProcessedMail
2. **Bulk Operations**: "Find all documents from this email" button in UI
3. **Cleanup Tool**: Remove custom field instances for deleted ProcessedMail entries
4. **Statistics**: Dashboard showing documents per email, emails per rule, etc.
5. **API Endpoint**: RESTful endpoint to query documents by mail UID

### Upstreaming Potential
This feature could be proposed to Paperless-ngx upstream:
- Minimal code changes
- Uses existing infrastructure
- Clear use case
- No breaking changes
- Well-documented

If upstreamed, RKC markers can be removed.

## Version History

- **v1.0.0 (2025-12-05)**: Initial implementation plan
  - Analysis of async processing problem
  - Custom field solution design
  - Minimal code change approach
  - RKC marker standards compliance
  - No database migration required

---

**Maintained by:** Rob Kenis Consulting (RKC)
**Last Updated:** 2025-12-05
**Related Documentation:** `RKC_CUSTOMIZATIONS.md`
