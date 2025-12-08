# Global Saved Views Management - TODO

## Phase 1: Backend Modifications

### 1.1 Allow Superuser Editing of Global Views
- [x] Read src/documents/views.py to locate SavedViewViewSet class
- [x] Modify `update()` method to allow superusers to edit global views
- [x] Modify `partial_update()` method to allow superusers to edit global views
- [x] Modify `destroy()` method to allow superusers to delete global views
- [x] Add RKC comments for all modifications

### 1.2 Expose Global Views Admin User ID
- [x] Locate UiSettingsView.get() method in src/documents/views.py
- [x] Add `global_views_admin_user_id` to ui_settings dict
- [x] Add RKC comments for modification

## Phase 2: Frontend Data Layer

### 2.1 Add Settings Key
- [x] Read src-ui/src/app/data/ui-settings.ts
- [x] Add GLOBAL_VIEWS_ADMIN_USER_ID to SETTINGS_KEYS object
- [x] Add RKC comment

### 2.2 Modify Saved Views Component TypeScript
- [x] Read src-ui/src/app/components/manage/saved-views/saved-views.component.ts
- [x] Add globalViews and personalViews properties
- [x] Add globalViewsGroup and personalViewsGroup FormGroup properties
- [x] Add isGlobalViewsAdmin getter
- [x] Modify ngOnInit() to separate global and personal views
- [x] Modify initialize() method to handle both view types
- [x] Modify save() method to process both view types
- [x] Modify deleteSavedView() to handle both view types
- [x] Add saveGlobalViewsOrder() method for admin ordering
- [x] Add RKC comments for all modifications

## Phase 3: Frontend UI

### 3.1 Modify Saved Views Component HTML
- [x] Read src-ui/src/app/components/manage/saved-views/saved-views.component.html
- [x] Create "Global Shared Views" section with card styling
- [x] Add "GLOBAL" badges to global views
- [x] Add warning message for non-admin users
- [x] Add "Save Global View Order" button for admin users
- [x] Update "Personal Saved Views" section
- [x] Add RKC comments for all modifications

## Testing

### 4.1 Backend Testing
- [ ] Test superuser can edit global view name
- [ ] Test superuser can delete global view
- [ ] Test non-superuser gets 403 when trying to edit global view
- [ ] Test global_views_admin_user_id is exposed in /api/ui_settings/

### 4.2 Frontend Testing - Non-Superuser
- [ ] Test regular user doesn't see global views in management page
- [ ] Test regular user still sees global views in sidebar
- [ ] Test regular user still sees global views on dashboard

### 4.3 Frontend Testing - Superuser (Not Admin)
- [ ] Test superuser sees global views section
- [ ] Test "GLOBAL" badges appear
- [ ] Test warning message appears
- [ ] Test can edit global view and save successfully
- [ ] Test can delete global view
- [ ] Test "Save Global View Order" button does NOT appear

### 4.4 Frontend Testing - Global Views Admin
- [ ] Test admin sees global views section
- [ ] Test "Save Global View Order" button appears
- [ ] Test can edit global views
- [ ] Test can save global view order
- [ ] Test order changes propagate to all users

## Documentation Updates

- [ ] Update RKC_CUSTOMIZATIONS.md with new feature details
- [ ] Add version entry to version history
- [ ] Document new UI sections and permissions

## Future Improvements

- Create new global views button in management UI
- Drag-drop reordering for global views
- Separate ordering controls for sidebar vs dashboard
- Bulk operations on global views
- View templates system
- Access control groups for global view management
- View preview functionality
- Change history tracking
