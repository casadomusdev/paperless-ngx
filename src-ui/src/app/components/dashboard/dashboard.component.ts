import {
  CdkDragDrop,
  CdkDragEnd,
  CdkDragStart,
  DragDropModule,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { Component, computed, inject } from '@angular/core'
import { RouterModule } from '@angular/router'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { TourNgBootstrapModule, TourService } from 'ngx-ui-tour-ng-bootstrap'
import { SavedView } from 'src/app/data/saved-view'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsService } from 'src/app/services/permissions.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { LogoComponent } from '../common/logo/logo.component'
import { PageHeaderComponent } from '../common/page-header/page-header.component'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import { SavedViewWidgetComponent } from './widgets/saved-view-widget/saved-view-widget.component'
import { StatisticsWidgetComponent } from './widgets/statistics-widget/statistics-widget.component'
import { UploadFileWidgetComponent } from './widgets/upload-file-widget/upload-file-widget.component'
import { WelcomeWidgetComponent } from './widgets/welcome-widget/welcome-widget.component'

@Component({
  selector: 'pngx-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
  imports: [
    LogoComponent,
    PageHeaderComponent,
    SavedViewWidgetComponent,
    StatisticsWidgetComponent,
    UploadFileWidgetComponent,
    WelcomeWidgetComponent,
    IfPermissionsDirective,
    DragDropModule,
    TourNgBootstrapModule,
    NgxBootstrapIconsModule,
    RouterModule,
  ],
})
export class DashboardComponent extends ComponentWithPermissions {
  settingsService = inject(SettingsService)
  savedViewService = inject(SavedViewService)
  // RKC: Inject PermissionsService for superuser checks in global view drag-drop handlers
  permissionsService = inject(PermissionsService)
  // /end RKC edit
  private tourService = inject(TourService)
  private toastService = inject(ToastService)

  // RKC: Separate global dashboard views (owner=null) from user dashboard views
  // Global views are ordered by admin's dashboard sort order, user views by current user's order
  globalDashboardViews = computed(() => {
    const allViews = this.savedViewService.dashboardViews
    const globalViews = allViews.filter((v) => v.owner === null)

    const globalSortOrder = this.settingsService.globalDashboardViewsSortOrder
    if (globalSortOrder?.length > 0) {
      return globalSortOrder
        .map((id) => globalViews.find((v) => v.id === id))
        .concat(globalViews.filter((v) => !globalSortOrder.includes(v.id)))
        .filter((v) => v)
    }
    return globalViews
  })

  userDashboardViews = computed(() => {
    return this.savedViewService.dashboardViews.filter((v) => v.owner !== null)
  })
  // /end RKC edit

  constructor() {
    super()

    this.savedViewService.listAll().subscribe()
  }

  get subtitle() {
    if (this.settingsService.displayName) {
      return $localize`Hello ${this.settingsService.displayName}, welcome to ${environment.appTitle}`
    } else {
      return $localize`Welcome to ${environment.appTitle}`
    }
  }

  completeTour() {
    if (this.tourService.getStatus() !== 0) {
      this.tourService.end() // will call settingsService.completeTour()
    } else {
      this.settingsService.completeTour()
    }
  }

  onDragStart(event: CdkDragStart) {
    this.settingsService.globalDropzoneEnabled = false
  }

  onDragEnd(event: CdkDragEnd) {
    this.settingsService.globalDropzoneEnabled = true
  }

  onDrop(event: CdkDragDrop<SavedView[]>) {
    // RKC: Only allow reordering user dashboard views, not global views
    const userViews = this.userDashboardViews()
    moveItemInArray(userViews, event.previousIndex, event.currentIndex)

    this.settingsService.updateDashboardViewsSort(userViews).subscribe({
      next: () => {
        this.toastService.showInfo($localize`Dashboard updated`)
      },
      error: (e) => {
        this.toastService.showError($localize`Error updating dashboard`, e)
      },
    })
    // /end RKC edit
  }

  // RKC: Handle drag-drop reordering of global dashboard views
  // Only superusers can reorder global views
  // Saves ordering to ApplicationConfiguration which applies to all users
  onDropGlobal(event: CdkDragDrop<SavedView[]>) {
    if (!this.permissionsService.isSuperUser()) {
      this.toastService.showError(
        $localize`Only superusers can reorder global views.`
      )
      return
    }

    const globalViews = this.globalDashboardViews()
    moveItemInArray(globalViews, event.previousIndex, event.currentIndex)

    this.settingsService.updateGlobalDashboardViewsSort(globalViews).subscribe({
      next: () => {
        this.toastService.showInfo($localize`Global dashboard views updated`)
        // Reload to reflect new ordering
        this.savedViewService.clearCache()
        this.savedViewService.listAll().subscribe()
      },
      error: (e) => {
        this.toastService.showError($localize`Error updating global dashboard views`, e)
      },
    })
  }
  // /end RKC edit
}
