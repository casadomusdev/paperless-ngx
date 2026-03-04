# RKC Environment Variables Reference

Complete reference of all environment variables introduced by RKC customizations. All are optional with sensible defaults.

## Security & Access Control

| Variable | Type | Default | Description | Details |
|----------|------|---------|-------------|---------|
| `PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER` | Boolean | `false` | Restrict PDF editor to superusers only | [PDF Editor](pdf-editor-restriction.md) |

## UI Defaults

| Variable | Type | Default | Description | Details |
|----------|------|---------|-------------|---------|
| `PAPERLESS_UI_THEME_COLOR` | String (hex) | `#17541f` | Default theme color | [UI Defaults](ui-defaults.md) |
| `PAPERLESS_UI_DARK_MODE_THUMB_INVERTED` | Boolean | `true` | Dark mode thumbnail inversion default | [UI Defaults](ui-defaults.md) |
| `PAPERLESS_UI_DEFAULT_LANGUAGE` | String | `de-de` | Default UI language | [UI Defaults](ui-defaults.md) |
| `PAPERLESS_SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE_DEFAULT` | Boolean | `true` | Unsaved changes warning default | [UI Defaults](ui-defaults.md) |
| `PAPERLESS_SHOW_CUSTOM_FIELD_NAMES_IN_CARDS` | Boolean | `false` | Show field names in card views | [Custom Field Filters](custom-field-filters.md) |

## Debugging

| Variable | Type | Default | Description | Details |
|----------|------|---------|-------------|---------|
| `PAPERLESS_DEBUG_SSO` | Boolean | `false` | Verbose SSO debug logging | [SSO Debug](sso-debug.md) |

## Mail System

| Variable | Type | Default | Description | Details |
|----------|------|---------|-------------|---------|
| `PAPERLESS_MAIL_CORRESPONDENT_MATCHING_ALGORITHM` | Integer | `6` | Matching algorithm for mail-created correspondents | [Mail System](mail-system.md) |
| `PAPERLESS_MAIL_UID_FIELD` | String | `"Mail UID"` | Custom field name for IMAP UID | [Mail System](mail-system.md) |
| `PAPERLESS_MAIL_FROM_FIELD` | String | `"Mail From"` | Custom field name for sender email | [Mail System](mail-system.md) |
| `PAPERLESS_MAIL_SENDER_FIELD` | String | `"Mail Sender"` | Custom field name for sender display name | [Mail System](mail-system.md) |
| `PAPERLESS_MAIL_SUBJECT_FIELD` | String | `"Mail Subject"` | Custom field name for email subject | [Mail System](mail-system.md) |
| `PAPERLESS_MAIL_DATE_FIELD` | String | `"Mail Date"` | Custom field name for received date | [Mail System](mail-system.md) |

## AI OCR

| Variable | Type | Default | Description | Details |
|----------|------|---------|-------------|---------|
| `AI_OCR_ENABLED` | Boolean | `false` | Enable AI OCR post-consumption script | [AI OCR](ai-ocr.md) |
| `AI_OCR_URL` | String | — | LiteLLM proxy base URL (e.g. `http://litellm:4000`) | [AI OCR](ai-ocr.md) |
| `AI_OCR_KEY` | String | — | LiteLLM virtual API key | [AI OCR](ai-ocr.md) |
| `AI_OCR_MODEL` | String | `mistral-ocr-latest` | OCR model name as configured in LiteLLM | [AI OCR](ai-ocr.md) |
| `AI_OCR_TAG_ID` | Integer | None | Tag ID to apply to the document on successful OCR | [AI OCR](ai-ocr.md) |
| `PAPERLESS_URL` | String | `http://localhost:8000` | Internal paperless URL (used by OCR script) | [AI OCR](ai-ocr.md) |
| `PAPERLESS_API_TOKEN` | String | — | Paperless superuser API token for OCR script | [AI OCR](ai-ocr.md) |

> Note: `PAPERLESS_URL` and `PAPERLESS_API_TOKEN` are used exclusively by the AI OCR post-consumption script. They are not consumed by paperless-ngx itself.

## Document Processing

| Variable | Type | Default | Description | Details |
|----------|------|---------|-------------|---------|
| `PAPERLESS_CONSUMER_READD_DOCUMENTS` | Boolean | `false` | Enable duplicate document re-add | [Duplicate Re-Add](duplicate-readd.md) |
| `PAPERLESS_CONSUMER_READD_TAG_ID` | Integer | None | Tag ID to apply on re-add | [Duplicate Re-Add](duplicate-readd.md) |
| `PAPERLESS_CONSUMER_READD_ADD_NOTE` | Boolean | `true` | Add note with re-add context | [Duplicate Re-Add](duplicate-readd.md) |
| `PAPERLESS_CONSUMER_READD_RETRASH` | Boolean | `false` | Re-trash trashed documents after re-add | [Duplicate Re-Add](duplicate-readd.md) |

## Removed Variables

| Variable | Removed In | Replaced By |
|----------|-----------|-------------|
| `PAPERLESS_GLOBAL_VIEWS_ADMIN_USER_ID` | v1.0.11 | System-wide `ApplicationConfiguration` model — any superuser can reorder |
| `PAPERLESS_SOCIALACCOUNT_DEBUG` | v1.0.5 | Renamed to `PAPERLESS_DEBUG_SSO` |
