import { ObjectWithPermissions } from './object-with-permissions'

export enum IMAPSecurity {
  None = 1,
  SSL = 2,
  STARTTLS = 3,
}

export enum MailAccountType {
  IMAP = 1,
  Gmail_OAuth = 2,
  Outlook_OAuth = 3,
}

export interface MailAccount extends ObjectWithPermissions {
  name: string

  imap_server: string

  imap_port: number

  imap_security: IMAPSecurity

  username: string

  password: string

  character_set?: string

  is_token: boolean

  account_type: MailAccountType

  expiration?: string // Date

  // RKC: SMTP email sending support (v1.1.0) - supports both OAuth2 and traditional
  use_for_sending?: boolean

  from_address?: string

  smtp_server?: string

  smtp_port?: number

  smtp_security?: string

  smtp_username?: string

  smtp_password?: string

  sending_account_info?: {
    changed: boolean
    previous_account: string
    previous_account_id: number
  }
  // /end RKC edit
}
