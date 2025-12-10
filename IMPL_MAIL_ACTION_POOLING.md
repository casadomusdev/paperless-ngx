# Implementation Plan: Mail Action Connection Pooling

## GOAL

Refactor the paperless-ngx mail processing system to eliminate OAuth2 authentication connection storms that trigger Microsoft IMAP rate limiting. Currently, each consumed email spawns an asynchronous Celery task that independently authenticates to perform post-consumption actions (mark as read, move, delete, etc.), causing hundreds of simultaneous authentication requests that exceed Microsoft's undocumented IMAP throttling limits.

## ANALYSIS

### Current Architecture Problems

1. **Connection Storm Pattern**
   - `queue_consumption_tasks()` uses Celery chord pattern
   - Each email spawns: `chord(header=[consume_tasks], body=apply_mail_action.s())`
   - 100 emails = 100 parallel chord completions = 100 near-simultaneous `apply_mail_action` calls
   - Each `apply_mail_action` creates new IMAP connection and authenticates
   - Microsoft rate limits OAuth2 token validation → `AUTHENTICATE failed` errors

2. **ProcessedMail Duplicate Entries**
   - Same UID can have multiple entries due to:
     - Multiple attachments per email (each creates consumption task)
     - EML + attachments processing (consumption_scope=EVERYTHING)
     - Multiple rules processing same UID
   - No unique constraint on (rule, uid, folder)

3. **Frontend Compatibility**
   - ProcessedMail dialog displays all statuses
   - User expects final status to be SUCCESS or FAILED
   - PENDING_POST_ACTION must be transient internal status

### Root Cause

The async Celery chord pattern, while efficient for parallel file consumption, creates an architectural impedance mismatch with IMAP's synchronous connection model. Each post-consumption action requires opening a new authenticated connection, and Microsoft's OAuth2 token validation has rate limits.

## IMPLEMENTATION

### Phase 1: Add Transient Status to Model

**File:** `src/paperless_mail/models.py`

Add new transient status that will be invisible to users in final state:

```python
STATUS_CHOICES = [
    ('SUCCESS', 'Success'),
    ('FAILED', 'Failed'),
    ('PROCESSED_WO_CONSUMPTION', 'Processed without consumption'),
    ('PENDING_POST_ACTION', 'Pending post-action'),  # RKC: Transient status for pooled processing
]
```

**Migration Required:** Yes - add new choice to status field

### Phase 2: Create Database Migration

**File:** `src/paperless_mail/migrations/00XX_add_pending_status.py`

Standard Django migration to add the new status choice.

### Phase 3: Add Helper Task for Status Updates

**File:** `src/paperless_mail/mail.py`

Create simple task to update ProcessedMail status:

```python
@shared_task
def update_mail_status(processed_mail_id: int, status: str, error: str = None):
    """
    Update status of a single ProcessedMail entry.
    
    RKC: Helper task for batched mail action processing to update individual
    mail statuses after pooled connection processing.
    """
    try:
        mail = ProcessedMail.objects.get(pk=processed_mail_id)
        mail.status = status
        if error:
            mail.error = error
        mail.save()
    except ProcessedMail.DoesNotExist:
        pass
```

### Phase 4: Refactor Consumption Completion

**File:** `src/paperless_mail/mail.py`

Modify `queue_consumption_tasks()` to create PENDING entries instead of calling `apply_mail_action`:

```python
def queue_consumption_tasks(...):
    # RKC: Create PENDING status entry instead of async post-action
    # This allows batched processing via scheduled task with pooled connections
    ProcessedMail.objects.create(
        owner=rule.owner,
        rule=rule,
        folder=rule.folder,
        uid=message.uid,
        subject=message.subject,
        received=make_aware(message.date) if is_naive(message.date) else message.date,
        status="PENDING_POST_ACTION",
    )
    
    # Chord without callback - status update handled by scheduled task
    chord(header=consume_tasks, body=None).delay()
```

Modify `error_callback()` to directly create FAILED entries:

```python
@shared_task
def error_callback(...):
    """Error callback creates final FAILED status directly."""
    ProcessedMail.objects.create(
        rule=rule,
        folder=rule.folder,
        uid=message.uid,
        subject=message.subject,
        received=make_aware(message_date) if is_naive(message_date) else message_date,
        status="FAILED",
        error=traceback.format_exc(),
    )
```

### Phase 5: Create Scheduled Batch Processor

**File:** `src/paperless_mail/mail.py`

Create new scheduled task that processes pending actions with pooled connections:

