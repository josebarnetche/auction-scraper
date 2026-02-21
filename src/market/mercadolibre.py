"""MercadoLibre client for market price comparison."""

import re
import logging
from typing import Optional
from dataclasses import dataclass
from urllib.parse import quote_plus
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class MLListing:
    """MercadoLibre listing data."""
    id: str
    title: str
    price: float
    currency: str
    condition: str
    permalink: str
    thumbnail: str
    location: dict
    attributes: dict


class MercadoLibreClient:
    """Client for MercadoLibre market data.

    Note: MercadoLibre API requires authentication for production use.
    Set ML_ACCESS_TOKEN environment variable or use demo mode.
    """

    BASE_URL = "https://api.mercadolibre.com"
    SITE_ID = "MLA"  # Argentina

    # Category IDs
    CATEGORIES = {
        "vehicles": "MLA1744",
        "real_estate": "MLA1459",
        "machinery": "MLA1512",
    }

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    }

    # Sample market prices for demo mode (USD)
    DEMO_PRICES = {
        "vehicles": {
            "ford ranger": 25000,
            "toyota hilux": 28000,
            "chevrolet s10": 22000,
            "volkswagen amarok": 30000,
            "renault duster": 15000,
            "fiat cronos": 12000,
            "peugeot 208": 14000,
            "default": 18000,
        },
        "real_estate": {
            "departamento": 80000,
            "casa": 120000,
            "terreno": 50000,
            "local": 70000,
            "oficina": 60000,
            "default": 75000,
        },
        "machinery": {
            "tractor": 35000,
            "cosechadora": 80000,
            "default": 25000,
        },
        "other": {
            "default": 5000,
        },
    }

    def __init__(self, demo_mode: bool = True):
        self._client: Optional[httpx.AsyncClient] = None
        self._demo_mode = demo_mode
        self._access_token = None

    async def __aenter__(self):
        import os
        self._access_token = os.environ.get("ML_ACCESS_TOKEN")
        if self._access_token:
            self._demo_mode = False
            headers = {**self.HEADERS, "Authorization": f"Bearer {self._access_token}"}
        else:
            headers = self.HEADERS

        self._client = httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        condition: Optional[str] = None,  # new, used
    ) -> list[MLListing]:
        """Search MercadoLibre listings.

        Args:
            query: Search terms
            category: Category key (vehicles, real_estate, machinery)
            limit: Max results
            condition: Filter by condition

        Returns:
            List of matching listings
        """
        # Try API if we have access token
        if self._access_token:
            results = await self._search_api(query, category, limit, condition)
            if results:
                return results

        # Use demo mode for testing
        if self._demo_mode:
            return self._generate_demo_results(query, category, limit)

        # Fallback to web scraping (may be blocked)
        return await self._search_web(query, category, limit)

    def _generate_demo_results(
        self, query: str, category: Optional[str], limit: int
    ) -> list[MLListing]:
        """Generate demo results for testing without API access."""
        cat = category or "other"
        prices = self.DEMO_PRICES.get(cat, self.DEMO_PRICES["other"])

        # Find matching price
        base_price = prices.get("default", 10000)
        query_lower = query.lower()
        for keyword, price in prices.items():
            if keyword != "default" and keyword in query_lower:
                base_price = price
                break

        # Generate varied results
        import random
        results = []
        for i in range(min(limit, 5)):
            variance = random.uniform(0.8, 1.2)
            price = base_price * variance

            results.append(MLListing(
                id=f"DEMO{i+1}",
                title=f"{query} - Comparable {i+1}",
                price=price,
                currency="USD",
                condition="used",
                permalink=f"https://mercadolibre.com.ar/demo/{i+1}",
                thumbnail="",
                location={"city": "Buenos Aires", "state": "Buenos Aires"},
                attributes={},
            ))

        logger.info(f"Generated {len(results)} demo results for '{query}' (ML API requires authentication)")
        return results

    async def _search_api(
        self, query: str, category: Optional[str], limit: int, condition: Optional[str]
    ) -> list[MLListing]:
        """Search using MercadoLibre API."""
        params = {
            "q": query,
            "limit": limit,
        }

        if category and category in self.CATEGORIES:
            params["category"] = self.CATEGORIES[category]

        if condition:
            params["condition"] = condition

        url = f"{self.BASE_URL}/sites/{self.SITE_ID}/search"

        try:
            response = await self._client.get(url, params=params)
            if response.status_code != 200:
                logger.debug(f"ML API returned {response.status_code}, trying web scraping")
                return []

            data = response.json()
            results = data.get("results", [])

            return [self._parse_result(r) for r in results]

        except Exception as e:
            logger.debug(f"ML API error: {e}")
            return []

    async def _search_web(
        self, query: str, category: Optional[str], limit: int
    ) -> list[MLListing]:
        """Search by scraping MercadoLibre web pages."""
        encoded_query = quote_plus(query)

        # Build search URL
        if category == "vehicles":
            url = f"https://autos.mercadolibre.com.ar/{encoded_query}"
        elif category == "real_estate":
            url = f"https://inmuebles.mercadolibre.com.ar/{encoded_query}"
        else:
            url = f"https://listado.mercadolibre.com.ar/{encoded_query}"

        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                logger.warning(f"ML web search failed: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "lxml")
            return self._parse_web_results(soup, limit)

        except Exception as e:
            logger.error(f"ML web search error: {e}")
            return []

    def _parse_web_results(self, soup: BeautifulSoup, limit: int) -> list[MLListing]:
        """Parse search results from HTML."""
        listings = []

        # Find result items - ML uses various class patterns
        items = soup.select(".ui-search-result, .ui-search-layout__item, [class*='ui-search-result']")

        for item in items[:limit]:
            try:
                listing = self._parse_web_item(item)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"Error parsing ML item: {e}")
                continue

        return listings

    def _parse_web_item(self, item) -> Optional[MLListing]:
        """Parse a single search result item from HTML."""
        # Find title and link
        title_elem = item.select_one(".ui-search-item__title, .ui-search-result__content-wrapper a, h2 a")
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        permalink = title_elem.get("href", "")

        # Extract ID from URL
        id_match = re.search(r"MLA-?(\d+)", permalink)
        item_id = f"MLA{id_match.group(1)}" if id_match else ""

        # Find price
        price_elem = item.select_one(".andes-money-amount__fraction, .price-tag-fraction, [class*='price']")
        price_text = price_elem.get_text(strip=True) if price_elem else "0"
        price = self._parse_price(price_text)

        # Currency (ML Argentina mostly uses ARS)
        currency = "ARS"
        currency_elem = item.select_one(".andes-money-amount__currency-symbol")
        if currency_elem and "U$S" in currency_elem.get_text():
            currency = "USD"

        # Thumbnail
        img_elem = item.select_one("img")
        thumbnail = img_elem.get("src", "") if img_elem else ""

        # Location
        location_elem = item.select_one(".ui-search-item__location, [class*='location']")
        location = {"city": "", "state": ""}
        if location_elem:
            loc_text = location_elem.get_text(strip=True)
            location["state"] = loc_text

        return MLListing(
            id=item_id,
            title=title,
            price=price,
            currency=currency,
            condition="used",
            permalink=permalink,
            thumbnail=thumbnail,
            location=location,
            attributes={},
        )

    def _parse_price(self, price_text: str) -> float:
        """Parse price from text."""
        # Remove currency symbols and dots (thousand separators)
        clean = re.sub(r"[^\d,]", "", price_text)
        # Handle Argentine format
        clean = clean.replace(".", "").replace(",", ".")
        try:
            return float(clean) if clean else 0.0
        except ValueError:
            return 0.0

    def _parse_result(self, result: dict) -> MLListing:
        """Parse API result into MLListing."""
        location = {}
        if "address" in result:
            addr = result["address"]
            location = {
                "city": addr.get("city_name", ""),
                "state": addr.get("state_name", ""),
            }
        elif "seller_address" in result:
            addr = result["seller_address"]
            location = {
                "city": addr.get("city", {}).get("name", ""),
                "state": addr.get("state", {}).get("name", ""),
            }

        attributes = {}
        for attr in result.get("attributes", []):
            attr_id = attr.get("id", "")
            if attr_id in ["BRAND", "MODEL", "YEAR", "KILOMETERS", "ROOMS", "TOTAL_AREA"]:
                attributes[attr_id.lower()] = attr.get("value_name", "")

        return MLListing(
            id=result.get("id", ""),
            title=result.get("title", ""),
            price=float(result.get("price", 0)),
            currency=result.get("currency_id", "ARS"),
            condition=result.get("condition", ""),
            permalink=result.get("permalink", ""),
            thumbnail=result.get("thumbnail", ""),
            location=location,
            attributes=attributes,
        )

    async def get_category_trends(self, category: str) -> dict:
        """Get trending searches in a category."""
        if category not in self.CATEGORIES:
            return {}

        url = f"{self.BASE_URL}/trends/{self.SITE_ID}/{self.CATEGORIES[category]}"

        try:
            response = await self._client.get(url)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"ML trends error: {e}")

        return {}


