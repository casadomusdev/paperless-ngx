# IMPLEMENT.md

## GOAL

Fix two related issues with encrypted/signed PDFs that prevent archive file creation:

1. **Paperless-internal fix**: When OCRmyPDF raises `DigitalSignatureError` or `EncryptedPdfError`, copy the original PDF as the archive file so all downstream features work (download, bulk export, AI OCR, metadata).
2. **AI OCR fallback**: When `DOCUMENT_ARCHIVE_PATH` is missing/empty for any reason, fall back to `DOCUMENT_SOURCE_PATH` instead of skipping.

## ANALYSIS

### Root Cause (Paperless-Internal)

In `src/paperless_tesseract/parsers.py`, the `except (DigitalSignatureError, EncryptedPdfError)` handler (line 393) extracts text from the original but never sets `self.archive_path`. It stays `None`. The consumer at line 685 then skips archive creation because `archive_path` is `None`.

This means encrypted/signed PDFs get `has_archive_version = False`, which causes:
- Archive download dropdown hidden in UI
- Bulk download (archive-only) skips the document
- AI OCR post-consume script skips (archive=None)
- Document metadata missing archive info
- Exporter skips archive export

### Root Cause (AI OCR)

In `scripts/ai_ocr_post_consume.py`, line 281-283, when `archive_path` is empty or doesn't exist, the script exits with code 0 (skip). No fallback to the original document file.

## IMPLEMENTATION

### Fix 1: Paperless-Internal (parsers.py)

In `src/paperless_tesseract/parsers.py`, modify the `except (DigitalSignatureError, EncryptedPdfError)` block to copy the original PDF as the archive file. This ensures `archive_path` is set, the consumer creates `archive_filename`, and `has_archive_version` returns `True`.

### Fix 2: AI OCR Fallback (ai_ocr_post_consume.py)

In `scripts/ai_ocr_post_consume.py`, modify section 4 to fall back to `DOCUMENT_SOURCE_PATH` when archive is missing. Also update the docstring to document the fallback.

### Documentation Updates

- `docs/rkc/ai-ocr.md` — Update "Graceful failures" section
- `docs/rkc/bug-fixes.md` — Document the encrypted/signed PDF archive fix
