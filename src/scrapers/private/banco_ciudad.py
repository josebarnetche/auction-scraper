"""Banco Ciudad auction scraper."""

import re
import logging
import asyncio
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, LotItem, detect_category
from src.utils.currency import get_blue_dollar_rate, convert_to_usd

logger = logging.getLogger(__name__)


class BancoCiudadScraper(BaseScraper):
    """Scraper for Banco Ciudad auctions (JS-rendered Angular site)."""

    SOURCE_NAME = "banco_ciudad"
    BASE_URL = "https://subastas.bancociudad.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._blue_dollar_rate = None

    async def _get_blue_dollar_rate(self) -> float:
        """Get blue dollar rate (cached)."""
        if self._blue_dollar_rate is None:
            self._blue_dollar_rate = get_blue_dollar_rate()
        return self._blue_dollar_rate

    async def scrape_auction_lots(self, page, auction_id: str, auction_url: str) -> list[LotItem]:
        """Fetch all lots within an auction.

        Args:
            page: Playwright page object
            auction_id: The auction ID
            auction_url: URL of the auction detail page

        Returns:
            List of LotItem objects
        """
        lots = []
        rate = await self._get_blue_dollar_rate()

        try:
            # Navigate to auction detail if not already there
            current_url = page.url
            if auction_id not in current_url:
                await page.goto(auction_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)

            # Get page content for lot extraction
            page_text = await page.evaluate("document.body.innerText") or ""
            page_html = await page.content()

            # Try to find lots via API first
            api_lots = await self._fetch_lots_from_api(page, auction_id)
            if api_lots:
                for lot_data in api_lots:
                    lot = self._parse_api_lot(lot_data, auction_id, rate)
                    if lot:
                        lots.append(lot)
                logger.info(f"Found {len(lots)} lots via API for auction {auction_id}")
                return lots

            # Fallback: Parse lots from page HTML
            lots = self._parse_lots_from_page(page_text, page_html, auction_id, rate)
            if lots:
                logger.info(f"Found {len(lots)} lots via HTML parsing for auction {auction_id}")

        except Exception as e:
            logger.debug(f"Error scraping lots for auction {auction_id}: {e}")

        return lots

    async def _fetch_lots_from_api(self, page, auction_id: str) -> list[dict]:
        """Try to fetch lot data from REST API.

        Tests various endpoint patterns to find lot data.
        """
        api_endpoints = [
            f"{self.BASE_URL}/subastas_rest/subastas/{auction_id}/lotes",
            f"{self.BASE_URL}/subastas_rest/lotes/subasta/{auction_id}",
            f"{self.BASE_URL}/subastas_rest/subastas/{auction_id}",
        ]

        for endpoint in api_endpoints:
            try:
                response = await page.request.get(endpoint)
                if response.status == 200:
                    data = await response.json()

                    # Handle different response structures
                    if isinstance(data, list) and data:
                        # Direct array of lots
                        if any(k in str(data[0]).lower() for k in ["lote", "precio", "base"]):
                            return data

                    elif isinstance(data, dict):
                        # Nested lots in response
                        for key in ["lotes", "lots", "items", "rubros"]:
                            if key in data and isinstance(data[key], list):
                                return data[key]

            except Exception as e:
                logger.debug(f"API endpoint {endpoint} failed: {e}")
                continue

        return []

    def _parse_api_lot(self, lot_data: dict, auction_id: str, rate: float) -> Optional[LotItem]:
        """Parse a lot from API response data."""
        try:
            # Common field names for lot number
            lot_number = (
                lot_data.get("numero") or
                lot_data.get("nro_lote") or
                lot_data.get("lote") or
                lot_data.get("numero_lote") or
                lot_data.get("item") or
                1
            )

            # Common field names for title/description
            title = (
                lot_data.get("titulo") or
                lot_data.get("descripcion") or
                lot_data.get("nombre") or
                lot_data.get("detalle") or
                f"Lote {lot_number}"
            )

            description = (
                lot_data.get("descripcion_larga") or
                lot_data.get("descripcion") or
                lot_data.get("detalle") or
                ""
            )

            # Common field names for price
            base_price = float(
                lot_data.get("base") or
                lot_data.get("precio_base") or
                lot_data.get("precio") or
                lot_data.get("monto_base") or
                0
            )

            # Detect currency from data or default to ARS for BC
            currency = "ARS"
            if lot_data.get("moneda"):
                currency = "USD" if "USD" in str(lot_data.get("moneda")).upper() else "ARS"
            elif "dolar" in str(lot_data).lower() or "usd" in str(lot_data).lower():
                currency = "USD"

            # Convert to USD
            base_price_usd = convert_to_usd(base_price, currency, rate)

            # Images
            images = []
            if lot_data.get("imagen"):
                images.append(lot_data["imagen"])
            elif lot_data.get("imagenes"):
                images = lot_data["imagenes"] if isinstance(lot_data["imagenes"], list) else [lot_data["imagenes"]]
            elif lot_data.get("id_lote"):
                # Construct image URL from lot ID
                images.append(f"{self.BASE_URL}/subastas_rest/lotes/imagen/{lot_data['id_lote']}/1")

            # Lot ID
            lot_id = lot_data.get("id_lote") or lot_data.get("id") or f"{auction_id}:{lot_number}"

            return LotItem(
                lot_id=f"bc:{auction_id}:{lot_id}",
                lot_number=int(lot_number),
                title=str(title)[:200],
                description=str(description)[:1000],
                base_price=base_price,
                currency=currency,
                base_price_usd=round(base_price_usd, 2),
                deposit_required=float(lot_data.get("seña") or lot_data.get("deposito") or 0),
                images=images,
            )

        except Exception as e:
            logger.debug(f"Error parsing API lot: {e}")
            return None

    def _parse_lots_from_page(self, page_text: str, page_html: str, auction_id: str, rate: float) -> list[LotItem]:
        """Parse lots from page HTML/text when API is not available."""
        lots = []

        # Pattern to match lot entries in page text
        # Common formats:
        # "Lote 1: 100 Computadoras... Base: $42.920.000"
        # "Rubro 1 - Equipamiento... ARS $5.328.000"
        # "Item #1: Cámaras Axis... Precio Base: USD 2.020"

        lot_patterns = [
            # Lote N: Title... Base/Precio: $Amount
            r'(?:Lote|Rubro|Item)\s*(?:#|N[°º]?)?\s*(\d+)[:\s\-]*(.+?)(?:Base|Precio\s*Base?|Valor)[:\s]*(?:\$|ARS|USD)?\s*([\d.,]+)',
            # Numbered items with prices
            r'(\d+)\.\s*(.{10,100}?)\s+(?:\$|ARS|USD)\s*([\d.,]+)',
        ]

        for pattern in lot_patterns:
            matches = re.findall(pattern, page_text, re.I | re.DOTALL)
            for match in matches:
                try:
                    lot_number = int(match[0])
                    title = match[1].strip()
                    price_str = match[2].replace(".", "").replace(",", ".")

                    # Clean title
                    title = re.sub(r'\s+', ' ', title).strip()
                    if len(title) < 5:
                        continue

                    base_price = float(price_str)
                    if base_price < 100:  # Skip invalid prices
                        continue

                    # Detect currency from context
                    currency = "ARS"
                    context_start = max(0, page_text.find(match[1]) - 50)
                    context = page_text[context_start:context_start + len(match[1]) + 100]
                    if "USD" in context.upper() or "U$S" in context or "DOLAR" in context.upper():
                        currency = "USD"

                    base_price_usd = convert_to_usd(base_price, currency, rate)

                    lot = LotItem(
                        lot_id=f"bc:{auction_id}:{lot_number}",
                        lot_number=lot_number,
                        title=title[:200],
                        description="",
                        base_price=base_price,
                        currency=currency,
                        base_price_usd=round(base_price_usd, 2),
                        images=[f"{self.BASE_URL}/subastas_rest/subastas/imagen/{auction_id}/{lot_number}"],
                    )
                    lots.append(lot)

                except (ValueError, IndexError) as e:
                    continue

        # Deduplicate by lot number
        seen_numbers = set()
        unique_lots = []
        for lot in lots:
            if lot.lot_number not in seen_numbers:
                seen_numbers.add(lot.lot_number)
                unique_lots.append(lot)

        return sorted(unique_lots, key=lambda x: x.lot_number)

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
                opportunity_count = 0
                for auction_id in seen_ids:
                    try:
                        # Create a new page for each auction to avoid Angular caching issues
                        detail_page = await context.new_page()
                        listing = await self._fetch_detail_page(detail_page, auction_id)

                        if listing:
                            # Scrape individual lots for this auction
                            auction_url = f"{self.BASE_URL}/subasta/{auction_id}"
                            lots = await self.scrape_auction_lots(detail_page, auction_id, auction_url)
                            listing.lots = lots
                            listing.lot_count = len(lots)

                            if lots:
                                logger.info(f"Auction {auction_id}: {len(lots)} lots scraped")

                            # Analyze for opportunities
                            listing = self.analyze_opportunity(listing)
                            if listing.extra.get("is_opportunity"):
                                opportunity_count += 1
                                logger.info(f"Opportunity found: {listing.title[:50]}... - {listing.extra.get('opportunity_reason')}")
                            all_listings.append(listing)

                        await detail_page.close()
                        await asyncio.sleep(0.3)  # Rate limit
                    except Exception as e:
                        logger.debug(f"Error fetching detail {auction_id}: {e}")

                if opportunity_count > 0:
                    logger.info(f"Found {opportunity_count} OPPORTUNITIES in Banco Ciudad")

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

            # Extract price from page text
            base_price = 0.0
            currency = "ARS"  # Default to ARS, detect USD from price format

            # Look for USD price format first (U$S, USD)
            usd_price_match = re.search(r'(?:U\$S|USD)\s*\$?\s*([\d.,]+)', page_text, re.I)
            if usd_price_match:
                currency = "USD"
                price_str = usd_price_match.group(1)
                if "," in price_str:
                    price_str = price_str.replace(".", "").replace(",", ".")
                else:
                    price_str = price_str.replace(".", "")
                try:
                    price = float(price_str)
                    if price > 100:
                        base_price = price
                except ValueError:
                    pass

            # If no USD price found, look for ARS price
            if base_price == 0:
                price_patterns = [
                    r'Base[:\s]*\$\s*([\d.,]+)',
                    r'Precio\s+Base[:\s]*\$\s*([\d.,]+)',
                    r'Valor[:\s]*\$\s*([\d.,]+)',
                ]

                for pattern in price_patterns:
                    match = re.search(pattern, page_text, re.I)
                    if match:
                        price_str = match.group(1)
                        if "," in price_str:
                            price_str = price_str.replace(".", "").replace(",", ".")
                        else:
                            price_str = price_str.replace(".", "")
                        try:
                            price = float(price_str)
                            if price > 100:  # Reasonable minimum
                                base_price = price
                                break
                        except ValueError:
                            pass

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

            # Extract description
            description = ""
            desc_patterns = [
                r'Descripción[:\s]*(.{20,500}?)(?:Información|Ubicación|Términos|$)',
                r'Detalle[:\s]*(.{20,500}?)(?:Información|Ubicación|Términos|$)',
            ]
            for pattern in desc_patterns:
                match = re.search(pattern, page_text, re.I | re.DOTALL)
                if match:
                    description = match.group(1).strip()
                    description = re.sub(r'\s+', ' ', description)
                    break

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=url,
                title=title[:200],
                description=description[:500],
                category=category,
                base_price=base_price,
                currency=currency,
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
