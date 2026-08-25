# TODO.md

## Current Task: Encrypted/Signed PDF Archive Fix + AI OCR Fallback

- [x] Analysis: identified root cause in tesseract parser and AI OCR script
- [x] Fix 1: Modify `parsers.py` exception handler to copy original as archive
- [x] Fix 2: Modify `ai_ocr_post_consume.py` to fall back to `DOCUMENT_SOURCE_PATH`
- [x] Update `docs/rkc/ai-ocr.md` — document fallback behavior
- [x] Update `docs/rkc/bug-fixes.md` — document encrypted/signed PDF fix
- [x] Verify syntax (ast.parse) on changed Python files

## Future Improvements

- Consider adding a `PAPERLESS_OCR_ARCHIVE_FALLBACK_COPY` env var to control whether original is copied as archive (opt-in for safety)
