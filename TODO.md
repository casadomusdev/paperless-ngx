# TODO: Mail Action Connection Pooling Implementation

## Phase 1: Model Changes
- [x] Add PENDING_POST_ACTION status to ProcessedMail model
- [x] Create database migration for new status (NOT NEEDED - CharField accepts any value)
- [x] Test migration on development database (NOT NEEDED)

## Phase 2: Helper Tasks
- [x] Implement update_mail_status shared task
- [x] Add error handling for non-existent ProcessedMail IDs
- [x] Add logging for status updates

## Phase 3: Refactor Consumption Tasks
- [x] Modify queue_consumption_tasks() to create PENDING_POST_ACTION entries
- [x] Update error_callback() to create FAILED status directly (ALREADY DOES THIS)
- [x] Remove apply_mail_action callback from chord
- [x] Preserve owner field in ProcessedMail creation

## Phase 4: Batch Processing Tasks
- [x] Implement process_pending_mail_actions() scheduled task
- [x] Implement process_account_pending_actions() batch processor
- [x] Add proper error handling and logging
- [x] Handle auth failures gracefully

## Phase 5: Celery Configuration
- [x] Add process_pending_mail_actions to celery beat schedule
- [x] Configure 5-minute interval
- [x] Find correct location in celery.py for beat schedule

## Phase 6: Documentation
- [x] Update RKC_CUSTOMIZATIONS.md with v1.0.17 entry
- [x] Document new status in implementation notes
- [x] Add testing instructions

## Phase 7: Testing
- [ ] Test single email processing end-to-end
- [ ] Test batch processing with multiple emails
- [ ] Verify PENDING_POST_ACTION transitions to SUCCESS
- [ ] Verify error cases create FAILED status
- [ ] Check connection pooling eliminates auth storms

## IMPLEMENTATION COMPLETE - READY FOR TESTING

All code changes have been implemented. The system is ready for deployment and testing.

**To deploy:**
1. Restart Celery workers to load new tasks
2. Ensure Celery Beat is running for scheduled processing
3. Monitor logs for "Processing X pending mail actions" messages
4. PENDING_POST_ACTION entries should transition to SUCCESS within 5 minutes

**Files Modified:**
- `src/paperless_mail/models.py` - Documented PENDING_POST_ACTION status
- `src/paperless_mail/mail.py` - Added 3 new tasks, modified queue_consumption_tasks
- `src/paperless/celery.py` - Added Celery Beat schedule
- `RKC_CUSTOMIZATIONS.md` - Added v1.0.17 entry
- `IMPL_MAIL_ACTION_POOLING.md` - Implementation documentation

## Future Improvements (Not in Scope)
- [ ] Add unique constraint on (rule, uid, folder)
- [ ] Implement auto-cleanup of old ProcessedMail entries
- [ ] Make batch interval configurable via environment variable
- [ ] Add metrics for batch processing performance
