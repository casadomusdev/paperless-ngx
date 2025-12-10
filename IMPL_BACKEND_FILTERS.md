# Server-Side Filtering Implementation Plan

## Overview

This document outlines the plan to implement server-side filtering for both the Processed Mail dialog and File Tasks page in Paperless-ngx. Currently, both use client-side filtering which only works on the current page of results (max 50 items). Server-side filtering will enable searching across the entire dataset and provide accurate filtered counts.

## Goals

1. **Enable full-dataset filtering**: Search across all entries, not just current page
2. **Accurate filtered counts**: Display total number of matching entries across all pages
3. **Maintain consistency**: Apply same filtering pattern to both Processed Mail and File Tasks
4. **Preserve performance**: Ensure database queries remain efficient
5. **Follow RKC conventions**: All changes properly marked and documented

## RKC Commenting and Documentation Conventions

All code changes must follow these conventions:

### Backend (Python)
```python
# RKC: Brief description of what the change does and why
# ... code here ...
# /end RKC edit
```

### Frontend (TypeScript)
```typescript
// RKC: Brief description of what the change does and why
// ... code here ...
// /end RKC edit
```

### Frontend (HTML)
```html
<!-- RKC: Brief description of what the change does and why -->
<!-- ... code here ... -->
<!-- /end RKC edit -->
```

### Documentation Updates
- Add entry to `RKC_CUSTOMIZATIONS.md` version history
- Include v1.0.16 entry documenting server-side filtering implementation
- Update relevant sections with new functionality details

## Backend Implementation

### Phase 1: Processed Mail API Endpoint

**File**: `src/paperless_mail/views.py` (or wherever ProcessedMailViewSet is located)

**Current State**: 
- API endpoint returns paginated results (50 per page)
- No filtering parameters accepted
- Query: `ProcessedMail.objects.filter(rule=rule_id).order_by('-processed_at')`

**Required Changes**:

1. **Accept new query parameters**:
   - `filter_field` (optional): Field to filter on ('error', 'subject', 'received', 'processed')
   - `filter_text` (optional): Search term (case-insensitive)

2. **Modify queryset filtering**:
   ```python
   # RKC: Add server-side filtering support for processed mail
   queryset = ProcessedMail.objects.filter(rule=rule_id)
   
   filter_field = request.query_params.get('filter_field', None)
   filter_text = request.query_params.get('filter_text', None)
   
   if filter_field and filter_text:
       if filter_field == 'error':
           queryset = queryset.filter(error__icontains=filter_text)
       elif filter_field == 'subject':
           queryset = queryset.filter(subject__icontains=filter_text)
       elif filter_field == 'received':
           # For datetime fields, search formatted string representation
           queryset = queryset.filter(received__icontains=filter_text)
       elif filter_field == 'processed':
           queryset = queryset.filter(processed__icontains=filter_text)
   
   queryset = queryset.order_by('-processed_at')
   # /end RKC edit
   ```

3. **Response format** (should already be correct):
   - `count`: Total number of filtered results
   - `results`: Current page of filtered results
   - `next`/`previous`: Pagination URLs

**Database Considerations**:
- `__icontains` performs case-insensitive search (uses ILIKE on PostgreSQL)
- Consider adding database indexes if performance becomes an issue:
  - Index on `error` field (if not already indexed)
  - Index on `subject` field (if not already indexed)
- For datetime fields, search works on string representation (acceptable for current use case)

### Phase 2: File Tasks API Endpoint

**File**: `src/documents/views.py` (FileTasksViewSet or similar)

**Current State**:
- API endpoint returns paginated file tasks
- No filtering parameters accepted

**Required Changes**:

1. **Accept same query parameters**:
   - `filter_field` (optional): Field to filter on ('name', 'created', 'result')
   - `filter_text` (optional): Search term (case-insensitive)

