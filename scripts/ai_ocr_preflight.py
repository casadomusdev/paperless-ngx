#!/usr/bin/env python3
"""
AI OCR pre-flight skip detection (RKC customization).

Decides whether a document is worth sending to the AI OCR provider at all.

Tiny images (icons, favicons, thumbnails) and other trivially small inputs
still get consumed into paperless as normal documents, but they physically
cannot contain text, so an OCR request would only ever return an empty
response.  That empty response then triggers the (intentional) empty-content
retry loop, wasting API cost and stalling the consumption pipeline.  Skipping
them up front avoids both.

This module is deliberately stdlib-only and best-effort:

- Geometry is probed with tools already present in the paperless-ngx image
  (ImageMagick ``identify`` and poppler ``pdfinfo``).
- If the geometry cannot be determined the caller must NOT skip - we fail open
  so a missing tool can never silently drop a real document.
"""

import os
import re
import subprocess

_IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".tif", ".tiff",
    ".bmp", ".gif", ".webp", ".heic",
}
_PDF_EXTS = {".pdf"}
_PROBE_TIMEOUT = 15
_PAGE_SIZE_RE = re.compile(r"Page size:\s*([\d.]+)\s*x\s*([\d.]+)")


def _run(cmd):
    """Run a probe command; return stdout on success, None on any failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_PROBE_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def probe_image_pixels(path):
    """Return (width, height) in pixels for an image file, or None."""
    out = _run(["identify", "-format", "%w %h", path])
    if not out or not out.strip():
        return None
    first = out.strip().splitlines()[0].strip()
    try:
        w, h = first.split()
        return int(w), int(h)
    except (ValueError, IndexError):
        return None


def probe_pdf_page_points(path):
    """Return (width, height) of a PDF's first page in points, or None."""
    out = _run(["pdfinfo", path])
    if not out:
        return None
    match = _PAGE_SIZE_RE.search(out)
    if not match:
        return None
    try:
        return int(round(float(match.group(1)))), int(round(float(match.group(2))))
    except ValueError:
        return None


def probe_geometry(path):
    """Dispatch to the right geometry probe by extension; None if unknown."""
    ext = os.path.splitext(path)[1].lower()
    if ext in _PDF_EXTS:
        return probe_pdf_page_points(path)
    if ext in _IMAGE_EXTS:
        return probe_image_pixels(path)
    return None


def _pick_probe_target(archive_path, source_path):
    """Prefer the original image source (exact pixel size); else the archive."""
    if source_path and os.path.isfile(source_path):
        if os.path.splitext(source_path)[1].lower() in _IMAGE_EXTS:
            return source_path
    if archive_path and os.path.isfile(archive_path):
        return archive_path
    return None


def _file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def should_skip_ocr(archive_path, source_path="", min_px=100, min_bytes=2048):
    """Decide whether AI OCR should be skipped for this document.

    Returns ``(skip, reason)``.

    Skips when the smaller page/image dimension is below ``min_px`` (``0``
    disables the dimension check).  When geometry is unavailable, a size-only
    heuristic applies to images: files below ``min_bytes`` (``0`` disables it)
    are treated as non-text.  Fails open - when nothing conclusive is found it
    returns ``(False, reason)`` so real documents are never dropped.
    """
    target = _pick_probe_target(archive_path, source_path)
    if not target:
        return False, "no probeable archive or source file - not skipping"

    if min_px and min_px > 0:
        geometry = probe_geometry(target)
        if geometry is not None:
            w, h = geometry
            name = os.path.basename(target)
            if min(w, h) < min_px:
                return True, (
                    f"{name} is {w}x{h} - smaller than the {min_px}px OCR floor; "
                    f"no text to OCR"
                )
            return False, f"{name} is {w}x{h} - above the {min_px}px OCR floor"

    # Geometry unknown (or dimension check disabled) - size-only fallback.
    ext = os.path.splitext(target)[1].lower()
    if ext in _IMAGE_EXTS and min_bytes and min_bytes > 0:
        size = _file_size(target)
        if size is not None and 0 < size < min_bytes:
            return True, (
                f"image is only {size:,} bytes (< {min_bytes:,}) and geometry "
                f"is unavailable - treating as non-text"
            )

    return False, "geometry unknown / inconclusive - not skipping"
