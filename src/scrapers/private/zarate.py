"""Remates Zárate scraper - Industrial equipment and vehicles."""

import re
import logging
from datetime import datetime
from typing import Optional

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class ZarateScraper(BaseScraper):
    """Scraper for Remates Zárate (70+ years of auctions)."""

    SOURCE_NAME = "zarate"
    BASE_URL = "https://remateszarate.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings."""
        all_listings = []

        pages = [
            "/",
            "/remates",
            "/subastas",
            "/proximos",
        ]

        for path in pages:
            url = f"{self.BASE_URL}{path}"
            logger.info(f"Scraping Zárate: {url}")

            html = await self.fetch_html(url)
            if not html:
                continue

            soup = self.parse_html(html)
            listings = self._parse_page(soup)
            all_listings.extend(listings)

        # Deduplicate
        seen = set()
        unique = []
        for listing in all_listings:
            if listing.id not in seen:
                seen.add(listing.id)
                unique.append(listing)

        logger.info(f"Found {len(unique)} Zárate listings")
        return unique

    def _parse_page(self, soup) -> list[AuctionListing]:
        """Parse listings from page."""
        listings = []

        # Look for auction links
        links = soup.find_all("a", href=True)
        seen = set()

        for link in links:
            href = link.get("href", "")

            # Skip non-auction links
            if not href or href == "#" or href == "/":
                continue
            if any(x in href.lower() for x in ['mailto:', 'tel:', 'javascript:', 'facebook', 'instagram', 'youtube']):
                continue

            # Look for auction-like URLs
            if re.search(r'/(remate|subasta|lote|producto|item)[s]?[/-]', href, re.I) or \
               re.search(r'/\d+/?$', href):
                if href in seen:
                    continue
                seen.add(href)

                listing = self._parse_link(link, href)
                if listing:
                    listings.append(listing)

        return listings

    def _parse_link(self, link, href: str) -> Optional[AuctionListing]:
        """Parse auction from link."""
        try:
            # Extract ID
            id_match = re.search(r'[/-](\d+)', href)
            auction_id = id_match.group(1) if id_match else str(hash(href) % 10**8)

            # Build URL
            if href.startswith("http"):
                source_url = href
            elif href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            else:
                source_url = f"{self.BASE_URL}/{href}"

            # Get title
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                parent = link.find_parent()
                if parent:
                    title = parent.get_text(strip=True)[:100]

            if not title or len(title) < 5:
                return None

            # Image
            images = []
            img = link.find("img")
            if not img:
                parent = link.find_parent()
                if parent:
                    img = parent.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src:
                    if src.startswith("/"):
                        src = f"{self.BASE_URL}{src}"
                    elif not src.startswith("http"):
                        src = f"{self.BASE_URL}/{src}"
                    images.append(src)

            category = detect_category(title, "")

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title,
                description="",
                category=category,
                base_price=0.0,
                currency="ARS",
                status="published",
                images=images,
            )
        except Exception as e:
            logger.error(f"Error parsing Zárate link: {e}")
            return None

    def parse_listing(self, element, status: str = "published") -> Optional[AuctionListing]:
        """Required by base class."""
        return None
