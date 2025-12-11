# RKC Pull Request Plan for Paperless-ngx

This document outlines the strategy for contributing RKC customizations back to the Paperless-ngx open-source project.

## Overview

We have developed 23 customizations to Paperless-ngx for our deployment. After reviewing the project's contribution guidelines, we've categorized these customizations by their suitability for upstream contribution.

## Contribution Requirements (from CONTRIBUTING.md)

⚠️ **Critical Requirements:**
- PRs implementing new features **must target an existing feature request** with community interest
- Changes should benefit the majority of users
- Must not interfere with users who don't want the feature
- Python code formatted with `ruff`
- Must pass `pytest` tests
- Non-trivial PRs need at least 2 team member approvals

## Customization Categories & PR Strategy

### TIER 1: BUGFIXES - Highest Priority ⭐

**Bug fixes don't require feature requests and can be submitted immediately. These should be our first PRs:**

#### 1. Dashboard Race Condition Fix (v1.0.23) 🆕
- **Type**: Bug fix
- **Impact**: Fixes empty dashboard when directly accessing `/dashboard` URL or refreshing page
- **Root Cause**: Computed signals reading from non-reactive getters
- **Files**: 3 frontend files (SavedViewService + DashboardComponent + AppFrameComponent)
- **Why excellent PR**: 
  - **Fixes real user-facing bug** - dashboard appears broken on page refresh
  - Clean Angular signals solution following framework best practices
  - Well-documented with clear root cause analysis
  - No breaking changes, pure reactivity fix
  - Upstream will appreciate proper Angular patterns
- **Effort**: Medium
- **PR Strategy**: 
  - Submit as bug fix (no feature request needed)
  - Create reproduction steps in vanilla Paperless-ngx
  - Emphasize proper reactive Angular patterns
  - Reference Angular signals documentation
  - Clear before/after behavior description

#### 2. Card Views Date Format Bug Fix (v1.0.22)
- **Type**: Bug fix
- **Impact**: Fixes hardcoded date format in card views, makes them respect user preferences
- **Files**: 2 template files
- **Why good PR**: 
  - Pure bug fix - no breaking changes
  - Aligns card views with table view behavior
  - Already working functionality in table view
