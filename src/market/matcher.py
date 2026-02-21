"""Item matching logic for comparing auction items to market listings."""

import re
import logging
from typing import Optional
from dataclasses import dataclass
import statistics

from src.market.mercadolibre import MLListing, extract_vehicle_info, extract_realestate_info

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of matching an auction item to market listings."""
    median_price: float
    currency: str
    comparables_count: int
    confidence_score: float
    comparable_urls: list[str]
    match_details: str


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate simple word-based similarity between two texts.

    Returns value between 0.0 and 1.0.
    """
    # Normalize
    words1 = set(re.findall(r"\w+", text1.lower()))
    words2 = set(re.findall(r"\w+", text2.lower()))

    if not words1 or not words2:
        return 0.0

    # Remove common stopwords
    stopwords = {"de", "la", "el", "en", "y", "a", "con", "para", "por", "del", "los", "las", "un", "una"}
    words1 = words1 - stopwords
    words2 = words2 - stopwords

    if not words1 or not words2:
        return 0.0

    # Jaccard similarity
    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0


class VehicleMatcher:
    """Matcher for vehicle auctions."""

    def match(self, auction_title: str, ml_listings: list[MLListing]) -> Optional[MatchResult]:
        """Match auction vehicle to market listings."""
        auction_info = extract_vehicle_info(auction_title)

        if not auction_info:
            # Fall back to text similarity
            return self._text_match(auction_title, ml_listings)

        matched = []
        for listing in ml_listings:
            score = self._score_vehicle_match(auction_info, listing)
            if score > 0.3:
                matched.append((listing, score))

        if not matched:
            return self._text_match(auction_title, ml_listings)

        # Sort by score
        matched.sort(key=lambda x: x[1], reverse=True)

        # Get prices from top matches
        prices = [m[0].price for m in matched[:10]]
        scores = [m[1] for m in matched[:10]]

        if not prices:
            return None

        median_price = statistics.median(prices)
        avg_score = statistics.mean(scores)

        return MatchResult(
            median_price=median_price,
            currency=matched[0][0].currency,
            comparables_count=len(matched),
            confidence_score=min(avg_score * 1.2, 1.0),  # Boost slightly
            comparable_urls=[m[0].permalink for m in matched[:5]],
            match_details=f"Matched by: {', '.join(auction_info.keys())}",
        )

    def _score_vehicle_match(self, auction_info: dict, listing: MLListing) -> float:
        """Score how well a listing matches auction info."""
        score = 0.0
        factors = 0

        listing_attrs = listing.attributes
        listing_title = listing.title.lower()

        # Brand match
        if "brand" in auction_info:
            brand = auction_info["brand"].lower()
            if brand in listing_title or listing_attrs.get("brand", "").lower() == brand:
                score += 0.4
            factors += 1

        # Year match
        if "year" in auction_info:
            auction_year = auction_info["year"]
            listing_year = None

            if "year" in listing_attrs:
                try:
                    listing_year = int(listing_attrs["year"])
                except ValueError:
                    pass

            if listing_year:
                year_diff = abs(auction_year - listing_year)
                if year_diff == 0:
                    score += 0.4
                elif year_diff <= 2:
                    score += 0.2
            factors += 1

        # Kilometers match (within 30%)
        if "kilometers" in auction_info and "kilometers" in listing_attrs:
            try:
                auction_km = auction_info["kilometers"]
                listing_km = int(listing_attrs["kilometers"].replace(".", "").replace(",", ""))
                ratio = min(auction_km, listing_km) / max(auction_km, listing_km)
                if ratio > 0.7:
                    score += 0.2
            except (ValueError, ZeroDivisionError):
                pass
            factors += 1

        if factors == 0:
            return 0.0

        return score / factors

    def _text_match(self, auction_title: str, ml_listings: list[MLListing]) -> Optional[MatchResult]:
        """Fall back to text-based matching."""
        if not ml_listings:
            return None

        matches = []
        for listing in ml_listings:
            sim = calculate_text_similarity(auction_title, listing.title)
            if sim > 0.2:
                matches.append((listing, sim))

        if not matches:
            # Use all listings with low confidence
            prices = [l.price for l in ml_listings[:10]]
            if prices:
                return MatchResult(
                    median_price=statistics.median(prices),
                    currency=ml_listings[0].currency,
                    comparables_count=len(ml_listings),
                    confidence_score=0.2,
                    comparable_urls=[l.permalink for l in ml_listings[:3]],
                    match_details="Text similarity too low, using category average",
                )
            return None

        matches.sort(key=lambda x: x[1], reverse=True)
        prices = [m[0].price for m in matches[:10]]

        return MatchResult(
            median_price=statistics.median(prices),
            currency=matches[0][0].currency,
            comparables_count=len(matches),
            confidence_score=statistics.mean([m[1] for m in matches[:10]]) * 0.8,
            comparable_urls=[m[0].permalink for m in matches[:5]],
            match_details="Matched by text similarity",
        )


