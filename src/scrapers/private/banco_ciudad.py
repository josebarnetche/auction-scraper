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

                # Find all auction links with /subasta/ pattern
                auction_links = await page.query_selector_all('a[href*="/subasta/"]')
                logger.info(f"Found {len(auction_links)} auction links")

                seen_ids = set()

                # Collect all auction IDs first
                for link in auction_links:
                    try:
                        href = await link.get_attribute("href")
                        if not href:
                            continue

                        id_match = re.search(r'/subasta/(\d+)', href)
                        if id_match:
                            seen_ids.add(id_match.group(1))
                    except Exception:
                        pass

                logger.info(f"Found {len(seen_ids)} unique auction IDs")

                # Fetch each detail page in a fresh page for accurate titles
                for auction_id in seen_ids:
                    try:
                        # Create a new page for each auction to avoid Angular caching issues
                        detail_page = await context.new_page()
                        listing = await self._fetch_detail_page(detail_page, auction_id)
                        await detail_page.close()

                        if listing:
                            all_listings.append(listing)
                        await asyncio.sleep(0.3)  # Rate limit
                    except Exception as e:
                        logger.debug(f"Error fetching detail {auction_id}: {e}")

                await browser.close()

        except Exception as e:
            logger.error(f"Playwright scraping failed: {e}")
            return []

        logger.info(f"Found {len(all_listings)} Banco Ciudad listings")
        return all_listings

    async def _fetch_detail_page(self, page, auction_id: str) -> Optional[AuctionListing]:
        """Fetch auction detail page for accurate title."""
        url = f"{self.BASE_URL}/subasta/{auction_id}"

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)  # Wait for Angular to fully render

            # Get full page text
            page_text = await page.evaluate("document.body.innerText") or ""

            # Try to find the title - appears between "Compartir" and "Sujeta a aprobación"
            title = ""

            # Primary pattern: Title is after "Compartir\n" and before "\nSujeta"
            compartir_match = re.search(r'Compartir\s*\n\s*(.+?)\s*\n\s*Sujeta', page_text, re.DOTALL)
            if compartir_match:
                title = compartir_match.group(1).strip()
                # Clean up any extra whitespace/newlines
                title = re.sub(r'\s+', ' ', title).strip()

            # Fallback: Extract from "Subasta N°XXXX | ORG\nCompartir\nTITLE"
            if not title or len(title) < 5:
                alt_match = re.search(r'Subasta\s+N[°º]?\d+\s*\|\s*[^\n]+\n\s*Compartir\s*\n\s*(.+?)\s*\n', page_text)
                if alt_match:
                    title = alt_match.group(1).strip()

            if not title or len(title) < 5:
                title = f"Subasta #{auction_id}"

            # Clean the title
            title = self._clean_title_text(title)

            # Extract date
            ends_at = None
            page_text = await page.evaluate("document.body.innerText") or ""
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', page_text)
            if date_match:
                try:
                    ends_at = datetime.strptime(date_match.group(1), "%d/%m/%Y")
                except ValueError:
                    pass

            # Get image
            images = []
            img = await page.query_selector('img[src*="imagen"], img[src*="subasta"]')
            if img:
                src = await img.get_attribute("src")
                if src:
                    if src.startswith("/"):
                        src = f"{self.BASE_URL}{src}"
                    images.append(src)

            if not images:
                images.append(f"{self.BASE_URL}/subastas_rest/subastas/imagen/{auction_id}/1")

            # Detect category
            category = detect_category(title, page_text[:500])

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=url,
                title=title[:200],
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
            logger.debug(f"Error fetching detail page {auction_id}: {e}")
            return None

    def _clean_title_text(self, title: str) -> str:
        """Clean title text from common artifacts."""
        if not title:
            return ""

        # Remove common prefixes/suffixes
        cleaned = re.sub(r'^(Subasta|Lote|Detalle)[:\s]*', '', title, flags=re.I)
        cleaned = re.sub(r'\s*(Subasta|Lote)\s*#?\d+\s*$', '', cleaned, flags=re.I)

        # Remove dates and times
        cleaned = re.sub(r'\d{2}/\d{2}/\d{4}', '', cleaned)
        cleaned = re.sub(r'\d{2}:\d{2}', '', cleaned)

        # Clean whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned[:200]

    def _parse_auction_text(self, auction_id: str, text: str, href: str) -> Optional[AuctionListing]:
        """Parse auction info from card text."""
        if not text or len(text) < 10:
            return None

        # Extract title - find the item description
        title = self._extract_item_title(text)

        if not title or len(title) < 5:
            return None

        # Build URL
        if href.startswith("/"):
            source_url = f"{self.BASE_URL}{href}"
        elif href.startswith("http"):
            source_url = href
        else:
            source_url = f"{self.BASE_URL}/{href}"

        # Extract date
        ends_at = None
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
        if date_match:
            try:
                ends_at = datetime.strptime(date_match.group(1), "%d/%m/%Y")
            except ValueError:
                pass

        # Detect category from clean title
        category = detect_category(title, text)

        # Extract image URL if present
        images = []
        if auction_id:
            # Banco Ciudad image pattern
            images.append(f"{self.BASE_URL}/subastas_rest/subastas/imagen/{auction_id}/1")

        return AuctionListing(
            id=self.generate_id(auction_id),
            source=self.SOURCE_NAME,
            source_url=source_url,
            title=title,
            description="",
            category=category,
            base_price=0.0,
            currency="USD",
            status="published",
            ends_at=ends_at,
            location={"province": "CABA", "city": "Buenos Aires"},
            images=images,
        )

    def _extract_item_title(self, text: str) -> str:
        """Extract the item/product title from auction text.

        Input examples:
        - "Subasta 382511 Lotes7.291 Suscribite antes del 25/03/2026 11:00 Hs BANCO CIUDAD DE BUENOS AIRESCELULARES SAMSUNG27/03/2026De 11:00 a 12:50 (GMT-3)"
        - Should extract: "CELULARES SAMSUNG"
        """
        if not text:
            return ""

        # Organization names that precede the item title
        org_patterns = [
            r'BANCO CIUDAD DE BUENOS AIRES',
            r'BANCO CIUDAD',
            r'BANCO NACION(?:AL)?',
            r'AUTOPISTAS URBANAS S\.?A\.?',
            r'INSTITUTO NACIONAL[^A-Z]+',
            r'MUNICIPALIDAD DE [A-Z\s]+?(?=[A-Z]{2})',
            r'PROCURACION [A-Z\.]+',
            r'A\.?R\.?C\.?A\.?',
        ]

        # Try to find org name + item pattern
        for org in org_patterns:
            pattern = org + r'\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s,\.\-0-9]+?)(?:\d{2}/\d{2}/|\d{2}:\d{2}|$)'
            match = re.search(pattern, text)
            if match:
                item = match.group(1).strip()
                # Clean trailing artifacts
                item = re.sub(r'[\d/:\s]+$', '', item).strip()
                if len(item) >= 5:
                    return item[:150]

        # Fallback: extract uppercase sequences after "Hs" marker
        hs_pattern = r'Hs\.?\s+[A-Z][^a-z]+?([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s,\.\-0-9]+?)(?:\d{2}/|\d{2}:|$)'
        match = re.search(hs_pattern, text)
        if match:
            item = match.group(1).strip()
            item = re.sub(r'[\d/:\s]+$', '', item).strip()
            if len(item) >= 5:
                return item[:150]

        # Last resort: find any meaningful uppercase sequence
        # Skip known noise words
        noise = {'SUBASTA', 'LOTES', 'SUSCRIBITE', 'ANTES', 'BANCO', 'CIUDAD', 'AIRES', 'GMT'}
        matches = re.findall(r'[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{4,}', text)
        for m in matches:
            words = m.strip().split()
            clean_words = [w for w in words if w.upper() not in noise]
            if clean_words and len(' '.join(clean_words)) >= 5:
                return ' '.join(clean_words)[:150]

        return ""

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

            # Extract title using comprehensive cleaning
            title = self._clean_banco_ciudad_title(text_content)

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

    def _clean_banco_ciudad_title(self, text: str) -> str:
        """Extract clean title from Banco Ciudad card text."""
        if not text:
            return ""

        # Normalize the text first
        cleaned = text.strip()

        # List of patterns to remove (order matters)
        remove_patterns = [
            r'Previous\s*Next',
            r'Previous',
            r'Next',
            r'Próximas\s+subastas',
            r'Proximas\s+subastas',
            r'Pr.ximas\s+subastas',  # Handle encoding issues
            r'Suscripci[oóÓ]n\s*(?:CERRADA|ABIERTA)',
            r'Suscribite\s+antes\s+del[^A-Z]*',
            r'Subasta\s*\d+',
            r'Lotes?\s*[\d.,]+',
            r'[\d.,]+\s*Lotes?',
            r'En\s+d[oóÓ]lar[es]*',
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # Dates
            r'\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?)?',  # Times
            r'De\s+:\s+a\s+:\s*\(?GMT[^)]*\)?',  # Empty time ranges
            r'De\s+\d+:\d+\s+a\s+\d+:\d+[^A-Z]*',
            r'\(GMT[^)]*\)',
            r'Hs\.?',
            r'A\s+consultar',
            r'Ver\s+detalle',
            r'Ver\s+más',
        ]

        for pattern in remove_patterns:
            cleaned = re.sub(pattern, ' ', cleaned, flags=re.I)

        # Remove standalone special chars and empty date/time artifacts
        cleaned = re.sub(r'[/:\-]{2,}', ' ', cleaned)
        cleaned = re.sub(r'\(\s*\)', '', cleaned)

        # Known organization names to remove
        org_patterns = [
            r'BANCO CIUDAD DE BUENOS AIRES',
            r'BANCO CIUDAD',
            r'BANCO NACION(?:AL)?',
            r'AUTOPISTAS URBANAS S\.?A\.?',
            r'INSTITUTO NACIONAL DE SERVICIOS SOCIALES PARA JUBILADOS Y PENSIONADOS',
            r'MUNICIPALIDAD DE [A-Z\s]+',
            r'A\.?R\.?C\.?A\.?(?:\s|$)',
            r'AFIP',
            r'ANSES',
            r'PAMI',
        ]

        for pattern in org_patterns:
            cleaned = re.sub(pattern, ' ', cleaned, flags=re.I)

        # Remove standalone numbers
        cleaned = re.sub(r'(?<![A-Za-z])[\d.,]+(?![A-Za-z])', ' ', cleaned)

        # Clean up whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Remove leading/trailing punctuation
        cleaned = re.sub(r'^[\s,.\-:()]+', '', cleaned)
        cleaned = re.sub(r'[\s,.\-:()]+$', '', cleaned)

        # If result is too short, try to extract uppercase item descriptions
        if len(cleaned) < 8:
            # Find sequences of uppercase words that look like item descriptions
            matches = re.findall(r'[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s,]{8,}', text)
            for match in matches:
                match = match.strip()
                # Skip if it looks like an organization
                skip_words = ['BANCO', 'INSTITUTO', 'MUNICIPALIDAD', 'AUTOPISTAS', 'NACIONAL']
                if any(word in match for word in skip_words):
                    continue
                if len(match) >= 8:
                    cleaned = match
                    break

        # Final cleanup
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned[:150] if cleaned else ""

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Required by base class."""
        return None
