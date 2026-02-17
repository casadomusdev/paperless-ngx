# SSO Debug Logging & UiSettings Auto-Creation

Debug logging for django-allauth SSO troubleshooting and automatic UiSettings creation for new SSO users.

## Environment Variable

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PAPERLESS_DEBUG_SSO` | Boolean | `false` | Enable verbose debug logging for SSO operations |

## SSO Debug Logging

### Purpose

Detailed debug logging for django-allauth SSO troubleshooting without enabling full Django DEBUG mode.

### Behavior

- **When disabled (default)**: Minimal logging, standard INFO/ERROR levels only
- **When enabled**: Verbose DEBUG logging for:
  - All django-allauth operations (signup, authentication, provider flow)
  - Django request/response cycle during SSO
  - Custom adapter operations (user creation, group assignment)
  - UiSettings auto-creation for new users

### What Gets Logged

| Logger | Content |
|--------|---------|
| `[allauth]` | General allauth framework operations |
| `[allauth.account]` | Account creation and management |
| `[allauth.socialaccount]` | Social provider authentication flow |
| `[SSO]` | Custom adapter debug messages |
| `Social SSO:` | User creation and group assignment |

### Log Output Location
- **Container**: `/usr/src/paperless/data/log/paperless.log`
- **Console**: `docker logs <container-name>` or systemd journal

### Usage

```bash
# Enable SSO debug logging
PAPERLESS_DEBUG_SSO=true

# Watch logs in real-time
docker compose logs -f webserver

# Attempt SSO signup, check logs for detailed debug output

# Disable after troubleshooting (may contain sensitive info like tokens)
PAPERLESS_DEBUG_SSO=false
```

## UiSettings Auto-Creation for SSO Users

### Problem

New SSO users would get an error on first login because `UiSettings.settings` field defaults to NULL, and views called `.get()` on None.

### Solution

1. **Signal Handler**: `post_save` signal on `User` model auto-creates `UiSettings` for new users
   - Located in `src/documents/signals/handlers.py`
   - Includes migration-safe table existence check to prevent transaction failures on fresh database installations
2. **Exception Handling**: Added `try/except` for `RelatedObjectDoesNotExist` in `IndexView.get_frontend_language()` and `UiSettingsView.get()`
3. **NULL Safety**: Proper NULL checks before accessing `ui_settings.settings`

## Files Modified

### Backend
- `src/paperless/settings.py` — Debug mode configuration, logger setup
- `src/paperless/adapter.py` — SSO user creation debug logging in `CustomSocialAccountAdapter`
- `src/documents/signals/handlers.py` — `create_ui_settings_for_new_user` signal handler with debug logging
- `src/documents/views.py` — NULL safety in `IndexView.get_frontend_language()` and `UiSettingsView.get()`

## Version History

- **v1.0.3**: SSO debug logging via `PAPERLESS_SOCIALACCOUNT_DEBUG` (later renamed)
- **v1.0.4**: UiSettings NULL fix for SSO users
- **v1.0.5**: Comprehensive fix with post_save signal auto-creation, migration-safe table check, enhanced Django logging
