#!/usr/bin/env python3
"""
Shared HTTP helper for the AI OCR scripts.

Provides a single retry-capable request function used for the paperless API
calls (tag fetch, content PATCH).  Transient failures — DNS hiccups
(``gaierror`` / "Name or service not known"), connection resets, timeouts and
HTTP 429/5xx — are retried with exponential backoff so a momentary network
blip does not fail an entire document consumption.  Persistent failures are
re-raised so the caller can still fail loudly.

Configuration (shared with the OCR retry logic):

  AI_OCR_MAX_RETRIES - retries after the first attempt (default 3)
  AI_OCR_RETRY_DELAY - base delay in seconds, doubles each attempt (default 5)

No third-party dependencies — Python stdlib only.
"""

import os
import time
import urllib.error
import urllib.request

# HTTP statuses that are worth retrying (rate limit + transient server errors)
RETRYABLE_HTTP_CODES = (429, 500, 502, 503, 504)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def retry_delay(attempt: int, base: int, exc: object = None) -> int:
    """Delay in seconds for retry ``attempt`` (1-indexed).

    Exponential backoff (``base * 2**(attempt-1)``).  When ``exc`` is an HTTP
    429 response carrying a ``Retry-After`` header, that value is honoured
    when it is larger than the computed delay.
    """
    delay = base * (2 ** (attempt - 1))
    if exc is not None and getattr(exc, "code", 0) == 429:
        ra = getattr(getattr(exc, "headers", {}), "get", lambda *_: "")(
            "Retry-After", "",
        )
        if str(ra).isdigit():
            delay = max(int(ra), delay)
    return delay


def http_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    data: bytes | None = None,
    timeout: int = 60,
    retries: int | None = None,
    retry_base: int | None = None,
    log=None,
    label: str | None = None,
):
    """Perform an HTTP request, retrying transient failures with backoff.

    Retries DNS/connection errors (``urllib.error.URLError``), timeouts and
    HTTP 429/500/502/503/504.  Any other HTTP error is raised immediately.
    Once all attempts are exhausted the last error is re-raised so the caller
    decides how loudly to fail.

    ``retries`` / ``retry_base`` default to the ``AI_OCR_MAX_RETRIES`` /
    ``AI_OCR_RETRY_DELAY`` env vars.  ``log`` is an optional callable that
    receives human-readable progress strings.  ``label`` names the operation
    in log lines (defaults to ``method``).

    Returns a 2-tuple ``(body_bytes, status_code)``.
    """
    if retries is None:
        retries = _env_int("AI_OCR_MAX_RETRIES", 3)
    if retry_base is None:
        retry_base = _env_int("AI_OCR_RETRY_DELAY", 5)
    total = 1 + max(0, retries)
    tag = label or method

    def _note(msg: str):
        if log is not None:
            log(msg)

    req = urllib.request.Request(
        url, data=data, headers=headers or {}, method=method,
    )
    for attempt in range(1, total + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read(), resp.status
        except urllib.error.HTTPError as exc:
            if exc.code in RETRYABLE_HTTP_CODES and attempt < total:
                delay = retry_delay(attempt, retry_base, exc)
                _note(f"{tag} attempt {attempt}/{total} — HTTP {exc.code}. "
                      f"Retrying in {delay}s...")
                time.sleep(delay)
                continue
            raise
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            if attempt < total:
                reason = getattr(exc, "reason", exc)
                delay = retry_delay(attempt, retry_base)
                _note(f"{tag} attempt {attempt}/{total} — {reason}. "
                      f"Retrying in {delay}s...")
                time.sleep(delay)
                continue
            raise

    raise RuntimeError("unreachable")  # pragma: no cover
