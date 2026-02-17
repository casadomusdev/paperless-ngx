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
2. If `CONSUMER_READD_DOCUMENTS=true`:
   - If existing doc is trashed → restore from trash first (`deleted_at=None`)
   - Reset `added` date to now (bypasses `auto_now_add=True` using `.update()`)
   - Apply tag (if `CONSUMER_READD_TAG_ID` configured)
   - Add note (if `CONSUMER_READD_ADD_NOTE` enabled) with source context
   - If doc was trashed AND `CONSUMER_READD_RETRASH=true` → re-trash document
   - Clean up duplicate file (if `CONSUMER_DELETE_DUPLICATES` is set)
   - Return from preflight (no error raised)
3. If feature disabled → normal duplicate rejection

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
- **Any workflow** where receiving a duplicate means "needs attention again"

## Files Modified

### Backend
- `src/paperless/settings.py` — 4 environment variable settings
- `src/documents/consumer.py` — Modified `pre_check_duplicate()`, added `_handle_readd()` and `_build_readd_source_info()` methods

## Version History

- **v1.2.1**: Initial implementation with full source-aware context, tagging, notes, and trashed document handling
