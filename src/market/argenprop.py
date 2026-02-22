"""Argenprop scraper for real estate market prices."""

import re
import logging
from typing import Optional
from dataclasses import dataclass
from urllib.parse import quote_plus
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ArgenpropProperty:
    """Argenprop property price data."""
    property_type: str
    location: str
    price_usd: float
    price_ars: float
    area_m2: Optional[int]
    rooms: Optional[int]
    source_url: str


class ArgenpropScraper:
    """Scraper for Argenprop real estate prices."""

    BASE_URL = "https://www.argenprop.com"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9",
    }

    # Property type URL mappings
    PROPERTY_TYPES = {
        "departamento": "departamento",
        "depto": "departamento",
        "casa": "casa",
        "terreno": "terreno",
        "lote": "terreno",
        "local": "local-comercial",
        "oficina": "oficina",
        "campo": "campo",
        "galpon": "galpon",
        "cochera": "cochera",
        "ph": "ph",
    }

    # Location mappings
    LOCATIONS = {
        "capital federal": "capital-federal",
        "caba": "capital-federal",
        "buenos aires": "buenos-aires",
        "gba": "gba",
        "cordoba": "cordoba",
        "rosario": "santa-fe/rosario",
        "mendoza": "mendoza",
        "la plata": "buenos-aires/la-plata",
        "mar del plata": "buenos-aires/mar-del-plata",
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
    ) -> list[ArgenpropProperty]:
        """Search for real estate prices."""
        # Normalize property type
        prop_slug = self.PROPERTY_TYPES.get(
            property_type.lower(),
            "departamento"
        )

        # Build URL
        location_slug = self._get_location_slug(location)

        if location_slug:
            url = f"{self.BASE_URL}/{prop_slug}-venta-{location_slug}"
        else:
            url = f"{self.BASE_URL}/{prop_slug}-venta"

        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                logger.debug(f"Argenprop returned {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "lxml")
            return self._parse_results(soup, property_type, location, limit)

        except Exception as e:
            logger.error(f"Argenprop search error: {e}")
            return []

    def _get_location_slug(self, location: str) -> str:
        """Get URL slug for location."""
        if not location:
            return ""

        location_lower = location.lower().strip()
        if location_lower in self.LOCATIONS:
            return self.LOCATIONS[location_lower]

        return location_lower.replace(" ", "-")

    def _parse_results(
        self,
        soup: BeautifulSoup,
        property_type: str,
        location: str,
        limit: int
    ) -> list[ArgenpropProperty]:
        """Parse search results."""
        properties = []

        # Find listing cards
        cards = soup.select(
            ".listing__item, [class*='listing-item'], "
            "[class*='card'], article"
        )

        for card in cards[:limit * 2]:
            try:
                prop = self._parse_card(card, property_type, location)
                if prop:
                    properties.append(prop)
                    if len(properties) >= limit:
                        break
            except Exception as e:
                logger.debug(f"Error parsing Argenprop card: {e}")

        return properties

    def _parse_card(
        self,
        card,
        property_type: str,
        search_location: str
    ) -> Optional[ArgenpropProperty]:
        """Parse a single listing card."""
        # Find price
        price_elem = card.select_one(
            "[class*='price'], [class*='Price'], "
            ".precio, [data-price]"
        )
        if not price_elem:
            return None

        price_text = price_elem.get_text(strip=True)
        price_usd, price_ars = self._parse_price(price_text)

        if price_usd <= 0 and price_ars <= 0:
            return None

        # Find location
        location_elem = card.select_one(
            "[class*='location'], [class*='address'], "
            "[class*='ubicacion'], .direccion"
        )
        location = search_location
        if location_elem:
            location = location_elem.get_text(strip=True)[:100]

        # Find area
        area_m2 = None
        area_elem = card.select_one("[class*='surface'], [class*='area']")
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
        link_elem = card.select_one("a[href*='/propiedades/'], a[href*='-']")
        source_url = ""
        if link_elem:
            href = link_elem.get("href", "")
            source_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        return ArgenpropProperty(
            property_type=property_type,
            location=location,
            price_usd=price_usd,
            price_ars=price_ars,
            area_m2=area_m2,
            rooms=rooms,
            source_url=source_url
        )

    def _parse_price(self, text: str) -> tuple[float, float]:
        """Parse price from text. Returns (USD, ARS)."""
        text = text.upper()

        is_usd = "USD" in text or "U$S" in text or "US$" in text

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
