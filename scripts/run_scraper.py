#!/usr/bin/env python3
"""Main orchestration script for auction scraping."""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.judicial.csjn import CSJNScraper
from src.scrapers.judicial.scba import SCBAScraper
from src.scrapers.judicial.comprar import ComprarScraper
from src.scrapers.private.adrian_mercado import AdrianMercadoScraper
from src.scrapers.private.banco_ciudad import BancoCiudadScraper
from src.scrapers.private.global_remates import GlobalRematesScraper
from src.scrapers.private.bidbit import BidBitScraper
from src.scrapers.private.manucha import ManuchaScraper
from src.scrapers.private.delafuente import DelaFuenteScraper
from src.scrapers.private.zarate import ZarateScraper
from src.scrapers.private.sitiodetiendas import SitioDeTiendasScraper
from src.storage.json_store import JSONStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# All available scrapers
SCRAPERS = {
    # Judicial auctions
    "csjn": CSJNScraper,
    "scba": SCBAScraper,
    "comprar": ComprarScraper,
    # Private auction houses
    "adrian_mercado": AdrianMercadoScraper,
    "banco_ciudad": BancoCiudadScraper,
    "global_remates": GlobalRematesScraper,
    "bidbit": BidBitScraper,
    "manucha": ManuchaScraper,
    "delafuente": DelaFuenteScraper,
    "zarate": ZarateScraper,
    "sitiodetiendas": SitioDeTiendasScraper,
}


async def run_scraper(name: str, scraper_class, store: JSONStore):
    """Run a single scraper and save results."""
    logger.info(f"Running scraper: {name}")

    try:
        async with scraper_class() as scraper:
            listings = await scraper.scrape()
            if listings:
                store.save_listings(name, listings)
                logger.info(f"{name}: saved {len(listings)} listings")
            else:
                logger.warning(f"{name}: no listings found")
            return listings
    except Exception as e:
        logger.error(f"{name}: scraper failed - {e}")
        return []


async def run_all_scrapers(sources: list[str], store: JSONStore):
    """Run multiple scrapers concurrently."""
    tasks = []

    for name in sources:
        if name not in SCRAPERS:
            logger.warning(f"Unknown scraper: {name}")
            continue
        tasks.append(run_scraper(name, SCRAPERS[name], store))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_listings = []
    for result in results:
        if isinstance(result, list):
            all_listings.extend(result)
        elif isinstance(result, Exception):
            logger.error(f"Scraper error: {result}")

    return all_listings


async def fetch_market_prices(listings: list):
    """Fetch real market prices for auction items.

    This is best-effort - if external sites are unavailable,
    the scraper continues without market prices.
    """
    try:
        from src.market.price_manager import MarketPriceManager
    except ImportError as e:
        logger.warning(f"Market price module not available: {e}")
        return

    logger.info("Fetching real market prices (best-effort)...")

    # Convert listings to dict format if needed
    listings_data = []
    for listing in listings:
        if hasattr(listing, "__dict__"):
            listings_data.append({
                "id": listing.id,
                "title": listing.title,
                "description": getattr(listing, "description", ""),
                "category": listing.category,
                "location": getattr(listing, "location", {}),
            })
        elif isinstance(listing, dict):
            listings_data.append(listing)

    # Only fetch for items that might have market comparables
    items_to_price = [
        l for l in listings_data
        if l.get("category") in ["vehicles", "real_estate"]
    ]

    if not items_to_price:
        logger.info("No vehicles or real estate to price")
        return

    logger.info(f"Attempting to fetch prices for {len(items_to_price)} items...")

    try:
        manager = MarketPriceManager()
        new_prices = await manager.fetch_prices_for_listings(items_to_price[:20])  # Limit to avoid timeouts
        logger.info(f"Successfully fetched {len(new_prices)} market prices")
    except Exception as e:
        logger.warning(f"Market price fetching failed (non-critical): {e}")
        logger.info("Continuing without market prices - site will not show comparisons")


async def main():
    parser = argparse.ArgumentParser(description="Argentina Auction Scraper")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=list(SCRAPERS.keys()) + ["all"],
        default=["all"],
        help="Sources to scrape"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode - only scrape first source"
    )
    parser.add_argument(
        "--skip-market-prices",
        action="store_true",
        help="Skip fetching market prices"
    )

    args = parser.parse_args()

    store = JSONStore()

    # Determine sources
    if "all" in args.sources:
        sources = list(SCRAPERS.keys())
    else:
        sources = args.sources

    if args.test:
        sources = sources[:1]
        logger.info(f"Test mode: only running {sources[0]}")

    # Run scrapers
    all_listings = await run_all_scrapers(sources, store)
    logger.info(f"Total listings scraped: {len(all_listings)}")

    # Fetch real market prices (unless skipped)
    if not args.skip_market_prices and not args.test:
        try:
            await fetch_market_prices(all_listings)
        except Exception as e:
            logger.error(f"Market price fetching failed: {e}")

    # Generate site files
    from scripts.generate_site import generate_site
    generate_site()

    logger.info("Scraping complete!")


if __name__ == "__main__":
    asyncio.run(main())
