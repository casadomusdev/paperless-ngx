# RKC Customizations Documentation

This document provides a comprehensive inventory of all RKC (Rob Kenis Consulting) customizations made to the Paperless-ngx project. These customizations are marked with "RKC:" comments throughout the codebase and include security enhancements, permission controls, and shared view functionality.

## Table of Contents

1. [Overview](#overview)
2. [Customizations At A Glance](#customizations-at-a-glance)
3. [Quick Start & Deployment](#quick-start--deployment)
4. [Core Features](#core-features)
5. [Permission System](#permission-system)
6. [Backend Customizations](#backend-customizations)
7. [Frontend Customizations](#frontend-customizations)
8. [File Structure](#file-structure)
9. [Testing](#testing)
10. [Environment Variables](#environment-variables)
11. [Maintenance Notes](#maintenance-notes)
12. [Version History](#version-history)

## Overview

The RKC customizations enhance Paperless-ngx with security controls, collaborative features, and customizable defaults. All customizations are marked with "RKC:" comments throughout the codebase for easy identification and maintenance.

## Customizations At A Glance

### Security & Access Control
- **[PDF Editor Superuser Restriction](#1-pdf-editor-superuser-restriction)** - Optional restriction of PDF editing to superusers only, preventing accidental modifications by regular users. Disabled by default. When enabled, superusers can edit ANY document's PDF regardless of ownership.
  - Environment Variable: `PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER` (default: false)
  - Backend: `src/documents/views.py`
  - Frontend: `src-ui/src/app/components/document-detail/`

### Collaborative Features
- **[Shared Saved Views](#2-shared-saved-views-null-owner)** - Enable organization-wide saved views by setting `owner_id = NULL`. All users can view but not modify shared views.
  - Backend: `src/documents/views.py`

- **[Global Views Organization](#3-global-saved-views-organization-sidebar--dashboard)** - Consistent ordering of global saved views across all users in both sidebar and dashboard using designated admin's sort order.
  - Environment Variable: `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`
  - Multiple frontend components

- **[Global Saved Views Management](#4-global-saved-views-management-ui)** - Full UI-based management of global saved views for superusers with visual distinction and admin-controlled ordering.
  - Environment Variable: `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`
  - Backend: `src/documents/views.py`
  - Frontend: `src-ui/src/app/components/manage/saved-views/` (TypeScript & HTML)
  - Frontend: `src-ui/src/app/data/ui-settings.ts`

### UI Customization Defaults
- **[Theme Color Default](#1-theme-color-default-paperless_ui_theme_color)** - Set organization-wide default theme color without overriding user preferences.
  - Environment Variable: `PAPERLESS_UI_THEME_COLOR`

- **[Dark Mode Thumbnail Inversion](#2-dark-mode-thumbnail-inversion-default-paperless_ui_dark_mode_thumb_inverted)** - Configure default thumbnail inversion setting for dark mode.
  - Environment Variable: `PAPERLESS_UI_DARK_MODE_THUMB_INVERTED`

- **[Default UI Language](#3-default-language-paperless_ui_default_language)** - Set organization-wide default interface language.
  - Environment Variable: `PAPERLESS_UI_DEFAULT_LANGUAGE`

### Troubleshooting & Debugging
- **[SSO Debug Logging](#5-social-account-debug-logging-paperless_socialaccount_debug)** - Detailed logging for django-allauth SSO troubleshooting.
  - Environment Variable: `PAPERLESS_SOCIALACCOUNT_DEBUG`
  - Backend: `src/paperless/settings.py`, `src/paperless/adapter.py`

### Bug Fixes & Enhancements
- **SSO UiSettings Auto-Creation** - Automatically creates UiSettings for new SSO users to prevent login errors.
  - Backend: `src/documents/signals/handlers.py`

## Quick Start & Deployment

### Setting Environment Variables

The RKC customizations support optional environment variables for customizing default appearance. Add these to your deployment configuration:

#### Docker Compose

Add to your `docker-compose.yml` or `docker-compose.env.yml`:

```yaml
services:
  webserver:
    environment:
      # Optional: Set custom default theme color (hex format)
      PAPERLESS_UI_THEME_COLOR: "#2563eb"
      
      # Optional: Set dark mode thumbnail inversion default (true/false)
      PAPERLESS_UI_DARK_MODE_THUMB_INVERTED: "true"
      
      # Optional: Set default UI language (language code)
      PAPERLESS_UI_DEFAULT_LANGUAGE: "de-de"
```

Or use an environment file (`.env`):

```bash
# .env file
PAPERLESS_UI_THEME_COLOR=#2563eb
PAPERLESS_UI_DARK_MODE_THUMB_INVERTED=true
PAPERLESS_UI_DEFAULT_LANGUAGE=de-de
```

#### Bare Metal Installation

Export environment variables before starting Paperless:

```bash
export PAPERLESS_UI_THEME_COLOR="#2563eb"
export PAPERLESS_UI_DARK_MODE_THUMB_INVERTED="true"
export PAPERLESS_UI_DEFAULT_LANGUAGE="de-de"

# Then start paperless
./manage.py runserver
```

Or add to your systemd service file:

```ini
[Service]
Environment="PAPERLESS_UI_THEME_COLOR=#2563eb"
Environment="PAPERLESS_UI_DARK_MODE_THUMB_INVERTED=true"
Environment="PAPERLESS_UI_DEFAULT_LANGUAGE=de-de"
```

### Rebuilding the Frontend

After modifying any frontend customizations, you must rebuild the Angular application:

#### Docker Installation

```bash
# Rebuild the Docker image
docker compose build

# Or if using the official image, rebuild only the frontend:
docker compose run --rm webserver python3 manage.py collectstatic --clear --no-input
```

#### Bare Metal Installation

```bash
# Navigate to frontend source directory
cd src-ui

# Install dependencies (if needed)
npm install

# Build production frontend
npm run build

# Navigate back to project root
cd ..

# Collect static files
python3 manage.py collectstatic --clear --no-input

# Restart your web server
sudo systemctl restart paperless-webserver
```

#### Development Mode

For development with live reload:

```bash
cd src-ui
npm install
npm run start

# Frontend will be available at http://localhost:4200
# Backend API should be running separately on port 8000
```

### Applying Changes

**After setting environment variables**:
1. No rebuild needed - just restart the Paperless container/service
2. Changes apply immediately to users without custom preferences
3. Existing user preferences remain unchanged

**After modifying code**:
1. Rebuild frontend (see above)
2. Restart backend service
3. Clear browser cache if changes don't appear

## Core Features

### 1. PDF Editor Superuser Restriction
**Purpose**: Optionally restrict PDF editor access to superusers only to prevent accidental file modifications by regular users

**Environment Variable**: `PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER`
- **Type**: Boolean
- **Default**: `false` (restriction disabled - original Paperless-ngx behavior)
- **Example**: `PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER=true`

**Files Modified**:
- `src/paperless/settings.py` - Environment variable configuration
- `src/documents/views.py` - Backend permission check + UI settings exposure
- `src-ui/src/app/data/ui-settings.ts` - Settings key definition
- `src-ui/src/app/components/document-detail/document-detail.component.ts` - Frontend setting getter
- `src-ui/src/app/components/document-detail/document-detail.component.html` - UI visibility control

**Behavior**:
- **When disabled (default)**: All users can access PDF editor (original Paperless-ngx behavior)
- **When enabled**: Only superusers can access PDF editor
  - Backend validates `user.is_superuser` before allowing PDF edit operations
  - Frontend hides PDF Editor button for non-superusers
  - Returns `HttpResponseForbidden` with clear error message when unauthorized
  - Superusers can edit ANY document's PDF regardless of ownership

**Security Benefits**:
- Defense in depth: Backend rejects unauthorized requests + Frontend hides the option
- Clean UX: Regular users don't see confusing disabled options when restriction is enabled
- API Protection: Direct API calls are rejected even if frontend bypass is attempted
- Flexible deployment: Can be enabled/disabled per environment without code changes

### 2. Shared Saved Views (NULL Owner)
**Purpose**: Enable global saved views that are visible to all users when owner_id is NULL

**Files Modified**:
- `src/documents/views.py` - Modified `SavedViewViewSet.get_queryset()`

**Key Changes**:
- Queries now include views where `owner__isnull=True` in addition to user-owned views
- Prevents editing/deleting of shared views through permission system
- Shared views appear in all users' saved view lists

**Use Case**:
- Administrator can create organization-wide saved views
- Users can access but not modify shared views
- Owner can be cleared directly in database: `UPDATE documents_savedview SET owner_id = NULL WHERE id = X`

### 3. Global Saved Views Organization (Sidebar & Dashboard)
**Purpose**: Organize global saved views with consistent ordering across all users in both sidebar and dashboard

**Environment Variable**:
- `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`: User ID of admin whose view sort orders determine global view ordering

**Files Modified**:
- `src/paperless/settings.py` - Environment variable configuration
- `src/documents/views.py` - Pass admin user's sidebar and dashboard sort orders to frontend
- `src-ui/src/app/data/ui-settings.ts` - Settings keys for global views sort orders
- `src-ui/src/app/services/settings.service.ts` - Getters for global views sort orders (sidebar and dashboard)
- `src-ui/src/app/components/app-frame/app-frame.component.ts` - Computed properties for sidebar view separation and sorting
- `src-ui/src/app/components/app-frame/app-frame.component.html` - Separate template sections for global and user sidebar views
- `src-ui/src/app/components/dashboard/dashboard.component.ts` - Computed properties for dashboard view separation and sorting
- `src-ui/src/app/components/dashboard/dashboard.component.html` - Separate template sections for global and user dashboard views
- `src-ui/src/app/components/manage/saved-views/saved-views.component.ts` - Filter global views from management page

**Key Changes**:
1. **Sidebar Display**:
   - Global views appear in "Shortcuts" section at top of sidebar
   - User's own views appear in "Saved views" section underneath
   - Global views are not draggable (prevents confusion)
   - User views remain draggable for personalized ordering

2. **Dashboard Display**:
   - Global views appear first on dashboard
   - User's own dashboard views appear after global views
   - Global views are not draggable (marked with `cdkDragDisabled`)
   - User dashboard views remain draggable for personalized ordering

3. **Ordering**:
   - Sidebar global views ordered by admin user's `sidebar-views-sort-order` setting
   - Dashboard global views ordered by admin user's `dashboard-views-sort-order` setting
   - Falls back to alphabetical ordering if admin sort order unavailable
   - Consistent ordering across all users in both locations

4. **Management Page**:
   - Global views hidden from non-admin users in saved views management
   - Prevents confusion and accidental attempts to edit global views
   - Admins can see all views including global ones

**Use Case**:
- Organization creates global saved views with `owner_id = NULL`
- Designated admin user (via PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID) organizes global views in both sidebar and dashboard
- All users see global views in same order as admin's organization in both locations
- Clean separation between organizational shortcuts and personal views
- Admin can organize sidebar and dashboard independently

### 4. Global Saved Views Management UI
**Purpose**: Enable full UI-based management of global saved views for superusers with visual separation and admin-controlled ordering

**Environment Variable**:
- `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`: User ID of admin authorized to save global view ordering

**Files Modified**:
- `src/documents/views.py` - Backend permission checks for global view editing
- `src-ui/src/app/data/ui-settings.ts` - Added GLOBAL_VIEWS_ADMIN_USER_ID settings key
- `src-ui/src/app/components/manage/saved-views/saved-views.component.ts` - Complete component refactor
- `src-ui/src/app/components/manage/saved-views/saved-views.component.html` - New UI layout

**Key Features**:

1. **Superuser Access Control**:
   - Only superusers can see and edit global views in the management page
   - Regular users only see their personal views
   - Backend enforces permissions - superusers can modify global views via API
   - Non-superusers get 403 Forbidden when attempting to modify global views

2. **Visual Distinction**:
   - **Global Shared Views Section**: Displayed in a blue card with "Global Shared Views" header
   - **GLOBAL Badges**: Each global view shows a blue "GLOBAL" ba dge for clear identification
   - **Personal Saved Views Section**: Displayed in standard card below global views
   - Clean separation prevents confusion between organizational and personal views

3. **Admin Authorization**:
   - Component includes `isGlobalViewsAdmin` getter
   - Checks if current user ID matches `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`
   - Only the designated admin sees "Save Global View Order" button
   - Non-admin superusers see warning: "Only the designated admin can reorder these views"

4. **Dual Form Management**:
   - Separate FormGroups for global views (`globalViewsGroup`) and personal views (`personalViewsGroup`)
   - Each group independently tracks changes and validation
   - Save operation combines both groups for efficient API call
   - Delete operation correctly identifies and removes from appropriate array

5. **Global View Ordering**:
   - `saveGlobalViewsOrder()` method stores current order to backend
   - Order saved to both sidebar and dashboard settings simultaneously
   - Changes immediately propagate to all users
   - Only authorized admin can save ordering

**Component Architecture**:

```typescript
// Properties
public globalViews: SavedView[] = []
public personalViews: SavedView[] = []
private globalViewsGroup = new FormGroup({})
private personalViewsGroup = new FormGroup({})

// Getters
get isGlobalViewsAdmin(): boolean {
  const adminUserId = this.settings.get(SETTINGS_KEYS.GLOBAL_VIEWS_ADMIN_USER_ID)
  return adminUserId !== null && this.permissionsService.currentUserId === adminUserId
}

// Key Methods
ngOnInit() - Separates views into global and personal arrays
initialize() - Creates separate FormGroups for each view type  
save() - Combines and saves both global and personal changes
deleteSavedView() - Removes from appropriate array
saveGlobalViewsOrder() - Stores global view order (admin only)
```

**UI Layout**:

```
┌─────────────────────────────────────────┐
│ Saved Views                              │
├─────────────────────────────────────────┤
│ ┌─ Global Shared Views (Blue Card) ───┐│
│ │ These views are visible to all users ││
│ │ [Warning if not admin]               ││
│ │                                       ││
│ │ [GLOBAL] View 1 - [Edit] [Delete]   ││
│ │ [GLOBAL] View 2 - [Edit] [Delete]   ││
│ │                                       ││
│ │ [Save Global View Order] (admin only)││
│ └─────────────────────────────────────┘│
│                                          │
│ ┌─ Personal Saved Views ──────────────┐│
│ │ These views are private to account   ││
│ │                                       ││
│ │ My View 1 - [Edit] [Delete]         ││
│ │ My View 2 - [Edit] [Delete]         ││
│ └─────────────────────────────────────┘│
│                                          │
│ [Cancel] [Save]                         │
└─────────────────────────────────────────┘
```

**Security Model**:
- **Backend**: `SavedViewViewSet` allows superusers to modify global views (owner=NULL)
- **Frontend**: Component separates and displays views based on owner field
- **Authorization**: Admin check prevents unauthorized ordering changes
- **Defense in Depth**: Both UI hiding and backend validation

**Workflow Example**:

1. **Admin Creates Global View**:
   ```sql
   -- Create view then clear owner
   UPDATE documents_savedview SET owner_id = NULL WHERE id = X;
   ```

2. **Superuser Edits Global View**:
   - Logs into Settings > Saved Views
   - Sees both "Global Shared Views" and "Personal Saved Views" sections
   - Edits global view name, visibility, or display settings
   - Clicks "Save" - backend allows modification

3. **Admin Organizes Global Views**:
   - Designated admin (matching PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID)
   - Sees "Save Global View Order" button
   - Arranges global views in desired order
   - Clicks "Save Global View Order"
   - Order propagates to all users' sidebar and dashboard

4. **Regular User Experience**:
   - Logs into Settings > Saved Views
   - Sees only "Personal Saved Views" section
   - Cannot see or modify global views in management page
   - Global views still appear normally in sidebar and dashboard

**Use Cases**:
- IT department creates standard views for different document types
- Superusers can refine global view settings without database access
- Designated admin maintains consistent organization across all users
- Users focus on personalizing their own views without confusion

**Benefits**:
- No more database manipulation required for editing global views
- Clear visual separation reduces user confusion
- Superuser-only access maintains security
- Admin ordering provides organization-wide consistency
- Clean upgrade path for future Paperless-ngx updates (all changes marked with RKC comments)

## Permission System

### Superuser Restrictions
1. **PDF Editor**: Only superusers can access PDF editing operations
   - Backend validation in `BulkEditView.post()`
   - Frontend visibility controlled by `userIsSuperuser` getter
   - Applies to all PDF manipulation operations (rotate, split, merge, edit)

### Shared View Permissions
1. **View Access**: All authenticated users can see shared views (NULL owner)
2. **Edit Restrictions**: Shared views cannot be edited through the API
3. **Delete Restrictions**: Shared views cannot be deleted through the API
4. **Database-Only Management**: Owner changes require direct database access

## Backend Customizations

### 1. PDF Editor Access Control (`src/documents/views.py`)
**Location**: `BulkEditView.post()` method

**Code**:
```python
# RKC: Optional restriction of PDF editor to superusers to prevent accidental file modifications
# Controlled via PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER environment variable (default: false)
if (
    method == bulk_edit.edit_pdf
    and settings.PDF_EDITOR_RESTRICT_TO_SUPERUSER
    and not user.is_superuser
):
    return HttpResponseForbidden("PDF editor is restricted to administrators")
# /end RKC edit
```

**Behavior**:
- Only applies when `PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER=true`
- Checks if operation is `edit_pdf`
- Validates user is superuser
- Returns 403 Forbidden if unauthorized
- Executes before any file operations occur
- When disabled, all users have access (original Paperless-ngx behavior)

### 2. Shared Saved Views (`src/documents/views.py`)
**Location**: `SavedViewViewSet.get_queryset()` method

**Code**:
```python
# RKC: Include saved views without owner (owner__isnull=True) to allow sharing views with all users
return (
    SavedView.objects.filter(Q(owner=user) | Q(owner__isnull=True))
    .select_related("owner")
    .prefetch_related("filter_rules")
)
# /end RKC edit
```

**Behavior**:
- Includes views owned by current user
- Includes views with NULL owner
- Maintains proper prefetching for performance
- Read-only access to shared views

## Frontend Customizations

### 1. PDF Editor Restriction Setting Getter (`src-ui/src/app/components/document-detail/document-detail.component.ts`)
**Location**: Component property getters

**Code**:
```typescript
// RKC: Check if user is superuser to restrict PDF editor access to admins only
get userIsSuperuser(): boolean {
  return this.permissionsService.isSuperUser()
}
// /end RKC edit

// RKC: Check if PDF editor restriction is enabled via environment variable
get pdfEditorRestrictToSuperuser(): boolean {
  return this.settings.get(SETTINGS_KEYS.PDF_EDITOR_RESTRICT_TO_SUPERUSER)
}
// /end RKC edit
```

**Purpose**:
- `userIsSuperuser`: Provides reactive superuser status check
- `pdfEditorRestrictToSuperuser`: Reads the restriction setting from backend
- Both used for conditional rendering in template
- Integrates with existing permissions and settings services

### 2. Conditional PDF Editor Button (`src-ui/src/app/components/document-detail/document-detail.component.html`)
**Location**: Actions dropdown menu

**Code**:
```html
<!-- RKC: Optionally hide PDF Editor menu item for non-superusers to prevent accidental file modifications
     Controlled via PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER environment variable (default: false)
     When restriction is enabled (!pdfEditorRestrictToSuperuser || userIsSuperuser):
     - If restriction disabled: all users see the button (original behavior)
     - If restriction enabled: only superusers see the button
     NOTE: Removed !userIsOwner condition to allow superusers to edit ANY document's PDF,
     not just documents they own. Superusers should have full editing rights. -->
<button *ngIf="!pdfEditorRestrictToSuperuser || userIsSuperuser" ngbDropdownItem (click)="editPdf()" [disabled]="!userCanEdit || originalContentRenderType !== ContentRenderType.PDF">
  <i-bs name="pencil"></i-bs>&nbsp;<ng-container i18n>PDF Editor</ng-container>
</button>
<!-- /end RKC edit -->
```

**Purpose**:
- Conditionally controls PDF Editor visibility based on environment variable
- When restriction disabled: all users see the button (original Paperless-ngx behavior)
- When restriction enabled: completely hides PDF Editor option for non-superusers
- Allows superusers to edit ANY document's PDF (including documents with NULL owner or owned by others)
- Still enforces that the document must be a PDF and the user must have edit permissions
- Prevents confusion from disabled buttons when restriction is active

## File Structure

### Backend Customizations
```
src/documents/
└── views.py
    ├── BulkEditView.post() - PDF editor superuser check
    └── SavedViewViewSet.get_queryset() - Shared saved views
```

### Frontend Customizations
```
src-ui/src/app/components/document-detail/
├── document-detail.component.ts - Superuser getter
└── document-detail.component.html - Conditional button rendering
```

## Testing

### Test Categories

#### 1. PDF Editor Restriction Tests
**Manual Tests**:
- Login as regular user → PDF Editor button should not appear
- Login as superuser → PDF Editor button should appear
- Attempt direct API call as regular user → Should receive 403 Forbidden
- Verify superuser can successfully use PDF editor

**Expected Behavior**:
- Non-superusers: No PDF editor UI element visible
- Non-superusers: API returns `403 Forbidden` with message "PDF editor is restricted to administrators"
- Superusers: Full PDF editor access including UI and API

#### 2. Shared Saved Views Tests
**Database Setup**:
```sql
-- Create shared view (as admin)
INSERT INTO documents_savedview (name, owner_id, ...) VALUES ('Shared Invoices', 1, ...);

-- Convert to shared view (clear owner)
UPDATE documents_savedview SET owner_id = NULL WHERE id = X;
```

**Manual Tests**:
- Login as User A → Shared view should appear in saved views list
- Login as User B → Same shared view should appear
- Attempt to edit shared view → Should fail (permission check)
- Attempt to delete shared view → Should fail (permission check)
- Verify regular user-owned views still work normally

**Expected Behavior**:
- All users see views with NULL owner_id
- Shared views are read-only through the API
- Personal views function normally
- Shared views work correctly in filters and searches

### Test Implementation
```bash
# Backend tests
pytest tests/test_rkc_pdf_editor.py
pytest tests/test_rkc_shared_views.py

# Frontend tests (if implemented)
ng test --include='**/*rkc*.spec.ts'
```

## Maintenance Notes

### Code Identification
- All custom code is marked with `RKC:` comments
- Backend Python: `# RKC: explanation`
- Frontend TypeScript: `// RKC: explanation`
- Frontend HTML: `<!-- RKC: explanation -->`
- All blocks end with `# /end RKC edit` (or equivalent)

### Update Considerations

#### When Upgrading Paperless-ngx:
1. **Search for RKC markers** before applying updates
2. **Review affected files**:
   - `src/documents/views.py`
   - `src-ui/src/app/components/document-detail/document-detail.component.ts`
   - `src-ui/src/app/components/document-detail/document-detail.component.html`
3. **Test customizations** after upgrade:
   - PDF editor access control
   - Shared saved views visibility
4. **Update this documentation** if customizations change

#### Critical Update Areas:
- **BulkEditView**: If bulk edit operations are refactored
- **SavedViewViewSet**: If saved view query logic changes
- **Document detail component**: If PDF editor UI is restructured
- **Permissions service**: If superuser checking logic changes

### Dependencies
- Django permissions system (superuser flag)
- Angular permissions service (`PermissionsService.isSuperUser()`)
- Existing saved view infrastructure
- Document bulk edit operations

### Database Considerations

#### Creating Shared Views:
```sql
-- Option 1: Create directly as shared
INSERT INTO documents_savedview (name, owner_id, show_on_dashboard, show_in_sidebar)
VALUES ('Shared View Name', NULL, true, true);

-- Option 2: Convert existing view to shared
UPDATE documents_savedview 
SET owner_id = NULL 
WHERE id = <view_id>;
```

#### Restoring Owner:
```sql
-- If edits needed, temporarily restore owner
UPDATE documents_savedview 
SET owner_id = <admin_user_id> 
WHERE id = <view_id>;

-- Make changes via API/UI...

-- Convert back to shared
UPDATE documents_savedview 
SET owner_id = NULL 
WHERE id = <view_id>;
```

## Environment Variables

### 1. PDF Editor Restriction (`PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER`)
**Purpose**: Optionally restrict PDF editor access to superusers only

**Type**: Boolean
**Default**: `false` (restriction disabled - original Paperless-ngx behavior)
**Example**: `PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER=true`

**Behavior**:
- When `false` (default): All users can access PDF editor (original Paperless-ngx behavior)
- When `true`: Only superusers can access PDF editor
  - Non-superusers won't see the PDF Editor button in the UI
  - Direct API calls from non-superusers return 403 Forbidden
  - Superusers can edit ANY document's PDF regardless of ownership
- Changes take effect immediately after restart
- No database changes required

**Use Cases**:
- Organizations wanting to prevent accidental PDF modifications by regular users
- Environments requiring strict document integrity controls
- Multi-tenant deployments with varying trust levels

**Implementation**:
- Backend: `src/paperless/settings.py` - Reads env var as boolean
- Backend: `src/documents/views.py` - Permission check + UI settings exposure
- Frontend: `src-ui/src/app/data/ui-settings.ts` - Settings key
- Frontend: `src-ui/src/app/components/document-detail/` - Conditional UI rendering

### 2. Theme Color Default (`PAPERLESS_UI_THEME_COLOR`)
**Purpose**: Set a custom default theme color for new users and users who haven't selected a color

**Type**: String (hex color)
**Default**: `#17541f` (Paperless green)
**Example**: `PAPERLESS_UI_THEME_COLOR=#2563eb`

**Behavior**:
- Users without a theme color preference will see this color
- Users can still override this by selecting their own color in Settings
- Changing this env var updates all users without a custom color instantly
- Does not overwrite existing user preferences

**Implementation**:
- Backend: `src/paperless/settings.py` - Reads env var
- Backend: `src/documents/views.py` - Passes to frontend via `/api/ui_settings/`
- Frontend: `src-ui/src/app/data/ui-settings.ts` - Adds setting key
- Frontend: `src-ui/src/app/services/settings.service.ts` - Uses as fallback

### 3. Dark Mode Thumbnail Inversion Default (`PAPERLESS_UI_DARK_MODE_THUMB_INVERTED`)
**Purpose**: Set the default for inverting document thumbnails in dark mode

**Type**: Boolean
**Default**: `true`
**Example**: `PAPERLESS_UI_DARK_MODE_THUMB_INVERTED=false`

**Behavior**:
- New users will have this setting as their default
- Users who haven't explicitly set this preference will use this value
- Users can still override this in Settings > Appearance
- Useful for organizations that want consistent default appearance

**Implementation**:
- Backend: `src/paperless/settings.py` - Reads env var as boolean
- Backend: `src/documents/views.py` - Passes to frontend via `/api/ui_settings/`
- Frontend: `src-ui/src/app/data/ui-settings.ts` - Adds setting key
- Frontend: `src-ui/src/app/services/settings.service.ts` - Uses as fallback in `get()` method

### 4. Default Language (`PAPERLESS_UI_DEFAULT_LANGUAGE`)
**Purpose**: Set the default UI language for new users and users who haven't selected a language

**Type**: String (language code)
**Default**: `de-de` (German)
**Example**: `PAPERLESS_UI_DEFAULT_LANGUAGE=fr-fr`

**Behavior**:
- Users without a language preference will see the UI in this language
- Users can still override this by selecting their own language in Settings > General
- Changing this env var updates all users without a custom language instantly
- Does not overwrite existing user preferences

**Available Language Codes**:
- `de-de` (German) - Default
- `en-us` (English US)
- `en-gb` (English GB)
- `fr-fr` (French)
- `es-es` (Spanish)
- `it-it` (Italian)
- `nl-nl` (Dutch)
- `pt-pt` (Portuguese)
- `pt-br` (Portuguese Brazil)
- `da-dk` (Danish)
- `no-no` (Norwegian)
- `sv-se` (Swedish)
- `fi-fi` (Finnish)
- `cs-cz` (Czech)
- `pl-pl` (Polish)
- `ru-ru` (Russian)
- `ja-jp` (Japanese)
- `ko-kr` (Korean)
- `zh-cn` (Chinese Simplified)
- `zh-tw` (Chinese Traditional)
- `ar-ar` (Arabic)
- And 15+ more languages

**Implementation**:
- Backend: `src/paperless/settings.py` - Reads env var
- Backend: `src/documents/views.py` - Passes to frontend via `/api/ui_settings/`
- Frontend: `src-ui/src/app/data/ui-settings.ts` - Adds setting key
- Frontend: `src-ui/src/app/services/settings.service.ts` - Uses as fallback in `get()` method

### 5. Global Views Admin User (`PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`)
**Purpose**: Designate which admin user's sidebar organization determines global saved views ordering

**Type**: Integer (User ID)
**Default**: None (alphabetical fallback)
**Example**: `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID=1`

**Behavior**:
- Specifies the user ID whose saved views sidebar sort order is used for global views
- Global saved views (owner=NULL) are displayed in "Shortcuts" section
- All users see global views in the same order as this designated admin
- Falls back to alphabetical ordering if not set or if admin user has no sort order
- Does not affect user's own personal saved views ordering

**Setup Process**:
1. Set `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID` to admin user's ID
2. That admin organizes global views in their sidebar (drag/drop)
3. All users immediately see global views in that order
4. Personal views remain independently sortable per user

**Implementation**:
- Backend: `src/paperless/settings.py` - Reads and validates env var
- Backend: `src/documents/views.py` - Fetches admin user's sort order settings
- Frontend: `src-ui/src/app/services/settings.service.ts` - Provides globalViewsSortOrder getter
- Frontend: `src-ui/src/app/components/app-frame/app-frame.component.ts` - Sorts global views accordingly

**Database Query**:
```sql
-- Find user ID to use for PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID
SELECT id, username, is_superuser FROM auth_user WHERE is_superuser = true;
```

### 6. SSO Debug Logging (`PAPERLESS_DEBUG_SSO`)
**Purpose**: Enable detailed debug logging for django-allauth SSO troubleshooting without full DEBUG mode

**Environment Variable**: `PAPERLESS_DEBUG_SSO`
- **Type**: Boolean
- **Default**: `false`
- **Example**: `PAPERLESS_DEBUG_SSO=true`

**Files Modified**:
- `src/paperless/settings.py` - Debug mode configuration and logger setup
- `src/paperless/adapter.py` - SSO user creation debug logging
- `src/documents/signals/handlers.py` - UiSettings creation debug logging

**Behavior**:
- When disabled (default): Minimal logging, standard INFO/ERROR levels only
- When enabled: Verbose DEBUG logging for:
  - All django-allauth operations (signup, authentication, provider flow)
  - Django request/response cycle during SSO
  - Custom adapter operations (user creation, group assignment)
  - UiSettings auto-creation for new users
- Logs to both `paperless.log` file and console
- No performance impact when disabled

**Use Cases**:
- Troubleshooting SSO signup failures
- Debugging OAuth provider configuration issues
- Investigating user creation problems
- Diagnosing authentication errors

**Log Output Location**:
- File: `/usr/src/paperless/data/log/paperless.log` (inside container)
- Console: `docker logs <container-name>` or systemd journal

**What Gets Logged**:
- `[allauth]` - General allauth framework operations
- `[allauth.account]` - Account creation and management
- `[allauth.socialaccount]` - Social provider authentication flow
- `[SSO]` - Custom adapter debug messages
- `Social SSO:` - User creation and group assignment
- Django request/response details during SSO flow

**Example Usage**:
```bash
# Enable SSO debug logging
docker compose down
# Add to docker-compose.yml environment section:
# - PAPERLESS_DEBUG_SSO=true
docker compose up -d

# Watch logs in real-time
docker compose logs -f webserver

# Attempt SSO signup
# Check logs for detailed debug output

# Disable after troubleshooting
# Remove or set to false, then restart
docker compose restart webserver
```

**Security Note**: Debug logs may contain sensitive information like tokens. Review before sharing and disable after troubleshooting.

**Implementation**:
- Backend: `src/paperless/settings.py` - Reads `PAPERLESS_DEBUG_SSO` env var and conditionally enables debug loggers
- Backend: `src/paperless/adapter.py` - Debug logging in `CustomSocialAccountAdapter` (respects `paperless.auth` logger level)
- Backend: `src/documents/signals/handlers.py` - Conditional debug logging in `create_ui_settings_for_new_user` signal

## Version History

- **v1.0.17 (2025-01-12)**: Mail action connection pooling to eliminate OAuth2 authentication storms
  - Implemented batched mail action processing via scheduled tasks to eliminate Microsoft IMAP rate limiting
  - **Problem**: Celery chord pattern created 100s of simultaneous OAuth2 authentication requests when processing emails
  - **Root Cause**: Each email spawned async `apply_mail_action` task requiring new IMAP connection and OAuth2 auth
  - **Solution**: 
    - Modified `queue_consumption_tasks()` to create PENDING_POST_ACTION entries instead of immediate callbacks
    - Added `update_mail_status()` helper task for asynchronous status updates
    - Created `process_pending_mail_actions()` scheduled task (runs every 5 minutes via Celery Beat)
    - Created `process_account_pending_actions()` batch processor that pools connections per account
    - One pooled IMAP connection per account per batch = eliminated authentication storm
  - **Architecture**:
    - PENDING_POST_ACTION is transient status - quickly transitions to SUCCESS/FAILED
    - Scheduled task groups pending entries by account for connection pooling  
    - Single authenticated IMAP session processes all actions for that account sequentially
    - Natural rate limiting via 5-minute schedule interval
  - **Benefits**:
    - Eliminates OAuth2 "AUTHENTICATE failed" errors from Microsoft rate limiting
    - Improved reliability through batch error handling
    - Better resource usage with predictable load patterns
    - Minimal code impact - backward compatible with existing entries
  - Files modified:
    - Backend: `src/paperless_mail/models.py` (documented PENDING_POST_ACTION status)
    - Backend: `src/paperless_mail/mail.py` (new tasks: update_mail_status, process_pending_mail_actions, process_account_pending_actions; modified queue_consumption_tasks)
    - Backend: `src/paperless/celery.py` (added Celery Beat schedule for periodic processing)
  - All changes properly marked with RKC comments for maintainability
  - See `IMPL_MAIL_ACTION_POOLING.md` for detailed implementation documentation

- **v1.0.16 (2025-01-12)**: Server-side filtering for Processed Mail
  - Migrated from client-side to server-side filtering for better search capabilities
  - **Problem**: Client-side filtering (v1.0.15) only worked on current page (max 50 items), could not search entire dataset
  - **Solution**: 
    - Backend accepts `filter_field` and `filter_text` query parameters via Django filters
    - Database queries filter entire dataset using `__icontains`, not just current page
    - Accurate filtered counts displayed across all entries
    - Significant improvement for finding specific items in large datasets (1000+ emails)
  - **Filter Fields**:
    - Error (default) - search error messages and tracebacks
    - Subject - filter by email subject line
    - Received - filter by email received timestamp
    - Processed - filter by processing timestamp
  - **Features**:
    - Case-insensitive search across entire dataset
    - Pagination works correctly with active filters
    - Debounced input (100ms, 3-char minimum) for performance
    - Filter automatically resets to page 1 when changed
    - Clear button to remove filter and reload all data
  - **Performance**:
    - Uses Django ORM `__icontains` for safe, efficient queries
    - 3-character minimum prevents excessive database load
    - Supports PostgreSQL ILIKE for case-insensitive matching
  - **Architecture**:
    - Custom FilterSet field `filter_text` with dynamic field targeting
    - Single `filter_by_text` method handles all field types
    - Frontend reloads data from server on filter change
    - Removed client-side `filteredMails` getter (now server-side)
  - Files modified:
    - Backend: `src/paperless_mail/filters.py` (added server-side filtering logic)
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.ts` (server-side reload)
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.html` (updated count display)
  - All changes properly marked with RKC comments for maintainability
  - **Future Enhancement**: File Tasks page could use same pattern (Phase 2 of IMPL_BACKEND_FILTERS.md)

- **v1.0.15 (2025-01-12)**: Processed mail filtering capability
  - Added client-side filtering to processed mail dialog matching file tasks page pattern
  - **Filter Targets**:
    - Error field (default) - key requirement for troubleshooting failed mail processing
    - Subject field - filter by email subject line
    - Received date - filter by email received timestamp
    - Processed date - filter by processing timestamp
  - **Implementation**:
    - RxJS debouncing (100ms) with 3-character minimum for performance
    - Enum-based filter target selection for type safety
    - Filter input with dropdown for target selection and clear button
    - Filter state resets on dialog open (minimal core code impact)
    - Follows exact same pattern as file tasks page for UI consistency
  - **UI Components**:
    - Input field with placeholder "Filter..."
    - Clear button (X) appears when filter text is present
    - Dropdown selector for choosing filter target field
    - Active filter target highlighted in dropdown
    - Keyboard support via Enter key (clears filter)
  - **Architecture**:
    - MailFilterTarget enum: Error (0), Subject (1), Received (2), Processed (3)
    - filteredMails getter with switch-case filtering logic
    - Private filterDebounce Subject for reactive filtering
    - Proper cleanup via OnDestroy to prevent memory leaks
  - Files modified:
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.ts` (added filtering logic, enums, properties)
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.html` (added filter UI, changed loop to filteredMails)
  - All changes properly marked with RKC comments for maintainability

- **v1.0.14 (2025-01-12)**: Processed mail dialog enhancements
  - Enhanced error column in processed mail dialog with clickable modal for full tracebacks
  - **Problem**: Error messages were limited to 20 character preview on hover, making full tracebacks inaccessible
  - **Solution**: 
    - Table column continues to show first 20 characters (maintains compact layout)
    - Hover popover displays full error text for quick reference
    - Made error text clickable with visual indicators (pointer cursor, dotted underline)
    - Click opens scrollable modal dialog showing complete error traceback
    - Modal includes email subject for context
  - **Date/Time Display Enhancement**:
    - Changed Received and Processed columns from date-only (`longDate`) to date+time (`short`)
    - Now displays date with hours:minutes for better tracking of mail processing
    - Format example: "1/12/25, 10:30 AM" instead of just "Jan 12, 2025"
  - **UX improvements**:
    - Compact table layout preserved (20 char limit)
    - Hover preview shows full error text in popover
    - Click opens large scrollable modal with full error content
    - Modal uses word-wrap for long lines
    - Clean close button in modal footer
    - Time-of-day visibility improves troubleshooting
  - Files modified:
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.ts` (added NgbModal injection, showErrorDetails method, ErrorDetailModalComponent)
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.html` (clickable error text with styling, changed date format from 'longDate' to 'short')
  - All changes properly marked with RKC comments for maintainability

- **v1.0.13 (2025-01-12)**: Processed mail pagination fix
  - Fixed bug where processed mail dialog pagination was broken
  - Problem: `ngb-pagination` was using `processedMails.length` (current page results only) instead of total count from API
  - This caused pagination to only show `<< 1 >>` even when multiple pages existed
  - Solution: Added `collectionSize` property to store `result.count` from API response
  - Updated pagination to use `collectionSize` for proper multi-page navigation
  - Files modified:
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.ts`
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.html`
  - All changes properly marked with RKC comments for maintainability

- **v1.0.12 (2025-12-09)**: Mail-document correlation via custom fields
  - Implemented reliable email-to-document correlation using IMAP UIDs
  - Solves async processing issue where timestamp-based correlation fails with Celery's parallel processing
  - Added `mail_uid` field to ConsumableDocument dataclass for passing IMAP UID through processing pipeline
  - Added `PAPERLESS_MAIL_CORRELATION_FIELD` environment variable (default: "Mail UID")
  - Helper function `_attach_mail_uid_custom_field()` creates CustomFieldInstance linking document to email
  - Non-critical enhancement: failures don't abort document consumption, only log warnings
  - Enables future queries to find documents originating from specific emails via custom field
  - **Querying documents by mail UID via REST API**:
    - Use the `custom_field_query` parameter to filter documents by "Mail UID" custom field
    - Example: `GET /api/documents/?custom_field_query=["Mail UID", "exact", "12345"]`
    - Retrieves all documents that were created from the email with IMAP UID "12345"
    - Supported operators for STRING fields: `exact`, `icontains`, `istartswith`, `iendswith`, `in`, `isnull`, `exists`
    - Complex queries supported with AND/OR/NOT logic for advanced filtering
  - Files modified:
    - Backend: `src/documents/data_models.py` (added mail_uid field)
    - Backend: `src/paperless/settings.py` (added PAPERLESS_MAIL_CORRELATION_FIELD env var)
    - Backend: `src/paperless_mail/mail.py` (pass mail_uid in both attachment and EML processing)
    - Backend: `src/documents/consumer.py` (added helper function and call after document.save())
  - All changes properly marked with RKC comments for maintainability
  - See `MAILDOC_CORRELATION.md` for detailed implementation documentation

- **v1.0.11 (2025-12-09)**: System-wide global view ordering with drag-drop interface
  - Replaced per-user global view ordering with centralized system-wide storage
  - Added two new fields to ApplicationConfiguration model:
    - `global_sidebar_views_order` - JSONField for sidebar ordering
    - `global_dashboard_views_order` - JSONField for dashboard ordering
  - Created Django migration `0005_add_global_views_order.py`
  - **Any superuser can now reorder global views via drag-drop** (not just one designated admin)
  - **Removed `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID` environment variable** - no longer needed
  - Backend reads order from ApplicationConfiguration singleton instead of admin user's settings
  - **Drag-drop reordering implementation**:
    - Global views draggable in sidebar for superusers (when organizing mode active)
    - Global views draggable on dashboard for superusers
    - Personal views draggable for all users (unchanged)
    - Separate cdkDropList for global and personal views (prevents intermixing)
    - Auto-save on drop for immediate feedback
  - **UI improvements**:
    - Added "Personal Saved Views" heading on dashboard to separate view types
    - Removed "Save Global View Order" button from management page
    - Single Save button handles both global and personal view properties
    - Global views show drag handle only for superusers in organizing mode
  - **SettingsService enhancements**:
    - Added `updateGlobalSidebarViewsSort()` method
    - Added `updateGlobalDashboardViewsSort()` method
    - Both methods PATCH to ApplicationConfiguration API endpoint
  - Single canonical ordering shared by all users
  - Removed yellow warning message from saved views management page
  - Files modified:
    - Backend: `src/paperless/settings.py` (removed GLOBAL_VIEWS_ADMIN_USER_ID env var)
    - Backend: `src/paperless/models.py` (added JSONField columns)
    - Backend: `src/paperless/migrations/0005_add_global_views_order.py` (new migration)
    - Backend: `src/documents/views.py` (read from ApplicationConfiguration instead of user settings)
    - Frontend: `src-ui/src/app/services/settings.service.ts` (added update methods)
    - Frontend: `src-ui/src/app/components/app-frame/app-frame.component.ts` (drag-drop handlers)
    - Frontend: `src-ui/src/app/components/app-frame/app-frame.component.html` (draggable global views)
    - Frontend: `src-ui/src/app/components/dashboard/dashboard.component.ts` (drag-drop handlers, heading)
    - Frontend: `src-ui/src/app/components/dashboard/dashboard.component.html` (separate drop lists, heading)
    - Frontend: `src-ui/src/app/components/manage/saved-views/saved-views.component.ts` (removed ordering method)
    - Frontend: `src-ui/src/app/components/manage/saved-views/saved-views.component.html` (removed ordering button)
  - Architecture: Moved from per-superuser settings to singleton model for true system-wide state
  - User experience: Reordering done where views are displayed (sidebar/dashboard), not on management page
  - All changes properly marked with RKC comments following conventions

- **v1.0.10 (2025-12-09)**: Toggle switches for personal/global view conversion
  - Added toggle switches to convert views between personal (owner=user) and global (owner=NULL)
  - Prominently displayed in each view container on saved views management page
  - Toggle state automatically sets owner field when saving
  - No confirmation dialogs - clean UX with instant state changes
  - Views automatically migrate between sections after save and refresh
  - Works for both global and personal view sections
  - Only available to superusers (leverages existing permission system)
  - Files modified:
    - Frontend: `src-ui/src/app/components/manage/saved-views/saved-views.component.ts` (added isGlobal control, modified save logic)
    - Frontend: `src-ui/src/app/components/manage/saved-views/saved-views.component.html` (added toggle UI)

- **v1.0.9 (2025-12-09)**: Global saved views management UI implementation
  - Implemented complete UI-based management system for global saved views
  - Superusers can now edit global views directly through Settings > Saved Views page
  - Backend modified to allow superusers to update/delete global views (owner=NULL)
  - Frontend separated into "Global Shared Views" and "Personal Saved Views" sections
  - Added visual distinction with blue card, "GLOBAL" badges, and warning messages
  - Only designated admin (via `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`) can save ordering
  - Non-admin superusers can edit but see warning about ordering restrictions
  - Regular users see only personal views (global views hidden from management page)
  - Files modified:
    - Backend: `src/documents/views.py` (allow superuser modifications)
    - Frontend: `src-ui/src/app/data/ui-settings.ts` (added GLOBAL_VIEWS_ADMIN_USER_ID key)
    - Frontend: `src-ui/src/app/components/manage/saved-views/` (complete refactor)
  - All changes marked with RKC comments for maintainability

- **v1.0.8 (2025-12-08)**: PDF Editor restriction now optional via environment variable
  - Added `PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER` environment variable (default: false)
  - When disabled (default): App behaves like original Paperless-ngx - all users can access PDF editor
  - When enabled: PDF editor restricted to superusers only
  - Defense in depth: Both backend permission check and frontend UI hiding honor the setting
  - Updated backend: `src/paperless/settings.py`, `src/documents/views.py`
  - Updated frontend: `src-ui/src/app/data/ui-settings.ts`, component TypeScript and HTML
  - Allows flexible deployment without code changes

- **v1.0.7 (2025-12-08)**: PDF Editor ownership restriction fix
  - Fixed bug where superusers couldn't access PDF editor on documents they don't own
  - Removed `!userIsOwner` condition from PDF editor button's disabled check
  - Superusers can now edit ANY document's PDF, regardless of ownership
  - This aligns with the intended behavior: only superusers should have PDF editing rights
  - Updated frontend: `src-ui/src/app/components/document-detail/document-detail.component.html`
  - Added detailed code comments explaining the fix

- **v1.0.6 (2025-12-08)**: Global saved views ordering and management
  - Added `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID` environment variable
  - Global saved views (owner=NULL) now display in separate "Shortcuts" section at top of sidebar
  - Global views ordered by designated admin user's settings with alphabetic fallback
  - Global views are not draggable (only user's own views can be reordered)
  - Global views hidden from management page for non-admin users
  - Prevents confusion and accidental attempts to edit global views

- **v1.0.5 (2025-12-02)**: SSO UiSettings comprehensive fix
  - Fixed critical bug where new SSO users would get error on first login
  - Problem: When UiSettings is created, `settings` field defaults to NULL
  - Fixed in `IndexView.get_frontend_language()` and `UiSettingsView.get()` with proper exception handling
  - Added try/except blocks to catch `RelatedObjectDoesNotExist` exception
  - Added post_save signal to auto-create UiSettings for new users (in `documents/signals/handlers.py`)
  - Enhanced Django logging in settings.py with django.request logger for better debugging
  - Added root logger level to capture all debug messages properly

- **v1.0.4 (2025-12-02)**: SSO UiSettings bug fix (deprecated - see v1.0.5)
  - Fixed critical bug where new SSO users would get error on first login
  - Problem: When UiSettings is created, `settings` field defaults to NULL
  - Views were calling `.get()` on None, causing AttributeError
  - Fixed in `IndexView.get_frontend_language()` and `UiSettingsView.get()`
  - Added NULL checks before accessing `ui_settings.settings`

- **v1.0.3 (2025-12-02)**: Social account debug logging
  - Added `PAPERLESS_SOCIALACCOUNT_DEBUG` environment variable for troubleshooting SSO issues
  - Enables verbose django-allauth logging when set to true
  - Logs to both paperless.log file and console output
  - Includes debug logging in CustomSocialAccountAdapter.save_user method
  - Helps diagnose social account signup and authentication problems

- **v1.0.2 (2025-12-01)**: Default language environment variable
  - Added `PAPERLESS_UI_DEFAULT_LANGUAGE` for custom default UI language
  - Renamed environment variables to use `PAPERLESS_UI_` prefix for consistency
  - All three UI defaults work as fallbacks without overriding user preferences
  
- **v1.0.1 (2025-12-01)**: Environment variable customizations
  - Added `PAPERLESS_UI_THEME_COLOR` for custom default theme color
  - Added `PAPERLESS_UI_DARK_MODE_THUMB_INVERTED` for dark mode thumbnail inversion default
  - Both work as fallbacks - don't override existing user preferences
  
- **v1.0.0 (2025-12-01)**: Initial RKC customizations
  - PDF editor superuser restriction (backend + frontend)
  - Shared saved views with NULL owner support
  - Defense-in-depth security implementation
  - Comprehensive documentation

## Related Documentation

- [Paperless-ngx Official Docs](https://docs.paperless-ngx.com/)
- [Paperless-ngx API Documentation](https://docs.paperless-ngx.com/api/)
- [Django Permissions](https://docs.djangoproject.com/en/stable/topics/auth/)
- [Angular Component Permissions](https://angular.io/guide/component-overview)

---

*This documentation should be updated whenever new RKC customizations are added or existing ones are modified.*
