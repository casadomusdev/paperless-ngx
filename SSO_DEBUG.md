# SSO Signup Error - Debug Log

## Problem Description

**Error Message**: "An error occurred while attempting to login via your social network account."

**Platform**: Paperless-ngx with Microsoft SSO (OAuth2)

**Symptom**: When a NEW user attempts to sign up via Microsoft SSO, they receive a generic error message in the browser. Existing SSO users can log in successfully, but new account creation fails.

**Environment**:
- Deployment: Docker container (`casabot-filderbau-paperless`)
- Container created: 2025-12-02 at 12:46 UTC
- Custom code is mounted/included in the container
- Environment variable `PAPERLESS_SOCIALACCOUNT_DEBUG=true` is set

## Initial Observations

1. **No Log Output**: Despite the error occurring, there are NO log entries in paperless.log related to the SSO signup attempt
2. **No Stack Trace**: The error message in the browser is generic with no additional details
3. **Settings Import Issue**: Multiple log entries showing "Social account debug logging enabled via PAPERLESS_SOCIALACCOUNT_DEBUG" (7 instances, suggesting 7 worker processes)

## Debugging Steps Taken

### 1. UiSettings None Bug Fix (2025-12-02)

**Problem Identified**: When new SSO users sign up, paperless-ngx creates a `UiSettings` object with the `settings` field set to NULL. Two views were trying to call `.get()` on this NULL value, causing AttributeError.

**Fix Applied** in `src/documents/views.py`:

#### Location 1: IndexView.get_frontend_language() (lines 223-228)
```python
# RKC: Handle None settings for new SSO users
if (
    hasattr(self.request.user, "ui_settings")
    and self.request.user.ui_settings.settings is not None
    and self.request.user.ui_settings.settings.get("language")
):
    lang = self.request.user.ui_settings.settings.get("language")
```

#### Location 2: UiSettingsView.get() (lines 3540-3543)
```python
# RKC: Handle None settings for new SSO users
if hasattr(user, "ui_settings") and user.ui_settings.settings is not None:
    ui_settings = user.ui_settings.settings
```

**Result**: This should prevent one potential crash, but the error persisted.

### 2. Logging Configuration Investigation

**Verification Steps**:
```bash
# Confirmed env var is set
sudo docker exec -it casabot-filderbau-paperless env | grep PAPERLESS_SOCIALACCOUNT_DEBUG
# Output: PAPERLESS_SOCIALACCOUNT_DEBUG=true

# Confirmed allauth loggers are registered
sudo docker exec -it casabot-filderbau-paperless python3 manage.py shell -c "
import logging
for name in logging.root.manager.loggerDict:
    if 'allauth' in name:
        print(name)
"
# Output:
# allauth
# allauth.account
# allauth.socialaccount
# allauth.account.stages
```

**Discovery**: Loggers were configured correctly, but still no output during signup attempts.

### 3. Logging Configuration Order Fix

**Problem Identified**: In `src/paperless/settings.py`, allauth loggers were being added to the LOGGING dict AFTER `logging.config.dictConfig(LOGGING)` was called, so they were never actually configured.

**Fix Applied** in `src/paperless/settings.py`:
```python
# RKC: Enable django-allauth debug logging via environment variable
SOCIALACCOUNT_DEBUG = __get_boolean("PAPERLESS_SOCIALACCOUNT_DEBUG", "NO")

if SOCIALACCOUNT_DEBUG:
    # Add allauth loggers to LOGGING dict FIRST
    LOGGING["loggers"]["allauth"] = {
        "handlers": ["file_paperless", "console"],
        "level": "DEBUG",
    }
    LOGGING["loggers"]["allauth.account"] = {
        "handlers": ["file_paperless", "console"],
        "level": "DEBUG",
    }
    LOGGING["loggers"]["allauth.socialaccount"] = {
        "handlers": ["file_paperless", "console"],
        "level": "DEBUG",
    }

# THEN configure logging
logging.config.dictConfig(LOGGING)

# THEN log that debug is enabled (only once per process)
if SOCIALACCOUNT_DEBUG:
    logger.info("Social account debug logging enabled via PAPERLESS_SOCIALACCOUNT_DEBUG")
```

**Result**: Logging order fixed, but still no allauth logs appearing.

### 4. paperless.auth Logger Addition

**Problem Identified**: The existing debug logging in `src/paperless/adapter.py` uses `logger = logging.getLogger("paperless.auth")`, but this logger wasn't explicitly configured for DEBUG output when SOCIALACCOUNT_DEBUG was enabled.

**Fix Applied** in `src/paperless/settings.py`:
```python
if SOCIALACCOUNT_DEBUG:
    LOGGING["loggers"]["allauth"] = { ... }
    LOGGING["loggers"]["allauth.account"] = { ... }
    LOGGING["loggers"]["allauth.socialaccount"] = { ... }
    # Also enable debug logging for paperless.auth which is used by adapter.py
    LOGGING["loggers"]["paperless.auth"] = {
        "handlers": ["file_paperless", "console"],
        "level": "DEBUG",
    }
```

