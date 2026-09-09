#!/usr/bin/env python3
"""
Standalone CLI tool for testing AI OCR on a PDF file.

Sends a PDF to the LiteLLM /v1/ocr endpoint and displays the response.
No paperless instance required for file mode — just needs AI_OCR_URL and AI_OCR_KEY.

Usage:
  python3 ai_ocr_test.py /path/to/document.pdf
  python3 ai_ocr_test.py --raw /path/to/document.pdf
  python3 ai_ocr_test.py --raw --text /path/to/document.pdf
  python3 ai_ocr_test.py --model azure-doc-intel /path/to/document.pdf
  python3 ai_ocr_test.py --rasterize /path/to/document.pdf
  python3 ai_ocr_test.py --doc-id 19713
  python3 ai_ocr_test.py --summary /path/to/document.pdf
"""

import argparse
import base64
import copy
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_ocr_quality import rasterize_pdf


def _ocr_request(url, key, model, data_url, timeout=300):
    """Send an OCR request to LiteLLM and return the parsed JSON response."""
    payload = {
        "model": model,
        "document": {"type": "document_url", "document_url": data_url},
    }
    if "mistral" in model.lower():
        payload["extract_header"] = True
        payload["extract_footer"] = True

    req = urllib.request.Request(
        f"{url}/v1/ocr",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
    elapsed = time.monotonic() - t0
    print(f"OCR request completed in {elapsed:.1f}s — HTTP {resp.status}", file=sys.stderr)
    return result


def _extract_text(ocr_result):
    """Extract text from OCR response, merging header/markdown/footer per page."""
    pages = ocr_result.get("pages", [])

    def _page_text(p):
        parts = []
        for field in ("header", "markdown", "footer"):
            val = (p.get(field) or "").strip()
            if val:
                parts.append(val)
        return "\n\n".join(parts)

    content = "\n\n".join(_page_text(p) for p in pages).strip()
    return content, len(pages)


def _response_summary(raw):
    """Truncated summary of an OCR response — excludes base64 image data."""
    pages = raw.get("pages", [])
    lines = [f"top-level keys: {sorted(k for k in raw if k != 'pages')}, pages: {len(pages)}"]
    for i, p in enumerate(pages[:10]):
        keys = sorted(p.keys())
        lines.append(f"  page[{i}]: keys={keys}")
        for k in keys:
            if k == "images":
                lines.append(f"    images: {len(p[k])} item(s)")
                continue
            v = p[k]
            vs = str(v) if v is not None else "null"
            trunc = f"{vs[:200]}...({len(vs)} chars)" if len(vs) > 200 else vs
            lines.append(f"    {k}: {trunc!r}")
    if len(pages) > 10:
        lines.append(f"  ... ({len(pages) - 10} more pages)")
    return "\n".join(lines)


def _strip_base64(ocr_result):
    """Deep-copy and strip base64 image data for readability."""
    debug = copy.deepcopy(ocr_result)
    for p in debug.get("pages", []):
        if "images" in p:
            p["images"] = [f"[{len(img)} chars base64]" if isinstance(img, str) else img for img in p["images"]]
        for k, v in list(p.items()):
            if isinstance(v, str) and len(v) > 1000 and "base64" in v[:100]:
                p[k] = f"[{len(v)} chars base64]"
    return debug


def _download_from_paperless(doc_id, paperless_url, paperless_tok):
    """Download a document's archived PDF from the paperless API."""
    headers = {"Authorization": f"Token {paperless_tok}"}

    for original_param in ("false", "true"):
        label = "archive" if original_param == "false" else "original"
        url = f"{paperless_url}/api/documents/{doc_id}/download/?original={original_param}"
        print(f"Downloading {label} from {url} ...", file=sys.stderr)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            print(f"Downloaded {len(data):,} bytes ({label}).", file=sys.stderr)
            return data
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and original_param == "false":
                print("Archive not found (404) — trying original...", file=sys.stderr)
                continue
            print(f"Error: HTTP {exc.code}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as exc:
            print(f"Error: {exc.reason}", file=sys.stderr)
            sys.exit(1)

    print("Error: could not download document.", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Test AI OCR on a PDF file or paperless document.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment variables:\n"
            "  AI_OCR_URL    LiteLLM proxy base URL (required)\n"
            "  AI_OCR_KEY    LiteLLM virtual API key (required)\n"
            "  AI_OCR_MODEL  Default OCR model (default: mistral-ocr-latest)\n"
            "  PAPERLESS_URL           Paperless URL for --doc-id mode\n"
            "  PAPERLESS_API_TOKEN     Paperless API token for --doc-id mode\n"
        ),
    )
    parser.add_argument("file", nargs="?", help="Path to PDF or image file")
    parser.add_argument("--doc-id", help="Paperless document ID (downloads via API)")
    parser.add_argument("--raw", action="store_true", help="Print full OCR response JSON (base64 stripped)")
    parser.add_argument("--text", action="store_true", help="Print extracted text (default)")
    parser.add_argument("--summary", action="store_true", help="Print truncated response summary")
    parser.add_argument("--rasterize", action="store_true", help="Rasterize PDF before sending")
    parser.add_argument("--model", help="Override AI_OCR_MODEL for this run")
    parser.add_argument("--url", help="Override AI_OCR_URL")
    parser.add_argument("--key", help="Override AI_OCR_KEY")
    parser.add_argument("--timeout", type=int, default=300, help="OCR request timeout in seconds (default: 300)")

    args = parser.parse_args()

    if not args.file and not args.doc_id:
        parser.error("Provide a file path or --doc-id")
    if args.file and args.doc_id:
        parser.error("Use either a file path or --doc-id, not both")

    # Default output mode to --text if nothing specified
    if not args.raw and not args.text and not args.summary:
        args.text = True

    # ── Configuration ──────────────────────────────────────────────────────────
    ocr_url = (args.url or os.getenv("AI_OCR_URL", "")).rstrip("/")
    ocr_key = args.key or os.getenv("AI_OCR_KEY", "")
    ocr_model = args.model or os.getenv("AI_OCR_MODEL", "mistral-ocr-latest")

    if not ocr_url:
        print("Error: AI_OCR_URL not set. Use --url or set the env var.", file=sys.stderr)
        sys.exit(1)
    if not ocr_key:
        print("Error: AI_OCR_KEY not set. Use --key or set the env var.", file=sys.stderr)
        sys.exit(1)

    # ── Get file bytes ─────────────────────────────────────────────────────────
    if args.doc_id:
        paperless_url = os.getenv("PAPERLESS_URL", "http://localhost:8000").rstrip("/")
        paperless_tok = os.getenv("PAPERLESS_API_TOKEN", "")
        if not paperless_tok:
            print("Error: PAPERLESS_API_TOKEN not set for --doc-id mode.", file=sys.stderr)
            sys.exit(1)
        file_bytes = _download_from_paperless(args.doc_id, paperless_url, paperless_tok)
        file_path = f"doc-{args.doc_id}.pdf"
    else:
        file_path = args.file
        if not os.path.isfile(file_path):
            print(f"Error: file not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        with open(file_path, "rb") as fh:
            file_bytes = fh.read()

    print(f"File: {file_path} ({len(file_bytes):,} bytes)", file=sys.stderr)
    print(f"Model: {ocr_model}", file=sys.stderr)

    # ── Rasterize (optional) ───────────────────────────────────────────────────
    rasterized_tmpdir = None
    if args.rasterize:
        ext = os.path.splitext(file_path)[1].lower()
        if ext != ".pdf":
            print("Warning: rasterization only works with PDF files — skipping.", file=sys.stderr)
        else:
            print("Rasterizing PDF...", file=sys.stderr)
            rasterized_path = rasterize_pdf(file_path)
            if rasterized_path:
                rasterized_tmpdir = os.path.dirname(rasterized_path)
                with open(rasterized_path, "rb") as fh:
                    file_bytes = fh.read()
                print(f"Rasterized: {len(file_bytes):,} bytes", file=sys.stderr)
            else:
                print("Rasterization failed — using original file.", file=sys.stderr)

    # ── Build data URL and call OCR ────────────────────────────────────────────
    ext = os.path.splitext(file_path)[1].lower()
    mime = "application/pdf" if ext == ".pdf" else "image/jpeg"
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    print(f"Sending to {ocr_url}/v1/ocr (timeout={args.timeout}s)...", file=sys.stderr)
    try:
        ocr_result = _ocr_request(ocr_url, ocr_key, ocr_model, data_url, timeout=args.timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Error: HTTP {exc.code}: {body[:500]}", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.URLError, Exception) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Output ─────────────────────────────────────────────────────────────────
    separator = "─" * 72

    if args.raw:
        print(separator)
        print("RAW OCR RESPONSE (base64 images stripped):")
        print(separator)
        print(json.dumps(_strip_base64(ocr_result), indent=2, ensure_ascii=False))
        print(separator)

    if args.summary:
        print(separator)
        print("RESPONSE SUMMARY:")
        print(separator)
        print(_response_summary(ocr_result))
        print(separator)

    if args.text:
        content, page_count = _extract_text(ocr_result)
        print(separator)
        print(f"EXTRACTED TEXT ({page_count} page(s), {len(content)} chars):")
        print(separator)
        print(content)
        print(separator)

    # ── Cleanup ────────────────────────────────────────────────────────────────
    if rasterized_tmpdir:
        import shutil
        shutil.rmtree(rasterized_tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
