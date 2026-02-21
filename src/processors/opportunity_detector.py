"""Opportunity detection - identifies auctions with 30%+ discounts."""

import logging
from typing import Optional

from src.models.listing import AuctionListing
from src.models.opportunity import Opportunity, calculate_discount
from src.market.mercadolibre import MercadoLibreClient
from src.market.currency import CurrencyConverter
from src.market.matcher import VehicleMatcher, RealEstateMatcher, GenericMatcher, MatchResult

logger = logging.getLogger(__name__)


# Condition adjustment factor for auction items
# Auction items are typically in unknown/as-is condition
AUCTION_CONDITION_FACTOR = 0.85  # Expect 15% less due to uncertainty


class OpportunityDetector:
    """Detects opportunities by comparing auction prices to market prices."""

    DISCOUNT_THRESHOLD = 30.0  # Flag opportunities with 30%+ discount

    def __init__(self):
        self.ml_client: Optional[MercadoLibreClient] = None
        self.currency = CurrencyConverter()
        self.vehicle_matcher = VehicleMatcher()
        self.realestate_matcher = RealEstateMatcher()
        self.generic_matcher = GenericMatcher()

    async def __aenter__(self):
        self.ml_client = MercadoLibreClient()
        await self.ml_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.ml_client:
            await self.ml_client.__aexit__(exc_type, exc_val, exc_tb)

    async def analyze_listing(self, listing: AuctionListing) -> Optional[Opportunity]:
        """Analyze a single listing for opportunity.

        Returns Opportunity if analysis successful, None otherwise.
        """
        if listing.base_price <= 0:
            logger.debug(f"Skipping {listing.id}: no price")
            return None

        # Search MercadoLibre for comparables
        search_query = self._build_search_query(listing)
        logger.debug(f"Searching ML: {search_query}")

        ml_listings = await self.ml_client.search(
            query=search_query,
            category=listing.category if listing.category != "other" else None,
            limit=20,
            condition="used",  # Most auction items are used
        )

        if not ml_listings:
            logger.debug(f"No ML results for: {listing.title}")
            return None

        # Match and get market price
        match_result = await self._match_listing(listing, ml_listings)

        if not match_result:
            return None

        # Normalize prices to USD
        auction_price_usd = await self.currency.normalize_to_usd(
            listing.base_price, listing.currency
        )

        market_price_usd = await self.currency.normalize_to_usd(
            match_result.median_price, match_result.currency
        )

        # Apply condition adjustment
        adjusted_market_price = market_price_usd * AUCTION_CONDITION_FACTOR

        # Calculate discount
        discount = calculate_discount(auction_price_usd, adjusted_market_price)

        is_flagged = discount >= self.DISCOUNT_THRESHOLD and match_result.confidence_score >= 0.3

        return Opportunity(
            listing=listing,
            market_median_usd=market_price_usd,
            auction_price_usd=auction_price_usd,
            discount_percentage=discount,
            confidence_score=match_result.confidence_score,
            comparables_count=match_result.comparables_count,
            is_flagged=is_flagged,
            comparable_urls=match_result.comparable_urls,
            analysis_notes=match_result.match_details,
        )

    async def analyze_listings(self, listings: list[AuctionListing]) -> list[Opportunity]:
        """Analyze multiple listings for opportunities."""
        opportunities = []

        for listing in listings:
            try:
                opp = await self.analyze_listing(listing)
                if opp:
                    opportunities.append(opp)
            except Exception as e:
                logger.error(f"Error analyzing {listing.id}: {e}")

        # Sort by discount percentage
        opportunities.sort(key=lambda x: x.discount_percentage, reverse=True)

        flagged_count = sum(1 for o in opportunities if o.is_flagged)
        logger.info(f"Analyzed {len(listings)} listings, found {flagged_count} flagged opportunities")

        return opportunities

    def _build_search_query(self, listing: AuctionListing) -> str:
        """Build search query from listing."""
        # Use title, but limit length
        query = listing.title[:80]

        # Remove common auction-specific terms
        remove_terms = [
            "subasta", "remate", "judicial", "base", "expediente",
            "lote", "n°", "nro", "número"
        ]

        for term in remove_terms:
            query = query.lower().replace(term, "")

        return query.strip()

    async def _match_listing(
        self, listing: AuctionListing, ml_listings: list
    ) -> Optional[MatchResult]:
        """Match listing to market comparables based on category."""
        if listing.category == "vehicles":
            return self.vehicle_matcher.match(listing.title, ml_listings)
        elif listing.category == "real_estate":
            return self.realestate_matcher.match(
                listing.title, listing.description, ml_listings
            )
        else:
            return self.generic_matcher.match(listing.title, ml_listings)