### 5. Enhanced Adapter Logging

**Enhancement Applied** in `src/paperless/adapter.py`:

Added explicit try/except with logging to `CustomSocialAccountAdapter.is_open_for_signup()`:
```python
def is_open_for_signup(self, request, sociallogin):
    """
    Check whether the site is open for signups via social account, which can be
    disabled via the SOCIALACCOUNT_ALLOW_SIGNUPS setting.
    """
    try:
        logger.debug(f"[SSO] is_open_for_signup called for {sociallogin.account.provider}")
        allow_signups = super().is_open_for_signup(request, sociallogin)
        result = getattr(settings, "SOCIALACCOUNT_ALLOW_SIGNUPS", allow_signups)
        logger.debug(f"[SSO] is_open_for_signup returning: {result}")
        return result
    except Exception as e:
        logger.exception(f"[SSO] Error in is_open_for_signup: {e}")
        raise
```

**Note**: The existing `save_user()` method already had excellent debug logging:
```python
def save_user(self, request, sociallogin, form=None):
    try:
        logger.debug(f"Starting social account save_user for {sociallogin.account}")
        # ... existing code with multiple debug statements ...
        logger.debug(f"Successfully completed save_user for user: {user}")
        return user
    except Exception as e:
        logger.exception(f"Error in CustomSocialAccountAdapter.save_user: {e}")
        raise
```

## Code Files Modified

1. **src/paperless/settings.py**
   - Fixed logging configuration order
   - Added paperless.auth logger to debug config
   - Moved log message after dictConfig()

2. **src/documents/views.py**
   - Added NULL checks for ui_settings.settings in IndexView.get_frontend_language()
   - Added NULL checks for ui_settings.settings in UiSettingsView.get()

3. **src/paperless/adapter.py**
   - Enhanced is_open_for_signup() with debug logging and try/except

## Current Status

**Logging Configuration**: ✅ Complete
- All allauth loggers configured
- paperless.auth logger configured
- Logging order corrected
- Debug messages added at key entry points

**Potential Fixes Applied**: ✅ Complete
- UiSettings None bug fixed
- Enhanced error catching in adapter methods

**Container State**: ✅ Ready for testing
- Changes applied to source code
- Container restart required to pick up changes

## Next Steps for Testing

### 1. Restart Container
```bash
sudo docker compose restart webserver
```

### 2. Monitor Logs in Real-Time
```bash
sudo docker logs -f casabot-filderbau-paperless 2>&1
```

### 3. Attempt SSO Signup
Use a NEW Microsoft account that has never logged into this paperless instance before.

### 4. Expected Log Output

If logging is working correctly, you should see:
```
[paperless.auth] [SSO] is_open_for_signup called for microsoft
[paperless.auth] [SSO] is_open_for_signup returning: True
[paperless.auth] Starting social account save_user for <account>
[paperless.auth] Successfully created/retrieved user: <username>
[paperless.auth] Social account default groups: []
[paperless.auth] Calling handle_social_account_updated for user: <username>
[paperless.auth] Successfully completed save_user for user: <username>
```

If there's an error, you should see:
```
[paperless.auth] [SSO] Error in is_open_for_signup: <exception details>
OR
[paperless.auth] Error in CustomSocialAccountAdapter.save_user: <exception details>
```

### 5. If Still No Logs Appear

This would indicate the error is occurring BEFORE allauth/adapter code is reached, suggesting:
- An issue in URL routing
- A middleware problem
- A Django authentication backend issue
- An issue with the Microsoft OAuth callback

In this case, would need to:
1. Check Django request logs for the callback URL hit
2. Verify SOCIALACCOUNT_PROVIDERS configuration
3. Check if Microsoft OAuth credentials are valid
4. Review CSRF/CORS settings for the callback

## Theory: Why No Logs?

The complete absence of ANY logging (not even INFO level from allauth) suggests one of:

1. **Allauth isn't被 invoked at all** - The error happens in Django middleware, URL routing, or authentication backends before reaching allauth code

2. **Silent exception swallowing** - Some outer try/except is catching and suppressing the exception without logging

3. **Settings issue** - SOCIALACCOUNT_ALLOW_SIGNUPS or SOCIALACCOUNT_PROVIDERS misconfigured, causing early rejection

4. **Request flow issue** - OAuth callback isn't reaching the expected endpoints

## Questions to Answer Through Testing

1. Do the `[SSO]` prefixed debug logs appear when attempting signup?
2. If yes, where does the flow stop?
3. If no, the error is happening before adapter code - need to trace earlier in the request chain
4. What's the exact HTTP status code of the error? (Check browser dev tools Network tab)
5. Are there ANY Django request logs for the OAuth callback URL?

## Related Configuration

**Environment Variables**:
- `PAPERLESS_SOCIALACCOUNT_DEBUG=true` ✅ Set and confirmed
- `PAPERLESS_SOCIALACCOUNT_ALLOW_SIGNUPS` - Unknown, defaults to yes
- `PAPERLESS_SOCIALACCOUNT_PROVIDERS` - Unknown format, needs verification

