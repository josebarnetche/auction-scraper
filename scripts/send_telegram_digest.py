#!/usr/bin/env python3
"""Send daily digest to Telegram users.

This script is designed to be run via cron or GitHub Actions at specific hours.
It sends the daily digest to all users who have enabled it for the current hour.

Usage:
    # Send digest for current Argentina hour
    python scripts/send_telegram_digest.py

    # Send digest for specific hour
    python scripts/send_telegram_digest.py --hour 9

    # Dry run (show what would be sent)
    python scripts/send_telegram_digest.py --dry-run

Environment variables:
    TELEGRAM_BOT_TOKEN: Bot token from @BotFather (required)

GitHub Actions example:
    name: Telegram Digest
    on:
      schedule:
        # Run every hour
        - cron: '0 * * * *'
    jobs:
      send-digest:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with:
              python-version: '3.11'
          - run: pip install python-telegram-bot>=20.0
          - run: python scripts/send_telegram_digest.py
            env:
              TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def send_digest(hour: int, dry_run: bool = False) -> int:
    """Send daily digest for specified hour.

    Args:
        hour: Argentina hour (0-23)
        dry_run: If True, don't actually send messages

    Returns:
        Number of users notified
    """
    from src.telegram.alerts import DigestJob

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        return 0

    job = DigestJob(token, str(project_root))

    # Get users for this hour
    users = job.data.get_users_for_digest_hour(hour)

    if not users:
        logger.info(f"No users want digest at hour {hour}")
        return 0

    logger.info(f"Found {len(users)} users for hour {hour}")

    if dry_run:
        for user in users:
            logger.info(f"Would send to user {user.user_id} (@{user.username})")
        return len(users)

    # Send digests
    count = await job.run(hour)
    logger.info(f"Sent digest to {count} users")

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Send Telegram daily digest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--hour",
        type=int,
        help="Argentina hour (0-23). Defaults to current hour."
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent without sending"
    )

    args = parser.parse_args()

    # Determine hour
    if args.hour is not None:
        hour = args.hour
    else:
        # Current Argentina hour (UTC-3)
        now = datetime.now(timezone.utc)
        hour = (now.hour - 3) % 24

    logger.info(f"Running digest for Argentina hour {hour}:00")

    # Run async
    count = asyncio.run(send_digest(hour, args.dry_run))

    if count > 0:
        logger.info(f"Successfully processed {count} users")
    else:
        logger.info("No digests sent")


if __name__ == "__main__":
    main()
