#!/usr/bin/env python3
"""
Offline unit tests for scripts/ai_ocr_preflight.py.

No server, no network and no ImageMagick/poppler required: the geometry probes
are mocked, so these run anywhere.  Run with:

    python3 scripts/test_ai_ocr_preflight.py
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai_ocr_preflight as pf


class ProbeParsingTest(unittest.TestCase):
    def test_image_pixels_parsed(self):
        with mock.patch.object(pf, "_run", return_value="57 57\n"):
            self.assertEqual(pf.probe_image_pixels("x.png"), (57, 57))

    def test_image_pixels_first_line_of_multi_page(self):
        with mock.patch.object(pf, "_run", return_value="120 80\n200 90\n"):
            self.assertEqual(pf.probe_image_pixels("x.tif"), (120, 80))

    def test_image_pixels_bad_output_returns_none(self):
        with mock.patch.object(pf, "_run", return_value="not-a-size\n"):
            self.assertIsNone(pf.probe_image_pixels("x.png"))

    def test_image_pixels_tool_missing_returns_none(self):
        with mock.patch.object(pf, "_run", return_value=None):
            self.assertIsNone(pf.probe_image_pixels("x.png"))

    def test_pdf_page_points_parsed(self):
        out = "Pages:           1\nPage size:       595.276 x 841.89 pts (A4)\n"
        with mock.patch.object(pf, "_run", return_value=out):
            self.assertEqual(pf.probe_pdf_page_points("a.pdf"), (595, 842))

    def test_pdf_page_points_missing_line_returns_none(self):
        with mock.patch.object(pf, "_run", return_value="Pages: 1\n"):
            self.assertIsNone(pf.probe_pdf_page_points("a.pdf"))

    def test_probe_geometry_dispatch(self):
        with mock.patch.object(pf, "probe_image_pixels", return_value=(1, 2)) as img, \
             mock.patch.object(pf, "probe_pdf_page_points", return_value=(3, 4)) as doc:
            self.assertEqual(pf.probe_geometry("a.png"), (1, 2))
            self.assertEqual(pf.probe_geometry("a.pdf"), (3, 4))
            self.assertIsNone(pf.probe_geometry("a.txt"))
            img.assert_called_once_with("a.png")
            doc.assert_called_once_with("a.pdf")


class SkipDecisionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _file(self, name, size=5000):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as fh:
            fh.write(b"\0" * size)
        return path

    def test_tiny_image_skipped(self):
        img = self._file("icon.png")
        with mock.patch.object(pf, "probe_geometry", return_value=(57, 57)):
            skip, reason = pf.should_skip_ocr("", img)
        self.assertTrue(skip)
        self.assertIn("57x57", reason)

    def test_normal_image_not_skipped(self):
        img = self._file("scan.png", size=2_000_000)
        with mock.patch.object(pf, "probe_geometry", return_value=(1240, 1754)):
            skip, _ = pf.should_skip_ocr("", img)
        self.assertFalse(skip)

    def test_tiny_pdf_page_skipped(self):
        pdf = self._file("icon.pdf")
        with mock.patch.object(pf, "probe_geometry", return_value=(40, 40)):
            skip, reason = pf.should_skip_ocr(pdf, "")
        self.assertTrue(skip)
        self.assertIn("40x40", reason)

    def test_a4_pdf_not_skipped(self):
        pdf = self._file("doc.pdf", size=500_000)
        with mock.patch.object(pf, "probe_geometry", return_value=(595, 842)):
            skip, _ = pf.should_skip_ocr(pdf, "")
        self.assertFalse(skip)

    def test_fail_open_when_geometry_unknown_for_pdf(self):
        pdf = self._file("doc.pdf", size=500_000)
        with mock.patch.object(pf, "probe_geometry", return_value=None):
            skip, reason = pf.should_skip_ocr(pdf, "")
        self.assertFalse(skip)
        self.assertIn("unknown", reason)

    def test_size_fallback_skips_tiny_image(self):
        img = self._file("icon.png", size=1200)
        with mock.patch.object(pf, "probe_geometry", return_value=None):
            skip, reason = pf.should_skip_ocr("", img)
        self.assertTrue(skip)
        self.assertIn("1,200", reason)

    def test_size_fallback_keeps_large_image(self):
        img = self._file("scan.png", size=3_000_000)
        with mock.patch.object(pf, "probe_geometry", return_value=None):
            skip, _ = pf.should_skip_ocr("", img)
        self.assertFalse(skip)

    def test_both_checks_disabled_never_skips(self):
        img = self._file("icon.png", size=1200)
        with mock.patch.object(pf, "probe_geometry", return_value=(57, 57)):
            skip, _ = pf.should_skip_ocr("", img, min_px=0, min_bytes=0)
        self.assertFalse(skip)

    def test_no_target_not_skipped(self):
        skip, reason = pf.should_skip_ocr("", "")
        self.assertFalse(skip)
        self.assertIn("no probeable", reason)

    def test_archive_pdf_used_when_no_source(self):
        pdf = self._file("archive.pdf")
        with mock.patch.object(pf, "probe_geometry", return_value=(57, 57)) as probe:
            skip, _ = pf.should_skip_ocr(pdf, "")
        self.assertTrue(skip)
        probe.assert_called_once_with(pdf)

    def test_source_image_preferred_over_archive(self):
        img = self._file("orig.png")
        pdf = self._file("archive.pdf")
        with mock.patch.object(pf, "probe_geometry", return_value=(57, 57)) as probe:
            skip, _ = pf.should_skip_ocr(pdf, img)
        self.assertTrue(skip)
        probe.assert_called_once_with(img)


if __name__ == "__main__":
    unittest.main(verbosity=2)
