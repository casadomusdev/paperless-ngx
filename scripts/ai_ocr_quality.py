#!/usr/bin/env python3
"""
OCR quality detection and PDF rasterization fallback.

Provides two capabilities for the AI OCR post-consumption pipeline:

1. Quality detection — scans OCR output for garbage/degradation patterns and
   reports whether the content is usable.  Two signals are combined:
   contiguous runs of very short alphabetic lines (e.g. "K\nK\nK\n...") and
   repetition loops (a line recurring many times, e.g. the interleaved
   "Bezirkungsbesitz\nK\nBezirkungsbesitz\nK\n..." pattern).  Detection-only —
   content is never modified.

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
from collections import Counter


def check_quality(content: str, threshold_pct: float = 30.0,
                  repeat_min: int | None = None):
    """Check OCR content for garbage/degradation patterns.

    Detection-only — never modifies or strips content.  When degradation is
    detected above the threshold, the caller should fall back to another model
    and/or rasterize and retry.

    Two independent signals are combined — the larger garbage share wins:

    1. **Contiguous garbage runs** — 3+ consecutive very short (≤2 char)
       alphabetic lines, e.g. ``"K\\nK\\nK\\n..."``.
    2. **Repetition loops** — lines that recur many times, e.g. the interleaved
       ``"Bezirkungsbesitz\\nK\\nBezirkungsbesitz\\nK\\n..."`` pattern where a
       repeated word alternates with a repeated single character.  Such a loop
       never forms a run of 3+ consecutive short lines, so signal 1 alone
       misses it.

    ``repeat_min`` is the recurrence count used by signal 2.  When ``None`` it
    is read from the ``AI_OCR_REPEAT_MIN`` env var (default 4).

    Returns a 2-tuple (is_usable, garbage_pct):

    - is_usable (bool): True if no significant degradation was found.
      False means a retry should be attempted.

    - garbage_pct (float): Percentage of total lines that look like garbage.
    """
    if not content or not content.strip():
        return False, 100.0

    lines = content.split("\n")
    total_lines = len(lines)
    if total_lines == 0:
        return False, 100.0

    if repeat_min is None:
        try:
            repeat_min = int(os.getenv("AI_OCR_REPEAT_MIN", "4"))
        except ValueError:
            repeat_min = 4
    repeat_min = max(2, repeat_min)  # a "repeat" is at least a duplicate

    run_pct = _contiguous_garbage_pct(lines, total_lines)
    repeat_pct = _repetition_garbage_pct(lines, repeat_min)

    garbage_pct = max(run_pct, repeat_pct)
    is_usable = garbage_pct < threshold_pct
    return is_usable, garbage_pct


def _contiguous_garbage_pct(lines: list, total_lines: int) -> float:
    """Percentage of lines from the first run of 3+ consecutive 'garbage' lines
    (very short alphabetic tokens) to the end of the content.  0.0 if none.

    Empty / whitespace-only lines are neutral — they don't break a run.  This
    catches the classic ``K\\nK\\nK\\n...`` degradation tail.
    """
    garbage = [False] * total_lines
    for i, line in enumerate(lines):
        stripped = line.strip()
        if 0 < len(stripped) <= 2 and stripped.isalpha():
            garbage[i] = True

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
                # Valid run followed by real content — stop scanning
                break

    # Handle case where the run extends to end of content
    if run_len >= 3 and degradation_idx is None:
        degradation_idx = run_start

    if degradation_idx is None:
        return 0.0
    # Count ALL lines from the degradation point to the end — including the
    # empty lines interleaved between the garbage ones.
    return (total_lines - degradation_idx) / total_lines * 100


def _repetition_garbage_pct(lines: list, repeat_min: int) -> float:
    """Percentage of non-empty, alphanumeric lines that belong to a repeated
    group — a line whose exact stripped text occurs at least ``repeat_min``
    times.  Empty and symbol-only lines (e.g. ``-``, ``•``) are ignored.
    """
    stripped = [l.strip() for l in lines
                if l.strip() and any(c.isalnum() for c in l)]
    if not stripped:
        return 0.0
    counts = Counter(stripped)
    repeated = sum(c for c in counts.values() if c >= repeat_min)
    return repeated / len(stripped) * 100


def is_table_only(ocr_result: dict) -> bool:
    """Check if Mistral classified the entire document as tables only.

    When Mistral returns only 'table' blocks (no 'text' blocks), it often
    means the model made an incorrect page-segmentation decision — e.g.,
    treating a horizontal line as a table boundary and ignoring the header
    content above it.

    Returns True if ALL blocks across ALL pages are type 'table' with no
    'text' blocks present.
    """
    pages = ocr_result.get("pages", [])
    if not pages:
        return False

    has_any_block = False
    has_text_block = False

    for page in pages:
        for block in page.get("blocks", []):
            has_any_block = True
            if block.get("type") != "table":
                has_text_block = True

    return has_any_block and not has_text_block


def llm_quality_score(content: str, api_url: str, api_key: str,
                      model: str, sample_chars: int = 2000) -> int | None:
    """Ask a cheap LLM to rate OCR text quality (0-100).

    Samples the first and last portion of the content (skipping the middle)
    to keep token costs minimal while catching both header and tail issues.

    Returns the score as an integer, or None on failure or invalid response.
    """
    import json as _json
    import urllib.error as _urllib_error
    import urllib.request as _urllib_request

    # Sample: first half + last half (skip the middle for long documents)
    if len(content) > sample_chars:
        half = sample_chars // 2
        sample = content[:half] + "\n[...]\n" + content[-half:]
    else:
        sample = content

    prompt = (
        "Rate the quality of this OCR text on a scale of 0 to 100.\n\n"
        "Examples:\n"
        "- 95: Clean real words, complete sentences, proper formatting\n"
        "- 70: Mostly readable but some garbled words or missing characters\n"
        "- 40: Many garbled words, repetitive patterns, incomplete text\n"
        "- 10: Mostly garbage characters, not real words\n\n"
        "Return ONLY the number, nothing else.\n\n"
        f"{sample}"
    )

    payload = _json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8,
        "temperature": 0.0,
    }).encode("utf-8")

    req = _urllib_request.Request(
        f"{api_url}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with _urllib_request.urlopen(req, timeout=15) as resp:
            result = _json.loads(resp.read())
        text = result["choices"][0]["message"]["content"].strip()
        digits = "".join(c for c in text if c.isdigit())
        score = int(digits) if digits else None
        if score is not None and 0 <= score <= 100:
            return score
        return None
    except Exception:
        return None


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
