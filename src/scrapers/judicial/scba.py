"""SCBA (Suprema Corte de Buenos Aires) auction scraper."""

import re
import logging
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class SCBAScraper(BaseScraper):
    """Scraper for Buenos Aires Province judicial auctions."""

    SOURCE_NAME = "scba"
    BASE_URL = "https://subastas.scba.gov.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings from SCBA."""
        all_listings = []

        # Main listings page
        url = f"{self.BASE_URL}/subastas"
        logger.info(f"Scraping SCBA auctions: {url}")

        html = await self.fetch_html(url)
        if not html:
            logger.warning(f"Failed to fetch {url}")
            return all_listings

        soup = self.parse_html(html)
        listings = self._parse_listings_page(soup)
        all_listings.extend(listings)

        logger.info(f"Found {len(all_listings)} SCBA listings")
        return all_listings

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse the listings page."""
        listings = []

        # Look for auction cards
        cards = soup.select(".subasta, .auction-item, .card, [class*='subasta']")

        if not cards:
            # Try table rows
            rows = soup.select("table tr, .list-item")
            cards = rows

        for card in cards:
            listing = self.parse_listing(card)
            if listing:
                listings.append(listing)

        return listings

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single auction element."""
        try:
            # Find link to detail page
            link = element.find("a", href=True)
            if not link:
                return None

            href = link.get("href", "")
            if not href:
                return None

            # Extract auction ID
            id_match = re.search(r"(\d+)", href)
            if not id_match:
                return None

            auction_id = id_match.group(1)

            # Build source URL
            if href.startswith("http"):
                source_url = href
            elif href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            else:
                source_url = f"{self.BASE_URL}/{href}"

            # Extract title
            title_elem = element.find(["h2", "h3", "h4", "strong", ".title"])
            title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

            if not title or len(title) < 5:
                return None

            # Extract description
            desc_elem = element.find(["p", ".description"])
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Extract price
            text = element.get_text()
            base_price, currency = self._parse_price(text)

            # Detect category
            category = detect_category(title, description)

            # Determine status from text
            text_lower = text.lower()
            if "finaliz" in text_lower:
                status = "finalized"
            elif "curso" in text_lower or "activ" in text_lower:
                status = "ongoing"
            else:
                status = "published"

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title,
                description=description,
                category=category,
                base_price=base_price,
                currency=currency,
                status=status,
                location={"province": "Buenos Aires", "city": ""},
                images=self._parse_images(element),
            )

        except Exception as e:
            logger.error(f"Error parsing SCBA listing: {e}")
            return None

    def _parse_price(self, text: str) -> tuple[float, str]:
        """Parse price from text."""
        currency = "ARS"
        if "USD" in text.upper() or "U$S" in text.upper():
            currency = "USD"

        # Find price pattern
        price_match = re.search(r"[\$]?\s*([\d.,]+)", text)
        if not price_match:
            return 0.0, currency

        price_str = price_match.group(1)

        # Handle Argentine number format
        if "," in price_str:
            price_str = price_str.replace(".", "").replace(",", ".")
        else:
            price_str = price_str.replace(".", "")

        try:
            return float(price_str), currency
        except ValueError:
            return 0.0, currency

    def _parse_images(self, element: Tag) -> list[str]:
        """Extract image URLs."""
        images = []
        for img in element.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src:
                if src.startswith("/"):
                    src = f"{self.BASE_URL}{src}"
                images.append(src)
        return images
