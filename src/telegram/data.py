"""Data access layer for Subasto Telegram bot."""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from dataclasses import dataclass, field, asdict

from .config import config

logger = logging.getLogger(__name__)


@dataclass
class UserPreferences:
    """User preferences and watchlist."""

    user_id: int
    username: Optional[str] = None
    language: str = "es"

    # Watchlist (list of listing IDs)
    watchlist: list[str] = field(default_factory=list)

    # Alert settings
    daily_digest_enabled: bool = False
    daily_digest_hour: int = 9  # Argentina time (UTC-3)
    instant_alerts_enabled: bool = False

    # Alert filters
    alert_categories: list[str] = field(default_factory=list)  # Empty = all
    alert_min_discount: Optional[int] = None
    alert_max_price_usd: Optional[int] = None

    # Metadata
    created_at: str = ""
    last_active: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserPreferences":
        return cls(**data)


class DataManager:
    """Manages auction data and user preferences."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.listings_path = self.base_path / config.listings_path
        self.hot_list_path = self.base_path / config.hot_list_path
        self.user_data_dir = self.base_path / config.user_data_dir

        # Create user data directory
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

        # Cache for listings
        self._listings_cache: Optional[dict] = None
        self._listings_cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)

    def _load_listings(self) -> dict:
        """Load listings from JSON file with caching."""
        now = datetime.now(timezone.utc)

        # Check cache validity
        if (
            self._listings_cache is not None
            and self._listings_cache_time is not None
            and now - self._listings_cache_time < self._cache_ttl
        ):
            return self._listings_cache

        # Load from file
        try:
            with open(self.listings_path, "r", encoding="utf-8") as f:
                self._listings_cache = json.load(f)
                self._listings_cache_time = now
                return self._listings_cache
        except Exception as e:
            logger.error(f"Error loading listings: {e}")
            return {"listings": [], "total_count": 0}

    def get_all_listings(self) -> list[dict]:
        """Get all listings."""
        data = self._load_listings()
        return data.get("listings", [])

    def get_listing_by_id(self, listing_id: str) -> Optional[dict]:
        """Get a single listing by ID."""
        listings = self.get_all_listings()
        for listing in listings:
            if listing.get("id") == listing_id:
                return listing
        return None

    def search_listings(
        self,
        query: str,
        category: Optional[str] = None,
        max_price_usd: Optional[float] = None,
        source: Optional[str] = None,
        limit: int = 10
    ) -> list[dict]:
        """Search listings with filters."""
        listings = self.get_all_listings()
        results = []

        query_lower = query.lower() if query else ""

        for listing in listings:
            # Text search
            if query_lower:
                title = listing.get("title", "").lower()
                desc = listing.get("description", "").lower()
                if query_lower not in title and query_lower not in desc:
                    continue

            # Category filter
            if category and listing.get("category") != category:
                continue

            # Price filter
            if max_price_usd:
                price = listing.get("base_price_usd") or listing.get("base_price", 0)
                if listing.get("currency") == "ARS":
                    # Convert ARS to USD using blue dollar rate
                    data = self._load_listings()
                    rate = data.get("blue_dollar_rate", 1430)
                    price = listing.get("base_price", 0) / rate
                if price > max_price_usd:
                    continue

            # Source filter
            if source and listing.get("source") != source:
                continue

            results.append(listing)

            if len(results) >= limit:
                break

        return results

    def get_listings_by_category(self, category: str, limit: int = 10) -> list[dict]:
        """Get listings by category."""
        return self.search_listings(query="", category=category, limit=limit)

    def get_ending_soon(self, hours: int = 24, limit: int = 10) -> list[dict]:
        """Get listings ending within specified hours."""
        listings = self.get_all_listings()
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours)

        ending_soon = []

        for listing in listings:
            ends_at = listing.get("ends_at")
            if not ends_at:
                continue

            try:
                if isinstance(ends_at, str):
                    end_dt = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                else:
                    end_dt = ends_at

                if now < end_dt <= cutoff:
                    listing["_hours_remaining"] = (end_dt - now).total_seconds() / 3600
                    ending_soon.append(listing)
            except Exception:
                continue

        # Sort by ending soonest
        ending_soon.sort(key=lambda x: x.get("_hours_remaining", 999))

        return ending_soon[:limit]

    def get_hot_list(self, limit: int = 10) -> list[dict]:
        """Get hot opportunities from hot_list.json."""
        try:
            with open(self.hot_list_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("items", [])[:limit]
        except Exception as e:
            logger.error(f"Error loading hot list: {e}")
            return []

    def get_stats(self) -> dict:
        """Get statistics about listings."""
        data = self._load_listings()
        return {
            "total_count": data.get("total_count", 0),
            "by_source": data.get("by_source", {}),
            "by_category": data.get("by_category", {}),
            "blue_dollar_rate": data.get("blue_dollar_rate", 0),
            "generated_at": data.get("generated_at", ""),
            "opportunity_count": data.get("opportunity_count", 0),
            "premium_count": data.get("premium_count", 0),
        }

    # User preferences methods

    def _user_path(self, user_id: int) -> Path:
        """Get path to user preferences file."""
        return self.user_data_dir / f"{user_id}.json"

    def get_user_preferences(self, user_id: int) -> UserPreferences:
        """Get user preferences, creating default if not exists."""
        path = self._user_path(user_id)

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    prefs = UserPreferences.from_dict(data)
                    prefs.last_active = datetime.now(timezone.utc).isoformat()
                    self.save_user_preferences(prefs)
                    return prefs
            except Exception as e:
                logger.error(f"Error loading user {user_id} preferences: {e}")

        # Create new preferences
        now = datetime.now(timezone.utc).isoformat()
        prefs = UserPreferences(
            user_id=user_id,
            created_at=now,
            last_active=now,
        )
        self.save_user_preferences(prefs)
        return prefs

    def save_user_preferences(self, prefs: UserPreferences) -> None:
        """Save user preferences."""
        path = self._user_path(prefs.user_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(prefs.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving user {prefs.user_id} preferences: {e}")

    def add_to_watchlist(self, user_id: int, listing_id: str) -> bool:
        """Add item to user's watchlist."""
        prefs = self.get_user_preferences(user_id)

        if listing_id in prefs.watchlist:
            return False  # Already in watchlist

        if len(prefs.watchlist) >= config.max_watchlist_items:
            return False  # Watchlist full

        prefs.watchlist.append(listing_id)
        self.save_user_preferences(prefs)
        return True

    def remove_from_watchlist(self, user_id: int, listing_id: str) -> bool:
        """Remove item from user's watchlist."""
        prefs = self.get_user_preferences(user_id)

        if listing_id not in prefs.watchlist:
            return False

        prefs.watchlist.remove(listing_id)
        self.save_user_preferences(prefs)
        return True

    def get_watchlist(self, user_id: int) -> list[dict]:
        """Get user's watchlist with full listing data."""
        prefs = self.get_user_preferences(user_id)
        watchlist = []

        for listing_id in prefs.watchlist:
            listing = self.get_listing_by_id(listing_id)
            if listing:
                watchlist.append(listing)

        return watchlist

    def clear_watchlist(self, user_id: int) -> int:
        """Clear user's watchlist. Returns number of items removed."""
        prefs = self.get_user_preferences(user_id)
        count = len(prefs.watchlist)
        prefs.watchlist = []
        self.save_user_preferences(prefs)
        return count

    def is_in_watchlist(self, user_id: int, listing_id: str) -> bool:
        """Check if item is in user's watchlist."""
        prefs = self.get_user_preferences(user_id)
        return listing_id in prefs.watchlist

    def get_users_with_alerts(self) -> list[UserPreferences]:
        """Get all users with alerts enabled."""
        users = []

        for path in self.user_data_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    prefs = UserPreferences.from_dict(data)
                    if prefs.daily_digest_enabled or prefs.instant_alerts_enabled:
                        users.append(prefs)
            except Exception as e:
                logger.error(f"Error loading user from {path}: {e}")

        return users

    def get_users_for_digest_hour(self, hour: int) -> list[UserPreferences]:
        """Get users who want daily digest at specified hour."""
        users = []

        for path in self.user_data_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    prefs = UserPreferences.from_dict(data)
                    if prefs.daily_digest_enabled and prefs.daily_digest_hour == hour:
                        users.append(prefs)
            except Exception as e:
                logger.error(f"Error loading user from {path}: {e}")

        return users
