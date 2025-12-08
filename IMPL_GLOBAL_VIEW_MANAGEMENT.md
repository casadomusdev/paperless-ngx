# Global Saved Views Management - Implementation Plan

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

**File:** `src/documents/views.py`  
**Location:** SavedViewViewSet class, methods: `update()`, `partial_update()`, `destroy()`

**Current Code:**
```python
def update(self, request, *args, **kwargs):
    instance = self.get_object()
    if instance.owner is None:
        return HttpResponseForbidden(
            "Shared saved views (without owner) cannot be modified",
        )
    return super().update(request, *args, **kwargs)
```

**New Code:**
```python
def update(self, request, *args, **kwargs):
    instance = self.get_object()
    # RKC: Allow superusers to edit global saved views (owner=NULL)
    # This enables management of organization-wide views through the UI
    if instance.owner is None and not request.user.is_superuser:
        return HttpResponseForbidden(
            "Shared saved views (without owner) cannot be modified",
        )
    # /end RKC edit
    return super().update(request, *args, **kwargs)
```

**Apply same change to `partial_update()` and `destroy()` methods.**

**Rationale:** This allows superusers to edit global views while still protecting them from regular users.

#### 1.2 Expose Global Views Admin User ID to Frontend

**File:** `src/documents/views.py`  
**Location:** UiSettingsView.get() method, after other ui_settings assignments

**Add after `global_dashboard_views_sort_order` assignment:**
```python
# RKC: Pass global views admin user ID to frontend
# This allows the frontend to determine if the current user is authorized
# to reorder global saved views in sidebar and dashboard
ui_settings["global_views_admin_user_id"] = getattr(
    settings, "GLOBAL_VIEWS_ADMIN_USER_ID", None
)
# /end RKC edit
```

**Rationale:** Frontend needs to know if current user is the designated admin to show/hide reordering controls.

### Phase 2: Frontend Data Layer

#### 2.1 Add Settings Key

**File:** `src-ui/src/app/data/ui-settings.ts`  
**Location:** SETTINGS_KEYS object

**Add to SETTINGS_KEYS:**
```typescript
export const SETTINGS_KEYS = {
  // ... existing keys ...
  GLOBAL_VIEWS_ADMIN_USER_ID: 'global_views_admin_user_id', // RKC: ID of user who can reorder global views
  // /end RKC edit
}
```

#### 2.2 Separate Global and Personal Views

**File:** `src-ui/src/app/components/manage/saved-views/saved-views.component.ts`

**Changes Required:**

1. **Add Properties:**
```typescript
// RKC: Separate global and personal saved views for distinct management
public globalViews: SavedView[] = []
public personalViews: SavedView[] = []
private globalViewsGroup = new FormGroup({})
private personalViewsGroup = new FormGroup({})
// /end RKC edit
```

2. **Add Getter for Admin Check:**
```typescript
// RKC: Check if current user is the designated global views admin
get isGlobalViewsAdmin(): boolean {
  const adminUserId = this.settings.get(SETTINGS_KEYS.GLOBAL_VIEWS_ADMIN_USER_ID)
  return adminUserId !== null && this.permissionsService.currentUserId === adminUserId
}
// /end RKC edit
```

3. **Modify ngOnInit():**
```typescript
ngOnInit(): void {
  this.loading = true
  this.savedViewService.listAll().subscribe((r) => {
    // RKC: Separate global views (owner=NULL) from personal views
    if (this.permissionsService.isSuperUser()) {
      this.globalViews = r.results.filter(v => v.owner === null)
      this.personalViews = r.results.filter(v => v.owner !== null)
    } else {
      this.globalViews = []
      this.personalViews = r.results.filter(v => v.owner !== null)
    }
    // /end RKC edit
    this.initialize()
  })
}
```

