#!/usr/bin/env python3
"""Generate hot deals JSON from auction listings.

This script:
1. Loads all listings from site/api/listings.json
2. Applies the hot deals scoring algorithm
3. Outputs top opportunities to data/hot_deals.json

Usage:
    python scripts/generate_hot_deals.py
    python scripts/generate_hot_deals.py --min-score 60 --max-results 100
    python scripts/generate_hot_deals.py --category vehicles
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.hot_deals import HotDealsScorer, DealTier


def load_listings(api_file: Path) -> tuple[list[dict], dict]:
    """Load listings from API JSON file.

    Returns:
        Tuple of (listings list, metadata dict)
    """
    if not api_file.exists():
        print(f"ERROR: {api_file} not found")
        return [], {}

    with open(api_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    listings = data.get("listings", [])
    metadata = {
        "total_count": data.get("total_count", len(listings)),
        "by_source": data.get("by_source", {}),
        "blue_dollar_rate": data.get("blue_dollar_rate", 1430.0),
        "generated_at": data.get("generated_at"),
    }

    return listings, metadata


def filter_by_category(listings: list[dict], category: str) -> list[dict]:
    """Filter listings by category."""
    if not category or category.lower() == "all":
        return listings
    return [l for l in listings if l.get("category", "").lower() == category.lower()]


def filter_active(listings: list[dict]) -> list[dict]:
    """Filter to only active/upcoming auctions."""
    now = datetime.now(timezone.utc)
    active = []

    for listing in listings:
        ends_at = listing.get("ends_at")
        if not ends_at:
            # No end date - include it
            active.append(listing)
            continue

        try:
            if isinstance(ends_at, str):
                end_date = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                if end_date > now:
                    active.append(listing)
        except (ValueError, TypeError):
            # Can't parse date - include it
            active.append(listing)

    return active


def print_deal_summary(deal, rank: int):
    """Print a formatted summary of a hot deal."""
    tier_emoji = {
        "exceptional": "[!!!]",
        "hot": "[!!]",
        "warm": "[!]",
        "neutral": "[~]",
        "cold": "[ ]",
    }

    emoji = tier_emoji.get(deal.tier, "[ ]")
    print(f"\n{rank:2}. {emoji} Score: {deal.score:.1f} | {deal.tier.upper()}")
    print(f"    {deal.title[:70]}...")
    print(f"    Price: {deal.currency} ${deal.base_price:,.0f} (USD ${deal.base_price_usd:,.0f})")

    if deal.market_price_usd:
        print(f"    Market: USD ${deal.market_price_usd:,.0f} | Discount: {deal.discount_percent:.0f}%")
        if deal.profit_potential_usd > 0:
            print(f"    Profit Potential: USD ${deal.profit_potential_usd:,.0f} ({deal.profit_potential_percent:.0f}%)")

    if deal.days_until_close is not None:
        if deal.days_until_close <= 0:
            print(f"    ENDS TODAY!")
        elif deal.days_until_close <= 7:
            print(f"    Ends in: {deal.days_until_close} day(s)")

    print(f"    Source: {deal.source} | Category: {deal.category}")
    print(f"    {deal.source_url}")
    print(f"    Recommendation: {deal.action_recommendation}")


def generate_stats(deals: list) -> dict:
    """Generate statistics from scored deals."""
    if not deals:
        return {}

    tier_counts = {}
    for tier in DealTier:
        tier_counts[tier.value] = sum(1 for d in deals if d.tier == tier.value)

    category_counts = {}
    for deal in deals:
        cat = deal.category
        if cat not in category_counts:
            category_counts[cat] = 0
        category_counts[cat] += 1

    source_counts = {}
    for deal in deals:
        src = deal.source
        if src not in source_counts:
            source_counts[src] = 0
        source_counts[src] += 1

    scores = [d.score for d in deals]
    avg_score = sum(scores) / len(scores) if scores else 0

    discounts = [d.discount_percent for d in deals if d.discount_percent > 0]
    avg_discount = sum(discounts) / len(discounts) if discounts else 0

    total_profit_potential = sum(d.profit_potential_usd for d in deals if d.profit_potential_usd > 0)

    return {
        "total_scored": len(deals),
        "by_tier": tier_counts,
        "by_category": category_counts,
        "by_source": source_counts,
        "avg_score": round(avg_score, 1),
        "avg_discount_percent": round(avg_discount, 1),
        "total_profit_potential_usd": round(total_profit_potential, 2),
        "exceptional_count": tier_counts.get("exceptional", 0),
        "hot_count": tier_counts.get("hot", 0),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate hot deals JSON from auction listings"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=40.0,
        help="Minimum score to include (default: 40)"
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Maximum results to output (default: 50)"
    )
    parser.add_argument(
        "--category",
        type=str,
        default="all",
        help="Filter by category (vehicles, real_estate, machinery, general_goods, other, all)"
    )
    parser.add_argument(
        "--include-past",
        action="store_true",
        help="Include past/expired auctions"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/hot_deals.json",
        help="Output file path"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console output"
    )

    args = parser.parse_args()

    # Paths
    project_root = Path(__file__).parent.parent
    api_file = project_root / "site" / "api" / "listings.json"
    output_file = project_root / args.output

    if not args.quiet:
        print("=" * 80)
        print("SUBASTO HOT DEALS GENERATOR")
        print("=" * 80)

    # Load listings
    listings, metadata = load_listings(api_file)
    if not listings:
        print("No listings found. Run the scraper first.")
        return 1

    if not args.quiet:
        print(f"\nLoaded {len(listings)} listings from {api_file}")
        print(f"Blue dollar rate: ${metadata.get('blue_dollar_rate', 1430)}")

    # Filter by category
    if args.category.lower() != "all":
        listings = filter_by_category(listings, args.category)
        if not args.quiet:
            print(f"Filtered to {len(listings)} {args.category} listings")

    # Filter active only
    if not args.include_past:
        listings = filter_active(listings)
        if not args.quiet:
            print(f"Filtered to {len(listings)} active listings")

    # Initialize scorer
    blue_rate = metadata.get("blue_dollar_rate", 1430.0)
    scorer = HotDealsScorer(blue_dollar_rate=blue_rate)

    # Score all listings
    if not args.quiet:
        print(f"\nScoring {len(listings)} listings...")

    all_deals = scorer.score_listings(listings)

    # Filter by minimum score
    hot_deals = [d for d in all_deals if d.score >= args.min_score]

    # Limit results
    hot_deals = hot_deals[:args.max_results]

    # Generate stats
    stats = generate_stats(hot_deals)

    if not args.quiet:
        print("\n" + "=" * 80)
        print("TOP HOT DEALS")
        print("=" * 80)

        # Show top 20 in console
        for i, deal in enumerate(hot_deals[:20], 1):
            print_deal_summary(deal, i)

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total scored: {stats.get('total_scored', 0)}")
        print(f"Exceptional deals (85+): {stats.get('exceptional_count', 0)}")
        print(f"Hot deals (70-84): {stats.get('hot_count', 0)}")
        print(f"Average score: {stats.get('avg_score', 0)}")
        print(f"Average discount: {stats.get('avg_discount_percent', 0):.1f}%")
        print(f"Total profit potential: USD ${stats.get('total_profit_potential_usd', 0):,.0f}")
        print("\nBy tier:", stats.get("by_tier", {}))
        print("By category:", stats.get("by_category", {}))

    # Prepare output data
    output_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "min_score": args.min_score,
            "max_results": args.max_results,
            "category_filter": args.category,
            "include_past": args.include_past,
        },
        "source_data": {
            "listings_file": str(api_file),
            "total_listings": len(listings),
            "blue_dollar_rate": blue_rate,
        },
        "stats": stats,
        "deals": [deal.to_dict() for deal in hot_deals],
    }

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    if not args.quiet:
        print(f"\nHot deals saved to: {output_file}")
        print(f"Total deals in output: {len(hot_deals)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
