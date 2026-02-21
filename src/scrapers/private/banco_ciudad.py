"""Banco Ciudad auction scraper."""

import re
import logging
import asyncio
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class BancoCiudadScraper(BaseScraper):
    """Scraper for Banco Ciudad auctions (JS-rendered Angular site)."""

    SOURCE_NAME = "banco_ciudad"
    BASE_URL = "https://subastas.bancociudad.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings using Playwright."""
        all_listings = []

        # This site is Angular/JS rendered, needs Playwright
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright not installed for Banco Ciudad scraper")
            return await self._scrape_fallback()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()

                logger.info(f"Scraping Banco Ciudad with Playwright: {self.BASE_URL}")

                await page.goto(self.BASE_URL, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(3)  # Wait for Angular to render

                # Try multiple selectors for property cards
                selectors = [
                    ".property-card",
                    ".inmueble",
                    ".card",
                    "[class*='property']",
                    "[class*='auction']",
                    "[class*='subasta']",
                    "article",
                    ".list-item",
                    ".item"
                ]

                cards = []
                for selector in selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        if len(elements) >= 3:
                            cards = elements
                            logger.info(f"Found {len(cards)} cards with selector: {selector}")
                            break
                    except Exception:
                        continue

                # If no cards found, try to find any links to property pages
                if not cards:
                    links = await page.query_selector_all('a[href*="inmueble"], a[href*="propiedad"], a[href*="subasta"]')
                    for link in links:
                        listing = await self._parse_link_element(link, page)
                        if listing:
                            all_listings.append(listing)

                # Parse cards
                for i, card in enumerate(cards[:50]):
                    try:
                        listing = await self._parse_card(card, page, i)
                        if listing:
                            all_listings.append(listing)
                    except Exception as e:
                        logger.debug(f"Error parsing card {i}: {e}")
                        continue

                # Try scrolling to load more
                for scroll in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1)

                    # Check for new cards
                    for selector in selectors:
                        try:
                            new_elements = await page.query_selector_all(selector)
                            if len(new_elements) > len(cards):
                                for j, card in enumerate(new_elements[len(cards):]):
                                    listing = await self._parse_card(card, page, len(all_listings) + j)
                                    if listing and listing.id not in [l.id for l in all_listings]:
                                        all_listings.append(listing)
                                cards = new_elements
                                break
                        except Exception:
                            continue

                await browser.close()

        except Exception as e:
            logger.error(f"Playwright scraping failed: {e}")
            return await self._scrape_fallback()

        # Deduplicate
        seen = set()
        unique = []
        for listing in all_listings:
            if listing.id not in seen:
                seen.add(listing.id)
                unique.append(listing)

        logger.info(f"Found {len(unique)} Banco Ciudad listings")
        return unique

    async def _parse_card(self, card, page, index: int) -> Optional[AuctionListing]:
        """Parse a property card element."""
        try:
            text_content = await card.text_content() or ""

            if len(text_content.strip()) < 20:
                return None

            # Get link
            source_url = self.BASE_URL
            link = await card.query_selector("a")
            if link:
                href = await link.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        source_url = f"{self.BASE_URL}{href}"
                    elif href.startswith("http"):
                        source_url = href

            # Extract title
            title = ""
            for sel in ["h2", "h3", "h4", "[class*='title']", "[class*='name']", "strong"]:
                try:
                    title_elem = await card.query_selector(sel)
                    if title_elem:
                        title = await title_elem.text_content() or ""
                        if len(title.strip()) > 5:
                            break
                except Exception:
                    continue

            if not title or len(title.strip()) < 5:
                lines = [l.strip() for l in text_content.split('\n') if len(l.strip()) > 5]
                title = lines[0] if lines else ""

            if not title or len(title) < 5:
                return None

            # Extract price
            price = 0.0
            currency = "USD"  # Banco Ciudad typically uses USD
            price_patterns = [
                r'USD\s*\$?\s*([\d.,]+)',
                r'U\$S\s*([\d.,]+)',
                r'\$\s*([\d.,]+)',
            ]
            for pattern in price_patterns:
                match = re.search(pattern, text_content, re.I)
                if match:
                    price_str = match.group(1).replace('.', '').replace(',', '.')
                    try:
                        price = float(price_str)
                        break
                    except ValueError:
                        continue

            # Extract image
            images = []
            try:
                img = await card.query_selector("img")
                if img:
                    src = await img.get_attribute("src") or await img.get_attribute("data-src")
                    if src and "logo" not in src.lower() and "icon" not in src.lower():
                        if src.startswith("/"):
                            src = f"{self.BASE_URL}{src}"
                        images.append(src)
            except Exception:
                pass

            # Generate ID
            id_match = re.search(r'/(\d+)', source_url)
            auction_id = id_match.group(1) if id_match else str(hash(title) % 10**8)

            # Banco Ciudad is primarily real estate
            category = detect_category(title, text_content)
            if category == "other":
                category = "real_estate"

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title.strip()[:200],
                description=text_content[:300] if text_content else "",
                category=category,
                base_price=price,
                currency=currency,
                status="published",
                location={"province": "CABA", "city": "Buenos Aires"},
                images=images,
            )

        except Exception as e:
            logger.debug(f"Error parsing card: {e}")
            return None

    async def _parse_link_element(self, link, page) -> Optional[AuctionListing]:
        """Parse a link element."""
        try:
            href = await link.get_attribute("href")
            if not href:
                return None

            title = await link.text_content() or ""
            if len(title.strip()) < 5:
                return None

            if href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            elif href.startswith("http"):
                source_url = href
            else:
                source_url = f"{self.BASE_URL}/{href}"

            id_match = re.search(r'/(\d+)', href)
            auction_id = id_match.group(1) if id_match else str(hash(href) % 10**8)

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title.strip()[:200],
                description="",
                category="real_estate",
                base_price=0.0,
                currency="USD",
                status="published",
                location={"province": "CABA", "city": "Buenos Aires"},
                images=[],
            )
        except Exception as e:
            logger.debug(f"Error parsing link: {e}")
            return None

    async def _scrape_fallback(self) -> list[AuctionListing]:
        """Fallback scraping without Playwright."""
        logger.info("Using fallback scraping for Banco Ciudad")

        html = await self.fetch_html(self.BASE_URL)
        if not html:
            return []

        soup = self.parse_html(html)
        listings = []

        # Look for any property links
        links = soup.find_all("a", href=True)
        seen = set()

        for link in links:
            href = link.get("href", "")
            if not href or href in seen:
                continue

            if any(x in href.lower() for x in ['inmueble', 'propiedad', 'subasta', 'auction']):
                seen.add(href)

                title = link.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                if href.startswith("/"):
                    source_url = f"{self.BASE_URL}{href}"
                else:
                    source_url = href

                id_match = re.search(r'/(\d+)', href)
                auction_id = id_match.group(1) if id_match else str(hash(href) % 10**8)

                listings.append(AuctionListing(
                    id=self.generate_id(auction_id),
                    source=self.SOURCE_NAME,
                    source_url=source_url,
                    title=title[:200],
                    description="",
                    category="real_estate",
                    base_price=0.0,
                    currency="USD",
                    status="published",
                    location={"province": "CABA", "city": "Buenos Aires"},
                    images=[],
                ))

        logger.info(f"Fallback found {len(listings)} Banco Ciudad listings")
        return listings

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Required by base class."""
        return None
