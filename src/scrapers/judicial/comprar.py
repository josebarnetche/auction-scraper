"""COMPR.AR government auction scraper."""

import re
import logging
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class ComprarScraper(BaseScraper):
    """Scraper for COMPR.AR government auctions."""

    SOURCE_NAME = "comprar"
    BASE_URL = "https://comprar.gob.ar"
    LISTINGS_URL = "https://comprar.gob.ar/SubastaPublica.aspx"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings from COMPR.AR."""
        all_listings = []

        logger.info(f"Scraping COMPR.AR auctions: {self.LISTINGS_URL}")

        html = await self.fetch_html(self.LISTINGS_URL)
        if not html:
            logger.warning(f"Failed to fetch {self.LISTINGS_URL}")
            return all_listings

        soup = self.parse_html(html)
        listings = self._parse_listings_page(soup)
        all_listings.extend(listings)

        logger.info(f"Found {len(all_listings)} COMPR.AR listings")
        return all_listings

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse the listings page."""
        listings = []

        # COMPR.AR uses ASP.NET GridView or similar
        # Look for table rows or list items
        rows = soup.select("table.grid tr, .subasta-row, .auction-item")

        if not rows:
            # Try finding any structured content
            rows = soup.select("[class*='subasta'], [class*='auction']")

        for row in rows:
            # Skip header rows
            if row.find("th"):
                continue

            listing = self.parse_listing(row)
            if listing:
                listings.append(listing)

        return listings

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single auction row/element."""
        try:
            # Get all text cells
            cells = element.find_all(["td", "div"])
            if len(cells) < 2:
                return None

            # Find link
            link = element.find("a", href=True)
            href = link.get("href", "") if link else ""

            # Extract ID from URL or generate from content
            id_match = re.search(r"id[=:](\d+)", href, re.I)
            if id_match:
                auction_id = id_match.group(1)
            else:
                # Use hash of content
                auction_id = str(hash(element.get_text()[:100]) % 10**8)

            # Build source URL
            if href:
                if href.startswith("http"):
                    source_url = href
                else:
                    source_url = f"{self.BASE_URL}/{href.lstrip('/')}"
            else:
                source_url = self.LISTINGS_URL

            # Extract title from first meaningful cell
            title = ""
            for cell in cells:
                text = cell.get_text(strip=True)
                if len(text) > 10:
                    title = text
                    break

            if not title:
                return None

            # Extract description
            description = " ".join(c.get_text(strip=True) for c in cells[1:3])

            # Extract price
            full_text = element.get_text()
            base_price, currency = self._parse_price(full_text)

            # Detect category
            category = detect_category(title, description)

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title[:200],  # Truncate long titles
                description=description[:500],
                category=category,
                base_price=base_price,
                currency=currency,
                status=status,
                location={"province": "", "city": ""},
                images=[],
                extra={"government": True}
            )

        except Exception as e:
            logger.error(f"Error parsing COMPR.AR listing: {e}")
            return None

    def _parse_price(self, text: str) -> tuple[float, str]:
        """Parse price from text."""
        currency = "ARS"
        if "USD" in text.upper() or "U$S" in text.upper():
            currency = "USD"

        # Find price patterns
        patterns = [
            r"\$\s*([\d.,]+)",
            r"([\d.,]+)\s*(?:pesos|ARS)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                price_str = match.group(1)
                # Handle Argentine format
                if "," in price_str:
                    price_str = price_str.replace(".", "").replace(",", ".")
                else:
                    price_str = price_str.replace(".", "")
                try:
                    return float(price_str), currency
                except ValueError:
                    continue

        return 0.0, currency
