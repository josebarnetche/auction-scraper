"""Kavak.com scraper for vehicle market prices."""

import re
import logging
import json
from typing import Optional
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)


@dataclass
class KavakVehicle:
    """Kavak vehicle price data."""
    brand: str
    model: str
    year: int
    price_usd: float
    price_ars: float
    source_url: str
    kilometers: Optional[int] = None


class KavakScraper:
    """Scraper for Kavak.com vehicle prices (Argentina)."""

    BASE_URL = "https://www.kavak.com/ar"
    API_URL = "https://www.kavak.com/api/ar"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "es-AR,es;q=0.9",
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
    ) -> list[KavakVehicle]:
        """Search Kavak for vehicle prices."""
        # Try API endpoint first
        try:
            vehicles = await self._search_api(brand, model, year, limit)
            if vehicles:
                return vehicles
        except Exception as e:
            logger.debug(f"Kavak API failed: {e}")

        # Fallback to web scraping
        return await self._search_web(brand, model, year, limit)

    async def _search_api(
        self,
        brand: str,
        model: str,
        year: Optional[int],
        limit: int
    ) -> list[KavakVehicle]:
        """Try to use Kavak's internal API."""
        # Kavak uses a specific API structure
        params = {
            "brand": brand,
            "limit": limit,
        }
        if model:
            params["model"] = model
        if year:
            params["year"] = year

        url = f"{self.API_URL}/search/cars"

        try:
            response = await self._client.get(url, params=params)
            if response.status_code != 200:
                return []

            data = response.json()
            vehicles = []

            for item in data.get("results", data.get("cars", [])):
                try:
                    vehicle = self._parse_api_item(item)
                    if vehicle:
                        vehicles.append(vehicle)
                except Exception as e:
                    logger.debug(f"Error parsing Kavak item: {e}")

            return vehicles[:limit]

        except Exception as e:
            logger.debug(f"Kavak API error: {e}")
            return []

    async def _search_web(
        self,
        brand: str,
        model: str,
        year: Optional[int],
        limit: int
    ) -> list[KavakVehicle]:
        """Scrape Kavak web pages."""
        from bs4 import BeautifulSoup

        # Build URL
        brand_slug = brand.lower().replace(" ", "-")
        url = f"{self.BASE_URL}/comprar-{brand_slug}"

        if model:
            model_slug = model.lower().replace(" ", "-")
            url = f"{self.BASE_URL}/comprar-{brand_slug}-{model_slug}"

        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                # Try generic search
                url = f"{self.BASE_URL}/comprar-autos?brand={brand}"
                response = await self._client.get(url)
                if response.status_code != 200:
                    return []

            soup = BeautifulSoup(response.text, "lxml")
            return self._parse_web_results(soup, brand, model, year, limit)

        except Exception as e:
            logger.error(f"Kavak web scrape error: {e}")
            return []

    def _parse_api_item(self, item: dict) -> Optional[KavakVehicle]:
        """Parse a vehicle from API response."""
        price = item.get("price", item.get("salePrice", 0))
        if not price:
            return None

        # Kavak prices are typically in ARS
        price_ars = float(price)
        price_usd = 0.0

        currency = item.get("currency", "ARS")
        if currency == "USD":
            price_usd = price_ars
            price_ars = 0.0

        return KavakVehicle(
            brand=item.get("brand", item.get("make", "")),
            model=item.get("model", ""),
            year=int(item.get("year", 0)),
            price_usd=price_usd,
            price_ars=price_ars,
            source_url=item.get("url", f"{self.BASE_URL}/car/{item.get('id', '')}"),
            kilometers=item.get("km", item.get("kilometers"))
        )

    def _parse_web_results(
        self,
        soup,
        brand: str,
        model: str,
        year: Optional[int],
        limit: int
    ) -> list[KavakVehicle]:
        """Parse vehicles from web page."""
        vehicles = []

        # Look for car cards
        cards = soup.select("[class*='card'], [class*='Car'], article, .vehicle-item")

        for card in cards[:limit * 2]:
            try:
                vehicle = self._parse_web_card(card, brand, model, year)
                if vehicle:
                    vehicles.append(vehicle)
                    if len(vehicles) >= limit:
                        break
            except Exception as e:
                logger.debug(f"Error parsing Kavak card: {e}")

        return vehicles

    def _parse_web_card(
        self,
        card,
        search_brand: str,
        search_model: str,
        search_year: Optional[int]
    ) -> Optional[KavakVehicle]:
        """Parse a single vehicle card from HTML."""
        # Find title
        title_elem = card.select_one("h2, h3, [class*='title'], [class*='name']")
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)

        # Find price
        price_elem = card.select_one("[class*='price'], [class*='Price']")
        if not price_elem:
            return None

        price_text = price_elem.get_text(strip=True)
        price_ars, price_usd = self._parse_price(price_text)

        if price_ars <= 0 and price_usd <= 0:
            return None

        # Extract info from title
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

        # Find km
        km = None
        km_elem = card.select_one("[class*='km'], [class*='Km']")
        if km_elem:
            km_match = re.search(r"([\d.,]+)", km_elem.get_text())
            if km_match:
                try:
                    km = int(km_match.group(1).replace(".", "").replace(",", ""))
                except ValueError:
                    pass

        return KavakVehicle(
            brand=brand.title() if brand else search_brand.title(),
            model=model.title() if model else "",
            year=year or 0,
            price_usd=price_usd,
            price_ars=price_ars,
            source_url=source_url,
            kilometers=km
        )

    def _parse_price(self, text: str) -> tuple[float, float]:
        """Parse price. Returns (ARS, USD)."""
        text = text.upper()
        is_usd = "USD" in text or "U$S" in text

        # Extract number
        price_match = re.search(r"[\d.,]+", text.replace(" ", ""))
        if not price_match:
            return 0.0, 0.0

        price_str = price_match.group().replace(".", "").replace(",", "")
        try:
            price = float(price_str)
        except ValueError:
            return 0.0, 0.0

        if is_usd:
            return 0.0, price
        return price, 0.0

    def _extract_info(self, title: str) -> tuple[str, str, int]:
        """Extract brand, model, year from title."""
        brands = [
            "ford", "chevrolet", "toyota", "volkswagen", "renault", "fiat",
            "peugeot", "citroen", "mercedes", "bmw", "audi", "honda", "nissan",
            "hyundai", "kia", "jeep", "dodge", "ram"
        ]

        title_lower = title.lower()
        brand = ""
        model = ""
        year = 0

        for b in brands:
            if b in title_lower:
                brand = b
                break

        year_match = re.search(r"\b(20\d{2})\b", title)
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

        BLUE_DOLLAR = 1200
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
