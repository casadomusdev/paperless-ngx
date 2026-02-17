# UI Customization Defaults

Organization-wide default settings for UI appearance and behavior. All work as fallbacks — existing user preferences are never overridden.

## Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PAPERLESS_UI_THEME_COLOR` | String (hex) | `#17541f` | Default theme color for users without a preference |
| `PAPERLESS_UI_DARK_MODE_THUMB_INVERTED` | Boolean | `true` | Default thumbnail inversion in dark mode |
| `PAPERLESS_UI_DEFAULT_LANGUAGE` | String | `de-de` | Default UI language (language code) |
| `PAPERLESS_SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE_DEFAULT` | Boolean | `true` | Default for unsaved changes warning on saved views |

## How It Works

All four settings follow the same pattern:
1. Backend reads environment variable in `src/paperless/settings.py`
2. Value exposed to frontend via `/api/ui_settings/` in `src/documents/views.py`
3. Frontend `settings.service.ts` uses value as fallback in `get()` method
4. User preference (stored in DB) always takes priority when set
5. Changes take effect immediately after restart — no rebuild needed

## Theme Color (`PAPERLESS_UI_THEME_COLOR`)

Sets organization-wide default theme color without overriding individual preferences.

```bash
PAPERLESS_UI_THEME_COLOR=#2563eb
```

- Users without a custom color see this color
- Users can still override by selecting their own in Settings
- Changing the env var updates all users without custom colors instantly

## Dark Mode Thumbnail Inversion (`PAPERLESS_UI_DARK_MODE_THUMB_INVERTED`)

Controls whether document thumbnails are inverted in dark mode by default.

```bash
PAPERLESS_UI_DARK_MODE_THUMB_INVERTED=false
```

- New users inherit this setting
- Users who haven't explicitly set the preference use this value
- Override available in Settings > Appearance

## Default Language (`PAPERLESS_UI_DEFAULT_LANGUAGE`)

Sets organization-wide default interface language.

```bash
PAPERLESS_UI_DEFAULT_LANGUAGE=en-us
```

**Common Language Codes**: `de-de`, `en-us`, `en-gb`, `fr-fr`, `es-es`, `it-it`, `nl-nl`, `pt-pt`, `pt-br`, `da-dk`, `no-no`, `sv-se`, `fi-fi`, `cs-cz`, `pl-pl`, `ru-ru`, `ja-jp`, `ko-kr`, `zh-cn`, `zh-tw`, `ar-ar` and 15+ more.

## Unsaved Changes Warning Default (`PAPERLESS_SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE_DEFAULT`)

Controls default for "Show warning when closing saved views with unsaved changes".

```bash
PAPERLESS_SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE_DEFAULT=false
```

- When `true` (default): New users see warnings when closing unsaved views
- When `false`: Streamlined workflow for experienced users
- Users can toggle individually in Settings > Saved Views

## Date+Time Format Options (v1.0.21)

Added 4 new date format options that include time display, extending Angular's built-in DatePipe:

| Format | Example | Description |
|--------|---------|-------------|
| `short` | `1/12/25, 3:50 PM` | Compact with hours:minutes |
| `medium` | `Jan 12, 2025, 3:50:36 PM` | Balanced with seconds |
| `long` | `January 12, 2025 at 3:50:36 PM GMT+1` | Full date with timezone |
| `full` | Complete with day-of-week and full timezone | Most verbose |

**Note**: Card views (small and large) now respect the user's date format preference (v1.0.22 bug fix — previously hardcoded `'mediumDate'`).

## Files Modified

### Backend
- `src/paperless/settings.py` — All environment variable definitions
- `src/documents/views.py` — All values exposed via `UiSettingsView`

### Frontend
- `src-ui/src/app/data/ui-settings.ts` — Settings key definitions
- `src-ui/src/app/services/settings.service.ts` — Fallback logic in `get()` method
- `src-ui/src/app/components/admin/settings/settings.component.html` — Date+time format radio buttons
- `src-ui/src/app/components/document-list/document-card-small/document-card-small.component.html` — Removed hardcoded date format
- `src-ui/src/app/components/document-list/document-card-large/document-card-large.component.html` — Removed hardcoded date format
- `src-ui/src/locale/messages.en_US.xlf` — English translations for date+time options
- `src-ui/src/locale/messages.de_DE.xlf` — German translations for date+time options

## Deployment Examples

### Docker Compose
```yaml
services:
  webserver:
    environment:
      PAPERLESS_UI_THEME_COLOR: "#2563eb"
      PAPERLESS_UI_DARK_MODE_THUMB_INVERTED: "true"
      PAPERLESS_UI_DEFAULT_LANGUAGE: "de-de"
```

### Environment File
```bash
PAPERLESS_UI_THEME_COLOR=#2563eb
PAPERLESS_UI_DARK_MODE_THUMB_INVERTED=true
PAPERLESS_UI_DEFAULT_LANGUAGE=de-de
```

### Bare Metal / systemd
```ini
[Service]
Environment="PAPERLESS_UI_THEME_COLOR=#2563eb"
Environment="PAPERLESS_UI_DARK_MODE_THUMB_INVERTED=true"
Environment="PAPERLESS_UI_DEFAULT_LANGUAGE=de-de"
```

## Version History

- **v1.0.1**: Theme color and dark mode thumbnail inversion defaults
- **v1.0.2**: Default language environment variable
- **v1.0.21**: Date+time format options
- **v1.0.22**: Card views respect user date format preference (bug fix)
- **v1.0.29**: Unsaved changes warning default
