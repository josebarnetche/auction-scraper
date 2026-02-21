"""Market price reference data for opportunity detection."""

# Price reference data in USD based on market research
# Format: (keyword_pattern, min_price, max_price, typical_price)

MACHINERY_PRICES = {
    # Forklifts
    "autoelevador": {"min": 6000, "max": 60000, "typical": 15000},
    "forklift": {"min": 6000, "max": 60000, "typical": 15000},
    "clark": {"min": 8000, "max": 45000, "typical": 18000},
    "toyota autoelevador": {"min": 12000, "max": 60000, "typical": 25000},
    "yale": {"min": 10000, "max": 40000, "typical": 18000},

    # Agricultural - Tractors
    "tractor": {"min": 8000, "max": 150000, "typical": 35000},
    "john deere tractor": {"min": 15000, "max": 120000, "typical": 45000},
    "massey ferguson": {"min": 12000, "max": 80000, "typical": 30000},
    "new holland tractor": {"min": 12000, "max": 90000, "typical": 35000},
    "valtra": {"min": 40000, "max": 155000, "typical": 80000},

    # Agricultural - Harvesters
    "cosechadora": {"min": 50000, "max": 300000, "typical": 120000},
    "combine": {"min": 50000, "max": 300000, "typical": 120000},

    # Construction - Excavators
    "excavadora": {"min": 15000, "max": 200000, "typical": 45000},
    "retroexcavadora": {"min": 25000, "max": 150000, "typical": 50000},
    "excavator": {"min": 15000, "max": 200000, "typical": 45000},
    "komatsu": {"min": 20000, "max": 180000, "typical": 55000},
    "caterpillar": {"min": 30000, "max": 250000, "typical": 80000},
    "cat 320": {"min": 35000, "max": 150000, "typical": 70000},

    # Construction - Loaders
    "pala cargadora": {"min": 40000, "max": 200000, "typical": 75000},
    "cargadora frontal": {"min": 35000, "max": 180000, "typical": 65000},
    "wheel loader": {"min": 40000, "max": 200000, "typical": 75000},
    "minicargadora": {"min": 15000, "max": 65000, "typical": 30000},
    "bobcat": {"min": 18000, "max": 60000, "typical": 35000},
    "skid steer": {"min": 15000, "max": 60000, "typical": 30000},

    # Construction - Other
    "motoniveladora": {"min": 40000, "max": 180000, "typical": 80000},
    "grader": {"min": 40000, "max": 180000, "typical": 80000},
    "compactador": {"min": 20000, "max": 120000, "typical": 45000},
    "rodillo": {"min": 15000, "max": 100000, "typical": 40000},
    "vibro": {"min": 15000, "max": 80000, "typical": 35000},

    # Industrial
    "compresor industrial": {"min": 3000, "max": 50000, "typical": 12000},
    "generador": {"min": 2000, "max": 80000, "typical": 15000},
    # Portable generators (Honda, etc.) - small units 1-10kW
    "grupo electrogeno honda": {"min": 300, "max": 3000, "typical": 1200},
    "grupo electrogeno portatil": {"min": 200, "max": 2000, "typical": 800},
    # Industrial generators (larger units 10kW+)
    "grupo electrogeno": {"min": 3000, "max": 100000, "typical": 20000},
    "soldadora": {"min": 500, "max": 15000, "typical": 3000},
    "torno": {"min": 5000, "max": 80000, "typical": 20000},
    "fresadora": {"min": 8000, "max": 100000, "typical": 30000},
    "cnc": {"min": 15000, "max": 200000, "typical": 50000},
    "prensa": {"min": 3000, "max": 60000, "typical": 15000},
    "guillotina": {"min": 5000, "max": 50000, "typical": 18000},
    "plegadora": {"min": 8000, "max": 80000, "typical": 25000},
}

