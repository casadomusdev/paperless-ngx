import { NgClass } from '@angular/common'
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
      useExisting: forwardRef(() => CheckComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-check',
  templateUrl: './check.component.html',
  styleUrls: ['./check.component.scss'],
  imports: [FormsModule, ReactiveFormsModule, NgClass, NgxBootstrapIconsModule],
})
export class CheckComponent extends AbstractInputComponent<boolean> {
  // RKC: Custom field filter support - enable filter button for checkbox inputs
  @Input()
  showFilter: boolean = false

  @Output()
  filterDocuments = new EventEmitter<boolean[]>()
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
