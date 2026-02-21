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
            return []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                logger.info(f"Scraping Banco Ciudad with Playwright: {self.BASE_URL}")

                await page.goto(self.BASE_URL, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(4)  # Wait for Angular to render

                # Find all auction cards - look for the main container with auction items
                # Banco Ciudad typically shows cards with auction info
                cards = await page.query_selector_all('.card, .subasta-card, [class*="auction"], [class*="subasta"], .item-subasta')

                if not cards or len(cards) < 3:
                    # Try alternative selectors
                    cards = await page.query_selector_all('.carousel-item, .slide, .swiper-slide')

                logger.info(f"Found {len(cards)} potential auction cards")

                for i, card in enumerate(cards[:50]):
                    try:
                        listing = await self._parse_card_v2(card, page, i)
                        if listing:
                            all_listings.append(listing)
                    except Exception as e:
                        logger.debug(f"Error parsing card {i}: {e}")
                        continue

                # Also try to find auction links directly
                auction_links = await page.query_selector_all('a[href*="/subasta/"], a[href*="/auction/"], a[href*="id="]')
                seen_ids = set(l.id for l in all_listings)

                for link in auction_links[:30]:
                    try:
                        href = await link.get_attribute("href")
                        if not href:
                            continue

                        # Extract auction ID
                        id_match = re.search(r'[/=](\d{4,})', href)
                        if not id_match:
                            continue

                        auction_id = id_match.group(1)
                        listing_id = self.generate_id(auction_id)

                        if listing_id in seen_ids:
                            continue
                        seen_ids.add(listing_id)

                        # Get link text and parent info
                        text = await link.text_content() or ""
                        text = text.strip()

                        if len(text) < 5:
                            continue

                        # Build URL
                        if href.startswith("/"):
                            source_url = f"{self.BASE_URL}{href}"
                        elif href.startswith("http"):
                            source_url = href
                        else:
                            source_url = f"{self.BASE_URL}/{href}"

                        all_listings.append(AuctionListing(
                            id=listing_id,
                            source=self.SOURCE_NAME,
                            source_url=source_url,
                            title=text[:200],
                            description="",
                            category="real_estate",
                            base_price=0.0,
                            currency="USD",
                            status="published",
                            location={"province": "CABA", "city": "Buenos Aires"},
                            images=[],
                        ))
                    except Exception as e:
                        logger.debug(f"Error parsing link: {e}")

                await browser.close()

        except Exception as e:
            logger.error(f"Playwright scraping failed: {e}")
            return []

        # Deduplicate
        seen = set()
        unique = []
        for listing in all_listings:
            if listing.id not in seen:
                seen.add(listing.id)
                unique.append(listing)

        logger.info(f"Found {len(unique)} Banco Ciudad listings")
        return unique

    async def _parse_card_v2(self, card, page, index: int) -> Optional[AuctionListing]:
        """Parse a property card element with better field extraction."""
        try:
            # Get all text and HTML
            text_content = await card.text_content() or ""
            inner_html = await card.inner_html() or ""

            # Skip navigation elements
            if "Previous" in text_content and "Next" in text_content and len(text_content) < 50:
                return None

            # Clean the text - remove navigation text
            text_clean = text_content.replace("Previous", "").replace("Next", "").strip()

            if len(text_clean) < 20:
                return None

            # Try to extract auction ID from the card
            auction_id = None

            # Look for subasta number pattern
            subasta_match = re.search(r'Subasta\s*(\d+)', text_content, re.I)
            if subasta_match:
                auction_id = subasta_match.group(1)

            # Try to find link with ID
            link = await card.query_selector("a[href]")
            source_url = self.BASE_URL
            if link:
                href = await link.get_attribute("href") or ""
                if href:
                    id_match = re.search(r'[/=](\d{4,})', href)
                    if id_match:
                        auction_id = auction_id or id_match.group(1)
                    if href.startswith("/"):
                        source_url = f"{self.BASE_URL}{href}"
                    elif href.startswith("http"):
                        source_url = href

            if not auction_id:
                auction_id = str(hash(text_content[:100]) % 10**8)

            # Extract title - look for the main description
            title = ""

            # Pattern 1: Look for company name + item description
            # e.g., "BANCO CIUDAD DE BUENOS AIRES CELULARES SAMSUNG"
            company_match = re.search(r'(?:BANCO CIUDAD[^A-Z]*|[A-Z]{2,}(?:\s+[A-Z]+){1,5})\s*([A-Z][A-Za-z0-9\s,]+)', text_content)
            if company_match:
                title = company_match.group(1).strip()

            # Pattern 2: Extract what's being auctioned
            if not title or len(title) < 10:
                # Look for item description patterns
                item_patterns = [
                    r'(?:Hs\s+)([A-Z][A-Z\s]+?)(?:\d{2}/\d{2}/\d{4})',
                    r'(?:AIRES|S\.A\.|S\.R\.L\.|INC\.)[\s]*([A-Z][A-Z\s,]+?)(?:\d{2}/)',
                    r'([A-Z][A-Z\s]{10,50})(?:\d{2}/\d{2}/\d{4})',
                ]
                for pattern in item_patterns:
                    match = re.search(pattern, text_content)
                    if match:
                        title = match.group(1).strip()
                        break

            # Pattern 3: Fallback - extract meaningful text
            if not title or len(title) < 10:
                # Remove common noise and extract remaining
                cleaned = text_content
                cleaned = re.sub(r'Previous\s*Next', '', cleaned)
                cleaned = re.sub(r'Suscripci[oó]n\s*(?:CERRADA|ABIERTA)', '', cleaned, flags=re.I)
                cleaned = re.sub(r'Subasta\s*\d+', '', cleaned)
                cleaned = re.sub(r'Lotes?\s*[\d.,]+', '', cleaned)
                cleaned = re.sub(r'En\s+d[oó]lar\s*[\d.,]*', '', cleaned, flags=re.I)
                cleaned = re.sub(r'Suscribite\s+antes\s+del\s+\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\s*Hs?', '', cleaned, flags=re.I)
                cleaned = re.sub(r'\d{2}/\d{2}/\d{4}', '', cleaned)
                cleaned = re.sub(r'De\s+\d{2}:\d{2}\s+a\s+\d{2}:\d{2}\s*\(GMT[^)]*\)', '', cleaned, flags=re.I)
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()

                if len(cleaned) > 10:
                    title = cleaned[:150]

            if not title or len(title) < 5:
                title = f"Subasta Banco Ciudad #{auction_id}"

            # Extract date
            ends_at = None
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', text_content)
            if date_match:
                try:
                    ends_at = datetime.strptime(date_match.group(1), "%d/%m/%Y")
                except ValueError:
                    pass

            # Extract image
            images = []
            img = await card.query_selector("img")
            if img:
                src = await img.get_attribute("src") or await img.get_attribute("data-src")
                if src:
                    if src.startswith("/"):
                        src = f"{self.BASE_URL}{src}"
                    # Skip placeholder/navigation images
                    if not any(x in src.lower() for x in ['logo', 'icon', 'arrow', 'prev', 'next', 'placeholder']):
                        images.append(src)

            # If no image in card, try to construct from auction ID
            if not images and auction_id and len(auction_id) >= 4:
                # Banco Ciudad image pattern
                images.append(f"{self.BASE_URL}/subastas_rest/subastas/imagen/{auction_id[:4]}/1")

            # Determine category
            category = detect_category(title, text_content)
            if category == "other":
                text_lower = text_content.lower()
                if any(x in text_lower for x in ['terreno', 'inmueble', 'departamento', 'casa', 'local']):
                    category = "real_estate"
                elif any(x in text_lower for x in ['vehiculo', 'auto', 'camion', 'moto']):
                    category = "vehicles"
                elif any(x in text_lower for x in ['maquinaria', 'equipo', 'herramienta']):
                    category = "machinery"

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title.strip(),
                description="",
                category=category,
                base_price=0.0,
                currency="USD",
                status="published",
                ends_at=ends_at,
                location={"province": "CABA", "city": "Buenos Aires"},
                images=images,
            )

        except Exception as e:
            logger.debug(f"Error parsing card: {e}")
            return None

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Required by base class."""
        return None
