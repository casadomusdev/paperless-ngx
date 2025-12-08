# RKC Customizations Documentation

This document provides a comprehensive inventory of all RKC (Rob Kenis Consulting) customizations made to the Paperless-ngx project. These customizations are marked with "RKC:" comments throughout the codebase and include security enhancements, permission controls, and shared view functionality.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start & Deployment](#quick-start--deployment)
3. [Core Features](#core-features)
4. [Permission System](#permission-system)
5. [Backend Customizations](#backend-customizations)
6. [Frontend Customizations](#frontend-customizations)
7. [File Structure](#file-structure)
8. [Testing](#testing)
9. [Maintenance Notes](#maintenance-notes)

## Overview

The RKC customizations focus on:
- Enhanced security controls for PDF editing operations
- Shared saved views functionality for all users
- Superuser-only access to destructive document operations
- Improved access control for collaborative features
- Customizable theme color and appearance defaults via environment variables

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
**Purpose**: Restrict PDF editor access to superusers only to prevent accidental file modifications by regular users

**Files Modified**:
- `src/documents/views.py` - Backend permission check
- `src-ui/src/app/components/document-detail/document-detail.component.ts` - Frontend superuser check
- `src-ui/src/app/components/document-detail/document-detail.component.html` - UI visibility control

**Key Changes**:
- Backend validates `user.is_superuser` before allowing PDF edit operations
- Frontend hides PDF Editor button for non-superusers
- Returns `HttpResponseForbidden` with clear error message when unauthorized

**Security Benefits**:
- Defense in depth: Backend rejects unauthorized requests + Frontend hides the option
- Clean UX: Regular users don't see confusing disabled options
- API Protection: Direct API calls are rejected even if frontend bypass is attempted

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
# RKC: Restrict PDF editor to superusers only to prevent accidental file modifications
if method == bulk_edit.edit_pdf and not user.is_superuser:
    return HttpResponseForbidden("PDF editor is restricted to administrators")
# /end RKC edit
```

**Behavior**:
- Checks if operation is `edit_pdf`
- Validates user is superuser
- Returns 403 Forbidden if unauthorized
- Executes before any file operations occur

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

### 1. Superuser Check Getter (`src-ui/src/app/components/document-detail/document-detail.component.ts`)
**Location**: Component property getter

**Code**:
```typescript
// RKC: Check if user is superuser to restrict PDF editor access to admins only
get userIsSuperuser(): boolean {
  return this.permissionsService.isSuperUser()
}
// /end RKC edit
```

**Purpose**:
- Provides reactive superuser status check
- Used for conditional rendering in template
- Integrates with existing permissions service

### 2. Conditional PDF Editor Button (`src-ui/src/app/components/document-detail/document-detail.component.html`)
**Location**: Actions dropdown menu

**Code**:
```html
<!-- RKC: Hide PDF Editor menu item for non-superusers to prevent accidental file modifications 
     NOTE: Removed !userIsOwner condition to allow superusers to edit ANY document's PDF,
     not just documents they own. Superusers should have full editing rights. -->
<button *ngIf="userIsSuperuser" ngbDropdownItem (click)="editPdf()" [disabled]="!userCanEdit || originalContentRenderType !== ContentRenderType.PDF">
  <i-bs name="pencil"></i-bs>&nbsp;<ng-container i18n>PDF Editor</ng-container>
</button>
<!-- /end RKC edit -->
```

**Purpose**:
- Completely hides PDF Editor option for non-superusers
- Allows superusers to edit ANY document's PDF (including documents with NULL owner or owned by others)
- Still enforces that the document must be a PDF and the user must have edit permissions
- Prevents confusion from disabled buttons

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

### 1. Theme Color Default (`PAPERLESS_UI_THEME_COLOR`)
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

### 2. Dark Mode Thumbnail Inversion Default (`PAPERLESS_UI_DARK_MODE_THUMB_INVERTED`)
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

### 3. Default Language (`PAPERLESS_UI_DEFAULT_LANGUAGE`)
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

### 4. Global Views Admin User (`PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`)
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

### 5. Social Account Debug Logging (`PAPERLESS_SOCIALACCOUNT_DEBUG`)
**Purpose**: Enable detailed debug logging for django-allauth SSO/social account signup and authentication

**Type**: Boolean
**Default**: `false`
**Example**: `PAPERLESS_SOCIALACCOUNT_DEBUG=true`

**Behavior**:
- When enabled, adds verbose logging for all django-allauth operations
- Logs to both `paperless.log` file and console output
- Captures internal allauth signup flow, authentication attempts, and errors
- Should only be enabled temporarily for troubleshooting SSO issues
- No performance impact when disabled

**Use Cases**:
- Troubleshooting SSO signup failures
- Debugging social account connection issues
- Investigating authentication errors with OAuth providers
- Diagnosing user creation problems

**Log Output Location**:
- File: `/usr/src/paperless/data/log/paperless.log` (inside container)
- Console: `docker logs <container-name>` or systemd journal

**What Gets Logged**:
- `[allauth]` - General allauth framework operations
- `[allauth.account]` - Account creation and management
- `[allauth.socialaccount]` - Social provider authentication flow

**Example Usage**:
```bash
# Enable debug logging
docker compose down
# Add to docker-compose.yml environment section:
# - PAPERLESS_SOCIALACCOUNT_DEBUG=true
docker compose up -d

# Watch logs in real-time
docker compose logs -f webserver

# Attempt SSO signup
# Check logs for detailed debug output

# Disable when troubleshooting complete
# Remove or set to false, then restart
docker compose restart webserver
```

**Security Note**: Debug logs may contain sensitive information. Review logs before sharing and disable after troubleshooting.

**Implementation**:
- Backend: `src/paperless/settings.py` - Conditionally adds allauth loggers to LOGGING configuration
- Backend: `src/paperless/adapter.py` - Contains additional debug logging in CustomSocialAccountAdapter

## Version History

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
