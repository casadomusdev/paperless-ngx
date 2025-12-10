# TODO: Mail Action Connection Pooling Implementation

## Phase 1: Model Changes
- [ ] Add PENDING_POST_ACTION status to ProcessedMail model
- [ ] Create database migration for new status
- [ ] Test migration on development database

## Phase 2: Helper Tasks
- [ ] Implement update_mail_status shared task
- [ ] Add error handling for non-existent ProcessedMail IDs
- [ ] Add logging for status updates

## Phase 3: Refactor Consumption Tasks
- [ ] Modify queue_consumption_tasks() to create PENDING_POST_ACTION entries
- [ ] Update error_callback() to create FAILED status directly
- [ ] Remove apply_mail_action callback from chord
- [ ] Preserve owner field in ProcessedMail creation

## Phase 4: Batch Processing Tasks
- [ ] Implement process_pending_mail_actions() scheduled task
- [ ] Implement process_account_pending_actions() batch processor
- [ ] Add proper error handling and logging
- [ ] Handle auth failures gracefully

## Phase 5: Celery Configuration
- [ ] Add process_pending_mail_actions to celery beat schedule
- [ ] Configure 5-minute interval
- [ ] Find correct location in celery.py for beat schedule

## Phase 6: Documentation
- [ ] Update RKC_CUSTOMIZATIONS.md with v1.0.17 entry
- [ ] Document new status in implementation notes
- [ ] Add testing instructions

## Phase 7: Testing
- [ ] Test single email processing end-to-end
- [ ] Test batch processing with multiple emails
- [ ] Verify PENDING_POST_ACTION transitions to SUCCESS
- [ ] Verify error cases create FAILED status
- [ ] Check connection pooling eliminates auth storms

## Future Improvements (Not in Scope)
- [ ] Add unique constraint on (rule, uid, folder)
- [ ] Implement auto-cleanup of old ProcessedMail entries
- [ ] Make batch interval configurable via environment variable
- [ ] Add metrics for batch processing performance
