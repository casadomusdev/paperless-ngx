import { AsyncPipe } from '@angular/common'
import { Component, OnDestroy, OnInit, inject } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { dirtyCheck } from '@ngneat/dirty-check-forms'
import { BehaviorSubject, Observable, takeUntil } from 'rxjs'
import { DisplayMode } from 'src/app/data/document'
import { SavedView } from 'src/app/data/saved-view'
// RKC: Import SETTINGS_KEYS for global views admin check
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
// /end RKC edit
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsService } from 'src/app/services/permissions.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmButtonComponent } from '../../common/confirm-button/confirm-button.component'
import { DragDropSelectComponent } from '../../common/input/drag-drop-select/drag-drop-select.component'
import { NumberComponent } from '../../common/input/number/number.component'
import { TextComponent } from '../../common/input/text/text.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'
@Component({
  selector: 'pngx-saved-views',
  templateUrl: './saved-views.component.html',
  styleUrl: './saved-views.component.scss',
  imports: [
    PageHeaderComponent,
    ConfirmButtonComponent,
    NumberComponent,
    TextComponent,
    IfPermissionsDirective,
    DragDropSelectComponent,
    FormsModule,
    ReactiveFormsModule,
    AsyncPipe,
  ],
})
export class SavedViewsComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  private savedViewService = inject(SavedViewService)
  private settings = inject(SettingsService)
  private toastService = inject(ToastService)
  private permissionsService = inject(PermissionsService)

  DisplayMode = DisplayMode

  public savedViews: SavedView[]
  // RKC: Separate global and personal saved views for distinct management
  public globalViews: SavedView[] = []
  public personalViews: SavedView[] = []
  private globalViewsGroup = new FormGroup({})
  private personalViewsGroup = new FormGroup({})
  // /end RKC edit
  private savedViewsGroup = new FormGroup({})
  public savedViewsForm: FormGroup = new FormGroup({
    savedViews: this.savedViewsGroup,
  })

  private store: BehaviorSubject<any>
  public isDirty$: Observable<boolean>

  get displayFields() {
    return this.settings.allDisplayFields
  }

  // RKC: Check if current user is the designated global views admin
  get isGlobalViewsAdmin(): boolean {
    const adminUserId = this.settings.get(SETTINGS_KEYS.GLOBAL_VIEWS_ADMIN_USER_ID)
    return adminUserId !== null && this.permissionsService['currentUser']?.id === adminUserId
  }
  // /end RKC edit

  constructor() {
    super()
    this.settings.organizingSidebarSavedViews = true
  }

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
      // Maintain backward compatibility with savedViews property
      this.savedViews = r.results
      // /end RKC edit
      this.initialize()
    })
  }

  ngOnDestroy(): void {
    this.settings.organizingSidebarSavedViews = false
    super.ngOnDestroy()
  }

  private initialize() {
    this.loading = false
    // RKC: Clear both global and personal view groups
    this.emptyGroup(this.globalViewsGroup)
    this.emptyGroup(this.personalViewsGroup)
    // /end RKC edit
    this.emptyGroup(this.savedViewsGroup)

    let storeData = {
      savedViews: {},
      // RKC: Add global and personal views to store
      globalViews: {},
      personalViews: {},
      // /end RKC edit
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
        // RKC: Toggle control for converting views between personal/global
        isGlobal: true,
        // /end RKC edit
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
          // RKC: Toggle control for converting views between personal/global
          isGlobal: new FormControl(true),
          // /end RKC edit
        })
      )
    }
    // /end RKC edit

    // RKC: Initialize personal views
    for (let view of this.personalViews) {
      storeData.personalViews[view.id.toString()] = {
        id: view.id,
        name: view.name,
        show_on_dashboard: view.show_on_dashboard,
        show_in_sidebar: view.show_in_sidebar,
        page_size: view.page_size,
        display_mode: view.display_mode,
        display_fields: view.display_fields,
        // RKC: Toggle control for converting views between personal/global
        isGlobal: false,
        // /end RKC edit
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
          // RKC: Toggle control for converting views between personal/global
          isGlobal: new FormControl(false),
          // /end RKC edit
        })
      )
    }
    // /end RKC edit

    for (let view of this.savedViews) {
      storeData.savedViews[view.id.toString()] = {
        id: view.id,
        name: view.name,
        show_on_dashboard: view.show_on_dashboard,
        show_in_sidebar: view.show_in_sidebar,
        page_size: view.page_size,
        display_mode: view.display_mode,
        display_fields: view.display_fields,
      }
      this.savedViewsGroup.addControl(
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

    // RKC: Update form to include both groups
    this.savedViewsForm = new FormGroup({
      globalViews: this.globalViewsGroup,
      personalViews: this.personalViewsGroup,
    })
    // /end RKC edit

    this.store = new BehaviorSubject(storeData)
    this.store
      .asObservable()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((state) => {
        this.savedViewsForm.patchValue(state, { emitEvent: false })
      })

    // Initialize dirtyCheck
    this.isDirty$ = dirtyCheck(this.savedViewsForm, this.store.asObservable())
  }

  public reset() {
    this.savedViewsForm.patchValue(this.store.getValue())
  }

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
      this.savedViewsGroup.removeControl(savedView.id.toString())
      this.savedViews.splice(this.savedViews.indexOf(savedView), 1)
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
        this.savedViews = r.results
        this.initialize()
      })
    })
  }

  private emptyGroup(group: FormGroup) {
    Object.keys(group.controls).forEach((key) => group.removeControl(key))
  }

  public save() {
    // RKC: Save both global and personal views
    const changedGlobal: SavedView[] = []
    const changedPersonal: SavedView[] = []

    Object.values(this.globalViewsGroup.controls)
      .filter((g: FormGroup) => !g.pristine)
      .forEach((group: FormGroup) => {
        const viewData = { ...group.value }
        // RKC: Set owner based on isGlobal toggle (NULL for global, user ID for personal)
        viewData.owner = viewData.isGlobal ? null : this.permissionsService['currentUser']?.id
        delete viewData.isGlobal
        // /end RKC edit
        changedGlobal.push(viewData)
      })

    Object.values(this.personalViewsGroup.controls)
      .filter((g: FormGroup) => !g.pristine)
      .forEach((group: FormGroup) => {
        const viewData = { ...group.value }
        // RKC: Set owner based on isGlobal toggle (NULL for global, user ID for personal)
        viewData.owner = viewData.isGlobal ? null : this.permissionsService['currentUser']?.id
        delete viewData.isGlobal
        // /end RKC edit
        changedPersonal.push(viewData)
      })

    const allChanged = [...changedGlobal, ...changedPersonal]
    // /end RKC edit

    if (allChanged.length) {
      this.savedViewService.patchMany(allChanged).subscribe({
        next: () => {
          this.toastService.showInfo($localize`Views saved successfully.`)
          this.store.next(this.savedViewsForm.value)
          // RKC: Refresh view list after save to reflect owner changes
          this.savedViewService.clearCache()
          this.savedViewService.listAll().subscribe((r) => {
            if (this.permissionsService.isSuperUser()) {
              this.globalViews = r.results.filter(v => v.owner === null)
              this.personalViews = r.results.filter(v => v.owner !== null)
            } else {
              this.globalViews = []
              this.personalViews = r.results.filter(v => v.owner !== null)
            }
            this.savedViews = r.results
            this.initialize()
          })
          // /end RKC edit
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

  // RKC: Save global views order for sidebar and dashboard
  // Only the designated admin can save the global ordering
  public saveGlobalViewsOrder() {
    if (!this.isGlobalViewsAdmin) {
      this.toastService.showError(
        $localize`Only the designated global views admin can change the order.`
      )
      return
    }

    // Get current order of global views
    const globalViewIds = this.globalViews.map(v => v.id)
    
    // Store in user settings (will be stored server-side for this admin user)
    this.settings.set(SETTINGS_KEYS.GLOBAL_VIEWS_SORT_ORDER, globalViewIds)
    this.settings.set(SETTINGS_KEYS.GLOBAL_DASHBOARD_VIEWS_SORT_ORDER, globalViewIds)
    
    this.settings.storeSettings().subscribe({
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
}
