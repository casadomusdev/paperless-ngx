# Testing

Testing guidance for the RKC customizations, focused on the AI OCR helper
scripts in `scripts/`.

## Offline unit tests (no server, no network)

The AI OCR helpers are covered by offline unit tests that mock `urllib` — no
paperless instance, LiteLLM proxy or container is needed.

```bash
# Straight from the repo root
python3 scripts/test_ai_ocr_helpers.py

# Or via unittest discovery
python3 -m unittest scripts.test_ai_ocr_helpers -v
```

Covered:

| Script                     | What is tested |
|----------------------------|----------------|
| `scripts/ai_ocr_http.py`   | `retry_delay()` backoff + `Retry-After` handling; `http_request()` success, retry on DNS/connection errors, retry on HTTP 429/5xx, immediate raise on other HTTP errors, exhaustion raises, log callback |
| `scripts/ai_ocr_quality.py`| `check_quality()` clean content, contiguous `K`-run, interleaved repetition loop, in-line repetition, empty content |

These tests need only the Python standard library. Run them before every
commit that touches `scripts/ai_ocr_*.py`.

## Syntax / import check

```bash
python3 -c "import ast; [ast.parse(open(f).read()) for f in \
  ['scripts/ai_ocr_http.py','scripts/ai_ocr_quality.py', \
   'scripts/ai_ocr_post_consume.py','scripts/ai_ocr_rerun.py', \
   'scripts/ai_ocr_test.py']]; print('syntax OK')"

cd scripts && python3 -c \
  "import ai_ocr_http, ai_ocr_quality, ai_ocr_post_consume, ai_ocr_rerun, ai_ocr_test; print('imports OK')"
```

## Manual / live test scenarios

These require the running Docker deployment (container name shown as
`casabot-filderbau-paperless`; adjust to your `COMPOSE_PROJECT`).

### 1. Re-run AI OCR on an existing document

```bash
docker exec -it casabot-filderbau-paperless \
  python3 /usr/src/paperless/scripts/ai_ocr_rerun.py <document_id>
```

Expect the log to end with `Document <id> updated successfully`.

### 2. Inspect OCR output without modifying the document

```bash
docker exec -e AI_OCR_DEBUG=true -it casabot-filderbau-paperless \
  python3 /usr/src/paperless/scripts/ai_ocr_rerun.py <document_id>
```

Expect `DEBUG MODE done — document NOT updated`.

### 3. Verify the transient-failure retry path

Temporarily point the script at an unreachable internal URL and confirm it
retries (with backoff) and, only after exhausting retries, exits non-zero:

```bash
docker exec -e AI_OCR_PAPERLESS_URL=http://no-such-host.invalid \
  -it casabot-filderbau-paperless \
  python3 /usr/src/paperless/scripts/ai_ocr_rerun.py <document_id>
```

Expect repeated `GET attempt n/N — ... Retrying in Ns...` lines, then a loud
failure. A single momentary DNS blip should instead recover on its own.

### 4. Confirm the internal-URL path removes the external dependency

With `AI_OCR_PAPERLESS_URL=http://webserver:8000` set in the compose env, a
normal consume should show `GET ... HTTP 200` and `PATCH ... HTTP 200` with no
external hostname involved.
