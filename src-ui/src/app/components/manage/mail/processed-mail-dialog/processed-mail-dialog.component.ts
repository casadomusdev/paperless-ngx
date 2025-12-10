import { SlicePipe } from '@angular/common'
import { Component, inject, Input, OnInit } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbActiveModal,
  NgbModal,
  NgbPagination,
  NgbPopoverModule,
  NgbTooltipModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { ConfirmButtonComponent } from 'src/app/components/common/confirm-button/confirm-button.component'
import { MailRule } from 'src/app/data/mail-rule'
import { ProcessedMail } from 'src/app/data/processed-mail'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { ProcessedMailService } from 'src/app/services/rest/processed-mail.service'
import { ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'pngx-processed-mail-dialog',
  imports: [
    ConfirmButtonComponent,
    CustomDatePipe,
    NgbPagination,
    NgbPopoverModule,
    NgbTooltipModule,
    NgxBootstrapIconsModule,
    FormsModule,
    ReactiveFormsModule,
    SlicePipe,
  ],
  templateUrl: './processed-mail-dialog.component.html',
  styleUrl: './processed-mail-dialog.component.scss',
})
export class ProcessedMailDialogComponent implements OnInit {
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
  // /end RKC edit

  @Input() rule: MailRule

  ngOnInit(): void {
    this.loadProcessedMails()
  }

  public close() {
    this.activeModal.close()
  }

  private loadProcessedMails(): void {
    this.loading = true
    this.clearSelection()
    this.processedMailService
      .list(this.page, 50, 'processed_at', true, { rule: this.rule.id })
      .subscribe((result) => {
        this.processedMails = result.results
        // RKC: Capture total count from API for proper pagination across all pages
        this.collectionSize = result.count
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
