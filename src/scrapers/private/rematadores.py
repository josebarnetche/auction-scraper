"""Rematadores.com auction scraper."""

import re
import logging
import asyncio
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class RematadoresScraper(BaseScraper):
    """Scraper for Rematadores.com auctions."""

    SOURCE_NAME = "rematadores"
    BASE_URL = "https://www.rematadores.com"
    RATE_LIMIT_SECONDS = 2.0

    # Spanish month names for date parsing
    MONTHS = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings from Rematadores.com."""
        all_listings = []

        # Main listing page
        url = f"{self.BASE_URL}/rematadores/default.asp"
        logger.info(f"Scraping Rematadores.com: {url}")

        html = await self.fetch_html(url)
        if not html:
            logger.error("Failed to fetch Rematadores.com main page")
            return all_listings

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

        logger.info(f"Found {len(unique)} Rematadores listings, enriching with detail pages...")
        enriched = await self._enrich_listings(unique)

        with_images = sum(1 for l in enriched if l.images)
        logger.info(f"Rematadores: {with_images}/{len(enriched)} listings have images")
        return enriched

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse listings from the main page."""
        listings = []

        # Find all auction links with idremate parameter
        auction_links = soup.find_all("a", href=re.compile(r'idremate.*\d+', re.I))

        seen_ids = set()
        for link in auction_links:
            href = link.get("href", "")

            # Extract auction ID from URL
            id_match = re.search(r'idremate[=_](\d+)', href, re.I)
            if not id_match:
                continue

            auction_id = id_match.group(1)
            if auction_id in seen_ids:
                continue
            seen_ids.add(auction_id)

            # Get the parent column/div for context
            parent = link.find_parent(["div", "td", "article", "li"])
            listing = self._parse_auction_card(link, parent, auction_id)
            if listing:
                listings.append(listing)

        logger.info(f"Found {len(listings)} auction links on page")
        return listings

    def _parse_auction_card(self, link: Tag, parent: Optional[Tag], auction_id: str) -> Optional[AuctionListing]:
        """Parse a single auction card from the main listing page."""
        try:
            # Build the detail URL
            href = link.get("href", "")
            if href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            elif href.startswith("http"):
                source_url = href
            else:
                source_url = f"{self.BASE_URL}/rematadores/{href}"

            # Get text from the link and parent for parsing
            link_text = link.get_text(" ", strip=True)
            parent_text = parent.get_text(" ", strip=True) if parent else link_text

            # Extract title - usually the auction description
            title = self._extract_title(link_text, parent_text)
            if not title or len(title) < 5:
                return None

            # Extract date from text
            ends_at = self._extract_date(parent_text)

            # Extract location from text
            location = self._extract_location(parent_text)

            # Detect category from title
            category = detect_category(title, "")

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title,
                description="",  # Will be enriched from detail page
                category=category,
                base_price=0.0,  # Often "SIN BASE" - no minimum
                currency="ARS",
                status="published",
                ends_at=ends_at,
                location=location,
                images=[],  # Will be enriched from detail page
            )

        except Exception as e:
            logger.error(f"Error parsing auction card {auction_id}: {e}")
            return None

    def _extract_title(self, link_text: str, parent_text: str) -> str:
        """Extract and clean the auction title."""
        # Try to get a meaningful title
        # Often the link text contains the description
        title = link_text

        # Clean up the title
        # Remove common prefixes like day names, dates
        title = re.sub(r'^(LUNES|MARTES|MIÉRCOLES|MIERCOLES|JUEVES|VIERNES|SÁBADO|SABADO|DOMINGO)\s*', '', title, flags=re.I)
        title = re.sub(r'^\d{1,2}\s+(de\s+)?\w+\s*', '', title, flags=re.I)

        # If title is too short, try parent text
        if len(title) < 10 and parent_text:
            # Look for description patterns in parent
            # Usually after date/time info
            match = re.search(r'(?:hs\.?|horas?)\s*(.+)', parent_text, re.I)
            if match:
                title = match.group(1).strip()

        # Clean up extra whitespace
        title = ' '.join(title.split())

        # Truncate if too long
        if len(title) > 200:
            title = title[:197] + "..."

        return title

    def _extract_date(self, text: str) -> Optional[datetime]:
        """Extract auction date from text."""
        # Pattern: "21 de FEBRERO" or "21 FEBRERO"
        match = re.search(r'(\d{1,2})\s+(?:de\s+)?(\w+)(?:\s+(?:de\s+)?(\d{4}))?', text, re.I)
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3)) if match.group(3) else datetime.now().year

            month = self.MONTHS.get(month_name)
            if month:
                try:
                    # Extract time if present
                    time_match = re.search(r'(\d{1,2})[:.]?(\d{2})?\s*(?:hs?|horas?)', text, re.I)
                    hour = int(time_match.group(1)) if time_match else 0
                    minute = int(time_match.group(2)) if time_match and time_match.group(2) else 0

                    return datetime(year, month, day, hour, minute)
                except ValueError:
                    pass

        # Fallback: dd/mm/yyyy or dd-mm-yyyy
        match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
        if match:
            try:
                day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                return datetime(year, month, day)
            except ValueError:
                pass

        return None

    def _extract_location(self, text: str) -> dict:
        """Extract location information from text."""
        location = {"province": "", "city": ""}

        # Look for "En [LOCATION]" pattern
        match = re.search(r'\bEn\s+([^.]+?)(?:\s+(?:SÁBADO|SABADO|DOMINGO|LUNES|MARTES|MIÉRCOLES|MIERCOLES|JUEVES|VIERNES|a\s+las|\d{1,2}:\d{2})|\.|$)', text, re.I)
        if match:
            loc_text = match.group(1).strip()
            # Clean up
            loc_text = re.sub(r'\s+', ' ', loc_text)
            if len(loc_text) > 5:
                location["city"] = loc_text[:100]  # Truncate if too long

        # Check for ONLINE indicator
        if re.search(r'\bONLINE\b', text, re.I):
            location["city"] = "ONLINE"

        return location

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single listing element (required by BaseScraper)."""
        link = element.find("a", href=re.compile(r'idremate', re.I))
        if not link:
            return None

        href = link.get("href", "")
        id_match = re.search(r'idremate[=_](\d+)', href, re.I)
        if not id_match:
            return None

        return self._parse_auction_card(link, element, id_match.group(1))

    async def _fetch_detail_page(self, listing: AuctionListing) -> AuctionListing:
        """Fetch and parse the detail page for a listing."""
        try:
            html = await self.fetch_html(listing.source_url)
            if not html:
                return listing

            soup = self.parse_html(html)

            # Extract description from blockquote or main content
            description = self._extract_description(soup)

            # Extract images
            images = self._extract_images(soup)

            # Extract price if available
            base_price, currency = self._extract_price(soup)

            # Try to get better location from detail page
            location = listing.location
            if not location.get("city"):
                location = self._extract_detail_location(soup)

            # Update the listing with enriched data
            return AuctionListing(
                id=listing.id,
                source=listing.source,
                source_url=listing.source_url,
                title=listing.title,
                description=description or listing.description,
                category=listing.category,
                base_price=base_price if base_price > 0 else listing.base_price,
                currency=currency,
                status=listing.status,
                starts_at=listing.starts_at,
                ends_at=listing.ends_at,
                location=location,
                images=images if images else listing.images,
            )

        except Exception as e:
            logger.debug(f"Error fetching detail page for {listing.id}: {e}")
            return listing

    def _extract_description(self, soup) -> str:
        """Extract description from detail page."""
        # Try blockquote first (common pattern on this site)
        blockquote = soup.find("blockquote")
        if blockquote:
            desc = blockquote.get_text(" ", strip=True)
            # Clean up
            desc = ' '.join(desc.split())
            if len(desc) > 20:
                return desc[:2000]  # Truncate if too long

        # Try main content area
        main_content = soup.find(["main", "article", ".content", "#content"])
        if main_content:
            desc = main_content.get_text(" ", strip=True)
            desc = ' '.join(desc.split())
            if len(desc) > 50:
                return desc[:2000]

        return ""

    def _extract_images(self, soup) -> list[str]:
        """Extract image URLs from detail page."""
        images = []

        skip_patterns = ['logo', 'icon', 'avatar', 'share', 'social', 'facebook',
                        'twitter', 'whatsapp', 'mail', 'print', 'banner', 'ad']

        # Look for gallery images - often in links to full-size images
        for link in soup.find_all("a", href=re.compile(r'\.(jpg|jpeg|png|gif|webp)', re.I)):
            href = link.get("href", "")
            if not href:
                continue

            href_lower = href.lower()
            if any(skip in href_lower for skip in skip_patterns):
                continue

            # Make URL absolute
            if href.startswith("/"):
                href = f"{self.BASE_URL}{href}"
            elif not href.startswith("http"):
                href = f"{self.BASE_URL}/rematadores/{href}"

            if href not in images:
                images.append(href)
                if len(images) >= 10:  # Limit to 10 images
                    break

        # Also check img tags
        if len(images) < 5:
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src")
                if not src:
                    continue

                src_lower = src.lower()
                if any(skip in src_lower for skip in skip_patterns):
                    continue

                # Skip small images (likely icons)
                width = img.get("width", "")
                height = img.get("height", "")
                if width and height:
                    try:
                        if int(width) < 100 or int(height) < 100:
                            continue
                    except ValueError:
                        pass

                # Make URL absolute
                if src.startswith("/"):
                    src = f"{self.BASE_URL}{src}"
                elif not src.startswith("http"):
                    src = f"{self.BASE_URL}/rematadores/{src}"

                if src not in images:
                    images.append(src)
                    if len(images) >= 10:
                        break

        return images

    def _extract_price(self, soup) -> tuple[float, str]:
        """Extract price from detail page."""
        page_text = soup.get_text()

        # Check for "SIN BASE" (no minimum)
        if re.search(r'SIN\s+BASE', page_text, re.I):
            return 0.0, "ARS"

        # Detect currency
        currency = "ARS"
        if re.search(r'USD|U\$S|DOLAR|DÓLAR', page_text, re.I):
            currency = "USD"

        # Try to find price patterns
        # Pattern: $1.234.567 or $ 1.234.567
        match = re.search(r'\$\s*([\d.,]+)', page_text)
        if match:
            price_str = match.group(1)
            # Handle Argentine format: 1.234.567,89 -> 1234567.89
            if "," in price_str:
                price_str = price_str.replace(".", "").replace(",", ".")
            else:
                price_str = price_str.replace(".", "")

            try:
                return float(price_str), currency
            except ValueError:
                pass

        return 0.0, currency

    def _extract_detail_location(self, soup) -> dict:
        """Extract location from detail page."""
        location = {"province": "", "city": ""}

        page_text = soup.get_text()

        # Look for "En [LOCATION]" pattern
        match = re.search(r'\bEn\s+([A-ZÁÉÍÓÚÑ][^.]+?)(?:\s+[A-ZÁÉÍÓÚÑ]+\s+\d|\.|a\s+las|$)', page_text)
        if match:
            loc_text = match.group(1).strip()
            loc_text = ' '.join(loc_text.split())
            if 5 < len(loc_text) < 150:
                location["city"] = loc_text

        # Check for ONLINE
        if re.search(r'\bONLINE\b', page_text, re.I):
            location["city"] = "ONLINE"

        return location

    async def _enrich_listings(self, listings: list[AuctionListing]) -> list[AuctionListing]:
        """Fetch detail pages to enrich listings."""
        enriched = []

        for listing in listings:
            await asyncio.sleep(self.RATE_LIMIT_SECONDS)
            enriched_listing = await self._fetch_detail_page(listing)
            enriched.append(enriched_listing)

        return enriched
