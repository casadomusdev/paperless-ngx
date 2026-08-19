# AI OCR via Post-Consumption Script

Replaces Tesseract OCR output with higher-quality text from an AI OCR provider
(Mistral OCR, Azure Document Intelligence, or any model exposed via LiteLLM's
`/v1/ocr` endpoint) without modifying the paperless-ngx source code.

## How It Works

1. **paperless-ngx consumes the document as normal** — Tesseract runs and
   produces its usual OCR output, which is stored in the `content` field.

2. **The post-consumption script fires** — paperless-ngx calls
   `PAPERLESS_POST_CONSUME_SCRIPT` once the document is fully indexed.

3. **The script checks the document MIME type** — email documents
   (`message/rfc822` and other `message/*` subtypes) are skipped immediately
   with exit code 0.  They are archived as PDF by Paperless, but AI OCR adds no
   value for structured email text.  More importantly, skipping prevents a race
   condition with the send-mail pipeline: if OCR ran on an email document it
   would PATCH `document_updated` before `patchCustomFields` (e.g., Email
   Subject) has been set, causing a Jinja2 `UndefinedError` in any workflow
   email template that references those custom fields.

4. **The script calls the LiteLLM `/v1/ocr` endpoint** — the document's
   archived PDF is base64-encoded and sent as a `data:application/pdf;base64,…`
   data URL in the request body.

5. **LiteLLM routes the request to the configured provider** — Mistral OCR,
   Azure Document Intelligence, or another provider with OCR capability. Cost
   tracking works via the native `/v1/ocr` endpoint (unlike the pass-through at
   `/mistral/v1/ocr` which bypasses accounting).

6. **The script PATCHes the `content` field** — the AI's markdown text is
   written to the document via `PATCH /api/documents/{id}/`.

7. **The search index auto-updates** — the `post_save` signal in
   `documents/signals/handlers.py` fires when the API persists the PATCH,
   so full-text search reflects the new content immediately.

### What Changes and What Doesn't

| Component              | Changed by this script |
|------------------------|------------------------|
| `content` field (DB)   | ✅ Replaced with AI OCR text |
| Full-text search index | ✅ Auto-updated via `post_save` |
| Archive PDF            | ❌ The Tesseract-layered PDF is kept as-is |
| PDF text selection     | ❌ Uses Tesseract layer (functional, slightly lower quality) |
| Metadata / tags / date | ❌ Untouched |

The archive PDF text layer (for text selection in the viewer) continues to use
the Tesseract layer. Only the database `content` field — used for search and the
document detail content panel — is upgraded.

---

## Configuration

All variables are set in your Docker Compose environment or `.env`. The script
is a no-op when `AI_OCR_ENABLED` is absent or not `"true"`.

### Required

| Variable              | Description |
|-----------------------|-------------|
| `AI_OCR_ENABLED`      | Set to `"true"` to enable; anything else disables the script silently |
| `AI_OCR_URL`          | LiteLLM proxy base URL, e.g. `http://litellm:4000` |
| `AI_OCR_KEY`          | LiteLLM virtual API key |
| `PAPERLESS_API_TOKEN` | Paperless superuser API token (create in Settings → Users) |

### Optional

| Variable         | Default                 | Description |
|------------------|-------------------------|-------------|
| `AI_OCR_MODEL`   | `mistral-ocr-latest`    | Model name as configured in LiteLLM |
| `AI_OCR_TAG_ID`  | _(none)_                | Tag ID to apply to the document on successful OCR. Requires a GET to fetch existing tags before the PATCH, so existing tags are preserved. No tag is added if unset. |
| `AI_OCR_DEBUG`    | `false`                 | Set to `"true"` to print the extracted OCR text to stdout and skip writing to the document. Useful for inspecting OCR quality without modifying any data. |
| `AI_OCR_LOG_FILE` | _(none)_                | Absolute path to a log file inside the container, e.g. `/logs/ai_ocr.log`. When set, every log line is appended to this file with a wallclock datetime prefix. Opt-in — no log file is written when unset. |
| `AI_OCR_MAX_RETRIES` | `3`                 | Maximum retry attempts on transient failures (empty content, HTTP 429/5xx, connection errors). Set to `0` to disable retries. |
| `AI_OCR_RETRY_DELAY` | `5`                 | Base retry delay in seconds. Doubles each attempt (5s → 10s → 20s). Respects `Retry-After` header on HTTP 429. |
| `AI_OCR_RASTERIZE`   | `auto`          | Rasterization mode: `"auto"` (try PDF first, rasterize on quality failure), `"always"` (always rasterize before OCR), `"never"` (no rasterization) |
| `AI_OCR_DEGRADATION_THRESHOLD` | `30`         | Percentage of garbage lines that triggers a rasterized retry. If the garbage percentage is below this threshold, only the garbage tail is stripped without retrying. |
| `PAPERLESS_URL`   | `http://localhost:8000` | Internal paperless URL |

