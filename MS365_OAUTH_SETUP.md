# Microsoft 365 OAuth Setup Guide for Paperless-ngx

## Overview

This guide explains how to configure Microsoft 365 (Outlook/Office 365) OAuth2 authentication for both **IMAP mail retrieval** and **SMTP mail sending** in Paperless-ngx.

**Key Insight:** Paperless-ngx uses **dynamic consent** with Exchange legacy protocols (IMAP/SMTP), which means you do NOT need to pre-configure API permissions in the Azure Portal. The required scopes are requested at runtime during the OAuth authorization flow.

## Table of Contents

1. [Understanding Dynamic Consent](#understanding-dynamic-consent)
2. [Azure AD App Registration Setup](#azure-ad-app-registration-setup)
3. [Common Misconceptions](#common-misconceptions)
4. [Permission Types Explained](#permission-types-explained)
5. [Testing and Verification](#testing-and-verification)
6. [Troubleshooting](#troubleshooting)

---

## Understanding Dynamic Consent

### What is Dynamic Consent?

**Dynamic Consent** (also called "incremental consent") means that OAuth scopes are requested **at runtime** via the authorization URL, rather than being pre-configured in the Azure Portal.

**How it works:**

1. Paperless-ngx constructs an OAuth authorization URL with required scopes
2. User clicks the authorization link and is redirected to Microsoft's login page
3. Microsoft shows a consent screen listing the requested permissions
4. User accepts, and Microsoft grants an access token with those scopes
5. **No prior configuration in Azure Portal needed!**

### Why Paperless-ngx Uses Dynamic Consent

- ✅ **Simpler setup** - No need to configure complex API permissions
- ✅ **User-friendly** - Users see exactly what they're authorizing
- ✅ **No admin bottleneck** - Users can self-authorize without IT department
- ✅ **Best practice** - Modern OAuth2 standard approach

### Scopes Requested by Paperless-ngx

From `src/paperless_mail/oauth.py`:

```python
scope=[
    "offline_access",                                    # Token refresh capability
    "https://outlook.office.com/IMAP.AccessAsUser.All",  # IMAP mail reading
    "https://graph.microsoft.com/Mail.Send",             # Graph API mail sending
]
```

**Note:** Paperless-ngx uses **Microsoft Graph API for sending** emails (not SMTP). This provides:
- ✅ Compatibility with Microsoft 365 Security Defaults
- ✅ No need to enable "Authenticated SMTP" per-user
- ✅ Better error messages and reliability
- ✅ Future-proof (Microsoft's strategic direction)

IMAP is still used for **receiving** emails, which works reliably with OAuth2.

These scopes are requested **dynamically** during the OAuth flow - they do NOT need to be configured in Azure AD.

---

## Azure AD App Registration Setup

### Prerequisites

- Microsoft 365 admin account (or permissions to create app registrations)
- Access to Azure Portal (https://portal.azure.com)
- Your Paperless-ngx public URL

### Step-by-Step Setup

#### 1. Create App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to: **Azure Active Directory** → **App registrations**
3. Click **+ New registration**
4. Configure:
   - **Name:** `Paperless-ngx Mail Access` (or any descriptive name)
   - **Supported account types:**
     - Single tenant (if only your organization)
     - Multitenant (if supporting external accounts)
   - **Redirect URI:**
     - Platform: **Web**
     - URI: `https://your-paperless-domain.com/api/oauth/callback/`
     - Example: `https://paperless.example.com/api/oauth/callback/`
5. Click **Register**

#### 2. Create Client Secret

1. In your new app registration, go to **Certificates & secrets**
2. Click **+ New client secret**
3. Description: `Paperless-ngx OAuth Secret`
4. Expires: Choose appropriate duration (e.g., 24 months)
5. Click **Add**
6. **IMPORTANT:** Copy the secret value immediately - it won't be shown again!

#### 3. Note Your Credentials

You'll need these for Paperless-ngx configuration:

- **Application (client) ID:** Found on the Overview page
- **Client secret:** Copied from step 2
- **Tenant ID:** Found on Overview page (optional, usually not needed)

#### 4. Configure Redirect URI (If Not Done in Step 1)

1. Go to **Authentication** in left menu
2. Under **Platform configurations** → **Web**
3. Add Redirect URI: `https://your-paperless-domain.com/api/oauth/callback/`
4. **Important:** Use HTTPS in production (HTTP only for localhost testing)
5. Click **Save**

#### 5. API Permissions - What NOT to Do

**DO NOT add these permissions manually:**
- ❌ Office 365 Exchange Online → IMAP.AccessAsUser.All
- ❌ Office 365 Exchange Online → SMTP.Send
- ❌ Microsoft Graph → Mail.Read or Mail.Send

**These are requested dynamically!**

**What you SHOULD see:**

Most likely just the default permission:
- ✅ **Microsoft Graph** → **User.Read** (Delegated)
  - Automatically added when creating app registration
  - Used for basic user profile info
  - **Keep this** - it's harmless and standard

**That's all you need!**

#### 6. Enterprise Applications (Optional)

If you want to control which users can authorize this app:

1. Go to **Azure Active Directory** → **Enterprise applications**
2. Find your app (same name as app registration)
3. Go to **Properties**
4. Set **User assignment required** to **Yes**
5. Go to **Users and groups** to assign specific users

---

## Common Misconceptions

### Misconception #1: "I need to add IMAP/SMTP permissions in Azure Portal"

❌ **False!** 

When searching for "Office 365 Exchange Online" API in the Azure Portal permissions page, you'll only see **Application permissions** (IMAP.AccessAsApp, SMTP.SendAsApp), not the **Delegated permissions** you need.

**Why?** Because delegated permissions for Exchange legacy protocols use **dynamic consent** and don't appear in the portal for manual addition.

### Misconception #2: "Application permissions will work"

❌ **Wrong!**

**Application permissions** (IMAP.AccessAsApp, SMTP.SendAsApp):
- Allow app to access **ANY user's mailbox** without user consent
- Require admin consent for entire organization
- Work without a logged-in user (daemon scenarios)
- **NOT what you want** for user-specific authentication

**Delegated permissions** (IMAP.AccessAsUser.All, SMTP.Send):
- Work in the context of the **signed-in user only**
- User grants consent during OAuth flow
- App can only access that specific user's mailbox
- **This is what Paperless-ngx uses**

### Misconception #3: "I need separate apps for IMAP and SMTP"

❌ **False!**

Both IMAP and SMTP are **Exchange legacy protocols** and can coexist in the same app registration.

The "mixing Graph API and legacy protocols" issue only applies when you try to mix:
- ❌ Microsoft Graph permissions (Mail.Read, Mail.Send) WITH Exchange legacy protocols (IMAP/SMTP)

For Paperless-ngx:
- ✅ Only uses Exchange legacy protocols (IMAP + SMTP)
- ✅ Single app registration works for both
- ✅ No conflicts because no Graph API is involved

---

## Permission Types Explained

### Comparison Table

| Aspect | Application Permissions | Delegated Permissions (Dynamic Consent) |
|--------|------------------------|---------------------------------------|
| **Portal Configuration** | ✅ Must add in Azure Portal | ❌ Requested at runtime, not in portal |
| **Admin Consent** | ✅ Required for entire tenant | ❌ User consents individually |
| **User Context** | ❌ No user context (any mailbox) | ✅ Only the signed-in user's mailbox |
| **Use Case** | Daemon apps, service accounts | User-facing apps (Paperless-ngx) |
| **Paperless-ngx** | ❌ NOT SUPPORTED | ✅ THIS IS WHAT'S USED |

### Why Dynamic Consent "Hides" Permissions

When you look at **API permissions** in your app registration, you might see:
- Just `Microsoft Graph → User.Read`
- No Exchange IMAP/SMTP permissions listed

**This is normal and correct!** The IMAP/SMTP permissions are:
1. Requested in the OAuth authorization URL
2. Shown to users on the consent screen
3. Granted when users click "Accept"
4. Included in the access token
5. **But NOT pre-configured in the portal**

---

## Testing and Verification

### Test the OAuth Flow

1. In Paperless-ngx, go to: **Settings** → **Mail** → **Mail Accounts**
2. Click **+ Add Mail Account**
3. Click **Enable OAuth2 Mail** and select **Outlook**
4. You'll be redirected to Microsoft login page
5. **Check the consent screen** - should request:
   - "Access your mail via IMAP" or similar
   - "Send mail on your behalf" or similar
6. Click **Accept**
7. You should be redirected back to Paperless-ngx with account created

### Verify Access Token Scopes

If you want to inspect what scopes were actually granted:

1. After successful OAuth authorization, the access token is stored in the database
2. The token is a JWT (JSON Web Token) that can be decoded
3. Use a JWT decoder (e.g., https://jwt.ms or https://jwt.io)
4. Paste the access token and look for the `scp` claim
5. Should contain: `IMAP.AccessAsUser.All SMTP.Send offline_access`

### Check Azure AD Portal (Optional)

After a user has authorized the app:

1. Go to **Azure Active Directory** → **Enterprise applications**
2. Find your app
3. Go to **Users and groups** or **Activity** → **Sign-ins**
4. You'll see the user who authorized
5. Click on the user to see what permissions they consented to

---

## Troubleshooting

### Problem: "AADSTS65001: The user or administrator has not consented"

**Cause:** User hasn't completed OAuth flow or consent was revoked

**Solution:**
1. Have user re-authorize via Paperless-ngx UI
2. Click "Enable OAuth2 Mail" again
3. Complete the consent flow

### Problem: "AADSTS50011: The redirect URI specified in the request does not match"

**Cause:** Mismatch between redirect URI in app registration and Paperless-ngx configuration

**Solution:**
1. Check Paperless-ngx URL (e.g., `https://paperless.example.com`)
2. Verify redirect URI in Azure: `https://paperless.example.com/api/oauth/callback/`
3. Ensure trailing slash matches
4. Ensure HTTPS (not HTTP) in production

### Problem: "Can't find IMAP/SMTP delegated permissions in portal"

**Cause:** You're looking for something that doesn't need to be configured

**Solution:**
- **Don't add them!** They are requested dynamically
- Only Application permissions appear in the portal for Exchange
- Delegated permissions for IMAP/SMTP use dynamic consent

### Problem: "Authentication failed: IMAP/SMTP not working"

**Cause:** Could be multiple issues

**Solutions:**
1. **Check token expiration:**
   - Tokens expire after 1 hour
   - Paperless-ngx should auto-refresh using refresh token
   - Check logs for refresh failures

2. **Verify account type:**
   - Must be a Microsoft 365 mailbox (not on-premises Exchange)
   - Must support modern authentication (legacy auth deprecated)

3. **Check tenant settings:**
   - Some organizations disable IMAP/SMTP access
   - Contact IT admin to enable Exchange protocols

### Problem: "Need admin consent"

**Cause:** Tenant policy requires admin approval for all apps

**Solution:**
1. Admin goes to **Azure AD** → **Enterprise applications** → Your app
2. Click **Permissions** in left menu
3. Click **Grant admin consent for [organization]**
4. Users can then authorize without admin intervention

---

## Security Best Practices

1. **Use strong client secrets:**
   - Choose longer expiration periods to reduce maintenance
   - Rotate secrets before expiration
   - Store securely (use environment variables, not hardcoded)

2. **Restrict access if needed:**
   - Enable "User assignment required" in Enterprise Application
   - Assign only specific users/groups who need mail access

3. **Monitor usage:**
   - Review sign-in logs in Azure AD
   - Check for unusual activity
   - Revoke tokens for compromised accounts

4. **Use HTTPS:**
   - Always use HTTPS for redirect URIs in production
   - HTTP only acceptable for localhost development

5. **Conditional Access (Enterprise):**
   - Configure conditional access policies in Azure AD
   - Require MFA for sensitive apps
   - Restrict by location/device if needed

---

## Advanced: Multi-Tenant Applications

If you want to support users from **any** Microsoft 365 organization:

1. **App Registration:**
   - Choose "Accounts in any organizational directory (Any Azure AD directory - Multitenant)"
   - Use `common` endpoint instead of tenant-specific

2. **Redirect URI:**
   - Same as single-tenant: `https://your-domain/api/oauth/callback/`

3. **Consent:**
   - Users from ANY organization can authorize
   - Each organization's admin may need to approve first
   - Dynamic consent still works the same way

4. **Considerations:**
   - More complex security model
   - Different organizations may have different policies
   - Users need to remember which tenant they're using

---

## Summary

### Minimum Required Configuration

```
Azure AD App Registration
├── Name: Paperless-ngx Mail Access
├── Application (client) ID: <copy this>
├── Client Secret: <copy this>
├── Redirect URI: https://your-paperless-domain/api/oauth/callback/
└── API Permissions:
    └── Microsoft Graph → User.Read (Delegated) [auto-added, keep it]
```

**That's it!** IMAP and SMTP scopes are requested dynamically.

### In Paperless-ngx Configuration

Set these environment variables:

```bash
OUTLOOK_OAUTH_CLIENT_ID=<your-application-client-id>
OUTLOOK_OAUTH_CLIENT_SECRET=<your-client-secret>
```

### User Workflow

1. User creates Mail Account in Paperless-ngx
2. Clicks "Enable OAuth2 Mail" → Outlook
3. Redirected to Microsoft login
4. Sees consent screen requesting IMAP + SMTP access
5. Clicks Accept
6. Returns to Paperless-ngx with working account

### For SMTP Sending (v1.0.18+)

When you enable an account for sending:
1. Users need to **re-authorize** to grant SMTP scope
2. Microsoft consent screen will show "Send mail on your behalf"
3. Same app registration works for both IMAP and SMTP
4. No changes needed in Azure Portal

---

## App-Only Send Mode (Personal Mailboxes)

### Background

By default, Paperless-ngx uses the **delegated token** (the signed-in `casabot` account) for sending.  This works perfectly for shared mailboxes, but Graph API refuses cross-user calls with delegated tokens when the target is a **personal (licensed) mailbox** — returning `404 ErrorItemNotFound` regardless of Exchange permissions.

To send as any personal mailbox in the tenant (e.g. `hoebold@wgbg.de`) and have the Sent Items copy land in **that user's Sent Items folder**, enable app-only send mode.

### Azure Portal — One-Time Admin Setup

1. Go to [Azure Portal](https://portal.azure.com) → **App registrations** → your Paperless app
2. Click **API permissions** in the left menu
3. Click **Add a permission** → **Microsoft Graph** → **Application permissions**
4. Search for `Mail.Send` and tick the **Application** variant (NOT the delegated one)
5. Click **Add permissions**
6. Click **Grant admin consent for [your organisation]** and confirm

That is the **only** Azure change needed.  The existing delegated permissions (`Mail.Read`, `Mail.Send` delegated, etc.) remain untouched.

### Paperless Environment Variables

Add to your `docker-compose.env` / `.env`:

```bash
# Your Azure AD tenant — find it on the App Registration Overview page
PAPERLESS_OUTLOOK_OAUTH_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Enable app-only sending
PAPERLESS_OUTLOOK_OAUTH_USE_APP_SEND=true
```

The same `PAPERLESS_OUTLOOK_OAUTH_CLIENT_ID` and `PAPERLESS_OUTLOOK_OAUTH_CLIENT_SECRET` are reused — no new app registration needed.

### What Changes, What Doesn't

| | Before | After |
|---|---|---|
| Mail receiving | Delegated token | Delegated token (unchanged) |
| Sending to shared mailbox | Delegated token | App-only token |
| Sending to personal mailbox | ❌ 404 error | ✅ App-only token |
| Per-user Send As delegation | Not required | Not required |
| Mail account in Paperless UI | Configured as today | Unchanged |
| GUI re-authorization needed? | — | No |

### Mixing Delegated and Application Permissions

It is fully supported and common to have both delegated and application permissions on the same app registration.  They produce different tokens via different flows and never conflict.  Microsoft explicitly documents this pattern for hybrid service/user apps.

---

## References

- [Microsoft Identity Platform Documentation](https://docs.microsoft.com/en-us/azure/active-directory/develop/)
- [OAuth 2.0 in Azure AD](https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-auth-code-flow)
- [Exchange Legacy Protocol OAuth](https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth)
- [Dynamic Consent in Azure AD](https://docs.microsoft.com/en-us/azure/active-directory/develop/consent-framework)

---

**Last Updated:** January 28, 2026  
**Paperless-ngx Version:** v2.x with OAuth2 mail support
