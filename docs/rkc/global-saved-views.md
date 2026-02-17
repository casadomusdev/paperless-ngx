# Global Saved Views

Comprehensive system for organization-wide saved views visible to all users, with centralized ordering, management UI, and personal/global toggle switches.

## Overview

Global saved views are views with `owner_id = NULL` in the database. They appear in all users' sidebars and dashboards. This system provides:

1. **Shared Views** — NULL-owner views visible to everyone
2. **Consistent Ordering** — System-wide ordering via `ApplicationConfiguration` model
3. **Management UI** — Superusers can edit global views through Settings > Saved Views
4. **Toggle Switches** — Convert views between personal and global with one click
5. **Drag-Drop Reordering** — Superusers can reorder global views in sidebar and dashboard
6. **Signal-Based Reactivity** — Angular signals ensure dashboard views load correctly

## Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| ~~`PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`~~ | ~~Integer~~ | ~~None~~ | **Removed in v1.0.11** — replaced by system-wide ApplicationConfiguration storage |

> **Note**: As of v1.0.11, any superuser can reorder global views. No admin user ID configuration needed.

## Creating Global Views

### Via UI (v1.0.10+)
1. Create a saved view as usual (it will be personal)
2. Go to Settings > Saved Views (requires superuser)
3. Toggle the "Global" switch on the desired view
4. Click Save

### Via Database (legacy)
```sql
-- Convert existing view to shared
UPDATE documents_savedview SET owner_id = NULL WHERE id = <view_id>;

-- Create directly as shared
INSERT INTO documents_savedview (name, owner_id, show_on_dashboard, show_in_sidebar)
VALUES ('Shared View Name', NULL, true, true);
```

## Feature Details

### 1. Shared Saved Views (NULL Owner)

Modified `SavedViewViewSet.get_queryset()` to include views where `owner__isnull=True`:

```python
# RKC: Include saved views without owner to allow sharing views with all users
return (
    SavedView.objects.filter(Q(owner=user) | Q(owner__isnull=True))
    .select_related("owner")
    .prefetch_related("filter_rules")
)
# /end RKC edit
```

**Permissions**:
- All authenticated users can **see** shared views
- Only superusers can **edit/delete** shared views via the API
- Backend enforces permissions — non-superusers get 403 Forbidden

### 2. Global View Ordering (System-Wide)

Ordering is stored in `ApplicationConfiguration` model (singleton) with two JSONFields:
- `global_sidebar_views_order` — sidebar ordering
- `global_dashboard_views_order` — dashboard ordering

**Migration**: `src/paperless/migrations/0005_add_global_views_order.py`

The backend reads these from `ApplicationConfiguration` and passes to frontend via `/api/ui_settings/`. Falls back to alphabetical ordering if no order is stored.

### 3. Sidebar & Dashboard Display

**Sidebar**:
- Global views appear in "Shortcuts" section at top
- User's own views appear in "Saved views" section underneath
- Global views are draggable only for superusers (in organizing mode)
- Uses separate `cdkDropList` to prevent intermixing

**Dashboard**:
- Global views appear first with "Personal Saved Views" heading separating sections
- Global views draggable only for superusers
- Separate drop lists for global and personal views

### 4. Management UI (Settings > Saved Views)

**For Superusers**:
- Two sections: "Global Shared Views" (blue card) and "Personal Saved Views"
- Each global view shows a blue "GLOBAL" badge
- Edit name, visibility, display settings for any global view
- Toggle switch to convert between personal ↔ global

**For Regular Users**:
- Only "Personal Saved Views" section visible
- Global views hidden from management page
- Global views still appear normally in sidebar and dashboard

**Component Architecture**:
```typescript
// Separate arrays and FormGroups
public globalViews: SavedView[] = []
public personalViews: SavedView[] = []
private globalViewsGroup = new FormGroup({})
private personalViewsGroup = new FormGroup({})
```

**UI Layout**:
```
┌─────────────────────────────────────────┐
│ Saved Views                              │
├─────────────────────────────────────────┤
│ ┌─ Global Shared Views (Blue Card) ───┐│
│ │ [GLOBAL] View 1 - [Toggle] [Delete] ││
│ │ [GLOBAL] View 2 - [Toggle] [Delete] ││
│ └─────────────────────────────────────┘│
│ ┌─ Personal Saved Views ──────────────┐│
│ │ My View 1 - [Toggle] [Delete]       ││
│ │ My View 2 - [Toggle] [Delete]       ││
│ └─────────────────────────────────────┘│
│ [Cancel] [Save]                         │
└─────────────────────────────────────────┘
```

### 5. Dashboard Race Condition Fix (v1.0.23)

Fixed race condition where dashboard appeared empty on direct URL access (`/dashboard`).

**Root Cause**: Computed signals were reading from non-reactive getters that returned data from plain arrays.

**Solution**: Converted `SavedViewService` to Angular signals:
- `savedViews` array → `savedViewsSignal` signal
- `sidebarViews` getter → computed signal
- `dashboardViews` getter → computed signal

**Reactive Chain**: HTTP response → `savedViewsSignal` → `dashboardViews` computed → `globalDashboardViews` computed → UI updates

## Files Modified

### Backend
- `src/paperless/settings.py` — (removed `GLOBAL_VIEWS_ADMIN_USER_ID` env var in v1.0.11)
- `src/paperless/models.py` — Added `global_sidebar_views_order` and `global_dashboard_views_order` JSONFields
- `src/paperless/migrations/0005_add_global_views_order.py` — Migration for new fields
- `src/documents/views.py` — Shared view queryset, superuser permission checks, ApplicationConfiguration reads

### Frontend
- `src-ui/src/app/data/ui-settings.ts` — Settings keys
- `src-ui/src/app/services/settings.service.ts` — Global views sort order getters, `updateGlobalSidebarViewsSort()`, `updateGlobalDashboardViewsSort()`
- `src-ui/src/app/services/rest/saved-view.service.ts` — Signal-based reactivity
- `src-ui/src/app/components/app-frame/app-frame.component.ts` — Sidebar separation, sorting, drag-drop handlers
- `src-ui/src/app/components/app-frame/app-frame.component.html` — Separate template sections, draggable global views
- `src-ui/src/app/components/dashboard/dashboard.component.ts` — Dashboard separation, sorting, drag-drop handlers, heading
- `src-ui/src/app/components/dashboard/dashboard.component.html` — Separate drop lists, heading
- `src-ui/src/app/components/manage/saved-views/saved-views.component.ts` — Complete refactor with dual FormGroups, toggle switches
- `src-ui/src/app/components/manage/saved-views/saved-views.component.html` — Two-section layout with badges and toggles

## Version History

- **v1.0.0**: Shared saved views (NULL owner) basic support
- **v1.0.6**: Global views ordering via admin user ID, sidebar organization
- **v1.0.9**: Management UI for superusers with visual distinction
- **v1.0.10**: Toggle switches for personal/global conversion
- **v1.0.11**: System-wide ordering via ApplicationConfiguration (removed admin user ID env var), drag-drop reordering
- **v1.0.23**: Dashboard race condition fix with Angular signals
