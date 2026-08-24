# TODO.md

## Current Task: Select All Across Pages

- [x] Add `allObjectIds` property to ManagementListComponent
- [x] Capture `c.all` from API response in `reloadData()`
- [x] Add `selectAll()` method
- [x] Add `isAllSelected` getter
- [x] Add "Select all" link in HTML template footer
- [x] Add unit tests
- [x] TypeScript type check passed

## Previous Task: Email Queue (Complete)

- [x] Phase 1: PendingEmail Model (models.py + migration 1076)
- [x] Phase 2: Queue Processing Core (email_queue.py)
- [x] Phase 3: Inline Retry in send_email() (documents/mail.py)
- [x] Phase 4: Integrate Queue into email_action() (signals/handlers.py)
- [x] Phase 5: Integrate Queue into Manual Sends (documents/views.py)
- [x] Phase 6: Settings and Beat Schedule (settings.py + urls.py)
- [x] Phase 7: Documentation — deferred to end of task
- [x] Phase 8: Admin UI Backend (email_queue_api.py)
- [x] Phase 8: Admin UI Frontend (pending-email-dialog + service + data model)

## Future Improvements

- Consider adding a per-webhook retry mechanism for transient failures
- Consider making the webhook fire asynchronously via Celery task
- Consider adding a source field to the webhook payload
- Consider filtering attachments from webhook payload when they exceed a configurable size threshold
- Consider adding a metric/alert for ABANDONED emails