def extract_vehicle_info(title: str) -> dict:
    """Extract vehicle information from title.

    Returns dict with brand, model, year if found.
    """
    info = {}

    # Common vehicle brands
    brands = [
        "ford", "chevrolet", "toyota", "volkswagen", "vw", "renault", "fiat",
        "peugeot", "citroen", "mercedes", "bmw", "audi", "honda", "nissan",
        "hyundai", "kia", "jeep", "dodge", "ram", "mitsubishi", "suzuki"
    ]

    title_lower = title.lower()

    for brand in brands:
        if brand in title_lower:
            info["brand"] = brand.capitalize()
            if brand == "vw":
                info["brand"] = "Volkswagen"
            break

    # Year pattern
    year_match = re.search(r"\b(19|20)\d{2}\b", title)
    if year_match:
        info["year"] = int(year_match.group())

    # Kilometers pattern
    km_match = re.search(r"(\d+[\d.,]*)\s*(?:km|kms|kilometros)", title_lower)
    if km_match:
        km_str = km_match.group(1).replace(".", "").replace(",", "")
        try:
            info["kilometers"] = int(km_str)
        except ValueError:
            pass

    return info


def extract_realestate_info(title: str, description: str = "") -> dict:
    """Extract real estate information from title/description."""
    info = {}
    text = f"{title} {description}".lower()

    # Area in m2
    area_match = re.search(r"(\d+)\s*(?:m2|m²|metros)", text)
    if area_match:
        info["area_m2"] = int(area_match.group(1))

    # Rooms/ambientes
    rooms_match = re.search(r"(\d+)\s*(?:amb|ambientes|dormitorios|habitaciones)", text)
    if rooms_match:
        info["rooms"] = int(rooms_match.group(1))

    return info
