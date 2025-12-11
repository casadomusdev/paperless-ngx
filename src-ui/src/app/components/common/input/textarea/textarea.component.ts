import { Component, EventEmitter, Input, Output, forwardRef } from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => TextAreaComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-textarea',
  templateUrl: './textarea.component.html',
  styleUrls: ['./textarea.component.scss'],
  imports: [
    FormsModule,
    ReactiveFormsModule,
    SafeHtmlPipe,
    NgxBootstrapIconsModule,
  ],
})
export class TextAreaComponent extends AbstractInputComponent<string> {
  @Input()
  placeholder: string = ''

  @Input()
  monospace: boolean = false

  // RKC: Custom field filter support - enable filter button for long text inputs
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
