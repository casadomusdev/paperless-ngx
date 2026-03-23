#!/usr/bin/env python3
"""
Re-run the AI OCR post-consumption script on an existing document.

Runs inside the celery container where all required env vars are already set.
Resolves the document's archive path via the Paperless API, then executes
ai_ocr_post_consume.py with DOCUMENT_ID and DOCUMENT_ARCHIVE_PATH injected.

Invoked by ai_ocr_rerun.sh via `docker compose exec celery`.
Can also be run directly inside the container:
  python3 /usr/src/paperless/scripts/ai_ocr_rerun.py <document_id>
"""

import json
import os
import subprocess
import sys
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

    # ── Resolve archive path via the Paperless API ─────────────────────────────
    print(f"Fetching document {doc_id} from {paperless_url} …")
    req = urllib.request.Request(
        f"{paperless_url}/api/documents/{doc_id}/",
        headers={"Authorization": f"Token {paperless_tok}"},
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

    archive_name = doc.get("archived_file_name")
    if not archive_name:
        print(
            f"Error: document {doc_id} has no archived file "
            f"(document may not be a PDF or has not been archived yet).",
            file=sys.stderr,
        )
        sys.exit(1)

    archive_path = f"/usr/src/paperless/media/documents/archive/{archive_name}"
    print(f"Archive path: {archive_path}")

    # ── Run the OCR script with the resolved env vars ──────────────────────────
    print(f"Running AI OCR on document {doc_id} …")
    script = os.path.join(os.path.dirname(__file__), "ai_ocr_post_consume.py")
    env = os.environ.copy()
    env["DOCUMENT_ID"] = doc_id
    env["DOCUMENT_ARCHIVE_PATH"] = archive_path

    result = subprocess.run([sys.executable, script], env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
