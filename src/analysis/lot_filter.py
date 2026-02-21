"""Filtering logic for AI analysis of auction lots.

Determines which lots qualify for Claude analysis based on:
- Source quality (priority auction houses)
- Category (machinery, vehicles, electronics)
- Price range (sweet spot for opportunities)
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.listing import LotItem, AuctionListing


# Priority sources with reliable lot data
PRIORITY_SOURCES = [
    "banco_ciudad",
    "csjn",
    "global_remates",
    "scba",
]

# Categories worth analyzing (skip real estate for now)
ANALYZABLE_CATEGORIES = [
    "machinery",
    "vehicles",
    "electronics",
    "industrial",
    "equipment",
    "other",  # Include other for now, AI will filter
]

# Skip categories that don't benefit from AI analysis
SKIP_CATEGORIES = [
    "real_estate",
]

# Price range in USD for analysis
# Too cheap = not worth analysis cost
# Too expensive = likely real estate or specialized
PRICE_RANGE_USD = (500, 100000)

# Minimum lot title length for meaningful analysis
MIN_TITLE_LENGTH = 10

# Keywords that indicate high-value lots worth analyzing
HIGH_VALUE_KEYWORDS = [
    # Industrial equipment
    "computadora", "servidor", "industrial", "maquina",
    "tractor", "cosechadora", "camion", "camión",
    # Electronics
    "camera", "cámara", "monitor", "impresora",
    "router", "switch", "ups", "generador",
    # Vehicles
    "auto", "vehiculo", "vehículo", "pickup",
    "utilitario", "furgon", "furgón",
    # Machinery
    "motor", "compresor", "soldadora", "torno",
    "fresadora", "grua", "grúa", "montacargas",
]

# Keywords that indicate low-value or bulk lots to skip
SKIP_KEYWORDS = [
    "varios", "lote residual", "scrap",
    "chatarra", "desecho", "rezago",
]


def should_analyze(lot: "LotItem", auction: "AuctionListing") -> bool:
    """Determine if lot qualifies for AI analysis.

    Args:
        lot: The lot to evaluate
        auction: Parent auction for context

    Returns:
        True if lot should be analyzed
    """
    # Check source priority
    if auction.source not in PRIORITY_SOURCES:
        return False

    # Check category
    category = auction.category.lower() if auction.category else "other"
    if category in SKIP_CATEGORIES:
        return False

    # Check price range
    price_usd = lot.base_price_usd
    if price_usd <= 0:
        # No price data - might still be valuable
        # Use base_price with rough estimate if needed
        if lot.currency == "ARS" and lot.base_price > 0:
            price_usd = lot.base_price / 1400  # Rough estimate
        else:
            price_usd = lot.base_price

    if not (PRICE_RANGE_USD[0] <= price_usd <= PRICE_RANGE_USD[1]):
        return False

    # Check title quality
    title = lot.title.lower() if lot.title else ""
    if len(title) < MIN_TITLE_LENGTH:
        return False

    # Skip low-value keywords
    if any(kw in title for kw in SKIP_KEYWORDS):
        return False

    # Prioritize high-value keywords
    has_high_value = any(kw in title for kw in HIGH_VALUE_KEYWORDS)

    # If no high-value keywords, still include but with lower priority
    # The AI analysis will determine actual value
    return True


def filter_lots_for_analysis(
    lots: list["LotItem"],
    auction: "AuctionListing",
    max_lots: int = 50
) -> list["LotItem"]:
    """Filter and prioritize lots for AI analysis.

    Args:
        lots: List of lots to filter
        auction: Parent auction
        max_lots: Maximum lots to return

    Returns:
        Filtered and prioritized list of lots
    """
    qualifying = []

    for lot in lots:
        if should_analyze(lot, auction):
            # Calculate priority score for sorting
            score = 0
            title = lot.title.lower() if lot.title else ""

            # High-value keywords boost priority
            for kw in HIGH_VALUE_KEYWORDS:
                if kw in title:
                    score += 10

            # Higher prices get priority (more opportunity value)
            if lot.base_price_usd > 10000:
                score += 20
            elif lot.base_price_usd > 5000:
                score += 10

            qualifying.append((score, lot))

    # Sort by priority score (highest first)
    qualifying.sort(key=lambda x: x[0], reverse=True)

    return [lot for _, lot in qualifying[:max_lots]]


def estimate_analysis_cost(lot_count: int, cost_per_lot: float = 0.015) -> float:
    """Estimate AI analysis cost.

    Args:
        lot_count: Number of lots to analyze
        cost_per_lot: Estimated cost per lot (Claude Haiku)

    Returns:
        Estimated total cost in USD
    """
    return lot_count * cost_per_lot