```python
@shared_task
def process_pending_mail_actions():
    """
    Scheduled task to process all pending mail actions with pooled IMAP connections.
    
    RKC: Batches pending post-actions by account to use single connection per account,
    eliminating OAuth2 authentication storms that trigger Microsoft rate limiting.
    """
    logger = logging.getLogger("paperless_mail")
    
    pending = ProcessedMail.objects.filter(
        status="PENDING_POST_ACTION"
    ).select_related('rule__account', 'rule')
    
    if not pending.exists():
        return
    
    logger.info(f"Processing {pending.count()} pending mail actions")
    
    # Group by account to pool connections
    by_account = {}
    for mail in pending:
        account_id = mail.rule.account.id
        by_account.setdefault(account_id, []).append(mail.id)
    
    # Process each account with ONE pooled connection
    for account_id, mail_ids in by_account.items():
        process_account_pending_actions.delay(account_id, mail_ids)


@shared_task
def process_account_pending_actions(account_id: int, mail_ids: list[int]):
    """
    Process all pending actions for ONE account with ONE pooled IMAP connection.
    
    RKC: Processes multiple mail actions through single authenticated session,
    avoiding per-action OAuth2 authentication that triggers rate limiting.
    """
    logger = logging.getLogger("paperless_mail")
    account = MailAccount.objects.get(pk=account_id)
    
    logger.info(f"Processing {len(mail_ids)} actions for account {account}")
    
    try:
        with get_mailbox(
            account.imap_server,
            account.imap_port,
            account.imap_security,
        ) as M:
            supports_gmail_labels = "X-GM-EXT-1" in M.client.capabilities
            mailbox_login(M, account)
            
            for mail_id in mail_ids:
                try:
                    mail = ProcessedMail.objects.get(pk=mail_id)
                    M.folder.set(mail.rule.folder)
                    action = get_rule_action(
                        mail.rule,
                        supports_gmail_labels=supports_gmail_labels
                    )
                    action.post_consume(M, mail.uid, mail.rule.action_parameter)
                    
                    update_mail_status.delay(mail_id, "SUCCESS")
                    
                except ProcessedMail.DoesNotExist:
                    logger.warning(f"ProcessedMail {mail_id} not found")
                except Exception as e:
                    logger.exception(f"Error processing mail {mail_id}: {e}")
                    update_mail_status.delay(
                        mail_id,
                        "FAILED",
                        traceback.format_exc()
                    )
                    
    except MailError as e:
        logger.error(f"Mail error for account {account}: {e}")
        # Mark all as failed if auth fails
        for mail_id in mail_ids:
            update_mail_status.delay(
                mail_id,
                "FAILED",
                f"Account authentication failed: {str(e)}"
            )
    except Exception as e:
        logger.exception(f"Unexpected error processing account {account}: {e}")
        for mail_id in mail_ids:
            update_mail_status.delay(
                mail_id,
                "FAILED",
                f"Unexpected error: {str(e)}"
            )
```

### Phase 6: Add Celery Beat Schedule

**File:** `src/paperless/celery.py`

Add scheduled task configuration:

```python
# RKC: Schedule batched mail action processing to avoid connection storms
app.conf.beat_schedule[' process-pending-mail-actions'] = {
    'task': 'paperless_mail.mail.process_pending_mail_actions',
    'schedule': crontab(minute='*/5'),  # Every 5 minutes
}
```

### Phase 7: Frontend Compatibility (Optional)

**Consideration:** PENDING_POST_ACTION is transient and should quickly transition to SUCCESS/FAILED. If users see this status in the UI, it simply means "being processed" which is acceptable. No frontend changes required unless we want to add special handling/icon for this status.

## BENEFITS

1. **Eliminates Connection Storms**
   - Single connection per account per batch
   - Natural rate limiting via 5-minute schedule
   - No simultaneous OAuth2 authentication requests

2. **Improved Reliability**
   - Batch processing tolerates individual failures
   - Failed auth affects batch, not individual mails
   - Retry-able via scheduled re-runs

3. **Better Resource Usage**
   - Connection pooling reduces overhead
   - Scheduled bursts easier to monitor
   - Predictable load pattern

4. **Minimal Code Impact**
   - Preserves existing task structure
   - Backward compatible (old entries unaffected)
   - Easy to test and rollback

## TESTING STRATEGY

1. **Unit Tests**
   - Test `update_mail_status` with valid/invalid IDs
   - Test `process_pending_mail_actions` grouping logic
   - Test `process_account_pending_actions` error handling

2. **Integration Tests**
   - Process single email end-to-end
   - Process batch of emails
   - Simulate auth failures
   - Verify final statuses are SUCCESS/FAILED only

3. **Manual Testing**
   - Monitor ProcessedMail table during processing
   - Verify PENDING_POST_ACTION transitions quickly
   - Check connection pooling in IMAP logs
   - Confirm no more OAuth2 auth storms

## ROLLBACK PLAN

If issues arise:
1. Revert migration to remove PENDING_POST_ACTION status
2. Revert mail.py changes to restore original chord callback
3. Remove celery beat schedule entry
4. Existing SUCCESS/FAILED entries remain valid

## FUTURE IMPROVEMENTS

1. Add unique constraint on (rule, uid, folder) to prevent duplicates
2. Add auto-cleanup of old ProcessedMail entries
3. Make batch schedule interval configurable via env var
4. Add metrics/monitoring for batch processing performance
