import { Component, EventEmitter, forwardRef, Input, Output } from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => UrlComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-url',
  templateUrl: './url.component.html',
  styleUrls: ['./url.component.scss'],
  imports: [NgxBootstrapIconsModule, FormsModule, ReactiveFormsModule],
})
export class UrlComponent extends AbstractInputComponent<string> {
  // RKC: Custom field filter support - enable filter button for URL inputs
  @Input()
  showFilter: boolean = false

  @Output()
  filterDocuments = new EventEmitter<string[]>()
  // /end RKC edit

  constructor() {
    super()
  }

  // RKC: Custom field filter support - emit filter event
  onFilterDocuments() {
    this.filterDocuments.emit([this.value])
  }

  get filterButtonTitle() {
    return $localize`Filter documents with this ${this.title}`
  }
  // /end RKC edit
}
