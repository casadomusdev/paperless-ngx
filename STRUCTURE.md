# Project Structure

Custom fork of [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) with RKC enhancements. All customizations are marked with `RKC:` comments in the codebase.

## Project Layout

```
paperless-ngx/
├── RKC_CUSTOMIZATIONS.md           # High-level overview of all RKC customizations
├── MS365_OAUTH_SETUP.md            # Microsoft 365 OAuth setup guide
├── IMPLEMENT.md                    # Current implementation task
├── TODO.md                         # Current task progress
├── STRUCTURE.md                    # This file
│
├── docs/                           # Documentation
│   ├── rkc/                        # RKC customization detail docs
│   │   ├── ai-ocr.md
│   │   ├── pdf-editor-restriction.md
│   │   ├── global-saved-views.md
│   │   ├── ui-defaults.md
│   │   ├── sso-debug.md
│   │   ├── custom-field-filters.md
│   │   ├── duplicate-readd.md
│   │   ├── mail-system.md
│   │   ├── workflow-email.md
│   │   ├── bug-fixes.md
│   │   └── environment-variables.md
│   ├── administration.md
│   ├── api.md
│   ├── configuration.md
│   └── ...                         # Other upstream docs
│
├── src/                            # Backend (Django/Python)
│   ├── paperless/                  # Core Django app
│   │   ├── settings.py             # RKC env vars defined here
│   │   ├── models.py               # ApplicationConfiguration (global view ordering)
│   │   ├── adapter.py              # SSO adapter with debug logging
│   │   └── migrations/
│   ├── documents/                  # Document management app
│   │   ├── views.py                # RKC: PDF editor, saved views, UI settings
│   │   ├── consumer.py             # RKC: duplicate re-add, mail metadata
│   │   ├── models.py               # RKC: workflow email fields
│   │   ├── mail.py                 # RKC: unified email sending
│   │   ├── serialisers.py          # RKC: workflow email serializers
│   │   ├── signals/handlers.py     # RKC: SSO, webhooks, email action
│   │   ├── data_models.py          # RKC: ConsumableDocument metadata fields
│   │   ├── templating/             # RKC: Jinja2 custom field context
│   │   └── migrations/
│   └── paperless_mail/             # Mail system app
│       ├── models.py               # RKC: SMTP fields, FROM_SMART, PROCESS_ALL
│       ├── mail.py                 # RKC: smart matching, pooling, metadata
│       ├── mail_oauth.py           # RKC: unified email backend
│       ├── mail_graph.py           # RKC: Graph API sending (NEW)
│       ├── mail_graph_retrieval.py # RKC: Graph API retrieval, multi-mailbox
│       ├── oauth.py                # RKC: updated OAuth scopes
│       ├── serialisers.py          # RKC: SMTP fields, password obfuscation
│       ├── filters.py              # RKC: server-side processed mail filtering
│       ├── views.py                # RKC: enhanced bulk_delete
│       ├── tasks.py                # RKC: enhanced log messaging
│       └── migrations/
│
├── src-ui/                         # Frontend (Angular/TypeScript)
│   ├── src/
│   │   ├── styles.scss             # RKC: tooltip dark mode fix
│   │   ├── locale/                 # RKC: EN + DE translations
│   │   └── app/
│   │       ├── data/               # RKC: ui-settings.ts, mail-account.ts, etc.
│   │       ├── services/           # RKC: settings.service.ts, saved-view.service.ts
│   │       └── components/
│   │           ├── document-detail/ # RKC: PDF editor, custom field filters
│   │           ├── document-list/   # RKC: card view filters, date format
│   │           ├── dashboard/       # RKC: global views, race condition fix
│   │           ├── app-frame/       # RKC: sidebar global views
│   │           ├── manage/
│   │           │   ├── mail/        # RKC: processed mail UI, sending badges
│   │           │   └── saved-views/ # RKC: global views management
│   │           ├── admin/settings/  # RKC: date+time format options
│   │           └── common/
│   │               ├── edit-dialog/ # RKC: mail account, workflow, correspondent
│   │               ├── input/       # RKC: filter support on all input types
│   │               └── custom-field-display/ # RKC: reusable filter component
│   └── ...
│
├── scripts/                        # Deployment scripts and hooks
│   ├── ai_ocr_post_consume.py      # RKC: AI OCR post-consumption hook (LiteLLM /v1/ocr)
│   ├── ai_ocr_rerun.py             # RKC: Re-run logic (runs inside container, all env vars present)
│   ├── check_smtp_port25.py        # RKC: Admin utility to test outbound SMTP port 25 reachability (v1.2.9)
│   ├── post-consumption-example.sh # Upstream example post-consumption script
│   ├── start_services.sh           # Service startup script
│   └── paperless-*.service         # Systemd service unit files
│
└── docker/                         # Docker configuration
```

## RKC Documentation Architecture

```
RKC_CUSTOMIZATIONS.md (232 lines)
  ├── High-level overview of all features
  ├── Quick Start & Deployment
  ├── Environment Variables summary table
  ├── Version History (one line per version)
  ├── Maintenance Notes
  └── Links to detailed docs ↓

docs/rkc/ (11 files)
  ├── ai-ocr.md                     — Processing: AI OCR post-consumption hook
  ├── pdf-editor-restriction.md     — Security: PDF editor access control
  ├── global-saved-views.md         — Collaborative: shared views system
  ├── ui-defaults.md                — Defaults: theme, language, appearance
  ├── sso-debug.md                  — Debug: SSO logging & UiSettings
  ├── custom-field-filters.md       — UI: filter buttons for custom fields
  ├── duplicate-readd.md            — Processing: duplicate document handling
  ├── mail-system.md                — Mail: SMTP, Graph API, matching, metadata
  ├── workflow-email.md             — Workflow: dynamic email templates
  ├── bug-fixes.md                  — Fixes: webhook, dashboard, tooltips, etc.
  └── environment-variables.md      — Reference: all RKC env vars
```
