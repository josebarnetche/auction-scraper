"""Córdoba judicial auctions scraper.

Scrapes from: https://subastas.justiciacordoba.gob.ar/
API endpoint: /api/good_search/?status=active&limit=50
"""

import logging
from datetime import datetime
from typing import Optional

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class CordobaScraper(BaseScraper):
    """Scraper for Córdoba Province judicial auctions."""

    SOURCE_NAME = "cordoba"
    BASE_URL = "https://subastas.justiciacordoba.gob.ar"
    API_URL = "https://subastas.justiciacordoba.gob.ar/api/good_search/"
    RATE_LIMIT_SECONDS = 1.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings from Córdoba."""
        all_listings = []
        page_url = f"{self.API_URL}?status=active&limit=50"

        while page_url:
            logger.info(f"Fetching Córdoba auctions: {page_url}")
            data = await self.fetch_json(page_url)

            if not data:
                logger.warning("Failed to fetch Córdoba API")
                break

            results = data.get("results", [])
            for item in results:
                listing = self.parse_listing(item)
                if listing:
                    all_listings.append(listing)

            # Handle pagination
            page_url = data.get("next")
            if page_url:
                if not page_url.startswith("http"):
                    page_url = f"{self.BASE_URL}{page_url}"
                # Ensure HTTPS
                page_url = page_url.replace("http://", "https://")

        logger.info(f"Found {len(all_listings)} Córdoba listings")
        return all_listings

    def parse_listing(self, item: dict) -> Optional[AuctionListing]:
        """Parse a single listing from API response."""
        try:
            auction_id = item.get("id")
            if not auction_id:
                return None

            # Basic fields
            title = item.get("name", "").strip()
            if not title:
                return None

            # Build source URL
            uri = item.get("uri", "")
            if uri:
                source_url = f"{self.BASE_URL}{uri}"
            else:
                source_url = f"{self.BASE_URL}/product/cba/{auction_id}/"

            # Price
            base_price = float(item.get("price", 0) or 0)

            # Currency
            currency_data = item.get("currency", {})
            currency_code = currency_data.get("code", "ARS") if currency_data else "ARS"
            currency = "USD" if currency_code == "USD" else "ARS"

            # Dates
            starts_at = self._parse_date(item.get("start_date"))
            ends_at = self._parse_date(item.get("end_date"))

            # Status
            status_text = item.get("status", "").lower()
            if "finaliz" in status_text or "cerrad" in status_text:
                status = "finalized"
            elif "subasta" in status_text or "activ" in status_text:
                status = "ongoing"
            else:
                status = "published"

            # Category
            category_data = item.get("category", {})
            category_name = category_data.get("name", "").lower() if category_data else ""
            if "vehículo" in category_name or "vehiculo" in category_name or "auto" in category_name:
                category = "vehicles"
            elif "inmueble" in category_name or "propiedad" in category_name:
                category = "real_estate"
            elif "maquinaria" in category_name or "equipo" in category_name:
                category = "machinery"
            else:
                # Try to detect from title
                category = detect_category(title, "")

            # Images
            images = []
            mini_photo = item.get("mini_photo")
            if mini_photo:
                images.append(mini_photo)

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title,
                description="",  # API doesn't provide description in list
                category=category,
                base_price=base_price,
                currency=currency,
                status=status,
                starts_at=starts_at,
                ends_at=ends_at,
                location={"province": "Córdoba", "city": ""},
                images=images,
            )

        except Exception as e:
            logger.error(f"Error parsing Córdoba listing: {e}")
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO 8601 date string."""
        if not date_str:
            return None
        try:
            # Handle formats like "2026-02-23T14:00:00.900000Z" or "2026-02-16T14:00:00Z"
            date_str = date_str.replace("Z", "+00:00")
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None
