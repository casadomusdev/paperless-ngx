# Global Saved Views Management - Implementation

## GOAL

Enable proper management of global shared views (views with `owner=NULL`) in the saved views management page with the following capabilities:

1. Only superusers can see and edit global shared views in the management interface
2. Global shared views appear in a visually distinct section above personal views
3. Only the designated global views admin (via `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`) can reorder global views in sidebar and dashboard
4. Minimize impact on core Paperless-ngx code to facilitate easier upstream merges

## ANALYSIS

### Current State

**What Works:**
- Global saved views (`owner=NULL`) are visible to all users in sidebar and dashboard
- Global views are sorted according to the designated admin's preferences (via `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`)
- Backend prevents modification of global views via 403 Forbidden responses
- Non-admin users are filtered out of seeing global views in the management UI

**What Needs Improvement:**
- Superusers can see global views in the management page but cannot edit them (backend blocks with 403)
- No visual separation between global and personal views in the management interface
- No way for the designated admin to change the order of global views through the UI (must manually edit database)
- Confusing UX: superusers see global views but get errors when trying to save changes

### Key Constraints

1. **Backend Restriction:** Current code in `src/documents/views.py` prevents ANY modification of views with `owner=NULL`
2. **Permissions Model:** Only superusers should access global view management
3. **Ordering Authority:** Only the user specified in `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID` should reorder global views
4. **Upstream Compatibility:** Changes must be minimal and clearly marked with RKC comments for easy maintenance

### Files to Modify

#### Backend (Python)
1. `src/documents/views.py` - SavedViewViewSet class modifications
2. `src/documents/views.py` - UiSettingsView to expose admin user ID

#### Frontend (TypeScript)
1. `src-ui/src/app/components/manage/saved-views/saved-views.component.ts`
2. `src-ui/src/app/data/ui-settings.ts`

#### Frontend (HTML)
1. `src-ui/src/app/components/manage/saved-views/saved-views.component.html`

## IMPLEMENTATION

### Phase 1: Backend Modifications

#### 1.1 Allow Superuser Editing of Global Views
- Modify `update()`, `partial_update()`, and `destroy()` methods in SavedViewViewSet
- Allow superusers to edit global views while protecting them from regular users
- Add RKC comments for easy identification

#### 1.2 Expose Global Views Admin User ID to Frontend
- Add `global_views_admin_user_id` to UiSettingsView.get() response
- Frontend needs this to determine if current user is authorized to reorder global views

### Phase 2: Frontend Data Layer

#### 2.1 Add Settings Key
- Add `GLOBAL_VIEWS_ADMIN_USER_ID` to SETTINGS_KEYS in ui-settings.ts

#### 2.2 Separate Global and Personal Views
- Add properties for globalViews and personalViews arrays
- Add separate FormGroups for each type
- Add isGlobalViewsAdmin getter to check authorization
- Modify ngOnInit() to separate views based on owner
- Update initialize() to handle both view types
- Update save() to process both types
- Update deleteSavedView() to handle both types
- Add saveGlobalViewsOrder() method for admin-only ordering

### Phase 3: Frontend UI

#### 3.1 Create Separate Sections in HTML
- Create "Global Shared Views" section with visual distinction (blue card)
- Add "GLOBAL" badges to global views
- Show warning if user is not the designated admin
- Add "Save Global View Order" button for admin users
- Keep "Personal Saved Views" section for user's own views
- Maintain all existing functionality for personal views

## IMPLEMENTATION STATUS

### ✅ COMPLETED

All phases of the implementation have been completed:

**Phase 1: Backend Modifications**
- ✅ Modified SavedViewViewSet.update() to allow superusers to edit global views
- ✅ Modified SavedViewViewSet.partial_update() to allow superusers to edit global views
- ✅ Modified SavedViewViewSet.destroy() to allow superusers to delete global views
- ✅ Added global_views_admin_user_id to UiSettingsView.get() response
- ✅ All modifications marked with RKC comments

**Phase 2: Frontend Data Layer**
- ✅ Added GLOBAL_VIEWS_ADMIN_USER_ID to SETTINGS_KEYS
- ✅ Added globalViews and personalViews properties to component
- ✅ Added globalViewsGroup and personalViewsGroup FormGroups
- ✅ Added isGlobalViewsAdmin getter
- ✅ Modified ngOnInit() to separate global and personal views
- ✅ Modified initialize() to handle both view types
- ✅ Modified save() to process both view types
- ✅ Modified deleteSavedView() to handle both view types
- ✅ Added saveGlobalViewsOrder() method
- ✅ All modifications marked with RKC comments

**Phase 3: Frontend UI**
- ✅ Created "Global Shared Views" section with card styling
- ✅ Added "GLOBAL" badges to global views
- ✅ Added warning message for non-admin users
- ✅ Added "Save Global View Order" button for admin users
- ✅ Updated "Personal Saved Views" section
- ✅ All modifications marked with RKC comments

### 📋 NEXT STEPS

1. **Testing**: Run through the test scenarios in TODO.md
2. **Documentation**: Update RKC_CUSTOMIZATIONS.md with feature details
3. **Deployment**: Build and deploy to test environment
4. **User Acceptance**: Verify with actual users

See TODO.md for detailed testing checklist and future improvements.
