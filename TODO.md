# TODO

## Phase 2 — Retry on paperless API calls
- [x] New `scripts/ai_ocr_http.py` with `http_request()` + `retry_delay()`
- [x] Use it for the tag GET and content PATCH in `ai_ocr_post_consume.py`
- [x] Drop the duplicated local `_retry_delay` from `ai_ocr_post_consume.py`

## Phase 3 — AI_OCR_PAPERLESS_URL
- [x] Add env lookup (falls back to PAPERLESS_URL) in post_consume, rerun, test

## Phase 4 — Keep loud failure
- [x] Confirm retries exhausted still exits non-zero (no behavioural change)

## Phase 5 — Docs, sample env, tests, structure
- [x] docs/rkc/ai-ocr.md
- [x] docs/rkc/environment-variables.md
- [x] RKC_CUSTOMIZATIONS.md (fix stale AI_OCR_RASTERIZE_FALLBACK row)
- [x] docker/compose/docker-compose.env sample
- [x] scripts/test_ai_ocr_helpers.py (offline unit tests)
- [x] STRUCTURE.md

## Future improvements
- Offline unit tests for `rasterize_pdf()` (needs poppler/ImageMagick).
- Consider retry for the downloads in `ai_ocr_rerun.py` / `ai_ocr_test.py`.
- Config export/import: REST API endpoints + Angular UI (currently CLI only).
- Config export/import: a destructive `replace` (wipe) import mode.
- Operator: re-run `ai_ocr_rerun.py` on a gibberish doc with `AI_OCR_FALLBACK_MODEL=azure-ocr` and confirm the fallback engages.
- Consider `AI_OCR_FALLBACK_EXTRA_PARAMS` so Mistral-only params can be applied to non-"mistral"-named models.
