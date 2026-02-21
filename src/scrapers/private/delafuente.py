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

        # Main page
        url = self.BASE_URL
        logger.info(f"Scraping De la Fuente: {url}")

        html = await self.fetch_html(url)
        if html:
            soup = self.parse_html(html)
            listings = self._parse_listings_page(soup, html)
            all_listings.extend(listings)

        # Subastas page
        url2 = f"{self.BASE_URL}/subastas"
        html2 = await self.fetch_html(url2)
        if html2:
            soup2 = self.parse_html(html2)
            listings2 = self._parse_listings_page(soup2, html2)
            all_listings.extend(listings2)

        # Deduplicate
        seen = set()
        unique = []
        for listing in all_listings:
            if listing.id not in seen:
                seen.add(listing.id)
                unique.append(listing)

        logger.info(f"Found {len(unique)} De la Fuente listings")
        return unique

    def _parse_listings_page(self, soup, html: str) -> list[AuctionListing]:
        """Parse listings from page."""
        listings = []

        # Find auction links - pattern: /remate/[id]
        # Only accept links that stay on this domain
        auction_links = soup.find_all("a", href=re.compile(r'/remate/\d+'))

        seen_ids = set()
        for link in auction_links:
            href = link.get("href", "")

            # Skip external domains
            if "rural.com" in href or "rural-" in href:
                continue

            # Extract ID
            id_match = re.search(r'/remate/(\d+)', href)
            if not id_match:
                continue

            auction_id = id_match.group(1)
            if auction_id in seen_ids:
                continue
            seen_ids.add(auction_id)

            listing = self._parse_auction_card(link, auction_id)
            if listing:
                listings.append(listing)

        return listings

    def _parse_auction_card(self, link, auction_id: str) -> Optional[AuctionListing]:
        """Parse auction from a link/card element."""
        try:
            source_url = f"{self.BASE_URL}/remate/{auction_id}"

            # Find parent container (card/article)
            parent = link.find_parent(["div", "article", "li"])
            if not parent:
                parent = link.find_parent()

            # Extract title - look for heading elements
            title = ""
            if parent:
                # Look for actual title in headings
                title_elem = parent.find(["h1", "h2", "h3", "h4", "h5"])
                if title_elem:
                    title = title_elem.get_text(strip=True)

                # If no heading, try to find meaningful text
                if not title or len(title) < 5:
                    # Get text but clean it
                    for text_elem in parent.find_all(["strong", "b", "span"]):
                        text = text_elem.get_text(strip=True)
                        # Skip dates, locations, etc
                        if len(text) > 10 and not text.startswith("Fecha") and not text.startswith("Ubicación"):
                            title = text
                            break

            # Clean up title - remove common noise
            if title:
                # Remove "SUBASTA DD/MM/YYYY HH:MMhs" pattern
                title = re.sub(r'^SUBASTA\s+\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*HS?\s*', '', title, flags=re.I)
                # Remove date info
                title = re.sub(r'Fecha:.*?(?=Categoría|Ubicación|$)', '', title, flags=re.I)
                # Remove category info
                title = re.sub(r'Categoría:.*?(?=Ubicación|$)', '', title, flags=re.I)
                # Remove location info
                title = re.sub(r'Ubicación:.*', '', title, flags=re.I)
                # Clean up whitespace
                title = re.sub(r'\s+', ' ', title).strip()

            # If still no good title, create descriptive one
            if not title or len(title) < 5:
                title = f"Subasta De la Fuente #{auction_id}"

            # Extract image
            images = []
            if parent:
                img = parent.find("img")
                if img:
                    src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                    if src:
                        # Accept thumbs2.rural-ftp.com images (they host the actual photos)
                        if src.startswith("//"):
                            src = "https:" + src
                        elif src.startswith("/"):
                            src = f"{self.BASE_URL}{src}"
                        # Skip logos/icons
                        if not any(x in src.lower() for x in ['logo', 'icon', 'favicon']):
                            images.append(src)

            # Extract date if available
            date_text = ""
            if parent:
                date_match = re.search(r'(\d{1,2})\s+de\s+(\w+),?\s*(\d{1,2}:\d{2})', parent.get_text(), re.I)
                if date_match:
                    date_text = date_match.group(0)

            # Extract category from text
            category = "other"
            text_lower = parent.get_text().lower() if parent else ""
            if "activo" in text_lower or "inmueble" in text_lower:
                category = "real_estate"
            elif "vehículo" in text_lower or "auto" in text_lower:
                category = "vehicles"
            elif "maquinaria" in text_lower or "equipo" in text_lower:
                category = "machinery"

            description = f"Subasta en Córdoba. {date_text}" if date_text else "Subasta en Córdoba."

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title,
                description=description,
                category=category,
                base_price=0.0,
                currency="ARS",
                status="published",
                location={"province": "Córdoba", "city": "Córdoba"},
                images=images,
            )
        except Exception as e:
            logger.error(f"Error parsing De la Fuente card: {e}")
            return None

    def parse_listing(self, element, status: str = "published") -> Optional[AuctionListing]:
        """Required by base class."""
        return None
