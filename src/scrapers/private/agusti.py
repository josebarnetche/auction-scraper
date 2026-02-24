"""Agusti Subastas auction scraper."""

import re
import logging
import asyncio
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class AgustiSubastasScraper(BaseScraper):
    """Scraper for Agusti Subastas (agustisubastas.com.ar)."""

    SOURCE_NAME = "agusti"
    BASE_URL = "https://www.agustisubastas.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    # Spanish month abbreviations used on the site
    MONTHS = {
        'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
    }

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings from Agusti Subastas."""
        all_listings = []

        # Main listings page
        url = f"{self.BASE_URL}/Default.aspx?mnu=lotes"
        logger.info(f"Scraping Agusti Subastas: {url}")

        html = await self.fetch_html(url)
        if not html:
            logger.error("Failed to fetch Agusti Subastas main page")
            return all_listings

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

        logger.info(f"Found {len(unique)} Agusti listings, enriching with detail pages...")
        enriched = await self._enrich_listings(unique)

        with_images = sum(1 for l in enriched if l.images)
        with_prices = sum(1 for l in enriched if l.base_price > 0)
        logger.info(f"Agusti: {with_images}/{len(enriched)} with images, {with_prices}/{len(enriched)} with prices")

        return enriched

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse listings from the main page."""
        listings = []

        # Find all auction detail links: ?mnu=detalle&sid=XXXX&lid=XXXX (case insensitive)
        auction_links = soup.find_all("a", href=re.compile(r'mnu=detalle.*sid=\d+.*l[iI]d=\d+', re.I))

        seen_ids = set()
        for link in auction_links:
            href = link.get("href", "")

            # Extract auction ID and lot ID (handle both lid and lId)
            sid_match = re.search(r'sid=(\d+)', href, re.I)
            lid_match = re.search(r'l[iI]d=(\d+)', href)

            if not sid_match or not lid_match:
                continue

            auction_id = f"{sid_match.group(1)}_{lid_match.group(1)}"
            if auction_id in seen_ids:
                continue
            seen_ids.add(auction_id)

            # Get parent container for context
            parent = link.find_parent(["div", "td", "article", "li", "tr"])
            listing = self._parse_auction_card(link, parent, auction_id, href)
            if listing:
                listings.append(listing)

        logger.info(f"Found {len(listings)} auction links on page")
        return listings

    def _parse_auction_card(self, link: Tag, parent: Optional[Tag], auction_id: str, href: str) -> Optional[AuctionListing]:
        """Parse a single auction card from the listing page."""
        try:
            # Build full URL
            if href.startswith("?"):
                source_url = f"{self.BASE_URL}/Default.aspx{href}"
            elif href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            elif href.startswith("http"):
                source_url = href
            else:
                source_url = f"{self.BASE_URL}/{href}"

            # Get text content
            link_text = link.get_text(" ", strip=True)
            parent_text = parent.get_text(" ", strip=True) if parent else link_text

            # Extract title
            title = self._extract_title(link_text, parent_text)
            if not title or len(title) < 5:
                return None

            # Extract price from card (format: "Oferta: $ 21000000,00")
            base_price, currency = self._extract_card_price(parent_text)

            # Extract date/time (format: "ju. 26 feb. 2026 - 11:33 Hs.")
            ends_at = self._extract_date(parent_text)

            # Extract location (format: "NEUQUEN - Neuquen")
            location = self._extract_card_location(parent_text)

            # Try to get image from card
            images = []
            if parent:
                img = parent.find("img")
                if img:
                    src = img.get("src") or img.get("data-src")
                    if src and not any(skip in src.lower() for skip in ['logo', 'icon', 'avatar']):
                        if src.startswith("/"):
                            src = f"{self.BASE_URL}{src}"
                        images.append(src)

            category = detect_category(title, "")

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title,
                description="",  # Will be enriched from detail page
                category=category,
                base_price=base_price,
                currency=currency,
                status="published",
                ends_at=ends_at,
                location=location,
                images=images,
            )

        except Exception as e:
            logger.error(f"Error parsing auction card {auction_id}: {e}")
            return None

    def _extract_title(self, link_text: str, parent_text: str) -> str:
        """Extract and clean the auction title."""
        # If link text is empty or just "ver detalle", extract from parent
        if not link_text or link_text.lower().strip() in ['', 'ver detalle']:
            # Extract title from parent text - usually at the start before "DOMINIO" or "ver detalle"
            if parent_text:
                # Try to get text before common delimiters
                for delimiter in ['DOMINIO', 'ver detalle', 'Lidera:', 'Oferta:']:
                    idx = parent_text.find(delimiter)
                    if idx > 5:  # Must have some text before delimiter
                        title = parent_text[:idx].strip()
                        break
                else:
                    # No delimiter found, take first 100 chars
                    title = parent_text[:100]
            else:
                title = ""
        else:
            title = link_text

        # Clean up common noise
        title = re.sub(r'^ver\s+detalle\s*', '', title, flags=re.I)
        title = re.sub(r'\bver\s+detalle\b', '', title, flags=re.I)
        title = re.sub(r'Oferta[:\s]*\$?\s*[\d.,]+', '', title)
        title = re.sub(r'Visitas[:\s]*\d+', '', title)
        title = re.sub(r'\d{1,2}:\d{2}\s*Hs\.?', '', title)
        title = re.sub(r'Lidera[:\s]*\$?\s*', '', title)

        # Clean whitespace
        title = ' '.join(title.split())

        if len(title) > 200:
            title = title[:197] + "..."

        return title.strip()

    def _extract_card_price(self, text: str) -> tuple[float, str]:
        """Extract price from card text."""
        currency = "ARS"

        # Check for USD indicators (u$s, USD, DOLAR, etc.)
        if re.search(r'u\$s|USD|DOLAR', text, re.I):
            currency = "USD"

        # Pattern 1: "u$s 88.400,00" or "U$S 88.400"
        match = re.search(r'u\$s\s*([\d.,]+)', text, re.I)
        if match:
            price_str = match.group(1)
            if "," in price_str:
                price_str = price_str.replace(".", "").replace(",", ".")
            else:
                price_str = price_str.replace(".", "")
            try:
                return float(price_str), "USD"
            except ValueError:
                pass

        # Pattern 2: "Oferta: $ 21000000,00" or "$ 1.234.567"
        match = re.search(r'(?:Oferta[:\s]*)?[\$]\s*([\d.,]+)', text)
        if match:
            price_str = match.group(1)
            # Handle Argentine format
            if "," in price_str:
                price_str = price_str.replace(".", "").replace(",", ".")
            else:
                price_str = price_str.replace(".", "")

            try:
                return float(price_str), currency
            except ValueError:
                pass

        return 0.0, currency

    def _extract_date(self, text: str) -> Optional[datetime]:
        """Extract auction date from text."""
        # Pattern: "ju. 26 feb. 2026 - 11:33 Hs."
        match = re.search(r'(\d{1,2})\s+(\w{3,})\.?\s+(\d{4})\s*[-–]\s*(\d{1,2}):(\d{2})', text, re.I)
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower().rstrip('.')
            year = int(match.group(3))
            hour = int(match.group(4))
            minute = int(match.group(5))

            month = self.MONTHS.get(month_name)
            if month:
                try:
                    return datetime(year, month, day, hour, minute)
                except ValueError:
                    pass

        # Simpler pattern: "dd/mm/yyyy"
        match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
        if match:
            try:
                return datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)))
            except ValueError:
                pass

        return None

    def _extract_card_location(self, text: str) -> dict:
        """Extract location from card text."""
        location = {"province": "", "city": ""}

        # Pattern: "NEUQUEN - Neuquen" at end of text
        match = re.search(r'([A-ZÁÉÍÓÚÑ]+)\s*[-–]\s*([A-Za-záéíóúñ]+)\s*$', text)
        if match:
            province = match.group(1).title()
            city = match.group(2).title()

            # Normalize province names
            province_map = {
                'Neuquen': 'Neuquén',
                'Cordoba': 'Córdoba',
                'Tucuman': 'Tucumán',
                'Entre Rios': 'Entre Ríos',
                'Rio Negro': 'Río Negro',
            }
            province = province_map.get(province, province)

            location["province"] = province
            location["city"] = city

        return location

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single listing element (required by BaseScraper)."""
        link = element.find("a", href=re.compile(r'mnu=detalle', re.I))
        if not link:
            return None

        href = link.get("href", "")
        sid_match = re.search(r'sid=(\d+)', href, re.I)
        lid_match = re.search(r'lid=(\d+)', href, re.I)

        if not sid_match or not lid_match:
            return None

        auction_id = f"{sid_match.group(1)}_{lid_match.group(1)}"
        return self._parse_auction_card(link, element, auction_id, href)

    async def _fetch_detail_page(self, listing: AuctionListing) -> AuctionListing:
        """Fetch and parse the detail page for complete data."""
        try:
            html = await self.fetch_html(listing.source_url)
            if not html:
                return listing

            soup = self.parse_html(html)
            page_text = soup.get_text(" ", strip=True)

            # Extract description
            description = self._extract_detail_description(soup)

            # Extract images from detail page
            images = self._extract_detail_images(soup)

            # Extract better price from detail page
            base_price, currency = self._extract_detail_price(soup, page_text)
            if base_price == 0:
                base_price = listing.base_price
                currency = listing.currency

            # Extract dates
            dates = self.extract_dates(page_text)
            ends_at = dates.get('ends_at') or listing.ends_at

            # Extract location
            location = self.extract_location(page_text)
            if not location.get("province"):
                location = listing.location

            # Find and download documents
            documents = self.find_document_links(soup, self.BASE_URL)
            doc_paths = []
            for doc in documents[:3]:
                path = await self.download_document(doc["url"], listing.id, doc["type"])
                if path:
                    doc_paths.append(path)

            extra = listing.extra.copy() if listing.extra else {}
            if doc_paths:
                extra["documents"] = doc_paths

            return AuctionListing(
                id=listing.id,
                source=listing.source,
                source_url=listing.source_url,
                title=listing.title,
                description=description or listing.description,
                category=listing.category,
                base_price=base_price,
                currency=currency,
                status=listing.status,
                starts_at=listing.starts_at,
                ends_at=ends_at,
                location=location,
                images=images if images else listing.images,
                extra=extra,
            )

        except Exception as e:
            logger.error(f"Error fetching detail page for {listing.id}: {e}")
            return listing

    def _extract_detail_description(self, soup) -> str:
        """Extract description from detail page."""
        # Look for description containers
        selectors = [
            ".descripcion", ".description", "[class*='descripcion']",
            ".detalle", ".detail", "[class*='detalle']",
            ".info-lote", ".lote-info", "blockquote"
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                desc = elem.get_text(" ", strip=True)
                desc = ' '.join(desc.split())
                if len(desc) > 30:
                    return desc[:2000]

        # Look for condition/damage info (common in vehicle auctions)
        condition_patterns = [
            r'USADO[,\s]+(.*?)(?:\.|$)',
            r'ESTADO[:\s]+(.*?)(?:\.|$)',
            r'CONDICION[:\s]+(.*?)(?:\.|$)',
        ]

        page_text = soup.get_text(" ", strip=True)
        for pattern in condition_patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                return match.group(0)[:500]

        return ""

    def _extract_detail_images(self, soup) -> list[str]:
        """Extract images from detail page."""
        images = []

        skip_patterns = ['logo', 'icon', 'avatar', 'share', 'social', 'facebook',
                        'twitter', 'whatsapp', 'banner', 'ad', 'spinner',
                        'home_agusti', 'agusti_subastas', 'empresas/']

        # Look for gallery images
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if not src:
                continue

            src_lower = src.lower()
            if any(skip in src_lower for skip in skip_patterns):
                continue

            # Skip small images (likely icons)
            width = img.get("width", "")
            height = img.get("height", "")
            try:
                if width and height and (int(width) < 50 or int(height) < 50):
                    continue
            except ValueError:
                pass

            # Make absolute URL
            if src.startswith("/"):
                src = f"{self.BASE_URL}{src}"
            elif not src.startswith("http"):
                src = f"{self.BASE_URL}/{src}"

            if src not in images:
                images.append(src)
                if len(images) >= 10:
                    break

        return images

    def _extract_detail_price(self, soup, page_text: str) -> tuple[float, str]:
        """Extract price from detail page."""
        currency = "ARS"

        # Check for USD indicators
        if re.search(r'u\$s|USD|DOLAR', page_text, re.I):
            currency = "USD"

        # Pattern for u$s prices first (e.g., "u$s 88.400,00")
        match = re.search(r'u\$s\s*([\d.,]+)', page_text, re.I)
        if match:
            price_str = match.group(1)
            if "," in price_str:
                price_str = price_str.replace(".", "").replace(",", ".")
            else:
                price_str = price_str.replace(".", "")
            try:
                price = float(price_str)
                if price > 100:
                    return price, "USD"
            except ValueError:
                pass

        # Look for base price patterns
        patterns = [
            r'(?:Base|Precio\s+Base)[:\s]*\$?\s*([\d.,]+)',
            r'(?:Oferta\s+Actual|Mejor\s+Oferta)[:\s]*\$?\s*([\d.,]+)',
            r'(?:Monto|Valor)[:\s]*\$?\s*([\d.,]+)',
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
                    if price > 1000:  # Filter tiny numbers
                        return price, currency
                except ValueError:
                    pass

        return 0.0, currency

    async def _enrich_listings(self, listings: list[AuctionListing]) -> list[AuctionListing]:
        """Fetch detail pages to enrich all listings."""
        enriched = []
        new_count = 0
        opportunity_count = 0

        for listing in listings:
            is_new = self.is_new_listing(listing.id)

            # Always fetch detail for new listings or those missing data
            if is_new or not listing.description or listing.base_price == 0:
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
                    logger.info(f"New Agusti listing: {listing.title[:50]}...")
            else:
                # Still analyze existing listings for opportunities
                analyzed = self.analyze_opportunity(listing)
                enriched.append(analyzed)
                if analyzed.extra.get("is_opportunity"):
                    opportunity_count += 1

        if new_count > 0:
            logger.info(f"Found {new_count} NEW listings in Agusti Subastas")
        if opportunity_count > 0:
            logger.info(f"Found {opportunity_count} OPPORTUNITIES in Agusti Subastas")

        return enriched
