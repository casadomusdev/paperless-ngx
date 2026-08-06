import { Injectable } from '@angular/core'
import { PendingEmail } from 'src/app/data/pending-email'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class PendingEmailService extends AbstractPaperlessService<PendingEmail> {
  constructor() {
    super()
    this.resourceName = 'pending_email'
  }

  public bulk_delete(ids: number[]) {
    return this.http.post(`${this.getResourceUrl()}bulk_delete/`, {
      ids: ids,
    })
  }

  public bulk_delete_filtered(
    filterField: string,
    filterText: string
  ) {
    return this.http.post(`${this.getResourceUrl()}bulk_delete/`, {
      delete_all: true,
      filter_field: filterField,
      filter_text: filterText,
    })
  }
}
