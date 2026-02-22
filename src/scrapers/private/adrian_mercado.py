"""Adrián Mercado auction scraper."""

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


class AdrianMercadoScraper(BaseScraper):
    """Scraper for Adrián Mercado private auctions."""

    SOURCE_NAME = "adrian_mercado"
    BASE_URL = "https://www.adrianmercado.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._blue_dollar_rate = None

    async def _get_blue_dollar_rate(self) -> float:
        """Get cached blue dollar rate."""
        if self._blue_dollar_rate is None:
            self._blue_dollar_rate = get_blue_dollar_rate()
        return self._blue_dollar_rate

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings."""
        all_listings = []

        # Main auction categories
        categories = [
            "/subastas",
            "/subastas/vehiculos",
            "/subastas/inmuebles",
            "/subastas/maquinarias",
        ]

        for path in categories:
            url = f"{self.BASE_URL}{path}"
            logger.info(f"Scraping Adrián Mercado: {url}")

            html = await self.fetch_html(url)
            if not html:
                continue

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

        # Fetch detail pages for images if missing
        logger.info(f"Found {len(unique)} Adrián Mercado listings, enriching...")
        enriched = await self._enrich_listings(unique)

        with_images = sum(1 for l in enriched if l.images)
        logger.info(f"Adrián Mercado: {with_images}/{len(enriched)} listings have images")
        return enriched

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse listings from page."""
        listings = []

        # Find all auction links - pattern: /subastas/[name]-[id]
        auction_links = soup.find_all("a", href=re.compile(r'/subastas/[^/]+-\d+'))

        seen_urls = set()
        for link in auction_links:
            href = link.get("href", "")
            if href in seen_urls:
                continue
            seen_urls.add(href)

            # Skip non-auction links
            if any(skip in href.lower() for skip in ['como-participar', 'tel:', 'mailto:', 'youtube', 'facebook']):
                continue

            listing = self._parse_auction_link(link, href)
            if listing:
                listings.append(listing)

        # Also look for cards/articles with auction links inside
        cards = soup.select(".card, article, [class*='subasta'], [class*='auction']")
        for card in cards:
            link = card.find("a", href=re.compile(r'/subastas/'))
            if link:
                href = link.get("href", "")
                if href not in seen_urls:
                    seen_urls.add(href)
                    listing = self.parse_listing(card)
                    if listing:
                        listings.append(listing)

        logger.info(f"Found {len(listings)} auction links on page")
        return listings

    def _extract_date(self, text: str) -> Optional[datetime]:
        """Extract date from text using common patterns."""
        # Pattern: dd/mm/yyyy or dd-mm-yyyy
        match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
        if match:
            try:
                day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                return datetime(year, month, day)
            except ValueError:
                pass

        # Pattern: "15 de marzo de 2026"
        months = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                  'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
        match = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})', text, re.I)
        if match:
            month = months.get(match.group(2).lower())
            if month:
                try:
                    return datetime(int(match.group(3)), month, int(match.group(1)))
                except ValueError:
                    pass

        return None

    def _parse_auction_link(self, link, href: str) -> Optional[AuctionListing]:
        """Parse auction from a link element."""
        try:
            # Extract ID from URL
            id_match = re.search(r'-(\d+)$', href)
            if not id_match:
                return None
            auction_id = id_match.group(1)

            # Build full URL
            if href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            else:
                source_url = href

            # Get parent for context
            parent = link.find_parent(["div", "article", "li", "td"])
            parent_text = parent.get_text(" ", strip=True) if parent else ""

            # Get title from link text or parent
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                if parent:
                    title = parent_text[:100]

            if not title or len(title) < 5:
                return None

            # Try to find image
            images = []
            img = link.find("img")
            if not img and parent:
                img = parent.find("img")
            if img:
                src = img.get("src") or img.get("data-src") or img.get("data-lazy")
                if src:
                    if src.startswith("/"):
                        src = f"{self.BASE_URL}{src}"
                    if not any(skip in src.lower() for skip in ['logo', 'icon', 'avatar']):
                        images.append(src)

            # Extract date
            ends_at = self._extract_date(parent_text or title)

            category = detect_category(title, "")

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title,
                description="",
                category=category,
                base_price=0.0,  # Price on detail page
                currency="ARS",
                status="published",
                ends_at=ends_at,
                images=images,
            )

        except Exception as e:
            logger.error(f"Error parsing auction link: {e}")
            return None

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single auction card."""
        try:
            link = element.find("a", href=True)
            if not link:
                return None

            href = link.get("href", "")
            id_match = re.search(r"[/-](\d+)", href)
            auction_id = id_match.group(1) if id_match else str(hash(href) % 10**8)

            if href.startswith("http"):
                source_url = href
            elif href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            else:
                source_url = f"{self.BASE_URL}/{href}"

            # Title
            title_elem = element.find(["h2", "h3", "h4", ".title", ".product-name"])
            title = title_elem.get_text(strip=True) if title_elem else ""

            if not title:
                title = link.get_text(strip=True)

            if not title or len(title) < 3:
                return None

            # Description
            desc_elem = element.find([".description", ".excerpt", "p"])
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Price
            price_elem = element.find(class_=re.compile(r"price|precio", re.I))
            price_text = price_elem.get_text() if price_elem else element.get_text()
            base_price, currency = self._parse_price(price_text)

            # Images
            images = []
            img = element.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src:
                    if src.startswith("/"):
                        src = f"{self.BASE_URL}{src}"
                    images.append(src)

            category = detect_category(title, description)

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
                images=images,
            )

        except Exception as e:
            logger.error(f"Error parsing Adrián Mercado listing: {e}")
            return None

    def _parse_price(self, text: str) -> tuple[float, str]:
        """Parse price from text."""
        currency = "ARS"
        text_upper = text.upper()
        if "USD" in text_upper or "U$S" in text_upper or "DOLAR" in text_upper:
            currency = "USD"

        match = re.search(r"[\$]?\s*([\d.,]+)", text)
        if not match:
            return 0.0, currency

        price_str = match.group(1)
        if "," in price_str:
            price_str = price_str.replace(".", "").replace(",", ".")
        else:
            price_str = price_str.replace(".", "")

        try:
            return float(price_str), currency
        except ValueError:
            return 0.0, currency

    async def _fetch_detail_page(self, listing: AuctionListing) -> AuctionListing:
        """Fetch and parse the detail page for complete data extraction."""
        try:
            html = await self.fetch_html(listing.source_url)
            if not html:
                return listing

            soup = self.parse_html(html)
            page_text = soup.get_text(" ", strip=True)

            # Extract images
            images = self._extract_detail_images(soup)

            # Extract price from detail page
            base_price, currency = self._extract_detail_price(soup, page_text)

            # Extract description
            description = self._extract_detail_description(soup)

            # Extract dates
            dates = self.extract_dates(page_text)
            ends_at = dates.get('ends_at') or listing.ends_at
            starts_at = dates.get('starts_at') or listing.starts_at

            # Extract location
            location = self._extract_detail_location(soup, page_text)
            if not location.get("province"):
                location = listing.location

            # Download any documents found
            documents = self.find_document_links(soup, self.BASE_URL)
            doc_paths = []
            for doc in documents[:3]:  # Limit to 3 documents
                path = await self.download_document(doc["url"], listing.id, doc["type"])
                if path:
                    doc_paths.append(path)

            # Store document paths in extra field
            extra = listing.extra.copy() if listing.extra else {}
            if doc_paths:
                extra["documents"] = doc_paths

            # Extract lots from multi-lot auctions
            # Get auction_id from listing.id (format: adrian_mercado:{auction_id})
            auction_id = listing.id.split(":")[-1] if ":" in listing.id else listing.id
            lots = await self._extract_lots_from_page(html, auction_id)

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
                starts_at=starts_at,
                ends_at=ends_at,
                location=location,
                images=images if images else listing.images,
                extra=extra,
                lots=lots,
                lot_count=len(lots),
            )

        except Exception as e:
            logger.error(f"Error fetching detail page for {listing.id}: {e}")
            return listing

    def _extract_detail_images(self, soup) -> list[str]:
        """Extract images from detail page."""
        images = []

        skip_patterns = ['logo', 'icon', 'avatar', 'ribbon', 'badge', 'placeholder',
                       'loading', 'spinner', 'social', 'share', 'whatsapp', 'facebook',
                       'footer', 'svg', 'googleads', 'afip', 'gptw', 'cerrar']

        product_patterns = ['amercado.azureedge.net', 'subastas/', 'products/', 'uploads/', 'auction']

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy")
            if not src:
                continue

            src_lower = src.lower()

            if any(skip in src_lower for skip in skip_patterns):
                continue

            is_product_image = any(pattern in src_lower for pattern in product_patterns)

            if is_product_image:
                if src.startswith("/"):
                    src = f"{self.BASE_URL}{src}"
                elif not src.startswith("http"):
                    src = f"{self.BASE_URL}/{src}"

                if src not in images:
                    images.insert(0, src)
                    if len(images) >= 10:
                        break

        return images

    def _extract_detail_price(self, soup, page_text: str) -> tuple[float, str]:
        """Extract price from detail page."""
        currency = "ARS"

        # Check for USD indicators
        if re.search(r'USD|U\$S|DOLAR|DÓLAR', page_text, re.I):
            currency = "USD"

        # Look for price in specific elements first
        price_selectors = [
            ".precio", ".price", "[class*='precio']", "[class*='price']",
            ".base", "[class*='base']", ".monto", "[class*='monto']"
        ]

        for selector in price_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text()
                match = re.search(r'[\$]?\s*([\d.,]+)', text)
                if match:
                    price_str = match.group(1)
                    if "," in price_str:
                        price_str = price_str.replace(".", "").replace(",", ".")
                    else:
                        price_str = price_str.replace(".", "")
                    try:
                        return float(price_str), currency
                    except ValueError:
                        pass

        # Look for price patterns in page text
        patterns = [
            r'(?:Base|Precio|Valor)[:\s]*\$?\s*([\d.,]+)',
            r'(?:Monto|Importe)[:\s]*\$?\s*([\d.,]+)',
            r'\$\s*([\d]{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?)',
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                price_str = match.group(1)
                if "," in price_str:
                    price_str = price_str.replace(".", "").replace(",", ".")
                else:
                    price_str = price_str.replace(".", "")
                try:
                    price = float(price_str)
                    if price > 100:  # Filter out small numbers that aren't prices
                        return price, currency
                except ValueError:
                    pass

        return 0.0, currency

    def _extract_detail_description(self, soup) -> str:
        """Extract description from detail page."""
        # Try specific description elements
        desc_selectors = [
            ".descripcion", ".description", "[class*='descripcion']",
            ".detalle", ".detail", "[class*='detalle']",
            "article", ".content", ".producto-descripcion"
        ]

        for selector in desc_selectors:
            elem = soup.select_one(selector)
            if elem:
                desc = elem.get_text(" ", strip=True)
                desc = ' '.join(desc.split())
                if len(desc) > 50:
                    return desc[:2000]

        # Try to find description in paragraphs
        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if len(text) > 100 and not any(skip in text.lower() for skip in ['cookie', 'copyright', 'reservado']):
                return text[:2000]

        return ""

    def _extract_detail_location(self, soup, page_text: str) -> dict:
        """Extract location from detail page."""
        location = {"province": "", "city": ""}

        # Look for location elements
        loc_selectors = [
            ".ubicacion", ".location", "[class*='ubicacion']",
            ".direccion", ".address", "[class*='direccion']"
        ]

        for selector in loc_selectors:
            elem = soup.select_one(selector)
            if elem:
                loc_text = elem.get_text(" ", strip=True)
                extracted = self.extract_location(loc_text)
                if extracted.get("province") or extracted.get("city"):
                    return extracted

        # Fall back to page text analysis
        return self.extract_location(page_text)

    async def _extract_lots_from_page(self, html: str, auction_id: str) -> list[LotItem]:
        """Extract individual lots from multi-lot auction page.

        Adrian Mercado embeds lot data as JSON in the HTML. The structure is:
        "lotes":[{"id":..., "titulo":"LOTE 1", "descripcion_breve":"...", "precio_inicial":...}, ...]

        Args:
            html: Raw HTML content of the detail page
            auction_id: The auction ID for generating lot IDs

        Returns:
            List of LotItem objects
        """
        import html as html_lib
        import json

        lots = []
        rate = await self._get_blue_dollar_rate()

        try:
            # Decode HTML entities in the page
            decoded = html_lib.unescape(html)

            # Find the start of the lotes array
            start_match = re.search(r'"lotes":\s*\[', decoded)
            if not start_match:
                return lots

            # Extract the complete lotes array by counting brackets
            start = start_match.end() - 1  # Include opening bracket
            bracket_count = 0
            end = start
            for i, char in enumerate(decoded[start:]):
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end = start + i + 1
                        break

            lotes_str = decoded[start:end]
            lotes_data = json.loads(lotes_str)

            for lot_data in lotes_data:
                try:
                    # Extract lot number from titulo (e.g., "LOTE 1" -> 1)
                    titulo = lot_data.get("titulo", "")
                    lot_num_match = re.search(r'LOTE\s*(\d+)', titulo, re.I)
                    if lot_num_match:
                        lot_number = int(lot_num_match.group(1))
                    else:
                        # Fallback: use array index + 1
                        lot_number = lotes_data.index(lot_data) + 1

                    # Get description (use descripcion_breve or descripcion_completa)
                    description = lot_data.get("descripcion_breve", "") or lot_data.get("descripcion_completa", "")
                    description = re.sub(r'\s+', ' ', description).strip()

                    # Use description as title (it contains the actual item info)
                    title = description[:200] if description else titulo

                    # Skip if no meaningful title
                    if len(title) < 10:
                        continue

                    # Get price (precio_inicial is in centavos or full amount)
                    precio = lot_data.get("precio_inicial", 0)
                    if precio is None:
                        precio = 0
                    base_price = float(precio)

                    # Skip if no price (might be "a confirmar")
                    if base_price <= 0:
                        continue

                    # Convert to USD using blue dollar rate
                    base_price_usd = convert_to_usd(base_price, "ARS", rate)

                    # Generate lot ID: am:{auction_id}:{lot_number}
                    lot_id = f"am:{auction_id}:{lot_number}"

                    # Get images from galeria
                    images = []
                    galeria = lot_data.get("galeria", [])
                    if galeria:
                        for img in galeria[:5]:  # Limit to 5 images per lot
                            if isinstance(img, dict) and img.get("src"):
                                images.append(img["src"])

                    lot = LotItem(
                        lot_id=lot_id,
                        lot_number=lot_number,
                        title=title,
                        description=description[:1000] if description else "",
                        base_price=base_price,
                        currency="ARS",
                        base_price_usd=round(base_price_usd, 2),
                        images=images,
                    )
                    lots.append(lot)

                except (ValueError, KeyError, TypeError) as e:
                    logger.debug(f"Error parsing lot data: {e}")
                    continue

        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"Error extracting lots JSON: {e}")
            return lots

        # Deduplicate by lot number (keep first occurrence)
        seen_numbers = set()
        unique_lots = []
        for lot in lots:
            if lot.lot_number not in seen_numbers:
                seen_numbers.add(lot.lot_number)
                unique_lots.append(lot)

        # Sort by lot number
        unique_lots = sorted(unique_lots, key=lambda x: x.lot_number)

        if unique_lots:
            logger.info(f"Extracted {len(unique_lots)} lots from auction {auction_id}")

        return unique_lots

    async def _enrich_listings(self, listings: list[AuctionListing]) -> list[AuctionListing]:
        """Fetch detail pages to get complete data for all listings."""
        enriched = []
        new_count = 0
        opportunity_count = 0

        for listing in listings:
            # Check if this is a new listing
            is_new = self.is_new_listing(listing.id)

            if is_new or not listing.images or listing.base_price == 0:
                await asyncio.sleep(self.RATE_LIMIT_SECONDS)
                enriched_listing = await self._fetch_detail_page(listing)

                # Analyze for opportunities
                enriched_listing = self.analyze_opportunity(enriched_listing)
                if enriched_listing.extra.get("is_opportunity"):
                    opportunity_count += 1
                    logger.info(f"Opportunity found: {enriched_listing.title[:50]}... - {enriched_listing.extra.get('opportunity_reason')}")

                enriched.append(enriched_listing)

                if is_new:
                    new_count += 1
                    self.mark_as_seen(listing.id)
                    logger.info(f"New listing found: {listing.title[:50]}...")
            else:
                # Still analyze existing listings for opportunities
                analyzed = self.analyze_opportunity(listing)
                enriched.append(analyzed)
                if analyzed.extra.get("is_opportunity"):
                    opportunity_count += 1

        if new_count > 0:
            logger.info(f"Found {new_count} NEW listings in Adrián Mercado")
        if opportunity_count > 0:
            logger.info(f"Found {opportunity_count} OPPORTUNITIES in Adrián Mercado")

        return enriched
