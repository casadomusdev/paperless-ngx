#!/usr/bin/env bash
# ai_ocr_rerun.sh — Re-run the AI OCR post-consume script on an existing document.
#
# Usage:
#   ./ai_ocr_rerun.sh <document_id>
#
# Required env vars (same as the docker-compose setup):
#   PAPERLESS_API_TOKEN  — Paperless superuser API token
#   PAPERLESS_URL        — Internal paperless URL (default: http://localhost:8000)
#
# The script resolves the archive path via the Paperless API and then executes
# ai_ocr_post_consume.py inside the celery container with the correct env vars.

set -euo pipefail

# ── Args ───────────────────────────────────────────────────────────────────────
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <document_id>" >&2
  exit 1
fi

DOC_ID="$1"

# ── Config from env ────────────────────────────────────────────────────────────
PAPERLESS_URL="${PAPERLESS_URL:-http://localhost:8000}"

if [[ -z "${PAPERLESS_API_TOKEN:-}" ]]; then
  echo "Error: PAPERLESS_API_TOKEN is not set." >&2
  exit 1
fi

# ── Resolve archive path via API ───────────────────────────────────────────────
echo "Fetching document $DOC_ID from $PAPERLESS_URL …"

ARCHIVE_NAME=$(curl -sf \
  -H "Authorization: Token ${PAPERLESS_API_TOKEN}" \
  "${PAPERLESS_URL}/api/documents/${DOC_ID}/" \
  | jq -r '.archived_file_name')

if [[ -z "$ARCHIVE_NAME" || "$ARCHIVE_NAME" == "null" ]]; then
  echo "Error: could not resolve archive path for document $DOC_ID." >&2
  echo "       The document may not exist or may have no archived PDF." >&2
  exit 1
fi

ARCHIVE_PATH="/usr/src/paperless/media/documents/archive/${ARCHIVE_NAME}"
echo "Archive path: $ARCHIVE_PATH"

# ── Run the OCR script inside the celery container ─────────────────────────────
echo "Running AI OCR on document $DOC_ID …"

docker compose exec celery bash -c "
  DOCUMENT_ID=${DOC_ID} \
  DOCUMENT_ARCHIVE_PATH=${ARCHIVE_PATH} \
  python3 /usr/src/paperless/scripts/ai_ocr_post_consume.py
"