VEHICLE_PRICES = {
    # Trucks
    "camion": {"min": 15000, "max": 120000, "typical": 45000},
    "mercedes benz camion": {"min": 25000, "max": 100000, "typical": 50000},
    "scania": {"min": 30000, "max": 120000, "typical": 55000},
    "volvo camion": {"min": 28000, "max": 110000, "typical": 52000},
    "iveco": {"min": 20000, "max": 80000, "typical": 40000},
    "atego": {"min": 25000, "max": 60000, "typical": 40000},
    "actros": {"min": 40000, "max": 120000, "typical": 70000},

    # Semi-trailers
    "semirremolque": {"min": 4000, "max": 65000, "typical": 20000},
    "acoplado": {"min": 3000, "max": 40000, "typical": 15000},

    # Vans/Commercial
    "furgon": {"min": 8000, "max": 45000, "typical": 18000},
    "sprinter": {"min": 12000, "max": 50000, "typical": 25000},
    "master": {"min": 10000, "max": 40000, "typical": 20000},
    "ducato": {"min": 10000, "max": 35000, "typical": 18000},

    # Pickups
    "hilux": {"min": 15000, "max": 55000, "typical": 30000},
    "ranger": {"min": 12000, "max": 50000, "typical": 28000},
    "amarok": {"min": 18000, "max": 55000, "typical": 32000},
    "frontier": {"min": 12000, "max": 45000, "typical": 25000},
    "s10": {"min": 10000, "max": 40000, "typical": 22000},

    # Cars (common models)
    "corolla": {"min": 8000, "max": 35000, "typical": 18000},
    "cruze": {"min": 7000, "max": 28000, "typical": 15000},
    "focus": {"min": 5000, "max": 22000, "typical": 12000},
    "208": {"min": 8000, "max": 25000, "typical": 14000},
    "polo": {"min": 8000, "max": 28000, "typical": 15000},
    "gol": {"min": 4000, "max": 15000, "typical": 8000},
    "etios": {"min": 6000, "max": 18000, "typical": 11000},
}

REAL_ESTATE_PRICES_PER_M2 = {
    # Buenos Aires Province (USD/m2)
    "buenos aires": {"min": 500, "max": 3500, "typical": 1500},
    "capital federal": {"min": 1500, "max": 6000, "typical": 2800},
    "caba": {"min": 1500, "max": 6000, "typical": 2800},
    "la plata": {"min": 800, "max": 2500, "typical": 1400},
    "mar del plata": {"min": 1000, "max": 3000, "typical": 1800},

    # Interior provinces (USD/m2)
    "cordoba": {"min": 600, "max": 2500, "typical": 1200},
    "mendoza": {"min": 500, "max": 2200, "typical": 1100},
    "rosario": {"min": 700, "max": 2800, "typical": 1400},
    "santa fe": {"min": 500, "max": 2000, "typical": 1000},
    "entre rios": {"min": 400, "max": 1800, "typical": 900},
    "tucuman": {"min": 400, "max": 1600, "typical": 800},
    "salta": {"min": 400, "max": 1500, "typical": 750},

    # Default for unknown
    "default": {"min": 400, "max": 2000, "typical": 1000},
}


def get_market_price(title: str, description: str = "", category: str = "") -> dict | None:
    """
    Get estimated market price based on title/description keywords.
    Returns dict with min, max, typical prices or None if no match.
    """
    text = f"{title} {description}".lower()

    # Check machinery first (higher priority)
    for keyword, prices in MACHINERY_PRICES.items():
        if keyword in text:
            return {
                "source": "market_reference",
                "keyword_match": keyword,
                "min_usd": prices["min"],
                "max_usd": prices["max"],
                "typical_usd": prices["typical"],
                "category": "machinery"
            }

    # Check vehicles
    for keyword, prices in VEHICLE_PRICES.items():
        if keyword in text:
            return {
                "source": "market_reference",
                "keyword_match": keyword,
                "min_usd": prices["min"],
                "max_usd": prices["max"],
                "typical_usd": prices["typical"],
                "category": "vehicles"
            }

    return None


