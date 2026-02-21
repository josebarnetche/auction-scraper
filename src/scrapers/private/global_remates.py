"""Global Remates auction scraper."""

import re
import logging
from datetime import datetime
from typing import Optional
from bs4 import Tag

from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

logger = logging.getLogger(__name__)


class GlobalRematesScraper(BaseScraper):
    """Scraper for Global Remates auctions."""

    SOURCE_NAME = "global_remates"
    BASE_URL = "https://www.globalremates.com.ar"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        """Scrape all auction listings."""
        all_listings = []

        # Main page has the listings
        url = self.BASE_URL
        logger.info(f"Scraping Global Remates: {url}")

        html = await self.fetch_html(url)
        if html:
            soup = self.parse_html(html)
            listings = self._parse_listings_page(soup)
            all_listings.extend(listings)

        # Also try the default.aspx page
        url2 = f"{self.BASE_URL}/default.aspx"
        html2 = await self.fetch_html(url2)
        if html2:
            soup2 = self.parse_html(html2)
            listings2 = self._parse_listings_page(soup2)
            all_listings.extend(listings2)

        # Try auction catalog page
        url3 = f"{self.BASE_URL}/AuctionCatalog.aspx"
        html3 = await self.fetch_html(url3)
        if html3:
            soup3 = self.parse_html(html3)
            listings3 = self._parse_listings_page(soup3)
            all_listings.extend(listings3)

        # Deduplicate
        seen = set()
        unique = []
        for listing in all_listings:
            if listing.id not in seen:
                seen.add(listing.id)
                unique.append(listing)

        logger.info(f"Found {len(unique)} Global Remates listings")
        return unique

    def _parse_listings_page(self, soup) -> list[AuctionListing]:
        """Parse listings from page."""
        listings = []

        # Find all auction links with pattern AuctionDetails.aspx?id=XXX
        auction_links = soup.find_all("a", href=re.compile(r'AuctionDetails\.aspx\?id=\d+', re.I))

        seen_ids = set()
        for link in auction_links:
            href = link.get("href", "")
            match = re.search(r'id=(\d+)', href, re.I)
            if not match:
                continue

            auction_id = match.group(1)
            if auction_id in seen_ids:
                continue
            seen_ids.add(auction_id)

            listing = self._parse_auction_link(link, auction_id)
            if listing:
                listings.append(listing)

        # Also find lot links
        lot_links = soup.find_all("a", href=re.compile(r'LotDetails\.aspx\?id=\d+', re.I))
        for link in lot_links:
            href = link.get("href", "")
            match = re.search(r'id=(\d+)', href, re.I)
            if not match:
                continue

            lot_id = match.group(1)
            lot_key = f"lot_{lot_id}"
            if lot_key in seen_ids:
                continue
            seen_ids.add(lot_key)

            listing = self._parse_lot_link(link, lot_id)
            if listing:
                listings.append(listing)

        # Also look for li items with auction data
        li_items = soup.find_all("li")
        for li in li_items:
            # Check if it looks like an auction item
            link = li.find("a", href=re.compile(r'(AuctionDetails|LotDetails)\.aspx', re.I))
            if not link:
                continue

            href = link.get("href", "")
            match = re.search(r'id=(\d+)', href)
            if not match:
                continue

            item_id = match.group(1)
            item_key = f"li_{item_id}"
            if item_key in seen_ids:
                continue
            seen_ids.add(item_key)

            listing = self._parse_li_item(li, item_id, href)
            if listing:
                listings.append(listing)

        return listings

    def _parse_auction_link(self, link, auction_id: str) -> Optional[AuctionListing]:
        """Parse an auction link."""
        try:
            source_url = f"{self.BASE_URL}/AuctionDetails.aspx?id={auction_id}"

            # Get title from link or parent
            title = link.get_text(strip=True)
            if len(title) < 5:
                parent = link.find_parent()
                if parent:
                    title = parent.get_text(strip=True)[:150]

            if not title or len(title) < 5:
                return None

            # Try to find image
            images = []
            parent = link.find_parent("li") or link.find_parent("div")
            if parent:
                img = parent.find("img")
                if img:
                    src = img.get("src") or img.get("data-src")
                    if src:
                        if src.startswith("/"):
                            src = f"{self.BASE_URL}{src}"
                        elif not src.startswith("http"):
                            src = f"{self.BASE_URL}/{src}"
                        if "status" not in src.lower():
                            images.append(src)

            category = detect_category(title, "")

            return AuctionListing(
                id=self.generate_id(f"auction_{auction_id}"),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title[:200],
                description="",
                category=category,
                base_price=0.0,
                currency="ARS",
                status="published",
                images=images,
            )
        except Exception as e:
            logger.error(f"Error parsing Global Remates auction link: {e}")
            return None

    def _parse_lot_link(self, link, lot_id: str) -> Optional[AuctionListing]:
        """Parse a lot link."""
        try:
            source_url = f"{self.BASE_URL}/LotDetails.aspx?id={lot_id}"

            title = link.get_text(strip=True)
            if len(title) < 5:
                parent = link.find_parent()
                if parent:
                    title = parent.get_text(strip=True)[:150]

            if not title or len(title) < 5:
                return None

            # Try to find image
            images = []
            parent = link.find_parent("li") or link.find_parent("div")
            if parent:
                img = parent.find("img")
                if img:
                    src = img.get("src") or img.get("data-src")
                    if src:
                        if src.startswith("/"):
                            src = f"{self.BASE_URL}{src}"
                        elif not src.startswith("http"):
                            src = f"{self.BASE_URL}/{src}"
                        if "status" not in src.lower():
                            images.append(src)

            # Try to extract price
            price = 0.0
            if parent:
                text = parent.get_text()
                price_match = re.search(r'\$\s*([\d.,]+)', text)
                if price_match:
                    price_str = price_match.group(1).replace('.', '').replace(',', '.')
                    try:
                        price = float(price_str)
                    except ValueError:
                        pass

            category = detect_category(title, "")

            return AuctionListing(
                id=self.generate_id(f"lot_{lot_id}"),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title[:200],
                description="",
                category=category,
                base_price=price,
                currency="ARS",
                status="published",
                images=images,
            )
        except Exception as e:
            logger.error(f"Error parsing Global Remates lot link: {e}")
            return None

    def _parse_li_item(self, li, item_id: str, href: str) -> Optional[AuctionListing]:
        """Parse an li item containing auction data."""
        try:
            # Build URL
            if "AuctionDetails" in href:
                source_url = f"{self.BASE_URL}/AuctionDetails.aspx?id={item_id}"
                id_prefix = "auction"
            else:
                source_url = f"{self.BASE_URL}/LotDetails.aspx?id={item_id}"
                id_prefix = "lot"

            # Get all text
            text = li.get_text(" ", strip=True)
            if len(text) < 10:
                return None

            # Extract title - usually first significant text
            lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 5]
            title = lines[0] if lines else text[:100]

            # Clean title
            title = re.sub(r'\s+', ' ', title).strip()
            if len(title) < 5:
                return None

            # Extract price
            price = 0.0
            price_match = re.search(r'\$\s*([\d.,]+)', text)
            if price_match:
                price_str = price_match.group(1).replace('.', '').replace(',', '.')
                try:
                    price = float(price_str)
                except ValueError:
                    pass

            # Extract image
            images = []
            img = li.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src and "status" not in src.lower():
                    if src.startswith("/"):
                        src = f"{self.BASE_URL}{src}"
                    elif not src.startswith("http"):
                        src = f"{self.BASE_URL}/{src}"
                    images.append(src)

            category = detect_category(title, text)

            return AuctionListing(
                id=self.generate_id(f"{id_prefix}_{item_id}"),
                source=self.SOURCE_NAME,
                source_url=source_url,
                title=title[:200],
                description=text[:300] if len(text) > 200 else "",
                category=category,
                base_price=price,
                currency="ARS",
                status="published",
                images=images,
            )
        except Exception as e:
            logger.error(f"Error parsing Global Remates li item: {e}")
            return None

    def parse_listing(self, element: Tag, status: str = "published") -> Optional[AuctionListing]:
        """Parse a single auction element."""
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
