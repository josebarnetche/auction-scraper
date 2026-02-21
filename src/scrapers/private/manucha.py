"""Manucha Subastas auction scraper with detail page support."""

import re
import logging
import asyncio
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class ManuchaScraper(BaseScraper):
    """Scraper for Manucha Subastas auctions."""

    SOURCE_NAME = "manucha"
    BASE_URL = "https://manuchasubastas.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings."""
        all_listings = []

        paths = ["/", "/subastas", "/proximas-subastas"]

        for path in paths:
            url = f"{self.BASE_URL}{path}"
            logger.info(f"Scraping Manucha: {url}")

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

        logger.info(f"Found {len(unique)} Manucha listings, enriching with detail pages...")
        enriched = await self._enrich_listings(unique)

        with_prices = sum(1 for l in enriched if l.base_price > 0)
        logger.info(f"Manucha: {with_prices}/{len(enriched)} listings have prices")

        return enriched

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse listings from page."""
        listings = []

        cards = soup.select(".subasta, .auction, .card, .item, article, [class*='subasta']")

        for card in cards:
            listing = self.parse_listing(card)
            if listing:
                listings.append(listing)

        return listings

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single auction element."""
        try:
            link = element.find("a", href=True)
            if not link:
                return None

            href = link.get("href", "")
            id_match = re.search(r"(\d+)", href)
            auction_id = id_match.group(1) if id_match else str(hash(href) % 10**8)

            if href.startswith("http"):
                source_url = href
            elif href.startswith("/"):
                source_url = f"{self.BASE_URL}{href}"
            else:
                source_url = f"{self.BASE_URL}/{href}"

            title_elem = element.find(["h2", "h3", "h4", ".title"])
            title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

            if not title or len(title) < 3:
                return None

            desc_elem = element.find([".description", "p"])
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            price_text = element.get_text()
            base_price, currency = self._parse_price(price_text)

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
            logger.error(f"Error parsing Manucha listing: {e}")
            return None

    def _parse_price(self, text: str) -> tuple[float, str]:
        """Parse price from text."""
        currency = "ARS"
        if "USD" in text.upper() or "U$S" in text.upper():
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

            # Extract description
            description = ""
            selectors = [".descripcion", ".description", "[class*='descripcion']",
                        ".detalle", ".detail", "article", ".content"]
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
                        description = text[:2000]
                        break

            # Extract images
            images = []
            skip_patterns = ['logo', 'icon', 'avatar', 'share', 'social', 'banner', 'ad']
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

            # Extract price from detail page
            base_price, currency = self._parse_price(page_text)
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
                location=location,
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
                    logger.info(f"New Manucha listing: {listing.title[:50]}...")
            else:
                # Still analyze existing listings for opportunities
                analyzed = self.analyze_opportunity(listing)
                enriched.append(analyzed)
                if analyzed.extra.get("is_opportunity"):
                    opportunity_count += 1

        if new_count > 0:
            logger.info(f"Found {new_count} NEW listings in Manucha")
        if opportunity_count > 0:
            logger.info(f"Found {opportunity_count} OPPORTUNITIES in Manucha")

        return enriched
