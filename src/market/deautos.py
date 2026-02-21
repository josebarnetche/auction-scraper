"""DeAutos.com scraper for real vehicle market prices."""

import re
import logging
import asyncio
from typing import Optional
from dataclasses import dataclass
from urllib.parse import quote_plus
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class VehiclePrice:
    """Vehicle market price data."""
    brand: str
    model: str
    year: int
    price_usd: float
    price_ars: float
    source: str
    source_url: str
    kilometers: Optional[int] = None
    condition: str = "used"


class DeAutosScraper:
    """Scraper for DeAutos.com vehicle prices."""

    BASE_URL = "https://www.deautos.com"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    }

    # Common vehicle brands for search
    BRANDS = [
        "ford", "chevrolet", "toyota", "volkswagen", "renault", "fiat",
        "peugeot", "citroen", "mercedes-benz", "bmw", "audi", "honda",
        "nissan", "hyundai", "kia", "jeep", "dodge", "ram", "mitsubishi"
    ]

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=30,
            headers=self.HEADERS,
            follow_redirects=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def search_vehicle(
        self,
        brand: str,
        model: str = "",
        year: Optional[int] = None,
        limit: int = 10
    ) -> list[VehiclePrice]:
        """Search for vehicle prices."""
        # Build search query
        query_parts = [brand]
        if model:
            query_parts.append(model)
        if year:
            query_parts.append(str(year))

        query = " ".join(query_parts)
        encoded_query = quote_plus(query)

        url = f"{self.BASE_URL}/autos/buscar?q={encoded_query}"

        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                logger.warning(f"DeAutos returned {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "lxml")
            return self._parse_results(soup, brand, model, year, limit)

        except Exception as e:
            logger.error(f"DeAutos search error: {e}")
            return []

    def _parse_results(
        self,
        soup: BeautifulSoup,
        brand: str,
        model: str,
        year: Optional[int],
        limit: int
    ) -> list[VehiclePrice]:
        """Parse search results from HTML."""
        prices = []

        # Find listing cards
        cards = soup.select(".listing-card, .card-container, [class*='listing'], article")

        for card in cards[:limit * 2]:  # Get more to filter
            try:
                price_data = self._parse_card(card, brand, model, year)
                if price_data:
                    prices.append(price_data)
                    if len(prices) >= limit:
                        break
            except Exception as e:
                logger.debug(f"Error parsing card: {e}")
                continue

        return prices

    def _parse_card(
        self,
        card,
        search_brand: str,
        search_model: str,
        search_year: Optional[int]
    ) -> Optional[VehiclePrice]:
        """Parse a single listing card."""
        # Find title
        title_elem = card.select_one("h2, h3, .title, [class*='title']")
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)

        # Find price
        price_elem = card.select_one(".price, [class*='price'], .amount")
        if not price_elem:
            return None

        price_text = price_elem.get_text(strip=True)
        price_usd, price_ars = self._parse_price(price_text)

        if price_usd <= 0 and price_ars <= 0:
            return None

        # Find link
        link_elem = card.select_one("a[href*='/autos/']")
        source_url = ""
        if link_elem:
            href = link_elem.get("href", "")
            source_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        # Extract vehicle info from title
        brand, model, year = self._extract_vehicle_info(title)

        if not brand:
            brand = search_brand
        if not model:
            model = search_model
        if not year and search_year:
            year = search_year

        # Find kilometers
        km = None
        km_elem = card.select_one("[class*='km'], [class*='kilometer']")
        if km_elem:
            km_match = re.search(r"([\d.,]+)\s*km", km_elem.get_text(), re.I)
            if km_match:
                try:
                    km = int(km_match.group(1).replace(".", "").replace(",", ""))
                except ValueError:
                    pass

        return VehiclePrice(
            brand=brand.title() if brand else "",
            model=model.title() if model else "",
            year=year or 0,
            price_usd=price_usd,
            price_ars=price_ars,
            source="deautos",
            source_url=source_url,
            kilometers=km,
            condition="used"
        )

    def _parse_price(self, text: str) -> tuple[float, float]:
        """Parse price from text. Returns (USD, ARS)."""
        text = text.upper()

        # Check currency
        is_usd = "USD" in text or "U$S" in text or "US$" in text or "DÓLAR" in text

        # Extract number
        price_match = re.search(r"[\d.,]+", text.replace(" ", ""))
        if not price_match:
            return 0.0, 0.0

        price_str = price_match.group()
        # Handle Argentine format (1.234.567 or 1,234,567)
        if "." in price_str and "," in price_str:
            # Format: 1.234,56 (European) or 1,234.56 (US)
            if price_str.rfind(",") > price_str.rfind("."):
                price_str = price_str.replace(".", "").replace(",", ".")
            else:
                price_str = price_str.replace(",", "")
        elif price_str.count(".") > 1:
            # Format: 1.234.567 (thousand separators)
            price_str = price_str.replace(".", "")
        elif price_str.count(",") > 1:
            price_str = price_str.replace(",", "")

        try:
            price = float(price_str)
        except ValueError:
            return 0.0, 0.0

        if is_usd:
            return price, 0.0
        else:
            return 0.0, price

    def _extract_vehicle_info(self, title: str) -> tuple[str, str, int]:
        """Extract brand, model, year from title."""
        title_lower = title.lower()

        brand = ""
        model = ""
        year = 0

        # Find brand
        for b in self.BRANDS:
            if b in title_lower:
                brand = b
                break

        # Find year
        year_match = re.search(r"\b(19|20)\d{2}\b", title)
        if year_match:
            year = int(year_match.group())

        # Model is typically after brand
        if brand:
            brand_pos = title_lower.find(brand)
            after_brand = title[brand_pos + len(brand):].strip()
            model_parts = after_brand.split()
            if model_parts:
                # Take first 2 words as model
                model = " ".join(model_parts[:2])
                # Remove year if in model
                model = re.sub(r"\b(19|20)\d{2}\b", "", model).strip()

        return brand, model, year

    async def get_median_price(
        self,
        brand: str,
        model: str = "",
        year: Optional[int] = None
    ) -> Optional[float]:
        """Get median USD price for a vehicle."""
        prices = await self.search_vehicle(brand, model, year, limit=10)

        if not prices:
            return None

        # Get USD prices (convert ARS if needed using approximate rate)
        usd_prices = []
        BLUE_DOLLAR_RATE = 1200  # Approximate, should use real rate

        for p in prices:
            if p.price_usd > 0:
                usd_prices.append(p.price_usd)
            elif p.price_ars > 0:
                usd_prices.append(p.price_ars / BLUE_DOLLAR_RATE)

        if not usd_prices:
            return None

        # Return median
        usd_prices.sort()
        mid = len(usd_prices) // 2
        if len(usd_prices) % 2 == 0:
            return (usd_prices[mid - 1] + usd_prices[mid]) / 2
        return usd_prices[mid]
