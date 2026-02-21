"""COMPR.AR government auction scraper."""

import re
import ssl
import logging
import aiohttp
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

    async def __aenter__(self):
        """Create session with SSL verification disabled for this site."""
        if self._session is None:
            # Create SSL context that doesn't verify
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(ssl=ssl_context)
            timeout = aiohttp.ClientTimeout(total=30)

            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
                }
            )
        return self

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings from COMPR.AR."""
        all_listings = []

        logger.info(f"Scraping COMPR.AR auctions: {self.LISTINGS_URL}")

        html = await self.fetch_html(self.LISTINGS_URL)
        if not html:
            # Try alternative URLs
            alt_urls = [
                "https://comprar.gob.ar/SubastasPublicas.aspx",
                "https://comprar.gob.ar/Subastas",
                "https://comprar.gob.ar/",
            ]
            for url in alt_urls:
                html = await self.fetch_html(url)
                if html:
                    logger.info(f"Found COMPR.AR content at {url}")
                    break

        if not html:
            logger.warning("Failed to fetch COMPR.AR")
            return all_listings

        soup = self.parse_html(html)
        listings = self._parse_listings_page(soup)
        all_listings.extend(listings)

        logger.info(f"Found {len(all_listings)} COMPR.AR listings")
        return all_listings

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse the listings page."""
        listings = []

        # COMPR.AR uses ASP.NET - look for various patterns
        # Try GridView rows
        rows = soup.select("table tr")
        for row in rows:
            if row.find("th"):  # Skip header
                continue
            listing = self._parse_table_row(row)
            if listing:
                listings.append(listing)

        # Try finding auction links directly
        auction_links = soup.find_all("a", href=re.compile(r'(subasta|auction|detalle)', re.I))
        seen_urls = set(l.source_url for l in listings)

        for link in auction_links:
            href = link.get("href", "")
            if not href:
                continue

            # Build full URL
            if href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            elif href.startswith("http"):
                source_url = href
            else:
                source_url = f"{self.BASE_URL}/{href}"

            if source_url in seen_urls:
                continue
            seen_urls.add(source_url)

            listing = self._parse_link(link, source_url)
            if listing:
                listings.append(listing)

        # Look for div-based listings
        cards = soup.select("[class*='subasta'], [class*='auction'], .card, .item, article")
        for card in cards:
            listing = self.parse_listing(card)
            if listing and listing.source_url not in seen_urls:
                seen_urls.add(listing.source_url)
                listings.append(listing)

        return listings

    def _parse_table_row(self, row) -> Optional[AuctionListing]:
        """Parse a table row."""
        try:
            cells = row.find_all("td")
            if len(cells) < 2:
                return None

            # Find link
            link = row.find("a", href=True)
            href = link.get("href", "") if link else ""

            # Extract ID
            id_match = re.search(r'id[=:](\d+)', href, re.I)
            if id_match:
                auction_id = id_match.group(1)
            else:
                text_content = row.get_text()
                auction_id = str(hash(text_content[:100]) % 10**8)

            # Build URL
            if href:
                if href.startswith("http"):
                    source_url = href
                else:
                    source_url = f"{self.BASE_URL}/{href.lstrip('/')}"
            else:
                source_url = self.LISTINGS_URL

            # Extract title from cells
            title = ""
            for cell in cells:
                text = cell.get_text(strip=True)
                if len(text) > 10 and not text.isdigit():
                    title = text
                    break

            if not title or len(title) < 5:
                return None

            # Extract description
            description = " ".join(c.get_text(strip=True) for c in cells[1:3] if c.get_text(strip=True))

            # Extract price
            full_text = row.get_text()
            base_price, currency = self._parse_price(full_text)

            category = detect_category(title, description)

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title[:200],
                description=description[:500],
                category=category,
                base_price=base_price,
                currency=currency,
                status="published",
                location={"province": "", "city": ""},
                images=[],
                extra={"government": True}
            )

        except Exception as e:
            logger.debug(f"Error parsing COMPR.AR row: {e}")
            return None

    def _parse_link(self, link, source_url: str) -> Optional[AuctionListing]:
        """Parse an auction link."""
        try:
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                parent = link.find_parent()
                if parent:
                    title = parent.get_text(strip=True)[:150]

            if not title or len(title) < 5:
                return None

            id_match = re.search(r'id[=:](\d+)', source_url, re.I)
            auction_id = id_match.group(1) if id_match else str(hash(source_url) % 10**8)

            category = detect_category(title, "")

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title[:200],
                description="",
                category=category,
                base_price=0.0,
                currency="ARS",
                status="published",
                location={"province": "", "city": ""},
                images=[],
                extra={"government": True}
            )
        except Exception as e:
            logger.debug(f"Error parsing COMPR.AR link: {e}")
            return None

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single auction row/element."""
        try:
            link = element.find("a", href=True)
            if not link:
                return None

            href = link.get("href", "")

            # Build URL
            if href.startswith("http"):
                source_url = href
            elif href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            else:
                source_url = f"{self.BASE_URL}/{href}"

            # Extract ID
            id_match = re.search(r'id[=:](\d+)', href, re.I)
            auction_id = id_match.group(1) if id_match else str(hash(href) % 10**8)

            # Extract title
            title_elem = element.find(["h2", "h3", "h4", "strong", ".title"])
            title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

            if not title or len(title) < 5:
                return None

            # Description
            desc_elem = element.find(["p", ".description"])
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Price
            full_text = element.get_text()
            base_price, currency = self._parse_price(full_text)

            category = detect_category(title, description)

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title[:200],
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
            logger.debug(f"Error parsing COMPR.AR listing: {e}")
            return None

    def _parse_price(self, text: str) -> tuple[float, str]:
        """Parse price from text."""
        currency = "ARS"
        if "USD" in text.upper() or "U$S" in text.upper():
            currency = "USD"

        patterns = [
            r"\$\s*([\d.,]+)",
            r"([\d.,]+)\s*(?:pesos|ARS)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                price_str = match.group(1)
                if "," in price_str:
                    price_str = price_str.replace(".", "").replace(",", ".")
                else:
                    price_str = price_str.replace(".", "")
                try:
                    return float(price_str), currency
                except ValueError:
                    continue

        return 0.0, currency