4. **Modify initialize() Method:**
```typescript
private initialize() {
  this.loading = false
  this.emptyGroup(this.savedViewsGroup)
  // RKC: Clear both global and personal view groups
  this.emptyGroup(this.globalViewsGroup)
  this.emptyGroup(this.personalViewsGroup)
  // /end RKC edit

  let storeData = {
    savedViews: {},
    globalViews: {}, // RKC: Add global views to store
    personalViews: {}, // RKC: Add personal views to store
  }

  // RKC: Initialize global views
  for (let view of this.globalViews) {
    storeData.globalViews[view.id.toString()] = {
      id: view.id,
      name: view.name,
      show_on_dashboard: view.show_on_dashboard,
      show_in_sidebar: view.show_in_sidebar,
      page_size: view.page_size,
      display_mode: view.display_mode,
      display_fields: view.display_fields,
    }
    this.globalViewsGroup.addControl(
      view.id.toString(),
      new FormGroup({
        id: new FormControl(null),
        name: new FormControl(null),
        show_on_dashboard: new FormControl(null),
        show_in_sidebar: new FormControl(null),
        page_size: new FormControl(null),
        display_mode: new FormControl(null),
        display_fields: new FormControl([]),
      })
    )
  }
  // /end RKC edit

  // RKC: Initialize personal views (keep existing logic)
  for (let view of this.personalViews) {
    storeData.personalViews[view.id.toString()] = {
      id: view.id,
      name: view.name,
      show_on_dashboard: view.show_on_dashboard,
      show_in_sidebar: view.show_in_sidebar,
      page_size: view.page_size,
      display_mode: view.display_mode,
      display_fields: view.display_fields,
    }
    this.personalViewsGroup.addControl(
      view.id.toString(),
      new FormGroup({
        id: new FormControl(null),
        name: new FormControl(null),
        show_on_dashboard: new FormControl(null),
        show_in_sidebar: new FormControl(null),
        page_size: new FormControl(null),
        display_mode: new FormControl(null),
        display_fields: new FormControl([]),
      })
    )
  }
  // /end RKC edit

  // RKC: Update form to include both groups
  this.savedViewsForm = new FormGroup({
    globalViews: this.globalViewsGroup,
    personalViews: this.personalViewsGroup,
  })
  // /end RKC edit

  this.store = new BehaviorSubject(storeData)
  // ... rest of initialize() unchanged ...
}
```

5. **Update save() Method:**
```typescript
public save() {
  // RKC: Save both global and personal views
  const changedGlobal: SavedView[] = []
  const changedPersonal: SavedView[] = []

  Object.values(this.globalViewsGroup.controls)
    .filter((g: FormGroup) => !g.pristine)
    .forEach((group: FormGroup) => {
      changedGlobal.push(group.value)
    })

  Object.values(this.personalViewsGroup.controls)
    .filter((g: FormGroup) => !g.pristine)
    .forEach((group: FormGroup) => {
      changedPersonal.push(group.value)
    })

  const allChanged = [...changedGlobal, ...changedPersonal]
  // /end RKC edit
  
  if (allChanged.length) {
    this.savedViewService.patchMany(allChanged).subscribe({
      next: () => {
        this.toastService.showInfo($localize`Views saved successfully.`)
        this.store.next(this.savedViewsForm.value)
      },
      error: (error) => {
        this.toastService.showError(
          $localize`Error while saving views.`,
          error
        )
      },
    })
  }
}
```

6. **Update deleteSavedView():**
```typescript
public deleteSavedView(savedView: SavedView) {
  this.savedViewService.delete(savedView).subscribe(() => {
    // RKC: Remove from appropriate array
    if (savedView.owner === null) {
      this.globalViewsGroup.removeControl(savedView.id.toString())
      this.globalViews.splice(this.globalViews.indexOf(savedView), 1)
    } else {
      this.personalViewsGroup.removeControl(savedView.id.toString())
      this.personalViews.splice(this.personalViews.indexOf(savedView), 1)
    }
    // /end RKC edit
    this.toastService.showInfo(
      $localize`Saved view "${savedView.name}" deleted.`
    )
    this.savedViewService.clearCache()
    this.savedViewService.listAll().subscribe((r) => {
      // RKC: Re-separate views after refresh
      if (this.permissionsService.isSuperUser()) {
        this.globalViews = r.results.filter(v => v.owner === null)
        this.personalViews = r.results.filter(v => v.owner !== null)
      } else {
        this.globalViews = []
        this.personalViews = r.results.filter(v => v.owner !== null)
      }
      // /end RKC edit
      this.initialize()
    })
  })
}
```

