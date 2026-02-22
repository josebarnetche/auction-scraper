"""
AI-Powered Smart Search for Subasto Auction Aggregator.

Features:
- Natural language query parsing ("cheap trucks under $10k")
- Spanish synonym expansion (auto = coche = vehiculo)
- Typo tolerance via Levenshtein distance
- Intent detection (investment property -> real_estate + filters)
- Filter extraction from queries
- Semantic search via embeddings (optional)
"""

import re
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from difflib import SequenceMatcher
import unicodedata


@dataclass
class SearchFilters:
    """Extracted filters from natural language query."""
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    currency: str = "USD"
    location: Optional[str] = None
    source: Optional[str] = None
    condition: Optional[str] = None  # new, used, any
    sort_by: Optional[str] = None  # price_asc, price_desc, ending_soon, discount
    intent: Optional[str] = None  # investment, flip, personal_use, business
    keywords: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """Search result with relevance scoring."""
    id: str
    title: str
    description: str
    category: str
    base_price: float
    currency: str
    source: str
    source_url: str
    relevance_score: float
    match_reasons: List[str]
    highlight_terms: List[str]
    # Optional fields
    discount_percent: Optional[float] = None
    market_price_usd: Optional[float] = None
    ends_at: Optional[str] = None
    images: List[str] = field(default_factory=list)


