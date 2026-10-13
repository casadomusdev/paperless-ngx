# TODO: (cleared)

## Future improvements
- Config export/import: REST API endpoints + Angular UI (currently CLI only).
- Config export/import: a destructive `replace` (wipe) import mode.
- Config export/import: emit an env-variable reference file alongside the export.
- Operator: re-run `ai_ocr_rerun.py` on a gibberish doc with
  `AI_OCR_FALLBACK_MODEL=azure-ocr` and confirm the fallback engages.
- Consider a dedicated `AI_OCR_FALLBACK_EXTRA_PARAMS` so Mistral-only params
  (`extract_header`/`extract_footer`) can be applied to non-"mistral"-named
  models such as the `azure-ocr` fallback route.
- `RKC_CUSTOMIZATIONS.md` env table still lists a stale `AI_OCR_RASTERIZE_FALLBACK`
  row (real var is `AI_OCR_RASTERIZE`, a string: auto/always/never); also missing
  `AI_OCR_FALLBACK_MODEL` / `AI_OCR_STATS_LOG` / `AI_OCR_QUALITY_*`.
- Offline unit test for `check_quality()` covering both signals and false-positive
  guards (no server needed).
