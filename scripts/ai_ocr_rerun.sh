#!/usr/bin/env bash
# ai_ocr_rerun.sh — Re-run AI OCR on an existing document.
#
# Usage (from the docker-compose directory):
#   ./scripts/ai_ocr_rerun.sh <document_id>
#
# Everything runs inside the celery container where all env vars are already set.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <document_id>" >&2
  exit 1
fi

docker compose exec celery python3 /usr/src/paperless/scripts/ai_ocr_rerun.py "$1"
