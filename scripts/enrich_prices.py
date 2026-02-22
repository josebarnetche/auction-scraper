#!/usr/bin/env python3
"""
Market Price Enrichment Script

Enriches auction listings with market price comparisons to show buyers
the true value proposition: "This $5,000 auction item is worth $12,000 on MercadoLibre"

Usage:
    python scripts/enrich_prices.py                    # Enrich all listings
    python scripts/enrich_prices.py --category vehicles  # Only vehicles
    python scripts/enrich_prices.py --source csjn      # Only CSJN listings
    python scripts/enrich_prices.py --no-live          # Skip live sources
    python scripts/enrich_prices.py --max 20           # Limit to 20 items
    python scripts/enrich_prices.py --stats            # Show statistics only
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.market.price_enricher import PriceEnricher
from src.market.currency import CurrencyConverter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_listings(source: str = None, category: str = None) -> list[dict]:
    """Load auction listings from raw data files."""
    raw_dir = Path("data/raw")
    all_listings = []

    if source:
        files = [raw_dir / f"{source}.json"]
    else:
        files = list(raw_dir.glob("*.json"))

    for file_path in files:
        if not file_path.exists():
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    listings = data
                else:
                    listings = [data]

                for listing in listings:
                    # Filter by category if specified
                    if category and listing.get("category") != category:
                        continue
                    all_listings.append(listing)

        except Exception as e:
            logger.warning(f"Error loading {file_path}: {e}")

    return all_listings


def print_summary(enricher: PriceEnricher):
    """Print enrichment summary."""
    stats = enricher.get_stats()

    print("\n" + "=" * 60)
    print("MARKET PRICE ENRICHMENT SUMMARY")
    print("=" * 60)
    print(f"\nTotal enriched: {stats['total']}")
    print(f"High confidence: {stats.get('high_confidence_count', 0)}")
    print(f"Opportunities found: {stats.get('opportunities_count', 0)}")
    print(f"Average discount: {stats.get('average_discount_percent', 0):.1f}%")
    print(f"Average confidence: {stats.get('average_confidence', 0):.2f}")

    by_cat = stats.get("by_category", {})
    if by_cat:
        print("\nBy Category:")
        for cat, data in by_cat.items():
            print(f"  {cat}: {data['count']} items, avg discount {data['avg_discount']:.1f}%")

    # Show top opportunities
    opportunities = enricher.get_opportunities(min_discount=30.0)
    if opportunities:
        print(f"\nTop Opportunities (30%+ discount):")
        sorted_opps = sorted(opportunities, key=lambda x: x.discount_percent, reverse=True)
        for opp in sorted_opps[:10]:
            print(f"  - {opp.auction_title[:40]}...")
            print(f"    Auction: ${opp.auction_price_usd:,.0f} | Market: ${opp.market_price_usd:,.0f} | "
                  f"Save: {opp.discount_percent:.0f}% (${opp.savings_usd:,.0f})")

    print("\n" + "=" * 60)


async def main():
    parser = argparse.ArgumentParser(
        description="Enrich auction listings with market price comparisons"
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Only process listings from this source (e.g., csjn, scba)"
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=["vehicles", "real_estate", "machinery", "general_goods"],
        help="Only process this category"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=50,
        help="Maximum items to process (default: 50)"
    )
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="Skip live market source queries (use reference data only)"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics only, don't enrich"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize enricher
    enricher = PriceEnricher()

    if args.stats:
        print_summary(enricher)
        return

    # Load listings
    logger.info("Loading auction listings...")
    listings = load_listings(source=args.source, category=args.category)

    if not listings:
        logger.warning("No listings found to enrich")
        return

    logger.info(f"Found {len(listings)} listings to process")

    # Filter for items with prices that can be enriched
    enrichable = [
        l for l in listings
        if l.get("base_price", 0) > 0
        and l.get("category") in ["vehicles", "real_estate", "machinery", "general_goods"]
    ]

    logger.info(f"Enrichable listings: {len(enrichable)}")

    if not enrichable:
        logger.warning("No enrichable listings found (need base_price > 0 and valid category)")
        return

    # Show current dollar rate
    converter = CurrencyConverter()
    rate = await converter.get_blue_dollar_rate()
    logger.info(f"Blue dollar rate: {rate}")

    # Enrich listings
    logger.info(f"Enriching up to {args.max} listings...")
    results = await enricher.enrich_listings(
        enrichable,
        use_live_sources=not args.no_live,
        max_items=args.max
    )

    logger.info(f"Successfully enriched {len(results)} listings")

    # Print summary
    print_summary(enricher)

    # Export for site
    site_data = enricher.export_for_site()
    site_file = Path("site/api/market_prices.json")
    site_file.parent.mkdir(parents=True, exist_ok=True)

    with open(site_file, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": results[0].enriched_at if results else "",
            "count": len(site_data),
            "prices": site_data
        }, f, indent=2, ensure_ascii=False)

    logger.info(f"Exported {len(site_data)} prices to {site_file}")


if __name__ == "__main__":
    asyncio.run(main())
