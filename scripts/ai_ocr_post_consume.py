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
  AI_OCR_MAX_RETRIES       - (optional) Max retries on transient failures (default: 3)
  AI_OCR_RETRY_DELAY       - (optional) Base retry delay in seconds; doubles each attempt
                             (default: 5 → 5s, 10s, 20s)
  AI_OCR_RASTERIZE       - Rasterization mode (default: "auto"):
                             "auto"   — try PDF first, rasterize if quality check fails
                             "always" — always rasterize before OCR (skip PDF attempt)
                             "never"  — never rasterize (old behavior)
  AI_OCR_DEGRADATION_THRESHOLD - Garbage-line percentage above which a rasterized retry is
                             triggered in "auto" mode (default: 30)
  PAPERLESS_URL            - Internal paperless URL, e.g. "http://webserver:8000"
  PAPERLESS_API_TOKEN      - Paperless superuser API token

Injected by paperless-ngx automatically:

  DOCUMENT_ID              - Database ID of the consumed document
  DOCUMENT_ARCHIVE_PATH    - Filesystem path to the archived (OCRed) PDF
  DOCUMENT_MIME_TYPE       - MIME type of the document (e.g. "application/pdf")

Usage with paperless-ngx:
  PAPERLESS_POST_CONSUME_SCRIPT=/usr/src/paperless/scripts/ai_ocr_post_consume.py
