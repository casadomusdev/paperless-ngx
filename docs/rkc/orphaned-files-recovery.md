# Orphaned Files Recovery

When paperless-ngx shows "File not found" errors for documents that exist in the
database, the files have been moved or deleted from their expected locations.

## Symptoms

- Document detail page shows "File not found" or loads indefinitely
- Preview/thumbnail fails to render
- API returns 404 for `/api/documents/{id}/preview/` or `/download/`

## Root Cause

The invoice processor moves documents between storage paths via PATCH API calls.
If the container restarts mid-process (between the storage_path change and the
file move completing), the database and filesystem get out of sync:

- Database says file is at `_Sources/Mail/VFG/2026/08/doc.pdf`
- File was actually moved to `Archiv/Dokumente/VFG/2026/08/doc.pdf`
- Or: file was deleted from old location but never arrived at new location

## Diagnosis

Run this inside the paperless container to find all orphaned documents:

```bash
docker exec -i casabot-filderbau-paperless python3 manage.py shell -c "
from pathlib import Path
from documents.models import Document

media_root = Path('/usr/src/paperless/media/documents')

print('=== Diagnosing Missing Files ===')
print()

for d in Document.objects.select_related('storage_path').all():
    src = d.source_path
    arc = d.archive_path
    src_exists = src.exists() if src else False
    arc_exists = arc.exists() if arc else False
    if src_exists and arc_exists:
        continue
    print(f'Doc {d.id}: {d.title}')
    print(f'  Storage: {d.storage_path.path if d.storage_path else None}')
    print(f'  Source:  {src}')
    print(f'    Exists: {src_exists}')
    print(f'  Archive: {arc}')
    print(f'    Exists: {arc_exists}')
    filename = d.filename.split('/')[-1] if d.filename else None
    if filename:
        matches = list(media_root.rglob(filename))
        if matches:
            print(f'  FOUND at: {matches[0]}')
        else:
            print(f'  NOT FOUND anywhere in media volume')
    print()
"
```

## Recovery Steps

### Step 1: Move source files to correct locations

```bash
docker exec -i casabot-filderbau-paperless python3 manage.py shell -c "
import shutil
from pathlib import Path
from documents.models import Document

media_root = Path('/usr/src/paperless/media/documents')
originals_root = media_root / 'originals'

print('=== Moving Source Files ===')

for d in Document.objects.select_related('storage_path').all():
    fn = d.filename or ''
    src_path = originals_root / fn if fn else None
    if not fn or fn.endswith('.eml') or (src_path and src_path.exists()):
        continue

    basename = fn.split('/')[-1]
    matches = list(originals_root.rglob(basename))
    if not matches:
        continue

    actual = matches[0]
    src_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(actual), str(src_path))
        print(f'Doc {d.id}: moved -> {fn}')
    except Exception as e:
        print(f'Doc {d.id}: ERROR — {e}')
"
```

### Step 2: Regenerate archives via bulk edit API

```bash
curl -X POST "https://inbox.filderbau.casabot.de/api/documents/bulk_edit/" \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"documents": [DOC_ID_1, DOC_ID_2, ...], "method": "reprocess"}'
```

This re-runs OCR, creates archive PDFs, and updates content. Handles signed
PDFs and email documents correctly.

### Step 3: Verify

```bash
# Check that all documents now have both files
docker exec -i casabot-filderbau-paperless python3 manage.py shell -c "
from documents.models import Document
for d in Document.objects.all():
    if not d.source_path.exists():
        print(f'Doc {d.id}: source missing')
    if d.archive_path and not d.archive_path.exists():
        print(f'Doc {d.id}: archive missing')
print('Done')
"
```

## Prevention

The invoice processor now uses atomic PATCH calls (single API call with
storage_path + document_type + tags) to prevent partial updates. The paperless
container should have `stop_grace_period: 60s` to allow in-progress operations
to complete before shutdown.

See also: [AI OCR](ai-ocr.md) for the AI OCR pipeline that also processes
these documents.
