"""Adrián Mercado auction scraper."""

import re
import logging
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class AdrianMercadoScraper(BaseScraper):
    """Scraper for Adrián Mercado private auctions."""

    SOURCE_NAME = "adrian_mercado"
    BASE_URL = "https://www.adrianmercado.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings."""
        all_listings = []

        # Main auction categories
        categories = [
            "/subastas",
            "/subastas/vehiculos",
            "/subastas/inmuebles",
            "/subastas/maquinarias",
        ]

        for path in categories:
            url = f"{self.BASE_URL}{path}"
            logger.info(f"Scraping Adrián Mercado: {url}")

            html = await self.fetch_html(url)
            if not html:
                continue

            soup = self.parse_html(html)
            listings = self._parse_listings_page(soup)
            all_listings.extend(listings)

        # Deduplicate by ID
        seen = set()
        unique = []
        for listing in all_listings:
            if listing.id not in seen:
                seen.add(listing.id)
                unique.append(listing)

        logger.info(f"Found {len(unique)} Adrián Mercado listings")
        return unique

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse listings from page."""
        listings = []

        # Look for auction cards
        cards = soup.select(".auction-card, .product-card, .item, [class*='subasta']")

        if not cards:
            cards = soup.select("article, .card")

        for card in cards:
            listing = self.parse_listing(card)
            if listing:
                listings.append(listing)

        return listings

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single auction card."""
        try:
            link = element.find("a", href=True)
            if not link:
                return None

            href = link.get("href", "")
            id_match = re.search(r"[/-](\d+)", href)
            auction_id = id_match.group(1) if id_match else str(hash(href) % 10**8)

            if href.startswith("http"):
                source_url = href
            elif href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            else:
                source_url = f"{self.BASE_URL}/{href}"

            # Title
            title_elem = element.find(["h2", "h3", "h4", ".title", ".product-name"])
            title = title_elem.get_text(strip=True) if title_elem else ""

            if not title:
                title = link.get_text(strip=True)

            if not title or len(title) < 3:
                return None

            # Description
            desc_elem = element.find([".description", ".excerpt", "p"])
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Price
            price_elem = element.find(class_=re.compile(r"price|precio", re.I))
            price_text = price_elem.get_text() if price_elem else element.get_text()
            base_price, currency = self._parse_price(price_text)

            # Images
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
            logger.error(f"Error parsing Adrián Mercado listing: {e}")
            return None

    def _parse_price(self, text: str) -> tuple[float, str]:
        """Parse price from text."""
        currency = "ARS"
        text_upper = text.upper()
        if "USD" in text_upper or "U$S" in text_upper or "DOLAR" in text_upper:
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
