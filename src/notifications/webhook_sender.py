#!/usr/bin/env python3
"""
Webhook Notification Sender for Subasto API

Sends notifications to registered webhook subscribers after each scrape run.
Called automatically after the daily scraper completes.

Usage:
    python -m src.notifications.webhook_sender
    # or
    python scripts/send_webhooks.py

The sender:
1. Loads active webhook subscriptions
2. Loads the latest scraped opportunities
3. Filters opportunities based on each subscriber's filters
4. Sends POST requests to webhook URLs with matching listings
5. Includes HMAC-SHA256 signature for verification
"""

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SUBSCRIPTIONS_FILE = DATA_DIR / "webhook_subscriptions.json"
LISTINGS_FILE = PROJECT_ROOT / "site" / "api" / "listings.json"

# Webhook configuration
WEBHOOK_TIMEOUT = 10.0  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds


class WebhookSubscription:
    """Represents a webhook subscription."""

    def __init__(self, data: dict):
        self.id = data["id"]
        self.webhook_url = data["webhook_url"]
        self.secret = data["secret"]
        self.filters = data.get("filters", {})
        self.is_active = data.get("is_active", True)
        self.expires_at = data.get("expires_at")
        self.notification_count = data.get("notification_count", 0)
        self.last_notified_at = data.get("last_notified_at")
        self.raw_data = data

    def is_expired(self) -> bool:
        """Check if subscription has expired."""
        if not self.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return expires < datetime.now(timezone.utc)
        except (ValueError, AttributeError):
            return False

    def matches_listing(self, listing: dict) -> tuple[bool, str]:
        """
        Check if a listing matches this subscription's filters.
        Returns (matches: bool, reason: str).
        """
        reasons = []

        # Category filter
        categories = self.filters.get("categories", [])
        listing_category = listing.get("category", "other")

        if categories and listing_category not in categories:
            return False, ""

        reasons.append(f"category:{listing_category}")

        # Price filter (max_price_usd)
        max_price = self.filters.get("max_price_usd")
        if max_price is not None:
            listing_price_usd = self._get_price_usd(listing)
            if listing_price_usd is None or listing_price_usd > max_price:
                return False, ""
            reasons.append(f"price:${listing_price_usd:.0f}<=${max_price}")

        # Discount filter (min_discount_percent)
        min_discount = self.filters.get("min_discount_percent")
        if min_discount is not None:
            discount = listing.get("discount_percent", 0)
            if discount < min_discount:
                return False, ""
            reasons.append(f"discount:{discount:.1f}%>={min_discount}%")

        return True, ", ".join(reasons)

    def _get_price_usd(self, listing: dict) -> Optional[float]:
        """Get listing price in USD."""
        # Try direct USD price first
        if listing.get("base_price_usd"):
            return listing["base_price_usd"]

        # Convert ARS to USD using blue dollar rate
        if listing.get("currency") == "ARS" and listing.get("base_price"):
            # Default blue dollar rate if not available
            blue_rate = listing.get("blue_dollar_rate", 1200)
            return listing["base_price"] / blue_rate

        if listing.get("currency") == "USD" and listing.get("base_price"):
            return listing["base_price"]

        return None


