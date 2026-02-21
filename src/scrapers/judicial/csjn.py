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
            page_text = soup.get_text()

            # Skip pages that are not actual auction details
            # Real auction pages have "Auto de la subasta" or specific auction codes
            is_real_auction = any(marker in page_text for marker in [
                "Auto de la subasta", "Auto de subasta", "Edicto",
                "Descripción del bien", "Valor base", "Base:",
                "La inscripción cierra en:"
            ])

            # Also skip if it's a welcome/home page
            title_tag = soup.find('title')
            page_title = title_tag.get_text(strip=True) if title_tag else ""
            if "Bienvenido" in page_title and "Detalle" not in page_title:
                return None

            if not is_real_auction:
                return None

            # Extract from hidden form fields (most reliable)
            hidden_fields = {}
            for inp in soup.find_all('input', type='hidden'):
                name = inp.get('name', '')
                value = inp.get('value', '')
                if name and value:
                    hidden_fields[name] = value

            # Extract the real auction item name/description
            title = ""

            # First, try to find a meaningful product title
            # Look for vehicle patterns (FORD, TOYOTA, etc.)
            vehicle_match = re.search(
                r'((?:FORD|TOYOTA|CHEVROLET|VOLKSWAGEN|RENAULT|FIAT|PEUGEOT|CITROEN|HONDA|'
                r'BMW|MERCEDES|AUDI|NISSAN|HYUNDAI|KIA|JEEP|RAM|DODGE|'
                r'AUTOMOTOR|CAMIONETA|CAMION|MOTO|MOTOCICLETA)[A-Z0-9\s\-/\.]+)',
                page_text, re.I
            )
            if vehicle_match:
                title = vehicle_match.group(1).strip()
                # Clean vehicle title
                title = re.sub(r'\s+', ' ', title)
                title = title[:100]

            # Look for property patterns
            if not title:
                prop_patterns = [
                    r'(CASA\s+(?:TIPO\s+)?(?:CHALET|QUINTA)?[^-]+(?:-[^-]+){0,2})',
                    r'(DEPARTAMENTO[^-]+(?:-[^-]+){0,2})',
                    r'(PH\s+\d+[^-]+(?:-[^-]+){0,2})',
                    r'(INMUEBLE[^-]+(?:-[^-]+){0,2})',
                    r'(TERRENO[^-]+(?:-[^-]+){0,2})',
                    r'(LOTE[^-]+(?:-[^-]+){0,2})',
                    r'(\d+\s*%?\s*INDIVISO[^-]+(?:-[^-]+){0,2})',
                ]
                for pattern in prop_patterns:
                    match = re.search(pattern, page_text, re.I)
                    if match:
                        title = match.group(1).strip()
                        break

            # Clean up common noise from titles
            if title:
                # Remove "EN DOLARES", "EN PESOS" etc from start
                title = re.sub(r'^(?:EN\s+)?(?:DOLARES|DÓLARES|PESOS|USD|U\$S)\s*[-–]?\s*', '', title, flags=re.I)
                # Remove "Cód." codes
                title = re.sub(r'Cód\.?\s*[A-Z0-9]+\s*', '', title)
                # Clean up multiple dashes/spaces
                title = re.sub(r'[-–]+', ' - ', title)
                title = re.sub(r'\s+', ' ', title).strip()
                title = title.strip(' -')

            # Fallback to extracting from description div
            if not title or len(title) < 10:
                desc_div = soup.find('div', class_=re.compile(r'description|detail', re.I))
                if desc_div:
                    desc_text = desc_div.get_text(strip=True)
                    # Get text after "Cód.XXX" up to "La inscripción"
                    match = re.search(r'Cód\.?\s*[A-Z0-9]+\s*(.{15,100}?)(?:La inscripción|Descripción)', desc_text)
                    if match:
                        title = match.group(1).strip()
                        title = re.sub(r'^(?:EN\s+)?(?:DOLARES|DÓLARES|PESOS)\s*[-–]?\s*', '', title, flags=re.I)

            if not title or len(title) < 5:
                title = f"Subasta Judicial #{auction_id}"

            # Final cleanup
            title = re.sub(r'\s+', ' ', title).strip()
            title = title[:120]  # Limit length

            # Get description from main content
            description = ""
            content_div = soup.find('div', class_=re.compile(r'content|detail|description', re.I))
            if content_div:
                description = content_div.get_text(strip=True)[:500]

            # Parse base price from hidden fields or page content
            base_price = 0.0
            currency = "ARS"

            # Try hidden field first
            if 'AuctionBaseValue' in hidden_fields:
                price_str = hidden_fields['AuctionBaseValue']
                price_str = price_str.replace('.', '').replace(',', '.')
                try:
                    base_price = float(price_str)
                except ValueError:
                    pass

            # If no price in hidden fields, try to extract from page text
            if base_price == 0:
                # Look for "Base: $X.XXX" or "Valor base: $X.XXX" patterns
                price_patterns = [
                    r'(?:Base|Valor base|Precio base)[:\s]*\$?\s*([\d.,]+)',
                    r'(?:USD|U\$S|US\$)\s*([\d.,]+)',
                    r'\$\s*([\d.,]+)',
                ]
                for pattern in price_patterns:
                    match = re.search(pattern, page_text, re.I)
                    if match:
                        price_str = match.group(1).replace('.', '').replace(',', '.')
                        try:
                            base_price = float(price_str)
                            if base_price > 0:
                                break
                        except ValueError:
                            continue

            # Detect currency from page
            if 'USD' in page_text or 'dólares' in page_text.lower() or 'U$S' in page_text or 'DOLARES' in page_text:
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
        """Extract image URLs from page, prioritizing actual product photos."""
        product_images = []
        other_images = []

        # Patterns to skip (UI elements, not products)
        skip_patterns = ['logo', 'icon', 'avatar', 'placeholder', 'ribbon', 'ajax-loader', 'loader']

        # Find all images
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if not src:
                continue

            # Skip UI elements
            if any(x in src.lower() for x in skip_patterns):
                continue

            # Make absolute URL
            if src.startswith('/'):
                src = f"{self.BASE_URL}{src}"
            elif not src.startswith('http'):
                src = f"{self.BASE_URL}/{src}"

            if src not in product_images and src not in other_images:
                # Prioritize AuctionImages (actual product photos)
                if '/AuctionImages/' in src:
                    product_images.append(src)
                else:
                    other_images.append(src)

        # Return product images first, then others
        all_images = product_images + other_images
        return all_images[:5]  # Limit to 5 images

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
