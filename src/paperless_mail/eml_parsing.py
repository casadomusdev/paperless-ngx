"""
RKC: Robust .eml parsing.

Paperless-ngx rejects an .eml outright when imap_tools cannot derive a sender
address: ``email.utils.getaddresses()`` returns nothing for an unquoted display
name containing square brackets in front of an angle-addr, for example
``E-Rechnung [Schaal & Mueller] <e-rechnung@schaal-mueller.de>``. E-invoicing
senders emit exactly that shape unencoded, so those mails never consume.

This module parses the raw file and, when ``from_values`` is missing, best-
effort extracts an address from ``From`` -> ``Sender`` -> ``Reply-To`` ->
``Return-Path`` (first via ``getaddresses``, then a tolerant regex) and
synthesizes an ``imap_tools.EmailAddress`` so the message still consumes. A
message carrying no address anywhere still raises ``ParseError``.
"""

import email
import re
from email.header import Header
from email.header import decode_header
from email.utils import getaddresses
from pathlib import Path

from imap_tools import EmailAddress
from imap_tools import MailMessage

from documents.parsers import ParseError

# Candidate headers, in order of preference for the displayed sender
_FROM_HEADERS = ("From", "Sender", "Reply-To", "Return-Path")

# Tolerant address matcher: catches both <addr@host> and bare addr@host
_ADDRESS_RE = re.compile(r"[^\s<>@,;:]+@[^\s<>@,;:]+")


def _decode_chunk(chunk, charset) -> str:
    """Decode one header chunk, tolerating unknown charsets"""
    if isinstance(chunk, bytes):
        try:
            return chunk.decode(charset or "utf-8", "ignore")
        except LookupError:
            return chunk.decode("utf-8", "ignore")
    return chunk


def _header_to_text(value) -> str:
    """
    Return a raw header value as a single decoded string.

    Handles the ``email.header.Header`` objects the email parser produces for
    8-bit/non-ASCII header values.
    """
    if isinstance(value, Header):
        return "".join(
            _decode_chunk(chunk, charset) for chunk, charset in decode_header(value)
        )
    if isinstance(value, bytes):
        return _decode_chunk(value, None)
    return str(value)


def _decode_name(name: str) -> str:
    """Decode RFC 2047 encoded words inside a display name"""
    return "".join(
        _decode_chunk(chunk, charset) for chunk, charset in decode_header(name)
    ).strip()


def _address_from_header(value) -> EmailAddress | None:
    """
    Extract a single address from one header value.

    Tries the standard parser first, then falls back to a regex so malformed
    display names do not lose the address entirely.
    """
    text = _header_to_text(value).replace("\r", " ").replace("\n", " ")
    for name, addr in getaddresses([text]):
        if addr and "@" in addr:
            return EmailAddress(_decode_name(name.strip()), addr.strip())

    match = _ADDRESS_RE.search(text)
    if match is None:
        return None

    addr = match.group(0)
    name = text.replace(addr, "").strip().strip("<>").strip().strip('"').strip()
    return EmailAddress(name, addr)


def tolerant_from_values(raw: bytes) -> EmailAddress | None:
    """Best-effort sender extraction from a malformed .eml"""
    try:
        message = email.message_from_bytes(raw)
    except Exception:  # pragma: no cover - defensive
        return None

    for header in _FROM_HEADERS:
        value = message.get(header)
        if not value:
            continue
        address = _address_from_header(value)
        if address is not None:
            return address
    return None


def parse_eml_to_message(filepath: Path) -> MailMessage:
    """
    Parse the given .eml file into an ``imap_tools.MailMessage``.

    Raises ``ParseError`` when the file cannot be read or carries no sender
    address in any of the standard headers.
    """
    try:
        with Path(filepath).open("rb") as eml:
            raw = eml.read()
        parsed = MailMessage.from_bytes(raw)
    except ParseError:
        raise
    except Exception as err:
        raise ParseError(f"Could not parse {filepath}: {err}") from err

    if parsed.from_values is None:
        fallback = tolerant_from_values(raw)
        if fallback is None:
            raise ParseError(f"Could not parse {filepath}: Missing 'from'")
        # cached_property values live on the instance, so assigning here makes
        # the synthesized sender visible to MailMessage.from_ as well
        parsed.from_values = fallback
        parsed.from_ = fallback.email

    return parsed
