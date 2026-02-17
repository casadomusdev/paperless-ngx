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

## Correspondent Matching Algorithm (v1.0.28)

See [Mail System](mail-system.md#5-smart-correspondent-matching-v1027) for details on the matching algorithm fix.
