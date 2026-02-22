"""
Market Price Enricher

Enriches auction listings with estimated market values from multiple sources.
Shows buyers the true value proposition: "This $5,000 auction item is worth $12,000 on MercadoLibre"
"""

import re
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict, field
import statistics

from src.market.currency import CurrencyConverter, converter
from src.market.price_reference import get_market_price, MACHINERY_PRICES, VEHICLE_PRICES

logger = logging.getLogger(__name__)


@dataclass
class MarketComparable:
    """A comparable item from the market."""
    source: str
    title: str
    price_usd: float
    url: str
    similarity_score: float = 0.0


@dataclass
class EnrichedPrice:
    """Enriched market price data for an auction listing."""
    auction_id: str
    auction_title: str
    auction_price_usd: float
    category: str

    # Market price data
    market_price_usd: float
    market_price_low: float
    market_price_high: float

    # Value proposition
    discount_percent: float
    savings_usd: float
    value_rating: str  # "excellent", "good", "fair", "poor"

    # Metadata
    confidence_score: float  # 0.0 - 1.0
    sources_used: list[str] = field(default_factory=list)
    comparables_count: int = 0
    comparable_urls: list[str] = field(default_factory=list)
    search_query: str = ""
    enriched_at: str = ""


class PriceEnricher:
    """
    Enriches auction listings with market price comparisons.

    Uses multiple sources to estimate true market value:
    - Vehicles: MercadoLibre, Autocosmos, DeMotores, DeAutos, Kavak
    - Real Estate: ZonaProp, Argenprop, MercadoLibre Inmuebles
    - Machinery: MercadoLibre Industrial, static reference data
    - General: MercadoLibre
    """

    OUTPUT_FILE = Path("data/market_prices.json")

    # Minimum confidence thresholds
    MIN_CONFIDENCE = 0.3
    HIGH_CONFIDENCE = 0.7

    # Value rating thresholds (discount %)
    VALUE_THRESHOLDS = {
        "excellent": 50,  # 50%+ discount
        "good": 30,       # 30-50% discount
        "fair": 15,       # 15-30% discount
        "poor": 0,        # <15% discount
    }

    # Vehicle brands for extraction
    VEHICLE_BRANDS = [
        "ford", "chevrolet", "toyota", "volkswagen", "vw", "renault", "fiat",
        "peugeot", "citroen", "mercedes", "bmw", "audi", "honda", "nissan",
        "hyundai", "kia", "jeep", "dodge", "ram", "mitsubishi", "suzuki",
        "alfa romeo", "volvo", "land rover", "jaguar", "porsche", "mini"
    ]

    # Vehicle models by brand
    VEHICLE_MODELS = {
        "ford": ["ranger", "f-100", "f100", "fiesta", "focus", "ecosport", "ka", "territory", "bronco", "mustang", "mondeo", "transit"],
        "chevrolet": ["s10", "cruze", "onix", "tracker", "equinox", "spin", "corsa", "classic", "montana", "silverado"],
        "toyota": ["hilux", "corolla", "etios", "yaris", "rav4", "sw4", "camry", "86", "fortuner"],
        "volkswagen": ["amarok", "gol", "polo", "golf", "vento", "tiguan", "taos", "t-cross", "saveiro", "up"],
        "renault": ["duster", "sandero", "logan", "kangoo", "stepway", "captur", "koleos", "oroch", "fluence"],
        "fiat": ["cronos", "argo", "mobi", "toro", "strada", "uno", "palio", "punto", "500"],
        "peugeot": ["208", "308", "2008", "3008", "partner", "boxer", "expert", "207"],
        "honda": ["civic", "hr-v", "cr-v", "fit", "city", "accord"],
        "nissan": ["frontier", "kicks", "sentra", "versa", "march", "np300"],
    }

    # Real estate types
    REALESTATE_TYPES = {
        "departamento": ["departamento", "depto", "dpto", "piso", "monoambiente", "dto"],
        "casa": ["casa", "chalet", "vivienda", "propiedad"],
        "terreno": ["terreno", "lote", "fraccion", "parcela"],
        "local": ["local", "comercial", "negocio"],
        "oficina": ["oficina"],
        "campo": ["campo", "hectareas", "has", "rural"],
        "galpon": ["galpon", "deposito", "nave", "galpn"],
    }

    def __init__(self):
        self._currency = CurrencyConverter()
        self._blue_dollar: float = 1200.0
        self._enriched: dict[str, EnrichedPrice] = {}
        self._load_existing()

    def _load_existing(self):
        """Load existing enriched prices."""
        if self.OUTPUT_FILE.exists():
            try:
                with open(self.OUTPUT_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("prices", []):
                        # Try to convert to EnrichedPrice, handle old format
                        if "auction_id" in item:
                            try:
                                # Check if it's the new format
                                if "auction_title" in item:
                                    self._enriched[item["auction_id"]] = EnrichedPrice(**{
                                        k: v for k, v in item.items()
                                        if k in EnrichedPrice.__dataclass_fields__
                                    })
                                else:
                                    # Old format - convert
                                    self._enriched[item["auction_id"]] = EnrichedPrice(
                                        auction_id=item["auction_id"],
                                        auction_title=item.get("search_query", ""),
                                        auction_price_usd=0,
                                        category="",
                                        market_price_usd=item.get("market_price_usd", 0),
                                        market_price_low=item.get("market_price_usd", 0) * 0.8,
                                        market_price_high=item.get("market_price_usd", 0) * 1.2,
                                        discount_percent=0,
                                        savings_usd=0,
                                        value_rating="unknown",
                                        confidence_score=item.get("confidence", 0.5),
                                        sources_used=[item.get("source", "unknown")],
                                        comparables_count=item.get("comparables_count", 0),
                                        comparable_urls=item.get("comparable_urls", []),
                                        search_query=item.get("search_query", ""),
                                        enriched_at=item.get("fetched_at", "")
                                    )
                            except Exception as e:
                                logger.debug(f"Could not convert item {item.get('auction_id')}: {e}")
                                continue
                logger.info(f"Loaded {len(self._enriched)} existing enriched prices")
            except Exception as e:
                logger.warning(f"Could not load existing prices: {e}")

    async def enrich_listings(
        self,
        listings: list[dict],
        use_live_sources: bool = True,
        max_items: int = 50
    ) -> list[EnrichedPrice]:
        """
        Enrich auction listings with market price data.

        Args:
            listings: List of auction listing dicts
            use_live_sources: Whether to query live market sources
            max_items: Maximum items to process (for rate limiting)

        Returns:
            List of EnrichedPrice objects
        """
        # Get current blue dollar rate
        self._blue_dollar = await self._currency.get_blue_dollar_rate()
        logger.info(f"Using blue dollar rate: {self._blue_dollar}")

        enriched = []
        processed = 0

        for listing in listings:
            if processed >= max_items:
                logger.info(f"Reached max items limit ({max_items})")
                break

            try:
                result = await self._enrich_single(listing, use_live_sources)
                if result:
                    enriched.append(result)
                    self._enriched[result.auction_id] = result
                    processed += 1

                    # Rate limiting for live sources
                    if use_live_sources:
                        await asyncio.sleep(1.5)

            except Exception as e:
                logger.error(f"Error enriching {listing.get('id')}: {e}")

        # Save results
        self._save_results()

        logger.info(f"Enriched {len(enriched)} listings with market prices")
        return enriched

    async def _enrich_single(
        self,
        listing: dict,
        use_live: bool
    ) -> Optional[EnrichedPrice]:
        """Enrich a single listing."""
        listing_id = listing.get("id", "")
        title = listing.get("title", "")
        description = listing.get("description", "")
        category = listing.get("category", "")
        base_price = listing.get("base_price", 0)
        currency = listing.get("currency", "ARS")

        if not title or not listing_id:
            return None

        # Convert auction price to USD
        auction_price_usd = base_price
        if currency == "ARS" and base_price > 0:
            auction_price_usd = base_price / self._blue_dollar
        elif base_price == 0:
            # No price listed, can't calculate discount
            return None

        # Get market price estimate
        market_data = await self._get_market_price(
            title, description, category, listing.get("location", {}), use_live
        )

        if not market_data:
            return None

        market_price = market_data["typical"]
        market_low = market_data["low"]
        market_high = market_data["high"]
        confidence = market_data["confidence"]
        sources = market_data["sources"]
        comparables = market_data.get("comparables", [])
        search_query = market_data.get("search_query", "")

        # Calculate discount/savings
        if market_price > 0:
            discount = ((market_price - auction_price_usd) / market_price) * 100
            savings = market_price - auction_price_usd
        else:
            discount = 0
            savings = 0

        # Determine value rating
        value_rating = "poor"
        for rating, threshold in self.VALUE_THRESHOLDS.items():
            if discount >= threshold:
                value_rating = rating
                break

        return EnrichedPrice(
            auction_id=listing_id,
            auction_title=title[:100],
            auction_price_usd=round(auction_price_usd, 2),
            category=category,
            market_price_usd=round(market_price, 2),
            market_price_low=round(market_low, 2),
            market_price_high=round(market_high, 2),
            discount_percent=round(discount, 1),
            savings_usd=round(savings, 2),
            value_rating=value_rating,
            confidence_score=round(confidence, 2),
            sources_used=sources,
            comparables_count=len(comparables),
            comparable_urls=[c.url for c in comparables[:5]],
            search_query=search_query,
            enriched_at=datetime.now(timezone.utc).isoformat()
        )

    async def _get_market_price(
        self,
        title: str,
        description: str,
        category: str,
        location: dict,
        use_live: bool
    ) -> Optional[dict]:
        """Get market price estimate from multiple sources."""

        # Route to appropriate method
        if category == "vehicles":
            return await self._get_vehicle_price(title, description, use_live)
        elif category == "real_estate":
            return await self._get_realestate_price(title, description, location, use_live)
        elif category == "machinery":
            return await self._get_machinery_price(title, description, use_live)
        else:
            return await self._get_general_price(title, description, use_live)

    async def _get_vehicle_price(
        self,
        title: str,
        description: str,
        use_live: bool
    ) -> Optional[dict]:
        """Get vehicle market price."""
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

        prices = []
        sources = []
        comparables = []

        # Try static reference first
        ref_data = get_market_price(title, description)
        if ref_data:
            prices.append(ref_data["typical_usd"])
            sources.append("reference")

        # Try live sources if enabled
        if use_live:
            live_prices = await self._fetch_vehicle_live_prices(brand, model, year)
            for source, price_list, comps in live_prices:
                prices.extend(price_list)
                sources.append(source)
                comparables.extend(comps)

        if not prices:
            return None

        # Calculate statistics
        median = statistics.median(prices)
        low = min(prices)
        high = max(prices)

        # Calculate confidence
        confidence = min(len(prices) / 10, 1.0)
        if len(prices) >= 3:
            avg = sum(prices) / len(prices)
            variance = sum((p - avg) ** 2 for p in prices) / len(prices)
            std_dev = variance ** 0.5
            if avg > 0 and std_dev / avg < 0.3:
                confidence = min(confidence + 0.2, 1.0)

        return {
            "typical": median,
            "low": low,
            "high": high,
            "confidence": confidence,
            "sources": list(set(sources)),
            "comparables": comparables,
            "search_query": search_query
        }

    async def _fetch_vehicle_live_prices(
        self,
        brand: str,
        model: str,
        year: Optional[int]
    ) -> list[tuple[str, list[float], list[MarketComparable]]]:
        """Fetch vehicle prices from live sources."""
        results = []

        # Try Autocosmos
        try:
            from src.market.autocosmos import AutocosmosScraper
            async with AutocosmosScraper() as scraper:
                vehicles = await scraper.search_vehicle(brand, model, year, limit=10)
                prices = []
                comps = []
                for v in vehicles:
                    price = v.price_usd if v.price_usd > 0 else v.price_ars / self._blue_dollar
                    if price > 0:
                        prices.append(price)
                        comps.append(MarketComparable(
                            source="autocosmos",
                            title=f"{v.brand} {v.model} {v.year}",
                            price_usd=price,
                            url=v.source_url
                        ))
                if prices:
                    results.append(("autocosmos", prices, comps))
        except Exception as e:
            logger.debug(f"Autocosmos error: {e}")

        # Try DeAutos
        try:
            from src.market.deautos import DeAutosScraper
            async with DeAutosScraper() as scraper:
                vehicles = await scraper.search_vehicle(brand, model, year, limit=10)
                prices = []
                comps = []
                for v in vehicles:
                    price = v.price_usd if v.price_usd > 0 else v.price_ars / self._blue_dollar
                    if price > 0:
                        prices.append(price)
                        comps.append(MarketComparable(
                            source="deautos",
                            title=f"{v.brand} {v.model} {v.year}",
                            price_usd=price,
                            url=v.source_url
                        ))
                if prices:
                    results.append(("deautos", prices, comps))
        except Exception as e:
            logger.debug(f"DeAutos error: {e}")

        # Try DeMotores
        try:
            from src.market.demotores import DeMotoresScraper
            async with DeMotoresScraper() as scraper:
                vehicles = await scraper.search_vehicle(brand, model, year, limit=10)
                prices = []
                comps = []
                for v in vehicles:
                    price = v.price_usd if v.price_usd > 0 else v.price_ars / self._blue_dollar
                    if price > 0:
                        prices.append(price)
                        comps.append(MarketComparable(
                            source="demotores",
                            title=f"{v.brand} {v.model} {v.year}",
                            price_usd=price,
                            url=v.source_url
                        ))
                if prices:
                    results.append(("demotores", prices, comps))
        except Exception as e:
            logger.debug(f"DeMotores error: {e}")

        # Try MercadoLibre
        try:
            from src.market.mercadolibre import MercadoLibreClient
            async with MercadoLibreClient(demo_mode=True) as ml:
                query = f"{brand} {model or ''} {year or ''}".strip()
                listings = await ml.search(query, category="vehicles", limit=10)
                prices = []
                comps = []
                for l in listings:
                    price = l.price if l.currency == "USD" else l.price / self._blue_dollar
                    if price > 0:
                        prices.append(price)
                        comps.append(MarketComparable(
                            source="mercadolibre",
                            title=l.title,
                            price_usd=price,
                            url=l.permalink
                        ))
                if prices:
                    results.append(("mercadolibre", prices, comps))
        except Exception as e:
            logger.debug(f"MercadoLibre error: {e}")

        return results

    async def _get_realestate_price(
        self,
        title: str,
        description: str,
        location: dict,
        use_live: bool
    ) -> Optional[dict]:
        """Get real estate market price."""
        text = f"{title} {description}".lower()

        # Detect property type
        prop_type = self._detect_property_type(text)

        # Extract location
        loc_str = ""
        if location:
            loc_str = location.get("city", "") or location.get("province", "")

        # Extract area
        area_match = re.search(r"(\d+)\s*m[2\u00b2]", text)
        area_m2 = int(area_match.group(1)) if area_match else None

        search_query = f"{prop_type} {loc_str}".strip()
        logger.debug(f"Searching real estate: {search_query}")

        prices = []
        sources = []
        comparables = []

        # Try static reference
        ref_data = get_market_price(title, description)
        if ref_data:
            prices.append(ref_data["typical_usd"])
            sources.append("reference")

        # Try live sources
        if use_live:
            live_prices = await self._fetch_realestate_live_prices(prop_type, loc_str, area_m2)
            for source, price_list, comps in live_prices:
                prices.extend(price_list)
                sources.append(source)
                comparables.extend(comps)

        if not prices:
            return None

        median = statistics.median(prices)
        confidence = min(len(prices) / 10, 1.0)

        return {
            "typical": median,
            "low": min(prices),
            "high": max(prices),
            "confidence": confidence,
            "sources": list(set(sources)),
            "comparables": comparables,
            "search_query": search_query
        }

    async def _fetch_realestate_live_prices(
        self,
        prop_type: str,
        location: str,
        area_m2: Optional[int]
    ) -> list[tuple[str, list[float], list[MarketComparable]]]:
        """Fetch real estate prices from live sources."""
        results = []

        # Try ZonaProp
        try:
            from src.market.zonaprop import ZonaPropScraper
            async with ZonaPropScraper() as scraper:
                props = await scraper.search_property(prop_type, location, limit=10)
                prices = []
                comps = []
                for p in props:
                    price = p.price_usd if p.price_usd > 0 else p.price_ars / self._blue_dollar
                    if price > 0:
                        prices.append(price)
                        comps.append(MarketComparable(
                            source="zonaprop",
                            title=f"{p.property_type} - {p.location}",
                            price_usd=price,
                            url=p.source_url
                        ))
                if prices:
                    results.append(("zonaprop", prices, comps))
        except Exception as e:
            logger.debug(f"ZonaProp error: {e}")

        # Try Argenprop
        try:
            from src.market.argenprop import ArgenpropScraper
            async with ArgenpropScraper() as scraper:
                props = await scraper.search_property(prop_type, location, limit=10)
                prices = []
                comps = []
                for p in props:
                    price = p.price_usd if p.price_usd > 0 else p.price_ars / self._blue_dollar
                    if price > 0:
                        prices.append(price)
                        comps.append(MarketComparable(
                            source="argenprop",
                            title=f"{p.property_type} - {p.location}",
                            price_usd=price,
                            url=p.source_url
                        ))
                if prices:
                    results.append(("argenprop", prices, comps))
        except Exception as e:
            logger.debug(f"Argenprop error: {e}")

        return results

    async def _get_machinery_price(
        self,
        title: str,
        description: str,
        use_live: bool
    ) -> Optional[dict]:
        """Get machinery market price."""
        text = f"{title} {description}".lower()

        # Use static reference data primarily
        ref_data = get_market_price(title, description)

        prices = []
        sources = []
        comparables = []

        if ref_data:
            prices.append(ref_data["typical_usd"])
            sources.append("reference")

        # Build search query
        search_query = self._extract_machinery_query(text)

        # Try live sources
        if use_live and search_query:
            try:
                from src.market.ml_industrial import MLIndustrialScraper
                async with MLIndustrialScraper() as scraper:
                    items = await scraper.search_machinery(search_query, limit=10)
                    for item in items:
                        price = item.price_usd if item.price_usd > 0 else item.price_ars / self._blue_dollar
                        if price > 0:
                            prices.append(price)
                            comparables.append(MarketComparable(
                                source="ml_industrial",
                                title=item.title,
                                price_usd=price,
                                url=item.source_url
                            ))
                    if prices:
                        sources.append("ml_industrial")
            except Exception as e:
                logger.debug(f"ML Industrial error: {e}")

        if not prices:
            return None

        median = statistics.median(prices)
        confidence = min(len(prices) / 8, 1.0)

        # Lower confidence for machinery (harder to compare)
        confidence = confidence * 0.8

        return {
            "typical": median,
            "low": min(prices),
            "high": max(prices),
            "confidence": confidence,
            "sources": list(set(sources)),
            "comparables": comparables,
            "search_query": search_query
        }

    async def _get_general_price(
        self,
        title: str,
        description: str,
        use_live: bool
    ) -> Optional[dict]:
        """Get general goods market price."""
        # For general goods, use MercadoLibre search
        search_query = self._clean_search_query(title)

        if not search_query or len(search_query) < 5:
            return None

        prices = []
        sources = []
        comparables = []

        if use_live:
            try:
                from src.market.mercadolibre import MercadoLibreClient
                async with MercadoLibreClient(demo_mode=True) as ml:
                    listings = await ml.search(search_query, limit=10, condition="used")
                    for l in listings:
                        price = l.price if l.currency == "USD" else l.price / self._blue_dollar
                        if price > 0:
                            prices.append(price)
                            comparables.append(MarketComparable(
                                source="mercadolibre",
                                title=l.title,
                                price_usd=price,
                                url=l.permalink
                            ))
                    if prices:
                        sources.append("mercadolibre")
            except Exception as e:
                logger.debug(f"MercadoLibre error: {e}")

        if not prices:
            return None

        median = statistics.median(prices)
        # Lower confidence for general goods
        confidence = min(len(prices) / 15, 0.7)

        return {
            "typical": median,
            "low": min(prices),
            "high": max(prices),
            "confidence": confidence,
            "sources": sources,
            "comparables": comparables,
            "search_query": search_query
        }

    def _extract_vehicle_info(self, text: str) -> tuple[str, str, int]:
        """Extract brand, model, year from text."""
        brand = ""
        model = ""
        year = 0

        # Find brand
        for b in self.VEHICLE_BRANDS:
            if b in text:
                brand = b
                if b == "vw":
                    brand = "volkswagen"
                break

        # Find model
        if brand and brand in self.VEHICLE_MODELS:
            for m in self.VEHICLE_MODELS[brand]:
                if m in text:
                    model = m
                    break

        # Find year
        year_match = re.search(r"\b(19[89]\d|20[012]\d)\b", text)
        if year_match:
            year = int(year_match.group())

        return brand, model, year

    def _detect_property_type(self, text: str) -> str:
        """Detect property type from text."""
        for ptype, keywords in self.REALESTATE_TYPES.items():
            if any(kw in text for kw in keywords):
                return ptype
        return "departamento"

    def _extract_machinery_query(self, text: str) -> str:
        """Extract search query for machinery."""
        # Look for known machinery keywords
        for keyword in MACHINERY_PRICES.keys():
            if keyword in text:
                return keyword
        return ""

    def _clean_search_query(self, title: str) -> str:
        """Clean title for use as search query."""
        # Remove common noise words
        noise = [
            "lote", "remate", "subasta", "judicial", "expediente",
            "usado", "varios", "articulos", "unidades"
        ]
        query = title.lower()
        for word in noise:
            query = query.replace(word, "")

        # Clean up
        query = re.sub(r"[^\w\s]", " ", query)
        query = re.sub(r"\s+", " ", query).strip()

        return query[:50]

    def _save_results(self):
        """Save enriched prices to file."""
        self.OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "blue_dollar_rate": self._blue_dollar,
            "count": len(self._enriched),
            "prices": [asdict(p) for p in self._enriched.values()]
        }

        with open(self.OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(self._enriched)} enriched prices to {self.OUTPUT_FILE}")

    def get_enriched_price(self, auction_id: str) -> Optional[EnrichedPrice]:
        """Get enriched price for an auction item."""
        return self._enriched.get(auction_id)

    def export_for_site(self) -> dict:
        """Export enriched prices in format suitable for the site."""
        result = {}
        for auction_id, price in self._enriched.items():
            if price.confidence_score >= self.MIN_CONFIDENCE:
                result[auction_id] = {
                    "market_price_usd": price.market_price_usd,
                    "discount_percent": price.discount_percent,
                    "savings_usd": price.savings_usd,
                    "value_rating": price.value_rating,
                    "confidence": price.confidence_score,
                    "sources": price.sources_used,
                    "comparables_count": price.comparables_count,
                    "comparable_urls": price.comparable_urls,
                }
        return result

    def get_opportunities(self, min_discount: float = 30.0) -> list[EnrichedPrice]:
        """Get listings that represent significant discounts."""
        return [
            p for p in self._enriched.values()
            if p.discount_percent >= min_discount
            and p.confidence_score >= self.MIN_CONFIDENCE
        ]

    def get_stats(self) -> dict:
        """Get enrichment statistics."""
        total = len(self._enriched)
        if total == 0:
            return {"total": 0}

        high_confidence = sum(1 for p in self._enriched.values() if p.confidence_score >= self.HIGH_CONFIDENCE)
        opportunities = sum(1 for p in self._enriched.values() if p.value_rating in ["excellent", "good"])

        discounts = [p.discount_percent for p in self._enriched.values() if p.discount_percent != 0]
        confidences = [p.confidence_score for p in self._enriched.values() if p.confidence_score > 0]

        avg_discount = statistics.mean(discounts) if discounts else 0
        avg_confidence = statistics.mean(confidences) if confidences else 0

        by_category = {}
        for p in self._enriched.values():
            cat = p.category or "other"
            if cat not in by_category:
                by_category[cat] = {"count": 0, "avg_discount": 0, "discounts": []}
            by_category[cat]["count"] += 1
            if p.discount_percent != 0:
                by_category[cat]["discounts"].append(p.discount_percent)

        for cat in by_category:
            cat_discounts = by_category[cat].pop("discounts", [])
            by_category[cat]["avg_discount"] = round(
                statistics.mean(cat_discounts), 1
            ) if cat_discounts else 0

        return {
            "total": total,
            "high_confidence_count": high_confidence,
            "opportunities_count": opportunities,
            "average_discount_percent": round(avg_discount, 1),
            "average_confidence": round(avg_confidence, 2),
            "by_category": by_category
        }
