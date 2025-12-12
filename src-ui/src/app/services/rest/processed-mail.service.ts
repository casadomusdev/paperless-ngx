import { Injectable } from '@angular/core'
import { ProcessedMail } from 'src/app/data/processed-mail'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class ProcessedMailService extends AbstractPaperlessService<ProcessedMail> {
  constructor() {
    super()
    this.resourceName = 'processed_mail'
  }

  public bulk_delete(mailIds: number[]) {
    return this.http.post(`${this.getResourceUrl()}bulk_delete/`, {
      mail_ids: mailIds,
    })
  }

  // RKC: Add filter-based bulk deletion to support "select all in database" functionality
  // Allows deleting all entries matching current filter criteria instead of just selected IDs
  public bulk_delete_filtered(
    ruleId: number,
    filterField: string,
    filterText: string
  ) {
    return this.http.post(`${this.getResourceUrl()}bulk_delete/`, {
      delete_all: true,
      rule: ruleId,
      filter_field: filterField,
      filter_text: filterText,
    })
  }
  // /end RKC edit
}
