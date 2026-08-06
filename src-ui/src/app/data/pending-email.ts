import { ObjectWithId } from './object-with-id'

export interface PendingEmail extends ObjectWithId {
  action: number | null
  document: number | null
  subject_template: string
  rendered_to: string
  status: string
  attempts: number
  max_attempts: number
  next_retry_at: Date
  last_error: string
  created_at: Date
  updated_at: Date
}
