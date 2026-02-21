"""Sitio de Tiendas scraper - Ecommerce businesses for sale."""

import re
import logging
import asyncio
from datetime import datetime
from typing import Optional

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class SitioDeTiendasScraper(BaseScraper):
    """Scraper for Sitio de Tiendas (ecommerce businesses marketplace)."""

    SOURCE_NAME = "sitiodetiendas"
    BASE_URL = "https://sitiodetiendas.com"
    RATE_LIMIT_SECONDS = 3.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all business listings using Playwright for JS rendering."""
        all_listings = []

        try:
            # Try to import playwright
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright not installed. Trying fallback method.")
            return await self._scrape_fallback()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()

                # Navigate to listings page
                url = f"{self.BASE_URL}/negocios-disponibles"
                logger.info(f"Scraping Sitio de Tiendas: {url}")

                await page.goto(url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(3)  # Wait for JS to render

                # Try to get all business cards
                # Common patterns for listing cards
                selectors = [
                    "[class*='card']",
                    "[class*='listing']",
                    "[class*='negocio']",
                    "[class*='business']",
                    "article",
                    ".grid > div",
                    "[class*='item']"
                ]

                cards = []
                for selector in selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        if len(elements) > 3:  # Likely found the listing cards
                            cards = elements
                            logger.info(f"Found {len(cards)} potential listings with selector: {selector}")
                            break
                    except Exception:
                        continue

                # Extract data from each card
                for i, card in enumerate(cards[:50]):  # Limit to 50 listings
                    try:
                        listing = await self._parse_card(card, page, i)
                        if listing:
                            all_listings.append(listing)
                    except Exception as e:
                        logger.debug(f"Error parsing card {i}: {e}")
                        continue

                # Try pagination if available
                try:
                    next_buttons = await page.query_selector_all("[class*='next'], [class*='pagination'] a")
                    for _ in range(3):  # Max 3 more pages
                        clicked = False
                        for btn in next_buttons:
                            try:
                                if await btn.is_visible():
                                    await btn.click()
                                    await asyncio.sleep(2)
                                    clicked = True
                                    break
                            except Exception:
                                continue

                        if not clicked:
                            break

                        # Parse new cards
                        for selector in selectors:
                            try:
                                elements = await page.query_selector_all(selector)
                                if len(elements) > 3:
                                    for j, card in enumerate(elements[:30]):
                                        listing = await self._parse_card(card, page, len(all_listings) + j)
                                        if listing and listing.id not in [l.id for l in all_listings]:
                                            all_listings.append(listing)
                                    break
                            except Exception:
                                continue
                except Exception as e:
                    logger.debug(f"Pagination error: {e}")

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

        logger.info(f"Found {len(unique)} Sitio de Tiendas listings")
        return unique

    async def _parse_card(self, card, page, index: int) -> Optional[AuctionListing]:
        """Parse a single business card."""
        try:
            # Get text content
            text_content = await card.text_content() or ""

            # Get inner HTML for more detailed parsing
            inner_html = await card.inner_html() or ""

            # Skip if too short (likely not a listing)
            if len(text_content.strip()) < 20:
                return None

            # Extract title - look for headings or strong text
            title = ""
            title_selectors = ["h2", "h3", "h4", "[class*='title']", "[class*='name']", "strong"]
            for sel in title_selectors:
                try:
                    title_elem = await card.query_selector(sel)
                    if title_elem:
                        title = await title_elem.text_content() or ""
                        if len(title.strip()) > 5:
                            break
                except Exception:
                    continue

            if not title or len(title.strip()) < 5:
                # Use first significant line of text
                lines = [l.strip() for l in text_content.split('\n') if len(l.strip()) > 5]
                title = lines[0] if lines else ""

            if not title or len(title) < 5:
                return None

            # Extract price
            price = 0.0
            currency = "USD"
            price_patterns = [
                r'USD\s*\$?\s*([\d.,]+)',
                r'\$\s*([\d.,]+)\s*USD',
                r'U\$S\s*([\d.,]+)',
                r'\$\s*([\d.,]+)',
                r'([\d.,]+)\s*(?:USD|dólares)',
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

            # Extract URL
            source_url = f"{self.BASE_URL}/negocios-disponibles"
            try:
                link = await card.query_selector("a")
                if link:
                    href = await link.get_attribute("href")
                    if href:
                        if href.startswith("/"):
                            source_url = f"{self.BASE_URL}{href}"
                        elif href.startswith("http"):
                            source_url = href
            except Exception:
                pass

            # Extract image
            images = []
            try:
                img = await card.query_selector("img")
                if img:
                    src = await img.get_attribute("src") or await img.get_attribute("data-src")
                    if src:
                        if src.startswith("/"):
                            src = f"{self.BASE_URL}{src}"
                        if not any(x in src.lower() for x in ['logo', 'icon', 'avatar', 'placeholder']):
                            images.append(src)
            except Exception:
                pass

            # Generate ID
            title_hash = str(hash(title.lower().strip()) % 10**8)
            auction_id = f"{index}_{title_hash}"

            # Detect category - for ecommerce businesses
            category = "other"
            text_lower = text_content.lower()
            if any(x in text_lower for x in ['tienda', 'ecommerce', 'shop', 'venta online']):
                category = "other"  # Could add "ecommerce" category

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title.strip()[:200],
                description=text_content[:500] if text_content else "",
                category=category,
                base_price=price,
                currency=currency,
                status="published",
                images=images,
            )

        except Exception as e:
            logger.debug(f"Error parsing card: {e}")
            return None

    async def _scrape_fallback(self) -> list[AuctionListing]:
        """Fallback scraping method without Playwright."""
        logger.info("Using fallback scraping for Sitio de Tiendas")

        # Try fetching the page anyway - might get some data
        html = await self.fetch_html(f"{self.BASE_URL}/negocios-disponibles")
        if not html:
            return []

        soup = self.parse_html(html)
        listings = []

        # Look for any links that might be business listings
        links = soup.find_all("a", href=True)
        seen = set()

        for link in links:
            href = link.get("href", "")
            if not href or href in seen:
                continue

            # Skip navigation links
            if any(x in href.lower() for x in ['login', 'register', 'contact', 'about', '#', 'javascript']):
                continue

            # Look for business-like URLs
            if re.search(r'/negocio[s]?/', href, re.I) or re.search(r'/tienda[s]?/', href, re.I):
                seen.add(href)

                title = link.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                if href.startswith("/"):
                    source_url = f"{self.BASE_URL}{href}"
                else:
                    source_url = href

                listings.append(AuctionListing(
                    id=self.generate_id(str(hash(href) % 10**8)),
                    source=self.SOURCE_NAME,
                    source_url=source_url,
                    title=title[:200],
                    description="",
                    category="other",
                    base_price=0.0,
                    currency="USD",
                    status="published",
                    images=[],
                ))

        logger.info(f"Fallback found {len(listings)} Sitio de Tiendas listings")
        return listings

    def parse_listing(self, element, status: str = "published") -> Optional[AuctionListing]:
        """Required by base class."""
        return None
