# AI OCR via Post-Consumption Script

Replaces Tesseract OCR output with higher-quality text from an AI OCR provider
(Mistral OCR, Azure Document Intelligence, or any model exposed via LiteLLM's
`/v1/ocr` endpoint) without modifying the paperless-ngx source code.

## How It Works

1. **paperless-ngx consumes the document as normal** — Tesseract runs and
   produces its usual OCR output, which is stored in the `content` field.

2. **The post-consumption script fires** — paperless-ngx calls
   `PAPERLESS_POST_CONSUME_SCRIPT` once the document is fully indexed.

3. **The script calls the LiteLLM `/v1/ocr` endpoint** — the document's
   archived PDF is base64-encoded and sent as a `data:application/pdf;base64,…`
   data URL in the request body.

4. **LiteLLM routes the request to the configured provider** — Mistral OCR,
   Azure Document Intelligence, or another provider with OCR capability. Cost
   tracking works via the native `/v1/ocr` endpoint (unlike the pass-through at
   `/mistral/v1/ocr` which bypasses accounting).

5. **The script PATCHes the `content` field** — the AI's markdown text is
   written to the document via `PATCH /api/documents/{id}/`.

6. **The search index auto-updates** — the `post_save` signal in
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
| `PAPERLESS_URL`  | `http://localhost:8000` | Internal paperless URL |

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

- **Script location**: `scripts/ai_ocr_post_consume.py`
- **No source modifications**: purely a post-consumption hook, zero changes to
  paperless-ngx Python or TypeScript code
- **No third-party dependencies**: uses only Python stdlib (`base64`, `json`,
  `os`, `sys`, `urllib`)
- **Graceful failures**: if the archive path is missing (e.g., for a plain text
  file without an archive PDF), the script exits with code 1 and logs clearly.
  If the OCR returns empty content, the script exits with code 0 (no-op),
  preserving Tesseract output.
- **Large file handling**: the script base64-encodes the whole PDF in memory.
  For most scanned documents (< 50 MB) this is fine. Very large multi-hundred-
  page PDFs may hit LiteLLM or provider upload limits.

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

## Log Output

When everything works you will see in the consumer log:
```
AI OCR: Document 42 updated — 3 page(s), 2847 chars, model: mistral-ocr-latest
```

Errors print to stderr and cause an exit code of 1 (paperless logs but continues):
```
AI OCR: OCR request failed — HTTP 429: {"error": "rate limit exceeded"}
AI OCR: Archive not found at '' (DOCUMENT_ARCHIVE_PATH may be empty for non-PDF documents)
AI OCR: Missing required configuration: AI_OCR_URL, PAPERLESS_API_TOKEN
```
