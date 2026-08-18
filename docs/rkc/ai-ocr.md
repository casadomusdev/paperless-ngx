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
| `AI_OCR_RASTERIZE_FALLBACK` | `true`         | Enable automatic rasterization retry when the quality check detects degraded output (e.g., repeated garbage lines). Set to `"false"` to disable. |
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
etc.).  If 3+ consecutive garbage lines are found, the script calculates what
percentage of total lines are garbage.

| Garbage % | Outcome |
|-----------|---------|
| 0% | Content is clean — use as-is |
| Below threshold (default 30%) | Strip the garbage tail, use the clean portion |
| Above threshold | Trigger rasterization fallback (if enabled) |

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
| `AI_OCR_RASTERIZE_FALLBACK` | `true` | Set to `"false"` to disable rasterization retry entirely |
| `AI_OCR_DEGRADATION_THRESHOLD` | `30` | Percentage of garbage lines that triggers retry. Increase for stricter detection, decrease to retry more aggressively. |

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

When everything works you will see in the consumer log:
```
AI OCR: Document 42 updated — 3 page(s), 2847 chars, model: mistral-ocr-latest
```

Errors print to stderr and cause an exit code of 1 (paperless logs but continues):
```
AI OCR: OCR request failed — HTTP 429: {"error": "rate limit exceeded"}
AI OCR: Missing required configuration: AI_OCR_URL, PAPERLESS_API_TOKEN
```

Soft skips print to stdout and exit with code 0 (paperless continues silently):
```
AI OCR: Skipping AI OCR for email document (MIME type: message/rfc822)
AI OCR: No archive file at '' — skipping AI OCR (non-PDF/image document, e.g. .eml upload)
```
