"""Alert system for Subasto Telegram bot."""

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode

from .config import config
from .data import DataManager, UserPreferences
from .formatters import format_alert_digest, format_ending_soon_alert

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages scheduled alerts and notifications."""

    def __init__(self, bot: Bot, data_manager: DataManager):
        self.bot = bot
        self.data = data_manager
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the alert scheduler."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Alert scheduler started")

    async def stop(self) -> None:
        """Stop the alert scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Alert scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        last_digest_hour = -1
        last_ending_check = datetime.min.replace(tzinfo=timezone.utc)

        while self._running:
            try:
                now = datetime.now(timezone.utc)

                # Argentina is UTC-3
                argentina_hour = (now.hour - 3) % 24

                # Daily digest - check once per hour
                if argentina_hour != last_digest_hour:
                    last_digest_hour = argentina_hour
                    await self._send_daily_digests(argentina_hour)

                # Ending soon alerts - check every 30 minutes
                if now - last_ending_check > timedelta(minutes=30):
                    last_ending_check = now
                    await self._send_ending_soon_alerts()

                # Sleep for 5 minutes
                await asyncio.sleep(300)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)

    async def _send_daily_digests(self, hour: int) -> None:
        """Send daily digest to users who want it at this hour."""
        users = self.data.get_users_for_digest_hour(hour)

        if not users:
            return

        logger.info(f"Sending daily digest to {len(users)} users at hour {hour}")

        hot_items = self.data.get_hot_list(limit=10)

        if not hot_items:
            logger.info("No hot items for digest")
            return

        stats = self.data.get_stats()
        blue_rate = stats.get("blue_dollar_rate", 1430)

        for user in users:
            try:
                # Filter items based on user preferences
                filtered_items = self._filter_items_for_user(hot_items, user)

                if not filtered_items:
                    continue

                message = format_alert_digest(filtered_items, blue_rate)

                await self.bot.send_message(
                    chat_id=user.user_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                )

                logger.info(f"Sent digest to user {user.user_id}")

            except Exception as e:
                logger.error(f"Error sending digest to user {user.user_id}: {e}")

            # Rate limiting
            await asyncio.sleep(0.5)

    async def _send_ending_soon_alerts(self) -> None:
        """Send alerts for watchlist items ending soon."""
        users = self.data.get_users_with_alerts()

        for user in users:
            try:
                # Get user's watchlist
                watchlist = self.data.get_watchlist(user.user_id)

                if not watchlist:
                    continue

                # Find items ending in next 2 hours
                now = datetime.now(timezone.utc)
                ending_soon = []

                for item in watchlist:
                    ends_at = item.get("ends_at")
                    if not ends_at:
                        continue

                    try:
                        if isinstance(ends_at, str):
                            end_dt = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                        else:
                            end_dt = ends_at

                        time_remaining = end_dt - now
                        # Alert if ending in 1-2 hours (so we don't spam)
                        if timedelta(hours=1) < time_remaining <= timedelta(hours=2):
                            ending_soon.append(item)
                    except Exception:
                        continue

                if not ending_soon:
                    continue

                stats = self.data.get_stats()
                blue_rate = stats.get("blue_dollar_rate", 1430)

                message = format_ending_soon_alert(ending_soon, blue_rate)

                await self.bot.send_message(
                    chat_id=user.user_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                )

                logger.info(f"Sent ending soon alert to user {user.user_id}")

            except Exception as e:
                logger.error(f"Error sending ending alert to user {user.user_id}: {e}")

            await asyncio.sleep(0.5)

    def _filter_items_for_user(
        self, items: list[dict], user: UserPreferences
    ) -> list[dict]:
        """Filter items based on user preferences."""
        filtered = []

        for item in items:
            # Category filter
            if user.alert_categories:
                if item.get("category") not in user.alert_categories:
                    continue

            # Price filter
            if user.alert_max_price_usd:
                # Try to extract USD price
                price_str = item.get("price", "")
                if "USD" in price_str:
                    try:
                        price = float(price_str.replace("USD", "").replace("$", "").replace(",", "").strip())
                        if price > user.alert_max_price_usd:
                            continue
                    except ValueError:
                        pass

            # Discount filter
            if user.alert_min_discount:
                discount = item.get("discount_percent", 0)
                if discount < user.alert_min_discount:
                    continue

            filtered.append(item)

        return filtered

    async def send_instant_alert(
        self,
        listing: dict,
        matching_users: list[UserPreferences],
    ) -> None:
        """Send instant alert for a new listing to matching users."""
        if not matching_users:
            return

        from .formatters import format_listing_short

        stats = self.data.get_stats()
        blue_rate = stats.get("blue_dollar_rate", 1430)

        message = (
            "🔔 *Nueva subasta que te puede interesar!*\n\n"
            + format_listing_short(listing, blue_rate)
            + f"\n\n🔗 {listing.get('source_url', '')}"
        )

        for user in matching_users:
            try:
                await self.bot.send_message(
                    chat_id=user.user_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                )
                logger.info(f"Sent instant alert to user {user.user_id}")
            except Exception as e:
                logger.error(f"Error sending instant alert to {user.user_id}: {e}")

            await asyncio.sleep(0.5)

    async def notify_new_listings(self, new_listings: list[dict]) -> None:
        """Process new listings and send instant alerts to matching users."""
        users_with_instant = [
            u for u in self.data.get_users_with_alerts()
            if u.instant_alerts_enabled
        ]

        if not users_with_instant:
            return

        for listing in new_listings:
            # Find users whose filters match this listing
            matching_users = []

            for user in users_with_instant:
                # Check category filter
                if user.alert_categories:
                    if listing.get("category") not in user.alert_categories:
                        continue

                # Check price filter
                if user.alert_max_price_usd:
                    price_usd = listing.get("base_price_usd") or 0
                    if listing.get("currency") == "ARS":
                        stats = self.data.get_stats()
                        rate = stats.get("blue_dollar_rate", 1430)
                        price_usd = listing.get("base_price", 0) / rate

                    if price_usd > user.alert_max_price_usd:
                        continue

                # Check discount filter
                if user.alert_min_discount:
                    discount = listing.get("discount_percent", 0)
                    if discount < user.alert_min_discount:
                        continue

                matching_users.append(user)

            if matching_users:
                await self.send_instant_alert(listing, matching_users)


