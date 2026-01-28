import { Component, ViewChild, inject } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbAlert, NgbAlertModule } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { IMAPSecurity, MailAccount, MailAccountType } from 'src/app/data/mail-account'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CheckComponent } from '../../input/check/check.component'
import { PasswordComponent } from '../../input/password/password.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'

const IMAP_SECURITY_OPTIONS = [
  { id: IMAPSecurity.None, name: $localize`No encryption` },
  { id: IMAPSecurity.SSL, name: $localize`SSL` },
  { id: IMAPSecurity.STARTTLS, name: $localize`STARTTLS` },
]

// RKC: SMTP security options (v1.1.0)
const SMTP_SECURITY_OPTIONS = [
  { id: 'SSL', name: $localize`SSL` },
  { id: 'STARTTLS', name: $localize`STARTTLS` },
  { id: 'NONE', name: $localize`None` },
]
// /end RKC edit

@Component({
  selector: 'pngx-mail-account-edit-dialog',
  templateUrl: './mail-account-edit-dialog.component.html',
  styleUrls: ['./mail-account-edit-dialog.component.scss'],
  imports: [
    TextComponent,
    CheckComponent,
    PasswordComponent,
    SelectComponent,
    FormsModule,
    ReactiveFormsModule,
    NgbAlertModule,
  ],
})
export class MailAccountEditDialogComponent extends EditDialogComponent<MailAccount> {
  testActive: boolean = false
  testResult: string
  alertTimeout

  @ViewChild('testResultAlert', { static: false }) testResultAlert: NgbAlert

  constructor() {
    super()
    this.service = inject(MailAccountService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)
  }

  getCreateTitle() {
    return $localize`Create new mail account`
  }

  getEditTitle() {
    return $localize`Edit mail account`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      imap_server: new FormControl(null),
      imap_port: new FormControl(null),
      imap_security: new FormControl(IMAPSecurity.SSL),
      username: new FormControl(null),
      password: new FormControl(null),
      is_token: new FormControl(false),
      character_set: new FormControl('UTF-8'),
      // RKC: SMTP email sending support (v1.1.0)
      use_for_sending: new FormControl(false),
      from_address: new FormControl(null),
      smtp_server: new FormControl(null),
      smtp_port: new FormControl(null),
      smtp_security: new FormControl(null),
      smtp_username: new FormControl(null),
      smtp_password: new FormControl(null),
      // /end RKC edit
    })
  }

  get imapSecurityOptions() {
    return IMAP_SECURITY_OPTIONS
  }

  // RKC: SMTP security options (v1.1.0)
  get smtpSecurityOptions() {
    return SMTP_SECURITY_OPTIONS
  }

  get isTraditionalAccount(): boolean {
    return this.objectForm.get('account_type')?.value === MailAccountType.IMAP ||
           !this.object?.account_type ||
           this.object?.account_type === MailAccountType.IMAP
  }

  onSendingToggle() {
    const usedForSending = this.objectForm.get('use_for_sending')?.value
    if (usedForSending) {
      this.setDefaultSmtpConfig()
    }
  }

  setDefaultSmtpConfig() {
    const accountType = this.object?.account_type || MailAccountType.IMAP
    const smtpServer = this.objectForm.get('smtp_server')
    const smtpPort = this.objectForm.get('smtp_port')
    const smtpSecurity = this.objectForm.get('smtp_security')

    // Only set defaults if fields are empty
    if (!smtpServer?.value) {
      if (accountType === MailAccountType.Gmail_OAuth) {
        smtpServer?.setValue('smtp.gmail.com')
        smtpPort?.setValue(587)
        smtpSecurity?.setValue('STARTTLS')
      } else if (accountType === MailAccountType.Outlook_OAuth) {
        smtpServer?.setValue('smtp.office365.com')
        smtpPort?.setValue(587)
        smtpSecurity?.setValue('STARTTLS')
      }
    }
  }

  override save() {
    // RKC: Check if sending account is being changed and show warning (v1.1.0)
    const usedForSending = this.objectForm.get('use_for_sending')?.value
    if (usedForSending && this.object?.id) {
      // Check if there's already a sending account (we'll get this info from the API response)
      // For now, just show a general warning
      const confirmed = confirm(
        $localize`Enabling this account for sending will disable any other accounts currently used for sending. Continue?`
      )
      if (!confirmed) {
        return
      }
    }
    // /end RKC edit
    
    super.save()
  }
  // /end RKC edit

  test() {
    this.testActive = true
    this.testResult = null
    clearTimeout(this.alertTimeout)
    const mailService = this.service as MailAccountService
    const newObject = Object.assign(
      Object.assign({}, this.object),
      this.objectForm.value
    )
    mailService.test(newObject).subscribe({
      next: (result: { success: boolean }) => {
        this.testActive = false
        this.testResult = result.success ? 'success' : 'danger'
        this.alertTimeout = setTimeout(() => this.testResultAlert.close(), 5000)
      },
      error: (e) => {
        this.testActive = false
        this.testResult = 'danger'
        this.alertTimeout = setTimeout(() => this.testResultAlert.close(), 5000)
      },
    })
  }

  get testResultMessage() {
    return this.testResult === 'success'
      ? $localize`Successfully connected to the mail server`
      : $localize`Unable to connect to the mail server`
  }
}
