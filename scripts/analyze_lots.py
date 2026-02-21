#!/usr/bin/env python3
"""Batch analysis script for auction lots.

Loads scraped listings, filters lots qualifying for AI analysis,
runs Claude analysis, and saves enriched results.
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.listing import AuctionListing, LotItem
from src.analysis.lot_filter import (
    filter_lots_for_analysis,
    should_analyze,
    estimate_analysis_cost,
    PRIORITY_SOURCES,
)
from src.analysis.lot_analyzer import (
    analyze_lot,
    apply_analysis_to_lot,
    calculate_discount_percent,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_listings() -> list[dict]:
    """Load all scraped listings from raw data files."""
    data_dir = Path("data/raw")
    all_listings = []

    for json_file in data_dir.glob("*.json"):
        if json_file.name == ".gitkeep":
            continue
        try:
            with open(json_file, encoding="utf-8") as f:
                listings = json.load(f)
                if isinstance(listings, list):
                    all_listings.extend(listings)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not read {json_file}: {e}")

    return all_listings


def save_analyzed_listings(listings: list[dict], output_path: Path):
    """Save analyzed listings to JSON file."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved analyzed listings to {output_path}")


async def analyze_new_lots(
    dry_run: bool = False,
    max_lots: int = 50,
    source_filter: str = None,
    model: str = "claude-3-haiku-20240307",
):
    """Analyze lots that pass filters and haven't been analyzed.

    Args:
        dry_run: If True, only show what would be analyzed
        max_lots: Maximum lots to analyze per run
        source_filter: Only analyze lots from this source
        model: Claude model to use
    """
    listings = load_listings()
    logger.info(f"Loaded {len(listings)} total listings")

    # Collect all qualifying lots
    lots_to_analyze = []
    auction_map = {}  # lot_id -> auction data

    for listing_data in listings:
        source = listing_data.get("source", "")

        # Apply source filter
        if source_filter and source != source_filter:
            continue

        # Check if source is priority
        if source not in PRIORITY_SOURCES:
            continue

        # Check for lots
        lots_data = listing_data.get("lots", [])
        if not lots_data:
            continue

        # Create temporary AuctionListing for filtering
        auction = AuctionListing(
            id=listing_data.get("id", ""),
            source=source,
            source_url=listing_data.get("source_url", ""),
            title=listing_data.get("title", ""),
            description=listing_data.get("description", ""),
            category=listing_data.get("category", "other"),
            base_price=listing_data.get("base_price", 0),
            currency=listing_data.get("currency", "ARS"),
            status=listing_data.get("status", "published"),
        )

        # Convert lot dicts to LotItem objects and filter
        for lot_data in lots_data:
            # Skip already analyzed lots
            if lot_data.get("ai_analyzed_at"):
                continue

            lot = LotItem(
                lot_id=lot_data.get("lot_id", ""),
                lot_number=lot_data.get("lot_number", 1),
                title=lot_data.get("title", ""),
                description=lot_data.get("description", ""),
                base_price=lot_data.get("base_price", 0),
                currency=lot_data.get("currency", "ARS"),
                base_price_usd=lot_data.get("base_price_usd", 0),
            )

            if should_analyze(lot, auction):
                lots_to_analyze.append((lot, auction, lot_data))
                auction_map[lot.lot_id] = {
                    "auction_title": auction.title,
                    "source": auction.source,
                }

    logger.info(f"Found {len(lots_to_analyze)} lots qualifying for analysis")

    if not lots_to_analyze:
        logger.info("No new lots to analyze")
        return

    # Limit to max_lots
    if len(lots_to_analyze) > max_lots:
        logger.info(f"Limiting to {max_lots} lots (from {len(lots_to_analyze)})")
        lots_to_analyze = lots_to_analyze[:max_lots]

    # Estimate cost
    estimated_cost = estimate_analysis_cost(len(lots_to_analyze))
    logger.info(f"Estimated analysis cost: ${estimated_cost:.2f}")

    if dry_run:
        logger.info("DRY RUN - Would analyze these lots:")
        for lot, auction, _ in lots_to_analyze[:10]:
            logger.info(f"  - [{auction.source}] {lot.title[:60]}... (${lot.base_price_usd:.0f} USD)")
        if len(lots_to_analyze) > 10:
            logger.info(f"  ... and {len(lots_to_analyze) - 10} more")
        return

    # Run analysis
    analyzed_count = 0
    high_opportunity_count = 0
    results = []

    for i, (lot, auction, lot_data) in enumerate(lots_to_analyze):
        logger.info(f"Analyzing [{i+1}/{len(lots_to_analyze)}]: {lot.title[:50]}...")

        try:
            analysis = await analyze_lot(
                lot,
                auction_title=auction.title,
                model=model
            )

            if analysis:
                # Apply analysis to lot
                apply_analysis_to_lot(lot, analysis)

                # Update the original lot_data dict
                lot_data["ai_specs"] = lot.ai_specs
                lot_data["ai_market_value_usd"] = lot.ai_market_value_usd
                lot_data["ai_opportunity_score"] = lot.ai_opportunity_score
                lot_data["ai_analyzed_at"] = lot.ai_analyzed_at.isoformat()

                discount = calculate_discount_percent(lot)

                analyzed_count += 1
                if lot.ai_opportunity_score and lot.ai_opportunity_score >= 7:
                    high_opportunity_count += 1
                    logger.info(f"  -> HIGH OPPORTUNITY! Score: {lot.ai_opportunity_score}/10, "
                              f"Discount: {discount:.0f}%" if discount else "")

                results.append({
                    "lot_id": lot.lot_id,
                    "title": lot.title,
                    "base_price_usd": lot.base_price_usd,
                    "market_value_usd": lot.ai_market_value_usd,
                    "opportunity_score": lot.ai_opportunity_score,
                    "discount_percent": discount,
                    "specs": lot.ai_specs,
                })

            # Rate limit
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error analyzing lot {lot.lot_id}: {e}")
            continue

    # Summary
    logger.info("=" * 60)
    logger.info("ANALYSIS COMPLETE")
    logger.info(f"  Analyzed: {analyzed_count}/{len(lots_to_analyze)} lots")
    logger.info(f"  High opportunities (score 7+): {high_opportunity_count}")

    if results:
        # Save analysis results
        output_path = Path("data/lot_analysis_results.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "total_analyzed": analyzed_count,
                "high_opportunities": high_opportunity_count,
                "results": results,
            }, f, indent=2, ensure_ascii=False)
        logger.info(f"Results saved to {output_path}")

        # Show top opportunities
        top_opps = sorted(
            [r for r in results if r.get("opportunity_score", 0) >= 7],
            key=lambda x: x.get("opportunity_score", 0),
            reverse=True
        )[:5]

        if top_opps:
            logger.info("\nTOP OPPORTUNITIES:")
            for opp in top_opps:
                discount = opp.get("discount_percent")
                discount_str = f"{discount:.0f}% off" if discount else "N/A"
                logger.info(f"  [{opp['opportunity_score']}/10] {opp['title'][:50]}... ({discount_str})")


async def main():
    parser = argparse.ArgumentParser(description="Analyze auction lots with AI")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be analyzed without making API calls"
    )
    parser.add_argument(
        "--max-lots",
        type=int,
        default=50,
        help="Maximum lots to analyze per run"
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Only analyze lots from this source"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-3-haiku-20240307",
        help="Claude model to use for analysis"
    )

    args = parser.parse_args()

    await analyze_new_lots(
        dry_run=args.dry_run,
        max_lots=args.max_lots,
        source_filter=args.source,
        model=args.model,
    )


if __name__ == "__main__":
    asyncio.run(main())
