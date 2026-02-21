"""Banco Ciudad auction scraper."""

import re
import logging
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class BancoCiudadScraper(BaseScraper):
    """Scraper for Banco Ciudad auctions."""

    SOURCE_NAME = "banco_ciudad"
    BASE_URL = "https://subastas.bancociudad.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings."""
        all_listings = []

        url = self.BASE_URL
        logger.info(f"Scraping Banco Ciudad: {url}")

        html = await self.fetch_html(url)
        if not html:
            logger.warning(f"Failed to fetch {url}")
            return all_listings

        soup = self.parse_html(html)
        listings = self._parse_listings_page(soup)
        all_listings.extend(listings)

        logger.info(f"Found {len(all_listings)} Banco Ciudad listings")
        return all_listings

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse listings from page."""
        listings = []

        # Look for property/auction cards
        cards = soup.select(".property, .auction, .card, [class*='inmueble']")

        if not cards:
            cards = soup.select("article, .item, .listing")

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

            # Title
            title_elem = element.find(["h2", "h3", "h4", ".title"])
            title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

            if not title or len(title) < 3:
                return None

            # Description
            desc_elem = element.find([".description", ".address", "p"])
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Price
            price_text = element.get_text()
            base_price, currency = self._parse_price(price_text)

            # Location - Banco Ciudad mostly operates in Buenos Aires
            location = {"province": "CABA", "city": "Buenos Aires"}

            # Extract neighborhood if available
            for text in element.stripped_strings:
                neighborhoods = ["Palermo", "Belgrano", "Recoleta", "Caballito", "Flores"]
                for barrio in neighborhoods:
                    if barrio.lower() in text.lower():
                        location["city"] = barrio
                        break

            # Images
            images = []
            img = element.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src:
                    if src.startswith("/"):
                        src = f"{self.BASE_URL}{src}"
                    images.append(src)

            # Banco Ciudad mostly auctions real estate
            category = detect_category(title, description)
            if category == "other":
                category = "real_estate"

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
                location=location,
                images=images,
            )

        except Exception as e:
            logger.error(f"Error parsing Banco Ciudad listing: {e}")
            return None

    def _parse_price(self, text: str) -> tuple[float, str]:
        """Parse price from text."""
        currency = "USD"  # Banco Ciudad typically prices in USD
        text_upper = text.upper()
        if "ARS" in text_upper or "PESOS" in text_upper:
            currency = "ARS"

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
