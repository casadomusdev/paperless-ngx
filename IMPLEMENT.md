# IMPLEMENT.md

## GOAL

Fix EML document deduplication and enable re-add support for email text documents. The existing checksum-based dedup doesn't work for EML files because `message.obj.as_bytes()` can produce different byte representations for the same email across fetches. Add Mail UID-based deduplication as a secondary check so EML duplicates are caught and can be re-added/re-trashed like PDFs.

## ANALYSIS

### Root Cause
- `pre_check_duplicate()` uses MD5 checksum of the original file to detect duplicates
- For PDFs/images: same file → same MD5 → dedup works
- For EML files: same email → different serialization bytes → different MD5 → dedup fails
- Since dedup never identifies EML as duplicate, re-add/re-trash logic never triggers

### Solution
Add a secondary dedup check in `pre_check_duplicate()` for mail-sourced documents using the Mail UID custom field that's already stored on consumed documents. The `mail_uid` is available on `ConsumableDocument` at dedup time.

Check order:
1. Existing MD5 checksum check (unchanged — works for PDFs/images)
2. If no checksum match AND document is mail-sourced with a `mail_uid` → query `CustomFieldInstance` for existing document with same Mail UID value
3. If either check finds a match → apply re-add logic or reject as duplicate

## IMPLEMENTATION

### Phase 1: Code Change

Modify `pre_check_duplicate()` in `src/documents/consumer.py`:
- After the checksum check finds no match, add a Mail UID lookup
- Query `CustomFieldInstance` joined through `CustomField` (using the configured field name from settings)
- If Mail UID match found, retrieve the document and apply same duplicate handling (re-add or reject)
- Search `global_objects` (including trashed docs) to match checksum behavior

### Phase 2: Documentation Update

Update `docs/rkc/duplicate-readd.md` and `RKC_CUSTOMIZATIONS.md` to describe EML dedup behavior as part of v1.2.1.
