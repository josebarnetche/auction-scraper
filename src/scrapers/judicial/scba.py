"""SCBA (Suprema Corte de Buenos Aires) auction scraper."""

import re
import logging
import asyncio
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class SCBAScraper(BaseScraper):
    """Scraper for Buenos Aires Province judicial auctions."""

    SOURCE_NAME = "scba"
    BASE_URL = "https://subastas.scba.gov.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings from SCBA."""
        all_listings = []

        # Try Playwright first for JS-rendered content
        try:
            listings = await self._scrape_with_playwright()
            if listings:
                return listings
        except Exception as e:
            logger.warning(f"Playwright scraping failed: {e}, trying fallback")

        # Fallback: try main page
        url = self.BASE_URL
        logger.info(f"Scraping SCBA auctions: {url}")

        html = await self.fetch_html(url)
        if not html:
            # Try alternative URL
            html = await self.fetch_html(f"{self.BASE_URL}/Home")

        if not html:
            logger.warning(f"Failed to fetch SCBA")
            return all_listings

        soup = self.parse_html(html)
        listings = self._parse_listings_page(soup)
        all_listings.extend(listings)

        # Also enumerate IDs if we found some
        if all_listings:
            known_ids = set()
            for listing in all_listings:
                match = re.search(r'/Auctions/Details/(\d+)', listing.source_url)
                if match:
                    known_ids.add(int(match.group(1)))

            if known_ids:
                max_id = max(known_ids)
                for auction_id in range(max(1, max_id - 30), max_id + 10):
                    if auction_id in known_ids:
                        continue
                    listing = await self._fetch_detail(auction_id)
                    if listing:
                        all_listings.append(listing)

        logger.info(f"Found {len(all_listings)} SCBA listings")
        return all_listings

    async def _scrape_with_playwright(self) -> list[AuctionListing]:
        """Scrape using Playwright for JS content."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return []

        listings = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(self.BASE_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Find all auction links with pattern /Auctions/Details/[id]
            links = await page.query_selector_all('a[href*="/Auctions/Details/"]')

            seen_ids = set()
            for link in links:
                try:
                    href = await link.get_attribute("href")
                    if not href:
                        continue

                    match = re.search(r'/Auctions/Details/(\d+)', href)
                    if not match:
                        continue

                    auction_id = match.group(1)
                    if auction_id in seen_ids:
                        continue
                    seen_ids.add(auction_id)

                    # Get parent card for more info
                    parent_text = await link.evaluate("el => el.closest('.card, article, [class*=\"subasta\"], li, tr')?.textContent || ''")

                    title = await link.text_content() or ""
                    title = title.strip()

                    if len(title) < 5:
                        # Try to get more text from parent
                        text = await link.evaluate("el => el.parentElement?.textContent || ''")
                        title = text.strip()[:150] if text else f"Subasta #{auction_id}"

                    source_url = f"{self.BASE_URL}/Auctions/Details/{auction_id}"

                    # Extract "Inicio de inscripcion" date from parent text
                    starts_at = None
                    text_to_search = parent_text or title

                    # Look for "Inicio de inscripcion" pattern first
                    inicio_match = re.search(r'[Ii]nicio\s+de\s+inscripci[oó]n[:\s]*(\d{2})/(\d{2})/(\d{4})', text_to_search)
                    if inicio_match:
                        try:
                            starts_at = datetime.strptime(f"{inicio_match.group(1)}/{inicio_match.group(2)}/{inicio_match.group(3)}", "%d/%m/%Y")
                        except ValueError:
                            pass

                    # Fallback to first date found
                    if not starts_at:
                        date_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text_to_search)
                        if date_match:
                            try:
                                starts_at = datetime.strptime(f"{date_match.group(1)}/{date_match.group(2)}/{date_match.group(3)}", "%d/%m/%Y")
                            except ValueError:
                                pass

                    listings.append(AuctionListing(
                        id=self.generate_id(auction_id),
                        source=self.SOURCE_NAME,
                        source_url=source_url,
                        title=title[:200],
                        description="",
                        category=detect_category(title, ""),
                        base_price=0.0,
                        currency="ARS",
                        status="published",
                        starts_at=starts_at,
                        location={"province": "Buenos Aires", "city": ""},
                        images=[],
                    ))
                except Exception as e:
                    logger.debug(f"Error parsing link: {e}")
                    continue

            await browser.close()

        logger.info(f"Playwright found {len(listings)} SCBA listings")
        return listings

    async def _fetch_detail(self, auction_id: int) -> Optional[AuctionListing]:
        """Fetch auction detail page."""
        url = f"{self.BASE_URL}/Auctions/Details/{auction_id}"
        html = await self.fetch_html(url)
        if not html:
            return None

        # Check if valid page
        if "subasta" not in html.lower() and "auction" not in html.lower():
            return None

        soup = self.parse_html(html)

        # Extract title
        title_elem = soup.find(["h1", "h2"])
        title = title_elem.get_text(strip=True) if title_elem else f"Subasta #{auction_id}"

        if len(title) < 5:
            return None

        # Extract price
        page_text = soup.get_text()
        base_price, currency = self._parse_price(page_text)

        # Extract images
        images = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and not any(x in src.lower() for x in ['logo', 'icon', 'avatar']):
                if src.startswith("/"):
                    src = f"{self.BASE_URL}{src}"
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
            location={"province": "Buenos Aires", "city": ""},
            images=images,
        )

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse the listings page."""
        listings = []

        # Find all auction links
        links = soup.find_all("a", href=re.compile(r'/Auctions/Details/\d+'))

        seen_ids = set()
        for link in links:
            href = link.get("href", "")
            match = re.search(r'/Auctions/Details/(\d+)', href)
            if not match:
                continue

            auction_id = match.group(1)
            if auction_id in seen_ids:
                continue
            seen_ids.add(auction_id)

            listing = self._parse_link(link, auction_id)
            if listing:
                listings.append(listing)

        return listings

    def _parse_link(self, link, auction_id: str) -> Optional[AuctionListing]:
        """Parse a single auction link."""
        try:
            source_url = f"{self.BASE_URL}/Auctions/Details/{auction_id}"

            # Get title from link or parent
            title = link.get_text(strip=True)
            if len(title) < 5:
                parent = link.find_parent()
                if parent:
                    title = parent.get_text(strip=True)[:150]

            if not title or len(title) < 5:
                return None

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
                location={"province": "Buenos Aires", "city": ""},
                images=[],
            )
        except Exception as e:
            logger.error(f"Error parsing SCBA link: {e}")
            return None

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single auction element."""
        return None

    def _parse_price(self, text: str) -> tuple[float, str]:
        """Parse price from text."""
        currency = "ARS"
        if "USD" in text.upper() or "U$S" in text.upper():
            currency = "USD"

        price_match = re.search(r"[\$]?\s*([\d.,]+)", text)
        if not price_match:
            return 0.0, currency

        price_str = price_match.group(1)
        if "," in price_str:
            price_str = price_str.replace(".", "").replace(",", ".")
        else:
            price_str = price_str.replace(".", "")

        try:
            return float(price_str), currency
        except ValueError:
            return 0.0, currency
