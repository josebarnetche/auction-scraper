#!/usr/bin/env python3
"""Batch analyze auction opportunities using Claude AI.

This script:
1. Loads listings from site/api/listings.json
2. Filters for high-potential opportunities
3. Runs AI analysis on each
4. Saves detailed analysis reports
5. Generates summary recommendations

Usage:
    python scripts/analyze_opportunities.py --max 10 --category vehicles
    python scripts/analyze_opportunities.py --min-discount 50
    python scripts/analyze_opportunities.py --listing-id cordoba:26092
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.opportunity_analyzer import (
    analyze_opportunity,
    batch_analyze,
    format_analysis_summary,
    OpportunityAnalysis,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


def load_listings(data_path: Path) -> dict:
    """Load listings from JSON file."""
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_opportunities(
    data: dict,
    min_discount: float = 30.0,
    category: str = None,
    max_items: int = 50,
    source: str = None,
) -> list[dict]:
    """Filter listings for analysis based on criteria.

    Args:
        data: Listings data from JSON
        min_discount: Minimum discount percentage
        category: Filter by category (vehicles, machinery, etc.)
        max_items: Maximum items to return
        source: Filter by source (cordoba, banco_ciudad, etc.)

    Returns:
        List of filtered listing dicts
    """
    opportunities = []

    # Get top_opportunities
    for opp in data.get("top_opportunities", []):
        if opp.get("discount_percent", 0) >= min_discount:
            if category and opp.get("category") != category:
                continue
            if source and opp.get("source") != source:
                continue

            opportunities.append({
                "id": opp.get("id"),
                "title": opp.get("title"),
                "description": "",
                "base_price": opp.get("base_price", 0),
                "currency": opp.get("currency", "ARS"),
                "category": opp.get("category", "other"),
                "source": opp.get("source", ""),
                "source_url": opp.get("source_url", ""),
                "discount_percent": opp.get("discount_percent", 0),
                "images": [],
            })

    # Get lots with images (more analyzable)
    for lot in data.get("lots", []):
        if lot.get("images"):
            if category and lot.get("category") != category:
                continue
            if source and lot.get("auction_source") != source:
                continue

            opportunities.append({
                "id": lot.get("lot_id"),
                "title": lot.get("title"),
                "description": lot.get("description", ""),
                "base_price": lot.get("base_price", 0),
                "currency": lot.get("currency", "ARS"),
                "category": "lot",
                "source": lot.get("auction_source", ""),
                "source_url": lot.get("auction_url", ""),
                "discount_percent": lot.get("discount_percent", 0),
                "images": lot.get("images", []),
            })

    # Sort by discount (highest first)
    opportunities.sort(key=lambda x: x.get("discount_percent", 0), reverse=True)

    return opportunities[:max_items]


async def analyze_single(listing: dict, blue_dollar_rate: float) -> OpportunityAnalysis | None:
    """Analyze a single listing."""
    logger.info(f"Analyzing: {listing['id']} - {listing['title'][:50]}...")

    result = await analyze_opportunity(
        listing_id=listing["id"],
        title=listing["title"],
        description=listing.get("description", ""),
        base_price=listing.get("base_price", 0),
        currency=listing.get("currency", "ARS"),
        category=listing.get("category", "other"),
        source=listing.get("source", ""),
        location="",
        end_date="",
        images=listing.get("images", []),
        blue_dollar_rate=blue_dollar_rate,
    )

    if result:
        logger.info(
            f"  -> Score: {result.opportunity_score}/10, "
            f"Action: {result.action_recommendation}, "
            f"Profit: ${result.profit_analysis.net_profit_usd:,.0f}"
        )
    else:
        logger.warning(f"  -> Analysis failed")

    return result


async def main():
    parser = argparse.ArgumentParser(
        description="Analyze auction opportunities with Claude AI"
    )
    parser.add_argument(
        "--max", type=int, default=10,
        help="Maximum number of listings to analyze (default: 10)"
    )
    parser.add_argument(
        "--min-discount", type=float, default=30.0,
        help="Minimum discount percentage to analyze (default: 30)"
    )
    parser.add_argument(
        "--category", type=str,
        help="Filter by category (vehicles, machinery, real_estate)"
    )
    parser.add_argument(
        "--source", type=str,
        help="Filter by source (cordoba, banco_ciudad, csjn, etc.)"
    )
    parser.add_argument(
        "--listing-id", type=str,
        help="Analyze a specific listing by ID"
    )
    parser.add_argument(
        "--output", type=str, default="data/opportunity_analysis.json",
        help="Output file path (default: data/opportunity_analysis.json)"
    )
    parser.add_argument(
        "--concurrent", type=int, default=3,
        help="Maximum concurrent API calls (default: 3)"
    )
    parser.add_argument(
        "--blue-rate", type=float, default=1430.0,
        help="Blue dollar exchange rate (default: 1430)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be analyzed without calling API"
    )

    args = parser.parse_args()

    # Paths
    project_root = Path(__file__).parent.parent
    listings_path = project_root / "site" / "api" / "listings.json"
    output_path = project_root / args.output

    # Load data
    logger.info(f"Loading listings from {listings_path}...")
    data = load_listings(listings_path)
    blue_rate = data.get("blue_dollar_rate", args.blue_rate)
    logger.info(f"Blue dollar rate: ${blue_rate}")

    # Handle single listing analysis
    if args.listing_id:
        # Find the specific listing
        listing = None
        for opp in data.get("top_opportunities", []):
            if opp.get("id") == args.listing_id:
                listing = {
                    "id": opp.get("id"),
                    "title": opp.get("title"),
                    "description": "",
                    "base_price": opp.get("base_price", 0),
                    "currency": opp.get("currency", "ARS"),
                    "category": opp.get("category", "other"),
                    "source": opp.get("source", ""),
                    "images": [],
                }
                break

        if not listing:
            for lot in data.get("lots", []):
                if lot.get("lot_id") == args.listing_id:
                    listing = {
                        "id": lot.get("lot_id"),
                        "title": lot.get("title"),
                        "description": lot.get("description", ""),
                        "base_price": lot.get("base_price", 0),
                        "currency": lot.get("currency", "ARS"),
                        "category": "lot",
                        "source": lot.get("auction_source", ""),
                        "images": lot.get("images", []),
                    }
                    break

        if not listing:
            logger.error(f"Listing not found: {args.listing_id}")
            sys.exit(1)

        if args.dry_run:
            logger.info(f"Would analyze: {listing['title']}")
            return

        result = await analyze_single(listing, blue_rate)
        if result:
            print(format_analysis_summary(result))

            # Save single result
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "listing_id": args.listing_id,
                    "analysis": result.to_dict(),
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"Analysis saved to {output_path}")
        return

    # Filter opportunities
    opportunities = filter_opportunities(
        data,
        min_discount=args.min_discount,
        category=args.category,
        max_items=args.max,
        source=args.source,
    )

    if not opportunities:
        logger.warning("No opportunities found matching criteria")
        return

    logger.info(f"Found {len(opportunities)} opportunities to analyze")

    if args.dry_run:
        logger.info("DRY RUN - Would analyze:")
        for i, opp in enumerate(opportunities, 1):
            logger.info(f"  {i}. [{opp['source']}] {opp['title'][:60]}... ({opp['discount_percent']:.0f}% off)")
        estimated_cost = len(opportunities) * 0.005  # ~$0.005 per analysis with Haiku
        logger.info(f"Estimated API cost: ${estimated_cost:.2f}")
        return

    # Run batch analysis
    logger.info(f"Starting batch analysis (max concurrent: {args.concurrent})...")
    start_time = datetime.now()

    results = []
    semaphore = asyncio.Semaphore(args.concurrent)

    async def analyze_with_semaphore(listing):
        async with semaphore:
            return await analyze_single(listing, blue_rate)

    tasks = [analyze_with_semaphore(opp) for opp in opportunities]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in task_results:
        if isinstance(result, Exception):
            logger.error(f"Analysis error: {result}")
        elif result:
            results.append(result)

    elapsed = (datetime.now() - start_time).total_seconds()

    # Generate summary
    logger.info(f"\n{'='*60}")
    logger.info(f"ANALYSIS COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Analyzed: {len(results)}/{len(opportunities)} listings")
    logger.info(f"Time: {elapsed:.1f}s")

    if results:
        # Sort by opportunity score
        results.sort(key=lambda x: x.opportunity_score, reverse=True)

        # Group by recommendation
        buy_recs = [r for r in results if r.action_recommendation == "BUY"]
        watch_recs = [r for r in results if r.action_recommendation == "WATCH"]
        skip_recs = [r for r in results if r.action_recommendation == "SKIP"]

        logger.info(f"\nRECOMMENDATIONS:")
        logger.info(f"  BUY: {len(buy_recs)}")
        logger.info(f"  WATCH: {len(watch_recs)}")
        logger.info(f"  SKIP: {len(skip_recs)}")

        # Top opportunities
        logger.info(f"\nTOP OPPORTUNITIES:")
        for i, result in enumerate(buy_recs[:5], 1):
            logger.info(
                f"  {i}. Score {result.opportunity_score}/10: {result.one_liner}"
            )
            logger.info(
                f"     Net Profit: ${result.profit_analysis.net_profit_usd:,.0f} "
                f"({result.profit_analysis.profit_margin_percent:.0f}%)"
            )

        # Calculate totals
        total_cost = sum(r.analysis_cost_usd for r in results)
        total_potential_profit = sum(
            r.profit_analysis.net_profit_usd for r in buy_recs
        )

        logger.info(f"\nSUMMARY:")
        logger.info(f"  Total analysis cost: ${total_cost:.4f}")
        logger.info(f"  Total profit potential (BUY recs): ${total_potential_profit:,.0f}")

        # Save results
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "blue_dollar_rate": blue_rate,
            "analyzed_count": len(results),
            "summary": {
                "buy_count": len(buy_recs),
                "watch_count": len(watch_recs),
                "skip_count": len(skip_recs),
                "total_analysis_cost_usd": total_cost,
                "total_profit_potential_usd": total_potential_profit,
            },
            "top_opportunities": [
                {
                    **r.to_dict(),
                    "source_listing": next(
                        (o for o in opportunities if o["id"] == r.listing_id),
                        {}
                    ),
                }
                for r in results if r.action_recommendation == "BUY"
            ],
            "all_analyses": [r.to_dict() for r in results],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        logger.info(f"\nResults saved to: {output_path}")

        # Print detailed analysis for top 3
        logger.info(f"\n{'='*60}")
        logger.info("DETAILED TOP OPPORTUNITIES")
        logger.info(f"{'='*60}")

        for result in buy_recs[:3]:
            print(format_analysis_summary(result))


if __name__ == "__main__":
    asyncio.run(main())
