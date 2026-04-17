# TODO.md

## Phase 1: Settings

- [x] Add 3 new env vars to `settings.py`: `MAIL_SEND_WEBHOOK_URL`, `MAIL_SEND_WEBHOOK_TOKEN`, `MAIL_SEND_WEBHOOK_TOKEN_HEADER`

## Phase 2: Core Logic (mail.py)

- [x] Add `fire_mail_send_webhook(email)` helper to `documents/mail.py`
- [x] Update `send_email()` return type to `tuple[int, str | None]`
- [x] Update `create_mail_send_note()` to accept `webhook_note` param and append it to note

## Phase 3: Caller Updates

- [x] Update `email_action()` in `signals/handlers.py` to unpack tuple + pass `webhook_note`
- [x] Update `email_documents()` in `views.py` to unpack tuple + pass `webhook_note`

## Phase 4: Documentation

- [x] Update `RKC_CUSTOMIZATIONS.md`: new feature, 3 new env vars, version history v1.4.0
- [x] Update `docs/rkc/mail-system.md`: new env var rows + Mail Send Webhook section

## Future Improvements

- Consider adding a per-webhook retry mechanism (e.g., 1 retry with backoff) for transient failures
- Consider making the webhook fire asynchronously via Celery task to avoid any latency on manual sends
- Consider adding a `source` field to the webhook payload indicating whether the send was "workflow" or "manual"
- Consider filtering attachments from webhook payload when they exceed a configurable size threshold
