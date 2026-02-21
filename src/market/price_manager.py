"""Market price manager - fetches and caches real market prices."""

import re
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict

from src.market.autocosmos import AutocosmosScraper
from src.market.zonaprop import ZonaPropScraper

logger = logging.getLogger(__name__)


@dataclass
class MarketPrice:
    """Market price for an auction item."""
    auction_id: str
    market_price_usd: float
    source: str  # deautos, kavak, zonaprop
    comparables_count: int
    confidence: float  # 0.0 - 1.0
    fetched_at: str
    search_query: str
    comparable_urls: list[str]


class MarketPriceManager:
    """Manages market price fetching and caching."""

    CACHE_FILE = Path("data/market_prices.json")

    # Vehicle brand patterns for matching
    VEHICLE_BRANDS = [
        "ford", "chevrolet", "toyota", "volkswagen", "vw", "renault", "fiat",
        "peugeot", "citroen", "mercedes", "bmw", "audi", "honda", "nissan",
        "hyundai", "kia", "jeep", "dodge", "ram", "mitsubishi", "suzuki",
        "alfa romeo", "volvo", "land rover", "jaguar", "porsche", "mini"
    ]

    # Vehicle model patterns
    VEHICLE_MODELS = {
        "ford": ["ranger", "f-100", "f100", "fiesta", "focus", "ecosport", "ka", "territory", "bronco", "mustang"],
        "chevrolet": ["s10", "cruze", "onix", "tracker", "equinox", "spin", "corsa", "classic", "montana"],
        "toyota": ["hilux", "corolla", "etios", "yaris", "rav4", "sw4", "camry", "86"],
        "volkswagen": ["amarok", "gol", "polo", "golf", "vento", "tiguan", "taos", "t-cross", "saveiro"],
        "renault": ["duster", "sandero", "logan", "kangoo", "stepway", "captur", "koleos", "oroch"],
        "fiat": ["cronos", "argo", "mobi", "toro", "strada", "uno", "palio", "punto", "500"],
        "peugeot": ["208", "308", "2008", "3008", "partner", "boxer", "expert"],
        "honda": ["civic", "hr-v", "cr-v", "fit", "city", "accord"],
        "nissan": ["frontier", "kicks", "sentra", "versa", "march", "np300"],
    }

    # Real estate type patterns
    REALESTATE_TYPES = {
        "departamento": ["departamento", "depto", "dpto", "piso", "monoambiente"],
        "casa": ["casa", "chalet", "vivienda", "propiedad"],
        "terreno": ["terreno", "lote", "fraccion", "parcela"],
        "local": ["local", "comercial", "negocio"],
        "oficina": ["oficina"],
        "campo": ["campo", "hectareas", "has", "rural"],
        "galpon": ["galpon", "deposito", "nave"],
    }

    def __init__(self):
        self._prices: dict[str, MarketPrice] = {}
        self._load_cache()

    def _load_cache(self):
        """Load cached prices from file."""
        if self.CACHE_FILE.exists():
            try:
                with open(self.CACHE_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("prices", []):
                        self._prices[item["auction_id"]] = MarketPrice(**item)
                logger.info(f"Loaded {len(self._prices)} cached market prices")
            except Exception as e:
                logger.warning(f"Could not load price cache: {e}")

    def _save_cache(self):
        """Save prices to cache file."""
        self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(self._prices),
            "prices": [asdict(p) for p in self._prices.values()]
        }
        with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(self._prices)} market prices to cache")

    def get_price(self, auction_id: str) -> Optional[MarketPrice]:
        """Get cached market price for an auction item."""
        return self._prices.get(auction_id)

    async def fetch_prices_for_listings(self, listings: list[dict]) -> dict[str, MarketPrice]:
        """Fetch market prices for a list of auction listings."""
        new_prices = {}

        # Group by category for efficient scraping
        vehicles = [l for l in listings if l.get("category") == "vehicles"]
        real_estate = [l for l in listings if l.get("category") == "real_estate"]

        logger.info(f"Fetching market prices: {len(vehicles)} vehicles, {len(real_estate)} real estate")

        # Fetch vehicle prices
        if vehicles:
            vehicle_prices = await self._fetch_vehicle_prices(vehicles)
            new_prices.update(vehicle_prices)

        # Fetch real estate prices
        if real_estate:
            realestate_prices = await self._fetch_realestate_prices(real_estate)
            new_prices.update(realestate_prices)

        # Update cache
        self._prices.update(new_prices)
        self._save_cache()

        logger.info(f"Fetched {len(new_prices)} new market prices")
        return new_prices

    async def _fetch_vehicle_prices(self, listings: list[dict]) -> dict[str, MarketPrice]:
        """Fetch market prices for vehicles."""
        prices = {}

        async with AutocosmosScraper() as autocosmos:
            for listing in listings:
                try:
                    price = await self._fetch_vehicle_price(listing, autocosmos)
                    if price:
                        prices[listing["id"]] = price

                    # Rate limit
                    await asyncio.sleep(2.0)
                except Exception as e:
                    logger.debug(f"Error fetching price for {listing['id']}: {e}")

        return prices

    async def _fetch_vehicle_price(
        self,
        listing: dict,
        autocosmos: AutocosmosScraper
    ) -> Optional[MarketPrice]:
        """Fetch market price for a single vehicle."""
        title = listing.get("title", "")
        description = listing.get("description", "")
        text = f"{title} {description}".lower()

        # Extract vehicle info
        brand, model, year = self._extract_vehicle_info(text)

        if not brand:
            logger.debug(f"Could not identify vehicle brand: {title[:50]}")
            return None

        search_query = brand
        if model:
            search_query = f"{brand} {model}"
        if year:
            search_query = f"{search_query} {year}"

        logger.info(f"Searching vehicle: {search_query}")

        # Search Autocosmos
        comparables = []
        prices_usd = []
        BLUE_DOLLAR = 1200

        try:
            results = await autocosmos.search_vehicle(brand, model, year, limit=10)
            for r in results:
                price_usd = r.price_usd if r.price_usd > 0 else r.price_ars / BLUE_DOLLAR
                if price_usd > 0:
                    prices_usd.append(price_usd)
                    if r.source_url:
                        comparables.append(r.source_url)
        except Exception as e:
            logger.debug(f"Autocosmos error: {e}")

        if not prices_usd:
            logger.debug(f"No prices found for: {search_query}")
            return None

        # Calculate median
        prices_usd.sort()
        mid = len(prices_usd) // 2
        median_price = prices_usd[mid]

        # Calculate confidence based on sample size and consistency
        confidence = min(len(prices_usd) / 10, 1.0)
        if len(prices_usd) >= 3:
            # Check price variance
            avg = sum(prices_usd) / len(prices_usd)
            variance = sum((p - avg) ** 2 for p in prices_usd) / len(prices_usd)
            std_dev = variance ** 0.5
            if avg > 0 and std_dev / avg < 0.3:  # Low variance = high confidence
                confidence = min(confidence + 0.2, 1.0)

        return MarketPrice(
            auction_id=listing["id"],
            market_price_usd=round(median_price, 2),
            source="autocosmos",
            comparables_count=len(prices_usd),
            confidence=round(confidence, 2),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            search_query=search_query,
            comparable_urls=comparables[:5]
        )

    def _extract_vehicle_info(self, text: str) -> tuple[str, str, int]:
        """Extract brand, model, year from text."""
        text_lower = text.lower()

        brand = ""
        model = ""
        year = 0

        # Find brand
        for b in self.VEHICLE_BRANDS:
            if b in text_lower:
                brand = b
                if b == "vw":
                    brand = "volkswagen"
                break

        # Find model
        if brand and brand in self.VEHICLE_MODELS:
            for m in self.VEHICLE_MODELS[brand]:
                if m in text_lower:
                    model = m
                    break

        # Find year
        year_match = re.search(r"\b(19[89]\d|20[012]\d)\b", text)
        if year_match:
            year = int(year_match.group())

        return brand, model, year

    async def _fetch_realestate_prices(self, listings: list[dict]) -> dict[str, MarketPrice]:
        """Fetch market prices for real estate."""
        prices = {}

        async with ZonaPropScraper() as zonaprop:
            for listing in listings:
                try:
                    price = await self._fetch_realestate_price(listing, zonaprop)
                    if price:
                        prices[listing["id"]] = price

                    await asyncio.sleep(1.5)
                except Exception as e:
                    logger.debug(f"Error fetching price for {listing['id']}: {e}")

        return prices

    async def _fetch_realestate_price(
        self,
        listing: dict,
        zonaprop: ZonaPropScraper
    ) -> Optional[MarketPrice]:
        """Fetch market price for a single property."""
        title = listing.get("title", "")
        description = listing.get("description", "")
        text = f"{title} {description}".lower()

        # Detect property type
        prop_type = "departamento"  # default
        for ptype, keywords in self.REALESTATE_TYPES.items():
            if any(kw in text for kw in keywords):
                prop_type = ptype
                break

        # Extract location
        location = ""
        loc_data = listing.get("location", {})
        if loc_data.get("city"):
            location = loc_data["city"]
        elif loc_data.get("province"):
            location = loc_data["province"]

        # Extract area
        area_match = re.search(r"(\d+)\s*m[2²]", text)
        area_m2 = int(area_match.group(1)) if area_match else None

        search_query = f"{prop_type} {location}".strip()
        logger.debug(f"Searching real estate: {search_query}")

        try:
            results = await zonaprop.search_property(
                prop_type, location, limit=10
            )
        except Exception as e:
            logger.debug(f"ZonaProp error: {e}")
            return None

        if not results:
            return None

        # Get prices
        prices_usd = []
        comparables = []

        for r in results:
            price_usd = r.price_usd if r.price_usd > 0 else r.price_ars / 1200
            if price_usd > 0:
                prices_usd.append(price_usd)
                if r.source_url:
                    comparables.append(r.source_url)

        if not prices_usd:
            return None

        # Calculate median
        prices_usd.sort()
        mid = len(prices_usd) // 2
        median_price = prices_usd[mid]

        # Calculate confidence
        confidence = min(len(prices_usd) / 10, 1.0)

        return MarketPrice(
            auction_id=listing["id"],
            market_price_usd=round(median_price, 2),
            source="zonaprop",
            comparables_count=len(prices_usd),
            confidence=round(confidence, 2),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            search_query=search_query,
            comparable_urls=comparables[:5]
        )

    def export_for_site(self) -> dict:
        """Export prices in format suitable for the site."""
        return {
            auction_id: {
                "market_price_usd": p.market_price_usd,
                "source": p.source,
                "comparables_count": p.comparables_count,
                "confidence": p.confidence,
                "comparable_urls": p.comparable_urls,
            }
            for auction_id, p in self._prices.items()
            if p.confidence >= 0.3  # Only export high-confidence prices
        }