7. **Add Method to Save Global View Order:**
```typescript
// RKC: Save global views order for sidebar and dashboard
// Only the designated admin can save the global ordering
public saveGlobalViewsOrder() {
  if (!this.isGlobalViewsAdmin) {
    this.toastService.showError(
      $localize`Only the designated global views admin can change the order.`
    )
    return
  }

  // Get current sidebar order from settings
  const currentSettings = this.settings.getLocalSettings()
  const savedViewsSettings = currentSettings['saved_views'] || {}
  
  // Update sidebar order with current global views order
  const globalViewIds = this.globalViews.map(v => v.id)
  savedViewsSettings['sidebar-views-sort-order'] = globalViewIds
  savedViewsSettings['dashboard-views-sort-order'] = globalViewIds
  
  currentSettings['saved_views'] = savedViewsSettings
  
  this.settings.updateLocalSettings(currentSettings).subscribe({
    next: () => {
      this.toastService.showInfo($localize`Global view order saved successfully.`)
    },
    error: (error) => {
      this.toastService.showError(
        $localize`Error saving global view order.`,
        error
      )
    },
  })
}
// /end RKC edit
```

### Phase 3: Frontend UI

#### 3.1 Create Separate Sections in HTML

**File:** `src-ui/src/app/components/manage/saved-views/saved-views.component.html`

**Replace entire `<form>` content with:**