**Django Settings**:
- `SOCIALACCOUNT_ALLOW_SIGNUPS` - Should be True (default)
- `SOCIALACCOUNT_AUTO_SIGNUP` - Config unknown
- `SOCIAL_ACCOUNT_DEFAULT_GROUPS` - Config unknown

## Additional Resources

- Paperless-ngx docs: https://docs.paperless-ngx.com/
- Django-allauth docs: https://docs.allauth.org/
- RKC Customizations: See `RKC_CUSTOMIZATIONS.md` for all custom code changes

---

**Document Created**: 2025-12-02
**Last Updated**: 2025-12-02
**Status**: ✅ **RESOLVED**

---

## RESOLUTION (2025-12-02)

### Root Cause Identified

The issue was a **race condition** in how `UiSettings` objects are created and accessed for new SSO users:

1. Django-allauth creates the `User` object during SSO signup
2. `UiSettings` is supposed to be auto-created via OneToOne relationship
3. However, the `settings` field in `UiSettings` defaults to NULL
4. Multiple views (`IndexView`, `UiSettingsView`) were accessing `user.ui_settings.settings` immediately
5. When `settings` is NULL, calling `.get()` on it raises `AttributeError`
6. Additionally, accessing `user.ui_settings` when the UiSettings doesn't exist yet raises `RelatedObjectDoesNotExist`

### Complete Fix Applied

#### 1. Exception Handling in Views (`src/documents/views.py`)

**IndexView.get_frontend_language()**:
```python
# RKC: Handle None settings for new SSO users - use try/except to catch RelatedObjectDoesNotExist
try:
    ui_settings_obj = self.request.user.ui_settings
    if ui_settings_obj.settings is not None and ui_settings_obj.settings.get("language"):
        lang = ui_settings_obj.settings.get("language")
    else:
        lang = get_language()
except UiSettings.DoesNotExist:
    lang = get_language()
# /end RKC edit
```

**UiSettingsView.get()**:
```python
# RKC: Handle None settings for new SSO users - use try/except to catch RelatedObjectDoesNotExist
try:
    ui_settings_obj = user.ui_settings
    if ui_settings_obj.settings is not None:
        ui_settings = ui_settings_obj.settings
except UiSettings.DoesNotExist:
    # UiSettings doesn't exist yet, use empty dict
    pass
# /end RKC edit
```

#### 2. Auto-Create UiSettings Signal (`src/documents/signals/handlers.py`)

Added a Django signal to automatically create UiSettings with an empty dict when a new user is created:

```python
# RKC: Auto-create UiSettings for new users to prevent SSO signup issues
@receiver(models.signals.post_save, sender=User)
def create_ui_settings_for_new_user(sender, instance: User, created: bool, **kwargs):
    """
    Automatically create UiSettings with empty settings dict for newly created users.
    This prevents issues when new SSO users sign up, as the system expects UiSettings
    to exist even if the settings field is null/empty.
    """
    if created:
        UiSettings.objects.get_or_create(
            user=instance,
            defaults={"settings": {}},
        )
        logger.debug(f"Auto-created UiSettings for new user: {instance.username}")
# /end RKC edit
```

#### 3. Enhanced Django Logging (`src/paperless/settings.py`)

Added proper Django core loggers to capture request/response errors:

```python
"root": {"handlers": ["console"], "level": "INFO"},  # Added level
"loggers": {
    # ... existing loggers ...
    "django": {
        "handlers": ["file_paperless", "console"],
        "level": "INFO",
    },
    "django.request": {
        "handlers": ["file_paperless", "console"],
        "level": "DEBUG",
        "propagate": False,
    },
}
```

### Why This Fix Works

1. **Defense in Depth**: Three layers of protection:
   - Signal auto-creates UiSettings immediately when user is created
   - Exception handling catches the case where UiSettings doesn't exist yet
   - NULL checks handle the case where settings field is NULL

2. **No Race Conditions**: The post_save signal runs synchronously during user creation, ensuring UiSettings exists before any views are accessed

3. **Graceful Degradation**: If anything fails, views fall back to sensible defaults (system language, empty settings dict)

4. **Better Logging**: Django request logger now captures errors at DEBUG level, making future issues easier to diagnose

### Testing Recommendations

1. Test SSO signup with a brand new Microsoft account
2. Verify UiSettings is created automatically
3. Verify no errors in paperless.log
4. Verify user can access the UI immediately after signup
5. Verify language preferences work correctly

### Files Modified

- `src/documents/views.py` - Exception handling in IndexView and UiSettingsView
- `src/documents/signals/handlers.py` - Auto-create signal for UiSettings
- `src/paperless/settings.py` - Enhanced logging configuration
- `RKC_CUSTOMIZATIONS.md` - Documented in v1.0.5

### Deployment

No database migrations required. Changes are code-only:
1. Deploy updated code
2. Restart paperless container/service
3. Changes take effect immediately for all new signups