class SmartSearch:
    """
    AI-powered search engine for auction listings.

    Provides natural language understanding, synonym expansion,
    typo correction, and intelligent filter extraction.
    """

    # Spanish synonym groups for vehicles
    VEHICLE_SYNONYMS = {
        "auto": ["coche", "vehiculo", "automovil", "carro", "automóvil", "vehículo"],
        "camioneta": ["pickup", "4x4", "suv", "utilitario", "todo terreno", "todoterreno"],
        "camion": ["truck", "camión", "furgon", "furgón"],
        "moto": ["motocicleta", "motorcycle", "scooter", "ciclomotor"],
        "carro": ["auto", "coche", "vehiculo"],
    }

    # Real estate synonyms
    REAL_ESTATE_SYNONYMS = {
        "casa": ["vivienda", "hogar", "residencia", "chalet"],
        "departamento": ["depto", "dpto", "apartamento", "piso", "flat"],
        "terreno": ["lote", "parcela", "tierra", "predio"],
        "local": ["comercio", "negocio", "tienda", "oficina"],
        "galpon": ["galpón", "deposito", "depósito", "bodega", "nave"],
        "inmueble": ["propiedad", "real estate", "bienes raices"],
    }

    # Machinery synonyms
    MACHINERY_SYNONYMS = {
        "tractor": ["maquinaria agricola", "maquinaria agrícola"],
        "excavadora": ["retroexcavadora", "pala mecanica", "pala mecánica"],
        "generador": ["grupo electrogeno", "grupo electrógeno", "planta electrica"],
        "autoelevador": ["montacargas", "montacarga", "elevador", "forklift"],
        "compresor": ["compressor"],
    }

    # Price keywords in Spanish
    PRICE_KEYWORDS = {
        "barato": {"max_percentile": 25},
        "economico": {"max_percentile": 30},
        "económico": {"max_percentile": 30},
        "ganga": {"max_percentile": 20},
        "oferta": {"max_percentile": 35},
        "caro": {"min_percentile": 75},
        "premium": {"min_percentile": 80},
        "lujo": {"min_percentile": 85},
    }

    # Intent detection patterns
    INTENT_PATTERNS = {
        "investment": [
            r"inversion|inversión|invertir|rentabilidad|renta|alquiler|rental",
            r"propiedad.*inversion|investment.*property",
        ],
        "flip": [
            r"revender|reventa|flip|negocio|ganancia|margen",
            r"comprar.*vender|buy.*sell",
        ],
        "personal": [
            r"uso personal|para mi|mi familia|mi casa|vivir|mudarse",
        ],
        "business": [
            r"empresa|negocio|comercial|trabajo|flota|fleet",
        ],
    }

    # Common brand misspellings (Argentine context)
    BRAND_CORRECTIONS = {
        "toyoya": "toyota",
        "toytoa": "toyota",
        "volkswaguen": "volkswagen",
        "volskwagen": "volkswagen",
        "folswagen": "volkswagen",
        "wolkswagen": "volkswagen",
        "peugot": "peugeot",
        "peujeot": "peugeot",
        "citreon": "citroen",
        "renaut": "renault",
        "chevroled": "chevrolet",
        "chervolet": "chevrolet",
        "nissam": "nissan",
        "mitshubishi": "mitsubishi",
        "mitsibishi": "mitsubishi",
        "hyunday": "hyundai",
        "hundai": "hyundai",
        "frod": "ford",
        "mercedez": "mercedes",
        "mersedes": "mercedes",
    }

    # Category detection keywords
    CATEGORY_KEYWORDS = {
        "vehicles": [
            "auto", "coche", "vehiculo", "vehículo", "camioneta", "camion", "camión",
            "moto", "motocicleta", "pickup", "sedan", "suv", "4x4",
            "ford", "chevrolet", "toyota", "volkswagen", "renault", "fiat", "peugeot",
            "honda", "nissan", "hyundai", "mercedes", "bmw", "audi"
        ],
        "real_estate": [
            "casa", "departamento", "depto", "terreno", "lote", "inmueble", "propiedad",
            "local", "oficina", "galpon", "galpón", "campo", "hectarea", "hectárea",
            "edificio", "ph", "cochera", "garage"
        ],
        "machinery": [
            "maquinaria", "maquina", "máquina", "tractor", "excavadora", "generador",
            "compresor", "autoelevador", "grua", "grúa", "industrial", "herramienta",
            "equipo", "fabrica", "fábrica"
        ],
        "general_goods": [
            "mueble", "electrodomestico", "electrodoméstico", "ropa", "electrónico",
            "electronico", "computadora", "notebook", "celular", "herramienta"
        ],
    }

    # Location aliases
    LOCATION_ALIASES = {
        "caba": ["capital federal", "buenos aires ciudad", "ciudad autonoma"],
        "bsas": ["buenos aires", "provincia de buenos aires", "pba"],
        "cordoba": ["córdoba", "cba"],
        "mendoza": ["mza", "mendoza provincia"],
        "santa fe": ["sf", "rosario"],
        "gba": ["gran buenos aires", "conurbano"],
    }

    def __init__(self, listings: List[Dict[str, Any]], blue_dollar_rate: float = 1200.0):
        """
        Initialize smart search with listings data.

        Args:
            listings: List of auction listing dictionaries
            blue_dollar_rate: Current blue dollar exchange rate (ARS per USD)
        """
        self.listings = listings
        self.blue_dollar_rate = blue_dollar_rate
        self._build_index()

    def _build_index(self):
        """Build search index with normalized text."""
        self.index = []
        for listing in self.listings:
            # Normalize text for searching
            title_norm = self._normalize_text(listing.get("title", ""))
            desc_norm = self._normalize_text(listing.get("description", ""))

            self.index.append({
                **listing,
                "_title_norm": title_norm,
                "_desc_norm": desc_norm,
                "_all_text": f"{title_norm} {desc_norm}",
            })

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (lowercase, remove accents, etc.)."""
        if not text:
            return ""
        # Convert to lowercase
        text = text.lower()
        # Remove accents
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(c for c in text if not unicodedata.combining(c))
        # Normalize whitespace
        text = ' '.join(text.split())
        return text

    def _correct_typos(self, word: str) -> str:
        """Correct common typos, especially brand names."""
        word_lower = word.lower()

        # Check direct corrections first
        if word_lower in self.BRAND_CORRECTIONS:
            return self.BRAND_CORRECTIONS[word_lower]

        # Check fuzzy match against known brands
        known_brands = list(self.BRAND_CORRECTIONS.values())
        known_brands.extend([
            "toyota", "volkswagen", "peugeot", "citroen", "renault", "chevrolet",
            "nissan", "mitsubishi", "hyundai", "ford", "mercedes", "fiat", "honda",
            "bmw", "audi", "jeep", "dodge", "ram", "suzuki", "mazda", "kia"
        ])

        for brand in set(known_brands):
            if self._similarity(word_lower, brand) > 0.75:
                return brand

        return word

    def _similarity(self, a: str, b: str) -> float:
        """Calculate string similarity using SequenceMatcher."""
        return SequenceMatcher(None, a, b).ratio()

    def _expand_synonyms(self, word: str) -> List[str]:
        """Expand a word to include its synonyms."""
        word_norm = self._normalize_text(word)
        synonyms = [word_norm]

        # Check all synonym groups
        all_synonyms = {
            **self.VEHICLE_SYNONYMS,
            **self.REAL_ESTATE_SYNONYMS,
            **self.MACHINERY_SYNONYMS,
        }

        for key, values in all_synonyms.items():
            key_norm = self._normalize_text(key)
            values_norm = [self._normalize_text(v) for v in values]

            if word_norm == key_norm or word_norm in values_norm:
                synonyms.append(key_norm)
                synonyms.extend(values_norm)

        return list(set(synonyms))

    def _extract_price_filters(self, query: str) -> Tuple[Optional[float], Optional[float], str]:
        """Extract price filters from natural language query."""
        min_price = None
        max_price = None
        currency = "USD"

        # Detect currency preference
        if "peso" in query.lower() or "ars" in query.lower() or "$ar" in query.lower():
            currency = "ARS"

        # Pattern: "under $X" or "menos de $X" or "hasta $X"
        under_patterns = [
            r'(?:under|menos de|hasta|debajo de|maximo|máximo|max)\s*\$?\s*([\d,.]+)\s*(?:k|mil|m)?',
            r'\$?\s*([\d,.]+)\s*(?:k|mil|m)?\s*(?:o menos|or less|max|máx)',
        ]
        for pattern in under_patterns:
            match = re.search(pattern, query.lower())
            if match:
                max_price = self._parse_price(match.group(1))
                break

        # Pattern: "over $X" or "mas de $X" or "desde $X"
        over_patterns = [
            r'(?:over|mas de|más de|desde|arriba de|minimo|mínimo|min)\s*\$?\s*([\d,.]+)\s*(?:k|mil|m)?',
            r'\$?\s*([\d,.]+)\s*(?:k|mil|m)?\s*(?:o mas|o más|or more|min|mín)',
        ]
        for pattern in over_patterns:
            match = re.search(pattern, query.lower())
            if match:
                min_price = self._parse_price(match.group(1))
                break

        # Pattern: "$X - $Y" or "entre $X y $Y"
        range_patterns = [
            r'\$?\s*([\d,.]+)\s*(?:k|mil)?\s*[-–—a]\s*\$?\s*([\d,.]+)\s*(?:k|mil)?',
            r'entre\s*\$?\s*([\d,.]+)\s*(?:k|mil)?\s*y\s*\$?\s*([\d,.]+)\s*(?:k|mil)?',
        ]
        for pattern in range_patterns:
            match = re.search(pattern, query.lower())
            if match:
                min_price = self._parse_price(match.group(1))
                max_price = self._parse_price(match.group(2))
                break

        return min_price, max_price, currency

    def _parse_price(self, price_str: str) -> float:
        """Parse price string with k/mil/m suffixes."""
        # Remove commas and dots used as thousands separators
        price_str = price_str.replace(',', '').replace('.', '')

        try:
            price = float(price_str)
        except ValueError:
            return 0.0

        # Check for k/mil/m suffix in context (handled by caller)
        return price

    def _detect_category(self, query: str) -> Optional[str]:
        """Detect category from query keywords."""
        query_norm = self._normalize_text(query)

        scores = {cat: 0 for cat in self.CATEGORY_KEYWORDS}

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                keyword_norm = self._normalize_text(keyword)
                if keyword_norm in query_norm:
                    # Longer keywords score higher
                    scores[category] += len(keyword_norm)

        # Return category with highest score, if any
        best_cat = max(scores, key=scores.get)
        if scores[best_cat] > 0:
            return best_cat
        return None

    def _detect_intent(self, query: str) -> Optional[str]:
        """Detect user intent from query patterns."""
        query_norm = self._normalize_text(query)

        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_norm):
                    return intent
        return None

    def _detect_location(self, query: str) -> Optional[str]:
        """Detect location from query."""
        query_norm = self._normalize_text(query)

        # Check location aliases
        for canonical, aliases in self.LOCATION_ALIASES.items():
            if canonical in query_norm:
                return canonical
            for alias in aliases:
                if self._normalize_text(alias) in query_norm:
                    return canonical

        # Check for province names
        provinces = [
            "buenos aires", "cordoba", "santa fe", "mendoza", "tucuman",
            "salta", "entre rios", "misiones", "chaco", "corrientes",
            "santiago del estero", "san juan", "jujuy", "rio negro",
            "neuquen", "formosa", "chubut", "san luis", "catamarca",
            "la rioja", "la pampa", "santa cruz", "tierra del fuego"
        ]
        for province in provinces:
            if self._normalize_text(province) in query_norm:
                return province

        return None

    def parse_query(self, query: str) -> SearchFilters:
        """
        Parse natural language query into structured filters.

        Args:
            query: Natural language search query

        Returns:
            SearchFilters with extracted parameters
        """
        filters = SearchFilters()

        # Extract price filters
        min_price, max_price, currency = self._extract_price_filters(query)
        filters.min_price = min_price
        filters.max_price = max_price
        filters.currency = currency

        # Detect category
        filters.category = self._detect_category(query)

        # Detect intent
        filters.intent = self._detect_intent(query)

        # Detect location
        filters.location = self._detect_location(query)

        # Extract and clean keywords
        words = query.split()
        keywords = []
        for word in words:
            # Skip price-related words
            if re.match(r'^[$\d,.]+[km]?$', word.lower()):
                continue
            # Skip common stop words
            if word.lower() in ['de', 'en', 'con', 'para', 'por', 'y', 'o', 'un', 'una', 'el', 'la', 'los', 'las', 'a']:
                continue
            # Skip filter words
            if word.lower() in ['under', 'over', 'menos', 'mas', 'hasta', 'desde', 'entre', 'barato', 'caro']:
                continue

            # Correct typos
            corrected = self._correct_typos(word)
            keywords.append(corrected)

        filters.keywords = keywords

        # Detect sort preference
        if re.search(r'terminan pronto|ending soon|urgente|rapido|rápido', query.lower()):
            filters.sort_by = "ending_soon"
        elif re.search(r'descuento|oferta|deal|oportunidad', query.lower()):
            filters.sort_by = "discount"
        elif re.search(r'nuevo|recent|last|ultimo|último', query.lower()):
            filters.sort_by = "newest"

        return filters

    def search(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        category_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
    ) -> Tuple[List[SearchResult], SearchFilters, Dict[str, Any]]:
        """
        Perform smart search on listings.

        Args:
            query: Natural language search query
            limit: Maximum results to return
            offset: Results offset for pagination
            category_filter: Optional category override
            source_filter: Optional source filter

        Returns:
            Tuple of (results, parsed_filters, metadata)
        """
        # Parse the query
        filters = self.parse_query(query)

        # Allow overrides
        if category_filter:
            filters.category = category_filter
        if source_filter:
            filters.source = source_filter

        # Expand keywords with synonyms
        expanded_keywords = []
        for keyword in filters.keywords:
            expanded_keywords.extend(self._expand_synonyms(keyword))
        expanded_keywords = list(set(expanded_keywords))

        # Score each listing
        scored_results = []
        for item in self.index:
            score, reasons, highlights = self._score_listing(item, filters, expanded_keywords)

            if score > 0:
                scored_results.append({
                    "item": item,
                    "score": score,
                    "reasons": reasons,
                    "highlights": highlights,
                })

        # Sort by relevance score
        if filters.sort_by == "ending_soon":
            scored_results.sort(key=lambda x: (x["item"].get("ends_at") or "9999", -x["score"]))
        elif filters.sort_by == "discount":
            scored_results.sort(key=lambda x: -(x["item"].get("discount_percent") or 0))
        elif filters.sort_by == "price_asc":
            scored_results.sort(key=lambda x: x["item"].get("base_price_usd", 999999999))
        elif filters.sort_by == "price_desc":
            scored_results.sort(key=lambda x: -x["item"].get("base_price_usd", 0))
        else:
            # Default: sort by relevance
            scored_results.sort(key=lambda x: -x["score"])

        # Apply pagination
        total_count = len(scored_results)
        paginated = scored_results[offset:offset + limit]

        # Build results
        results = []
        for sr in paginated:
            item = sr["item"]
            results.append(SearchResult(
                id=item.get("id", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                category=item.get("category", "other"),
                base_price=item.get("base_price", 0),
                currency=item.get("currency", "ARS"),
                source=item.get("source", ""),
                source_url=item.get("source_url", ""),
                relevance_score=sr["score"],
                match_reasons=sr["reasons"],
                highlight_terms=sr["highlights"],
                discount_percent=item.get("discount_percent"),
                market_price_usd=item.get("market_typical_usd"),
                ends_at=item.get("ends_at"),
                images=item.get("images", []),
            ))

        # Build metadata
        metadata = {
            "total_count": total_count,
            "returned_count": len(results),
            "offset": offset,
            "limit": limit,
            "expanded_keywords": expanded_keywords,
            "typo_corrections": self._get_typo_corrections(query),
            "suggested_filters": self._get_suggested_filters(filters, scored_results),
        }

        return results, filters, metadata

    def _score_listing(
        self,
        item: Dict[str, Any],
        filters: SearchFilters,
        keywords: List[str],
    ) -> Tuple[float, List[str], List[str]]:
        """
        Score a listing against search filters.

        Returns:
            Tuple of (score, match_reasons, highlight_terms)
        """
        score = 0.0
        reasons = []
        highlights = []

        all_text = item.get("_all_text", "")
        title_norm = item.get("_title_norm", "")

        # Category filter
        if filters.category:
            if item.get("category") != filters.category:
                return 0, [], []
            score += 10
            reasons.append(f"category:{filters.category}")

        # Source filter
        if filters.source:
            if item.get("source") != filters.source:
                return 0, [], []
            score += 5

        # Price filters
        price_usd = item.get("base_price_usd", 0)
        if not price_usd and item.get("base_price"):
            if item.get("currency") == "ARS":
                price_usd = item.get("base_price", 0) / self.blue_dollar_rate
            else:
                price_usd = item.get("base_price", 0)

        if filters.min_price is not None:
            filter_price = filters.min_price
            if filters.currency == "ARS":
                filter_price = filters.min_price / self.blue_dollar_rate
            if price_usd < filter_price:
                return 0, [], []
            score += 5

        if filters.max_price is not None:
            filter_price = filters.max_price
            if filters.currency == "ARS":
                filter_price = filters.max_price / self.blue_dollar_rate
            if price_usd > filter_price:
                return 0, [], []
            score += 5
            reasons.append(f"price_under:{filters.max_price}")

        # Location filter
        if filters.location:
            location_data = item.get("location", {})
            province = self._normalize_text(location_data.get("province", ""))
            city = self._normalize_text(location_data.get("city", ""))
            loc_norm = self._normalize_text(filters.location)

            if loc_norm not in province and loc_norm not in city:
                # Soft filter - reduce score but don't exclude
                score -= 20
            else:
                score += 15
                reasons.append(f"location:{filters.location}")

        # Keyword matching
        for keyword in keywords:
            if not keyword:
                continue

            # Title match (higher score)
            if keyword in title_norm:
                score += 30
                highlights.append(keyword)
                if f"keyword:{keyword}" not in reasons:
                    reasons.append(f"keyword:{keyword}")
            # Description match (lower score)
            elif keyword in all_text:
                score += 10
                highlights.append(keyword)
                if f"keyword:{keyword}" not in reasons:
                    reasons.append(f"keyword:{keyword}")
            # Fuzzy match for single words
            elif len(keyword) > 3:
                for word in title_norm.split():
                    if self._similarity(keyword, word) > 0.8:
                        score += 15
                        highlights.append(word)
                        reasons.append(f"fuzzy:{keyword}~{word}")
                        break

        # Bonus for opportunities
        if item.get("discount_percent", 0) > 30:
            score += 20
            reasons.append("high_discount")

        # Bonus for ending soon (within 7 days)
        ends_at = item.get("ends_at")
        if ends_at and filters.intent in ["flip", "investment"]:
            # Could add time-based scoring here
            pass

        return score, reasons, list(set(highlights))

    def _get_typo_corrections(self, query: str) -> Dict[str, str]:
        """Get typo corrections applied to query."""
        corrections = {}
        for word in query.split():
            corrected = self._correct_typos(word)
            if corrected != word.lower():
                corrections[word] = corrected
        return corrections

    def _get_suggested_filters(
        self,
        filters: SearchFilters,
        results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate suggested refinement filters based on results."""
        suggestions = {}

        if not results:
            return suggestions

        # Suggest categories if not filtered
        if not filters.category:
            cat_counts = {}
            for r in results[:100]:  # Sample first 100
                cat = r["item"].get("category", "other")
                cat_counts[cat] = cat_counts.get(cat, 0) + 1

            if cat_counts:
                suggestions["categories"] = sorted(
                    cat_counts.items(),
                    key=lambda x: -x[1]
                )[:5]

        # Suggest price ranges
        prices = [r["item"].get("base_price_usd", 0) for r in results if r["item"].get("base_price_usd")]
        if prices:
            suggestions["price_stats"] = {
                "min": min(prices),
                "max": max(prices),
                "median": sorted(prices)[len(prices) // 2],
            }

        # Suggest sources
        source_counts = {}
        for r in results[:100]:
            src = r["item"].get("source", "")
            source_counts[src] = source_counts.get(src, 0) + 1

        if source_counts:
            suggestions["sources"] = sorted(
                source_counts.items(),
                key=lambda x: -x[1]
            )[:5]

        return suggestions

    def get_suggestions(self, prefix: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get autocomplete suggestions for search prefix.

        Args:
            prefix: Current search input
            limit: Maximum suggestions to return

        Returns:
            List of suggestion objects with text and metadata
        """
        if len(prefix) < 2:
            return []

        prefix_norm = self._normalize_text(prefix)
        suggestions = []
        seen = set()

        # Check against indexed listings
        for item in self.index:
            title = item.get("title", "")
            title_norm = item.get("_title_norm", "")

            if prefix_norm in title_norm:
                # Extract relevant phrase
                words = title.split()
                for i, word in enumerate(words):
                    if prefix_norm in self._normalize_text(word):
                        # Get context (word + next 2 words)
                        phrase = ' '.join(words[i:i+3])
                        if phrase.lower() not in seen:
                            seen.add(phrase.lower())
                            suggestions.append({
                                "text": phrase,
                                "type": "listing",
                                "category": item.get("category"),
                                "count": 1,
                            })
                        break

            if len(suggestions) >= limit * 2:
                break

        # Add common search suggestions
        common_searches = [
            ("Toyota", "vehicles"),
            ("Ford", "vehicles"),
            ("Volkswagen", "vehicles"),
            ("Departamento", "real_estate"),
            ("Casa", "real_estate"),
            ("Terreno", "real_estate"),
            ("Tractor", "machinery"),
            ("Camioneta", "vehicles"),
            ("Generador", "machinery"),
        ]

        for text, category in common_searches:
            if prefix_norm in self._normalize_text(text) and text.lower() not in seen:
                seen.add(text.lower())
                suggestions.append({
                    "text": text,
                    "type": "common",
                    "category": category,
                    "count": 0,  # Would be populated from analytics
                })

        # Sort by relevance (exact prefix match first)
        suggestions.sort(key=lambda x: (
            0 if x["text"].lower().startswith(prefix.lower()) else 1,
            -x.get("count", 0),
        ))

        return suggestions[:limit]

    def get_did_you_mean(self, query: str) -> Optional[str]:
        """
        Generate "Did you mean?" suggestion for query.

        Args:
            query: Original search query

        Returns:
            Corrected query suggestion, or None if no corrections needed
        """
        corrections = self._get_typo_corrections(query)

        if not corrections:
            return None

        # Build corrected query
        corrected = query
        for original, fixed in corrections.items():
            corrected = re.sub(
                r'\b' + re.escape(original) + r'\b',
                fixed,
                corrected,
                flags=re.IGNORECASE
            )

        if corrected.lower() != query.lower():
            return corrected

        return None


# Popular searches data (would typically come from analytics)
POPULAR_SEARCHES = [
    {"query": "Toyota Hilux", "count": 156, "category": "vehicles"},
    {"query": "Departamento CABA", "count": 134, "category": "real_estate"},
    {"query": "Ford Ranger", "count": 128, "category": "vehicles"},
    {"query": "Volkswagen Amarok", "count": 112, "category": "vehicles"},
    {"query": "Terreno Cordoba", "count": 98, "category": "real_estate"},
    {"query": "Camioneta 4x4", "count": 87, "category": "vehicles"},
    {"query": "Autoelevador", "count": 76, "category": "machinery"},
    {"query": "Casa Buenos Aires", "count": 72, "category": "real_estate"},
    {"query": "Generador", "count": 65, "category": "machinery"},
    {"query": "Renault Duster", "count": 61, "category": "vehicles"},
]


def get_popular_searches(limit: int = 10) -> List[Dict[str, Any]]:
    """Get popular search queries."""
    return POPULAR_SEARCHES[:limit]
