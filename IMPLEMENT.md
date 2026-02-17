# Duplicate Document Re-Add (v1.2.1)

## GOAL

When a duplicate document is detected during consumption, instead of silently rejecting it, reset the existing document's `added` date so it surfaces at the top of the inbox again. Essential for invoice reminder workflows where the same invoice PDF is re-sent via email when payment is overdue. Optionally tag the document and add an informational note with source context.

## ANALYSIS

### Existing Infrastructure
- `ConsumerPreflightPlugin.pre_check_duplicate()` in `consumer.py` computes MD5 of incoming file and checks against `checksum` and `archive_checksum` of all existing documents
- If duplicate found, raises `ConsumerError` — document is rejected
- `Document.added` field uses `auto_now_add=True`, requiring `Document.objects.filter(pk=pk).update(added=now)` to bypass
- `Note` model (`SoftDeleteModel`) with `note` text field and `document` FK available for adding notes
- `ConsumableDocument` dataclass has `source`, `mail_uid`, `mail_from`, `mail_sender`, `mail_subject`, `mail_date` fields
- `DocumentSource` enum: ConsumeFolder=1, ApiUpload=2, MailFetch=3, WebUI=4
- Settings pattern uses `__get_boolean()`, `__get_int()`, `os.getenv()` helpers

### Key Design Decisions
- 3 new env vars: `PAPERLESS_CONSUMER_READD_DOCUMENTS` (bool, default false), `PAPERLESS_CONSUMER_READD_TAG_ID` (int, optional), `PAPERLESS_CONSUMER_READD_ADD_NOTE` (bool, default true)
- Trashed documents (`deleted_at is not None`) should NOT be re-added — falls through to normal duplicate rejection
- Works with ALL document sources (not just mail), with source-specific context in notes
- No database migrations required — uses existing models
- Feature disabled by default for backward compatibility

## IMPLEMENTATION

### Phase 1: Settings
1. Add `CONSUMER_READD_DOCUMENTS` boolean setting (default false)
2. Add `CONSUMER_READD_TAG_ID` integer setting (None if not set)
3. Add `CONSUMER_READD_ADD_NOTE` boolean setting (default true)

### Phase 2: Consumer Logic
1. Modify `pre_check_duplicate()`: at the top of the `if existing_doc.exists():` block, check `settings.CONSUMER_READD_DOCUMENTS` and `existing_doc.first().deleted_at is None`
2. If conditions met, call `self._handle_readd(existing_doc.get())`, handle file deletion, and return early
3. Add `_handle_readd(self, existing_doc: Document)` method: reset `added` via `.update()`, apply tag if configured, create Note if enabled
4. Add `_build_readd_source_info(self)` method: return mail metadata for MailFetch source, or source type + filename for other sources

### Phase 3: Documentation
1. Update `RKC_CUSTOMIZATIONS.md` — At A Glance, Core Features section, Environment Variables, Version History
