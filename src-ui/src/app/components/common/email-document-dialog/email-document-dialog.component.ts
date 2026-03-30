import { Component, Input, OnInit, inject } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { CustomField } from 'src/app/data/custom-field'
import { CustomFieldInstance } from 'src/app/data/custom-field-instance'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-email-document-dialog',
  templateUrl: './email-document-dialog.component.html',
  styleUrl: './email-document-dialog.component.scss',
  imports: [FormsModule, NgxBootstrapIconsModule],
})
export class EmailDocumentDialogComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  private activeModal = inject(NgbActiveModal)
  private documentService = inject(DocumentService)
  private toastService = inject(ToastService)
  // RKC: Settings service for CF pre-fill (v1.3.0)
  private settingsService = inject(SettingsService)
  // /end RKC edit

  @Input() documentIds: number[]

  private _hasArchiveVersion: boolean = true

  @Input()
  set hasArchiveVersion(value: boolean) {
    this._hasArchiveVersion = value
    this.useArchiveVersion = value
  }

  get hasArchiveVersion(): boolean {
    return this._hasArchiveVersion
  }

  public useArchiveVersion: boolean = true
  public emailAddress: string = ''
  public emailSubject: string = ''
  public emailMessage: string = ''
  // RKC: Extended email fields (v1.3.0)
  public emailFrom: string = ''
  public emailCc: string = ''
  public emailBcc: string = ''
  // /end RKC edit

  // RKC: Custom field pre-fill inputs (v1.3.0)
  @Input() customFields: CustomField[] = []
  @Input() customFieldInstances: CustomFieldInstance[] = []
  // /end RKC edit

  constructor() {
    super()
    this.loading = false
  }

  // RKC: Pre-fill dialog fields from document custom fields (v1.3.0)
  ngOnInit() {
    if (!this.documentIds || this.documentIds.length !== 1) return
    const cfNames = this.settingsService.get(SETTINGS_KEYS.MAIL_CF_FIELD_NAMES) ?? {}
    const findCfValue = (cfName: string): string => {
      if (!cfName) return ''
      const def = this.customFields?.find((f) => f.name === cfName)
      if (!def) return ''
      const inst = this.customFieldInstances?.find((i) => i.field === def.id)
      if (!inst) return ''
      if (inst.value === null || inst.value === undefined || inst.value === '')
        return ''
      return String(inst.value)
    }
    if (!this.emailAddress) this.emailAddress = findCfValue(cfNames['to'])
    if (!this.emailSubject) this.emailSubject = findCfValue(cfNames['subject'])
    if (!this.emailFrom) this.emailFrom = findCfValue(cfNames['from'])
    if (!this.emailCc) this.emailCc = findCfValue(cfNames['cc'])
    if (!this.emailBcc) this.emailBcc = findCfValue(cfNames['bcc'])
    if (!this.emailMessage) this.emailMessage = findCfValue(cfNames['body'])
  }
  // /end RKC edit

  public emailDocuments() {
    this.loading = true
    this.documentService
      .emailDocuments(
        this.documentIds,
        this.emailAddress,
        this.emailSubject,
        this.emailMessage,
        this.useArchiveVersion,
        this.emailFrom || undefined,  // RKC: v1.3.0
        this.emailCc || undefined,    // RKC: v1.3.0
        this.emailBcc || undefined    // RKC: v1.3.0
      )
      .subscribe({
        next: () => {
          this.loading = false
          this.emailAddress = ''
          this.emailSubject = ''
          this.emailMessage = ''
          this.emailFrom = ''
          this.emailCc = ''
          this.emailBcc = ''
          this.close()
          this.toastService.showInfo($localize`Email sent`)
        },
        error: (e) => {
          this.loading = false
          const errorMessage =
            this.documentIds.length > 1
              ? $localize`Error emailing documents`
              : $localize`Error emailing document`
          this.toastService.showError(errorMessage, e)
        },
      })
  }

  public close() {
    this.activeModal.close()
  }
}
