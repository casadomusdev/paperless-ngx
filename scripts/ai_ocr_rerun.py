#!/usr/bin/env python3
"""
Re-run the AI OCR post-consumption script on an existing document.

Runs inside the celery container where all required env vars are already set.
Downloads the archived PDF via the Paperless API into a temp file, then
executes ai_ocr_post_consume.py with DOCUMENT_ID and DOCUMENT_ARCHIVE_PATH
pointing at that temp file — no filesystem path assumptions needed.

Usage (inside the container):
  python3 /usr/src/paperless/scripts/ai_ocr_rerun.py <document_id>
"""

import datetime
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

# ── Optional file logging (mirrors ai_ocr_post_consume.py) ────────────────────
_log_file_path = os.getenv("AI_OCR_LOG_FILE", "").strip()
_log_fh = None
if _log_file_path:
    try:
        os.makedirs(os.path.dirname(_log_file_path) or ".", exist_ok=True)
        _log_fh = open(_log_file_path, "a", encoding="utf-8", buffering=1)
    except OSError as _e:
        print(f"ai_ocr_rerun: WARNING — cannot open log file '{_log_file_path}': {_e}", flush=True)


def _print(msg: str, error: bool = False):
    """Print helper that also appends to AI_OCR_LOG_FILE when set.
    All output goes to stdout for unified logging in paperless consumer log."""
    print(msg, flush=True)
    if _log_fh is not None:
        ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        _log_fh.write(f"{ts} {'ERROR ' if error else ''}{msg}\n")


def main():
    if len(sys.argv) != 2:
        _print(f"Usage: {sys.argv[0]} <document_id>", error=True)
        sys.exit(1)

    doc_id = sys.argv[1]

    paperless_url = os.environ.get("PAPERLESS_URL", "http://localhost:8000").rstrip("/")
    paperless_tok = os.environ.get("PAPERLESS_API_TOKEN", "")

    if not paperless_tok:
        _print("Error: PAPERLESS_API_TOKEN is not set in the container environment.", error=True)
        sys.exit(1)

    headers = {"Authorization": f"Token {paperless_tok}"}

    # ── Check the document exists and has an archive ───────────────────────────
    _print(f"Fetching document {doc_id} from {paperless_url} …")
    req = urllib.request.Request(
        f"{paperless_url}/api/documents/{doc_id}/",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            doc = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        _print(f"Error: API returned HTTP {exc.code} for document {doc_id}.", error=True)
        sys.exit(1)
    except urllib.error.URLError as exc:
        _print(f"Error: could not reach {paperless_url} — {exc.reason}", error=True)
        sys.exit(1)

    if not doc.get("archived_file_name"):
        _print(
            f"Error: document {doc_id} has no archived file "
            f"(document may not be a PDF or has not been archived yet).",
            error=True,
        )
        sys.exit(1)

    # ── Download the archived PDF via the API ──────────────────────────────────
    # Try archive first (?original=false), fall back to original (?original=true)
    # if no archive exists (e.g., OCR never ran or archive was lost).
    download_url = f"{paperless_url}/api/documents/{doc_id}/download/?original=false"
    _print(f"Downloading archived PDF from {download_url} …")
    dl_req = urllib.request.Request(download_url, headers=headers)
    try:
        with urllib.request.urlopen(dl_req, timeout=120) as resp:
            pdf_bytes = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            _print("Archive not found (404) — falling back to original file…")
            download_url = f"{paperless_url}/api/documents/{doc_id}/download/?original=true"
            _print(f"Downloading original from {download_url} …")
            dl_req = urllib.request.Request(download_url, headers=headers)
            try:
                with urllib.request.urlopen(dl_req, timeout=120) as resp:
                    pdf_bytes = resp.read()
            except urllib.error.HTTPError as exc2:
                _print(f"Error: original download returned HTTP {exc2.code}.", error=True)
                sys.exit(1)
            except urllib.error.URLError as exc2:
                _print(f"Error: original download failed — {exc2.reason}", error=True)
                sys.exit(1)
        else:
            _print(f"Error: download returned HTTP {exc.code}.", error=True)
            sys.exit(1)
    except urllib.error.URLError as exc:
        _print(f"Error: download failed — {exc.reason}", error=True)
        sys.exit(1)

    _print(f"Downloaded {len(pdf_bytes):,} bytes.")

    # ── Write to a temp file and run the OCR script ────────────────────────────
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        _print(f"Running AI OCR on document {doc_id} (tmp: {tmp_path}) …")
        script = os.path.join(os.path.dirname(__file__), "ai_ocr_post_consume.py")
        env = os.environ.copy()
        env["DOCUMENT_ID"] = doc_id
        env["DOCUMENT_ARCHIVE_PATH"] = tmp_path

        result = subprocess.run([sys.executable, script], env=env)
    finally:
        os.unlink(tmp_path)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
