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

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <document_id>", file=sys.stderr)
        sys.exit(1)

    doc_id = sys.argv[1]

    paperless_url = os.environ.get("PAPERLESS_URL", "http://localhost:8000").rstrip("/")
    paperless_tok = os.environ.get("PAPERLESS_API_TOKEN", "")

    if not paperless_tok:
        print("Error: PAPERLESS_API_TOKEN is not set in the container environment.", file=sys.stderr)
        sys.exit(1)

    headers = {"Authorization": f"Token {paperless_tok}"}

    # ── Check the document exists and has an archive ───────────────────────────
    print(f"Fetching document {doc_id} from {paperless_url} …")
    req = urllib.request.Request(
        f"{paperless_url}/api/documents/{doc_id}/",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            doc = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"Error: API returned HTTP {exc.code} for document {doc_id}.", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Error: could not reach {paperless_url} — {exc.reason}", file=sys.stderr)
        sys.exit(1)

    if not doc.get("archived_file_name"):
        print(
            f"Error: document {doc_id} has no archived file "
            f"(document may not be a PDF or has not been archived yet).",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Download the archived PDF via the API ──────────────────────────────────
    # Using ?original=false returns the Tesseract-processed archive PDF.
    download_url = f"{paperless_url}/api/documents/{doc_id}/download/?original=false"
    print(f"Downloading archived PDF from {download_url} …")
    dl_req = urllib.request.Request(download_url, headers=headers)
    try:
        with urllib.request.urlopen(dl_req, timeout=120) as resp:
            pdf_bytes = resp.read()
    except urllib.error.HTTPError as exc:
        print(f"Error: download returned HTTP {exc.code}.", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Error: download failed — {exc.reason}", file=sys.stderr)
        sys.exit(1)

    print(f"Downloaded {len(pdf_bytes):,} bytes.")

    # ── Write to a temp file and run the OCR script ────────────────────────────
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        print(f"Running AI OCR on document {doc_id} (tmp: {tmp_path}) …")
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
