"""Remates Zárate scraper - Industrial equipment and vehicles with detail page support."""

import re
import logging
import asyncio
from datetime import datetime
from typing import Optional

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class ZarateScraper(BaseScraper):
    """Scraper for Remates Zárate (70+ years of auctions) with detail page enrichment."""

    SOURCE_NAME = "zarate"
    BASE_URL = "https://remateszarate.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings with detail page enrichment."""
        all_listings = []

        pages = [
            "/",
            "/remates",
            "/subastas",
            "/proximos",
        ]

        for path in pages:
            url = f"{self.BASE_URL}{path}"
            logger.info(f"Scraping Zárate: {url}")

            html = await self.fetch_html(url)
            if not html:
                continue

            soup = self.parse_html(html)
            listings = self._parse_page(soup)
            all_listings.extend(listings)

        # Deduplicate
        seen = set()
        unique = []
        for listing in all_listings:
            if listing.id not in seen:
                seen.add(listing.id)
                unique.append(listing)

        logger.info(f"Found {len(unique)} Zárate listings, enriching with detail pages...")
        enriched = await self._enrich_listings(unique)

        with_prices = sum(1 for l in enriched if l.base_price > 0)
        logger.info(f"Zárate: {with_prices}/{len(enriched)} listings have prices")

        return enriched

    def _parse_page(self, soup) -> list[AuctionListing]:
        """Parse listings from page."""
        listings = []

        # Look for auction links
        links = soup.find_all("a", href=True)
        seen = set()

        for link in links:
            href = link.get("href", "")

            # Skip non-auction links
            if not href or href == "#" or href == "/":
                continue
            if any(x in href.lower() for x in ['mailto:', 'tel:', 'javascript:', 'facebook', 'instagram', 'youtube']):
                continue

            # Look for auction-like URLs
            if re.search(r'/(remate|subasta|lote|producto|item)[s]?[/-]', href, re.I) or \
               re.search(r'/\d+/?$', href):
                if href in seen:
                    continue
                seen.add(href)

                listing = self._parse_link(link, href)
                if listing:
                    listings.append(listing)

        return listings

    def _parse_link(self, link, href: str) -> Optional[AuctionListing]:
        """Parse auction from link."""
        try:
            # Extract ID
            id_match = re.search(r'[/-](\d+)', href)
            auction_id = id_match.group(1) if id_match else str(hash(href) % 10**8)

            # Build URL
            if href.startswith("http"):
                source_url = href
            elif href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            else:
                source_url = f"{self.BASE_URL}/{href}"

            # Get title
            title = link.get_text(strip=True)
            parent = link.find_parent()
            parent_text = parent.get_text(" ", strip=True) if parent else ""

            if not title or len(title) < 5:
                if parent_text:
                    title = parent_text[:100]

            if not title or len(title) < 5:
                return None

            # Extract price from card
            base_price, currency = self.extract_price(parent_text)

            # Extract date
            dates = self.extract_dates(parent_text)
            ends_at = dates.get('ends_at')

            # Image
            images = []
            img = link.find("img")
            if not img and parent:
                img = parent.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src:
                    if src.startswith("/"):
                        src = f"{self.BASE_URL}{src}"
                    elif not src.startswith("http"):
                        src = f"{self.BASE_URL}/{src}"
                    images.append(src)

            # Location
            location = self.extract_location(parent_text)
            if not location.get("province"):
                location = {"province": "Buenos Aires", "city": "Zárate"}

            category = detect_category(title, parent_text)

            return AuctionListing(
                id=self.generate_id(auction_id),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title,
                description="",
                category=category,
                base_price=base_price,
                currency=currency,
                status="published",
                ends_at=ends_at,
                location=location,
                images=images,
            )
        except Exception as e:
            logger.error(f"Error parsing Zárate link: {e}")
            return None

    async def _fetch_detail_page(self, listing: AuctionListing) -> AuctionListing:
        """Fetch and parse the detail page for complete data."""
        try:
            html = await self.fetch_html(listing.source_url)
            if not html:
                return listing

            soup = self.parse_html(html)
            page_text = soup.get_text(" ", strip=True)

            # Extract description
            description = ""
            selectors = [".descripcion", ".description", ".detalle", ".content", "article", "blockquote"]
            for selector in selectors:
                elem = soup.select_one(selector)
                if elem:
                    description = elem.get_text(" ", strip=True)
                    description = ' '.join(description.split())
                    if len(description) > 30:
                        break

            if not description:
                for p in soup.find_all("p"):
                    text = p.get_text(" ", strip=True)
                    if len(text) > 100:
                        description = text[:1000]
                        break

            # Extract images
            images = []
            skip_patterns = ['logo', 'icon', 'avatar', 'share', 'social', 'banner']
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src")
                if not src:
                    continue
                if any(skip in src.lower() for skip in skip_patterns):
                    continue

                if src.startswith("/"):
                    src = f"{self.BASE_URL}{src}"
                elif not src.startswith("http"):
                    src = f"{self.BASE_URL}/{src}"

                if src not in images:
                    images.append(src)
                    if len(images) >= 10:
                        break

            # Extract price
            base_price, currency = self.extract_price(page_text)
            if base_price == 0:
                base_price = listing.base_price
                currency = listing.currency

            # Extract dates
            dates = self.extract_dates(page_text)
            ends_at = dates.get('ends_at') or listing.ends_at

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
                description=description[:2000] or listing.description,
                category=listing.category,
                base_price=base_price,
                currency=currency,
                status=listing.status,
                starts_at=listing.starts_at,
                ends_at=ends_at,
                location=listing.location,
                images=images if images else listing.images,
                extra=extra,
            )

        except Exception as e:
            logger.error(f"Error fetching detail page for {listing.id}: {e}")
            return listing

    async def _enrich_listings(self, listings: list[AuctionListing]) -> list[AuctionListing]:
        """Fetch detail pages for all listings."""
        enriched = []
        new_count = 0
        opportunity_count = 0

        for listing in listings:
            is_new = self.is_new_listing(listing.id)

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
                    logger.info(f"New Zárate listing: {listing.title[:50]}...")
            else:
                # Still analyze existing listings for opportunities
                analyzed = self.analyze_opportunity(listing)
                enriched.append(analyzed)
                if analyzed.extra.get("is_opportunity"):
                    opportunity_count += 1

        if new_count > 0:
            logger.info(f"Found {new_count} NEW listings in Zárate")
        if opportunity_count > 0:
            logger.info(f"Found {opportunity_count} OPPORTUNITIES in Zárate")

        return enriched

    def parse_listing(self, element, status: str = "published") -> Optional[AuctionListing]:
        """Required by base class."""
        return None
