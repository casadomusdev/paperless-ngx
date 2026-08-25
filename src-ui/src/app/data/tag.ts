import { MatchingModel } from './matching-model'

export interface Tag extends MatchingModel {
  color?: string

  text_color?: string

  is_inbox_tag?: boolean

  // RKC: Hidden tags — suppress badge rendering in document list views (v1.6.0)
  is_hidden?: boolean
  // /end RKC edit

  parent?: number // Tag ID

  children?: Tag[] // read-only

  // UI-only: computed depth and order for hierarchical dropdowns
  depth?: number
  orderIndex?: number
}
