#!/usr/bin/env python3
"""
Send webhook notifications to subscribers.

This script is called automatically after the daily scraper runs,
or can be run manually to send notifications.

Usage:
    python scripts/send_webhooks.py
    python scripts/send_webhooks.py --dry-run  # Preview without sending
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.notifications.webhook_sender import WebhookSender
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Send webhook notifications")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview notifications without sending"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    sender = WebhookSender()

    # Load data
    sub_count = sender.load_subscriptions()
    listing_count = sender.load_listings()

    logger.info(f"Loaded {sub_count} active subscriptions")
    logger.info(f"Loaded {listing_count} opportunities to notify about")

    if sub_count == 0:
        logger.info("No active subscriptions - nothing to do")
        return

    if args.dry_run:
        # Preview mode - show what would be sent
        logger.info("\n=== DRY RUN - Preview Only ===\n")

        for sub in sender.subscriptions:
            matched = sender.filter_listings_for_subscription(sub)
            logger.info(f"\nSubscription: {sub.id}")
            logger.info(f"  Webhook URL: {sub.webhook_url}")
            logger.info(f"  Filters: {sub.filters}")
            logger.info(f"  Matched listings: {len(matched)}")

            if matched and args.verbose:
                for listing in matched[:5]:  # Show first 5
                    logger.info(f"    - {listing['title'][:50]}...")
                    logger.info(f"      {listing.get('match_reason', '')}")

        logger.info("\n=== End of Preview ===")
        return

    # Send notifications
    stats = await sender.send_all_notifications()

    # Print summary
    print("\n" + "=" * 50)
    print("WEBHOOK NOTIFICATION SUMMARY")
    print("=" * 50)
    print(f"Total subscriptions: {stats['total_subscriptions']}")
    print(f"Notifications sent:  {stats['notifications_sent']}")
    print(f"Notifications failed: {stats['notifications_failed']}")
    print(f"Skipped (no matches): {stats['skipped_no_matches']}")
    print(f"Total listings sent:  {stats['listings_notified']}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
