#!/usr/bin/env python3
"""
Admin utility: Check whether outbound SMTP port 25 is reachable from this container.

Run this inside the paperless worker container to verify that the SMTP port 25 probe
used by PAPERLESS_MAIL_VERIFY_RECIPIENT=dns+smtp will work correctly.

Usage:
    # Test with Gmail's MX server (default):
    python3 scripts/check_smtp_port25.py

    # Test with a specific MX host:
    python3 scripts/check_smtp_port25.py mx1.example.com

    # Run from inside the Docker container:
    docker exec <paperless-worker-container> python3 /opt/paperless/scripts/check_smtp_port25.py

Exit codes:
    0  - OK, port 25 is reachable
    1  - Connection refused (no server on that port / hard firewall RESET)
    2  - Timeout (outbound port 25 is blocked by provider/firewall)
    3  - Other network error

If you get exit code 2 (timeout), outbound port 25 is likely blocked by your cloud or
VPS provider (common on Hetzner, AWS EC2, DigitalOcean, etc.). Options:
    1. Contact provider to enable outbound port 25 (may require account verification)
    2. Keep PAPERLESS_MAIL_VERIFY_RECIPIENT=dns (the default) which skips the port probe

Note: Only port 25 is relevant for mail delivery checks. Ports 587 (submission) and
465 (SMTPS) are for outbound mail clients connecting to their own mail server — they
are not used by MX records and not relevant for verifying recipient domains.
"""
import socket
import sys

TEST_HOST = sys.argv[1] if len(sys.argv) > 1 else "smtp.gmail.com"
TEST_PORT = 25
TIMEOUT = 5.0

print(f"Testing outbound TCP connection to {TEST_HOST}:{TEST_PORT} (timeout: {TIMEOUT}s)...")
print()

try:
    conn = socket.create_connection((TEST_HOST, TEST_PORT), timeout=TIMEOUT)
    print(f"✓  SUCCESS — outbound port {TEST_PORT} is reachable at {TEST_HOST}.")
    try:
        conn.settimeout(3.0)
        banner_bytes = conn.recv(512)
        banner = banner_bytes.decode("ascii", errors="replace").strip()
        if banner:
            print(f"   SMTP banner: {banner[:120]}")
        else:
            print("   (No banner received — connection was accepted)")
    except Exception:
        print("   (No banner received within timeout — connection was accepted)")
    try:
        conn.sendall(b"QUIT\r\n")
    except Exception:
        pass
    conn.close()
    print()
    print("   PAPERLESS_MAIL_VERIFY_RECIPIENT=dns+smtp will work correctly.")
    sys.exit(0)

except ConnectionRefusedError:
    print(f"✗  REFUSED — port {TEST_PORT} actively refused at {TEST_HOST}.")
    print("   A firewall is sending TCP RESET, or no SMTP listener is present.")
    print(f"   Use PAPERLESS_MAIL_VERIFY_RECIPIENT=dns (the default) to skip the port probe.")
    sys.exit(1)

except socket.timeout:
    print(f"⚠  TIMEOUT — connection to {TEST_HOST}:{TEST_PORT} timed out after {TIMEOUT}s.")
    print("   Outbound port 25 is most likely BLOCKED by your VPS/cloud provider.")
    print()
    print("   To fix:")
    print("     1. Contact your provider to unblock outbound port 25")
    print("        (may require account verification or a support ticket).")
    print("     2. Or keep PAPERLESS_MAIL_VERIFY_RECIPIENT=dns (default) to skip the SMTP probe.")
    sys.exit(2)

except OSError as e:
    print(f"✗  ERROR — {e}")
    print(f"   Use PAPERLESS_MAIL_VERIFY_RECIPIENT=dns (the default) to skip the SMTP probe.")
    sys.exit(3)