def calculate_discount(auction_price_usd: float, market_data: dict) -> float:
    """
    Calculate discount percentage compared to typical market price.
    Returns positive number if auction is below market (good deal).
    """
    if not market_data or auction_price_usd <= 0:
        return 0.0

    typical = market_data.get("typical_usd", 0)
    if typical <= 0:
        return 0.0

    discount = ((typical - auction_price_usd) / typical) * 100
    return round(discount, 1)


def is_opportunity(auction_price_usd: float, market_data: dict, threshold: float = 30.0) -> bool:
    """Check if auction price represents an opportunity (30%+ below market)."""
    discount = calculate_discount(auction_price_usd, market_data)
    return discount >= threshold


# Keywords that indicate premium opportunities (liquidations, bankruptcies, etc.)
PREMIUM_KEYWORDS = {
    "liquidation": [
        "liquidacion", "liquidación", "cierre", "cese", "clausura",
        "remate judicial", "quiebra", "concurso", "fallido",
    ],
    "fleet": [
        "flota", "fleet", "renovacion de flota", "renovación de flota",
        "lote de vehiculos", "lote de vehículos", "multiple unidades",
    ],
    "factory": [
        "fabrica", "fábrica", "planta", "industrial",
        "linea de produccion", "línea de producción", "maquinaria completa",
    ],
    "bankruptcy": [
        "quiebra", "concurso preventivo", "fallido", "insolvencia",
        "ejecucion", "ejecución", "embargo", "secuestro judicial",
    ],
    "urgent": [
        "urgente", "urgent", "inmediato", "cierre definitivo",
        "ultima oportunidad", "última oportunidad", "sin base",
    ],
}


def detect_premium_opportunity(title: str, description: str = "") -> dict | None:
    """
    Detect if listing is a premium opportunity based on keywords.

    Returns:
        Dict with premium_type and confidence, or None if not premium
    """
    text = f"{title} {description}".lower()

    detected_types = []
    total_matches = 0

    for premium_type, keywords in PREMIUM_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in text)
        if matches > 0:
            detected_types.append(premium_type)
            total_matches += matches

    if detected_types:
        # Determine primary type (most specific)
        type_priority = ["bankruptcy", "factory", "fleet", "liquidation", "urgent"]
        primary_type = "liquidation"
        for pt in type_priority:
            if pt in detected_types:
                primary_type = pt
                break

        return {
            "is_premium": True,
            "premium_type": primary_type,
            "premium_types": detected_types,
            "confidence": min(1.0, total_matches * 0.3),  # More matches = higher confidence
            "why_premium": f"Detected: {', '.join(detected_types)}"
        }

    return None


def analyze_listing(title: str, description: str, base_price: float, currency: str,
                   blue_dollar_rate: float = 1250) -> dict:
    """
    Comprehensive analysis of a listing for opportunity detection.

    Returns:
        Dict with market_data, discount, is_opportunity, premium_info
    """
    result = {
        "market_data": None,
        "auction_price_usd": 0,
        "discount_percent": 0,
        "is_opportunity": False,
        "premium_info": None,
    }

    # Convert to USD
    if base_price > 0:
        if currency == "USD":
            result["auction_price_usd"] = base_price
        else:
            result["auction_price_usd"] = base_price / blue_dollar_rate

    # Get market data
    market_data = get_market_price(title, description)
    if market_data:
        result["market_data"] = market_data

        if result["auction_price_usd"] > 0:
            discount = calculate_discount(result["auction_price_usd"], market_data)
            result["discount_percent"] = discount
            result["is_opportunity"] = discount >= 30

    # Check for premium keywords
    premium_info = detect_premium_opportunity(title, description)
    if premium_info:
        result["premium_info"] = premium_info
        # Premium keywords boost opportunity status even without market data
        if not result["is_opportunity"] and premium_info.get("confidence", 0) > 0.5:
            result["is_opportunity"] = True

    return result
