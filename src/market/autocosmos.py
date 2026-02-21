"""Autocosmos scraper for vehicle market prices."""

import re
import logging
from typing import Optional
from dataclasses import dataclass
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class AutocosmosVehicle:
    """Autocosmos vehicle price data."""
    brand: str
    model: str
    year: int
    price_usd: float
    price_ars: float
    source_url: str
    kilometers: Optional[int] = None


class AutocosmosScraper:
    """Scraper for Autocosmos.com.ar vehicle prices."""

    BASE_URL = "https://www.autocosmos.com.ar"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        "Referer": "https://www.autocosmos.com.ar/",
    }

    # Brand URL slugs
    BRAND_SLUGS = {
        "ford": "ford",
        "chevrolet": "chevrolet",
        "toyota": "toyota",
        "volkswagen": "volkswagen",
        "renault": "renault",
        "fiat": "fiat",
        "peugeot": "peugeot",
        "citroen": "citroen",
        "honda": "honda",
        "nissan": "nissan",
        "hyundai": "hyundai",
        "kia": "kia",
        "jeep": "jeep",
        "ram": "ram",
        "mercedes": "mercedes-benz",
        "bmw": "bmw",
        "audi": "audi",
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

    async def search_vehicle(
        self,
        brand: str,
        model: str = "",
        year: Optional[int] = None,
        limit: int = 10
    ) -> list[AutocosmosVehicle]:
        """Search for used vehicle prices."""
        brand_slug = self.BRAND_SLUGS.get(brand.lower(), brand.lower())

        # Build search URL for used cars
        if model:
            model_slug = model.lower().replace(" ", "-")
            url = f"{self.BASE_URL}/auto/usado/{brand_slug}/{model_slug}"
        else:
            url = f"{self.BASE_URL}/auto/usado/{brand_slug}"

        if year:
            url = f"{url}?anio={year}"

        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                logger.debug(f"Autocosmos returned {response.status_code} for {url}")
                # Try alternative search
                return await self._search_alternative(brand, model, year, limit)

            soup = BeautifulSoup(response.text, "lxml")
            return self._parse_results(soup, brand, model, year, limit)

        except Exception as e:
            logger.error(f"Autocosmos search error: {e}")
            return []

    async def _search_alternative(
        self,
        brand: str,
        model: str,
        year: Optional[int],
        limit: int
    ) -> list[AutocosmosVehicle]:
        """Try alternative search method."""
        search_query = f"{brand} {model}".strip()
        url = f"{self.BASE_URL}/buscar?q={search_query.replace(' ', '+')}&tipo=usado"

        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "lxml")
            return self._parse_results(soup, brand, model, year, limit)

        except Exception as e:
            logger.debug(f"Autocosmos alternative search error: {e}")
            return []

    def _parse_results(
        self,
        soup: BeautifulSoup,
        brand: str,
        model: str,
        year: Optional[int],
        limit: int
    ) -> list[AutocosmosVehicle]:
        """Parse search results from HTML."""
        vehicles = []

        # Find listing items - Autocosmos uses various card formats
        cards = soup.select(
            ".listado-item, .car-card, .vehicle-card, "
            "[class*='listing'], article, .resultado"
        )

        for card in cards[:limit * 2]:
            try:
                vehicle = self._parse_card(card, brand, model, year)
                if vehicle:
                    vehicles.append(vehicle)
                    if len(vehicles) >= limit:
                        break
            except Exception as e:
                logger.debug(f"Error parsing Autocosmos card: {e}")

        return vehicles

    def _parse_card(
        self,
        card,
        search_brand: str,
        search_model: str,
        search_year: Optional[int]
    ) -> Optional[AutocosmosVehicle]:
        """Parse a single vehicle card."""
        # Find title
        title_elem = card.select_one("h2, h3, .title, [class*='title'], a")
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        if len(title) < 3:
            return None

        # Find price
        price_elem = card.select_one(
            ".price, [class*='price'], [class*='precio'], "
            ".monto, [class*='valor']"
        )
        if not price_elem:
            return None

        price_text = price_elem.get_text(strip=True)
        price_usd, price_ars = self._parse_price(price_text)

        if price_usd <= 0 and price_ars <= 0:
            return None

        # Extract vehicle info from title
        brand, model, year = self._extract_info(title)

        if not brand:
            brand = search_brand
        if not model:
            model = search_model
        if not year and search_year:
            year = search_year

        # Find link
        link_elem = card.select_one("a[href]")
        source_url = ""
        if link_elem:
            href = link_elem.get("href", "")
            source_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        # Find kilometers
        km = None
        km_elem = card.select_one("[class*='km'], [class*='kilo']")
        if km_elem:
            km_match = re.search(r"([\d.,]+)", km_elem.get_text())
            if km_match:
                try:
                    km = int(km_match.group(1).replace(".", "").replace(",", ""))
                except ValueError:
                    pass

        return AutocosmosVehicle(
            brand=brand.title() if brand else search_brand.title(),
            model=model.title() if model else "",
            year=year or 0,
            price_usd=price_usd,
            price_ars=price_ars,
            source_url=source_url,
            kilometers=km
        )

    def _parse_price(self, text: str) -> tuple[float, float]:
        """Parse price from text. Returns (USD, ARS)."""
        text = text.upper()

        is_usd = "USD" in text or "U$S" in text or "US$" in text or "DOLAR" in text

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

        try:
            price = float(price_str)
        except ValueError:
            return 0.0, 0.0

        if is_usd:
            return price, 0.0
        return 0.0, price

    def _extract_info(self, title: str) -> tuple[str, str, int]:
        """Extract brand, model, year from title."""
        title_lower = title.lower()

        brand = ""
        model = ""
        year = 0

        for b in self.BRAND_SLUGS.keys():
            if b in title_lower:
                brand = b
                break

        year_match = re.search(r"\b(20[012]\d)\b", title)
        if year_match:
            year = int(year_match.group())

        return brand, model, year

    async def get_median_price(
        self,
        brand: str,
        model: str = "",
        year: Optional[int] = None
    ) -> Optional[float]:
        """Get median USD price for a vehicle."""
        vehicles = await self.search_vehicle(brand, model, year, limit=10)

        if not vehicles:
            return None

        BLUE_DOLLAR = 1200  # Should use real rate
        usd_prices = []

        for v in vehicles:
            if v.price_usd > 0:
                usd_prices.append(v.price_usd)
            elif v.price_ars > 0:
                usd_prices.append(v.price_ars / BLUE_DOLLAR)

        if not usd_prices:
            return None

        usd_prices.sort()
        mid = len(usd_prices) // 2
        return usd_prices[mid]
