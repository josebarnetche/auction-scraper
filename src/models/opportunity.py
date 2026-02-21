"""Opportunity model for auction deals."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import json

from .listing import AuctionListing


def _utcnow():
    return datetime.now(timezone.utc)


@dataclass
class Opportunity:
    """Represents a potential auction opportunity with discount analysis."""

    listing: AuctionListing
    market_median_usd: float
    auction_price_usd: float
    discount_percentage: float
    confidence_score: float  # 0.0 to 1.0
    comparables_count: int
    is_flagged: bool  # True if >= 30% discount
    comparable_urls: list[str] = field(default_factory=list)
    analysis_notes: str = ""
    analyzed_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            "listing": self.listing.to_dict(),
            "market_median_usd": self.market_median_usd,
            "auction_price_usd": self.auction_price_usd,
            "discount_percentage": round(self.discount_percentage, 2),
            "confidence_score": round(self.confidence_score, 2),
            "comparables_count": self.comparables_count,
            "is_flagged": self.is_flagged,
            "comparable_urls": self.comparable_urls,
            "analysis_notes": self.analysis_notes,
            "analyzed_at": self.analyzed_at.isoformat(),
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Opportunity":
        """Create instance from dictionary."""
        listing_data = data.pop("listing")
        listing = AuctionListing.from_dict(listing_data)
        if isinstance(data.get("analyzed_at"), str):
            data["analyzed_at"] = datetime.fromisoformat(data["analyzed_at"])
        return cls(listing=listing, **data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def calculate_discount(auction_price: float, market_price: float) -> float:
    """Calculate discount percentage.

    Returns positive value if auction is cheaper than market.
    """
    if market_price <= 0:
        return 0.0
    return ((market_price - auction_price) / market_price) * 100
