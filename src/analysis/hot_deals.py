"""Hot Deals Scoring System for Subasto.

This module implements a sophisticated scoring algorithm to identify
"can't miss" auction opportunities based on multiple factors:

1. Price vs Market Value - The core discount metric
2. Time Urgency - Days until auction closes
3. Category-Specific Factors - Vehicles depreciate, real estate appreciates
4. Data Quality - Images, descriptions, completeness
5. Source Reliability - Judicial > Private, established > unknown
6. Lot Size & Completeness - Full info = higher confidence

Scoring Philosophy:
- Maximum score: 100 points
- Hot Deal threshold: 70+ points
- "Can't Miss" threshold: 85+ points
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class DealTier(Enum):
    """Deal quality tiers based on score."""
    EXCEPTIONAL = "exceptional"  # 85+ - Can't miss, immediate action recommended
    HOT = "hot"                  # 70-84 - Great opportunity, act fast
    WARM = "warm"                # 55-69 - Good deal, worth monitoring
    NEUTRAL = "neutral"          # 40-54 - Fair price, no urgency
    COLD = "cold"                # <40 - Not recommended


# Source reliability tiers (higher = more trustworthy)
# Judicial sources have court oversight, private can vary
SOURCE_RELIABILITY = {
    # Judicial sources (highest trust - court supervised)
    "csjn": 1.0,         # Supreme Court - highest authority
    "scba": 0.95,        # Buenos Aires Supreme Court
    "cordoba": 0.95,     # Cordoba Judicial
    "entrerios": 0.90,   # Entre Rios Judicial

    # Institutional (high trust - bank/government)
    "banco_ciudad": 0.90,  # Bank auctions, regulated

    # Established private auctioneers (medium-high trust)
    "adrian_mercado": 0.80,
    "global_remates": 0.80,
    "agusti": 0.75,
    "manucha": 0.75,
    "bidbit": 0.70,
    "delafuente": 0.70,
    "zarate": 0.70,
    "rematadores": 0.65,
    "sitiodetiendas": 0.60,

    # Curated/manual entries
    "curated": 0.85,

    # Default for unknown sources
    "default": 0.50,
}

# Category appreciation/depreciation factors
# Positive = tends to appreciate, Negative = tends to depreciate
CATEGORY_FACTORS = {
    "real_estate": {
        "trend": 0.05,           # 5% annual appreciation trend
        "volatility": 0.10,      # Low volatility
        "liquidity": 0.7,        # Slower to sell
        "base_multiplier": 1.0,  # Standard scoring
    },
    "vehicles": {
        "trend": -0.15,          # 15% annual depreciation
        "volatility": 0.15,      # Medium volatility
        "liquidity": 0.85,       # Easy to sell
        "base_multiplier": 1.1,  # Slightly boost vehicle deals
    },
    "machinery": {
        "trend": -0.10,          # 10% depreciation
        "volatility": 0.20,      # Higher volatility
        "liquidity": 0.5,        # Harder to sell
        "base_multiplier": 0.9,  # Slightly reduce for liquidity
    },
    "general_goods": {
        "trend": -0.20,          # Quick depreciation
        "volatility": 0.30,      # High volatility
        "liquidity": 0.9,        # Easy to flip
        "base_multiplier": 0.85, # Lower scores (smaller margins)
    },
    "other": {
        "trend": -0.10,
        "volatility": 0.25,
        "liquidity": 0.6,
        "base_multiplier": 0.8,
    },
}


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of how a hot deal score was calculated."""

    # Core components (out of their max)
    discount_score: float = 0.0      # Max 35 - Price vs market
    urgency_score: float = 0.0       # Max 20 - Time pressure
    source_score: float = 0.0        # Max 15 - Source reliability
    data_quality_score: float = 0.0  # Max 15 - Completeness
    category_score: float = 0.0      # Max 10 - Category factors
    bonus_score: float = 0.0         # Max 5 - Premium/special flags

    # Computed totals
    raw_score: float = 0.0           # Sum before adjustments
    final_score: float = 0.0         # After category multiplier

    # Explanations
    discount_reason: str = ""
    urgency_reason: str = ""
    source_reason: str = ""
    data_quality_reason: str = ""
    category_reason: str = ""
    bonus_reason: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class HotDeal:
    """Represents a scored hot deal opportunity."""

    # Listing identification
    listing_id: str
    title: str
    source: str
    source_url: str
    category: str

    # Pricing
    base_price: float
    currency: str
    base_price_usd: float
    market_price_usd: Optional[float] = None
    discount_percent: float = 0.0

    # Timing
    ends_at: Optional[datetime] = None
    days_until_close: Optional[int] = None

    # Scoring
    score: float = 0.0
    tier: str = "neutral"
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)

    # Analysis
    profit_potential_usd: float = 0.0
    profit_potential_percent: float = 0.0
    reasoning: str = ""
    action_recommendation: str = ""
    risk_factors: list[str] = field(default_factory=list)

    # Metadata
    has_images: bool = False
    image_count: int = 0
    is_premium: bool = False
    premium_type: str = ""
    location: dict = field(default_factory=dict)

    # Timestamps
    scored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            "listing_id": self.listing_id,
            "title": self.title,
            "source": self.source,
            "source_url": self.source_url,
            "category": self.category,
            "base_price": self.base_price,
            "currency": self.currency,
            "base_price_usd": round(self.base_price_usd, 2),
            "market_price_usd": round(self.market_price_usd, 2) if self.market_price_usd else None,
            "discount_percent": round(self.discount_percent, 1),
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "days_until_close": self.days_until_close,
            "score": round(self.score, 1),
            "tier": self.tier,
            "breakdown": self.breakdown.to_dict(),
            "profit_potential_usd": round(self.profit_potential_usd, 2),
            "profit_potential_percent": round(self.profit_potential_percent, 1),
            "reasoning": self.reasoning,
            "action_recommendation": self.action_recommendation,
            "risk_factors": self.risk_factors,
            "has_images": self.has_images,
            "image_count": self.image_count,
            "is_premium": self.is_premium,
            "premium_type": self.premium_type,
            "location": self.location,
            "scored_at": self.scored_at.isoformat(),
        }
        return data


