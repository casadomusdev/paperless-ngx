# TODO.md

## Future Improvements

- Consider adding a per-webhook retry mechanism (e.g., 1 retry with backoff) for transient failures
- Consider making the webhook fire asynchronously via Celery task to avoid any latency on manual sends
- Consider adding a `source` field to the webhook payload indicating whether the send was "workflow" or "manual"
- Consider filtering attachments from webhook payload when they exceed a configurable size threshold