```html
<pngx-page-header
  title="Saved Views"
  i18n-title
  info="Customize the views of your documents."
  i18n-info>
</pngx-page-header>

<form [formGroup]="savedViewsForm" (ngSubmit)="save()">
  
  <!-- RKC: Global Shared Views Section (Superusers Only) -->
  @if (globalViews && globalViews.length > 0) {
    <div class="card mb-3 border-primary">
      <div class="card-header bg-primary text-white">
        <h5 class="mb-0" i18n>Global Shared Views</h5>
        <small i18n>These views are visible to all users in the organization.</small>
        @if (!isGlobalViewsAdmin) {
          <div class="mt-2">
            <small class="badge bg-warning text-dark" i18n>
              Only the designated admin can reorder these views
            </small>
          </div>
        }
      </div>
      <div class="card-body">
        <ul class="list-group" formGroupName="globalViews">
          @for (view of globalViews; track view) {
            <li class="list-group-item py-3">
              <div [formGroupName]="view.id">
                <div class="row">
                  <div class="col">
                    <div class="d-flex align-items-center mb-2">
                      <span class="badge bg-info me-2" i18n>GLOBAL</span>
                      <pngx-input-text title="Name" formControlName="name"></pngx-input-text>
                    </div>
                  </div>
                  <div class="col">
                    <div class="form-check form-switch mt-3">
                      <input type="checkbox" class="form-check-input" id="global_show_on_dashboard_{{view.id}}" formControlName="show_on_dashboard">
                      <label class="form-check-label" for="global_show_on_dashboard_{{view.id}}" i18n>Show on dashboard</label>
                    </div>
                    <div class="form-check form-switch">
                      <input type="checkbox" class="form-check-input" id="global_show_in_sidebar_{{view.id}}" formControlName="show_in_sidebar">
                      <label class="form-check-label" for="global_show_in_sidebar_{{view.id}}" i18n>Show in sidebar</label>
                    </div>
                  </div>
                  <div class="col-auto">
                    <label class="form-label" for="global_name_{{view.id}}" i18n>Actions</label>
                    <pngx-confirm-button
                      label="Delete"
                      i18n-label
                      (confirm)="deleteSavedView(view)"
                      *pngxIfPermissions="{ action: PermissionAction.Delete, type: PermissionType.SavedView }"
                      buttonClasses="btn-sm btn-outline-danger form-control"
                      iconName="trash">
                    </pngx-confirm-button>
                  </div>
                </div>
                <div class="row">
                  <div class="col">
                    <pngx-input-number i18n-title title="Documents page size" [showAdd]="false" formControlName="page_size"></pngx-input-number>
                  </div>
                  <div class="col">
                    <label class="form-label" for="global_display_mode_{{view.id}}" i18n>Display as</label>
                    <select class="form-select" formControlName="display_mode">
                      <option [ngValue]="DisplayMode.TABLE" i18n>Table</option>
                      <option [ngValue]="DisplayMode.SMALL_CARDS" i18n>Small Cards</option>
                      <option [ngValue]="DisplayMode.LARGE_CARDS" i18n>Large Cards</option>
                    </select>
                  </div>
                  @if (displayFields) {
                    <pngx-input-drag-drop-select i18n-title title="Show" i18n-emptyText emptyText="Default" [items]="displayFields" formControlName="display_fields"></pngx-input-drag-drop-select>
                  }
                </div>
              </div>
            </li>
          }
        </ul>
        @if (isGlobalViewsAdmin) {
          <div class="mt-3">
            <button type="button" (click)="saveGlobalViewsOrder()" class="btn btn-outline-primary btn-sm" i18n>
              Save Global View Order
            </button>
            <small class="text-muted ms-2" i18n>
              The order shown here will be applied to all users' sidebars and dashboards
            </small>
          </div>
        }
      </div>
    </div>
  }
  <!-- /end RKC edit -->

  <!-- Personal Saved Views Section -->
  <div class="card">
    <div class="card-header">
      <h5 class="mb-0" i18n>Personal Saved Views</h5>
      <small i18n>These views are private to your account.</small>
    </div>
    <div class="card-body">
      <ul class="list-group" formGroupName="personalViews">
        @for (view of personalViews; track view) {
          <li class="list-group-item py-3">
            <div [formGroupName]="view.id">
              <div class="row">
                <div class="col">
                  <pngx-input-text title="Name" formControlName="name"></pngx-input-text>
                </div>
                <div class="col">
                  <div class="form-check form-switch mt-3">
                    <input type="checkbox" class="form-check-input" id="show_on_dashboard_{{view.id}}" formControlName="show_on_dashboard">
                    <label class="form-check-label" for="show_on_dashboard_{{view.id}}" i18n>Show on dashboard</label>
                  </div>
                  <div class="form-check form-switch">
                    <input type="checkbox" class="form-check-input" id="show_in_sidebar_{{view.id}}" formControlName="show_in_sidebar">
                    <label class="form-check-label" for="show_in_sidebar_{{view.id}}" i18n>Show in sidebar</label>
                  </div>
                </div>
                <div class="col-auto">
                  <label class="form-label" for="name_{{view.id}}" i18n>Actions</label>
                  <pngx-confirm-button
                    label="Delete"
                    i18n-label
                    (confirm)="deleteSavedView(view)"
                    *pngxIfPermissions="{ action: PermissionAction.Delete, type: PermissionType.SavedView }"
                    buttonClasses="btn-sm btn-outline-danger form-control"
                    iconName="trash">
                  </pngx-confirm-button>
                </div>
              </div>
              <div class="row">
                <div class="col">
                  <pngx-input-number i18n-title title="Documents page size" [showAdd]="false" formControlName="page_size"></pngx-input-number>
                </div>
                <div class="col">
                  <label class="form-label" for="display_mode_{{view.id}}" i18n>Display as</label>
                  <select class="form-select" formControlName="display_mode">
                    <option [ngValue]="DisplayMode.TABLE" i18n>Table</option>
                    <option [ngValue]="DisplayMode.SMALL_CARDS" i18n>Small Cards</option>
                    <option [ngValue]="DisplayMode.LARGE_CARDS" i18n>Large Cards</option>
                  </select>
                </div>
                @if (displayFields) {
                  <pngx-input-drag-drop-select i18n-title title="Show" i18n-emptyText emptyText="Default" [items]="displayFields" formControlName="display_fields"></pngx-input-drag-drop-select>
                }
              </div>
            </div>
          </li>
        }

        @if (personalViews && personalViews.length === 0) {
          <li class="list-group-item">
            <div i18n>No personal saved views defined.</div>
          </li>
        }

        @if (loading) {
          <li class="list-group-item">
            <div class="spinner-border spinner-border-sm fw-normal ms-2 me-auto" role="status"></div>
            <div class="visually-hidden" i18n>Loading...</div>
          </li>
        }
      </ul>
    </div>
  </div>

  <div class="mt-3">
    <button type="button" (click)="reset()" class="btn btn-outline-secondary mb-2" [disabled]="(isDirty$ | async) === false" i18n>Cancel</button>
    <button type="submit" class="btn btn-primary ms-2 mb-2" [disabled]="(isDirty$ | async) === false" i18n>Save</button>
  </div>
</form>
```