---

## Docker Compose Setup

```yaml
services:
  webserver: &paperless
    environment:
      PAPERLESS_POST_CONSUME_SCRIPT: /usr/src/paperless/scripts/ai_ocr_post_consume.py
      AI_OCR_ENABLED: "true"
      AI_OCR_URL: "http://litellm:4000"
      AI_OCR_KEY: "sk-your-litellm-virtual-key"
      AI_OCR_MODEL: "mistral-ocr-latest"
      PAPERLESS_URL: "http://webserver:8000"
      PAPERLESS_API_TOKEN: "your-paperless-superuser-token"

  celery: *paperless   # consumer runs in the celery service

  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    # ... your existing LiteLLM config
```

> **Note:** The consumption worker is the `celery` service, not `webserver`.
> Both services must have the same environment variables. Using a YAML anchor
> (`&paperless` / `*paperless`) is the easiest way to share them.

### Script Path in Docker

The `scripts/` directory is mounted inside the container. Ensure it reaches:
```
/usr/src/paperless/scripts/ai_ocr_post_consume.py
```

The script must be executable — either `chmod +x` the file or mount it with
appropriate permissions. In practice, paperless-ngx calls it with the python3
interpreter from the shebang, so the execute bit is enough.

---

## LiteLLM Provider Configuration

### Mistral OCR

In your LiteLLM `config.yaml`:
```yaml
model_list:
  - model_name: mistral-ocr-latest
    litellm_params:
      model: mistral/mistral-ocr-latest
      api_key: os.environ/MISTRAL_API_KEY
```

Then set `AI_OCR_MODEL: "mistral-ocr-latest"`.

Whenever `AI_OCR_MODEL` contains the string `"mistral"` (case-insensitive), the
script automatically adds `extract_header: true` and `extract_footer: true` to
every OCR request. These Mistral-specific parameters instruct the model to
include document headers and footers in the extracted text, which are skipped by
default. No extra configuration is needed.

### Azure Document Intelligence

```yaml
model_list:
  - model_name: azure-doc-intel
    litellm_params:
      model: azure_ai/azure-doc-intel
      mode: ocr
      api_base: https://your-resource.cognitiveservices.azure.com/
      api_key: os.environ/AZURE_DOC_INTEL_KEY
```

Then set `AI_OCR_MODEL: "azure-doc-intel"`.

### Azure AI OCR

```yaml
model_list:
  - model_name: azure-ocr
    litellm_params:
      model: azure_ai/azure-ocr
      mode: ocr
      api_base: https://your-resource.cognitiveservices.azure.com/
      api_key: os.environ/AZURE_OCR_KEY
```

All three providers return the same response format:
```json
{
  "pages": [
    { "index": 0, "markdown": "... extracted text ..." },
    { "index": 1, "markdown": "... page 2 text ..." }
  ]
}
```

The script joins pages with `\n\n` before writing to the `content` field.

---

## Cost Tracking

LiteLLM's native `/v1/ocr` endpoint is used (not the pass-through
`/mistral/v1/ocr`). This means:

- ✅ Cost tracked per token / per request in LiteLLM's spend log
- ✅ Virtual key budgets and rate limits apply
- ✅ Team/user attribution works

If you use the Mistral pass-through (`/mistral/v1/ocr`), cost tracking is
bypassed. Always configure via the model list approach above.

---

## Implementation Details

- **Script locations**: `scripts/ai_ocr_post_consume.py` (main logic) and
  `scripts/ai_ocr_quality.py` (quality detection + PDF rasterization)
- **No source modifications**: purely a post-consumption hook, zero changes to
  paperless-ngx Python or TypeScript code
- **No third-party dependencies**: uses only Python stdlib (`base64`, `json`,
  `os`, `sys`, `urllib`, `subprocess`, `glob`, `shutil`).  Rasterization uses
  `pdftoppm` (poppler-utils) and `convert` (ImageMagick), both already installed
  in the paperless-ngx Docker image.
