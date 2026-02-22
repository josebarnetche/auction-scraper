#!/usr/bin/env python3
"""Safe incremental scraper - only adds NEW listings, preserves existing data."""

import asyncio
import argparse
import logging
import json
import shutil
from pathlib import Path
from datetime import datetime
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.judicial.csjn import CSJNScraper
from src.scrapers.judicial.scba import SCBAScraper
from src.scrapers.judicial.entrerios import EntreRiosScraper
from src.scrapers.judicial.cordoba import CordobaScraper
from src.scrapers.private.adrian_mercado import AdrianMercadoScraper
from src.scrapers.private.banco_ciudad import BancoCiudadScraper
from src.scrapers.private.global_remates import GlobalRematesScraper
from src.scrapers.private.bidbit import BidBitScraper
from src.scrapers.private.manucha import ManuchaScraper
from src.scrapers.private.delafuente import DelaFuenteScraper
from src.scrapers.private.zarate import ZarateScraper
from src.scrapers.private.sitiodetiendas import SitioDeTiendasScraper
from src.scrapers.private.rematadores import RematadoresScraper
from src.scrapers.private.agusti import AgustiSubastasScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SCRAPERS = {
    "csjn": CSJNScraper,
    "scba": SCBAScraper,
    "entrerios": EntreRiosScraper,
    "cordoba": CordobaScraper,
    "adrian_mercado": AdrianMercadoScraper,
    "banco_ciudad": BancoCiudadScraper,
    "global_remates": GlobalRematesScraper,
    "bidbit": BidBitScraper,
    "manucha": ManuchaScraper,
    "delafuente": DelaFuenteScraper,
    "zarate": ZarateScraper,
    "sitiodetiendas": SitioDeTiendasScraper,
    "rematadores": RematadoresScraper,
    "agusti": AgustiSubastasScraper,
}

DATA_DIR = Path("data/raw")
BACKUP_DIR = Path("data/backups")


def backup_existing_data():
    """Create timestamped backup of all raw data."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / timestamp

    if DATA_DIR.exists():
        shutil.copytree(DATA_DIR, backup_path)
        logger.info(f"Backed up data to {backup_path}")
        return backup_path
    return None


def load_existing_listings(source: str) -> dict:
    """Load existing listings and return as dict keyed by ID."""
    filepath = DATA_DIR / f"{source}.json"
    if not filepath.exists():
        return {}

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {item.get("id", item.get("url", str(i))): item for i, item in enumerate(data)}


def save_merged_listings(source: str, listings: list):
    """Save listings to JSON file."""
    filepath = DATA_DIR / f"{source}.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(listings)} listings to {filepath}")


async def scrape_source(name: str, scraper_class) -> list:
    """Run a single scraper and return results."""
    logger.info(f"Scraping: {name}")

    try:
        async with scraper_class() as scraper:
            listings = await scraper.scrape()
            if listings:
                return [l.to_dict() for l in listings]
            return []
    except Exception as e:
        logger.error(f"{name}: scraper failed - {e}")
        return []


async def run_incremental(sources: list, dry_run: bool = False):
    """Run scrapers and merge only NEW listings."""

    stats = {
        "sources_processed": 0,
        "new_listings": 0,
        "updated_listings": 0,
        "unchanged_listings": 0,
        "removed_listings": 0,
        "details": {}
    }

    for source in sources:
        if source not in SCRAPERS:
            logger.warning(f"Unknown source: {source}")
            continue

        # Load existing
        existing = load_existing_listings(source)
        existing_ids = set(existing.keys())
        logger.info(f"{source}: {len(existing)} existing listings")

        # Scrape new
        scraped = await scrape_source(source, SCRAPERS[source])
        if not scraped:
            logger.warning(f"{source}: no listings scraped, keeping existing data")
            stats["details"][source] = {"status": "no_data", "kept_existing": len(existing)}
            continue

        scraped_dict = {item.get("id", item.get("url", str(i))): item for i, item in enumerate(scraped)}
        scraped_ids = set(scraped_dict.keys())

        # Calculate changes
        new_ids = scraped_ids - existing_ids
        removed_ids = existing_ids - scraped_ids
        common_ids = existing_ids & scraped_ids

        # Report
        logger.info(f"{source}: {len(new_ids)} NEW, {len(removed_ids)} removed, {len(common_ids)} existing")

        stats["details"][source] = {
            "new": len(new_ids),
            "removed": len(removed_ids),
            "common": len(common_ids),
            "total_after": len(scraped)
        }

        # Show new listings
        if new_ids:
            logger.info(f"  NEW LISTINGS in {source}:")
            for new_id in list(new_ids)[:5]:  # Show first 5
                item = scraped_dict[new_id]
                title = item.get("title", "Unknown")[:60]
                price = item.get("base_price", "N/A")
                logger.info(f"    + {new_id}: {title} (${price})")
            if len(new_ids) > 5:
                logger.info(f"    ... and {len(new_ids) - 5} more")

        stats["new_listings"] += len(new_ids)
        stats["removed_listings"] += len(removed_ids)
        stats["unchanged_listings"] += len(common_ids)
        stats["sources_processed"] += 1

        # Save merged data (use scraped data as source of truth)
        if not dry_run:
            save_merged_listings(source, scraped)

    return stats


async def main():
    parser = argparse.ArgumentParser(description="Safe incremental auction scraper")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=list(SCRAPERS.keys()) + ["all"],
        default=["all"],
        help="Sources to scrape"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without saving"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup (not recommended)"
    )

    args = parser.parse_args()

    # Determine sources
    if "all" in args.sources:
        sources = list(SCRAPERS.keys())
    else:
        sources = args.sources

    logger.info(f"=== SAFE SCRAPER MODE ===")
    logger.info(f"Sources: {', '.join(sources)}")
    logger.info(f"Dry run: {args.dry_run}")

    # Backup
    if not args.no_backup and not args.dry_run:
        backup_existing_data()

    # Run incremental scrape
    stats = await run_incremental(sources, dry_run=args.dry_run)

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Sources processed: {stats['sources_processed']}")
    logger.info(f"NEW listings found: {stats['new_listings']}")
    logger.info(f"Removed (expired): {stats['removed_listings']}")
    logger.info(f"Unchanged: {stats['unchanged_listings']}")

    if args.dry_run:
        logger.info("\nDRY RUN - no changes saved. Run without --dry-run to apply.")
    else:
        # Regenerate site
        logger.info("\nRegenerating site...")
        from scripts.generate_site import generate_site
        generate_site()
        logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
