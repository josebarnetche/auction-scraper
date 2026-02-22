"""
Digest Generator for Subasto Email System.

Generates personalized email digests based on subscriber preferences.
Supports multiple digest types:
- Daily digest with top 10 opportunities
- Category-specific digests (vehicles only, real estate only, etc.)
- "Ending today" alerts
- Welcome emails with tips
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from .templates import (
    render_daily_digest,
    render_ending_today,
    render_welcome_email,
    render_category_digest,
)


@dataclass
class SubscriberPreferences:
    """Subscriber preferences for filtering content."""
    categories: list[str] = field(default_factory=lambda: [
        "vehicles", "real_estate", "machinery", "general_goods", "other"
    ])
    provinces: list[str] = field(default_factory=list)  # Empty = all
    price_min_usd: float = 0
    price_max_usd: float = 0  # 0 = no max
    opportunities_only: bool = False
    ending_today_alerts: bool = True


@dataclass
class DigestItem:
    """A single item in the digest."""
    id: str
    title: str
    description: str
    category: str
    source: str
    source_url: str
    base_price: float
    currency: str
    base_price_usd: float
    discount_percent: Optional[float]
    market_price_usd: Optional[float]
    ends_at: Optional[str]
    ends_at_formatted: Optional[str]
    location: dict
    image_url: Optional[str]
    is_opportunity: bool
    is_ending_today: bool
    is_premium: bool


@dataclass
class DigestContent:
    """Complete digest content ready for rendering."""
    subscriber_email: str
    unsubscribe_token: str
    generated_at: str
    digest_type: str  # daily, ending_today, category, welcome

    # Content
    items: list[DigestItem] = field(default_factory=list)
    ending_today_items: list[DigestItem] = field(default_factory=list)

    # Stats
    total_listings: int = 0
    opportunities_count: int = 0
    new_since_last: int = 0

    # Metadata
    blue_dollar_rate: float = 0
    categories_included: list[str] = field(default_factory=list)


class DigestGenerator:
    """Generates email digests from auction listings data."""

    def __init__(self, listings_path: Optional[Path] = None):
        """Initialize with path to listings.json."""
        self.listings_path = listings_path or Path("site/api/listings.json")
        self._data = None
        self._loaded_at = None

    def _load_data(self) -> dict:
        """Load and cache listings data."""
        now = datetime.now()
        # Reload if older than 5 minutes
        if self._data is None or (now - self._loaded_at).seconds > 300:
            with open(self.listings_path, encoding="utf-8") as f:
                self._data = json.load(f)
            self._loaded_at = now
        return self._data

    def _listing_to_item(self, listing: dict, now: datetime) -> DigestItem:
        """Convert a listing dict to DigestItem."""
        ends_at = listing.get("ends_at")
        ends_at_dt = None
        is_ending_today = False
        ends_at_formatted = None

        if ends_at:
            try:
                ends_at_dt = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                # Format for display
                ends_at_formatted = ends_at_dt.strftime("%d/%m %H:%M")
                # Check if ending today (within 24 hours)
                tomorrow = now + timedelta(days=1)
                is_ending_today = now <= ends_at_dt <= tomorrow
            except (ValueError, TypeError):
                pass

        # Get market data
        market_data = listing.get("market_data", {})
        discount = market_data.get("discount_percent") or listing.get("discount_percent")
        market_price = market_data.get("typical_usd") or market_data.get("market_typical_usd")
        is_opportunity = market_data.get("is_opportunity", False) or (discount and discount >= 30)

        # Get first image
        images = listing.get("images", [])
        image_url = images[0] if images else None

        return DigestItem(
            id=listing.get("id", ""),
            title=listing.get("title", "")[:100],
            description=listing.get("description", "")[:200],
            category=listing.get("category", "other"),
            source=listing.get("source", ""),
            source_url=listing.get("source_url", ""),
            base_price=listing.get("base_price", 0),
            currency=listing.get("currency", "ARS"),
            base_price_usd=listing.get("base_price_usd", 0),
            discount_percent=round(discount, 1) if discount else None,
            market_price_usd=market_price,
            ends_at=ends_at,
            ends_at_formatted=ends_at_formatted,
            location=listing.get("location", {}),
            image_url=image_url,
            is_opportunity=is_opportunity,
            is_ending_today=is_ending_today,
            is_premium=listing.get("is_premium", False),
        )

    def _filter_listings(
        self,
        listings: list[dict],
        preferences: SubscriberPreferences,
        now: datetime
    ) -> list[DigestItem]:
        """Filter listings based on subscriber preferences."""
        filtered = []

        for listing in listings:
            # Skip search_only items
            if listing.get("visibility") == "search_only":
                continue

            # Category filter
            category = listing.get("category", "other")
            if preferences.categories and category not in preferences.categories:
                continue

            # Province filter
            if preferences.provinces:
                location = listing.get("location", {})
                province = location.get("province", "")
                if province and province not in preferences.provinces:
                    continue

            # Price filter
            price_usd = listing.get("base_price_usd", 0)
            if preferences.price_min_usd > 0 and price_usd < preferences.price_min_usd:
                continue
            if preferences.price_max_usd > 0 and price_usd > preferences.price_max_usd:
                continue

            # Opportunities only filter
            if preferences.opportunities_only:
                market_data = listing.get("market_data", {})
                if not market_data.get("is_opportunity"):
                    continue

            item = self._listing_to_item(listing, now)
            filtered.append(item)

        return filtered

    def generate_daily_digest(
        self,
        subscriber_email: str,
        unsubscribe_token: str,
        preferences: Optional[SubscriberPreferences] = None,
        max_items: int = 10
    ) -> DigestContent:
        """Generate a daily digest for a subscriber."""
        data = self._load_data()
        prefs = preferences or SubscriberPreferences()
        now = datetime.now(timezone.utc)

        listings = data.get("listings", [])

        # Filter and convert to items
        all_items = self._filter_listings(listings, prefs, now)

        # Sort by opportunity score (discount + premium + recency)
        def sort_key(item: DigestItem):
            score = 0
            if item.discount_percent:
                score += item.discount_percent
            if item.is_premium:
                score += 50
            if item.is_ending_today:
                score += 30
            return score

        all_items.sort(key=sort_key, reverse=True)

        # Split into main items and ending today
        top_items = all_items[:max_items]
        ending_today = [i for i in all_items if i.is_ending_today][:5]

        # Count opportunities
        opportunities = [i for i in all_items if i.is_opportunity]

        # Get unique categories in this digest
        categories = list(set(i.category for i in top_items))

        return DigestContent(
            subscriber_email=subscriber_email,
            unsubscribe_token=unsubscribe_token,
            generated_at=now.isoformat(),
            digest_type="daily",
            items=top_items,
            ending_today_items=ending_today,
            total_listings=data.get("total_count", 0),
            opportunities_count=len(opportunities),
            new_since_last=0,  # Would need last digest date to calculate
            blue_dollar_rate=data.get("blue_dollar_rate", 0),
            categories_included=categories,
        )

    def generate_ending_today_alert(
        self,
        subscriber_email: str,
        unsubscribe_token: str,
        preferences: Optional[SubscriberPreferences] = None
    ) -> Optional[DigestContent]:
        """Generate an 'ending today' alert digest."""
        data = self._load_data()
        prefs = preferences or SubscriberPreferences()
        now = datetime.now(timezone.utc)

        listings = data.get("listings", [])
        all_items = self._filter_listings(listings, prefs, now)

        # Only items ending today
        ending_today = [i for i in all_items if i.is_ending_today]

        if not ending_today:
            return None  # Nothing to send

        # Sort by end time
        ending_today.sort(key=lambda x: x.ends_at or "")

        return DigestContent(
            subscriber_email=subscriber_email,
            unsubscribe_token=unsubscribe_token,
            generated_at=now.isoformat(),
            digest_type="ending_today",
            items=ending_today[:10],
            ending_today_items=ending_today,
            total_listings=len(ending_today),
            blue_dollar_rate=data.get("blue_dollar_rate", 0),
        )

    def generate_category_digest(
        self,
        subscriber_email: str,
        unsubscribe_token: str,
        category: str,
        max_items: int = 10
    ) -> DigestContent:
        """Generate a category-specific digest."""
        # Create preferences for just this category
        prefs = SubscriberPreferences(categories=[category])

        data = self._load_data()
        now = datetime.now(timezone.utc)

        listings = data.get("listings", [])
        all_items = self._filter_listings(listings, prefs, now)

        # Sort by discount
        all_items.sort(
            key=lambda x: x.discount_percent or 0,
            reverse=True
        )

        return DigestContent(
            subscriber_email=subscriber_email,
            unsubscribe_token=unsubscribe_token,
            generated_at=now.isoformat(),
            digest_type="category",
            items=all_items[:max_items],
            total_listings=len(all_items),
            categories_included=[category],
            blue_dollar_rate=data.get("blue_dollar_rate", 0),
        )

    def generate_welcome_email(
        self,
        subscriber_email: str,
        unsubscribe_token: str
    ) -> DigestContent:
        """Generate a welcome email with tips and sample opportunities."""
        data = self._load_data()
        now = datetime.now(timezone.utc)

        # Get top 3 opportunities as samples
        top_opps = data.get("top_opportunities", [])[:3]

        sample_items = []
        for opp in top_opps:
            # Convert top_opportunity format to DigestItem
            sample_items.append(DigestItem(
                id=opp.get("id", ""),
                title=opp.get("title", ""),
                description="",
                category=opp.get("category", "other"),
                source=opp.get("source", ""),
                source_url=opp.get("source_url", ""),
                base_price=opp.get("base_price", 0),
                currency=opp.get("currency", "ARS"),
                base_price_usd=0,
                discount_percent=opp.get("discount_percent"),
                market_price_usd=opp.get("market_typical_usd"),
                ends_at=None,
                ends_at_formatted=None,
                location={},
                image_url=None,
                is_opportunity=True,
                is_ending_today=False,
                is_premium=opp.get("is_premium", False),
            ))

        return DigestContent(
            subscriber_email=subscriber_email,
            unsubscribe_token=unsubscribe_token,
            generated_at=now.isoformat(),
            digest_type="welcome",
            items=sample_items,
            total_listings=data.get("total_count", 0),
            opportunities_count=data.get("opportunity_count", 0),
            blue_dollar_rate=data.get("blue_dollar_rate", 0),
        )


def generate_daily_digest(
    subscriber_email: str,
    unsubscribe_token: str,
    preferences: Optional[dict] = None,
    listings_path: Optional[Path] = None
) -> tuple[str, str]:
    """
    Convenience function to generate a daily digest.

    Returns: (subject, html_content)
    """
    generator = DigestGenerator(listings_path)

    # Convert dict preferences to dataclass
    prefs = None
    if preferences:
        prefs = SubscriberPreferences(
            categories=preferences.get("categories", []),
            provinces=preferences.get("provinces", []),
            price_min_usd=preferences.get("priceMinUsd", 0),
            price_max_usd=preferences.get("priceMaxUsd", 0),
            opportunities_only=preferences.get("opportunitiesOnly", False),
            ending_today_alerts=preferences.get("endingTodayAlerts", True),
        )

    digest = generator.generate_daily_digest(
        subscriber_email,
        unsubscribe_token,
        prefs
    )

    subject = f"Subasto Digest: {len(digest.items)} oportunidades hoy"
    html = render_daily_digest(digest)

    return subject, html
