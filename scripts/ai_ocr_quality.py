#!/usr/bin/env python3
"""
OCR quality detection and PDF rasterization fallback.

Provides two capabilities for the AI OCR post-consumption pipeline:

1. Quality detection — scans OCR output for garbage/degradation patterns
   (e.g., repeated single-character lines like "K\nK\nK\n...") and returns
   a cleaned version with the garbage tail stripped.

2. PDF rasterization — converts a PDF's pages to high-resolution PNG images
   and reassembles them into a clean, pixel-based PDF.  This eliminates font
   encoding issues, unusual text layers, and other PDF-structural oddities
   that can cause OCR engines to degrade.

Dependencies: poppler-utils (pdftoppm) and ImageMagick (convert), both
already present in the paperless-ngx Docker image.
"""

import glob
import os
import subprocess
import tempfile


def check_quality(content: str, threshold_pct: float = 30.0):
    """Check OCR content for garbage/degradation patterns.

    Returns a 3-tuple (is_usable, cleaned_content, garbage_pct):

    - is_usable (bool): True if the content is good enough to use as-is
      (either clean, or after stripping a minor garbage tail).  False means
      the content has significant degradation and a rasterized retry should
      be attempted.

    - cleaned_content (str): The original content with any trailing garbage
      lines removed.  If no garbage was found, this equals the input.

    - garbage_pct (float): Percentage of total lines that were garbage.
    """
    if not content or not content.strip():
        return False, content, 100.0

    lines = content.split("\n")
    total_lines = len(lines)
    if total_lines == 0:
        return False, content, 100.0

    # ── Detect "garbage lines" ────────────────────────────────────────────────
    # A garbage line is very short (≤2 non-whitespace chars) and entirely
    # alphabetic.  This catches "K", "k", "a", "OK", "ii", etc.
    garbage = [False] * total_lines
    for i, line in enumerate(lines):
        stripped = line.strip()
        if 0 < len(stripped) <= 2 and stripped.isalpha():
            garbage[i] = True

    # ── Find the first run of 3+ consecutive garbage lines ────────────────────
    # Empty / whitespace-only lines are treated as neutral — they don't break
    # a garbage run.  This catches patterns like "K\n\nK\n\nK\n\n...".
    run_start = None
    run_len = 0
    degradation_idx = None  # index of the first garbage line in the run

    for i in range(total_lines):
        if garbage[i]:
            if run_len == 0:
                run_start = i
            run_len += 1
            if run_len >= 3 and degradation_idx is None:
                degradation_idx = run_start
        elif not lines[i].strip():
            # Empty / whitespace-only line — neutral, don't break the run
            pass
        else:
            # Non-empty, non-garbage line — breaks the run
            if run_len < 3:
                run_start = None
                run_len = 0
            else:
                # We found a valid run and hit real content — stop scanning
                break

    # Handle case where the run extends to end of content
    if run_len >= 3 and degradation_idx is None:
        degradation_idx = run_start

    # ── No garbage found ──────────────────────────────────────────────────────
    if degradation_idx is None:
        return True, content, 0.0

    # ── Calculate garbage percentage ──────────────────────────────────────────
    # Count ALL lines from the degradation point to end of content — not just
    # explicit garbage lines but also the empty lines interleaved between them.
    garbage_count = total_lines - degradation_idx
    garbage_pct = (garbage_count / total_lines) * 100

    # ── Strip the garbage tail ────────────────────────────────────────────────
    cleaned = "\n".join(lines[:degradation_idx]).strip()
    is_usable = garbage_pct < threshold_pct

    return is_usable, cleaned, garbage_pct


def rasterize_pdf(pdf_path: str, dpi: int = 300) -> str | None:
    """Convert a PDF to a rasterized (pixel-based) PDF via PNG intermediates.

    Uses pdftoppm (poppler-utils) to render each page as a high-res PNG,
    then ImageMagick convert to reassemble the PNGs into a single PDF.

    Returns the path to the rasterized PDF (inside a temp directory that the
    caller must clean up), or None if rasterization failed.
    """
    if not os.path.isfile(pdf_path):
        return None

    tmpdir = tempfile.mkdtemp(prefix="ai_ocr_raster_")
    prefix = os.path.join(tmpdir, "page")

    try:
        # ── Step 1: PDF → PNGs ────────────────────────────────────────────────
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), pdf_path, prefix],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return None

        pngs = sorted(glob.glob(f"{prefix}-*.png") + glob.glob(f"{prefix}.png"))
        if not pngs:
            return None

        # ── Step 2: PNGs → single PDF ─────────────────────────────────────────
        out_pdf = os.path.join(tmpdir, "rasterized.pdf")
        result = subprocess.run(
            ["convert"] + pngs + [out_pdf],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return None

        # Clean up intermediate PNGs — keep only the final PDF
        for png in pngs:
            os.unlink(png)

        if not os.path.isfile(out_pdf):
            return None

        return out_pdf  # Caller owns tmpdir; will clean up

    except (subprocess.TimeoutExpired, OSError):
        # Rasterization failed — clean up temp dir
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None
