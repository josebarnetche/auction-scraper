"""JSON file storage for auction data."""

import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from src.models.listing import AuctionListing
from src.models.opportunity import Opportunity

logger = logging.getLogger(__name__)


class JSONStore:
    """Handles JSON storage and retrieval of auction data."""

    def __init__(self, data_dir: str = "data", site_dir: str = "site"):
        self.data_dir = Path(data_dir)
        self.site_dir = Path(site_dir)
        self.raw_dir = self.data_dir / "raw"
        self.api_dir = self.site_dir / "api"

        # Create directories
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.api_dir.mkdir(parents=True, exist_ok=True)

    def save_listings(self, source: str, listings: list[AuctionListing]) -> Path:
        """Save listings to source-specific JSON file."""
        filepath = self.raw_dir / f"{source}.json"
        data = [listing.to_dict() for listing in listings]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(listings)} listings to {filepath}")
        return filepath

    def load_listings(self, source: str) -> list[AuctionListing]:
        """Load listings from source-specific JSON file."""
        filepath = self.raw_dir / f"{source}.json"
        if not filepath.exists():
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return [AuctionListing.from_dict(item) for item in data]

    def load_all_listings(self) -> list[AuctionListing]:
        """Load all listings from all source files."""
        all_listings = []
        for filepath in self.raw_dir.glob("*.json"):
            source = filepath.stem
            listings = self.load_listings(source)
            all_listings.extend(listings)
        return all_listings

    def save_opportunities(self, opportunities: list[Opportunity]) -> Path:
        """Save opportunities to API directory."""
        filepath = self.api_dir / "opportunities.json"
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(opportunities),
            "flagged_count": sum(1 for o in opportunities if o.is_flagged),
            "opportunities": [opp.to_dict() for opp in opportunities]
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(opportunities)} opportunities to {filepath}")
        return filepath

    def save_all_listings_api(self, listings: list[AuctionListing]) -> Path:
        """Save all listings to API directory for static site."""
        filepath = self.api_dir / "listings.json"

        # Group by source
        by_source = {}
        for listing in listings:
            if listing.source not in by_source:
                by_source[listing.source] = []
            by_source[listing.source].append(listing.to_dict())

        # Group by category
        by_category = {}
        for listing in listings:
            if listing.category not in by_category:
                by_category[listing.category] = []
            by_category[listing.category].append(listing.to_dict())

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_count": len(listings),
            "by_source": {k: len(v) for k, v in by_source.items()},
            "by_category": {k: len(v) for k, v in by_category.items()},
            "listings": [listing.to_dict() for listing in listings]
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(listings)} listings to {filepath}")
        return filepath

    def get_stats(self) -> dict:
        """Get statistics about stored data."""
        listings = self.load_all_listings()

        stats = {
            "total_listings": len(listings),
            "by_source": {},
            "by_category": {},
            "by_status": {},
        }

        for listing in listings:
            stats["by_source"][listing.source] = stats["by_source"].get(listing.source, 0) + 1
            stats["by_category"][listing.category] = stats["by_category"].get(listing.category, 0) + 1
            stats["by_status"][listing.status] = stats["by_status"].get(listing.status, 0) + 1

        return stats
