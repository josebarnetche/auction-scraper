#!/usr/bin/env python3
"""Test price comparison functionality."""

import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.listing import AuctionListing
from src.processors.opportunity_detector import OpportunityDetector
from src.storage.json_store import JSONStore


async def test_comparison(sample_size: int = 5):
    """Test price comparison on sample listings."""
    store = JSONStore()
    listings = store.load_all_listings()

    if not listings:
        print("No listings found. Run the scraper first.")
        return

    print(f"Loaded {len(listings)} listings")

    # Take sample
    sample = listings[:sample_size]

    print(f"\nAnalyzing {len(sample)} sample listings...\n")

    async with OpportunityDetector() as detector:
        for listing in sample:
            print(f"Analyzing: {listing.title[:50]}...")

            opp = await detector.analyze_listing(listing)

            if opp:
                print(f"  Auction: USD {opp.auction_price_usd:,.0f}")
                print(f"  Market:  USD {opp.market_median_usd:,.0f}")
                print(f"  Discount: {opp.discount_percentage:.1f}%")
                print(f"  Confidence: {opp.confidence_score:.0%}")
                print(f"  Flagged: {'YES' if opp.is_flagged else 'no'}")
                print(f"  Notes: {opp.analysis_notes}")
            else:
                print("  Could not analyze (no comparables found)")

            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=5, help="Number of listings to test")
    args = parser.parse_args()

    asyncio.run(test_comparison(args.sample))
