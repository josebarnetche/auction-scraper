#!/usr/bin/env python3
"""
Daily Digest Sender Script.

Sends personalized email digests to all active subscribers.
Designed to run as a scheduled job (e.g., GitHub Actions, cron).

Usage:
    python scripts/send_daily_digest.py [--dry-run] [--test EMAIL]

Options:
    --dry-run       Don't actually send emails, just log
    --test EMAIL    Send test digest to specific email only
    --ending-today  Send "ending today" alerts instead of daily digest

Environment variables:
    EMAIL_PROVIDER      Email provider (resend, sendgrid, smtp, dry_run)
    RESEND_API_KEY      Resend API key
    SENDGRID_API_KEY    SendGrid API key
    VERCEL_KV_URL       Vercel KV URL for subscriber storage
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.email.sender import (
    EmailSender,
    send_digest,
    send_ending_today_alert,
)


def load_subscribers_from_file(path: Path) -> list[dict]:
    """Load subscribers from a JSON file (fallback for no KV)."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_subscribers_from_kv() -> list[dict]:
    """Load subscribers from Vercel KV via REST API."""
    kv_url = os.getenv("VERCEL_KV_REST_API_URL")
    kv_token = os.getenv("VERCEL_KV_REST_API_TOKEN")

    if not kv_url or not kv_token:
        print("Warning: Vercel KV not configured, using local file")
        return load_subscribers_from_file(Path("data/subscribers.json"))

    try:
        # Get all subscriber email hashes
        req = urllib.request.Request(
            f"{kv_url}/smembers/subscribers:emails",
            headers={"Authorization": f"Bearer {kv_token}"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            email_hashes = result.get("result", [])

        if not email_hashes:
            return []

        # Get each subscriber
        subscribers = []
        for hash in email_hashes:
            req = urllib.request.Request(
                f"{kv_url}/get/subscriber:{hash}",
                headers={"Authorization": f"Bearer {kv_token}"},
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                data = result.get("result")
                if data:
                    subscriber = json.loads(data)
                    subscribers.append(subscriber)

        return subscribers

    except Exception as e:
        print(f"Error loading from KV: {e}")
        return load_subscribers_from_file(Path("data/subscribers.json"))


def update_subscriber_kv(subscriber: dict) -> None:
    """Update subscriber in Vercel KV."""
    kv_url = os.getenv("VERCEL_KV_REST_API_URL")
    kv_token = os.getenv("VERCEL_KV_REST_API_TOKEN")

    if not kv_url or not kv_token:
        return

    try:
        email_hash = subscriber["emailHash"]
        data = json.dumps(subscriber)
        req = urllib.request.Request(
            f"{kv_url}/set/subscriber:{email_hash}",
            data=data.encode(),
            headers={
                "Authorization": f"Bearer {kv_token}",
                "Content-Type": "application/json",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30):
            pass
    except Exception as e:
        print(f"Error updating subscriber in KV: {e}")


def send_daily_digests(dry_run: bool = False, test_email: str = None):
    """Send daily digests to all active subscribers."""
    print(f"\n{'='*60}")
    print("SUBASTO DAILY DIGEST")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*60}\n")

    # Set dry run mode
    if dry_run:
        os.environ["EMAIL_PROVIDER"] = "dry_run"

    # Load subscribers
    print("Loading subscribers...")
    subscribers = load_subscribers_from_kv()
    print(f"Found {len(subscribers)} total subscribers")

    # Filter active daily subscribers
    active_daily = [
        s for s in subscribers
        if s.get("status") == "active"
        and s.get("preferences", {}).get("digestFrequency", "daily") == "daily"
    ]
    print(f"Active daily subscribers: {len(active_daily)}")

    # If test email specified, only send to that
    if test_email:
        active_daily = [s for s in active_daily if s.get("email") == test_email]
        if not active_daily:
            # Create a test subscriber
            active_daily = [{
                "email": test_email,
                "emailHash": "test",
                "unsubscribeToken": "test_token_12345",
                "preferences": {},
                "status": "active",
            }]
        print(f"Test mode: sending only to {test_email}")

    if not active_daily:
        print("No subscribers to send to.")
        return

    # Send digests
    success_count = 0
    error_count = 0
    listings_path = Path("site/api/listings.json")

    for subscriber in active_daily:
        email = subscriber.get("email", "unknown")
        print(f"\nSending to: {email}...")

        try:
            result = send_digest(
                to_email=email,
                unsubscribe_token=subscriber.get("unsubscribeToken", ""),
                preferences=subscriber.get("preferences"),
                listings_path=listings_path,
            )

            if result.success:
                print(f"  OK - Message ID: {result.message_id}")
                success_count += 1

                # Update subscriber stats
                subscriber["lastDigestSent"] = datetime.now(timezone.utc).isoformat()
                subscriber["digestCount"] = subscriber.get("digestCount", 0) + 1
                if not dry_run:
                    update_subscriber_kv(subscriber)
            else:
                print(f"  ERROR: {result.error}")
                error_count += 1

        except Exception as e:
            print(f"  EXCEPTION: {e}")
            error_count += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"  Sent: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total: {len(active_daily)}")
    print(f"{'='*60}\n")


def send_ending_today_alerts(dry_run: bool = False, test_email: str = None):
    """Send 'ending today' alerts to subscribers who opted in."""
    print(f"\n{'='*60}")
    print("SUBASTO ENDING TODAY ALERTS")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    if dry_run:
        os.environ["EMAIL_PROVIDER"] = "dry_run"

    subscribers = load_subscribers_from_kv()

    # Filter subscribers who want ending today alerts
    alert_subscribers = [
        s for s in subscribers
        if s.get("status") == "active"
        and s.get("preferences", {}).get("endingTodayAlerts", True)
    ]

    if test_email:
        alert_subscribers = [{"email": test_email, "unsubscribeToken": "test", "preferences": {}}]

    print(f"Subscribers with alerts enabled: {len(alert_subscribers)}")

    success_count = 0
    skipped_count = 0
    listings_path = Path("site/api/listings.json")

    for subscriber in alert_subscribers:
        email = subscriber.get("email", "unknown")

        result = send_ending_today_alert(
            to_email=email,
            unsubscribe_token=subscriber.get("unsubscribeToken", ""),
            preferences=subscriber.get("preferences"),
            listings_path=listings_path,
        )

        if result is None:
            print(f"  Skipped {email} (no items ending today)")
            skipped_count += 1
        elif result.success:
            print(f"  Sent to {email}")
            success_count += 1
        else:
            print(f"  Error for {email}: {result.error}")

    print(f"\nSent: {success_count}, Skipped: {skipped_count}")


def main():
    parser = argparse.ArgumentParser(description="Send Subasto email digests")
    parser.add_argument("--dry-run", action="store_true", help="Don't send, just log")
    parser.add_argument("--test", metavar="EMAIL", help="Send test to specific email")
    parser.add_argument("--ending-today", action="store_true", help="Send ending today alerts")

    args = parser.parse_args()

    if args.ending_today:
        send_ending_today_alerts(dry_run=args.dry_run, test_email=args.test)
    else:
        send_daily_digests(dry_run=args.dry_run, test_email=args.test)


if __name__ == "__main__":
    main()