## TESTING

### Test Scenarios

#### 1. Non-Superuser
- **Expected:** Should not see global views section at all in management page
- **Steps:**
  1. Log in as regular user
  2. Navigate to Settings > Saved Views
  3. Verify only "Personal Saved Views" section appears

#### 2. Superuser (Not Global Admin)
- **Expected:** Can see and edit global views but cannot reorder them
- **Steps:**
  1. Log in as superuser (not the one set in `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`)
  2. Navigate to Settings > Saved Views
  3. Verify "Global Shared Views" section appears with "GLOBAL" badges
  4. Verify warning badge: "Only the designated admin can reorder these views"
  5. Edit a global view's name, click Save
  6. Verify changes persist after refresh
  7. Verify no "Save Global View Order" button appears

#### 3. Global Views Admin
- **Expected:** Full control over global views including ordering
- **Steps:**
  1. Log in as user whose ID matches `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID`
  2. Navigate to Settings > Saved Views
  3. Verify "Global Shared Views" section appears
  4. Verify "Save Global View Order" button appears
  5. Reorder global views (if drag-drop implemented), click "Save Global View Order"
  6. Log in as different user, verify sidebar shows views in new order
  7. Verify dashboard also shows views in new order

#### 4. Global View Visibility for Regular Users
- **Expected:** All users see global views in sidebar/dashboard
- **Steps:**
  1. Create/modify global views as superuser
  2. Log in as regular user
  3. Verify global views appear in "Shortcuts" section of sidebar
  4. Verify global views appear on dashboard
  5. Verify global views are in order set by admin

#### 5. Delete Global View
- **Expected:** Only superusers can delete global views
- **Steps:**
  1. Log in as superuser
  2. Navigate to Settings > Saved Views
  3. Click delete on a global view
  4. Confirm deletion
  5. Verify view removed from list
  6. Verify view no longer appears in sidebar for any user

## FUTURE ENHANCEMENTS (Out of Scope)

1. **Create New Global Views:** Add UI button to create new global views directly in management page
2. **Separate Ordering Controls:** Allow different admins for sidebar vs dashboard ordering
3. **Bulk Operations:** Select multiple global views for bulk edit/delete
4. **View Templates:** Create templates from global views for users to customize
5. **Drag-Drop Reordering:** Implement actual drag-drop interface for reordering (currently requires manual array manipulation)
6. **Access Control Groups:** Instead of single admin user, allow admin groups to manage global views
7. **View Preview:** Preview how global view will look before saving
8. **Change History:** Track who modified global views and when

## MIGRATION NOTES

### For Existing Deployments

If you have existing global views (with `owner=NULL`):

1. **No Database Changes Required:** This implementation works with existing data
2. **Backend Configuration:** Ensure `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID` is set to a valid superuser ID
3. **Verify Permissions:** Run this SQL to identify global views:
   ```sql
   SELECT id, name, owner_id FROM documents_savedview WHERE owner_id IS NULL;
   ```
4. **Ordering Setup:** The designated admin should log in and their current sidebar/dashboard view order will be used for all users

### Rollback Plan

If issues arise:
1. Revert backend changes to restore 403 blocks on global view editing
2. Revert frontend to show single list of views
3. Global views will still function for end users in sidebar/dashboard

## VERSION HISTORY

- **v1.0.0 (Planned):** Initial implementation of global view management
  - Superuser editing of global views
  - Visual separation of global vs personal views
  - Admin-controlled ordering for global views
  - Minimal impact on core code for upstream compatibility

## NOTES

- All code changes are marked with `// RKC:` comments for easy identification
- Backend permission checks maintain security even if frontend is bypassed
- Ordering is stored in the admin user's `ui_settings`, leveraging existing infrastructure
- This feature builds on existing `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID` setting
- Future upstream updates to SavedView functionality should be easy to merge
