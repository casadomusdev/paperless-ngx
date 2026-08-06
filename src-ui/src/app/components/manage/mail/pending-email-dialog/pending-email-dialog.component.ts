import { CommonModule, SlicePipe } from '@angular/common'
import { Component, inject, OnDestroy, OnInit } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbActiveModal,
  NgbDropdownModule,
  NgbPagination,
  NgbPopoverModule,
  NgbTooltipModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { debounceTime, distinctUntilChanged, filter, Subject, takeUntil } from 'rxjs'
import { ConfirmButtonComponent } from 'src/app/components/common/confirm-button/confirm-button.component'
import { PendingEmail } from 'src/app/data/pending-email'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { PendingEmailService } from 'src/app/services/rest/pending-email.service'
import { ToastService } from 'src/app/services/toast.service'

enum QueueFilterTarget {
  LastError,
  Subject,
  Recipients,
  Status,
}

@Component({
  selector: 'pngx-pending-email-dialog',
  imports: [
    CommonModule,
    ConfirmButtonComponent,
    CustomDatePipe,
    NgbPagination,
    NgbPopoverModule,
    NgbTooltipModule,
    NgbDropdownModule,
    NgxBootstrapIconsModule,
    FormsModule,
    ReactiveFormsModule,
    SlicePipe,
  ],
  templateUrl: './pending-email-dialog.component.html',
  styleUrl: './pending-email-dialog.component.scss',
})
export class PendingEmailDialogComponent implements OnInit, OnDestroy {
  private readonly activeModal = inject(NgbActiveModal)
  private readonly pendingEmailService = inject(PendingEmailService)
  private readonly toastService = inject(ToastService)

  public pendingEmails: PendingEmail[] = []
  public loading: boolean = true
  public toggleAllEnabled: boolean = false
  public readonly selectedIds: Set<number> = new Set<number>()
  public selectAllInDatabase: boolean = false

  public get selectedCount(): number {
    return this.selectAllInDatabase ? this.collectionSize : this.selectedIds.size
  }

  public page: number = 1
  public collectionSize: number = 0
  public totalUnfilteredCount: number = 0

  private _filterText: string = ''
  get filterText() { return this._filterText }
  set filterText(value: string) { this.filterDebounce.next(value) }

  public filterTargetID: QueueFilterTarget = QueueFilterTarget.LastError
  public get filterTargetName(): string {
    return this.filterTargets.find((t) => t.id == this.filterTargetID).name
  }
  private filterDebounce: Subject<string> = new Subject<string>()
  private unsubscribeNotifier: Subject<void> = new Subject<void>()

  public get filterTargets(): Array<{ id: number; name: string }> {
    return [
      { id: QueueFilterTarget.LastError, name: $localize`Error` },
      { id: QueueFilterTarget.Subject, name: $localize`Subject` },
      { id: QueueFilterTarget.Recipients, name: $localize`Recipients` },
      { id: QueueFilterTarget.Status, name: $localize`Status` },
    ]
  }

  private getFilterFieldName(): string {
    switch (this.filterTargetID) {
      case QueueFilterTarget.LastError: return 'last_error'
      case QueueFilterTarget.Subject: return 'subject'
      case QueueFilterTarget.Recipients: return 'recipients'
      case QueueFilterTarget.Status: return 'status'
      default: return 'last_error'
    }
  }

  ngOnInit(): void {
    this.loadPendingEmails()
    this.filterDebounce
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        debounceTime(500),
        distinctUntilChanged(),
        filter((query) => !query.length || query.length > 2)
      )
      .subscribe((query) => {
        this._filterText = query
        this.page = 1
        this.loadPendingEmails()
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next()
    this.unsubscribeNotifier.complete()
  }

  public close() { this.activeModal.close() }

  public loadPendingEmails(): void {
    this.loading = true
    this.clearSelection()
    const params: any = {}
    if (this._filterText && this._filterText.length > 2) {
      params.filter_field = this.getFilterFieldName()
      params.filter_text = this._filterText
    }
    this.pendingEmailService
      .list(this.page, 50, 'created_at', true, params)
      .subscribe((result) => {
        this.pendingEmails = result.results
        this.collectionSize = result.count
        if (!this._filterText || this._filterText.length < 3) {
          this.totalUnfilteredCount = result.count
        }
        this.loading = false
      })
  }

  public deleteSelected(): void {
    const count = this.selectedCount
    let filterMsg = ''
    if (this.selectAllInDatabase) {
      filterMsg = this._filterText ? ` matching filter '${this._filterText}'` : ' matching current view'
    }
    const confirmMsg = count === 1
      ? $localize`Delete 1 pending email${filterMsg}?`
      : $localize`Delete ${count} pending emails${filterMsg}?`
    if (!confirm(confirmMsg)) return

    if (this.selectAllInDatabase) {
      this.pendingEmailService
        .bulk_delete_filtered(this.getFilterFieldName(), this._filterText || '')
        .subscribe(() => {
          this.toastService.showInfo($localize`${count} pending emails deleted`)
          this.clearSelection()
          this.loadPendingEmails()
        })
    } else {
      this.pendingEmailService
        .bulk_delete(Array.from(this.selectedIds))
        .subscribe(() => {
          this.toastService.showInfo($localize`${count} pending emails deleted`)
          this.loadPendingEmails()
        })
    }
  }

  public toggleAll(event: PointerEvent) {
    if ((event.target as HTMLInputElement).checked) {
      this.selectAllInDatabase = false
      this.selectedIds.clear()
      this.pendingEmails.forEach((pe) => this.selectedIds.add(pe.id))
    } else {
      this.clearSelection()
    }
  }

  public toggleSelected(pe: PendingEmail) {
    if (this.selectedIds.has(pe.id)) {
      this.selectedIds.delete(pe.id)
      this.selectAllInDatabase = false
    } else {
      this.selectedIds.add(pe.id)
    }
    this.toggleAllEnabled = this.selectedIds.size === this.pendingEmails.length
  }

  public selectAllInDb() { this.selectAllInDatabase = true }

  public clearSelection() {
    this.selectedIds.clear()
    this.selectAllInDatabase = false
    this.toggleAllEnabled = false
  }

  public resetFilter() {
    this._filterText = ''
    this.page = 1
    this.loadPendingEmails()
  }

  public filterInputKeyup(event: KeyboardEvent) {
    this.filterText = (event.target as HTMLInputElement).value
  }
}
