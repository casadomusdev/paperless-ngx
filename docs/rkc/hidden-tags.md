# Hidden Tags

**Version:** v1.6.0
**Added:** v1.6.0

## Overview

Tags can be marked as "hidden" to suppress their badge rendering in document list views. The tag remains assigned to documents and fully functional — only the visual badge is suppressed in card and table views.

This is useful for organizational or automation tags (e.g., inbox tags, workflow markers) that clutter the document list without adding value for most users.

## Behavior

- **Hidden tags are still assigned to documents** — the tag relationship is preserved
- **Hidden tags are still visible in the document detail view** — full tag management is unaffected
- **Hidden tags are still available in filter dropdowns** — users can still filter by hidden tags
- **Hidden tag badges are suppressed** in:
  - Small card view (document list)
  - Large card view (document list)
  - Table view (dashboard saved-view widgets)
- **The tag management list** (Settings > Tags) shows a "Hidden" column indicating which tags are hidden

## Configuration

No environment variables. Per-tag setting via the tag edit dialog:

1. Go to **Settings > Tags**
2. Edit a tag (or create a new one)
3. Check **"Hide in list views"**
4. Save

## Implementation Details

### Backend

| File | Change |
|------|--------|
| `src/documents/models.py` | `Tag.is_hidden = BooleanField(default=False)` |
| `src/documents/serialisers.py` | `is_hidden` added to `TagSerializer` and `TagSerializerVersion1` field lists |
| `src/documents/migrations/1075_tag_is_hidden.py` | Adds the field to the database |

### Frontend

| File | Change |
|------|--------|
| `src-ui/src/app/data/tag.ts` | `is_hidden?: boolean` on `Tag` interface |
| `src-ui/src/app/components/common/tag/tag.component.ts` | `@Input() hideIfHidden: boolean` — when true and tag is hidden, renders nothing |
| `src-ui/src/app/components/common/tag/tag.component.html` | Guard: `@if (tag && !(hideIfHidden && tag.is_hidden))` |
| `src-ui/src/app/components/common/edit-dialog/tag-edit-dialog/` | Form control + checkbox "Hide in list views" |
| `src-ui/src/app/components/document-list/document-card-small/` | `[hideIfHidden]="true"` on `<pngx-tag>` |
| `src-ui/src/app/components/document-list/document-card-large/` | `[hideIfHidden]="true"` on `<pngx-tag>` |
| `src-ui/src/app/components/dashboard/widgets/saved-view-widget/` | `[hideIfHidden]="true"` on `<pngx-tag>` in table view |
| `src-ui/src/app/components/manage/tag-list/` | "Hidden" column in `extraColumns` |

### Design Decisions

- **`hideIfHidden` input on TagComponent** rather than filtering at the card level — this keeps the filtering logic centralized and allows any consumer to opt in by setting the input
- **Default `hideIfHidden = false`** — existing usages (filter dropdowns, edit dialogs) are unaffected; only list views opt in
- **No backend filtering** — the API still returns all tags on a document; filtering is purely a presentation concern
