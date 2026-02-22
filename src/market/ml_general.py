"""MercadoLibre General Goods scraper for furniture, electronics, appliances."""

import re
import logging
from typing import Optional
from dataclasses import dataclass
from urllib.parse import quote_plus
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class MLGeneralItem:
    """MercadoLibre general item price data."""
    title: str
    category: str
    price_usd: float
    price_ars: float
    source_url: str
    condition: str = "used"


class MLGeneralScraper:
    """Scraper for MercadoLibre general goods (furniture, electronics, appliances)."""

    BASE_URL = "https://www.mercadolibre.com.ar"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9",
    }

    # Category mappings for common general goods
    CATEGORIES = {
        # Electronics
        "tv": "electronica/televisores",
        "television": "electronica/televisores",
        "televisor": "electronica/televisores",
        "notebook": "computacion/notebooks",
        "laptop": "computacion/notebooks",
        "computadora": "computacion/computadoras",
        "pc": "computacion/computadoras",
        "celular": "celulares-y-telefonos/celulares",
        "telefono": "celulares-y-telefonos/celulares",
        "tablet": "computacion/tablets",
        "impresora": "computacion/impresoras",
        "monitor": "computacion/monitores",
        "proyector": "electronica/proyectores",
        "audio": "electronica/audio",
        "parlante": "electronica/audio/parlantes",
        "camara": "electronica/camaras-y-accesorios",

        # Appliances
        "heladera": "electrodomesticos/heladeras-y-freezers",
        "freezer": "electrodomesticos/heladeras-y-freezers",
        "lavarropas": "electrodomesticos/lavarropas-y-secadoras",
        "secarropa": "electrodomesticos/lavarropas-y-secadoras",
        "lavavajilla": "electrodomesticos/lavavajillas",
        "microondas": "electrodomesticos/hornos-y-microondas",
        "horno": "electrodomesticos/hornos-y-microondas",
        "aire acondicionado": "electrodomesticos/climatizacion/aires-acondicionados",
        "aire": "electrodomesticos/climatizacion/aires-acondicionados",
        "calefactor": "electrodomesticos/climatizacion/calefactores",
        "estufa": "electrodomesticos/climatizacion/estufas",
        "cocina": "electrodomesticos/cocinas",
        "anafe": "electrodomesticos/anafes-y-hornallas",
        "aspiradora": "electrodomesticos/aspiradoras",
        "ventilador": "electrodomesticos/climatizacion/ventiladores",

        # Furniture
        "sillon": "hogar-muebles-y-jardin/muebles/sillones",
        "sofa": "hogar-muebles-y-jardin/muebles/sillones",
        "mesa": "hogar-muebles-y-jardin/muebles/mesas",
        "escritorio": "hogar-muebles-y-jardin/muebles/escritorios",
        "silla": "hogar-muebles-y-jardin/muebles/sillas",
        "cama": "hogar-muebles-y-jardin/muebles/camas",
        "colchon": "hogar-muebles-y-jardin/muebles/colchones",
        "placard": "hogar-muebles-y-jardin/muebles/placards-y-armarios",
        "ropero": "hogar-muebles-y-jardin/muebles/placards-y-armarios",
        "biblioteca": "hogar-muebles-y-jardin/muebles/bibliotecas",
        "estante": "hogar-muebles-y-jardin/muebles/estantes-y-estanterias",
        "modular": "hogar-muebles-y-jardin/muebles/modulares",
        "comoda": "hogar-muebles-y-jardin/muebles/comodas-y-cajoneras",
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

    async def search(
        self,
        query: str,
        condition: str = "used",
        limit: int = 10
    ) -> list[MLGeneralItem]:
        """Search for general goods prices."""
        # Check for known category
        query_lower = query.lower()
        category_path = None
        for keyword, path in self.CATEGORIES.items():
            if keyword in query_lower:
                category_path = path
                break

        # Build URL
        if category_path:
            url = f"{self.BASE_URL}/{category_path}"
            if condition == "used":
                url = f"{url}_ITEM*CONDITION_2230581"
        else:
            encoded_query = quote_plus(query)
            url = f"{self.BASE_URL}/{encoded_query}"
            if condition == "used":
                url = f"{url}_ITEM*CONDITION_2230581"

        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                return await self._fallback_search(query, limit)

            soup = BeautifulSoup(response.text, "lxml")
            return self._parse_results(soup, query, limit)

        except Exception as e:
            logger.error(f"ML General search error: {e}")
            return []

    async def _fallback_search(
        self,
        query: str,
        limit: int
    ) -> list[MLGeneralItem]:
        """Fallback search."""
        encoded_query = quote_plus(query + " usado")
        url = f"{self.BASE_URL}/listado/{encoded_query}"

        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "lxml")
            return self._parse_results(soup, query, limit)

        except Exception as e:
            logger.debug(f"ML General fallback search error: {e}")
            return []

    def _parse_results(
        self,
        soup: BeautifulSoup,
        query: str,
        limit: int
    ) -> list[MLGeneralItem]:
        """Parse search results."""
        items = []

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
                logger.debug(f"Error parsing ML General card: {e}")

        return items

    def _parse_card(
        self,
        card,
        search_query: str
    ) -> Optional[MLGeneralItem]:
        """Parse a single listing card."""
        # Find title
        title_elem = card.select_one(
            ".ui-search-item__title, h2, [class*='title'], a"
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

        # Check currency
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

        # Detect condition
        condition = "used"
        if "nuevo" in title.lower():
            condition = "new"

        return MLGeneralItem(
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
        clean = clean.replace(".", "").replace(",", ".")
        try:
            return float(clean) if clean else 0.0
        except ValueError:
            return 0.0

    def _detect_category(self, title: str) -> str:
        """Detect item category from title."""
        title_lower = title.lower()

        category_map = [
            (["tv", "television", "televisor", "smart tv"], "electronics_tv"),
            (["notebook", "laptop"], "electronics_laptop"),
            (["celular", "telefono", "iphone", "samsung galaxy"], "electronics_phone"),
            (["heladera", "refrigerador"], "appliance_refrigerator"),
            (["lavarropas", "lavadora"], "appliance_washer"),
            (["aire acondicionado", "split"], "appliance_ac"),
            (["microondas"], "appliance_microwave"),
            (["sillon", "sofa"], "furniture_sofa"),
            (["mesa", "escritorio"], "furniture_table"),
            (["cama", "colchon"], "furniture_bed"),
        ]

        for keywords, category in category_map:
            if any(kw in title_lower for kw in keywords):
                return category

        return "general"

    async def get_median_price(
        self,
        query: str,
        condition: str = "used"
    ) -> Optional[float]:
        """Get median USD price for an item."""
        items = await self.search(query, condition, limit=10)

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


# Sample reference prices for common items (USD)
GENERAL_REFERENCE_PRICES = {
    # Electronics
    "tv 32": {"min": 150, "max": 400, "typical": 250},
    "tv 50": {"min": 300, "max": 800, "typical": 500},
    "tv 55": {"min": 400, "max": 1000, "typical": 600},
    "notebook": {"min": 200, "max": 1500, "typical": 500},
    "celular": {"min": 100, "max": 1200, "typical": 300},
    "impresora": {"min": 50, "max": 500, "typical": 150},

    # Appliances
    "heladera": {"min": 200, "max": 1500, "typical": 500},
    "lavarropas": {"min": 200, "max": 1000, "typical": 400},
    "aire acondicionado": {"min": 300, "max": 1200, "typical": 500},
    "microondas": {"min": 50, "max": 300, "typical": 100},
    "cocina": {"min": 150, "max": 800, "typical": 350},

    # Furniture
    "sillon": {"min": 100, "max": 800, "typical": 300},
    "mesa comedor": {"min": 80, "max": 500, "typical": 200},
    "escritorio": {"min": 50, "max": 400, "typical": 150},
    "cama": {"min": 100, "max": 600, "typical": 250},
    "colchon": {"min": 100, "max": 800, "typical": 300},
}


def get_reference_price(query: str) -> Optional[dict]:
    """Get reference price for common items."""
    query_lower = query.lower()
    for keyword, prices in GENERAL_REFERENCE_PRICES.items():
        if keyword in query_lower:
            return prices
    return None