class DigestJob:
    """Standalone job for running daily digest from cron/scheduler."""

    def __init__(self, bot_token: str, base_path: str = "."):
        self.bot_token = bot_token
        self.data = DataManager(base_path)

    async def run(self, hour: Optional[int] = None) -> int:
        """Run digest for specified hour (or current Argentina hour)."""
        from telegram import Bot

        bot = Bot(token=self.bot_token)

        if hour is None:
            now = datetime.now(timezone.utc)
            hour = (now.hour - 3) % 24  # Argentina UTC-3

        users = self.data.get_users_for_digest_hour(hour)

        if not users:
            logger.info(f"No users want digest at hour {hour}")
            return 0

        hot_items = self.data.get_hot_list(limit=10)

        if not hot_items:
            logger.info("No hot items for digest")
            return 0

        stats = self.data.get_stats()
        blue_rate = stats.get("blue_dollar_rate", 1430)

        sent_count = 0

        for user in users:
            try:
                # Filter for user
                filtered = []
                for item in hot_items:
                    if user.alert_categories and item.get("category") not in user.alert_categories:
                        continue
                    filtered.append(item)

                if not filtered:
                    continue

                message = format_alert_digest(filtered[:5], blue_rate)

                await bot.send_message(
                    chat_id=user.user_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                )

                sent_count += 1
                logger.info(f"Sent digest to user {user.user_id}")

            except Exception as e:
                logger.error(f"Error sending to {user.user_id}: {e}")

            await asyncio.sleep(0.5)

        return sent_count
