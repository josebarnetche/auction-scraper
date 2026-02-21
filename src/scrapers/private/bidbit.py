"""BidBit auction scraper with full detail page support."""

import re
import logging
import asyncio
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class BidBitScraper(BaseScraper):
    """Scraper for BidBit auctions with detail page enrichment."""

    SOURCE_NAME = "bidbit"
    BASE_URL = "https://www.bidbit.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings with detail page enrichment."""
        all_listings = []

        # Main auction pages
        paths = ["/", "/subastas", "/subastas-activas", "/proximas-subastas"]

        for path in paths:
            url = f"{self.BASE_URL}{path}"
            logger.info(f"Scraping BidBit: {url}")

            html = await self.fetch_html(url)
            if not html:
                continue

            soup = self.parse_html(html)
            listings = self._parse_listings_page(soup)
            all_listings.extend(listings)

        # Deduplicate
        seen = set()
        unique = []
        for listing in all_listings:
            if listing.id not in seen:
                seen.add(listing.id)
                unique.append(listing)

        logger.info(f"Found {len(unique)} BidBit listings, enriching with detail pages...")
        enriched = await self._enrich_listings(unique)

        with_prices = sum(1 for l in enriched if l.base_price > 0)
        logger.info(f"BidBit: {with_prices}/{len(enriched)} listings have prices")

        return enriched

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse listings from page."""
        listings = []

        # Find auction links - common patterns
        auction_links = soup.find_all("a", href=re.compile(r'/subasta[s]?/|/auction|/remate', re.I))

        seen_ids = set()
        for link in auction_links:
            href = link.get("href", "")

            # Skip invalid links
            if any(skip in href.lower() for skip in ['login', 'register', 'terms', 'contact', 'about']):
                continue

            # Extract ID
            id_match = re.search(r'/(\d+)|[?&]id=(\d+)', href)
            if id_match:
                auction_id = id_match.group(1) or id_match.group(2)
            else:
                # Use URL hash as ID
                auction_id = str(abs(hash(href)) % 10**8)

            if auction_id in seen_ids:
                continue
            seen_ids.add(auction_id)

            # Get parent container
            parent = link.find_parent(["div", "article", "li", "section"])

            listing = self._parse_auction_card(link, parent, auction_id, href)
            if listing:
                listings.append(listing)

        # Also look for card-based layouts
        cards = soup.select(".auction-card, .product-card, .item-card, .card, [class*='subasta']")
        for card in cards:
            link = card.find("a", href=True)
            if not link:
                continue

            href = link.get("href", "")
            id_match = re.search(r'/(\d+)|[?&]id=(\d+)', href)
            auction_id = (id_match.group(1) or id_match.group(2)) if id_match else str(abs(hash(href)) % 10**8)

            if auction_id in seen_ids:
                continue
            seen_ids.add(auction_id)

            listing = self._parse_auction_card(link, card, auction_id, href)
            if listing:
                listings.append(listing)

        return listings

    def _parse_auction_card(self, link: Tag, parent: Optional[Tag], auction_id: str, href: str) -> Optional[AuctionListing]:
        """Parse a single auction card."""
        try:
            # Build full URL
            if href.startswith("http"):
                source_url = href
            elif href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            else:
                source_url = f"{self.BASE_URL}/{href}"

            # Get text content
            link_text = link.get_text(" ", strip=True)
            parent_text = parent.get_text(" ", strip=True) if parent else link_text

            # Extract title
            title = ""
            if parent:
                title_elem = parent.find(["h2", "h3", "h4", "h5"])
                if title_elem:
                    title = title_elem.get_text(strip=True)

            if not title:
                title = link_text

            # Clean title
            title = re.sub(r'\bver\s+más\b', '', title, flags=re.I)
            title = re.sub(r'\bver\s+detalle\b', '', title, flags=re.I)
            title = ' '.join(title.split())

            if not title or len(title) < 5:
                return None

            # Extract price from card
            base_price, currency = self.extract_price(parent_text)

            # Extract date
            dates = self.extract_dates(parent_text)
            ends_at = dates.get('ends_at')

            # Extract image
            images = []
            if parent:
                img = parent.find("img")
                if img:
                    src = img.get("src") or img.get("data-src")
                    if src and not any(skip in src.lower() for skip in ['logo', 'icon', 'avatar']):
                        if src.startswith("/"):
                            src = f"{self.BASE_URL}{src}"
                        images.append(src)

            # Extract location
            location = self.extract_location(parent_text)

            category = detect_category(title, parent_text[:500] if parent_text else "")

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title[:200],
                description="",  # Will be enriched
                category=category,
                base_price=base_price,
                currency=currency,
                status="published",
                ends_at=ends_at,
                location=location,
                images=images,
            )

        except Exception as e:
            logger.error(f"Error parsing BidBit card {auction_id}: {e}")
            return None

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single auction element (required by base class)."""
        link = element.find("a", href=True)
        if not link:
            return None

        href = link.get("href", "")
        id_match = re.search(r'/(\d+)|[?&]id=(\d+)', href)
        auction_id = (id_match.group(1) or id_match.group(2)) if id_match else str(abs(hash(href)) % 10**8)

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
            description = self._extract_description(soup)

            # Extract images
            images = self._extract_images(soup)

            # Extract price (override if found)
            base_price, currency = self._extract_detail_price(soup, page_text)
            if base_price == 0:
                base_price = listing.base_price
                currency = listing.currency

            # Extract dates
            dates = self.extract_dates(page_text)
            ends_at = dates.get('ends_at') or listing.ends_at
            starts_at = dates.get('starts_at') or listing.starts_at

            # Extract location
            location = self.extract_location(page_text)
            if not location.get("province"):
                location = listing.location

            # Find documents
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
                starts_at=starts_at,
                ends_at=ends_at,
                location=location,
                images=images if images else listing.images,
                extra=extra,
            )

        except Exception as e:
            logger.error(f"Error fetching detail page for {listing.id}: {e}")
            return listing

    def _extract_description(self, soup) -> str:
        """Extract description from detail page."""
        selectors = [
            ".descripcion", ".description", "[class*='descripcion']",
            ".detalle", ".detail", "[class*='detalle']",
            ".info", ".content", "article", "blockquote"
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                desc = elem.get_text(" ", strip=True)
                desc = ' '.join(desc.split())
                if len(desc) > 30:
                    return desc[:2000]

        # Try paragraphs
        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if len(text) > 100:
                return text[:2000]

        return ""

    def _extract_images(self, soup) -> list[str]:
        """Extract images from detail page."""
        images = []
        skip_patterns = ['logo', 'icon', 'avatar', 'share', 'social', 'banner', 'ad', 'spinner']

        # Look for gallery images
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy")
            if not src:
                continue

            src_lower = src.lower()
            if any(skip in src_lower for skip in skip_patterns):
                continue

            # Skip small images
            width = img.get("width", "")
            height = img.get("height", "")
            try:
                if width and height and (int(width) < 50 or int(height) < 50):
                    continue
            except ValueError:
                pass

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

        if re.search(r'USD|U\$S|DOLAR|DÓLAR', page_text, re.I):
            currency = "USD"

        # Look for price elements
        price_selectors = [
            ".precio", ".price", "[class*='precio']", "[class*='price']",
            ".base", ".monto", "[class*='base']"
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
                        price = float(price_str)
                        if price > 1000:
                            return price, currency
                    except ValueError:
                        pass

        # Look for patterns in page text
        patterns = [
            r'(?:Base|Precio)[:\s]*\$?\s*([\d.,]+)',
            r'(?:Valor|Monto)[:\s]*\$?\s*([\d.,]+)',
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
                    if price > 1000:
                        return price, currency
                except ValueError:
                    pass

        return 0.0, currency

    async def _enrich_listings(self, listings: list[AuctionListing]) -> list[AuctionListing]:
        """Fetch detail pages for all listings."""
        enriched = []
        new_count = 0
        opportunity_count = 0

        for listing in listings:
            is_new = self.is_new_listing(listing.id)

            # Fetch detail for new listings or those missing data
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
                    logger.info(f"New BidBit listing: {listing.title[:50]}...")
            else:
                # Still analyze existing listings for opportunities
                analyzed = self.analyze_opportunity(listing)
                enriched.append(analyzed)
                if analyzed.extra.get("is_opportunity"):
                    opportunity_count += 1

        if new_count > 0:
            logger.info(f"Found {new_count} NEW listings in BidBit")
        if opportunity_count > 0:
            logger.info(f"Found {opportunity_count} OPPORTUNITIES in BidBit")

        return enriched
