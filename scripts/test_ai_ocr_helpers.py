#!/usr/bin/env python3
"""
Offline unit tests for the AI OCR helper scripts.

No network, no server, no paperless instance required — urllib is mocked.
Covers the shared HTTP retry helper (`ai_ocr_http`) and the OCR quality
detector (`ai_ocr_quality`).

Run:
  python3 scripts/test_ai_ocr_helpers.py
  # or
  python3 -m unittest scripts.test_ai_ocr_helpers -v
"""

import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_ocr_http import http_request, retry_delay  # noqa: E402
from ai_ocr_quality import check_quality  # noqa: E402


class _FakeResp:
    """Minimal stand-in for the http.client response returned by urlopen."""

    def __init__(self, body: bytes = b"ok", status: int = 200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(code, headers=None):
    return urllib.error.HTTPError(
        "http://example.test/", code, "err", headers or {}, None,
    )


class RetryDelayTests(unittest.TestCase):
    def test_exponential_backoff(self):
        self.assertEqual(retry_delay(1, 5), 5)
        self.assertEqual(retry_delay(2, 5), 10)
        self.assertEqual(retry_delay(3, 5), 20)

    def test_respects_retry_after_on_429(self):
        exc = _http_error(429, {"Retry-After": "30"})
        self.assertEqual(retry_delay(1, 5, exc), 30)

    def test_retry_after_ignored_on_other_codes(self):
        exc = _http_error(500, {"Retry-After": "30"})
        self.assertEqual(retry_delay(1, 5, exc), 5)


class HttpRequestTests(unittest.TestCase):
    def setUp(self):
        self._sleep = mock.patch("ai_ocr_http.time.sleep")
        self._sleep.start()
        self.addCleanup(self._sleep.stop)

    def _run(self, side_effect, **kwargs):
        with mock.patch(
            "urllib.request.urlopen", side_effect=side_effect,
        ) as urlopen:
            result = http_request("http://example.test/", **kwargs)
        return result, urlopen

    def test_success_returns_body_and_status(self):
        (body, status), urlopen = self._run(
            [_FakeResp(b"hello", 200)],
        )
        self.assertEqual(body, b"hello")
        self.assertEqual(status, 200)
        self.assertEqual(urlopen.call_count, 1)

    def test_retries_transient_urlerror_then_succeeds(self):
        calls = [urllib.error.URLError("Name or service not known"),
                 _FakeResp(b"ok", 200)]
        (body, status), urlopen = self._run(
            calls, retries=2, retry_base=1,
        )
        self.assertEqual(body, b"ok")
        self.assertEqual(status, 200)
        self.assertEqual(urlopen.call_count, 2)

    def test_retries_http_500_then_succeeds(self):
        calls = [_http_error(500), _FakeResp(b"ok", 200)]
        (body, status), urlopen = self._run(
            calls, retries=2, retry_base=1,
        )
        self.assertEqual(status, 200)
        self.assertEqual(urlopen.call_count, 2)

    def test_non_retryable_http_error_raises_immediately(self):
        with mock.patch(
            "urllib.request.urlopen", side_effect=_http_error(404),
        ) as urlopen:
            with self.assertRaises(urllib.error.HTTPError):
                http_request("http://example.test/", retries=3, retry_base=1)
        self.assertEqual(urlopen.call_count, 1)

    def test_exhausts_retries_and_raises(self):
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Name or service not known"),
        ) as urlopen:
            with self.assertRaises(urllib.error.URLError):
                http_request("http://example.test/", retries=2, retry_base=1)
        self.assertEqual(urlopen.call_count, 3)  # 1 initial + 2 retries

    def test_log_callback_receives_retry_messages(self):
        messages = []
        calls = [urllib.error.URLError("boom"), _FakeResp(b"ok", 200)]
        with mock.patch(
            "urllib.request.urlopen", side_effect=calls,
        ):
            http_request(
                "http://example.test/", retries=1, retry_base=1,
                log=messages.append, label="PATCH",
            )
        self.assertEqual(len(messages), 1)
        self.assertIn("PATCH", messages[0])
        self.assertIn("Retrying", messages[0])


class CheckQualityTests(unittest.TestCase):
    def test_clean_content_is_usable(self):
        usable, pct = check_quality(
            "Rechnung Nr. 12345\nBetrag: 99,00 EUR\nDatum: 19.10.2026\n",
        )
        self.assertTrue(usable)
        self.assertEqual(pct, 0.0)

    def test_contiguous_garbage_run_detected(self):
        content = "Header line\n" + "\n".join(["K"] * 12)
        usable, pct = check_quality(content)
        self.assertFalse(usable)
        self.assertGreater(pct, 30)

    def test_interleaved_repetition_loop_detected(self):
        content = "Rechnung\n" + "Bezirkungsbesitz\nK\n" * 6
        usable, pct = check_quality(content)
        self.assertFalse(usable)
        self.assertGreater(pct, 30)

    def test_inline_repetition_detected(self):
        content = "567a/" * 400
        usable, pct = check_quality(content)
        self.assertFalse(usable)
        self.assertGreater(pct, 30)

    def test_empty_content_not_usable(self):
        usable, pct = check_quality("")
        self.assertFalse(usable)
        self.assertEqual(pct, 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
