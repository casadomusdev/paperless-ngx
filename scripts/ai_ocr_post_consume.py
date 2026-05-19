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
  AI_OCR_TAG_ID            - (optional) Tag ID to apply on successful OCR
  AI_OCR_DEBUG             - Set to "true" to print OCR output to stdout and skip the PATCH
  AI_OCR_LOG_FILE          - (optional) Path to a log file; all log lines are appended there
                             with a wallclock datetime prefix, e.g. "/logs/ai_ocr.log"
  PAPERLESS_URL            - Internal paperless URL, e.g. "http://webserver:8000"
  PAPERLESS_API_TOKEN      - Paperless superuser API token

Injected by paperless-ngx automatically:

  DOCUMENT_ID              - Database ID of the consumed document
  DOCUMENT_ARCHIVE_PATH    - Filesystem path to the archived (OCRed) PDF

Usage with paperless-ngx:
  PAPERLESS_POST_CONSUME_SCRIPT=/usr/src/paperless/scripts/ai_ocr_post_consume.py
"""

import base64
import datetime
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.request


_SCRIPT_START = time.monotonic()

# ── Optional file logging ──────────────────────────────────────────────────────
# When AI_OCR_LOG_FILE is set, every _log() call is also appended to that file
# with a wallclock datetime prefix. The file is opened once here so output is
# captured even if the script crashes before main() runs.
_log_file_path = os.getenv("AI_OCR_LOG_FILE", "").strip()
_log_fh = None
if _log_file_path:
    try:
        os.makedirs(os.path.dirname(_log_file_path) or ".", exist_ok=True)
        _log_fh = open(_log_file_path, "a", encoding="utf-8", buffering=1)  # line-buffered
    except OSError as _e:
        print(f"AI OCR: WARNING — cannot open log file '{_log_file_path}': {_e}", file=sys.stderr, flush=True)


def _log(msg: str, error: bool = False):
    """Timestamped log helper. Flushes immediately so logs appear real-time in Celery output.
    When AI_OCR_LOG_FILE is set, also appends to that file with a wallclock prefix."""
    elapsed = time.monotonic() - _SCRIPT_START
    line = f"AI OCR [{elapsed:6.1f}s]: {msg}"
    if error:
        print(line, file=sys.stderr, flush=True)
    else:
        print(line, flush=True)
    if _log_fh is not None:
        ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        _log_fh.write(f"{ts} {line}\n")


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
    debug_mode    = os.getenv("AI_OCR_DEBUG", "false").lower() == "true"

    tag_id_str    = os.getenv("AI_OCR_TAG_ID", "").strip()
    ai_ocr_tag_id = int(tag_id_str) if tag_id_str.isdigit() else None

    _log(f"Starting — doc={document_id}, model={ai_ocr_model}, archive={archive_path}")

    missing = [k for k, v in {
        "AI_OCR_URL": ai_ocr_url,
        "AI_OCR_KEY": ai_ocr_key,
        "PAPERLESS_API_TOKEN": paperless_tok,
        "DOCUMENT_ID": document_id,
    }.items() if not v]
    if missing:
        _log(f"Missing required configuration: {', '.join(missing)}", error=True)
        sys.exit(1)

    # ── 3. Read document file ──────────────────────────────────────────────────
    if not archive_path or not os.path.exists(archive_path):
        _log(
            f"No archive file at '{archive_path}' — skipping AI OCR "
            f"(non-PDF/image document, e.g. .eml upload)"
        )
        sys.exit(0)

    with open(archive_path, "rb") as fh:
        file_bytes = fh.read()

    _log(f"Read archive file: {len(file_bytes):,} bytes")

    # ── 4. Determine MIME type from extension ──────────────────────────────────
    ext = os.path.splitext(archive_path)[1].lower()
    mime = "application/pdf" if ext == ".pdf" else "image/jpeg"
    _log(f"Detected MIME type: {mime}")

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

    # ── 5a. Provider-specific extra params ─────────────────────────────────────
    if "mistral" in ai_ocr_model.lower():
        ocr_payload["extract_header"] = True
        ocr_payload["extract_footer"] = True
        _log("Mistral model detected — adding extract_header=true, extract_footer=true")

    ocr_req = urllib.request.Request(
        f"{ai_ocr_url}/v1/ocr",
        data=json.dumps(ocr_payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ai_ocr_key}",
        },
        method="POST",
    )

    _log(f"Sending OCR request to {ai_ocr_url}/v1/ocr (timeout=300s)...")
    t_ocr = time.monotonic()

    try:
        with urllib.request.urlopen(ocr_req, timeout=300) as resp:
            ocr_status = resp.status
            ocr_result = json.loads(resp.read())
        _log(f"OCR request completed in {time.monotonic() - t_ocr:.1f}s — HTTP {ocr_status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        _log(
            f"OCR request failed after {time.monotonic() - t_ocr:.1f}s — "
            f"HTTP {exc.code}: {body[:500]}",
            error=True,
        )
        _log(traceback.format_exc(), error=True)
        sys.exit(1)
    except urllib.error.URLError as exc:
        _log(
            f"OCR request failed after {time.monotonic() - t_ocr:.1f}s — "
            f"URLError: {exc.reason}",
            error=True,
        )
        _log(traceback.format_exc(), error=True)
        sys.exit(1)
    except Exception as exc:
        _log(
            f"OCR request failed after {time.monotonic() - t_ocr:.1f}s — "
            f"Unexpected: {exc}",
            error=True,
        )
        _log(traceback.format_exc(), error=True)
        sys.exit(1)

    # ── 6. Extract text from pages ─────────────────────────────────────────────
    # When extract_header/extract_footer are set (Mistral), those fields are
    # returned separately from `markdown` and must be merged explicitly.
    pages = ocr_result.get("pages", [])

    def _page_text(p: dict) -> str:
        parts = []
        for field in ("header", "markdown", "footer"):
            val = (p.get(field) or "").strip()
            if val:
                parts.append(val)
        return "\n\n".join(parts)

    content = "\n\n".join(_page_text(p) for p in pages).strip()

    _log(f"Extracted {len(pages)} page(s), {len(content)} chars of text")

    if not content:
        _log(
            "No text content returned — leaving Tesseract output intact",
            error=True,
        )
        sys.exit(0)  # Not fatal; Tesseract result remains

    # ── 6a. Debug mode — print OCR output and exit without patching ────────────
    if debug_mode:
        _log("DEBUG MODE — OCR output follows (document NOT updated):")
        separator = "─" * 72
        print(separator, flush=True)
        print(content, flush=True)
        print(separator, flush=True)
        _log(f"DEBUG MODE done — {len(pages)} page(s), {len(content)} chars")
        sys.exit(0)

    # ── 7. Build PATCH payload ─────────────────────────────────────────────────
    patch_payload: dict = {"content": content}

    if ai_ocr_tag_id is not None:
        # Fetch current document tags so we can merge without clobbering existing ones.
        # PATCH with a list field replaces the whole list, so we must include all tags.
        _log(f"Fetching current tags for document {document_id} (tag_id={ai_ocr_tag_id})...")
        t_get = time.monotonic()
        get_req = urllib.request.Request(
            f"{paperless_url}/api/documents/{document_id}/",
            headers={"Authorization": f"Token {paperless_tok}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(get_req, timeout=30) as resp:
                get_status = resp.status
                doc_data = json.loads(resp.read())
            _log(f"GET completed in {time.monotonic() - t_get:.1f}s — HTTP {get_status}")
            current_tags: list = doc_data.get("tags", [])
            if ai_ocr_tag_id not in current_tags:
                current_tags.append(ai_ocr_tag_id)
            patch_payload["tags"] = current_tags
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            _log(
                f"Could not fetch document tags after {time.monotonic() - t_get:.1f}s — "
                f"{exc}. Tag {ai_ocr_tag_id} not added, content update proceeds.",
                error=True,
            )
            _log(traceback.format_exc(), error=True)

    # ── 8. PATCH document content (and optionally tags) via paperless API ──────
    _log(
        f"Sending PATCH to {paperless_url}/api/documents/{document_id}/ "
        f"(content={len(content)} chars, fields={list(patch_payload.keys())}, timeout=60s)..."
    )
    t_patch = time.monotonic()

    patch_req = urllib.request.Request(
        f"{paperless_url}/api/documents/{document_id}/",
        data=json.dumps(patch_payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Token {paperless_tok}",
        },
        method="PATCH",
    )

    try:
        with urllib.request.urlopen(patch_req, timeout=60) as resp:
            patch_status = resp.status
            resp.read()  # consume response body
        _log(f"PATCH completed in {time.monotonic() - t_patch:.1f}s — HTTP {patch_status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        _log(
            f"PATCH failed after {time.monotonic() - t_patch:.1f}s — "
            f"HTTP {exc.code}: {body[:500]}",
            error=True,
        )
        _log(traceback.format_exc(), error=True)
        sys.exit(1)
    except urllib.error.URLError as exc:
        _log(
            f"PATCH failed after {time.monotonic() - t_patch:.1f}s — "
            f"URLError: {exc.reason}",
            error=True,
        )
        _log(traceback.format_exc(), error=True)
        sys.exit(1)
    except Exception as exc:
        _log(
            f"PATCH failed after {time.monotonic() - t_patch:.1f}s — "
            f"Unexpected: {exc}",
            error=True,
        )
        _log(traceback.format_exc(), error=True)
        sys.exit(1)

    # ── 9. Done ────────────────────────────────────────────────────────────────
    total = time.monotonic() - _SCRIPT_START
    tag_info = f", tag: {ai_ocr_tag_id}" if ai_ocr_tag_id is not None else ""
    _log(
        f"Document {document_id} updated successfully — "
        f"{len(pages)} page(s), {len(content)} chars, model: {ai_ocr_model}{tag_info}, "
        f"total time: {total:.1f}s"
    )


if __name__ == "__main__":
    main()