2. **Modify queryset filtering**:
   ```python
   # RKC: Add server-side filtering support for file tasks
   queryset = PaperlessTask.objects.all()
   
   filter_field = request.query_params.get('filter_field', None)
   filter_text = request.query_params.get('filter_text', None)
   
   if filter_field and filter_text:
       if filter_field == 'name':
           queryset = queryset.filter(task_file_name__icontains=filter_text)
       elif filter_field == 'created':
           queryset = queryset.filter(date_created__icontains=filter_text)
       elif filter_field == 'result':
           queryset = queryset.filter(result__icontains=filter_text)
   
   # Maintain existing ordering and status filtering
   # /end RKC edit
   ```

3. **Note**: File tasks page has multiple tabs (Failed, Complete, Started, Queued)
   - Filtering should work within the current tab
   - Backend already filters by status, add text filtering on top

## Frontend Implementation

### Phase 3: Processed Mail Dialog Frontend

**File**: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.ts`

**Current State**:
- Client-side filtering via `filteredMails` getter
- Filter parameters not sent to backend
- Debouncing implemented for UX

**Required Changes**:

1. **Remove client-side filtering**:
   ```typescript
   // RKC: Remove client-side filtering - now done server-side
   // Delete the filteredMails getter entirely
   // /end RKC edit
   ```

2. **Modify loadProcessedMails() to send filter params**:
   ```typescript
   // RKC: Send filter parameters to backend for server-side filtering
   private loadProcessedMails(): void {
     this.loading = true
     this.clearSelection()
     
     const params: any = { rule: this.rule.id }
     
     // Add filter parameters if active
     if (this._filterText && this._filterText.length > 2) {
       params.filter_field = this.getFilterFieldName()
       params.filter_text = this._filterText
     }
     
     this.processedMailService
       .list(this.page, 50, 'processed_at', true, params)
       .subscribe((result) => {
         this.processedMails = result.results
         this.collectionSize = result.count // Now reflects filtered count
         this.loading = false
       })
   }
   
   private getFilterFieldName(): string {
     switch (this.filterTargetID) {
       case MailFilterTarget.Error: return 'error'
       case MailFilterTarget.Subject: return 'subject'
       case MailFilterTarget.Received: return 'received'
       case MailFilterTarget.Processed: return 'processed'
       default: return 'error'
     }
   }
   // /end RKC edit
   ```

3. **Update filter debounce subscription**:
   ```typescript
   // RKC: Reload data when filter changes (server-side filtering)
   this.filterDebounce
     .pipe(
       takeUntil(this.unsubscribeNotifier),
       debounceTime(100),
       distinctUntilChanged(),
       filter((query) => !query.length || query.length > 2)
     )
     .subscribe((query) => {
       this._filterText = query
       this.page = 1 // Reset to first page when filter changes
       this.loadProcessedMails() // Reload with new filter
     })
   // /end RKC edit
   ```

4. **Update resetFilter() method**:
   ```typescript
   // RKC: Reload data when filter is cleared
   public resetFilter(): void {
     this._filterText = ''
     this.page = 1
     this.loadProcessedMails()
   }
   // /end RKC edit
   ```

**File**: `src-ui/src/app/components/manage/mail/processed-mail-dialog/processed-mail-dialog.component.html`

**Required Changes**:

1. **Update table loop** (change back from filteredMails to processedMails):
   ```html
   <!-- RKC: Use processedMails directly - filtering now done server-side -->
   @for (mail of processedMails; track mail.id) {
   <!-- /end RKC edit -->
   ```

2. **Update filtered count display**:
   ```html
   <!-- RKC: Show filtered count from server (collectionSize reflects filtered total) -->
   <div class="text-muted" style="width: 50%; padding-right: 1rem;">
     @if (filterText?.length) {
       <ng-container i18n>{collectionSize, plural, =1 {One entry matches filter} other {{{collectionSize}} entries match filter}}</ng-container>
     } @else {
       <ng-container i18n>{collectionSize, plural, =1 {One total email message processed} other {{{collectionSize}} total entries of emails processed}}</ng-container>
     }
   </div>
   <!-- /end RKC edit -->
   ```

### Phase 4: File Tasks Frontend

**File**: `src-ui/src/app/components/admin/tasks/tasks.component.ts`

**Current State**:
- Client-side filtering via computed property `currentTasks`
- Filter parameters not sent to backend
- Multiple tabs with different task statuses

**Required Changes**:

1. **Identify the API call method** (likely in TasksService)
   - Update to send filter parameters: `filter_field`, `filter_text`

2. **Remove client-side filtering**:
   - Delete or modify the filtering logic in `currentTasks` getter
   - Make it simply return the tasks array from API

3. **Update filter change handler**:
   - Reset to page 1 when filter changes
   - Reload data from backend with new filter params

4. **Handle tab switching**:
   - Maintain filter when switching tabs
   - Reload data for new tab with current filter applied

**File**: `src-ui/src/app/components/admin/tasks/tasks.component.html`

**Required Changes**:

1. **Update filtered count display** (if applicable)
   - Show count from API response instead of client-side filtered array length

### Phase 5: Service Layer Updates

**File**: `src-ui/src/app/services/rest/processed-mail.service.ts`

**Current State**:
- `list()` method likely doesn't pass arbitrary params

**Required Changes**:
- Ensure `list()` method passes through filter parameters to API
- If using generic REST service, verify params are properly passed

**File**: `src-ui/src/app/services/rest/tasks.service.ts` (or similar)

**Current State**:
- Service for file tasks API calls

**Required Changes**:
- Ensure filter parameters are passed through to API
- May need to add or modify method signatures

## Testing Strategy

### Backend Testing

1. **Manual API Testing** (via curl or Postman):
   ```bash
   # Test processed mail filtering
   GET /api/processed_mail/?rule=1&filter_field=error&filter_text=timeout
   GET /api/processed_mail/?rule=1&filter_field=subject&filter_text=invoice
   
   # Test file tasks filtering
   GET /api/tasks/?filter_field=name&filter_text=document.pdf
   GET /api/tasks/?filter_field=result&filter_text=error
   ```

2. **Verify Response**:
   - Check that `count` reflects filtered total
   - Verify `results` contain only matching items
   - Confirm pagination works correctly with filters

3. **Edge Cases**:
   - Empty filter text (should return all results)
   - Filter text with special characters
   - Case sensitivity (should be case-insensitive)
   - Non-existent filter field (should handle gracefully)

### Frontend Testing

1. **Processed Mail Dialog**:
   - Open dialog, apply filter, verify results update
   - Check filtered count matches server response
   - Verify pagination shows correct total pages
   - Test filter reset
   - Test switching filter fields
   - Test debouncing (no request until 3+ chars)

2. **File Tasks Page**:
   - Apply filter on each tab (Failed, Complete, Started, Queued)
   - Verify filter persists when switching tabs
   - Check filtered count display
   - Test pagination with filters active

3. **Performance Testing**:
   - Test with large datasets (1000+ entries)
   - Verify reasonable response times
   - Check for any UI lag or freezing

### Integration Testing

1. **Filter + Pagination**:
   - Apply filter resulting in 100+ matches
   - Navigate through pages
   - Verify results stay filtered on all pages

2. **Filter + Selection**:
   - Apply filter, select items, remove filter
   - Verify selections are preserved/cleared appropriately

3. **Filter + Delete**:
   - Filter results, delete some items
   - Verify filtered count updates correctly

## Implementation Sequence

### Recommended Order

1. **Phase 1**: Implement Processed Mail backend filtering
2. **Phase 3**: Update Processed Mail frontend to use server-side filtering
3. **Test**: Thoroughly test Processed Mail implementation
4. **Phase 2**: Implement File Tasks backend filtering
5. **Phase 4**: Update File Tasks frontend to use server-side filtering
6. **Test**: Thoroughly test File Tasks implementation
7. **Phase 5**: Verify/update service layer as needed
8. **Documentation**: Update RKC_CUSTOMIZATIONS.md with v1.0.16 entry

### Why This Order?

1. Start with Processed Mail (smaller, simpler implementation)
2. Learn from any issues before tackling File Tasks
3. File Tasks has more complexity (multiple tabs, status filtering)
4. Incremental testing reduces debugging time

## Potential Issues and Solutions

### Issue 1: Performance with Large Datasets

**Problem**: `__icontains` can be slow on large tables without indexes

**Solution**:
- Add database indexes on filtered fields
- Consider using PostgreSQL full-text search for better performance
- Monitor query performance with Django Debug Toolbar

### Issue 2: Datetime Field Filtering

**Problem**: Searching datetime fields by string representation may not work well

**Solution**:
- For date/time fields, consider separate date range filtering
- Or parse filter text as date and use date range queries
- Current string search is acceptable for MVP but may need improvement

### Issue 3: Multiple Filter Fields Simultaneously

**Current Plan**: Only one field at a time

**Future Enhancement**: 
- Could support multiple fields with AND/OR logic
- Would require more complex query building
- Not needed for v1.0.16

### Issue 4: Special Characters in Filter Text

**Problem**: SQL injection or regex characters could cause issues

**Solution**:
- Django ORM handles SQL escaping automatically
- `__icontains` is safe for user input
- No additional escaping needed

## Documentation Updates

### RKC_CUSTOMIZATIONS.md Entry

Add this to version history:

```markdown
- **v1.0.16 (2025-01-12)**: Server-side filtering for Processed Mail and File Tasks
  - Migrated from client-side to server-side filtering for better search capabilities
  - **Problem**: Client-side filtering only worked on current page (max 50 items)
  - **Solution**: 
    - Backend accepts `filter_field` and `filter_text` query parameters
    - Database queries filter entire dataset, not just current page
    - Accurate filtered counts displayed across all entries
    - Significant improvement for finding specific items in large datasets
  - **Filter Fields**:
    - Processed Mail: Error, Subject, Received, Processed
    - File Tasks: Name, Created, Result
  - **Features**:
    - Case-insensitive search across entire dataset
    - Pagination works correctly with filters
    - Debounced input (100ms, 3-char minimum) for performance
    - Filter resets to page 1 when changed
  - **Performance**:
    - Database indexes recommended for large datasets
    - Uses Django ORM `__icontains` for safe, efficient queries
  - Files modified:
    - Backend: `src/paperless_mail/views.py` (ProcessedMail filtering)
    - Backend: `src/documents/views.py` (FileTask filtering)
    - Frontend: `src-ui/src/app/components/manage/mail/processed-mail-dialog/*`
    - Frontend: `src-ui/src/app/components/admin/tasks/*`
  - All changes properly marked with RKC comments for maintainability
```

## Success Criteria

Implementation is complete when:

1. ✅ Processed Mail dialog filters across all entries in database
2. ✅ File Tasks page filters across all tasks in database
3. ✅ Filtered counts show total matches across all pages
4. ✅ Pagination works correctly with active filters
5. ✅ Filter reset clears filter and reloads all data
6. ✅ All changes marked with RKC comments
7. ✅ RKC_CUSTOMIZATIONS.md updated with v1.0.16 entry
8. ✅ Manual testing passes all scenarios
9. ✅ No performance degradation with large datasets
10. ✅ Both components follow same pattern for consistency

## Rollback Plan

If issues arise:

1. Revert frontend changes (go back to client-side filtering)
2. Revert backend changes (remove filter parameters)
3. Previous v1.0.15 implementation still works as fallback
4. No data migrations required, safe to roll back

## Future Enhancements (Not in v1.0.16)

1. **Advanced Filtering**:
   - Multi-field filtering (search multiple fields simultaneously)
   - Boolean operators (AND, OR, NOT)
   - Date range filtering for datetime fields

2. **Performance Optimization**:
   - PostgreSQL full-text search for better text search
   - Elasticsearch integration for very large datasets
   - Database indexes on commonly filtered fields

3. **UI Enhancements**:
   - Saved filters/search templates
   - Recent searches history
   - Filter presets (e.g., "Failed emails last week")

4. **Analytics**:
   - Most common search terms
   - Filter usage statistics
   - Performance monitoring

---

**Document Version**: 1.0  
**Created**: 2025-01-12  
**Last Updated**: 2025-01-12  
**Status**: Ready for Implementation
