"""ZonaProp scraper for real estate market prices."""

import re
import logging
from typing import Optional
from dataclasses import dataclass
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class RealEstatePrice:
    """Real estate market price data."""
    property_type: str  # departamento, casa, terreno, local
    location: str
    price_usd: float
    price_ars: float
    area_m2: Optional[int]
    rooms: Optional[int]
    source: str
    source_url: str


class ZonaPropScraper:
    """Scraper for ZonaProp real estate prices."""

    BASE_URL = "https://www.zonaprop.com.ar"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9",
    }

    PROPERTY_TYPES = {
        "departamento": "departamentos",
        "depto": "departamentos",
        "casa": "casas",
        "terreno": "terrenos",
        "lote": "terrenos",
        "local": "locales-comerciales",
        "oficina": "oficinas",
        "campo": "campos",
        "cochera": "cocheras",
        "galpon": "galpones",
    }

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

    async def search_property(
        self,
        property_type: str,
        location: str = "",
        min_area: Optional[int] = None,
        max_area: Optional[int] = None,
        limit: int = 10
    ) -> list[RealEstatePrice]:
        """Search for real estate prices."""
        # Normalize property type
        prop_slug = self.PROPERTY_TYPES.get(
            property_type.lower(),
            "propiedades"
        )

        # Build URL
        if location:
            location_slug = self._slugify(location)
            url = f"{self.BASE_URL}/{prop_slug}-venta-{location_slug}.html"
        else:
            url = f"{self.BASE_URL}/{prop_slug}-venta.html"

        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                logger.warning(f"ZonaProp returned {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "lxml")
            return self._parse_results(soup, property_type, location, limit)

        except Exception as e:
            logger.error(f"ZonaProp search error: {e}")
            return []

    def _slugify(self, text: str) -> str:
        """Convert location to URL slug."""
        # Common location mappings
        mappings = {
            "capital federal": "capital-federal",
            "caba": "capital-federal",
            "buenos aires": "buenos-aires",
            "gba": "gran-buenos-aires",
            "cordoba": "cordoba",
            "rosario": "rosario",
            "mendoza": "mendoza",
        }

        text_lower = text.lower().strip()
        if text_lower in mappings:
            return mappings[text_lower]

        return text_lower.replace(" ", "-")

    def _parse_results(
        self,
        soup: BeautifulSoup,
        property_type: str,
        location: str,
        limit: int
    ) -> list[RealEstatePrice]:
        """Parse search results."""
        prices = []

        # Find listing cards
        cards = soup.select(
            "[class*='posting'], [class*='listing'], "
            "[data-posting-type], article, .property-card"
        )

        for card in cards[:limit * 2]:
            try:
                price_data = self._parse_card(card, property_type, location)
                if price_data:
                    prices.append(price_data)
                    if len(prices) >= limit:
                        break
            except Exception as e:
                logger.debug(f"Error parsing ZonaProp card: {e}")

        return prices

    def _parse_card(
        self,
        card,
        property_type: str,
        search_location: str
    ) -> Optional[RealEstatePrice]:
        """Parse a single listing card."""
        # Find price
        price_elem = card.select_one(
            "[class*='price'], [class*='Price'], "
            "[data-price], .precio"
        )
        if not price_elem:
            return None

        price_text = price_elem.get_text(strip=True)
        price_usd, price_ars = self._parse_price(price_text)

        if price_usd <= 0 and price_ars <= 0:
            return None

        # Find location
        location_elem = card.select_one(
            "[class*='location'], [class*='direccion'], "
            "[class*='address'], .ubicacion"
        )
        location = search_location
        if location_elem:
            location = location_elem.get_text(strip=True)

        # Find area
        area_m2 = None
        area_elem = card.select_one("[class*='area'], [class*='surface']")
        if area_elem:
            area_match = re.search(r"(\d+)\s*m", area_elem.get_text())
            if area_match:
                area_m2 = int(area_match.group(1))

        # Find rooms
        rooms = None
        rooms_elem = card.select_one("[class*='room'], [class*='ambiente']")
        if rooms_elem:
            rooms_match = re.search(r"(\d+)", rooms_elem.get_text())
            if rooms_match:
                rooms = int(rooms_match.group(1))

        # Find link
        link_elem = card.select_one("a[href*='/propiedades/'], a[href*='.html']")
        source_url = ""
        if link_elem:
            href = link_elem.get("href", "")
            source_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        return RealEstatePrice(
            property_type=property_type,
            location=location[:100] if location else "",
            price_usd=price_usd,
            price_ars=price_ars,
            area_m2=area_m2,
            rooms=rooms,
            source="zonaprop",
            source_url=source_url
        )

    def _parse_price(self, text: str) -> tuple[float, float]:
        """Parse price from text. Returns (USD, ARS)."""
        text = text.upper()

        is_usd = "USD" in text or "U$S" in text or "US$" in text or "DÓLAR" in text

        # Extract number
        price_match = re.search(r"[\d.,]+", text.replace(" ", ""))
        if not price_match:
            return 0.0, 0.0

        price_str = price_match.group()
        # Handle thousand separators
        if price_str.count(".") > 1:
            price_str = price_str.replace(".", "")
        elif "." in price_str and "," in price_str:
            if price_str.rfind(",") > price_str.rfind("."):
                price_str = price_str.replace(".", "").replace(",", ".")
            else:
                price_str = price_str.replace(",", "")
        elif "," in price_str:
            price_str = price_str.replace(",", "")

        try:
            price = float(price_str)
        except ValueError:
            return 0.0, 0.0

        if is_usd:
            return price, 0.0
        return 0.0, price

    async def get_median_price(
        self,
        property_type: str,
        location: str = "",
        area_m2: Optional[int] = None
    ) -> Optional[float]:
        """Get median USD price for a property type/location."""
        properties = await self.search_property(
            property_type, location, limit=15
        )

        if not properties:
            return None

        BLUE_DOLLAR = 1200
        usd_prices = []

        for p in properties:
            if p.price_usd > 0:
                usd_prices.append(p.price_usd)
            elif p.price_ars > 0:
                usd_prices.append(p.price_ars / BLUE_DOLLAR)

        if not usd_prices:
            return None

        usd_prices.sort()
        mid = len(usd_prices) // 2
        return usd_prices[mid]

    async def get_price_per_m2(
        self,
        property_type: str,
        location: str = ""
    ) -> Optional[float]:
        """Get median price per m2 in USD."""
        properties = await self.search_property(
            property_type, location, limit=20
        )

        if not properties:
            return None

        BLUE_DOLLAR = 1200
        prices_per_m2 = []

        for p in properties:
            if not p.area_m2 or p.area_m2 <= 0:
                continue

            if p.price_usd > 0:
                prices_per_m2.append(p.price_usd / p.area_m2)
            elif p.price_ars > 0:
                prices_per_m2.append((p.price_ars / BLUE_DOLLAR) / p.area_m2)

        if not prices_per_m2:
            return None

        prices_per_m2.sort()
        mid = len(prices_per_m2) // 2
        return prices_per_m2[mid]
