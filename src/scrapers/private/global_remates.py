"""Global Remates auction scraper."""

import re
import logging
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class GlobalRematesScraper(BaseScraper):
    """Scraper for Global Remates auctions."""

    SOURCE_NAME = "global_remates"
    BASE_URL = "https://www.globalremates.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings."""
        all_listings = []

        # Try common paths
        paths = ["/", "/remates", "/subastas", "/proximos-remates"]

        for path in paths:
            url = f"{self.BASE_URL}{path}"
            logger.info(f"Scraping Global Remates: {url}")

            html = await self.fetch_html(url)
            if not html:
                continue

            soup = self.parse_html(html)
            listings = self._parse_listings_page(soup)
            all_listings.extend(listings)

        # Deduplicate
        seen = set()
        unique = []
        for listing in all_listings:
            if listing.id not in seen:
                seen.add(listing.id)
                unique.append(listing)

        logger.info(f"Found {len(unique)} Global Remates listings")
        return unique

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse listings from page."""
        listings = []

        cards = soup.select(".remate, .auction, .card, .item, article")

        for card in cards:
            listing = self.parse_listing(card)
            if listing:
                listings.append(listing)

        return listings

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single auction element."""
        try:
            link = element.find("a", href=True)
            if not link:
                return None

            href = link.get("href", "")
            id_match = re.search(r"(\d+)", href)
            auction_id = id_match.group(1) if id_match else str(hash(href) % 10**8)

            if href.startswith("http"):
                source_url = href
            elif href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            else:
                source_url = f"{self.BASE_URL}/{href}"

            title_elem = element.find(["h2", "h3", "h4", ".title"])
            title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

            if not title or len(title) < 3:
                return None

            desc_elem = element.find([".description", "p"])
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            price_text = element.get_text()
            base_price, currency = self._parse_price(price_text)

            images = []
            img = element.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src:
                    if src.startswith("/"):
                        src = f"{self.BASE_URL}{src}"
                    images.append(src)

            category = detect_category(title, description)

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
                images=images,
            )

        except Exception as e:
            logger.error(f"Error parsing Global Remates listing: {e}")
            return None

    def _parse_price(self, text: str) -> tuple[float, str]:
        """Parse price from text."""
        currency = "ARS"
        if "USD" in text.upper() or "U$S" in text.upper():
            currency = "USD"

        match = re.search(r"[\$]?\s*([\d.,]+)", text)
        if not match:
            return 0.0, currency

        price_str = match.group(1)
        if "," in price_str:
            price_str = price_str.replace(".", "").replace(",", ".")
        else:
            price_str = price_str.replace(".", "")

        try:
            return float(price_str), currency
        except ValueError:
            return 0.0, currency
