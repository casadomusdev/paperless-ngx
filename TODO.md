# TODO.md

## Phase 1: EML Duplicate Detection & Re-Add

- [x] Analyze why EML deduplication fails (MD5 checksum varies for same email across fetches)
- [x] Add Mail UID-based secondary dedup in `pre_check_duplicate()` in `consumer.py`
- [x] Halt pipeline after re-add via `StopConsumeTaskError` to prevent ConsumerPlugin from creating duplicates
- [x] Update `docs/rkc/duplicate-readd.md` with two-tier dedup documentation
- [x] Update `RKC_CUSTOMIZATIONS.md` feature description and version history
- [x] Git commit

## Future Improvements

- Consider content-hash based dedup (hash of extracted text) as a third dedup tier for documents consumed outside the mail system (e.g., via API or consume folder) that have semantically identical content but different file bytes
- Add EML dedup metrics/logging to track how often Tier 2 (Mail UID) catches duplicates vs Tier 1 (MD5)