- **Effort**: Low
- **PR Strategy**: 
  - Can be submitted immediately (bug fixes don't require feature request)
  - Search for related issues about card view date formatting
  - Simple, focused PR with clear before/after

#### 3. Processed Mail Pagination Fix (v1.0.13)
- **Type**: Bug fix
- **Impact**: Fixed broken pagination in processed mail dialog
- **Problem**: Pagination showed only "<< 1 >>" even with multiple pages
- **Files**: 2 frontend files (TypeScript + HTML)
- **Why good PR**: 
  - Clear bug - pagination completely broken
  - Simple fix - use correct total count from API
  - Easy to reproduce and verify
- **Effort**: Low
- **PR Strategy**: 
  - Submit as bug fix (no feature request needed)
  - Provide steps to reproduce with many processed mails
  - Show before/after screenshots

### TIER 2: ENHANCEMENTS - High Priority

**Strong PR candidates with broad appeal. Require feature request validation first:**

#### 4. Date+Time Format Options (v1.0.21)
- **Type**: Enhancement
- **Impact**: Adds 4 new date+time display formats to complement existing date-only formats
- **Files**: 1 template + 2 translation files
- **Why good PR**: 
  - Clear user benefit - see actual timestamps instead of just dates
  - Uses native Angular DatePipe - no custom code
  - Backward compatible - just adds more options
  - Users requested time display in documents
- **Effort**: Medium
- **PR Strategy**: 
  - Search GitHub discussions for "time display" or "timestamp" requests
  - If found, reference in PR description
  - Emphasize zero performance impact
  - Provide screenshots showing the new options

#### 5. Custom Field Filter Buttons (v1.0.6)
- **Type**: UX Enhancement
- **Impact**: Quick filtering by custom field values (all 10 field types)
- **Files**: 10 input components + translations
- **Why good PR**: 
  - Improves UX consistency (matches existing filter buttons)
  - Works with existing filter infrastructure
  - No configuration needed - automatically works
  - Supports null/empty values
- **Effort**: Medium
- **PR Strategy**: 
  - Search for feature requests about custom field filtering
  - Highlight consistency with existing correspondent/document type filters
  - Emphasize "no configuration required"
  - Demonstrate with GIF/video of the feature

#### 6. OAuth2 Email Sending Support (v1.0.18)
- **Type**: Major Feature
- **Impact**: Enables OAuth2 for outgoing SMTP (Gmail/Outlook)
- **Files**: Backend models, migrations, new OAuth backend
- **Why good PR**: 
  - Eliminates need for separate SMTP credentials
  - High community value (OAuth2 becoming standard)
  - Organizations using OAuth2 for receiving should use it for sending
  - Security improvement
- **Effort**: High
- **PR Strategy**: 
  - **REQUIRES feature request discussion first** (per CONTRIBUTING.md)
  - Search for OAuth2 sending requests
  - If none exist, create feature request in GitHub Discussions
  - Wait for community interest (upvotes, comments)
  - Non-trivial PR - will need 2+ maintainer approvals
  - Provide detailed testing instructions
  - Document fallback to SMTP behavior

#### 7. Mail Action "Process All Mails" (v1.0.19)
- **Type**: Feature Enhancement
- **Impact**: Process read+unread mails without modification
- **Files**: 2 backend files (enum + action class)
- **Why good PR**: 
  - Useful for archive folders
  - Clean architecture - follows existing patterns
  - Small code footprint
- **Effort**: Low
- **PR Strategy**: 
  - Search for mail processing feature requests
  - Emphasize use case: processing historical archives
  - Highlight non-invasive nature (leaves mails untouched)

### TIER 3: Medium Priority - Context-Dependent

**Valuable but may need feature request validation:**

#### 8. Processed Mail Enhancements (v1.0.14-15, v1.0.20)
- **Components**: Filtering, error details modal, UID column
- **Why possibly good**: Significantly improves mail debugging
- **Concern**: Multiple related changes - may need bundling discussion
- **PR Strategy**: 
  - Could bundle as single "Mail Management UX Improvements" PR
  - Or split into separate PRs (filtering vs. enhancements)
  - Search for issues about mail processing debugging

#### 9. Mail-Document Correlation via Custom Fields (v1.0.12)
- **Type**: Feature
- **Why possibly good**: Enables email tracking
- **Concern**: Requires custom field setup, may be niche use case
- **PR Strategy**: 
  - Search for mail-document correlation feature requests
  - Emphasize value for auditing/compliance scenarios
  - Make it optional via environment variable

#### 10. Mail Action Connection Pooling (v1.0.17)
- **Type**: Performance Fix
- **Why good**: Eliminates OAuth2 rate limiting storms
- **Concern**: Complex change to Celery architecture
- **PR Strategy**: 
  - Search for issues about mail processing performance or OAuth2 errors
  - Provide detailed explanation of the problem
  - Include performance metrics if possible

### TIER 4: Low Priority - Organization-Specific

**Valuable for our use case but may not have broad appeal:**

#### 11. Global Saved Views (v1.0.6, 9, 10, 11)
- **Concern**: Very organization-specific, complex UI changes
- **Strategy**: Probably keep private unless many users request it

#### 12. PDF Editor Restriction (v1.0.8)
- **Concern**: Optional security feature, not universal need
- **Strategy**: Could propose as optional env var if there's interest

#### 13. UI Defaults (Theme, Language, Dark Mode)
- **Concern**: Personal preference, not core functionality
- **Strategy**: Low priority unless specifically requested

#### 14. SSO Debug Logging (v1.0.5)
- **Concern**: Troubleshooting aid, not production feature
- **Strategy**: Very low priority

## Recommended First PRs

**Start with bugfixes first to build trust and establish contribution pattern. Bug fixes are always welcome and don't require feature request discussions:**

### Phase 1: Immediate Bug Fix Submissions (No Feature Request Needed)

1. **Dashboard Race Condition Fix** (v1.0.23) - NEW! ⭐
   - Critical bug affecting user experience
   - Clean reactive solution
   - Shows understanding of Angular best practices
   - Will impress maintainers

2. **Card Views Date Format Bug Fix** (v1.0.22)
   - Pure bug fix
   - Simple, focused  
   - Easy review

3. **Processed Mail Pagination Fix** (v1.0.13)
   - Simple fix
   - Clear before/after
   - Low risk

### Phase 2: After Feature Request Discussion

4. **Date+Time Format Options** (v1.0.21)
   - Small, clean enhancement
   - Clear user value
   - Low risk

5. **Custom Field Filter Buttons** (v1.0.6) OR **OAuth2 Email Sending** (v1.0.18)
   - Choose based on which has more community interest
   - OAuth2 is bigger impact but requires more review
   - Custom field filters are safer bet for acceptance

## Implementation Plan

### Phase 1: Research & Preparation
- [ ] Search GitHub Discussions for related feature requests
- [ ] Search GitHub Issues for related bugs
- [ ] Review recent PRs to understand current merge patterns
- [ ] Fork the paperless-ngx repository
- [ ] Set up local development environment

### Phase 2: Bug Fix PRs (All Three)
- [ ] Create feature branch for dashboard race condition
- [ ] Extract dashboard signal conversion fix (clean, isolated changes)
- [ ] Test changes locally on vanilla Paperless-ngx
- [ ] Create PR with detailed root cause analysis
- [ ] Reference Angular signals best practices
- [ ] Respond to review feedback

- [ ] Create feature branch for card view date format
- [ ] Extract card view fixes (2 template files)
- [ ] Test with different user date format preferences
- [ ] Create PR with before/after screenshots
- [ ] Simple, focused description

- [ ] Create feature branch for pagination fix
- [ ] Extract pagination fix changes
- [ ] Test wit many processed mails
- [ ] Create PR with reproduction steps

### Phase 3: Small Enhancement PR (Date+Time Formats)
- [ ] Create or find feature request discussion
- [ ] Wait for community interest/approval
- [ ] Create feature branch from `dev`
- [ ] Extract date+time format changes
- [ ] Ensure translations are complete
- [ ] Test with multiple locales
- [ ] Create PR with screenshots
- [ ] Reference feature request discussion

### Phase 4: Medium Enhancement PR (Based on feedback)
- [ ] Assess which PR got best reception
- [ ] Decide on next contribution
- [ ] Follow same process

## Git Workflow

### Repository Setup
```bash
# Fork paperless-ngx on GitHub first
cd ~/dev/projects
git clone https://github.com/paperless-ngx/paperless-ngx.git paperless-ngx-upstream
cd paperless-ngx-upstream

# Add your fork as remote
git remote add fork https://github.com/YOUR_USERNAME/paperless-ngx.git

# Fetch latest
git fetch origin
git checkout dev
git pull origin dev
```

### Per-PR Workflow
```bash
# Create feature branch
git checkout dev
git pull origin dev
git checkout -b fix/dashboard-race-condition

# Make changes (extract from RKC customization)
# ... edit files ...

# Format Python code (if applicable)
ruff format .

# Test
pytest

# Commit with descriptive message
git add .
git commit -m "[FIX] Dashboard views empty on page refresh

Fixes race condition where computed signals cache null before HTTP
data loads. Converted SavedViewService to use Angular signals for
proper reactivity.

- Changed savedViews array to savedViewsSignal
- Converted dashboardViews/sidebarViews to computed signals
- Updated consumers to call signals as functions

Proper reactive chain now works: HTTP → signal → computed → UI

Related to #XXXX"

# Push to fork
git push fork fix/dashboard-race-condition

# Create PR on GitHub
```

## PR Description Template

```markdown
## Description
[Clear, concise description of what this PR does]

## Motivation
[Why is this change needed? What problem does it solve?]

## Related Issues
Fixes #XXXX
Relates to discussion #YYYY

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)

## Testing
[Describe how this was tested]

- [ ] Tested locally
- [ ] Added/updated tests
- [ ] All tests pass

## Screenshots (if applicable)
[Before/after screenshots]

## Checklist
- [ ] My code follows the code style of this project
- [ ] I have formatted Python code with `ruff format`
- [ ] My change requires a change to the documentation
- [ ] I have updated the documentation accordingly
- [ ] I have added tests to cover my changes
- [ ] All new and existing tests passed
```

## Code Extraction Strategy

When extracting customizations for PRs:

1. **Remove RKC-specific context**
   - Strip out RKC comments
   - Remove organization-specific references
   - Generalize environment variable names if needed

2. **Preserve RKC comments in local repo**
   - Keep local customizations marked with RKC
   - Easier future maintenance and upgrades

3. **Clean commit history**
   - Each PR should have clean, logical commits
   - Squash if needed before final PR

4. **Test in isolation**
   - Test each customization independently on vanilla Paperless-ngx
   - Ensure no dependencies on other RKC changes

## Monitoring & Maintenance

### After PR Submission
- [ ] Monitor for review comments
- [ ] Respond promptly to feedback
- [ ] Make requested changes quickly
- [ ] Be patient - reviews may take time

### If PR is Merged
- [ ] Update local RKC customizations to match upstream
- [ ] Remove RKC-specific implementation if identical to upstream
- [ ] Update RKC_CUSTOMIZATIONS.md to note which features went upstream

### If PR is Rejected
- [ ] Understand the reasons
- [ ] Keep as private customization
- [ ] Consider alternative approaches
- [ ] Don't take it personally - focused project scope is healthy

## Success Metrics

### Short-term (3 months)
- Get 3 bug fixes merged
- Build rapport with maintainers
- Understand project's contribution style

### Medium-term (6-12 months)
- Have 3-5 enhancements accepted
- Become recognized contributor
- Help review other PRs

### Long-term (1+ years)
- Contribute major features (like OAuth2 sending)
- Reduce maintenance burden of RKC-specific code
- Give back to community that gave us Paperless-ngx

## Notes

- **Be humble**: We're guests in their project
- **Be patient**: Maintainers are volunteers
- **Be helpful**: Answer questions, help other users
- **Be respectful**: Accept decisions about project direction
- **Quality over quantity**: Better to have 3 well-crafted bug fix PRs than 10 rushed ones
- **Bug fixes first**: They're always welcome and build trust

## Resources

- [Paperless-ngx Contributing Guide](https://github.com/paperless-ngx/paperless-ngx/blob/main/CONTRIBUTING.md)
- [Development Documentation](https://docs.paperless-ngx.com/development/)
- [GitHub Discussions](https://github.com/paperless-ngx/paperless-ngx/discussions)
- [Matrix Chat](https://matrix.to/#/#paperless:matrix.org)

---

*Last Updated: 2025-01-12*
*RKC Customizations Version: 1.0.23+*
