# TODO: v1.2.1 Duplicate Document Re-Add

## Phase 1: Settings
- [x] Add `CONSUMER_READD_DOCUMENTS` boolean setting (default false)
- [x] Add `CONSUMER_READD_TAG_ID` integer setting (None if not set)
- [x] Add `CONSUMER_READD_ADD_NOTE` boolean setting (default true)
- [x] Add `CONSUMER_READD_RETRASH` boolean setting (default false)

## Phase 2: Consumer Logic
- [x] Modify `pre_check_duplicate()` to check re-add conditions before raising error
- [x] Add `_handle_readd()` method (reset added date, apply tag, create note)
- [x] Add `_build_readd_source_info()` method (mail metadata or source type context)
- [x] Handle file cleanup for duplicate when re-add succeeds
- [x] Handle trashed duplicates: restore → re-add → optionally re-trash
- [x] Add "Restored from trash" indicator in re-add notes
- [x] Re-trash logic when `CONSUMER_READD_RETRASH=true`

## Phase 3: Documentation
- [x] Update `RKC_CUSTOMIZATIONS.md` — At A Glance entry under "Document Processing"
- [x] Update `RKC_CUSTOMIZATIONS.md` — Core Features section "### 7. Duplicate Document Re-Add"
- [x] Update `RKC_CUSTOMIZATIONS.md` — Environment Variables entries 8, 9, 10, 11
- [x] Update `RKC_CUSTOMIZATIONS.md` — Version History entry v1.2.1
- [x] Update `IMPLEMENT.md` with current task
- [x] Update `TODO.md` with current task

## Future Improvements
- Template preview/validation in the UI (render templates with dummy data to show users what the output will look like)
- MS365 Graph API sending support for workflow emails (currently only SMTP)
- Recipient auto-suggestion from correspondent email addresses
- Email delivery status tracking and retry mechanism
- Template library/snippets for common email patterns
- Re-add count tracking: store how many times a document has been re-added (custom field or model field)
- Re-add notification: workflow trigger when a document is re-added (e.g. send email alert)
- UI indicator for re-added documents (badge or icon showing document was re-surfaced)
- Auto-remove re-add tag when document is manually processed/acknowledged
