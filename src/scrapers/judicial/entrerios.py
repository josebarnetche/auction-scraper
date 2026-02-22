"""Entre Rios judicial auction scraper."""

import re
import logging
import asyncio
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup, Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class EntreRiosScraper(BaseScraper):
    """Scraper for Entre Rios Province judicial auctions.

    The site (subastas.jusentrerios.gob.ar) is a React SPA that requires
    JavaScript rendering. This scraper uses Playwright for JS content.
    """

    SOURCE_NAME = "entrerios"
    BASE_URL = "https://subastas.jusentrerios.gob.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings from Entre Rios judicial auctions."""
        all_listings = []

        # Use Playwright for JS-rendered content
        try:
            listings = await self._scrape_with_playwright()
            if listings:
                return listings
        except Exception as e:
            logger.warning(f"Playwright scraping failed: {e}")

        # Fallback: try direct HTTP requests
        logger.info(f"Attempting fallback scraping for Entre Rios: {self.BASE_URL}")
        html = await self.fetch_html(self.BASE_URL)
        if html:
            soup = self.parse_html(html)
            listings = self._parse_listings_from_html(soup)
            all_listings.extend(listings)

        logger.info(f"Found {len(all_listings)} Entre Rios listings")
        return all_listings

    async def _scrape_with_playwright(self) -> list[AuctionListing]:
        """Scrape using Playwright for JS content."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright not installed, skipping JS rendering")
            return []

        auction_data = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()

            try:
                logger.info(f"Loading Entre Rios auctions page: {self.BASE_URL}")
                await page.goto(self.BASE_URL, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(3)  # Wait for React to render

                # Try to find auction cards/links on the main page
                # Common patterns for auction sites
                selectors = [
                    'a[href*="/subasta/"]',
                    'a[href*="/auction/"]',
                    'a[href*="/detalle/"]',
                    'a[href*="/detail/"]',
                    '.card a',
                    '.auction-card a',
                    '.subasta-card a',
                    '[class*="auction"] a',
                    '[class*="subasta"] a',
                ]

                links_found = set()
                for selector in selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        for elem in elements:
                            href = await elem.get_attribute("href")
                            if href:
                                links_found.add(href)
                    except Exception:
                        continue

                # Also try to capture auction IDs from any numeric links
                all_links = await page.query_selector_all('a[href]')
                for link in all_links:
                    try:
                        href = await link.get_attribute("href")
                        if href and re.search(r'/\d+', href):
                            links_found.add(href)
                    except Exception:
                        continue

                logger.info(f"Found {len(links_found)} potential auction links")

                # Extract auction IDs from links
                auction_ids = set()
                for href in links_found:
                    # Match patterns like /subasta/123, /auction/123, /detalle/123, or just /123
                    match = re.search(r'(?:/subasta/|/auction/|/detalle/|/detail/|/)(\d+)(?:$|[/?#])', href)
                    if match:
                        auction_ids.add(int(match.group(1)))

                # If no specific links found, try to extract data directly from the page
                if not auction_ids:
                    logger.info("No auction IDs found, extracting data from main page")
                    page_content = await page.content()
                    soup = BeautifulSoup(page_content, "lxml")
                    listings = self._extract_listings_from_rendered_page(soup)
                    await browser.close()
                    return listings

                # Scrape detail pages
                for auction_id in sorted(auction_ids):
                    try:
                        listing = await self._fetch_detail_playwright(page, auction_id)
                        if listing:
                            auction_data.append(listing)
                        await asyncio.sleep(self.RATE_LIMIT_SECONDS)
                    except Exception as e:
                        logger.debug(f"Error fetching detail {auction_id}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Playwright error: {e}")
            finally:
                await browser.close()

        # Deduplicate by title + base_price (site shows same auction on multiple URLs)
        seen = set()
        unique_listings = []
        for listing in auction_data:
            key = (listing.title, listing.base_price)
            if key not in seen:
                seen.add(key)
                unique_listings.append(listing)

        logger.info(f"Playwright found {len(auction_data)} Entre Rios listings ({len(unique_listings)} unique)")
        return unique_listings

    async def _fetch_detail_playwright(self, page, auction_id: int) -> Optional[AuctionListing]:
        """Fetch auction detail page using Playwright."""
        # Try common URL patterns
        url_patterns = [
            f"{self.BASE_URL}/subasta/{auction_id}",
            f"{self.BASE_URL}/auction/{auction_id}",
            f"{self.BASE_URL}/detalle/{auction_id}",
            f"{self.BASE_URL}/{auction_id}",
        ]

        for url in url_patterns:
            try:
                response = await page.goto(url, wait_until="networkidle", timeout=30000)
                if response and response.status == 200:
                    await asyncio.sleep(1)  # Wait for content to render
                    page_content = await page.content()

                    # Check if it's a valid auction page
                    if "subasta" in page_content.lower() or "auction" in page_content.lower():
                        soup = BeautifulSoup(page_content, "lxml")
                        return self._parse_detail_page(soup, auction_id, url)
            except Exception as e:
                logger.debug(f"Failed to load {url}: {e}")
                continue

        return None

    def _parse_detail_page(self, soup: BeautifulSoup, auction_id: int, url: str) -> Optional[AuctionListing]:
        """Parse a single auction detail page."""
        try:
            page_text = soup.get_text(separator=" ", strip=True)

            # Extract title
            title = self._extract_title(soup, page_text, auction_id)
            if not title or len(title) < 5:
                return None

            # Extract description
            description = self._extract_description(soup, page_text)

            # Extract price
            base_price, currency = self._parse_price(page_text)

            # Extract dates
            starts_at = self._parse_date_from_text(page_text, "inicio")
            ends_at = self._parse_date_from_text(page_text, "cierre")

            # Extract images
            images = self._extract_images(soup)

            # Detect category
            category = detect_category(title, description)

            # Extract location
            location = self._parse_location(page_text)
            location["province"] = "Entre Rios"  # Always set province

            # Determine status
            status = self._determine_status(page_text, starts_at, ends_at)

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=url,
                title=title,
                description=description[:500] if description else "",
                category=category,
                base_price=base_price,
                currency=currency,
                status=status,
                starts_at=starts_at,
                ends_at=ends_at,
                location=location,
                images=images,
            )

        except Exception as e:
            logger.error(f"Error parsing Entre Rios auction {auction_id}: {e}")
            return None

    def _extract_title(self, soup: BeautifulSoup, page_text: str, auction_id: int) -> str:
        """Extract title from page."""
        # Try common title selectors
        title_selectors = [
            'h1',
            'h2',
            '.title',
            '.auction-title',
            '.subasta-title',
            '[class*="title"]',
            '[class*="titulo"]',
        ]

        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                if len(title) >= 5 and len(title) <= 200:
                    return self._clean_title(title)

        # Try to extract from meta tags
        meta_title = soup.find("meta", property="og:title")
        if meta_title and meta_title.get("content"):
            return self._clean_title(meta_title["content"])

        # Try to find vehicle or property patterns in text
        vehicle_match = re.search(
            r'((?:FORD|TOYOTA|CHEVROLET|VOLKSWAGEN|RENAULT|FIAT|PEUGEOT|CITROEN|HONDA|'
            r'BMW|MERCEDES|AUDI|NISSAN|HYUNDAI|KIA|JEEP|RAM|DODGE)[A-Z0-9\s\-/\.]+)',
            page_text, re.I
        )
        if vehicle_match:
            return self._clean_title(vehicle_match.group(1))

        # Property patterns
        prop_match = re.search(
            r'((?:CASA|DEPARTAMENTO|TERRENO|LOTE|INMUEBLE|PH|GALPÓN|GALPON|LOCAL)[^.]{10,100})',
            page_text, re.I
        )
        if prop_match:
            return self._clean_title(prop_match.group(1))

        return f"Subasta #{auction_id}"

    def _clean_title(self, title: str) -> str:
        """Clean up title text."""
        title = re.sub(r'\s+', ' ', title).strip()
        title = re.sub(r'^(?:EN\s+)?(?:DOLARES|DÓLARES|PESOS|USD|U\$S)\s*[-–]?\s*', '', title, flags=re.I)
        return title[:150]

    def _extract_description(self, soup: BeautifulSoup, page_text: str) -> str:
        """Extract description from page."""
        desc_selectors = [
            '.description',
            '.descripcion',
            '.auction-description',
            '.detail',
            '.detalle',
            '[class*="description"]',
            '[class*="descripcion"]',
        ]

        for selector in desc_selectors:
            elem = soup.select_one(selector)
            if elem:
                desc = elem.get_text(strip=True)
                if len(desc) > 20:
                    return desc[:500]

        # Use a portion of the page text
        return page_text[:500] if page_text else ""

    def _parse_price(self, text: str) -> tuple[float, str]:
        """Parse price from text."""
        currency = "ARS"
        if "USD" in text.upper() or "U$S" in text.upper() or "DÓLAR" in text.upper():
            currency = "USD"

        # Price patterns
        patterns = [
            r'(?:Base|Valor base|Precio base)[:\s]*\$?\s*([\d.,]+)',
            r'(?:USD|U\$S|US\$)\s*([\d.,]+)',
            r'\$\s*([\d.,]+)',
            r'([\d.,]+)\s*(?:pesos|dólares)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                price_str = match.group(1)
                # Handle Argentine number format (periods for thousands, comma for decimals)
                if "," in price_str:
                    price_str = price_str.replace(".", "").replace(",", ".")
                else:
                    price_str = price_str.replace(".", "")

                try:
                    price = float(price_str)
                    if price > 0:
                        return price, currency
                except ValueError:
                    continue

        return 0.0, currency

    def _parse_date_from_text(self, text: str, date_type: str) -> Optional[datetime]:
        """Parse date from text based on type (inicio/cierre)."""
        if date_type == "inicio":
            keywords = ["inicio", "comienza", "apertura", "inscripción desde"]
        else:
            keywords = ["cierre", "finaliza", "fin", "hasta"]

        # Build pattern with keywords
        for keyword in keywords:
            # Pattern: keyword + date DD/MM/YYYY + optional time
            pattern = rf'{keyword}[:\s]*(\d{{1,2}})[/\-](\d{{1,2}})[/\-](\d{{2,4}})(?:\s*[-–]\s*(\d{{1,2}}):(\d{{2}})(?:\s*(AM|PM|am|pm|hs)?)?)?'
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    groups = match.groups()
                    day = int(groups[0])
                    month = int(groups[1])
                    year = int(groups[2])
                    if year < 100:
                        year += 2000

                    hour = 0
                    minute = 0
                    if groups[3] and groups[4]:
                        hour = int(groups[3])
                        minute = int(groups[4])
                        am_pm = groups[5] if len(groups) > 5 else None
                        if am_pm and am_pm.upper() == 'PM' and hour < 12:
                            hour += 12
                        elif am_pm and am_pm.upper() == 'AM' and hour == 12:
                            hour = 0

                    return datetime(year, month, day, hour, minute)
                except (ValueError, IndexError):
                    continue

        # Generic date pattern
        date_patterns = [
            r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s*(?:[-–]\s*)?(\d{1,2}):(\d{2})\s*(AM|PM|am|pm|hs)?',
            r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    groups = match.groups()
                    day = int(groups[0])
                    month = int(groups[1])
                    year = int(groups[2])
                    if year < 100:
                        year += 2000

                    if len(groups) > 3 and groups[3] and groups[4]:
                        hour = int(groups[3])
                        minute = int(groups[4])
                        return datetime(year, month, day, hour, minute)

                    return datetime(year, month, day)
                except (ValueError, IndexError):
                    continue

        return None

    def _extract_images(self, soup: BeautifulSoup) -> list[str]:
        """Extract image URLs from page."""
        images = []
        skip_patterns = [
            'logo', 'icon', 'avatar', 'placeholder', 'ribbon', 'loader',
            'badge', 'banner', 'button', 'arrow', 'favicon', '.gif', 'spinner'
        ]

        # Look for images in galleries/carousels first
        gallery_selectors = [
            '.carousel img',
            '.gallery img',
            '.slider img',
            '.images img',
            '[class*="photo"] img',
            '[class*="image"] img',
            '[class*="foto"] img',
        ]

        for selector in gallery_selectors:
            for img in soup.select(selector):
                src = img.get("src") or img.get("data-src") or img.get("data-lazy")
                if self._is_valid_image(src, skip_patterns):
                    src = self._make_absolute_url(src)
                    if src not in images:
                        images.append(src)

        # If no gallery images, try all images
        if not images:
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or img.get("data-lazy")
                if self._is_valid_image(src, skip_patterns):
                    src = self._make_absolute_url(src)
                    if src not in images:
                        images.append(src)

        return images[:5]

    def _is_valid_image(self, src: str, skip_patterns: list[str]) -> bool:
        """Check if image URL is valid (not a UI element)."""
        if not src:
            return False
        src_lower = src.lower()
        return not any(pattern in src_lower for pattern in skip_patterns)

    def _make_absolute_url(self, url: str) -> str:
        """Make URL absolute."""
        if not url:
            return ""
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            return f"{self.BASE_URL}{url}"
        if not url.startswith("http"):
            return f"{self.BASE_URL}/{url}"
        return url

    def _parse_location(self, text: str) -> dict:
        """Extract location from text."""
        location = {"province": "Entre Rios", "city": ""}

        # Entre Rios cities
        cities = [
            "Paraná", "Concordia", "Gualeguaychú", "Gualeguay", "Concepción del Uruguay",
            "Villaguay", "Chajarí", "La Paz", "Federación", "Colón", "Victoria",
            "Diamante", "Nogoyá", "Crespo", "San José", "Basavilbaso", "Rosario del Tala",
            "Federal", "Feliciano", "Islas del Ibicuy"
        ]

        text_lower = text.lower()
        for city in cities:
            if city.lower() in text_lower:
                location["city"] = city
                break

        return location

    def _determine_status(self, text: str, starts_at: Optional[datetime], ends_at: Optional[datetime]) -> str:
        """Determine auction status."""
        text_lower = text.lower()

        if "finalizada" in text_lower or "cerrada" in text_lower or "terminada" in text_lower:
            return "finalized"
        if "en curso" in text_lower or "activa" in text_lower or "abierta" in text_lower:
            return "ongoing"

        now = datetime.now()
        if ends_at and ends_at < now:
            return "finalized"
        if starts_at and starts_at <= now:
            if ends_at and ends_at > now:
                return "ongoing"
            return "ongoing"

        return "published"

    def _extract_listings_from_rendered_page(self, soup: BeautifulSoup) -> list[AuctionListing]:
        """Extract listings directly from rendered main page."""
        listings = []

        # Try to find auction cards
        card_selectors = [
            '.card',
            '.auction-card',
            '.subasta-card',
            '[class*="auction"]',
            '[class*="subasta"]',
            'article',
        ]

        cards_found = []
        for selector in card_selectors:
            cards = soup.select(selector)
            if cards:
                cards_found = cards
                break

        for idx, card in enumerate(cards_found):
            try:
                listing = self._parse_card(card, idx)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"Error parsing card {idx}: {e}")
                continue

        return listings

    def _parse_card(self, card: Tag, index: int) -> Optional[AuctionListing]:
        """Parse a single auction card."""
        card_text = card.get_text(separator=" ", strip=True)

        # Extract title
        title_elem = card.find(["h1", "h2", "h3", "h4", "h5"])
        title = title_elem.get_text(strip=True) if title_elem else ""
        if not title:
            title = self._extract_title(BeautifulSoup(str(card), "lxml"), card_text, index)

        if len(title) < 5:
            return None

        # Extract link
        link_elem = card.find("a", href=True)
        source_url = self.BASE_URL
        if link_elem:
            href = link_elem.get("href", "")
            source_url = self._make_absolute_url(href)

        # Extract price
        base_price, currency = self._parse_price(card_text)

        # Extract images
        images = []
        for img in card.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and not any(x in src.lower() for x in ["logo", "icon", "avatar"]):
                images.append(self._make_absolute_url(src))
                if len(images) >= 3:
                    break

        category = detect_category(title, card_text)

        return AuctionListing(
            id=self.generate_id(index),
            source=self.SOURCE_NAME,
            source_url=source_url,
            title=title,
            description=card_text[:300],
            category=category,
            base_price=base_price,
            currency=currency,
            status="published",
            starts_at=self._parse_date_from_text(card_text, "inicio"),
            ends_at=self._parse_date_from_text(card_text, "cierre"),
            location={"province": "Entre Rios", "city": ""},
            images=images,
        )

    def _parse_listings_from_html(self, soup: BeautifulSoup) -> list[AuctionListing]:
        """Fallback: parse listings from static HTML."""
        # This is a fallback for when Playwright is not available
        # The site requires JS, so this may not find much
        return self._extract_listings_from_rendered_page(soup)

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single listing element (required by base class)."""
        return self._parse_card(element, 0)


async def main():
    """Test the Entre Rios scraper."""
    logging.basicConfig(level=logging.INFO)

    async with EntreRiosScraper() as scraper:
        listings = await scraper.scrape()
        print(f"\nFound {len(listings)} total listings")

        for listing in listings[:5]:
            print(f"\n{listing.title}")
            print(f"  Price: {listing.currency} {listing.base_price:,.2f}")
            print(f"  Category: {listing.category}")
            print(f"  Status: {listing.status}")
            print(f"  Location: {listing.location}")
            print(f"  URL: {listing.source_url}")


if __name__ == "__main__":
    asyncio.run(main())