class RealEstateMatcher:
    """Matcher for real estate auctions."""

    def match(self, auction_title: str, auction_desc: str, ml_listings: list[MLListing]) -> Optional[MatchResult]:
        """Match auction property to market listings."""
        auction_info = extract_realestate_info(auction_title, auction_desc)

        matched = []
        for listing in ml_listings:
            score = self._score_property_match(auction_info, listing)
            if score > 0.2:
                matched.append((listing, score))

        if not matched:
            # Use all listings with low confidence
            if ml_listings:
                prices = [l.price for l in ml_listings[:10]]
                return MatchResult(
                    median_price=statistics.median(prices),
                    currency=ml_listings[0].currency,
                    comparables_count=len(ml_listings),
                    confidence_score=0.15,
                    comparable_urls=[l.permalink for l in ml_listings[:3]],
                    match_details="Low confidence - using search results average",
                )
            return None

        matched.sort(key=lambda x: x[1], reverse=True)
        prices = [m[0].price for m in matched[:10]]

        return MatchResult(
            median_price=statistics.median(prices),
            currency=matched[0][0].currency,
            comparables_count=len(matched),
            confidence_score=statistics.mean([m[1] for m in matched[:10]]),
            comparable_urls=[m[0].permalink for m in matched[:5]],
            match_details=f"Matched by: {', '.join(auction_info.keys()) or 'location'}",
        )

    def _score_property_match(self, auction_info: dict, listing: MLListing) -> float:
        """Score how well a listing matches auction property."""
        score = 0.3  # Base score for being in same search

        listing_attrs = listing.attributes

        # Area match (within 20%)
        if "area_m2" in auction_info and "total_area" in listing_attrs:
            try:
                auction_area = auction_info["area_m2"]
                listing_area = int(listing_attrs["total_area"])
                ratio = min(auction_area, listing_area) / max(auction_area, listing_area)
                if ratio > 0.8:
                    score += 0.4
                elif ratio > 0.6:
                    score += 0.2
            except (ValueError, ZeroDivisionError):
                pass

        # Rooms match
        if "rooms" in auction_info and "rooms" in listing_attrs:
            try:
                auction_rooms = auction_info["rooms"]
                listing_rooms = int(listing_attrs["rooms"])
                if auction_rooms == listing_rooms:
                    score += 0.3
                elif abs(auction_rooms - listing_rooms) <= 1:
                    score += 0.1
            except ValueError:
                pass

        return min(score, 1.0)


class GenericMatcher:
    """Generic matcher for other categories."""

    def match(self, auction_title: str, ml_listings: list[MLListing]) -> Optional[MatchResult]:
        """Match auction item to market listings using text similarity."""
        if not ml_listings:
            return None

        matches = []
        for listing in ml_listings:
            sim = calculate_text_similarity(auction_title, listing.title)
            matches.append((listing, sim))

        matches.sort(key=lambda x: x[1], reverse=True)

        # Take top matches
        top_matches = [m for m in matches[:10] if m[1] > 0.15]

        if not top_matches:
            # Use all results with very low confidence
            prices = [l.price for l in ml_listings[:10]]
            return MatchResult(
                median_price=statistics.median(prices),
                currency=ml_listings[0].currency,
                comparables_count=len(ml_listings),
                confidence_score=0.1,
                comparable_urls=[l.permalink for l in ml_listings[:3]],
                match_details="Low similarity, using category average",
            )

        prices = [m[0].price for m in top_matches]

        return MatchResult(
            median_price=statistics.median(prices),
            currency=top_matches[0][0].currency,
            comparables_count=len(top_matches),
            confidence_score=statistics.mean([m[1] for m in top_matches]),
            comparable_urls=[m[0].permalink for m in top_matches[:5]],
            match_details="Matched by text similarity",
        )