- **Graceful failures**: if the document MIME type starts with `message/`
  (email documents), the script exits with code 0 and logs the skip reason.
  If the archive path is missing for any other document type, the script also
  exits with code 0 and logs clearly (no error; paperless continues normally).
  If the OCR returns empty content, the script exits with code 0 (no-op),
  preserving Tesseract output.
- **Large file handling**: the script base64-encodes the whole PDF in memory.
  For most scanned documents (< 50 MB) this is fine. Very large multi-hundred-
  page PDFs may hit LiteLLM or provider upload limits.

---

## Quality Detection & Rasterization Fallback

Some OCR providers (notably Mistral) occasionally produce degraded output where
valid header content is followed by a long tail of single-character garbage lines
(e.g., `K\nK\nK\n...`).  The script automatically detects and compensates for
this pattern.

### How Quality Detection Works

After receiving OCR content, the script scans for **garbage lines** — lines that
are ≤2 characters and entirely alphabetic (catches `"K"`, `"k"`, `"a"`, `"OK"`,
etc.).  If 3+ consecutive garbage lines are found (empty lines between them are
ignored), the script calculates what percentage of total lines are garbage.

| Garbage % | Outcome |
|-----------|---------|
| 0% | Content is clean — use as-is |
| Below threshold (default 30%) | Minor garbage — use content as-is |
| Above threshold | Significant degradation — trigger rasterization fallback |

The check is **detection-only** — it never strips or modifies content.  When
degradation is detected, the only remedy is rasterization.

### How Rasterization Works

When triggered, the script:

1. Converts each PDF page to a 300 DPI PNG using `pdftoppm` (poppler-utils)
2. Reassembles the PNGs into a clean, pixel-based PDF using ImageMagick `convert`
3. Sends the rasterized PDF to the OCR API as a second attempt
4. Compares the quality of both results and uses the better one

Rasterization eliminates font encoding issues, unusual text layers, and other
PDF-structural oddities that can confuse the OCR engine — the model sees pure
pixel content.

### When It Helps

Rasterization is most effective for PDFs with:
- Unusual font encodings or missing ToUnicode maps
- Layered content where text partially overlaps
- Scanned documents with complex layouts that confuse text extraction
- Documents where the OCR engine "gives up" partway through

### Controlling the Behavior

| Env var | Default | Purpose |
|---------|---------|---------|
| `AI_OCR_RASTERIZE` | `auto` | `"auto"` — try PDF first, rasterize on quality failure. `"always"` — always rasterize before OCR (best quality, higher cost). `"never"` — disable rasterization entirely. |
| `AI_OCR_FALLBACK_MODEL` | _(empty)_ | Fallback OCR model for table-only failures. When the primary model returns only table blocks, tries this model on the original PDF first, then on rasterized if needed. Example: `mistral-ocr-latest`. |
| `AI_OCR_STATS_LOG` | _(empty)_ | Path to a JSON-lines stats log file (e.g. `/logs/ai_ocr_stats.jsonl`). Each OCR run appends one JSON object with metrics. Disabled if empty. |
| `AI_OCR_QUALITY_MODEL` | _(empty)_ | Cheap LLM model for quality evaluation (e.g. `mistral-small-latest`). Empty = disabled. |
| `AI_OCR_QUALITY_KEY` | _(empty)_ | API key for the quality model. Falls back to `AI_OCR_KEY`. |
| `AI_OCR_QUALITY_URL` | _(empty)_ | LiteLLM URL for quality model. Falls back to `AI_OCR_URL`. |
| `AI_OCR_QUALITY_THRESHOLD` | `70` | Minimum quality score (0-100). Below this, rasterization is triggered. |
| `AI_OCR_DEGRADATION_THRESHOLD` | `30` | Percentage of garbage lines that triggers retry. Increase for stricter detection, decrease to retry more aggressively. |

### LLM Quality Check (optional)

When `AI_OCR_QUALITY_MODEL` is set, the script sends a sample of the OCR output
to a cheap LLM and asks it to rate text quality on a 0-100 scale.  This catches
subtle quality issues that the deterministic checks miss — garbled text, poor OCR
accuracy, or content that looks structurally fine but is actually low quality.

The check only runs when:
- The deterministic checks (table-only, garbage pattern) passed clean
- The document is a PDF (can rasterize)
- Rasterization is not disabled

The LLM receives a ~2000-char sample (first half + last half of the content)
and returns a single number.  Cost is minimal (~500 input tokens, ~2 output tokens).

