# IMPLEMENT.md

## GOAL

Fix bug where personal saved views in the sidebar cannot be reordered via drag-drop. Views snap back to their original position after dropping.

## ANALYSIS

### Root Cause

In `app-frame.component.ts`, the `onDrop` method (line 258) operates on
`this.savedViewService.sidebarViews()` — the FULL list of sidebar views (global + personal).
But the `@for` template loop iterates over `userSidebarViews` (personal only). The drag event
indices (`previousIndex`, `currentIndex`) are personal-only indices, but `moveItemInArray`
applies them to the combined array. When global views exist, this moves the wrong items,
leaving personal views unchanged.

### Fix

Change `onDrop` to operate on `userSidebarViews` (same array the template iterates),
matching the dashboard component's correct pattern.

## IMPLEMENTATION

1. Fix `onDrop` in `app-frame.component.ts` — use `userSidebarViews` instead of full `sidebarViews`
2. Update test in `app-frame.component.spec.ts` — add `owner` fields to test data to cover the global/personal split scenario
