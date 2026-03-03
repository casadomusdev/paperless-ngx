#!/usr/bin/env python3
"""
AI OCR Post-Consumption Script for paperless-ngx (RKC customization).

Calls a LiteLLM proxy /v1/ocr endpoint to produce higher-quality OCR text
and updates the document's `content` field via the paperless-ngx REST API.
Tesseract still runs as normal; this script overwrites its output afterward.

The search index updates automatically via the post_save signal in
documents/signals/handlers.py — no extra steps needed.

Configuration (set in your Docker Compose environment / .env):

  AI_OCR_ENABLED           - Set to "true" to enable (default: false / no-op when absent)
  AI_OCR_URL               - LiteLLM proxy base URL, e.g. "http://litellm:4000"
  AI_OCR_KEY               - LiteLLM virtual API key
  AI_OCR_MODEL             - Model name, e.g. "mistral-ocr-latest" or "azure-doc-intel"
  PAPERLESS_URL            - Internal paperless URL, e.g. "http://webserver:8000"
  PAPERLESS_API_TOKEN      - Paperless superuser API token

Injected by paperless-ngx automatically:

  DOCUMENT_ID              - Database ID of the consumed document
  DOCUMENT_ARCHIVE_PATH    - Filesystem path to the archived (OCRed) PDF

Usage with paperless-ngx:
  PAPERLESS_POST_CONSUME_SCRIPT=/usr/src/paperless/scripts/ai_ocr_post_consume.py
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request


def main():
    # ── 1. Feature gate ────────────────────────────────────────────────────────
    if os.getenv("AI_OCR_ENABLED", "false").lower() != "true":
        sys.exit(0)

    # ── 2. Configuration ───────────────────────────────────────────────────────
    ai_ocr_url    = os.getenv("AI_OCR_URL", "").rstrip("/")
    ai_ocr_key    = os.getenv("AI_OCR_KEY", "")
    ai_ocr_model  = os.getenv("AI_OCR_MODEL", "mistral-ocr-latest")
    paperless_url = os.getenv("PAPERLESS_URL", "http://localhost:8000").rstrip("/")
    paperless_tok = os.getenv("PAPERLESS_API_TOKEN", "")
    document_id   = os.getenv("DOCUMENT_ID", "")
    archive_path  = os.getenv("DOCUMENT_ARCHIVE_PATH", "")

    missing = [k for k, v in {
        "AI_OCR_URL": ai_ocr_url,
        "AI_OCR_KEY": ai_ocr_key,
        "PAPERLESS_API_TOKEN": paperless_tok,
        "DOCUMENT_ID": document_id,
    }.items() if not v]
    if missing:
        print(
            f"AI OCR: Missing required configuration: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── 3. Read document file ──────────────────────────────────────────────────
    if not archive_path or not os.path.exists(archive_path):
        print(
            f"AI OCR: Archive not found at '{archive_path}' "
            f"(DOCUMENT_ARCHIVE_PATH may be empty for non-PDF documents)",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(archive_path, "rb") as fh:
        file_bytes = fh.read()

    # ── 4. Determine MIME type from extension ──────────────────────────────────
    ext = os.path.splitext(archive_path)[1].lower()
    mime = "application/pdf" if ext == ".pdf" else "image/jpeg"

    # ── 5. Send to LiteLLM /v1/ocr ────────────────────────────────────────────
    b64      = base64.b64encode(file_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    ocr_payload = {
        "model": ai_ocr_model,
        "document": {
            "type": "document_url",
            "document_url": data_url,
        },
    }

    ocr_req = urllib.request.Request(
        f"{ai_ocr_url}/v1/ocr",
        data=json.dumps(ocr_payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ai_ocr_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(ocr_req, timeout=300) as resp:
            ocr_result = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(
            f"AI OCR: OCR request failed — HTTP {exc.code}: {body}",
            file=sys.stderr,
        )
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"AI OCR: OCR request failed — {exc.reason}", file=sys.stderr)
        sys.exit(1)

    # ── 6. Extract text from pages ─────────────────────────────────────────────
    pages   = ocr_result.get("pages", [])
    content = "\n\n".join(p.get("markdown", "") for p in pages).strip()

    if not content:
        print(
            "AI OCR: No text content returned — leaving Tesseract output intact",
            file=sys.stderr,
        )
        sys.exit(0)  # Not fatal; Tesseract result remains

    # ── 7. PATCH document content via paperless REST API ──────────────────────
    patch_req = urllib.request.Request(
        f"{paperless_url}/api/documents/{document_id}/",
        data=json.dumps({"content": content}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Token {paperless_tok}",
        },
        method="PATCH",
    )

    try:
        with urllib.request.urlopen(patch_req, timeout=60) as resp:
            resp.read()  # consume response body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(
            f"AI OCR: Failed to update document {document_id} — "
            f"HTTP {exc.code}: {body}",
            file=sys.stderr,
        )
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(
            f"AI OCR: Failed to reach paperless API — {exc.reason}",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── 8. Done ────────────────────────────────────────────────────────────────
    print(
        f"AI OCR: Document {document_id} updated — "
        f"{len(pages)} page(s), {len(content)} chars, model: {ai_ocr_model}"
    )


if __name__ == "__main__":
    main()