class HotDealsScorer:
    """Scores auction listings to identify hot deal opportunities."""

    # Score component weights (must sum to 100 max)
    MAX_DISCOUNT_SCORE = 35.0
    MAX_URGENCY_SCORE = 20.0
    MAX_SOURCE_SCORE = 15.0
    MAX_DATA_QUALITY_SCORE = 15.0
    MAX_CATEGORY_SCORE = 10.0
    MAX_BONUS_SCORE = 5.0

    # Tier thresholds
    TIER_EXCEPTIONAL = 85.0
    TIER_HOT = 70.0
    TIER_WARM = 55.0
    TIER_NEUTRAL = 40.0

    def __init__(self, blue_dollar_rate: float = 1430.0):
        """Initialize scorer.

        Args:
            blue_dollar_rate: Current blue dollar rate for ARS to USD conversion
        """
        self.blue_dollar_rate = blue_dollar_rate

    def score_listing(self, listing: dict) -> HotDeal:
        """Score a single listing and return a HotDeal.

        Args:
            listing: Listing dict from listings.json

        Returns:
            HotDeal with complete scoring breakdown
        """
        breakdown = ScoreBreakdown()

        # Extract basic info
        listing_id = listing.get("id", "")
        title = listing.get("title", "")[:100]
        source = listing.get("source", "unknown")
        source_url = listing.get("source_url", "")
        category = listing.get("category", "other")
        base_price = listing.get("base_price", 0)
        currency = listing.get("currency", "ARS")

        # Calculate USD price
        if currency == "USD":
            base_price_usd = base_price
        else:
            base_price_usd = base_price / self.blue_dollar_rate

        # Get market data if available
        market_data = listing.get("market_data", {}) or listing.get("extra", {}).get("market_data", {})
        market_price_usd = market_data.get("typical_usd") or market_data.get("market_typical_usd")

        # Also check top-level discount info
        top_level_discount = listing.get("extra", {}).get("discount_percent", 0)
        top_level_market = listing.get("extra", {}).get("market_typical_usd", 0)

        if top_level_market and not market_price_usd:
            market_price_usd = top_level_market

        # Calculate discount
        discount_percent = 0.0
        if market_price_usd and market_price_usd > 0:
            discount_percent = ((market_price_usd - base_price_usd) / market_price_usd) * 100
        elif top_level_discount:
            discount_percent = top_level_discount

        # Parse end date
        ends_at = None
        days_until_close = None
        ends_at_str = listing.get("ends_at")
        if ends_at_str:
            try:
                if isinstance(ends_at_str, str):
                    ends_at = datetime.fromisoformat(ends_at_str.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    delta = ends_at - now
                    days_until_close = max(0, delta.days)
            except (ValueError, TypeError):
                pass

        # Get extra info
        images = listing.get("images", [])
        extra = listing.get("extra", {})
        is_premium = listing.get("is_premium", False) or extra.get("is_premium", False)
        premium_type = extra.get("premium_type", "")
        location = listing.get("location", {})

        # ===================
        # SCORE COMPONENTS
        # ===================

        # 1. DISCOUNT SCORE (max 35 points)
        breakdown.discount_score, breakdown.discount_reason = self._score_discount(
            discount_percent, market_price_usd, category
        )

        # 2. URGENCY SCORE (max 20 points)
        breakdown.urgency_score, breakdown.urgency_reason = self._score_urgency(
            days_until_close, category
        )

        # 3. SOURCE RELIABILITY SCORE (max 15 points)
        breakdown.source_score, breakdown.source_reason = self._score_source(source)

        # 4. DATA QUALITY SCORE (max 15 points)
        breakdown.data_quality_score, breakdown.data_quality_reason = self._score_data_quality(
            listing, images
        )

        # 5. CATEGORY SCORE (max 10 points)
        breakdown.category_score, breakdown.category_reason = self._score_category(
            category, discount_percent, base_price_usd
        )

        # 6. BONUS SCORE (max 5 points)
        breakdown.bonus_score, breakdown.bonus_reason = self._score_bonuses(
            is_premium, premium_type, extra
        )

        # Calculate raw and final scores
        breakdown.raw_score = (
            breakdown.discount_score +
            breakdown.urgency_score +
            breakdown.source_score +
            breakdown.data_quality_score +
            breakdown.category_score +
            breakdown.bonus_score
        )

        # Apply category multiplier
        cat_factors = CATEGORY_FACTORS.get(category, CATEGORY_FACTORS["other"])
        breakdown.final_score = breakdown.raw_score * cat_factors["base_multiplier"]

        # Cap at 100
        breakdown.final_score = min(100.0, breakdown.final_score)

        # Determine tier
        tier = self._determine_tier(breakdown.final_score)

        # Calculate profit potential
        profit_potential_usd = 0.0
        profit_potential_percent = 0.0
        if market_price_usd and base_price_usd > 0:
            # Conservative estimate: 70% of market price is realistic resale
            realistic_resale = market_price_usd * 0.7
            profit_potential_usd = max(0, realistic_resale - base_price_usd)
            profit_potential_percent = (profit_potential_usd / base_price_usd) * 100 if base_price_usd > 0 else 0

        # Generate reasoning and recommendation
        reasoning = self._generate_reasoning(breakdown, category, discount_percent, days_until_close)
        action_recommendation = self._generate_recommendation(tier, days_until_close, discount_percent)
        risk_factors = self._identify_risks(listing, source, category, market_price_usd)

        return HotDeal(
            listing_id=listing_id,
            title=title,
            source=source,
            source_url=source_url,
            category=category,
            base_price=base_price,
            currency=currency,
            base_price_usd=base_price_usd,
            market_price_usd=market_price_usd,
            discount_percent=discount_percent,
            ends_at=ends_at,
            days_until_close=days_until_close,
            score=breakdown.final_score,
            tier=tier,
            breakdown=breakdown,
            profit_potential_usd=profit_potential_usd,
            profit_potential_percent=profit_potential_percent,
            reasoning=reasoning,
            action_recommendation=action_recommendation,
            risk_factors=risk_factors,
            has_images=len(images) > 0,
            image_count=len(images),
            is_premium=is_premium,
            premium_type=premium_type,
            location=location,
        )

    def _score_discount(
        self,
        discount_percent: float,
        market_price_usd: Optional[float],
        category: str
    ) -> tuple[float, str]:
        """Score based on discount from market price.

        Scoring curve:
        - 0-10% discount: 0-5 points (fair price)
        - 10-30% discount: 5-15 points (good deal)
        - 30-50% discount: 15-25 points (great deal)
        - 50-70% discount: 25-30 points (exceptional)
        - 70%+ discount: 30-35 points (can't miss)
        """
        if not market_price_usd or discount_percent <= 0:
            return 0.0, "No market price available for comparison"

        score = 0.0
        reason = ""

        if discount_percent >= 70:
            score = 30.0 + min(5.0, (discount_percent - 70) / 10 * 5)
            reason = f"Exceptional {discount_percent:.0f}% below market - potential steal"
        elif discount_percent >= 50:
            score = 25.0 + (discount_percent - 50) / 20 * 5
            reason = f"Strong {discount_percent:.0f}% discount - great opportunity"
        elif discount_percent >= 30:
            score = 15.0 + (discount_percent - 30) / 20 * 10
            reason = f"Good {discount_percent:.0f}% discount - solid deal"
        elif discount_percent >= 10:
            score = 5.0 + (discount_percent - 10) / 20 * 10
            reason = f"Moderate {discount_percent:.0f}% discount - fair opportunity"
        else:
            score = discount_percent / 10 * 5
            reason = f"Minimal {discount_percent:.0f}% discount - near market price"

        return min(self.MAX_DISCOUNT_SCORE, score), reason

    def _score_urgency(
        self,
        days_until_close: Optional[int],
        category: str
    ) -> tuple[float, str]:
        """Score based on time urgency.

        Urgency is good for hot deals because:
        - Less competition from slow buyers
        - Motivated sellers
        - Actionable opportunities

        Scoring:
        - Ending today: 20 points
        - 1-2 days: 18 points
        - 3-5 days: 15 points
        - 6-7 days: 12 points
        - 1-2 weeks: 8 points
        - 2-4 weeks: 4 points
        - 4+ weeks or unknown: 2 points
        """
        if days_until_close is None:
            return 2.0, "End date unknown - may require follow-up"

        if days_until_close <= 0:
            return self.MAX_URGENCY_SCORE, "Ending TODAY - immediate action required!"
        elif days_until_close <= 2:
            return 18.0, f"Ending in {days_until_close} day(s) - urgent"
        elif days_until_close <= 5:
            return 15.0, f"Ending in {days_until_close} days - act soon"
        elif days_until_close <= 7:
            return 12.0, f"Ending this week ({days_until_close} days)"
        elif days_until_close <= 14:
            return 8.0, f"Ending in {days_until_close} days - time to research"
        elif days_until_close <= 28:
            return 4.0, f"Ending in {days_until_close} days - no rush"
        else:
            return 2.0, f"Ending in {days_until_close} days - long window"

    def _score_source(self, source: str) -> tuple[float, str]:
        """Score based on source reliability.

        Judicial sources are more reliable because:
        - Court supervised
        - Legal guarantees
        - Transparent process
        - Professional appraisals
        """
        reliability = SOURCE_RELIABILITY.get(source, SOURCE_RELIABILITY["default"])
        score = reliability * self.MAX_SOURCE_SCORE

        if reliability >= 0.95:
            reason = f"Judicial source ({source}) - highest trust, court supervised"
        elif reliability >= 0.85:
            reason = f"Institutional source ({source}) - regulated, reliable"
        elif reliability >= 0.70:
            reason = f"Established auctioneer ({source}) - good reputation"
        elif reliability >= 0.50:
            reason = f"Private auctioneer ({source}) - standard reliability"
        else:
            reason = f"Unknown source ({source}) - verify independently"

        return score, reason

    def _score_data_quality(
        self,
        listing: dict,
        images: list
    ) -> tuple[float, str]:
        """Score based on data completeness and quality.

        Better data = more confidence in the deal.

        Factors:
        - Has images: +5 points
        - Multiple images: +2 points
        - Has description: +3 points
        - Has location: +2 points
        - Has market data: +3 points
        """
        score = 0.0
        factors = []

        # Images (max 7)
        if images:
            score += 5.0
            factors.append("has images")
            if len(images) >= 3:
                score += 2.0
                factors.append(f"{len(images)} photos")

        # Description
        description = listing.get("description", "")
        if description and len(description) > 50:
            score += 3.0
            factors.append("detailed description")

        # Location
        location = listing.get("location", {})
        if location.get("city") or location.get("province"):
            score += 2.0
            factors.append("location specified")

        # Market data
        market_data = listing.get("market_data", {}) or listing.get("extra", {}).get("market_data", {})
        if market_data.get("typical_usd") or listing.get("extra", {}).get("market_typical_usd"):
            score += 3.0
            factors.append("market price validated")

        if not factors:
            return 0.0, "Limited data available - verify before bidding"

        return min(self.MAX_DATA_QUALITY_SCORE, score), "Data quality: " + ", ".join(factors)

    def _score_category(
        self,
        category: str,
        discount_percent: float,
        base_price_usd: float
    ) -> tuple[float, str]:
        """Score based on category-specific factors.

        Different categories have different value propositions:
        - Vehicles: Fast-moving, easy to flip, but depreciate
        - Real Estate: Appreciates, but slower to sell
        - Machinery: Niche market, can be very profitable
        - General Goods: Quick flip, small margins
        """
        cat_factors = CATEGORY_FACTORS.get(category, CATEGORY_FACTORS["other"])
        score = 0.0
        reasons = []

        # Liquidity bonus (easier to resell = better)
        liquidity = cat_factors["liquidity"]
        score += liquidity * 4.0
        if liquidity >= 0.8:
            reasons.append("high liquidity")
        elif liquidity <= 0.5:
            reasons.append("limited buyer pool")

        # Trend consideration
        trend = cat_factors["trend"]
        if trend > 0 and discount_percent >= 30:
            # Appreciating asset at discount = great
            score += 3.0
            reasons.append("appreciating asset")
        elif trend < -0.1 and discount_percent < 30:
            # Depreciating asset without big discount = risky
            score -= 1.0
            reasons.append("depreciating asset")

        # Price sweet spot bonus
        if category == "vehicles" and 5000 <= base_price_usd <= 30000:
            score += 2.0
            reasons.append("popular price range")
        elif category == "machinery" and base_price_usd >= 1000:
            score += 1.5
            reasons.append("commercial-grade equipment")
        elif category == "general_goods" and base_price_usd <= 1000:
            score += 1.0
            reasons.append("quick flip potential")

        reason = f"{category.replace('_', ' ').title()}: " + (", ".join(reasons) if reasons else "standard profile")
        return min(self.MAX_CATEGORY_SCORE, max(0, score)), reason

    def _score_bonuses(
        self,
        is_premium: bool,
        premium_type: str,
        extra: dict
    ) -> tuple[float, str]:
        """Score bonus factors.

        Premium listings indicate:
        - Bankruptcy/liquidation (motivated seller)
        - Fleet disposal (volume = better prices)
        - Special circumstances
        """
        score = 0.0
        bonuses = []

        if is_premium:
            score += 3.0
            bonuses.append("premium listing")

        if premium_type:
            if "liquidacion" in premium_type.lower() or "quiebra" in premium_type.lower():
                score += 2.0
                bonuses.append("liquidation sale")
            elif "flota" in premium_type.lower():
                score += 1.5
                bonuses.append("fleet disposal")
            elif "banco" in premium_type.lower():
                score += 1.5
                bonuses.append("bank auction")

        # Check for opportunity flags
        if extra.get("is_opportunity"):
            score += 1.0
            bonuses.append("flagged opportunity")

        if not bonuses:
            return 0.0, ""

        return min(self.MAX_BONUS_SCORE, score), "Bonuses: " + ", ".join(bonuses)

    def _determine_tier(self, score: float) -> str:
        """Determine the deal tier based on score."""
        if score >= self.TIER_EXCEPTIONAL:
            return DealTier.EXCEPTIONAL.value
        elif score >= self.TIER_HOT:
            return DealTier.HOT.value
        elif score >= self.TIER_WARM:
            return DealTier.WARM.value
        elif score >= self.TIER_NEUTRAL:
            return DealTier.NEUTRAL.value
        else:
            return DealTier.COLD.value

    def _generate_reasoning(
        self,
        breakdown: ScoreBreakdown,
        category: str,
        discount_percent: float,
        days_until_close: Optional[int]
    ) -> str:
        """Generate human-readable reasoning for the score."""
        parts = []

        # Lead with the strongest factor
        if breakdown.discount_score >= 25:
            parts.append(f"Exceptional discount of {discount_percent:.0f}% below market value")
        elif breakdown.discount_score >= 15:
            parts.append(f"Strong discount at {discount_percent:.0f}% below market")

        if breakdown.urgency_score >= 15 and days_until_close is not None:
            parts.append(f"ending in {days_until_close} day(s) creates urgency")

        if breakdown.source_score >= 12:
            parts.append("backed by reliable judicial/institutional source")

        if breakdown.bonus_score >= 3:
            parts.append("premium opportunity with additional value indicators")

        if not parts:
            if breakdown.final_score >= 55:
                parts.append("Solid opportunity with multiple positive factors")
            else:
                parts.append("Fair deal but limited standout factors")

        return ". ".join(parts).capitalize() + "."

    def _generate_recommendation(
        self,
        tier: str,
        days_until_close: Optional[int],
        discount_percent: float
    ) -> str:
        """Generate actionable recommendation."""
        if tier == DealTier.EXCEPTIONAL.value:
            if days_until_close is not None and days_until_close <= 2:
                return "IMMEDIATE ACTION - Register and bid now, exceptional opportunity closing soon!"
            return "HIGH PRIORITY - Research quickly and prepare to bid, this is a rare find."

        elif tier == DealTier.HOT.value:
            if days_until_close is not None and days_until_close <= 5:
                return "ACT SOON - Strong deal closing this week, don't miss out."
            return "RECOMMENDED - Good opportunity worth pursuing, set your max bid."

        elif tier == DealTier.WARM.value:
            return "MONITOR - Decent opportunity, worth following up if the price is right for you."

        elif tier == DealTier.NEUTRAL.value:
            return "HOLD - Fair price but no compelling urgency, consider if it fits your specific needs."

        else:
            return "PASS - Limited opportunity, look for better deals unless this is exactly what you need."

    def _identify_risks(
        self,
        listing: dict,
        source: str,
        category: str,
        market_price_usd: Optional[float]
    ) -> list[str]:
        """Identify potential risks with this deal."""
        risks = []

        # No market data
        if not market_price_usd:
            risks.append("No market price verification - discount may be overstated")

        # Unknown source
        if SOURCE_RELIABILITY.get(source, 0.5) < 0.6:
            risks.append("Less established source - verify auctioneer reputation")

        # No images
        if not listing.get("images"):
            risks.append("No images available - condition unknown")

        # Real estate complexity
        if category == "real_estate":
            risks.append("Real estate requires additional due diligence (title, liens, etc.)")

        # Vehicle specifics
        if category == "vehicles":
            risks.append("Verify VIN, service history, and conduct inspection before bidding")

        # High value items
        extra = listing.get("extra", {})
        base_price = listing.get("base_price", 0)
        currency = listing.get("currency", "ARS")
        if currency == "USD" and base_price > 50000:
            risks.append("High-value item - consider professional appraisal")
        elif currency == "ARS" and base_price > 50000000:
            risks.append("High-value item - consider professional appraisal")

        # No description
        if not listing.get("description") or len(listing.get("description", "")) < 30:
            risks.append("Limited description - may need to contact auctioneer for details")

        return risks

    def score_listings(self, listings: list[dict]) -> list[HotDeal]:
        """Score multiple listings and return sorted by score.

        Args:
            listings: List of listing dicts

        Returns:
            List of HotDeal objects sorted by score (highest first)
        """
        deals = []

        for listing in listings:
            try:
                deal = self.score_listing(listing)
                deals.append(deal)
            except Exception as e:
                logger.warning(f"Error scoring listing {listing.get('id', 'unknown')}: {e}")

        # Sort by score descending
        deals.sort(key=lambda d: d.score, reverse=True)

        return deals

    def get_hot_deals(
        self,
        listings: list[dict],
        min_score: float = 55.0,
        max_results: int = 50
    ) -> list[HotDeal]:
        """Get the top hot deals from listings.

        Args:
            listings: List of listing dicts
            min_score: Minimum score to include (default: WARM tier)
            max_results: Maximum number of results

        Returns:
            List of qualifying HotDeal objects
        """
        all_deals = self.score_listings(listings)

        # Filter by minimum score
        hot_deals = [d for d in all_deals if d.score >= min_score]

        return hot_deals[:max_results]
