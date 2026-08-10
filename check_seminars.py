#!/usr/bin/env python3
"""Monitor Harvard First-Year Seminars "Fall Seminars with Open Seats".

Fetches the seminar directory page, extracts seminars tagged with the
"Fall Seminars with Open Seats" category (WordPress term ID 32), diffs
against the committed state.json, and emails azweiback1618@gmail.com
when seminars are added or removed. Stdlib only.

Env vars required to send email: GMAIL_ADDRESS, GMAIL_APP_PASSWORD.
"""

import html
import json
import os
import re
import smtplib
import ssl
import sys
import urllib.request
from email.message import EmailMessage
from pathlib import Path

PAGE_URL = "https://firstyearseminarprogram.college.harvard.edu/seminars/"
OPEN_SEATS_TERM_ID = "32"
STATE_FILE = Path(__file__).parent / "state.json"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

ITEM_RE = re.compile(
    r'<div class="cp-dir-content-grid-item[^"]*" data-entry-id="(?P<id>\d+)">'
    r"(?P<body>.*?)"
    r'cp-dir-field-cp_directory_category-\d+" data-value="(?P<cats>[^"]*)"',
    re.S,
)
TITLE_RE = re.compile(r'cp-dir-field-post_title" data-value="([^"]*)"')
LINK_RE = re.compile(r'cp-dir-field-post_title"[^>]*><a href="([^"]*)"')


def ssl_context():
    # Fall back to certifi's CA bundle when the system store is unusable
    # (common with python.org installs on macOS).
    ctx = ssl.create_default_context()
    if not ctx.cert_store_stats().get("x509_ca"):
        try:
            import certifi

            ctx.load_verify_locations(certifi.where())
        except ImportError:
            pass
    return ctx


def fetch_page():
    req = urllib.request.Request(PAGE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60, context=ssl_context()) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_seminars(page_html):
    """Return (total_item_count, {entry_id: {title, url}}) for open-seat fall seminars."""
    open_seats = {}
    total = 0
    for m in ITEM_RE.finditer(page_html):
        total += 1
        cats = set(m.group("cats").split(","))
        if OPEN_SEATS_TERM_ID not in cats:
            continue
        body = m.group("body")
        title_m = TITLE_RE.search(body)
        link_m = LINK_RE.search(body)
        title = html.unescape(title_m.group(1)) if title_m else f"(untitled #{m.group('id')})"
        url = link_m.group(1).split("?")[0] if link_m else PAGE_URL
        open_seats[m.group("id")] = {"title": title, "url": url}
    return total, open_seats


def send_email(subject, body):
    address = os.environ.get("GMAIL_ADDRESS")
    password = (os.environ.get("GMAIL_APP_PASSWORD") or "").replace(" ", "")
    recipient = os.environ.get("EMAIL_TO") or address
    if not address or not password:
        print("GMAIL_ADDRESS/GMAIL_APP_PASSWORD not set; would have sent:")
        print(f"Subject: {subject}\n\n{body}")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = address
    msg["To"] = recipient
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl_context()) as smtp:
        smtp.login(address, password)
        smtp.send_message(msg)
    print(f"Email sent: {subject}")
    return True


def seminar_lines(entries):
    return "\n".join(
        f"  - {info['title']}\n    {info['url']}"
        for _, info in sorted(entries.items(), key=lambda kv: kv[1]["title"].lower())
    )


def main():
    try:
        page_html = fetch_page()
    except Exception as exc:
        print(f"ERROR: failed to fetch page: {exc}", file=sys.stderr)
        send_email(
            "[Seminar Monitor] Fetch failed — monitor may be broken",
            f"Could not fetch {PAGE_URL}:\n\n{exc}\n\n"
            "State was not updated; will retry on the next scheduled run.",
        )
        return 1

    total, current = parse_seminars(page_html)
    print(f"Parsed {total} total seminars, {len(current)} with open fall seats.")

    if total == 0:
        print("ERROR: parsed 0 items — page markup may have changed.", file=sys.stderr)
        send_email(
            "[Seminar Monitor] Parsed 0 seminars — monitor may be broken",
            f"The page at {PAGE_URL} fetched OK but no seminar items were found.\n"
            "The site's markup may have changed. State was not updated.",
        )
        return 1

    if not STATE_FILE.exists():
        STATE_FILE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        send_email(
            f"[Seminar Monitor] Now watching — {len(current)} fall seminars with open seats",
            "Monitoring is live. You'll get an email whenever this list changes.\n\n"
            f"Current fall seminars with open seats ({len(current)}):\n\n"
            + seminar_lines(current),
        )
        return 0

    previous = json.loads(STATE_FILE.read_text())
    added = {k: v for k, v in current.items() if k not in previous}
    removed = {k: v for k, v in previous.items() if k not in current}

    if not added and not removed:
        print("No changes.")
        return 0

    parts = []
    if added:
        parts.append(f"ADDED ({len(added)}):\n\n" + seminar_lines(added))
    if removed:
        parts.append(f"REMOVED ({len(removed)}):\n\n" + seminar_lines(removed))
    parts.append(f"Now {len(current)} fall seminars with open seats.\n{PAGE_URL}")

    summary_bits = []
    if added:
        summary_bits.append(f"{len(added)} added")
    if removed:
        summary_bits.append(f"{len(removed)} removed")
    subject = "[Seminar Monitor] Open-seat seminars changed: " + ", ".join(summary_bits)

    send_email(subject, "\n\n".join(parts))
    STATE_FILE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(f"State updated: +{len(added)} / -{len(removed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
