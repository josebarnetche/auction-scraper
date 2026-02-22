"""MercadoLibre Industrial scraper for machinery market prices."""

import re
import logging
from typing import Optional
from dataclasses import dataclass
from urllib.parse import quote_plus
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class MLIndustrialItem:
    """MercadoLibre Industrial item price data."""
    title: str
    category: str
    price_usd: float
    price_ars: float
    source_url: str
    condition: str = "used"


class MLIndustrialScraper:
    """Scraper for MercadoLibre Industrial/Machinery prices."""

    BASE_URL = "https://www.mercadolibre.com.ar"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9",
    }

    # Category slugs for machinery
    CATEGORIES = {
        "autoelevador": "autoelevadores",
        "forklift": "autoelevadores",
        "tractor": "tractores",
        "excavadora": "excavadoras",
        "retroexcavadora": "retroexcavadoras",
        "pala cargadora": "palas-cargadoras",
        "minicargadora": "minicargadoras",
        "compresor": "compresores",
        "generador": "grupos-electrogenos",
        "grupo electrogeno": "grupos-electrogenos",
        "soldadora": "soldadoras",
        "torno": "tornos",
        "fresadora": "fresadoras",
        "guillotina": "cizallas-y-guillotinas",
        "prensa": "prensas",
        "rodillo": "rodillos-compactadores",
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

    async def search_machinery(
        self,
        query: str,
        condition: str = "used",
        limit: int = 10
    ) -> list[MLIndustrialItem]:
        """Search for machinery prices."""
        # Check if we have a specific category
        query_lower = query.lower()
        category_slug = None
        for keyword, slug in self.CATEGORIES.items():
            if keyword in query_lower:
                category_slug = slug
                break

        # Build URL
        if category_slug:
            url = f"{self.BASE_URL}/{category_slug}"
            if condition == "used":
                url = f"{url}_Maquinas-usadas"
        else:
            encoded_query = quote_plus(query)
            url = f"{self.BASE_URL}/{encoded_query}"
            if condition == "used":
                url = f"{url}_ITEM*CONDITION_2230581"  # Used condition filter

        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                # Try simple search
                return await self._simple_search(query, limit)

            soup = BeautifulSoup(response.text, "lxml")
            return self._parse_results(soup, query, limit)

        except Exception as e:
            logger.error(f"ML Industrial search error: {e}")
            return []

    async def _simple_search(
        self,
        query: str,
        limit: int
    ) -> list[MLIndustrialItem]:
        """Simple search fallback."""
        encoded_query = quote_plus(query + " usado")
        url = f"{self.BASE_URL}/listado/{encoded_query}"

        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "lxml")
            return self._parse_results(soup, query, limit)

        except Exception as e:
            logger.debug(f"ML Industrial simple search error: {e}")
            return []

    def _parse_results(
        self,
        soup: BeautifulSoup,
        query: str,
        limit: int
    ) -> list[MLIndustrialItem]:
        """Parse search results."""
        items = []

        # Find listing cards
        cards = soup.select(
            ".ui-search-result, .ui-search-layout__item, "
            "[class*='ui-search-result']"
        )

        for card in cards[:limit * 2]:
            try:
                item = self._parse_card(card, query)
                if item:
                    items.append(item)
                    if len(items) >= limit:
                        break
            except Exception as e:
                logger.debug(f"Error parsing ML Industrial card: {e}")

        return items

    def _parse_card(
        self,
        card,
        search_query: str
    ) -> Optional[MLIndustrialItem]:
        """Parse a single listing card."""
        # Find title
        title_elem = card.select_one(
            ".ui-search-item__title, h2, "
            "[class*='title'], a"
        )
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        if len(title) < 3:
            return None

        # Find price
        price_elem = card.select_one(
            ".andes-money-amount__fraction, .price-tag-fraction, "
            "[class*='price']"
        )
        if not price_elem:
            return None

        price_text = price_elem.get_text(strip=True)

        # Check currency symbol
        currency_elem = card.select_one(".andes-money-amount__currency-symbol")
        is_usd = False
        if currency_elem:
            currency_text = currency_elem.get_text(strip=True)
            is_usd = "U$S" in currency_text or "USD" in currency_text

        price = self._parse_price_value(price_text)
        if price <= 0:
            return None

        price_usd = price if is_usd else 0.0
        price_ars = 0.0 if is_usd else price

        # Find link
        link_elem = card.select_one("a[href*='mercadolibre']")
        source_url = ""
        if link_elem:
            source_url = link_elem.get("href", "")

        # Detect condition from title
        condition = "used"
        if "nuevo" in title.lower():
            condition = "new"

        return MLIndustrialItem(
            title=title,
            category=self._detect_category(title),
            price_usd=price_usd,
            price_ars=price_ars,
            source_url=source_url,
            condition=condition
        )

    def _parse_price_value(self, text: str) -> float:
        """Parse numeric price value."""
        clean = re.sub(r"[^\d.,]", "", text)
        # Handle Argentine format (dots for thousands)
        clean = clean.replace(".", "").replace(",", ".")
        try:
            return float(clean) if clean else 0.0
        except ValueError:
            return 0.0

    def _detect_category(self, title: str) -> str:
        """Detect machinery category from title."""
        title_lower = title.lower()

        categories = [
            ("autoelevador", "forklift"),
            ("tractor", "tractor"),
            ("excavadora", "excavator"),
            ("retroexcavadora", "backhoe"),
            ("cargadora", "loader"),
            ("minicargadora", "skid_steer"),
            ("compresor", "compressor"),
            ("generador", "generator"),
            ("grupo electrogeno", "generator"),
            ("soldadora", "welder"),
            ("torno", "lathe"),
            ("fresadora", "mill"),
            ("guillotina", "shear"),
            ("prensa", "press"),
        ]

        for keyword, category in categories:
            if keyword in title_lower:
                return category

        return "machinery"

    async def get_median_price(
        self,
        query: str,
        condition: str = "used"
    ) -> Optional[float]:
        """Get median USD price for machinery."""
        items = await self.search_machinery(query, condition, limit=10)

        if not items:
            return None

        BLUE_DOLLAR = 1200
        usd_prices = []

        for item in items:
            if item.price_usd > 0:
                usd_prices.append(item.price_usd)
            elif item.price_ars > 0:
                usd_prices.append(item.price_ars / BLUE_DOLLAR)

        if not usd_prices:
            return None

        usd_prices.sort()
        mid = len(usd_prices) // 2
        return usd_prices[mid]
