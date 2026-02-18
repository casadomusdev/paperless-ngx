# Duplicate Document Re-Add

When a duplicate document is detected during consumption, instead of silently rejecting it, the existing document's `added` date is reset so it surfaces at the top of the inbox again. Essential for invoice reminder workflows where the same PDF is re-sent when payment is overdue.

## Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PAPERLESS_CONSUMER_READD_DOCUMENTS` | Boolean | `false` | Master switch to enable the feature |
| `PAPERLESS_CONSUMER_READD_TAG_ID` | Integer | None | Tag ID to apply when a document is re-added |
| `PAPERLESS_CONSUMER_READD_ADD_NOTE` | Boolean | `true` | Add informational note with re-add context |
| `PAPERLESS_CONSUMER_READD_RETRASH` | Boolean | `false` | Re-trash trashed documents after re-add |

## Behavior Flow

1. Consumer detects duplicate via MD5 checksum match
2. If no checksum match and document is mail-sourced with a Mail UID → secondary dedup via Mail UID custom field lookup (handles EML files whose byte representation varies across fetches)
3. If `CONSUMER_READD_DOCUMENTS=true`:
   - If existing doc is trashed → restore from trash first (`deleted_at=None`)
   - Reset `added` date to now (bypasses `auto_now_add=True` using `.update()`)
   - Apply tag (if `CONSUMER_READD_TAG_ID` configured)
   - Add note (if `CONSUMER_READD_ADD_NOTE` enabled) with source context
   - If doc was trashed AND `CONSUMER_READD_RETRASH=true` → re-trash document
   - Clean up duplicate file (if `CONSUMER_DELETE_DUPLICATES` is set)
   - Raise `StopConsumeTaskError` to halt the plugin pipeline — prevents `ConsumerPlugin` from running and creating a duplicate document. The exception is caught cleanly in `tasks.py` and its message is returned as the task result.
4. If feature disabled → normal duplicate rejection

## Duplicate Detection

### Two-tier deduplication

**Tier 1 — MD5 Checksum** (all document types):
Computes MD5 of the incoming file and checks against `Document.checksum` and `Document.archive_checksum`. Works reliably for binary-identical files like PDFs and images.

**Tier 2 — Mail UID Custom Field** (mail-sourced documents only):
When no checksum match is found and the incoming document carries a `mail_uid` (set by the mail fetcher), queries `CustomFieldInstance` for an existing document with the same Mail UID value in the configured correlation field (`PAPERLESS_MAIL_UID_FIELD`, default: "Mail UID"). This catches EML duplicates where checksum-based dedup fails because `message.obj.as_bytes()` can produce different byte representations for the same email across fetches due to header reordering, MIME boundary regeneration, and line ending normalization.

Both tiers search `Document.global_objects` (including trashed documents) to ensure soft-deleted duplicates are caught.

## Features

### Added Date Reset
Uses `Document.objects.filter(pk=pk).update(added=now)` to bypass `auto_now_add=True`. Document appears at top of inbox when sorted by "Added" (default).

### Optional Tagging
If `CONSUMER_READD_TAG_ID` is set, applies the specified tag on each re-add. Graceful handling: logs warning if tag ID doesn't exist, doesn't abort. Useful for saved views filtering re-added documents.

### Informational Note
Creates a `Note` on the document with re-add details. Content varies by source:

**Mail sources** (`DocumentSource.MailFetch`):
```
Originally added:  2026-01-15 10:30:00
Re-added:  2026-02-17 14:22:00
In:  Default
Mail UID: 12345
Subject: Payment Reminder - Invoice #2024-001
From: accounts@company.com
```

**Other sources** (Consume Folder, API Upload, Web UI):
```
Originally added:  2026-01-15 10:30:00
Re-added:  2026-02-17 14:22:00
Source:  Consume Folder
Filename: invoice_2024-001.pdf
```

### Trashed Document Handling
- `Document.checksum` has a UNIQUE constraint — a second document with the same checksum cannot be created
- When a duplicate is trashed: restore → apply re-add logic → optionally re-trash
- If `CONSUMER_READD_RETRASH=true`: document stays in trash but with updated `added` date, tag, and note
- If `CONSUMER_READD_RETRASH=false` (default): document remains restored (out of trash)
- Note text includes "Restored from trash" and "(will be re-trashed)" indicators as appropriate

## Use Cases

- **Invoice reminders**: Same PDF re-sent when payment overdue → document resurfaces in inbox
- **Contract renewals**: Same contract PDF attached to reminder emails
- **Email re-processing**: Same EML consumed again (different mail rule, re-fetch) → detected via Mail UID and re-added instead of creating a duplicate
- **Any workflow** where receiving a duplicate means "needs attention again"

## Files Modified

### Backend
- `src/paperless/settings.py` — 4 environment variable settings
- `src/documents/consumer.py` — Modified `pre_check_duplicate()` (two-tier dedup with Mail UID fallback), added `_handle_readd()` and `_build_readd_source_info()` methods

## Version History

- **v1.2.1**: Full implementation with two-tier deduplication (MD5 checksum + Mail UID for EML), source-aware context, tagging, notes, and trashed document handling
