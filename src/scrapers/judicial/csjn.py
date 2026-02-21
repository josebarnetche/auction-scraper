"""CSJN (Corte Suprema de Justicia de la Nación) auction scraper."""

import re
import logging
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup, Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class CSJNScraper(BaseScraper):
    """Scraper for CSJN judicial auctions.

    The CSJN website uses ASP.NET MVC with these patterns:
    - Home page shows sample auctions
    - /Auctions/Details/{id} for individual auction pages
    - Authentication required for full search
    """

    SOURCE_NAME = "csjn"
    BASE_URL = "https://subastaselectronicasjudiciales.csjn.gov.ar"
    RATE_LIMIT_SECONDS = 1.5

    # Max auction ID to enumerate beyond known IDs
    MAX_EXTRA_IDS = 10

    async def scrape(self) -> list[AuctionListing]:
        """Scrape auctions by enumerating detail pages."""
        all_listings = []
        known_ids = set()

        # First, get IDs from home page
        logger.info(f"Scraping CSJN home page: {self.BASE_URL}/")
        html = await self.fetch_html(f"{self.BASE_URL}/")

        if html:
            soup = self.parse_html(html)
            # Extract auction IDs from home page links
            home_ids = self._extract_auction_ids(soup)
            known_ids.update(home_ids)
            logger.info(f"Found {len(home_ids)} auction IDs on home page")

        # Add some IDs around the known ones to catch new auctions
        if known_ids:
            max_known = max(known_ids)
            min_known = min(known_ids)
            # Try a range from min to max + a few extra
            known_ids.update(range(min_known, max_known + self.MAX_EXTRA_IDS))

        # Scrape each auction detail page
        scraped_count = 0
        for auction_id in sorted(known_ids):
            url = f"{self.BASE_URL}/Auctions/Details/{auction_id}"

            html = await self.fetch_html(url)
            if not html:
                continue

            # Check if it's a valid auction page
            if "Subasta" not in html and "subasta" not in html.lower():
                continue

            soup = self.parse_html(html)
            listing = self._parse_detail_page(soup, auction_id)

            if listing:
                all_listings.append(listing)
                scraped_count += 1
                logger.debug(f"Scraped auction {auction_id}: {listing.title[:50]}")

        logger.info(f"CSJN: Found {scraped_count} valid auctions")
        return all_listings

    def _extract_auction_ids(self, soup: BeautifulSoup) -> set[int]:
        """Extract auction IDs from page links."""
        ids = set()

        # Find all links to auction details
        links = soup.find_all('a', href=re.compile(r'/Auctions/Details/(\d+)', re.I))
        for link in links:
            match = re.search(r'/Auctions/Details/(\d+)', link.get('href', ''), re.I)
            if match:
                ids.add(int(match.group(1)))

        return ids

    def _parse_detail_page(self, soup: BeautifulSoup, auction_id: int) -> Optional[AuctionListing]:
        """Parse a single auction detail page."""
        try:
            # Extract from hidden form fields (most reliable)
            hidden_fields = {}
            for inp in soup.find_all('input', type='hidden'):
                name = inp.get('name', '')
                value = inp.get('value', '')
                if name and value:
                    hidden_fields[name] = value

            # Get title from h1 or page title
            title = ""
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
            if not title:
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text(strip=True)
            if not title:
                title = f"Subasta CSJN #{auction_id}"

            # Clean up title
            title = re.sub(r'\s+', ' ', title).strip()

            # Get description from main content
            description = ""
            content_div = soup.find('div', class_=re.compile(r'content|detail|description', re.I))
            if content_div:
                description = content_div.get_text(strip=True)[:500]

            # Parse price from hidden fields or page content
            base_price = 0.0
            currency = "ARS"

            if 'AuctionBaseValue' in hidden_fields:
                price_str = hidden_fields['AuctionBaseValue']
                # Handle Argentine format: "37.500,00" or "37500,00"
                price_str = price_str.replace('.', '').replace(',', '.')
                try:
                    base_price = float(price_str)
                except ValueError:
                    pass

            # Detect currency from page
            page_text = soup.get_text()
            if 'USD' in page_text or 'dólares' in page_text.lower():
                currency = "USD"

            # Determine status from hidden fields
            status = "published"
            if hidden_fields.get('isInProgress', '').lower() == 'true':
                status = "ongoing"
            elif hidden_fields.get('isPublished', '').lower() == 'false':
                status = "finalized"

            # Parse dates
            starts_at = None
            ends_at = None

            if 'countdown_finish_date' in hidden_fields:
                ends_at = self._parse_date(hidden_fields['countdown_finish_date'])
            if 'dead_line_inscription_date' in hidden_fields:
                starts_at = self._parse_date(hidden_fields['dead_line_inscription_date'])

            # Extract location
            location = self._parse_location(page_text)

            # Extract images
            images = self._extract_images(soup, auction_id, hidden_fields.get('LotID'))

            # Detect category
            category = detect_category(title, description)

            source_url = f"{self.BASE_URL}/Auctions/Details/{auction_id}"

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
                starts_at=starts_at,
                ends_at=ends_at,
                location=location,
                images=images,
                extra={
                    "auction_code": str(auction_id),
                    "lot_id": hidden_fields.get('LotID', ''),
                }
            )

        except Exception as e:
            logger.error(f"Error parsing CSJN auction {auction_id}: {e}")
            return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse Argentine date format: DD/MM/YYYY HH:MM:SS a. m."""
        if not date_str:
            return None

        # Remove "a. m." or "p. m." and normalize
        date_str = date_str.replace('a. m.', 'AM').replace('p. m.', 'PM')
        date_str = date_str.replace('a.m.', 'AM').replace('p.m.', 'PM')

        formats = [
            "%d/%m/%Y %I:%M:%S %p",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %I:%M %p",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def _parse_location(self, text: str) -> dict:
        """Extract location from page text."""
        location = {"province": "", "city": ""}

        provinces = {
            "buenos aires": "Buenos Aires",
            "caba": "CABA",
            "capital federal": "CABA",
            "ciudad autónoma": "CABA",
            "córdoba": "Córdoba",
            "cordoba": "Córdoba",
            "santa fe": "Santa Fe",
            "mendoza": "Mendoza",
            "tucumán": "Tucumán",
            "entre ríos": "Entre Ríos",
            "salta": "Salta",
            "misiones": "Misiones",
            "chaco": "Chaco",
            "corrientes": "Corrientes",
            "san juan": "San Juan",
            "jujuy": "Jujuy",
            "río negro": "Río Negro",
            "neuquén": "Neuquén",
            "formosa": "Formosa",
            "chubut": "Chubut",
            "san luis": "San Luis",
            "catamarca": "Catamarca",
            "la rioja": "La Rioja",
            "la pampa": "La Pampa",
            "santa cruz": "Santa Cruz",
            "tierra del fuego": "Tierra del Fuego",
        }

        text_lower = text.lower()
        for key, value in provinces.items():
            if key in text_lower:
                location["province"] = value
                break

        return location

    def _extract_images(self, soup: BeautifulSoup, auction_id: int, lot_id: Optional[str]) -> list[str]:
        """Extract image URLs from page."""
        images = []

        # Find all images
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if not src:
                continue

            # Skip icons and logos
            if any(x in src.lower() for x in ['logo', 'icon', 'avatar', 'placeholder']):
                continue

            # Make absolute URL
            if src.startswith('/'):
                src = f"{self.BASE_URL}{src}"
            elif not src.startswith('http'):
                src = f"{self.BASE_URL}/{src}"

            if src not in images:
                images.append(src)

        return images[:5]  # Limit to 5 images

    def parse_listing(self, element, status: str = "published") -> Optional[AuctionListing]:
        """Required by base class - delegates to detail page parser."""
        return None


async def main():
    """Test the CSJN scraper."""
    import asyncio
    logging.basicConfig(level=logging.INFO)

    async with CSJNScraper() as scraper:
        listings = await scraper.scrape()
        print(f"\nFound {len(listings)} total listings")

        for listing in listings[:5]:
            print(f"\n{listing.title}")
            print(f"  Price: {listing.currency} {listing.base_price:,.2f}")
            print(f"  Category: {listing.category}")
            print(f"  Status: {listing.status}")
            print(f"  URL: {listing.source_url}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
