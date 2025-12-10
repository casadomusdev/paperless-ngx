import { CommonModule, SlicePipe } from '@angular/common'
import { Component, inject, Input, OnDestroy, OnInit } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbActiveModal,
  NgbDropdownModule,
  NgbModal,
  NgbPagination,
  NgbPopoverModule,
  NgbTooltipModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
// RKC: Import RxJS operators for filter debouncing
import {
  debounceTime,
  distinctUntilChanged,
  filter,
  Subject,
  takeUntil,
} from 'rxjs'
// /end RKC edit
import { ConfirmButtonComponent } from 'src/app/components/common/confirm-button/confirm-button.component'
import { MailRule } from 'src/app/data/mail-rule'
import { ProcessedMail } from 'src/app/data/processed-mail'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { ProcessedMailService } from 'src/app/services/rest/processed-mail.service'
import { ToastService } from 'src/app/services/toast.service'

// RKC: Filter target enum for processed mail filtering
enum MailFilterTarget {
  Error,
  Subject,
  Received,
  Processed,
}
// /end RKC edit

@Component({
  selector: 'pngx-processed-mail-dialog',
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
  templateUrl: './processed-mail-dialog.component.html',
  styleUrl: './processed-mail-dialog.component.scss',
})
export class ProcessedMailDialogComponent implements OnInit, OnDestroy {
  private readonly activeModal = inject(NgbActiveModal)
  private readonly processedMailService = inject(ProcessedMailService)
  private readonly toastService = inject(ToastService)
  // RKC: Inject modal service for error detail popup
  private readonly modalService = inject(NgbModal)
  // /end RKC edit

  public processedMails: ProcessedMail[] = []

  public loading: boolean = true
  public toggleAllEnabled: boolean = false
  public readonly selectedMailIds: Set<number> = new Set<number>()

  public page: number = 1
  // RKC: Store total count for pagination (fixes bug where pagination only showed current page count)
  public collectionSize: number = 0
  // RKC: Store total unfiltered count to show alongside filtered results
  public totalUnfilteredCount: number = 0
  // /end RKC edit

  // RKC: Filter properties for client-side filtering (similar to file tasks page)
  private _filterText: string = ''
  get filterText() {
    return this._filterText
  }
  set filterText(value: string) {
    this.filterDebounce.next(value)
  }

  public filterTargetID: MailFilterTarget = MailFilterTarget.Error
  public get filterTargetName(): string {
    return this.filterTargets.find((t) => t.id == this.filterTargetID).name
  }
  private filterDebounce: Subject<string> = new Subject<string>()
  private unsubscribeNotifier: Subject<void> = new Subject<void>()

  public get filterTargets(): Array<{ id: number; name: string }> {
    return [
      { id: MailFilterTarget.Error, name: $localize`Error` },
      { id: MailFilterTarget.Subject, name: $localize`Subject` },
      { id: MailFilterTarget.Received, name: $localize`Received` },
      { id: MailFilterTarget.Processed, name: $localize`Processed` },
    ]
  }

  // RKC: Convert filter target enum to backend field name for server-side filtering
  private getFilterFieldName(): string {
    switch (this.filterTargetID) {
      case MailFilterTarget.Error:
        return 'error'
      case MailFilterTarget.Subject:
        return 'subject'
      case MailFilterTarget.Received:
        return 'received'
      case MailFilterTarget.Processed:
        return 'processed'
      default:
        return 'error'
    }
  }
  // /end RKC edit

  @Input() rule: MailRule

  ngOnInit(): void {
    this.loadProcessedMails()
    
    // RKC: Set up filter debouncing with server-side reload (500ms delay allows user to finish typing, min 3 chars)
    // When filter changes, reload data from backend with filter parameters
    this.filterDebounce
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        debounceTime(500),
        distinctUntilChanged(),
        filter((query) => !query.length || query.length > 2)
      )
      .subscribe((query) => {
        this._filterText = query
        this.page = 1 // Reset to first page when filter changes
        this.loadProcessedMails() // Reload with new filter from server
      })
    // /end RKC edit
  }

  ngOnDestroy(): void {
    // RKC: Clean up subscriptions
    this.unsubscribeNotifier.next()
    this.unsubscribeNotifier.complete()
    // /end RKC edit
  }

  public close() {
    this.activeModal.close()
  }

  private loadProcessedMails(): void {
    this.loading = true
    this.clearSelection()
    
    // RKC: Build params object with filter parameters for server-side filtering
    const params: any = { rule: this.rule.id }
    
    // Add filter parameters if filter is active (min 3 chars)
    if (this._filterText && this._filterText.length > 2) {
      params.filter_field = this.getFilterFieldName()
      params.filter_text = this._filterText
    }
    // /end RKC edit
    
    this.processedMailService
      .list(this.page, 50, 'processed_at', true, params)
      .subscribe((result) => {
        this.processedMails = result.results
        // RKC: Capture total count from API - now reflects filtered count for server-side filtering
        this.collectionSize = result.count
        // RKC: Store total unfiltered count on initial load to show alongside filtered results
        if (!this._filterText || this._filterText.length < 3) {
          this.totalUnfilteredCount = result.count
        }
        // /end RKC edit
        this.loading = false
      })
  }

  public deleteSelected(): void {
    this.processedMailService
      .bulk_delete(Array.from(this.selectedMailIds))
      .subscribe(() => {
        this.toastService.showInfo($localize`Processed mail(s) deleted`)
        this.loadProcessedMails()
      })
  }

  public toggleAll(event: PointerEvent) {
    if ((event.target as HTMLInputElement).checked) {
      this.selectedMailIds.clear()
      this.processedMails.forEach((mail) => this.selectedMailIds.add(mail.id))
    } else {
      this.clearSelection()
    }
  }

  public clearSelection() {
    this.toggleAllEnabled = false
    this.selectedMailIds.clear()
  }

  public toggleSelected(mail: ProcessedMail) {
    this.selectedMailIds.has(mail.id)
      ? this.selectedMailIds.delete(mail.id)
      : this.selectedMailIds.add(mail.id)
  }

  // RKC: Open modal dialog to display full error traceback
  public showErrorDetails(errorContent: string, subject: string): void {
    const modalRef = this.modalService.open(ErrorDetailModalComponent, {
      size: 'lg',
      scrollable: true,
    })
    modalRef.componentInstance.errorContent = errorContent
    modalRef.componentInstance.subject = subject
  }

  // RKC: Filter helper methods for server-side filtering (reload data when filter cleared)
  public resetFilter(): void {
    this._filterText = ''
    this.page = 1
    this.loadProcessedMails() // Reload data without filter
  }

  filterInputKeyup(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      this._filterText = (event.target as HTMLInputElement).value
    } else if (event.key === 'Escape') {
      this.resetFilter()
    }
  }
  // /end RKC edit
}

// RKC: Standalone modal component for displaying error details
@Component({
  selector: 'pngx-error-detail-modal',
  standalone: true,
  imports: [],
  template: `
    <div class="modal-header">
      <h6 class="modal-title">Error Details: {{ subject }}</h6>
      <button type="button" class="btn-close" aria-label="Close" (click)="activeModal.close()"></button>
    </div>
    <div class="modal-body">
      <pre class="small mb-0" style="white-space: pre-wrap; word-wrap: break-word;">{{ errorContent }}</pre>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" (click)="activeModal.close()">Close</button>
    </div>
  `,
})
export class ErrorDetailModalComponent {
  public readonly activeModal = inject(NgbActiveModal)
  @Input() errorContent: string = ''
  @Input() subject: string = ''
}
// /end RKC edit
