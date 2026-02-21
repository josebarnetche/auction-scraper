"""De la Fuente Subastas scraper - Córdoba based auction house."""

import re
import logging
from datetime import datetime
from typing import Optional

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class DelaFuenteScraper(BaseScraper):
    """Scraper for De la Fuente Subastas (Córdoba)."""

    SOURCE_NAME = "delafuente"
    BASE_URL = "https://delafuentesubastas.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings."""
        all_listings = []

        # Main pages to check
        pages = [
            "/",
            "/remates",
            "/subastas",
            "/proximos-remates",
        ]

        for path in pages:
            url = f"{self.BASE_URL}{path}"
            logger.info(f"Scraping De la Fuente: {url}")

            html = await self.fetch_html(url)
            if not html:
                continue

            soup = self.parse_html(html)
            listings = self._parse_listings_page(soup)
            all_listings.extend(listings)

        # Also try to enumerate recent IDs
        # Pattern: /remate/[ID]
        known_ids = set()
        for listing in all_listings:
            match = re.search(r'/remate/(\d+)', listing.source_url)
            if match:
                known_ids.add(int(match.group(1)))

        if known_ids:
            max_id = max(known_ids)
            # Try nearby IDs
            for auction_id in range(max(1, max_id - 20), max_id + 10):
                if auction_id in known_ids:
                    continue
                listing = await self._fetch_detail(auction_id)
                if listing:
                    all_listings.append(listing)

        # Deduplicate
        seen = set()
        unique = []
        for listing in all_listings:
            if listing.id not in seen:
                seen.add(listing.id)
                unique.append(listing)

        logger.info(f"Found {len(unique)} De la Fuente listings")
        return unique

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse listings from page."""
        listings = []

        # Find auction links - pattern: /remate/[id]
        auction_links = soup.find_all("a", href=re.compile(r'/remate/\d+'))

        seen_urls = set()
        for link in auction_links:
            href = link.get("href", "")
            if href in seen_urls:
                continue
            seen_urls.add(href)

            listing = self._parse_auction_link(link, href)
            if listing:
                listings.append(listing)

        return listings

    def _parse_auction_link(self, link, href: str) -> Optional[AuctionListing]:
        """Parse auction from a link element."""
        try:
            id_match = re.search(r'/remate/(\d+)', href)
            if not id_match:
                return None
            auction_id = id_match.group(1)

            if href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            else:
                source_url = href

            # Get title
            title = link.get_text(strip=True)
            if not title or len(title) < 3:
                parent = link.find_parent()
                if parent:
                    title = parent.get_text(strip=True)[:100]

            if not title:
                title = f"Remate #{auction_id}"

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
            logger.error(f"Error parsing De la Fuente link: {e}")
            return None

    async def _fetch_detail(self, auction_id: int) -> Optional[AuctionListing]:
        """Fetch detail page to extract full info."""
        url = f"{self.BASE_URL}/remate/{auction_id}"
        html = await self.fetch_html(url)
        if not html:
            return None

        # Check if it's a valid auction page
        if "remate" not in html.lower() and "subasta" not in html.lower():
            return None

        soup = self.parse_html(html)
        page_text = soup.get_text()

        # Extract title
        title_elem = soup.find(["h1", "h2"])
        title = title_elem.get_text(strip=True) if title_elem else f"Remate #{auction_id}"

        if len(title) < 5:
            return None

        # Extract price
        base_price = 0.0
        currency = "ARS"
        price_patterns = [
            r'(?:base|precio)[:\s]*\$?\s*([\d.,]+)',
            r'(?:USD|U\$S)\s*([\d.,]+)',
            r'\$\s*([\d.,]+)',
        ]
        for pattern in price_patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                price_str = match.group(1).replace('.', '').replace(',', '.')
                try:
                    base_price = float(price_str)
                    break
                except ValueError:
                    continue

        if "USD" in page_text or "dólar" in page_text.lower():
            currency = "USD"

        # Extract images
        images = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and not any(x in src.lower() for x in ['logo', 'icon', 'avatar']):
                if src.startswith("/"):
                    src = f"{self.BASE_URL}{src}"
                if src not in images:
                    images.append(src)
                if len(images) >= 5:
                    break

        category = detect_category(title, page_text[:500])

        return AuctionListing(
            id=self.generate_id(auction_id),
            source=self.SOURCE_NAME,
            source_url=url,
            title=title,
            description=page_text[:300] if page_text else "",
            category=category,
            base_price=base_price,
            currency=currency,
            status="published",
            images=images,
        )

    def parse_listing(self, element, status: str = "published") -> Optional[AuctionListing]:
        """Required by base class."""
        return None
