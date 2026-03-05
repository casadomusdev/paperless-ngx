# Bug Fixes & Patches

Upstream bug fixes and minor enhancements that don't fall under a specific feature category.

## Webhook Docker Hostname Fix (v1.1.1)

### Problem
Upstream PR #10555 ("Enhancement: support webhook restrictions") introduced IP validation for outgoing webhooks. The logic `not ip or (not _is_public_ip(ip) and not WEBHOOKS_ALLOW_INTERNAL_REQUESTS)` short-circuits on `not ip` when `_resolve_first_ip()` returns `None` (DNS fails for Docker hostnames like `paperless-invoice-processor`), blocking the webhook even when `PAPERLESS_WEBHOOKS_ALLOW_INTERNAL_REQUESTS` is `True` (the default).

### Solution
Restructured the boolean logic so the entire IP validation block is skipped when `WEBHOOKS_ALLOW_INTERNAL_REQUESTS` is `True`. Only when internal requests are explicitly disallowed does the IP check enforce public-only destinations.

### File Modified
- `src/documents/signals/handlers.py` — Fixed IP validation logic in `send_webhook()`

## Dashboard Race Condition Fix (v1.0.23)

See [Global Saved Views](global-saved-views.md#5-dashboard-race-condition-fix-v1023) for details.

Converted `SavedViewService` to Angular signals to fix empty dashboard on direct URL access.

### Files Modified
- `src-ui/src/app/services/rest/saved-view.service.ts`
- `src-ui/src/app/components/dashboard/dashboard.component.ts`
- `src-ui/src/app/components/app-frame/app-frame.component.ts`

## Card Views Date Format (v1.0.22)

### Problem
Small cards and large cards views hardcoded `'mediumDate'` format, ignoring the user's DATE_FORMAT setting from Settings > General.

### Solution
Removed hardcoded format parameter from both card view templates. Now card views use the same format as the table view, including date+time formats from v1.0.21.

### Files Modified
- `src-ui/src/app/components/document-list/document-card-small/document-card-small.component.html`
- `src-ui/src/app/components/document-list/document-card-large/document-card-large.component.html`

## Processed Mail Pagination (v1.0.13)

### Problem
`ngb-pagination` was using `processedMails.length` (current page results only, max 50) instead of total count from API, causing pagination to show `<< 1 >>` even with multiple pages.

### Solution
Added `collectionSize` property storing `result.count` from API response.

### Files Modified
- `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.ts`
- `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.html`

## SSO UiSettings Auto-Creation (v1.0.4 → v1.0.5)

See [SSO Debug](sso-debug.md) for details on the UiSettings NULL fix and auto-creation signal.

## Bootstrap Tooltip Dark Mode (v1.1.0)

### Problem
Tooltip text was black-on-black in dark mode (unreadable). Bootstrap adapts text color to page theme, but tooltip background is always dark.

### Solution
Global CSS rule in `src-ui/src/styles.scss`:
```css
::ng-deep .tooltip-inner { color: white !important; }
```

## WebSocket Upload Progress UI Hang (v1.2.6)

### Problem
When uploading documents via the web interface, the UI would get stuck in "Upload complete, waiting..." state indefinitely, even though the backend successfully processed the document and sent a SUCCESS WebSocket message. The issue was in `StatusConsumer._can_view()` in `src/paperless/consumers.py`, which filters WebSocket messages server-side before forwarding them to the browser.

The Angular frontend has this check:
```typescript
!messageData.owner_id ||  // If no owner, everyone sees it
user.is_superuser ||
(messageData.owner_id && messageData.owner_id === user.id) ||
...
```

But the Python backend was missing the crucial `not owner_id` fallback:
```python
return (
    user.is_superuser
    or user.id == owner_id  # Fails when owner_id=None!
    or user.id in users_can_view
    or ...
)
```

When the consumer sends a SUCCESS message with `owner_id=None` (which happens when documents are uploaded via the web UI without explicit ownership), non-superuser WebSocket connections would fail the `_can_view()` check → message silently dropped on the server → browser never receives SUCCESS → UI hangs forever.

### Solution
Added the missing `not owner_id` condition to match the frontend's behavior:
```python
return (
    not owner_id  # NEW: Allow all authenticated users if no owner is set
    or user.is_superuser
    or user.id == owner_id
    or user.id in users_can_view
    or ...
)
```

This ensures that WebSocket progress messages with no owner restriction (`owner_id=None`) are visible to all authenticated users, just like the frontend expects.

### Files Modified
- `src/paperless/consumers.py` — Added `not owner_id` condition to `StatusConsumer._can_view()`

## Correspondent Matching Algorithm (v1.0.28)

See [Mail System](mail-system.md#5-smart-correspondent-matching-v1027) for details on the matching algorithm fix.
