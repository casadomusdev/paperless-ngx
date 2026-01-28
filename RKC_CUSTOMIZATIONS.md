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

### UI Enhancements
- **[Custom Field Filter Buttons](#6-custom-field-filter-buttons)** - Quick filter buttons for custom field values on document detail page, enabling instant filtering by any custom field value with support for all data types including null/empty values.
  - Frontend: `src-ui/src/app/components/document-detail/` (TypeScript & HTML)
  - Translations: `src-ui/src/locale/messages.en_US.xlf`, `messages.de_DE.xlf`

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

### 5. SSO Debug Logging
**Purpose**: Enable detailed debug logging for django-allauth SSO troubleshooting without full DEBUG mode

Documented in [Environment Variables](#6-sso-debug-logging-paperless_debug_sso) section.

### 6. Custom Field Filter Buttons
**Purpose**: Enable quick filtering of documents by custom field values directly from the document detail page

**Files Modified**:
- `src-ui/src/app/components/document-detail/document-detail.component.ts` - Filter method implementation
- `src-ui/src/app/components/document-detail/document-detail.component.html` - Filter button integration for all custom field types
- `src-ui/src/app/components/common/input/text/text.component.ts` - Added filter support
- `src-ui/src/app/components/common/input/text/text.component.html` - Filter button UI
- `src-ui/src/app/components/common/input/number/number.component.ts` - Added filter support
- `src-ui/src/app/components/common/input/number/number.component.html` - Filter button UI
- `src-ui/src/app/components/common/input/monetary/monetary.component.ts` - Added filter support
- `src-ui/src/app/components/common/input/monetary/monetary.component.html` - Filter button UI
- `src-ui/src/app/components/common/input/check/check.component.ts` - Added filter support
- `src-ui/src/app/components/common/input/check/check.component.html` - Filter button UI
- `src-ui/src/app/components/common/input/url/url.component.ts` - Added filter support
- `src-ui/src/app/components/common/input/url/url.component.html` - Filter button UI
- `src-ui/src/app/components/common/input/document-link/document-link.component.ts` - Added filter support
- `src-ui/src/app/components/common/input/document-link/document-link.component.html` - Filter button UI
- `src-ui/src/app/components/common/input/textarea/textarea.component.ts` - Added filter support
- `src-ui/src/app/components/common/input/textarea/textarea.component.html` - Filter button UI
- `src-ui/src/locale/messages.en_US.xlf` - English translation
- `src-ui/src/locale/messages.de_DE.xlf` - German translation

**Key Features**:

1. **Universal Custom Field Support**:
   - Works with all 10 custom field data types: String, Date, Integer, Float, Monetary, Boolean, Url, DocumentLink, Select, LongText
   - Filter buttons appear for ALL fields, even when value is null/empty
   - Consistent with existing filter buttons (correspondent, document type, etc.)

2. **Filter Mechanism**:
   - Uses `FILTER_CUSTOM_FIELDS_QUERY` filter type (ID 42) from existing Paperless filter infrastructure
   - Query format: `JSON.stringify(["FieldName", "exact", "value"])`
   - Null/empty values converted to empty string for filtering
   - Navigation via `DocumentListViewService.quickFilter()`

3. **User Experience**:
   - Filter icon button displayed to the right of each custom field value
   - Tooltip on hover: "Filter documents with this custom field value" (EN) / "Dokumente mit diesem benutzerdefinierten Feldwert filtern" (DE)
   - Single click navigates to document list with filter applied
   - Works identically to other metadata filter buttons

**Implementation**:

**TypeScript Method** (`document-detail.component.ts`):
```typescript
// RKC: Filter documents by custom field value
filterByCustomField(fieldInstance: CustomFieldInstance) {
  const field = this.getCustomFieldFromInstance(fieldInstance)
  if (!field) return
  
  const queryValue = JSON.stringify([
    field.name,
    'exact',
    fieldInstance.value?.toString() ?? '',
  ])
  
  const filterRule: FilterRule = {
    rule_type: FILTER_CUSTOM_FIELDS_QUERY,
    value: queryValue,
  }
  
  this.documentListViewService.quickFilter([filterRule])
}
// /end RKC edit
```

**Template Integration** (`document-detail.component.html`):
All 10 custom field input components enhanced with:
```html
[showFilter]="true" 
(filterDocuments)="filterByCustomField(fieldInstance)"
```

Applied to:
- `app-input-text` (String)
- `app-input-date` (Date)
- `app-input-number` (Integer, Float, Monetary)
- `app-input-switch` (Boolean)
- `app-input-url` (Url)
- `app-input-document-link` (DocumentLink)
- `app-input-select` (Select)
- `app-input-longtext` (LongText)

**Translation Integration**:
Text-based translation ID to avoid numeric ID collisions:
```xml
<trans-unit id="rkc-custom-field-filter-tooltip">
  <source>Filter documents with this custom field value</source>
  <target>Filter documents with this custom field value</target>
</trans-unit>
```

**Use Cases**:
- User viewing invoice finds "Project: ABC-123" custom field → clicks filter → sees all invoices for that project
- Reviewer sees "Status: Approved" on document → clicks filter → sees all approved documents
- Accountant viewing document with "Fiscal Year: 2024" → clicks filter → finds all 2024 fiscal documents
- User sees document with empty "Department" field → clicks filter → finds all documents without department assignment
- Works with any custom field configuration without code changes

**Benefits**:
- Rapid document discovery based on custom metadata
- Consistent UX with existing Paperless filter buttons
- No configuration required - automatically works with all custom fields
- Supports all custom field data types including null/empty values
- Integrates seamlessly with existing filter infrastructure
- All changes properly marked with RKC comments for easy maintenance

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

### 7. Mail Correspondent Matching Algorithm (`PAPERLESS_MAIL_CORRESPONDENT_MATCHING_ALGORITHM`)
**Purpose**: Control what matching algorithm is used when creating new correspondents from mail rules

**Type**: Integer (MatchingModel algorithm value)
**Default**: `6` (MATCH_AUTO - Automatic matching)
**Example**: `PAPERLESS_MAIL_CORRESPONDENT_MATCHING_ALGORITHM=1`

**Behavior**:
- Sets the `matching_algorithm` field for correspondents created by mail rules
- Defaults to MATCH_AUTO (6) to match UI behavior where manually-created correspondents use "Automatic" by default
- Without this setting, mail-created correspondents would use model default (MATCH_ANY = 1 "Any word")
- User can still manually change the matching algorithm for any correspondent in the UI

**Available Algorithm Values**:
- `0` - MATCH_NONE: No matching (disabled)
- `1` - MATCH_ANY: Any word
- `2` - MATCH_ALL: All words
- `3` - MATCH_LITERAL: Exact match
- `4` - MATCH_REGEX: Regular expression
- `5` - MATCH_FUZZY: Fuzzy matching
- `6` - MATCH_AUTO: Automatic (default - recommended)

**Use Cases**:
- Organizations wanting consistent matching behavior between UI-created and mail-created correspondents
- Ensuring mail automation uses intelligent "Automatic" matching by default
- Customizing matching strictness for specific deployment needs

**Why This Matters**:
- **Problem**: Originally, `_correspondent_from_name()` didn't specify `matching_algorithm`, so new correspondents got the Django model default (MATCH_ANY = 1)
- **UI Inconsistency**: When users manually create correspondents in the UI, they get MATCH_AUTO (6) by default
- **Result**: Mail-created vs UI-created correspondents behaved differently during document matching
- **Solution**: This environment variable makes mail-created correspondents use MATCH_AUTO (6) by default, matching UI behavior

**Implementation**:
- Backend: `src/paperless/settings.py` - Reads `PAPERLESS_MAIL_CORRESPONDENT_MATCHING_ALGORITHM` env var with default value 6
- Backend: `src/paperless_mail/mail.py` - `_correspondent_from_name()` includes `matching_algorithm` in defaults dict
- Uses `settings.MAIL_CORRESPONDENT_MATCHING_ALG` when creating new correspondents

## Version History

- **v1.1.1 (2026-01-28)**: Mail Account List View Enhancements
  - Added visual indicators for which account is configured for email sending
  - Enhanced mail accounts list with send-fill icon badge and tooltip for sending account
  - Added info message when SMTP is configured via environment variables
  - **Problem**: Users couldn't easily identify which mail account was configured for sending emails
  - **Solution**: 
    - Added `smtp_env_configured` flag to backend ui_settings (uses existing `EMAIL_ENABLED` setting)
    - Created conditional info alert that displays when env vars configured but no account-based sending enabled
    - Added send-fill icon badge with tooltip next to account name when `use_for_sending=true`
    - Badge shows "This account is used for sending emails" tooltip on hover
  - **Info Message Display Logic**:
    - Only shows when `smtpEnvConfigured=true` AND `hasSendingAccount()=false`
    - Message: "ℹ️ Mail sending is configured via environment variables. To override these environment variables, enable 'Use for sending' for any of the accounts set up here."
    - Disappears automatically when user enables sending on any account
  - **Visual Elements**:
    - Uses `send-fill` icon from ngx-bootstrap-icons (matches v1.1.0 edit dialog)
    - Icon displays inline after account type badge (IMAP/Gmail/Outlook)
    - Tooltip integration via NgbTooltipModule with top placement
    - Consistent styling with existing account list badges
  - **Backend Changes**:
    - Added `smtp_env_configured` to ui_settings dict in `UiSettingsView`
    - Value sourced from `settings.EMAIL_ENABLED` (traditional SMTP configuration)
    - Allows frontend to differentiate between env var and account-based sending config
  - **Frontend Changes**:
    - Added `SMTP_ENV_CONFIGURED` key to SETTINGS_KEYS enum
    - Added corresponding UiSetting entry with boolean type, default false
    - Added `smtpEnvConfigured` getter to MailComponent reading from SettingsService
    - Added `hasSendingAccount()` method checking if any account has `use_for_sending=true`
    - Imported NgbTooltipModule for tooltip functionality
    - Added conditional info alert in template above mail accounts section
    - Added send-fill icon with ngbTooltip directive inline with account names
  - **Use Cases**:
    - Admin can quickly see which account handles outgoing email
    - Users understand relationship between env var config and account-based config
    - Clear visual feedback when migrating from env vars to account-based sending
    - Tooltip provides additional context without cluttering the interface
  - **Benefits**:
    - Improved discoverability of sending account configuration
    - Clear indication when environment variable fallback is active
    - Consistent icon usage across edit dialog and list view
    - Non-intrusive UI enhancement that complements existing v1.1.0 functionality
    - Helps users understand the configuration hierarchy (env vars vs accounts)
  - Files modified:
    - Backend: `src/documents/views.py` (added smtp_env_configured to ui_settings, properly marked in existing RKC section)
    - Frontend: `src-ui/src/app/data/ui-settings.ts` (added SMTP_ENV_CONFIGURED key and setting)
    - Frontend: `src-ui/src/app/components/manage/mail/mail.component.ts` (added smtpEnvConfigured getter, hasSendingAccount method, NgbTooltipModule import)
    - Frontend: `src-ui/src/app/components/manage/mail/mail.component.html` (added info alert and send-fill icon badge)
  - All changes properly marked with RKC comments for maintainability
  - **Architecture**: Minimal core code impact - leverages existing settings infrastructure and tooltip components

- **v1.1.0 (2026-01-28)**: SMTP Email Sending via Mail Accounts
  - Refactored OAuth2-specific email sending (v1.0.18) into general SMTP sending feature
  - **Problem**: v1.0.18 only supported OAuth2, had hardcoded SMTP settings, no enforcement of "only one sending account"
  - **Solution**: 
    - Extended MailAccount model with comprehensive SMTP configuration fields
    - Support for both OAuth2 XOAUTH2 and traditional username/password SMTP authentication
    - Automatic enforcement: only one account can be enabled for sending at a time
    - Flexible SMTP server configuration for all account types
    - Clean UI separation between IMAP (receiving) and SMTP (sending)
    - Environment variables remain as fallback when no mail account configured
  - **New MailAccount Fields**:
    - `smtp_server` - SMTP server hostname (optional, uses defaults for Gmail/Outlook OAuth)
    - `smtp_port` - SMTP port (587 for STARTTLS, 465 for SSL, 25 for unencrypted)
    - `smtp_security` - Security protocol: SSL, STARTTLS, or NONE
    - `smtp_username` - SMTP username for traditional auth (optional, falls back to IMAP username)
    - `smtp_password` - SMTP password for traditional auth (optional, falls back to IMAP password)
    - `sending_account_info` - Read-only API field showing if account replaced another as sending account
  - **Backend Changes**:
    - Refactored `OAuth2EmailBackend` → `MailAccountEmailBackend`
    - Supports both OAuth2 XOAUTH2 (via `_open_oauth()`) and traditional auth (via `_open_traditional()`)
    - Updated `MailAccount.save()` to auto-disable other sending accounts
    - Updated `MailAccount.clean()` to validate SMTP config for traditional accounts
    - Updated `MailAccount._set_default_smtp_config()` to set Gmail/Outlook defaults
    - Updated `get_sending_mail_account()` to return ANY account type (not just OAuth)
    - Updated `send_email()` in documents/mail.py to use new unified backend
    - Updated serializers with new fields and obfuscated password handling
  - **Frontend Changes**:
    - Reorganized mail account edit dialog into "Receiving (IMAP)" and "Sending (SMTP)" sections
    - Added SMTP configuration fields with conditional display based on account type
    - OAuth accounts show info box explaining XOAUTH2 usage
    - Traditional accounts show SMTP username/password fields
    - Added warning dialog when changing sending account
    - Added `onSendingToggle()` to populate default SMTP settings
    - Added `isTraditionalAccount` getter to conditionally show/hide fields
  - **Migration**: 0031_add_smtp_fields.py
    - Adds new SMTP fields to MailAccount model
    - Updates help text for use_for_sending field
    - Backward compatible: existing v1.0.18 accounts continue working
  - **Use Cases**:
    - Organizations using OAuth2 (Gmail/Outlook) for mail retrieval AND sending
    - Organizations using traditional SMTP with username/password
    - Mixed environments with both OAuth2 and traditional accounts
    - Custom SMTP servers with non-standard ports/security
  - **Benefits**:
    - Single interface for all SMTP authentication methods
    - No need for separate environment variables for email sending
    - Clear UI guidance for configuring different account types
    - Automatic defaults reduce configuration burden
    - Environment variables still work as fallback for security-conscious deployments
  - Files modified:
    - Backend: `src/paperless_mail/models.py` (fields, validation, enforcement)
    - Backend: `src/paperless_mail/migrations/0031_add_smtp_fields.py` (NEW)
    - Backend: `src/paperless_mail/mail_oauth.py` (unified backend)
    - Backend: `src/paperless_mail/serialisers.py` (API fields)
    - Backend: `src/documents/mail.py` (uses new backend)
    - Frontend: `src-ui/src/app/data/mail-account.ts` (TypeScript interface)
    - Frontend: `src-ui/src/app/components/common/edit-dialog/mail-account-edit-dialog/` (UI refactor)
  - All changes properly marked with RKC comments for maintainability
  - **Architecture**: Clean separation of concerns - OAuth2 vs traditional handled transparently

- **v1.0.29 (2025-12-16)**: Saved views unsaved changes warning default
  - Added environment variable to control default value of "Show warning when closing saved views with unsaved changes" option
  - **Problem**: Organizations have different policies around accidental data loss - some want warnings enabled by default, others prefer streamlined workflow without warnings
  - **Solution**: 
    - Added `PAPERLESS_SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE_DEFAULT` environment variable (default: true)
    - Acts as org-wide default without overriding existing user preferences
    - Users can still toggle the setting in Settings > Saved Views
    - Maintains current Paperless-ngx behavior when not configured (warning enabled)
  - **Environment Variable**: `PAPERLESS_SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE_DEFAULT`
    - **Type**: Boolean
    - **Default**: `true` (maintains current Paperless-ngx behavior - warnings enabled)
    - **Example**: `PAPERLESS_SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE_DEFAULT=false`
  - **Behavior**:
    - When `true` (default): New users and users without preference see warning when closing unsaved views
    - When `false`: New users and users without preference don't see warnings (streamlined workflow)
    - Existing user preferences always take priority
    - Only acts as fallback when user has not explicitly set their preference
  - **Implementation Pattern**: Follows exact same pattern as v1.0.1 and v1.0.2 customizations
    - Backend reads environment variable and exposes to frontend via UiSettingsView
    - Frontend uses as fallback in settings.service.ts get() method
    - User preference checked first, env default used only when undefined
    - No database changes required - pure runtime fallback logic
  - **Use Cases**:
    - Power user organizations: Disable warnings for experienced users who rarely make mistakes
    - Training environments: Enable warnings to prevent accidental data loss during onboarding
    - Mixed deployments: Different defaults per environment (production vs. staging)
    - Policy compliance: Organization-wide defaults without restricting user choice
  - **Benefits**:
    - Clean separation between org policy (env var) and user preference (db setting)
    - Zero impact on existing user configurations
    - No migrations needed - works immediately after restart
    - Follows established RKC customization pattern for consistency
    - User autonomy preserved - can override at any time
  - Files modified:
    - Backend: `src/paperless/settings.py` (added SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE_DEFAULT env var with default true)
    - Backend: `src/documents/views.py` (exposed setting to frontend via UiSettingsView)
    - Frontend: `src-ui/src/app/data/ui-settings.ts` (added SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE_DEFAULT key and boolean setting)
    - Frontend: `src-ui/src/app/services/settings.service.ts` (added fallback logic in get() method)
  - All changes properly marked with RKC comments for maintainability

- **v1.0.28 (2025-12-16)**: Mail correspondent matching algorithm fix
  - Fixed inconsistency where mail-created correspondents used different matching algorithm than UI-created correspondents
  - **Problem**: 
    - Mail-created correspondents (from any mode: FROM_EMAIL, FROM_NAME, FROM_SMART) were using Django model default (MATCH_ANY = 1 "Any word")
    - UI-created correspondents use MATCH_AUTO (6 "Automatic") by default
    - This caused inconsistent matching behavior between mail-created and manually-created correspondents
  - **Solution - Backend**:
    - Added `PAPERLESS_MAIL_CORRESPONDENT_MATCHING_ALGORITHM` environment variable (default: 6)
    - Updated `_correspondent_from_name()` method to include `matching_algorithm` in defaults dict
    - Uses `settings.MAIL_CORRESPONDENT_MATCHING_ALG` when creating new correspondents via mail rules
  - **Solution - Frontend**:
    - Exposed `mail_correspondent_matching_algorithm` setting to frontend via UiSettingsView
    - Updated correspondent edit dialog to read default from settings instead of hardcoded constant
    - UI now respects environment variable when creating correspondents manually
  - **Impact**:
    - Applies to ALL correspondent creation: mail rules AND manual UI creation
    - Both backend and frontend use same configurable default
    - Only affects newly created correspondents - existing ones unchanged
    - Default behavior is MATCH_AUTO (6 "Automatic") matching UI expectation
    - Customizable via environment variable if different algorithm needed
  - **Benefits**:
    - Complete consistency across all correspondent creation methods (mail rules, UI)
    - Eliminates confusion from different default behaviors
    - Single environment variable controls both backend and frontend defaults
    - Configurable for organizations with specific matching requirements
  - Files modified:
    - Backend: `src/paperless/settings.py` (added environment variable with default value 6)
    - Backend: `src/paperless_mail/mail.py` (updated `_correspondent_from_name()` method)
    - Backend: `src/documents/views.py` (exposed setting to frontend via UiSettingsView)
    - Frontend: `src-ui/src/app/data/ui-settings.ts` (added MAIL_CORRESPONDENT_MATCHING_ALG key)
    - Frontend: `src-ui/src/app/components/common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component.ts` (read from settings)
  - All changes properly marked with RKC comments for maintainability

- **v1.0.27 (2025-12-16)**: Smart correspondent matching for mail rules
  - Added intelligent correspondent matching based on email addresses to solve sender name change issues
  - **Problem**: Existing correspondent assignment modes break when sender changes display name or creates ugly correspondent names
    - `FROM_EMAIL` mode creates ugly correspondents like "accounts@company.com"
    - `FROM_NAME` mode breaks when sender changes their display name (e.g., "John Smith" → "John S.")
    - Neither approach provides stable+readable correspondent names
  - **Solution - Part 1: Smart Correspondent Creation**:
    - Added `FROM_SMART` mode (value 5) to CorrespondentSource enum
    - Creates correspondents in RFC 5322 format: `"Sender Name <sender@email.com>"`
    - Clean readable names with stable email address embedded
    - Example: `"John Smith <john@company.com>"`
  - **Solution - Part 2: Partial Email Matching**:
    - Intelligent three-tier matching strategy when assigning correspondents:
      1. **Exact match**: Try to find correspondent with exact name match
      2. **Email extraction match**: Extract email from angle brackets `<email>` and compare
      3. **Create new**: If no match, create new correspondent in smart format
  - **Smart Matching Examples**:
    - Existing: `"Accounts <accounts@company.com>"` + Incoming: `"John <accounts@company.com>"` = Match (email matches)
    - Admin renames to: `"Company.com Accounts <accounts@company.com>"` + Next mail: `"Jane <accounts@company.com>"` = Still matches
    - Incoming: `"New Sender <new@example.com>"` = Creates new correspondent `"New Sender <new@example.com>"`
  - **Implementation**:
    - Backend: Added `FROM_SMART` to `MailRule.CorrespondentSource` enum
    - Backend: Added `_extract_email_from_correspondent_name()` helper using regex
    - Backend: Added `_get_or_create_correspondent_smart()` matching method
    - Backend: Updated `_get_correspondent()` to handle FROM_SMART mode
    - Frontend: Added `FromSmart = 5` to `MailMetadataCorrespondentOption` enum
    - Frontend: Added option to `METADATA_CORRESPONDENT_OPTIONS` array in mail rule edit dialog
    - Translations: Automatically generated from Django backend strings
  - **Benefits**:
    - **Readable**: Human-friendly names in UI (`"John Smith <john@company.com>"`)
    - **Stable**: Email-based matching survives name changes
    - **Flexible**: Admins can rename correspondents without breaking automation
    - **Backward Compatible**: Existing rules continue working unchanged
    - **Case Insensitive**: Email matching ignores case differences
  - **Use Cases**:
    - Shared department emails: `"Accounts <accounts@company.com>"` matches all senders from that address
    - Dynamic sender names: Email address provides stable identifier across name changes
    - Multi-user shared mailboxes: Different people sending from same address matched to same correspondent
    - Renamed correspondents: Organization renames still work via email extraction
  - **Database Impact**: No migrations needed - IntegerChoices enum values are application-level only
  - Files modified:
    - Backend: `src/paperless_mail/models.py` (added FROM_SMART enum value)
    - Backend: `src/paperless_mail/mail.py` (added helper methods and matching logic)
    - Frontend: `src-ui/src/app/data/mail-rule.ts` (added FromSmart enum value)
  - All changes properly marked with RKC comments for maintainability
  - **Note**: This is Part 1 of intelligent correspondent matching - creates foundation for future enhancements

- **v1.0.26 (2025-12-15)**: Email metadata custom fields
  - Expanded mail UID correlation (v1.0.12) to capture comprehensive email metadata as custom fields
  - **Problem**: Only IMAP UID was being saved, limiting searchability and context for email-sourced documents
  - **Solution**: 
    - Added 4 new metadata fields: Mail From, Mail Sender, Mail Subject, Mail Date
    - All 5 fields (including Mail UID) now automatically captured when document consumed from email
    - Each field name configurable via environment variable for multilingual support
    - Mail Date stored as DATE type custom field (YYYY-MM-DD format)
  - **Metadata Fields Captured**:
    - **Mail UID**: IMAP unique identifier (existing from v1.0.12)
    - **Mail From**: Sender's email address (e.g., "john@company.com")
    - **Mail Sender**: Sender's display name (e.g., "John Smith")
    - **Mail Subject**: Email subject line
    - **Mail Date**: Email received date in YYYY-MM-DD format (DATE custom field type)
  - **Environment Variables**:
    - `PAPERLESS_MAIL_UID_FIELD` (default: "Mail UID") - IMAP UID field name
    - `PAPERLESS_MAIL_FROM_FIELD` (default: "Mail From") - Sender email address field name
    - `PAPERLESS_MAIL_SENDER_FIELD` (default: "Mail Sender") - Sender display name field name
    - `PAPERLESS_MAIL_SUBJECT_FIELD` (default: "Mail Subject") - Subject line field name
    - `PAPERLESS_MAIL_DATE_FIELD` (default: "Mail Date") - Received date field name
  - **Implementation**:
    - Extended `ConsumableDocument` dataclass with 4 new optional fields: mail_from, mail_sender, mail_subject, mail_date
    - Updated mail.py to extract metadata from imap_tools MailMessage (from_values.email, from_values.name, subject, date)
    - Refactored consumer helper from `_attach_mail_uid_custom_field()` to `_attach_mail_metadata_custom_fields()`
    - Helper creates CustomField definitions on first run, then CustomFieldInstance for each document
    - Uses value_text for STRING fields (UID, From, Sender, Subject) and value_date for DATE field
    - Non-critical enhancement: failures log warnings without aborting document consumption
  - **Data Flow**:
    - Mail retrieval: imap_tools extracts metadata → passed to ConsumableDocument
    - Document consumption: consumer.py creates custom field definitions and instances
    - All 5 fields stored as separate custom fields on document
    - Fields appear in document detail view and can be searched/filtered
  - **Use Cases**:
    - Search all documents from specific sender email address
    - Find documents by sender name (handles display name changes)
    - Filter documents by email subject keywords
    - Find documents received on specific dates
    - Correlate documents with original emails via UID
  - **Benefits**:
    - Rich metadata preservation without database schema changes
    - Configurable field names support multilingual deployments
    - Works with existing custom field search and filter infrastructure
    - Clean separation: v1.0.26 captures metadata, v1.0.27 will add smart correspondent matching
    - Minimal performance impact - fields created once, reused for all documents
  - Files modified:
    - Backend: `src/paperless/settings.py` (added 5 environment variables with defaults)
    - Backend: `src/documents/data_models.py` (added 4 new fields to ConsumableDocument)
    - Backend: `src/paperless_mail/mail.py` (extract and pass metadata in _process_attachments and _process_eml)
    - Backend: `src/documents/consumer.py` (refactored helper function to handle all 5 fields)
  - All changes properly marked with RKC comments for maintainability
  - **Note**: Mail To field intentionally excluded - separate mail rules per account handle recipient targeting

- **v1.0.25 (2025-12-12)**: Custom field names and filter buttons in card views
  - Enhanced document card views (small and large) with optional field name display and quick filter buttons
  - **Problem**: Card views only showed custom field values without context, no way to quickly filter by field value
  - **Solution**: 
    - Added optional field name display in "FieldName: Value" format with environment variable control
    - Added filter buttons to all custom field types in card views matching document detail page functionality
    - Filter buttons aligned right with funnel icon, same as other metadata filter buttons
  - **Environment Variable**: `PAPERLESS_SHOW_CUSTOM_FIELD_NAMES_IN_CARDS` (default: NO)
    - When disabled (default): Shows only values for compact display (original behavior)
    - When enabled: Shows "FieldName: Value" format for better context
    - Boolean field always shows name (unchanged from original)
  - **Filter Button Features**:
    - Appears for ALL custom field types including null/empty values
    - Tooltip: "Show all with this value" (EN) / "Alle mit diesem Wert anzeigen" (DE)
    - Uses FILTER_CUSTOM_FIELDS_QUERY filter type (ID 42) same as document detail page
    - Single click navigates to document list with filter applied
    - Works with all 10 field types: String, Date, Integer, Float, Monetary, Boolean, Url, DocumentLink, Select, LongText
  - **Implementation**:
    - Created reusable `custom-field-display` component with inputs for custom field instances
    - Component accepts `showFilter` input and emits `filterClick` event
    - Both card components implement `filterByCustomField()` handler method
    - Field name display controlled by `showFieldName` getter reading from settings service
    - Filter buttons use same query format as document detail filters for consistency
  - **User Experience**:
    - Compact default display (values only) reduces clutter in card views
    - Opt-in field name display via environment variable for those who need context
    - Quick one-click filtering matches workflow of correspondent/type/tag filter buttons
    - Works identically across small cards, large cards, and document detail page
  - **Benefits**:
    - Rapid document discovery based on custom field values in card views
    - Consistent UX with existing Paperless filter buttons
    - Optional field names prevent UI clutter while providing context when needed
    - No configuration required - automatically works with all custom fields
    - Environment variable allows org-level policy without user-level settings
  - Files modified:
    - Backend: `src/paperless/settings.py` (added SHOW_CUSTOM_FIELD_NAMES_IN_CARDS env var)
    - Backend: `src/documents/views.py` (exposed setting to frontend)
    - Frontend: `src-ui/src/app/data/ui-settings.ts` (added settings key)
    - Frontend: `src-ui/src/app/components/common/custom-field-display/custom-field-display.component.ts` (inputs, outputs, logic)
    - Frontend: `src-ui/src/app/components/common/custom-field-display/custom-field-display.component.html` (field names, filter buttons)
    - Frontend: `src-ui/src/app/components/document-list/document-card-small/` (filter handler and template)
    - Frontend: `src-ui/src/app/components/document-list/document-card-large/` (filter handler and template)
    - Translations: `src-ui/src/locale/messages.en_US.xlf` (tooltip translation)
    - Translations: `src-ui/src/locale/messages.de_DE.xlf` (tooltip translation)
  - All changes properly marked with RKC comments for maintainability

- **v1.0.24 (2025-12-12)**: Processed mail "select all in database" with selection count
  - Added ability to select and delete all processed mail entries matching current filter criteria
  - Displays selection count in UI to show how many items are currently selected
  - **User Experience**:
    - Check header checkbox → selects current page items (max 50)
    - Banner appears: "X items selected. Select all Y items?" (with filter context if active)
    - Click "Select all Y items" → enables database-wide selection
    - Shows "All Y items are selected" with clear selection link
    - Delete button shows count: "Delete N" with badge
    - Confirmation dialog with exact count and filter context
  - **Frontend Changes**:
    - Added `selectAllInDatabase` boolean flag to track selection mode
    - Added `selectedCount` getter: returns either selectedMailIds.size or collectionSize
    - Added `selectAllInDb()` method to enable database-wide selection
    - Added selection banner component (info alert when page selected, primary when all selected)
    - Enhanced `deleteSelected()` with confirmation dialog showing count and filter context
    - Updated button toolbar to display selection count in badges
    - Modified `toggleAll()` and `clearSelection()` to reset selectAllInDatabase flag
  - **Backend Changes**:
    - Enhanced `bulk_delete` endpoint to accept `delete_all` parameter
    - Filter-based deletion using same criteria as list view (rule, filter_field, filter_text)
    - Supports all filter fields: error, subject, received, processed, uid
    - Permission checking before deletion for security
    - Returns deleted count for user feedback
  - **Service Layer**:
    - Added `bulk_delete_filtered()` method to ProcessedMailService
    - Sends delete_all: true with rule, filter_field, and filter_text parameters
  - **Filter Context**:
    - "Select all" applies only to currently filtered results
    - Clear indication in banners and confirmation dialogs when filter is active
    - Example: "Delete 89 processed mail entries matching filter 'timeout'?"
    - Without filter: "Delete 347 processed mail entries matching current view?"
  - **Benefits**:
    - Enables bulk cleanup of mail processing errors or specific subsets
    - Clear visual feedback at every step with counts
    - Safe operation with confirmation dialogs
    - Works seamlessly with existing server-side filtering (v1.0.16)
    - Gmail/Google Drive-style UX pattern familiar to users
  - Files modified:
    - Backend: `src/paperless_mail/views.py` (enhanced bulk_delete method)
    - Frontend: `src-ui/src/app/services/rest/processed-mail.service.ts` (added bulk_delete_filtered)
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.ts` (selection logic)
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.html` (selection UI)
  - All changes properly marked with RKC comments for maintainability

- **v1.0.23 (2025-01-12)**: Dashboard saved views race condition fix (signal-based reactivity)
  - Fixed race condition where dashboard would appear empty when directly accessing `/dashboard` URL
  - **Root Cause**: Computed signals were reading from non-reactive getters that returned data from plain arrays. When HTTP response populated the array, computed signals didn't know to recalculate.
  - **Solution**: Converted SavedViewService to use Angular signals for proper reactive data flow
    - Changed `savedViews` array → `savedViewsSignal` signal
    - Converted `sidebarViews` getter → computed signal
    - Converted `dashboardViews` getter → computed signal
    - Updated all consuming components to call signals as functions
  - **Reactive Chain**: HTTP response updates `savedViewsSignal` → triggers `dashboardViews` computed → triggers `globalDashboardViews` computed → UI updates automatically
  - **Benefits**:
    - Dashboard views load correctly on page refresh and direct URL access
    - Proper Angular reactivity pattern eliminates race conditions
    - Works reliably for both SPA navigation and direct page loads
    - Clean, maintainable solution following Angular best practices
  - Files modified:
    - Frontend: `src-ui/src/app/services/rest/saved-view.service.ts` (signal conversion)
    - Frontend: `src-ui/src/app/components/dashboard/dashboard.component.ts` (function call updates)
    - Frontend: `src-ui/src/app/components/app-frame/app-frame.component.ts` (function call updates)
  - All changes properly marked with RKC comments for maintainability

- **v1.0.22 (2025-01-12)**: Card views respect user date format preference (Paperless bug fix)
  - Fixed bug where small cards and large cards views ignored the user's date format setting
  - **Problem**: Card views hardcoded `'mediumDate'` format, completely ignoring the DATE_FORMAT setting from Settings > General
  - **Root Cause**: Template files explicitly passed `'mediumDate'` parameter to customDate pipe, overriding user preference
  - **Solution**: 
    - Removed hardcoded format parameter from both card view templates
    - Now respects user's date format preference just like table view does
    - Enables date+time formats (from v1.0.21) to work in card views
  - **Impact**:
    - Small cards and large cards now use same format as table view
    - User can select date+time formats and see actual timestamps in card views
    - `added` and `modified` fields will show real time data when using time formats
    - `created` field shows 00:00:00 because it's a DATE field (no time component in database)
  - **Files Modified**:
    - Frontend: `src-ui/src/app/components/document-list/document-card-small/document-card-small.component.html`
    - Frontend: `src-ui/src/app/components/document-list/document-card-large/document-card-large.component.html`
  - **User Experience**:
    - Consistent date formatting across all three view modes (table, small cards, large cards)
    - Date+time formats now work properly in card views
    - To see actual timestamps, users should display "Added" field instead of "Created" field
  - All changes properly marked with RKC comments for maintainability
  - This is a Paperless-ngx bug fix, not an RKC enhancement

- **v1.0.21 (2025-01-12)**: Date+time format options for user preferences
  - Added 4 new date format options that include time display in addition to date
  - **Problem**: Users could only select date-only formats (shortDate, mediumDate, longDate) with no way to see timestamps
  - **Solution**: 
    - Added 4 new format options leveraging Angular's built-in DatePipe time formats
    - No backend changes needed - DatePipe natively supports these formats
    - Formats: `short`, `medium`, `long`, `full` (vs. existing `shortDate`, `mediumDate`, `longDate`)
  - **New Format Options**:
    - **Short with time**: `1/12/25, 3:50 PM` - Compact format with hours:minutes
    - **Medium with time**: `Jan 12, 2025, 3:50:36 PM` - Balanced format with hours:minutes:seconds
    - **Long with time**: Full date with timezone (e.g., `January 12, 2025 at 3:50:36 PM GMT+1`)
    - **Full with time**: Complete format with day of week and full timezone
  - **User Experience**:
    - Options appear in Settings > General > Date display > Date format section
    - Live preview shows actual formatted date+time for each option
    - Compatible with all locale settings (uses user's selected language)
    - Setting stored per-user in ui_settings (key: `general-settings:date-display:date-format`)
  - **Implementation**:
    - Leverages existing customDate pipe infrastructure
    - No changes to pipe logic - simply passes new format strings to Angular's DatePipe
    - Maintains backward compatibility with existing date-only formats
    - All text properly internationalized with i18n support
  - **Benefits**:
    - Users can see precise timestamps on documents for time-sensitive workflows
    - Minimal code impact - extends existing dropdown with 4 new options
    - No performance overhead - uses native Angular functionality
    - Consistent with Angular framework patterns
  - Files modified:
    - Frontend: `src-ui/src/app/components/admin/settings/settings.component.html` (added 4 radio button options)
    - Frontend: `src-ui/src/locale/messages.en_US.xlf` (added 4 English translation entries)
    - Frontend: `src-ui/src/locale/messages.de_DE.xlf` (added 4 German translation entries)
  - All changes properly marked with RKC comments for maintainability

- **v1.0.20 (2025-01-12)**: Mail UID column in processed mail overview
  - Added Mail UID as first visible data column in processed mail dialog
  - Mail UID is now searchable/filterable via existing filter dropdown
  - **Column Order**: Checkbox, Mail UID, Subject, Received, Processed, Status, Error
  - **Filter Capability**: Mail UID added to filter targets alongside Error, Subject, Received, and Processed
  - **Implementation**:
    - Backend: Added UID filtering support to `ProcessedMailFilterSet.filter_by_text()` method
    - Frontend TypeScript: Added `Uid` to `MailFilterTarget` enum, added "Mail UID" filter option, updated `getFilterFieldName()` method
    - Frontend HTML: Added Mail UID column header and data cells
  - **Use Cases**:
    - Find specific emails by their IMAP UID
    - Cross-reference emails between mail server and processed mail log
    - Debug mail processing issues by tracking specific UIDs
  - **Benefits**:
    - Uses existing server-side filtering infrastructure (no performance issues)
    - Consistent with existing filter patterns (Error, Subject, etc.)
    - 3-character minimum search for performance
    - Case-insensitive contains search via Django ORM
  - Files modified:
    - Backend: `src/paperless_mail/filters.py` (added uid field filtering)
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.ts` (enum, filter targets, field mapping)
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.html` (column header and data cells)
  - All changes properly marked with RKC comments for maintainability

- **v1.0.19 (2025-11-12)**: Mail action "Process all mails (read and unread)"
  - Added new mail rule action that processes all mails regardless of read status without marking them
  - **Problem**: Existing actions either filter out read mails (MARK_READ) or modify mail state (FLAG, TAG, MOVE, DELETE)
  - **Solution**: 
    - Added PROCESS_ALL action (value 6) to MailAction enum
    - Created ProcessAllMailAction class with empty get_criteria() and no-op post_consume()
    - Processes ALL matching mails (read or unread) without any post-processing
    - Each mail still only processed once due to ProcessedMail UID tracking
  - **Use Cases**:
    - Archive folders where mails are already marked as read
    - Shared mailboxes where read status is managed by other systems
    - Bulk processing existing mail archives
    - Mail rules that should run on historical data without modifying it
  - **Benefits**:
    - No duplication - ProcessedMail table prevents reprocessing
    - Read status agnostic - processes both read and unread mails
    - Non-invasive - leaves mails completely untouched
    - Clean architecture - follows existing BaseMailAction pattern
  - Files modified:
    - Backend: `src/paperless_mail/models.py` (added PROCESS_ALL to MailAction enum)
    - Backend: `src/paperless_mail/mail.py` (added ProcessAllMailAction class and handler)
  - All changes properly marked with RKC comments for maintainability

- **v1.0.18 (2025-11-12)**: OAuth2 Email Sending Support
  - Added OAuth2 authentication for outgoing SMTP emails
  - **Problem**: Organizations using OAuth2 for mail retrieval still needed separate SMTP credentials for sending
  - **Solution**: 
    - Extended MailAccount model with `use_for_sending` and `from_address` fields
    - Created OAuth2EmailBackend using XOAUTH2 SASL mechanism
    - Modified send_email() to use OAuth2 when available, fallback to SMTP
    - Reuses existing OAuth2 infrastructure and token refresh logic
  - **Configuration**:
    - Enable "Use for sending" on any Gmail/Outlook OAuth2 MailAccount
    - Set "From address" if username is not an email address
    - If no OAuth2 sending account configured, falls back to SMTP
    - If SMTP not configured, email sending disabled (current behavior)
  - **Architecture**:
    - Minimal core code impact - isolated to RKC-marked sections
    - Automatic token refresh before sending
    - SMTP XOAUTH2 authentication (Gmail: smtp.gmail.com:587, Outlook: smtp.office365.com:587)
    - Uses Python's smtplib with OAuth2 tokens - OAuth2 is the authentication method, SMTP remains the protocol
    - Graceful degradation through multiple fallback layers
  - **Frontend UI**:
    - Added "OAuth2 Email Sending" section to Mail Account edit dialog
    - Checkbox control: "Use for sending emails"
    - Text input control: "From address" (with validation for email format)
    - Form controls integrated into Angular reactive forms pattern
    - Data model extended with optional use_for_sending and from_address fields
  - **Bug Fix #1 - Workflow Email Actions Blocked**:
    - **Issue**: Workflows with email actions failed with "Email backend has not been configured" error
    - **Root Cause**: `email_action()` in signals/handlers.py only checked `EMAIL_ENABLED` (traditional SMTP), not OAuth2 accounts
    - **Solution**: Modified check to `if not settings.EMAIL_ENABLED and not get_sending_mail_account():`
    - **Impact**: Workflows can now send emails when only OAuth2 is configured, without requiring traditional SMTP settings
    - **Note**: Could not modify EMAIL_ENABLED directly due to circular import constraints
  - **Bug Fix #2 - OAuth2 SMTP Authentication Failure**:
    - **Issue**: OAuth2 sending failed with "(530, b'5.7.57 Client not authenticated to send mail. Error: 535 5.7.3 Authentication unsuccessful"
    - **Root Cause**: Incorrect SMTP authentication method - was using `docmd('AUTH', 'XOAUTH2 ...')` which doesn't properly handle XOAUTH2 SASL mechanism
    - **Solution**: Changed to use `connection.auth('XOAUTH2', lambda: auth_string.encode())` which is Python's smtplib correct method for custom SASL authentication
    - **Technical Details**: 
      - SMTP response code 235 indicates successful authentication
      - Lambda function provides base64-encoded auth string as initial SASL response
      - Enhanced error handling to catch authentication failures with detailed logging
    - **Impact**: OAuth2 SMTP authentication now works correctly with Gmail/Outlook SMTP servers
  - **Bug Fix #3 - Lambda Function Signature Error**:
    - **Issue**: Email sending failed with "OAuth2EmailBackend.open.<locals>.<lambda>() missing 1 required positional argument: 'x'"
    - **Root Cause**: Lambda function defined as `lambda x: auth_string.encode()` but Python's smtplib `auth()` method calls authobject with NO arguments for XOAUTH2 mechanism
    - **Solution**: Fixed lambda signature from `lambda x:` to `lambda:` (removed unused parameter)
    - **Technical Details**:
      - XOAUTH2 mechanism supports initial client response
      - smtplib calls authobject() with zero arguments in this case
      - Lambda was expecting one parameter but smtplib provided none
    - **Impact**: OAuth2 email sending now works correctly without signature mismatch errors
  - Files modified:
    - Backend: `src/paperless_mail/models.py` (added use_for_sending, from_address fields + validation)
    - Backend: `src/paperless_mail/mail_oauth.py` (new OAuth2EmailBackend, helper functions, fixed auth method)
    - Backend: `src/documents/mail.py` (modified send_email to use OAuth2)
    - Backend: `src/documents/signals/handlers.py` (fixed EMAIL_ENABLED check in email_action)
    - Backend: `src/paperless_mail/admin.py` (admin fieldsets)
    - Backend: `src/paperless_mail/serialisers.py` (API serializers)
    - Migration: `src/paperless_mail/migrations/0030_add_oauth_sending_fields.py`
    - Frontend: `src-ui/src/app/data/mail-account.ts` (added use_for_sending, from_address fields to interface)
    - Frontend: `src-ui/src/app/components/common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component.html` (added OAuth2 Email Sending section UI)
    - Frontend: `src-ui/src/app/components/common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component.ts` (added form controls)
  - All changes properly marked with RKC comments for maintainability
  - **Note on Architecture**: OAuth2 is an authentication method, not a protocol replacement. We still use SMTP protocol with XOAUTH2 SASL authentication instead of traditional username/password. The alternative would be REST APIs (Gmail API/Microsoft Graph API) which would require complete rewrite and break Django EmailBackend compatibility.

- **v1.0.17 (2025-11-12)**: Mail action connection pooling to eliminate OAuth2 authentication storms
  - Implemented batched mail action processing via scheduled tasks to eliminate Microsoft IMAP rate limiting
  - **Problem**: Celery chord pattern created 100s of simultaneous OAuth2 authentication requests when processing emails
  - **Root Cause**: Each email spawned async `apply_mail_action` task requiring new IMAP connection and OAuth2 auth
  - **Solution**: 
    - Modified `queue_consumption_tasks()` to create PENDING_POST_ACTION entries instead of immediate callbacks
    - Added `update_mail_status()` helper task for asynchronous status updates
    - Created `process_pending_mail_actions()` scheduled task via Celery Beat
    - Created `process_account_pending_actions()` batch processor that pools connections per account
    - One pooled IMAP connection per account per batch = eliminated authentication storm
  - **Architecture**:
    - PENDING_POST_ACTION is transient status - quickly transitions to SUCCESS/FAILED
    - Scheduled task groups pending entries by account for connection pooling  
    - Single authenticated IMAP session processes all actions for that account sequentially
    - Uses existing `PAPERLESS_EMAIL_TASK_CRON` schedule (default: every 10 minutes)
  - **Configuration**:
    - Schedule controlled by `PAPERLESS_EMAIL_TASK_CRON` environment variable
    - Default: `*/10 * * * *` (every 10 minutes)
    - Same schedule used for both mail retrieval and pending action processing
    - Can be customized via environment variable for different intervals
  - **Benefits**:
    - Eliminates OAuth2 "AUTHENTICATE failed" errors from Microsoft rate limiting
    - Improved reliability through batch error handling
    - Better resource usage with predictable load patterns
    - Minimal code impact - backward compatible with existing entries
    - No additional environment variables needed - reuses existing configuration
  - Files modified:
    - Backend: `src/paperless_mail/models.py` (documented PENDING_POST_ACTION status)
    - Backend: `src/paperless_mail/mail.py` (new tasks: update_mail_status, process_pending_mail_actions, process_account_pending_actions; modified queue_consumption_tasks)
    - Backend: `src/paperless/settings.py` (added process_pending_mail_actions to Celery Beat schedule using PAPERLESS_EMAIL_TASK_CRON)
  - All changes properly marked with RKC comments for maintainability
  - See `IMPL_MAIL_ACTION_POOLING.md` for detailed implementation documentation

- **v1.0.16 (2025-11-12)**: Server-side filtering for Processed Mail
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