**Docker Compose example:**
```yaml
services:
  webserver: &paperless
    environment:
      AI_OCR_QUALITY_MODEL: "mistral-small-latest"
      AI_OCR_QUALITY_KEY: "sk-your-quality-key"
      AI_OCR_QUALITY_THRESHOLD: "70"
```

If the score is below the threshold, the PDF is rasterized and re-OCRed.  The
rasterized result is used if it's non-empty and at least half the length of the
basic result (sanity check).

### Log Output for Quality Issues

```
AI OCR [ 13.4s]: Quality check FAILED — 45% garbage lines detected (threshold: 30%)
AI OCR [ 13.4s]: Rasterization fallback enabled — converting PDF to pixel-based format...
AI OCR [ 15.8s]: Rasterized PDF: 2,340,567 bytes
AI OCR [ 15.8s]: Sending OCR request to http://litellm:4000/v1/ocr (timeout=300s)...
AI OCR [ 28.2s]: OCR request completed in 12.4s — HTTP 200
AI OCR [ 28.2s]: Rasterized retry: 4 page(s), 3945 chars
AI OCR [ 28.2s]: Rasterized result is better (garbage: 0% vs 45%) — using it
```

---

## Re-running AI OCR on Existing Documents

The `ai_ocr_rerun.py` script re-processes a document that already exists in
paperless.  It downloads the archived PDF (or falls back to the original if
no archive exists), runs the AI OCR pipeline, and updates the document.

### Regular mode — update the document

```bash
docker exec -it casabot-filderbau-paperless \
  python3 /usr/src/paperless/scripts/ai_ocr_rerun.py 19713
```

Output:
```
Fetching document 19713 from https://inbox.filderbau.casabot.de …
Downloading archived PDF from https://inbox.filderbau.casabot.de/api/documents/19713/download/?original=false …
Downloaded 230,194 bytes.
Running AI OCR on document 19713 (tmp: /tmp/tmpXXXXXX.pdf) …
AI OCR [   0.0s]: Starting — doc=19713, model=mistral-ocr-latest, archive=/tmp/tmpXXXXXX.pdf
AI OCR [   0.9s]: Extracted 1 page(s), 3025 chars of text
AI OCR [   0.9s]: Quality check passed — content is clean
AI OCR [   1.2s]: Document 19713 updated successfully — 1 page(s), 3025 chars, model: mistral-ocr-latest, total time: 1.2s
```

### Debug mode — inspect without modifying

Add `AI_OCR_DEBUG=true` to see the full Mistral response (images stripped)
and extracted text **without updating the document**:

```bash
docker exec -e AI_OCR_DEBUG=true -it casabot-filderbau-paperless \
  python3 /usr/src/paperless/scripts/ai_ocr_rerun.py 19713
```

Output includes the raw Mistral response JSON and extracted text:
```
AI OCR [   0.9s]: DEBUG MODE — raw Mistral response (images stripped):
────────────────────────────────────────────────────────────────────────
{
  "pages": [
    {
      "index": 0,
      "markdown": "... full markdown content ...",
      "images": [],
      "blocks": [...]
    }
  ],
  "model": "mistral-ocr-latest"
}
────────────────────────────────────────────────────────────────────────
AI OCR [   0.9s]: DEBUG MODE — extracted text (1 page(s), 3025 chars):
────────────────────────────────────────────────────────────────────────
[extracted text here]
────────────────────────────────────────────────────────────────────────
AI OCR [   0.9s]: DEBUG MODE done — 1 page(s), 3025 chars
```

### Batch re-run

```bash
# Re-run AI OCR on multiple documents
for doc_id in 19699 19713 19711; do
  docker exec -it casabot-filderbau-paperless \
    python3 /usr/src/paperless/scripts/ai_ocr_rerun.py $doc_id
done
```

---

## Obtaining a Paperless API Token

1. Go to **Settings → Users** in the paperless-ngx UI
2. Click on the superuser account
3. Scroll to **Auth Token** → copy the token

Or via CLI:
```bash
docker compose exec webserver python3 manage.py drf_create_token <username>
```

---

## Log File

By default the script logs only to stdout/stderr, which ends up in the celery
container log. To get a persistent, human-readable audit log, set
`AI_OCR_LOG_FILE` to an absolute path **inside the container**.

### Docker Compose example