"""

import base64
import copy
import datetime
import json
import os
import shutil
import sys
import time
import traceback
import urllib.error
import urllib.request

# Add the scripts directory to the path so we can import the quality helper.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_ocr_quality import check_quality, is_table_only, rasterize_pdf


_SCRIPT_START = time.monotonic()

# ── Optional file logging ──────────────────────────────────────────────────────
_log_file_path = os.getenv("AI_OCR_LOG_FILE", "").strip()
_log_fh = None
if _log_file_path:
    try:
        os.makedirs(os.path.dirname(_log_file_path) or ".", exist_ok=True)
        _log_fh = open(_log_file_path, "a", encoding="utf-8", buffering=1)
    except OSError as _e:
        print(f"AI OCR: WARNING — cannot open log file '{_log_file_path}': {_e}", flush=True)


def _log(msg: str, error: bool = False):
    """Timestamped log helper. All output goes to stdout so it lands in a single
    'stdout:' section of the paperless consumer log. The error flag only affects
    the AI_OCR_LOG_FILE where error lines are prefixed with 'ERROR'."""
    elapsed = time.monotonic() - _SCRIPT_START
    line = f"AI OCR [{elapsed:6.1f}s]: {msg}"
    print(line, flush=True)
    if _log_fh is not None:
        ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        _log_fh.write(f"{ts} {'ERROR ' if error else ''}{line}\n")


def _ocr_request(ai_ocr_url, ai_ocr_key, ai_ocr_model, data_url, timeout=300):
    """Send an OCR request to LiteLLM and return the parsed JSON response."""
    ocr_payload = {
        "model": ai_ocr_model,
        "document": {"type": "document_url", "document_url": data_url},
    }
    if "mistral" in ai_ocr_model.lower():
        ocr_payload["extract_header"] = True
        ocr_payload["extract_footer"] = True

    req = urllib.request.Request(
        f"{ai_ocr_url}/v1/ocr",
        data=json.dumps(ocr_payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ai_ocr_key}",
        },
        method="POST",
    )
    _log(f"Sending OCR request to {ai_ocr_url}/v1/ocr (timeout={timeout}s)...")
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
    _log(f"OCR request completed in {time.monotonic() - t0:.1f}s — HTTP {resp.status}")
    return result


def _extract_text(ocr_result):
    """Extract text from OCR response, merging header/markdown/footer per page."""
    pages = ocr_result.get("pages", [])

    def _page_text(p):
        parts = []
        for field in ("header", "markdown", "footer"):
            val = (p.get(field) or "").strip()
            if val:
                parts.append(val)
        return "\n\n".join(parts)

    content = "\n\n".join(_page_text(p) for p in pages).strip()
    return content, len(pages)


def _response_summary(raw: dict) -> list[str]:
    """Debug-safe summary of an OCR response — excludes base64 image data."""
    pages = raw.get("pages", [])
    lines = [f"top-level keys: {sorted(k for k in raw if k != 'pages')}, pages: {len(pages)}"]
    for i, p in enumerate(pages[:5]):
        keys = sorted(p.keys())
        lines.append(f"  page[{i}]: keys={keys}")
        for k in keys:
            if k == "images":
                lines.append(f"    images: {len(p[k])} item(s)")
                continue
            v = p[k]
            vs = str(v) if v is not None else "null"
            trunc = f"{vs[:150]}...({len(vs)} chars)" if len(vs) > 150 else vs
            lines.append(f"    {k}: {trunc!r}")
    return lines


def _retry_delay(attempt: int, base: int, exc: object = None) -> int:
    """Calculate delay for retry attempt (1-indexed). Respects Retry-After on 429."""
    delay = base * (2 ** (attempt - 1))
    if exc is not None and getattr(exc, "code", 0) == 429:
        ra = getattr(getattr(exc, "headers", {}), "get", lambda *_: "")("Retry-After", "")
        if str(ra).isdigit():
            delay = max(int(ra), delay)
    return delay


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
    max_retries   = int(os.getenv("AI_OCR_MAX_RETRIES", "3"))
    retry_base    = int(os.getenv("AI_OCR_RETRY_DELAY", "5"))
    rasterize_mode = os.getenv("AI_OCR_RASTERIZE", "auto").lower().strip()
    degrade_pct    = float(os.getenv("AI_OCR_DEGRADATION_THRESHOLD", "30"))
    tag_id_str    = os.getenv("AI_OCR_TAG_ID", "").strip()
    ai_ocr_tag_id = int(tag_id_str) if tag_id_str.isdigit() else None

    total_attempts = 1 + max_retries
    _log(f"Starting — doc={document_id}, model={ai_ocr_model}, archive={archive_path}")

    missing = [k for k, v in {
        "AI_OCR_URL": ai_ocr_url, "AI_OCR_KEY": ai_ocr_key,
        "PAPERLESS_API_TOKEN": paperless_tok, "DOCUMENT_ID": document_id,
    }.items() if not v]
    if missing:
        _log(f"Missing required configuration: {', '.join(missing)}", error=True)
        sys.exit(1)

    # ── 3. Skip non-OCR document types ────────────────────────────────────────
    doc_mime = os.getenv("DOCUMENT_MIME_TYPE", "").lower().strip()
    if doc_mime.startswith("message/"):
        _log(f"Skipping AI OCR for email document (MIME type: {doc_mime})")
        sys.exit(0)

    # ── 4. Read document file ──────────────────────────────────────────────────
    if not archive_path or not os.path.exists(archive_path):
        _log(f"No archive file at '{archive_path}' — skipping AI OCR")
        sys.exit(0)

    with open(archive_path, "rb") as fh:
        file_bytes = fh.read()
    _log(f"Read archive file: {len(file_bytes):,} bytes")

    ext = os.path.splitext(archive_path)[1].lower()
    mime = "application/pdf" if ext == ".pdf" else "image/jpeg"

    # ── 5. Rasterize upfront if "always" mode ────────────────────────────────
    rasterized_tmpdir = None
    if rasterize_mode == "always" and mime == "application/pdf":
        _log("Rasterize mode=always — converting PDF to pixel-based format before OCR...")
        rasterized_path = rasterize_pdf(archive_path)
        if rasterized_path:
            rasterized_tmpdir = os.path.dirname(rasterized_path)
            with open(rasterized_path, "rb") as fh:
                file_bytes = fh.read()
            _log(f"Rasterized PDF: {len(file_bytes):,} bytes")
        else:
            _log("Rasterization failed — falling back to original PDF", error=True)

    # ── 6. OCR with retry ─────────────────────────────────────────────────────
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    content = ""
    page_count = 0
    ocr_result: dict = {}

    for attempt in range(1, total_attempts + 1):
        if attempt > 1:
            _log(f"Attempt {attempt}/{total_attempts} — retrying OCR request...")

        try:
            ocr_result = _ocr_request(ai_ocr_url, ai_ocr_key, ai_ocr_model, data_url)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            _log(f"OCR request failed — HTTP {exc.code}: {body[:500]}", error=True)
            if exc.code in (429, 500, 502, 503, 504) and attempt < total_attempts:
                delay = _retry_delay(attempt, retry_base, exc)
                _log(f"Attempt {attempt}/{total_attempts} — HTTP {exc.code}. Retrying in {delay}s...")
                time.sleep(delay)
                continue
            sys.exit(1)
        except (urllib.error.URLError, Exception) as exc:
            _log(f"OCR request failed — {exc}", error=True)
            if attempt < total_attempts:
                delay = _retry_delay(attempt, retry_base)
                _log(f"Attempt {attempt}/{total_attempts} — {type(exc).__name__}. Retrying in {delay}s...")
                time.sleep(delay)
                continue
            sys.exit(1)

        content, page_count = _extract_text(ocr_result)
        _log(f"Extracted {page_count} page(s), {len(content)} chars of text")

        if content:
            break

        # Empty content — dump response structure for debugging
        _log("Empty content returned — response summary:", error=True)
        for line in _response_summary(ocr_result):
            _log(line, error=True)

        if attempt < total_attempts:
            delay = _retry_delay(attempt, retry_base)
            _log(f"Attempt {attempt}/{total_attempts} — empty content. Retrying in {delay}s...")
            time.sleep(delay)

    if not content:
        _log(
            f"All {total_attempts} attempts returned empty content — "
            f"leaving Tesseract output intact",
            error=True,
        )
        sys.exit(0)

    # ── 6. Table-only detection + rasterization ───────────────────────────────
    # If Mistral classified the entire page as table blocks (no text blocks),
    # it likely made a wrong segmentation decision — e.g., a horizontal line
    # caused it to ignore the header content above the table.
    if rasterize_mode != "never" and mime == "application/pdf" and is_table_only(ocr_result):
        _log("Table-only blocks detected — Mistral may have missed header content")
        _log("Rasterizing PDF to force full-page text extraction...")
        rasterized_path = rasterize_pdf(archive_path)
        if rasterized_path:
            try:
                with open(rasterized_path, "rb") as fh:
                    raster_bytes = fh.read()
                _log(f"Rasterized PDF: {len(raster_bytes):,} bytes")
                raster_b64 = base64.b64encode(raster_bytes).decode("utf-8")
                raster_url = f"data:application/pdf;base64,{raster_b64}"

                ocr_result_2 = _ocr_request(
                    ai_ocr_url, ai_ocr_key, ai_ocr_model, raster_url
                )
                content_2, page_count_2 = _extract_text(ocr_result_2)

                if content_2 and len(content_2) > len(content):
                    _log(
                        f"Rasterized result has more content "
                        f"({len(content_2)} vs {len(content)} chars) — using it"
                    )
                    content = content_2
                    page_count = page_count_2
                    ocr_result = ocr_result_2
                else:
                    _log("Rasterized result not better — keeping original")
            except (urllib.error.HTTPError, urllib.error.URLError, Exception) as exc:
                _log(f"Table-only rasterize retry failed: {exc}", error=True)
            finally:
                if rasterized_path:
                    shutil.rmtree(os.path.dirname(rasterized_path), ignore_errors=True)
        else:
            _log("Rasterization failed — keeping original content", error=True)

    # ── 7. Garbage quality check + rasterization fallback ─────────────────────
    raw_content = content  # preserve for debug/comparison
    is_usable, garbage_pct = check_quality(content, degrade_pct)

    # Log quality check details — always, not just in debug mode
    if garbage_pct > 0:
        _log(
            f"Quality check detail — {len(raw_content)} chars, "
            f"{garbage_pct:.0f}% garbage (usable={is_usable})"
        )

    if debug_mode:
        separator = "─" * 72

        _log("DEBUG MODE — raw Mistral response (images stripped):")
        print(separator, flush=True)
        # Deep-copy response and strip base64 image data for readability
        debug_resp = copy.deepcopy(ocr_result)
        for p in debug_resp.get("pages", []):
            if "images" in p:
                p["images"] = [f"[{len(img)} chars base64]" if isinstance(img, str) else img for img in p["images"]]
            # Also strip any inline base64 in other fields
            for k, v in list(p.items()):
                if isinstance(v, str) and len(v) > 1000 and "base64" in v[:100]:
                    p[k] = f"[{len(v)} chars base64]"
        print(json.dumps(debug_resp, indent=2, ensure_ascii=False), flush=True)
        print(separator, flush=True)

        _log(f"DEBUG MODE — extracted text ({page_count} page(s), {len(raw_content)} chars):")
        print(separator, flush=True)
        print(raw_content, flush=True)
        print(separator, flush=True)

    if not is_usable and garbage_pct > 0:
        _log(
            f"Quality check FAILED — {garbage_pct:.0f}% garbage lines detected "
            f"(threshold: {degrade_pct:.0f}%)", error=True
        )

        if rasterize_mode != "never" and mime == "application/pdf":
            _log("Rasterization fallback — converting PDF to pixel-based format...")
            rasterized_path = None
            try:
                rasterized_path = rasterize_pdf(archive_path)
                if rasterized_path:
                    with open(rasterized_path, "rb") as fh:
                        raster_bytes = fh.read()
                    _log(f"Rasterized PDF: {len(raster_bytes):,} bytes")
                    raster_b64 = base64.b64encode(raster_bytes).decode("utf-8")
                    raster_url = f"data:application/pdf;base64,{raster_b64}"

                    ocr_result_2 = _ocr_request(
                        ai_ocr_url, ai_ocr_key, ai_ocr_model, raster_url
                    )
                    content_2, page_count_2 = _extract_text(ocr_result_2)
                    _log(f"Rasterized retry: {page_count_2} page(s), {len(content_2)} chars")

                    _, garbage_pct_2 = check_quality(content_2, degrade_pct)

                    if content_2 and (garbage_pct_2 == 0 or garbage_pct_2 < garbage_pct):
                        _log(
                            f"Rasterized result is better "
                            f"(garbage: {garbage_pct_2:.0f}% vs {garbage_pct:.0f}%) — using it"
                        )
                        content = content_2
                        page_count = page_count_2
                    else:
                        _log("Rasterized result not better — using original")
                else:
                    _log("Rasterization failed — using original content", error=True)
            except (urllib.error.HTTPError, urllib.error.URLError, Exception) as exc:
                _log(f"Rasterized retry failed: {exc} — using original", error=True)
            finally:
                if rasterized_path:
                    shutil.rmtree(os.path.dirname(rasterized_path), ignore_errors=True)
        else:
            if mime != "application/pdf":
                _log("Non-PDF document — cannot rasterize")
            else:
                _log("Rasterization disabled (mode=never)")

    elif garbage_pct > 0:
        _log(f"Minor garbage detected ({garbage_pct:.0f}%) — using content as-is")
    else:
        _log("Quality check passed — content is clean")

    if not content:
        _log("Content is empty after quality processing — leaving Tesseract output intact", error=True)
        sys.exit(0)

    # ── 7. Debug mode ──────────────────────────────────────────────────────────
    if debug_mode:
        _log("DEBUG MODE — OCR output follows (document NOT updated):")
        separator = "─" * 72
        print(separator, flush=True)
        print(content, flush=True)
        print(separator, flush=True)
        _log(f"DEBUG MODE done — {page_count} page(s), {len(content)} chars")
        sys.exit(0)

    # ── 8. Build PATCH payload ─────────────────────────────────────────────────
    patch_payload: dict = {"content": content}

    if ai_ocr_tag_id is not None:
        _log(f"Fetching current tags for document {document_id} (tag_id={ai_ocr_tag_id})...")
        t_get = time.monotonic()
        get_req = urllib.request.Request(
            f"{paperless_url}/api/documents/{document_id}/",
            headers={"Authorization": f"Token {paperless_tok}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(get_req, timeout=30) as resp:
                doc_data = json.loads(resp.read())
            _log(f"GET completed in {time.monotonic() - t_get:.1f}s — HTTP {resp.status}")
            current_tags: list = doc_data.get("tags", [])
            if ai_ocr_tag_id not in current_tags:
                current_tags.append(ai_ocr_tag_id)
            patch_payload["tags"] = current_tags
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            _log(
                f"Could not fetch document tags — {exc}. "
                f"Tag {ai_ocr_tag_id} not added, content update proceeds.",
                error=True,
            )

    # ── 9. PATCH document content ──────────────────────────────────────────────
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
            resp.read()
        _log(f"PATCH completed in {time.monotonic() - t_patch:.1f}s — HTTP {resp.status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        _log(f"PATCH failed — HTTP {exc.code}: {body[:500]}", error=True)
        sys.exit(1)
    except (urllib.error.URLError, Exception) as exc:
        _log(f"PATCH failed — {exc}", error=True)
        sys.exit(1)

    # ── 10. Cleanup + done ─────────────────────────────────────────────────────
    if rasterized_tmpdir:
        shutil.rmtree(rasterized_tmpdir, ignore_errors=True)

    total = time.monotonic() - _SCRIPT_START
    tag_info = f", tag: {ai_ocr_tag_id}" if ai_ocr_tag_id is not None else ""
    _log(
        f"Document {document_id} updated successfully — "
        f"{page_count} page(s), {len(content)} chars, model: {ai_ocr_model}{tag_info}, "
        f"total time: {total:.1f}s"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        _log(f"Unhandled exception:\n{traceback.format_exc()}", error=True)
        sys.exit(1)
