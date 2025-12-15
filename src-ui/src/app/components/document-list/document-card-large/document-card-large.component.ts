import { AsyncPipe } from '@angular/common'
import {
  AfterViewInit,
  Component,
  EventEmitter,
  Input,
  Output,
  ViewChild,
  inject,
} from '@angular/core'
import { RouterModule } from '@angular/router'
import {
  NgbProgressbarModule,
  NgbTooltipModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { delay, of } from 'rxjs'
import { CustomField } from 'src/app/data/custom-field'
import { CustomFieldInstance } from 'src/app/data/custom-field-instance'
import {
  DEFAULT_DISPLAY_FIELDS,
  DisplayField,
  Document,
} from 'src/app/data/document'
import { FilterRule } from 'src/app/data/filter-rule'
import { FILTER_CUSTOM_FIELDS_QUERY } from 'src/app/data/filter-rule-type'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CorrespondentNamePipe } from 'src/app/pipes/correspondent-name.pipe'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { DocumentTypeNamePipe } from 'src/app/pipes/document-type-name.pipe'
import { IsNumberPipe } from 'src/app/pipes/is-number.pipe'
import { StoragePathNamePipe } from 'src/app/pipes/storage-path-name.pipe'
import { UsernamePipe } from 'src/app/pipes/username.pipe'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CustomFieldDisplayComponent } from '../../common/custom-field-display/custom-field-display.component'
import { PreviewPopupComponent } from '../../common/preview-popup/preview-popup.component'
import { TagComponent } from '../../common/tag/tag.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-document-card-large',
  templateUrl: './document-card-large.component.html',
  styleUrls: ['./document-card-large.component.scss'],
  imports: [
    DocumentTitlePipe,
    IsNumberPipe,
    PreviewPopupComponent,
    TagComponent,
    CustomFieldDisplayComponent,
    AsyncPipe,
    UsernamePipe,
    CorrespondentNamePipe,
    DocumentTypeNamePipe,
    StoragePathNamePipe,
    IfPermissionsDirective,
    CustomDatePipe,
    RouterModule,
    NgbTooltipModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
  ],
})
export class DocumentCardLargeComponent
  extends LoadingComponentWithPermissions
  implements AfterViewInit
{
  private documentService = inject(DocumentService)
  settingsService = inject(SettingsService)
  // RKC: Add services for custom field filtering
  private documentListViewService = inject(DocumentListViewService)
  private customFieldsService = inject(CustomFieldsService)
  // /end RKC edit

  DisplayField = DisplayField

  @Input()
  selected = false

  @Input()
  displayFields: string[] = DEFAULT_DISPLAY_FIELDS.map((f) => f.id)

  @Output()
  toggleSelected = new EventEmitter()

  get selectable() {
    return this.toggleSelected.observers.length > 0
  }

  @Input()
  document: Document

  @Output()
  dblClickDocument = new EventEmitter()

  @Output()
  clickTag = new EventEmitter<number>()

  @Output()
  clickCorrespondent = new EventEmitter<number>()

  @Output()
  clickDocumentType = new EventEmitter<number>()

  @Output()
  clickStoragePath = new EventEmitter<number>()

  @Output()
  clickMoreLike = new EventEmitter()

  @ViewChild('popupPreview') popupPreview: PreviewPopupComponent

  mouseOnPreview = false
  popoverHidden = true

  ngAfterViewInit(): void {
    of(true)
      .pipe(delay(50))
      .subscribe(() => {
        this.show = true
      })
  }

  get searchScoreClass() {
    if (this.document.__search_hit__) {
      if (this.document.__search_hit__.score > 0.7) {
        return 'success'
      } else if (this.document.__search_hit__.score > 0.3) {
        return 'warning'
      } else {
        return 'danger'
      }
    }
  }

  get searchNoteHighlights() {
    let highlights = []
    if (
      this.document['__search_hit__'] &&
      this.document['__search_hit__'].note_highlights
    ) {
      // only show notes with a match
      highlights = (this.document['__search_hit__'].note_highlights as string)
        .split(',')
        .filter((highlight) => highlight.includes('<span'))
    }
    return highlights
  }

  getIsThumbInverted() {
    return this.settingsService.get(SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED)
  }

  getThumbUrl() {
    return this.documentService.getThumbUrl(this.document.id)
  }

  getDownloadUrl() {
    return this.documentService.getDownloadUrl(this.document.id)
  }

  mouseLeaveCard() {
    this.popupPreview?.close()
  }

  get contentTrimmed() {
    return (
      this.document.content.substring(0, 500) +
      (this.document.content.length > 500 ? '...' : '')
    )
  }

  get notesEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
  }

  // RKC: Filter documents by custom field value
  filterByCustomField(fieldInstance: CustomFieldInstance) {
    // Get the custom field definition
    this.customFieldsService.getCached(fieldInstance.field).subscribe(
      (field: CustomField) => {
        if (!field) return

        // Construct the custom field query in the format: ["FieldName", "exact", "value"]
        // The value can be null/empty - that's a valid filter condition
        const queryValue = JSON.stringify([
          field.name,
          'exact',
          fieldInstance.value?.toString() ?? '',
        ])

        const filterRule: FilterRule = {
          rule_type: FILTER_CUSTOM_FIELDS_QUERY,
          value: queryValue,
        }

        this.documentListViewService.quickFilter([filterRule])
      }
    )
  }
  // /end RKC edit
}