```yaml
services:
  webserver: &paperless
    environment:
      AI_OCR_LOG_FILE: "/logs/ai_ocr.log"
    volumes:
      - paperless-ai-ocr-logs:/logs

  celery: *paperless

volumes:
  paperless-ai-ocr-logs:
```

The directory is created automatically if it does not exist. The file is opened
in append mode, so it accumulates across restarts.

### Log format

Each line in the file has a wallclock datetime prefix followed by the normal
`AI OCR [Xs]:` line that also appears in celery's output:

```
2026-03-30T12:05:01 AI OCR [  0.0s]: Starting — doc=447, model=mistral-ocr-latest, archive=/tmp/tmpXXXXXX.pdf
2026-03-30T12:05:01 AI OCR [  0.1s]: Read archive file: 1,204,832 bytes
2026-03-30T12:05:01 AI OCR [  0.1s]: Mistral model detected — adding extract_header=true, extract_footer=true
2026-03-30T12:05:01 AI OCR [  0.1s]: Sending OCR request to http://litellm:4000/v1/ocr (timeout=300s)...
2026-03-30T12:05:14 AI OCR [ 13.4s]: OCR request completed in 13.3s — HTTP 200
2026-03-30T12:05:14 AI OCR [ 13.4s]: Extracted 4 page(s), 3821 chars of text
2026-03-30T12:05:14 AI OCR [ 13.4s]: Sending PATCH to http://webserver:8000/api/documents/447/ ...
2026-03-30T12:05:14 AI OCR [ 13.5s]: PATCH completed in 0.1s — HTTP 200
2026-03-30T12:05:14 AI OCR [ 13.5s]: Document 447 updated successfully — 4 page(s), 3821 chars, model: mistral-ocr-latest, total time: 13.5s
```

> **Tip:** To watch the log in real time from outside the container:
> ```bash
> docker exec paperless-celery tail -f /logs/ai_ocr.log
> ```

---

## Log Output

All script messages appear in the paperless consumer log under a single `stdout:`
section at INFO level. Errors are distinguished by content, not log level.

When everything works:
```
AI OCR [  0.0s]: Starting — doc=42, model=mistral-ocr-latest, archive=...
AI OCR [  0.1s]: Read archive file: 1,204,832 bytes
AI OCR [ 13.4s]: OCR completed in 13.3s — 4 page(s), 2847 chars
AI OCR [ 13.4s]: Quality check passed — content is clean
AI OCR [ 13.5s]: PATCH completed in 0.1s — HTTP 200
AI OCR [ 13.5s]: Document 42 updated successfully — 4 page(s), 2847 chars
```

When retries are triggered (empty content or transient HTTP errors):
```
AI OCR [  1.1s]: OCR completed in 1.1s — 1 page(s), 0 chars
AI OCR [  1.1s]: Empty content returned — response summary:
AI OCR [  1.1s]: top-level keys: [], pages: 1
AI OCR [  1.1s]:   page[0]: keys=['index', 'markdown']
AI OCR [  1.1s]:     index: 0
AI OCR [  1.1s]:     markdown: ''
AI OCR [  1.1s]: Attempt 1/4 — empty content. Retrying in 5s...
AI OCR [  6.2s]: Attempt 2/4 — retrying OCR request...
AI OCR [  7.5s]: OCR completed in 1.2s — 4 page(s), 3945 chars
```

Soft skips (exit 0, paperless continues silently):
```
AI OCR [  0.0s]: Skipping AI OCR for email document (MIME type: message/rfc822)
AI OCR [  0.0s]: No archive file at '' — skipping AI OCR
```

### Finding Errors in the Paperless Log

All AI OCR messages appear under the `stdout:` section of the paperless consumer
log. To find problems:

```bash
# All AI OCR activity
grep "AI OCR" /path/to/paperless.log

# Only failures and retries
grep "AI OCR.*\(empty content\|failed\|Retrying\|attempts returned\)" /path/to/paperless.log

# Response dumps (what the OCR API actually returned)
grep "AI OCR.*\(response summary\|page\[\|top-level keys\)" /path/to/paperless.log

# If AI_OCR_LOG_FILE is set (e.g. /logs/ai_ocr.log)
grep "ERROR" /logs/ai_ocr.log

# Watch in real time
docker exec paperless-celery tail -f /logs/ai_ocr.log | grep -E "ERROR|failed|empty|Retrying"
```

The response summary after `Empty content returned — response summary:` shows
exactly what the OCR API sent back — page keys, field values, and whether
`markdown` was empty, null, or missing.