class WebhookSender:
    """Sends webhook notifications to subscribers."""

    def __init__(self):
        self.subscriptions: list[WebhookSubscription] = []
        self.listings: list[dict] = []
        self.blue_dollar_rate: float = 1200.0  # Default rate
        self.scrape_run_id: str = ""

    def load_subscriptions(self) -> int:
        """Load active subscriptions from storage. Returns count."""
        if not SUBSCRIPTIONS_FILE.exists():
            logger.info("No subscriptions file found")
            return 0

        try:
            with open(SUBSCRIPTIONS_FILE) as f:
                data = json.load(f)

            self.subscriptions = []
            for sub_id, sub_data in data.items():
                sub = WebhookSubscription(sub_data)

                # Skip inactive or expired
                if not sub.is_active:
                    logger.debug(f"Skipping inactive subscription: {sub_id}")
                    continue
                if sub.is_expired():
                    logger.debug(f"Skipping expired subscription: {sub_id}")
                    continue

                self.subscriptions.append(sub)

            logger.info(f"Loaded {len(self.subscriptions)} active subscriptions")
            return len(self.subscriptions)

        except Exception as e:
            logger.error(f"Failed to load subscriptions: {e}")
            return 0

    def load_listings(self) -> int:
        """Load latest listings/opportunities. Returns count."""
        if not LISTINGS_FILE.exists():
            logger.error(f"Listings file not found: {LISTINGS_FILE}")
            return 0

        try:
            with open(LISTINGS_FILE) as f:
                data = json.load(f)

            # Get opportunities (already filtered for good deals)
            self.listings = data.get("top_opportunities", [])
            self.blue_dollar_rate = data.get("blue_dollar_rate", 1200.0)
            self.scrape_run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

            # Add blue rate to each listing for price conversion
            for listing in self.listings:
                listing["blue_dollar_rate"] = self.blue_dollar_rate

            logger.info(f"Loaded {len(self.listings)} opportunities")
            return len(self.listings)

        except Exception as e:
            logger.error(f"Failed to load listings: {e}")
            return 0

    def filter_listings_for_subscription(
        self, subscription: WebhookSubscription
    ) -> list[dict]:
        """Filter listings based on subscription's filters."""
        matched = []

        for listing in self.listings:
            matches, reason = subscription.matches_listing(listing)
            if matches:
                # Add match reason to listing
                listing_copy = listing.copy()
                listing_copy["match_reason"] = reason
                listing_copy["opportunity_score"] = self._calculate_score(listing)
                matched.append(listing_copy)

        # Sort by opportunity score (best deals first)
        matched.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)

        return matched

    def _calculate_score(self, listing: dict) -> int:
        """Calculate opportunity score (1-100) based on discount and category."""
        score = 50  # Base score

        # Discount contributes up to 40 points
        discount = listing.get("discount_percent", 0)
        score += min(40, int(discount * 0.6))

        # Premium listings get bonus
        if listing.get("is_premium"):
            score += 10

        # Before March (closing soon) gets bonus
        if listing.get("before_march"):
            score += 5

        return min(100, max(1, score))

    def create_payload(
        self,
        subscription: WebhookSubscription,
        matched_listings: list[dict]
    ) -> dict:
        """Create webhook payload for a subscription."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # Format listings for notification
        formatted_listings = []
        for listing in matched_listings:
            formatted_listings.append({
                "id": listing.get("id", ""),
                "title": listing.get("title", ""),
                "category": listing.get("category", "other"),
                "source": listing.get("source", ""),
                "source_url": listing.get("source_url", ""),
                "base_price": listing.get("base_price", 0),
                "currency": listing.get("currency", "ARS"),
                "base_price_usd": self._get_price_usd(listing),
                "market_price_usd": listing.get("market_typical_usd"),
                "discount_percent": listing.get("discount_percent", 0),
                "closing_at": listing.get("ends_at") or listing.get("closing_date"),
                "images": listing.get("images", [])[:3],  # Limit images
                "location": listing.get("location", {"province": "", "city": ""}),
                "opportunity_score": listing.get("opportunity_score", 50),
                "match_reason": listing.get("match_reason", ""),
            })

        payload = {
            "event": "new_opportunity",
            "timestamp": timestamp,
            "subscription_id": subscription.id,
            "data": {
                "listings": formatted_listings,
                "total_count": len(formatted_listings),
                "scrape_run_id": self.scrape_run_id,
                "blue_dollar_rate": self.blue_dollar_rate,
            },
        }

        return payload

    def _get_price_usd(self, listing: dict) -> float:
        """Get listing price in USD."""
        if listing.get("base_price_usd"):
            return listing["base_price_usd"]

        if listing.get("currency") == "USD":
            return listing.get("base_price", 0)

        if listing.get("currency") == "ARS":
            return listing.get("base_price", 0) / self.blue_dollar_rate

        return 0

    def sign_payload(self, payload: dict, secret: str) -> str:
        """Create HMAC-SHA256 signature of payload."""
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    async def send_webhook(
        self,
        subscription: WebhookSubscription,
        payload: dict
    ) -> bool:
        """
        Send webhook notification to a subscriber.
        Returns True on success.
        """
        # Sign the payload
        signature = self.sign_payload(payload, subscription.secret)
        payload["signature"] = signature

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-ID": str(uuid.uuid4()),
            "X-Subscription-ID": subscription.id,
            "User-Agent": "Subasto-Webhook/1.0",
        }

        body = json.dumps(payload)

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
                    response = await client.post(
                        subscription.webhook_url,
                        content=body,
                        headers=headers,
                    )

                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(
                        f"Webhook sent successfully to {subscription.id}: "
                        f"{len(payload['data']['listings'])} listings"
                    )
                    return True
                else:
                    logger.warning(
                        f"Webhook {subscription.id} returned {response.status_code}: "
                        f"{response.text[:200]}"
                    )

            except httpx.TimeoutException:
                logger.warning(
                    f"Webhook {subscription.id} timed out (attempt {attempt + 1}/{MAX_RETRIES})"
                )
            except httpx.RequestError as e:
                logger.warning(
                    f"Webhook {subscription.id} request failed: {e} "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})"
                )

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        logger.error(f"Webhook {subscription.id} failed after {MAX_RETRIES} attempts")
        return False

    def update_subscription_stats(
        self,
        subscription: WebhookSubscription,
        success: bool
    ) -> None:
        """Update subscription statistics after notification attempt."""
        if not SUBSCRIPTIONS_FILE.exists():
            return

        try:
            with open(SUBSCRIPTIONS_FILE) as f:
                data = json.load(f)

            if subscription.id in data:
                if success:
                    data[subscription.id]["notification_count"] = (
                        data[subscription.id].get("notification_count", 0) + 1
                    )
                    data[subscription.id]["last_notified_at"] = (
                        datetime.now(timezone.utc).isoformat()
                    )

                with open(SUBSCRIPTIONS_FILE, "w") as f:
                    json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to update subscription stats: {e}")

    async def send_all_notifications(self) -> dict:
        """
        Send notifications to all active subscribers.
        Returns summary statistics.
        """
        stats = {
            "total_subscriptions": len(self.subscriptions),
            "notifications_sent": 0,
            "notifications_failed": 0,
            "listings_notified": 0,
            "skipped_no_matches": 0,
        }

        for subscription in self.subscriptions:
            # Filter listings for this subscription
            matched = self.filter_listings_for_subscription(subscription)

            if not matched:
                stats["skipped_no_matches"] += 1
                logger.debug(f"No matches for subscription {subscription.id}")
                continue

            # Create and send payload
            payload = self.create_payload(subscription, matched)
            success = await self.send_webhook(subscription, payload)

            if success:
                stats["notifications_sent"] += 1
                stats["listings_notified"] += len(matched)
                self.update_subscription_stats(subscription, True)
            else:
                stats["notifications_failed"] += 1

        return stats


async def main():
    """Main entry point for webhook sender."""
    logger.info("Starting webhook notification sender...")

    sender = WebhookSender()

    # Load data
    sub_count = sender.load_subscriptions()
    if sub_count == 0:
        logger.info("No active subscriptions to notify")
        return

    listing_count = sender.load_listings()
    if listing_count == 0:
        logger.warning("No listings to notify about")
        return

    # Send notifications
    stats = await sender.send_all_notifications()

    # Log summary
    logger.info(
        f"Webhook notifications complete: "
        f"{stats['notifications_sent']} sent, "
        f"{stats['notifications_failed']} failed, "
        f"{stats['skipped_no_matches']} skipped (no matches), "
        f"{stats['listings_notified']} total listings notified"
    )

    return stats


if __name__ == "__main__":
    asyncio.run(main())
