"""Source analytics module for evaluating auction house quality and performance.

Calculates metrics to help buyers choose where to bid:
- Listing quality scores (images, descriptions, dates)
- Fee structure comparison
- Source type (judicial vs private)
- Trust indicators
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class SourceMetrics:
    """Metrics for a single auction source."""

    source_id: str
    source_name: str
    source_type: str  # "judicial" or "private"

    # Volume metrics
    total_listings: int = 0
    active_listings: int = 0
    with_lots: int = 0
    total_lots: int = 0

    # Quality metrics (0-100 scale)
    quality_score: int = 0
    image_score: int = 0  # % with images
    description_score: int = 0  # % with descriptions
    price_score: int = 0  # % with prices
    date_score: int = 0  # % with end dates
    location_score: int = 0  # % with location data

    # Category breakdown
    categories: dict = None

    # Fee structure
    buyer_commission_pct: float = 0.0
    platform_fee_pct: float = 0.0
    iva_included: bool = False
    typical_total_fees: str = ""

    # Trust indicators
    is_government: bool = False
    years_operating: int = 0
    has_physical_location: bool = False
    requires_registration: bool = True

    # Response/Service (manual ratings, 1-5)
    response_rating: Optional[float] = None
    transparency_rating: Optional[float] = None

    # Website quality
    website_url: str = ""
    has_api: bool = False
    mobile_friendly: bool = False

    # Computed trust score (0-100)
    trust_score: int = 0

    def __post_init__(self):
        if self.categories is None:
            self.categories = {}

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


# Source metadata - curated information about each source
SOURCE_METADATA = {
    # Judicial sources - government operated, highest trust
    "csjn": {
        "name": "CSJN - Corte Suprema",
        "full_name": "Corte Suprema de Justicia de la Nacion",
        "type": "judicial",
        "website": "https://subastaselectronicasjudiciales.csjn.gov.ar",
        "is_government": True,
        "years_operating": 8,
        "has_physical_location": True,
        "requires_registration": True,
        "buyer_commission_pct": 3.0,  # Real estate
        "vehicle_commission_pct": 10.0,
        "platform_fee_pct": 0.25,
        "iva_included": False,
        "response_rating": 4.0,
        "transparency_rating": 5.0,
        "has_api": False,
        "mobile_friendly": True,
        "why_trust": "Operado por la Corte Suprema de Justicia. Maxima transparencia y seguridad juridica.",
        "typical_fees": "Inmuebles: 3% comision + 0.25% arancel CSJN. Vehiculos: 10% comision + 0.25% arancel.",
    },
    "scba": {
        "name": "SCBA - Buenos Aires",
        "full_name": "Suprema Corte de Justicia de Buenos Aires",
        "type": "judicial",
        "website": "https://subastas.scba.gov.ar",
        "is_government": True,
        "years_operating": 10,
        "has_physical_location": True,
        "requires_registration": True,
        "buyer_commission_pct": 3.0,
        "platform_fee_pct": 0.0,
        "iva_included": False,
        "response_rating": 3.5,
        "transparency_rating": 5.0,
        "has_api": False,
        "mobile_friendly": True,
        "why_trust": "Poder Judicial de la Provincia de Buenos Aires. Alta credibilidad institucional.",
        "typical_fees": "3% comision sobre precio final. Sin IVA para particulares.",
    },
    "cordoba": {
        "name": "Cordoba Judicial",
        "full_name": "Poder Judicial de Cordoba",
        "type": "judicial",
        "website": "https://subastas.justiciacordoba.gob.ar",
        "is_government": True,
        "years_operating": 6,
        "has_physical_location": True,
        "requires_registration": True,
        "buyer_commission_pct": 3.0,
        "platform_fee_pct": 0.0,
        "iva_included": False,
        "response_rating": 4.0,
        "transparency_rating": 5.0,
        "has_api": True,  # Has JSON API
        "mobile_friendly": True,
        "why_trust": "Sistema judicial provincial. Proceso transparente con supervision estatal.",
        "typical_fees": "3% comision. Inmuebles pueden tener sellados adicionales.",
    },
    "entrerios": {
        "name": "Entre Rios Judicial",
        "full_name": "Poder Judicial de Entre Rios",
        "type": "judicial",
        "website": "https://subastas.jusentrerios.gob.ar",
        "is_government": True,
        "years_operating": 5,
        "has_physical_location": True,
        "requires_registration": True,
        "buyer_commission_pct": 3.0,
        "platform_fee_pct": 0.0,
        "iva_included": False,
        "response_rating": 3.5,
        "transparency_rating": 5.0,
        "has_api": True,
        "mobile_friendly": True,
        "why_trust": "Justicia provincial. Menor volumen pero alta seguridad juridica.",
        "typical_fees": "3% comision sobre precio de venta.",
    },

    # Private sources - commercial operators
    "banco_ciudad": {
        "name": "Banco Ciudad",
        "full_name": "Banco Ciudad de Buenos Aires",
        "type": "private",
        "website": "https://subastas.bancociudad.com.ar",
        "is_government": True,  # Public bank
        "years_operating": 40,
        "has_physical_location": True,
        "requires_registration": True,
        "buyer_commission_pct": 3.0,
        "platform_fee_pct": 0.5,
        "iva_included": True,
        "response_rating": 4.5,
        "transparency_rating": 4.5,
        "has_api": True,
        "mobile_friendly": True,
        "why_trust": "Banco publico de la Ciudad de Buenos Aires. Larga trayectoria en remates.",
        "typical_fees": "3-5% comision + IVA. Gastos administrativos adicionales.",
    },
    "adrian_mercado": {
        "name": "Adrian Mercado",
        "full_name": "Adrian Mercado Subastas",
        "type": "private",
        "website": "https://www.adrianmercado.com.ar",
        "is_government": False,
        "years_operating": 25,
        "has_physical_location": True,
        "requires_registration": True,
        "buyer_commission_pct": 10.0,
        "platform_fee_pct": 0.0,
        "iva_included": True,
        "response_rating": 4.0,
        "transparency_rating": 4.0,
        "has_api": False,
        "mobile_friendly": True,
        "why_trust": "Casa de remates tradicional con mas de 25 anos. Especialista en maquinaria industrial.",
        "typical_fees": "10% comision + IVA (12.1% total). Gaston de retiro variables.",
    },
    "global_remates": {
        "name": "Global Remates",
        "full_name": "Global Remates y Subastas",
        "type": "private",
        "website": "https://www.globalremates.com.ar",
        "is_government": False,
        "years_operating": 15,
        "has_physical_location": True,
        "requires_registration": True,
        "buyer_commission_pct": 10.0,
        "platform_fee_pct": 0.0,
        "iva_included": True,
        "response_rating": 3.5,
        "transparency_rating": 3.5,
        "has_api": False,
        "mobile_friendly": True,
        "why_trust": "Empresa establecida con operaciones regulares. Buena variedad de categorias.",
        "typical_fees": "10% comision + IVA.",
    },
    "bidbit": {
        "name": "BidBit",
        "full_name": "BidBit Subastas Online",
        "type": "private",
        "website": "https://www.bidbit.ar",
        "is_government": False,
        "years_operating": 5,
        "has_physical_location": False,
        "requires_registration": True,
        "buyer_commission_pct": 8.0,
        "platform_fee_pct": 2.0,
        "iva_included": True,
        "response_rating": 4.0,
        "transparency_rating": 4.0,
        "has_api": False,
        "mobile_friendly": True,
        "why_trust": "Plataforma moderna 100% online. Especialista en ejecuciones prendarias bancarias.",
        "typical_fees": "8-10% comision + IVA. Garantia de oferta requerida.",
    },
    "agusti": {
        "name": "Agusti",
        "full_name": "Agusti Subastas",
        "type": "private",
        "website": "https://www.agusti.com.ar",
        "is_government": False,
        "years_operating": 20,
        "has_physical_location": True,
        "requires_registration": True,
        "buyer_commission_pct": 15.0,
        "platform_fee_pct": 0.0,
        "iva_included": True,
        "response_rating": 3.0,
        "transparency_rating": 3.0,
        "has_api": False,
        "mobile_friendly": False,
        "why_trust": "Casa tradicional. Alto volumen pero comisiones elevadas.",
        "typical_fees": "15% comision + IVA (18.15% total). Costos de retiro adicionales.",
    },
    "zarate": {
        "name": "Zarate",
        "full_name": "Zarate Remates",
        "type": "private",
        "website": "https://www.zarateremates.com.ar",
        "is_government": False,
        "years_operating": 10,
        "has_physical_location": True,
        "requires_registration": True,
        "buyer_commission_pct": 10.0,
        "platform_fee_pct": 0.0,
        "iva_included": True,
        "response_rating": 3.5,
        "transparency_rating": 3.5,
        "has_api": False,
        "mobile_friendly": True,
        "why_trust": "Operador regional con presencia en zona norte.",
        "typical_fees": "10% comision + IVA.",
    },
    "manucha": {
        "name": "Manucha",
        "full_name": "Manucha Subastas",
        "type": "private",
        "website": "https://www.manucha.com.ar",
        "is_government": False,
        "years_operating": 8,
        "has_physical_location": True,
        "requires_registration": True,
        "buyer_commission_pct": 12.0,
        "platform_fee_pct": 0.0,
        "iva_included": True,
        "response_rating": 3.0,
        "transparency_rating": 3.0,
        "has_api": False,
        "mobile_friendly": False,
        "why_trust": "Casa de remates con operaciones regulares.",
        "typical_fees": "12% comision + IVA.",
    },
    "rematadores": {
        "name": "Rematadores",
        "full_name": "Rematadores.com",
        "type": "private",
        "website": "https://www.rematadores.com",
        "is_government": False,
        "years_operating": 12,
        "has_physical_location": False,
        "requires_registration": True,
        "buyer_commission_pct": 10.0,
        "platform_fee_pct": 0.0,
        "iva_included": True,
        "response_rating": 3.0,
        "transparency_rating": 3.0,
        "has_api": False,
        "mobile_friendly": True,
        "why_trust": "Agregador de multiples martilleros. Verificar condiciones por subasta.",
        "typical_fees": "Variable segun martillero. Tipicamente 10-15% + IVA.",
    },
    "sitiodetiendas": {
        "name": "Sitio de Tiendas",
        "full_name": "Sitio de Tiendas Remates",
        "type": "private",
        "website": "https://www.sitiodetiendas.com.ar",
        "is_government": False,
        "years_operating": 5,
        "has_physical_location": False,
        "requires_registration": True,
        "buyer_commission_pct": 10.0,
        "platform_fee_pct": 0.0,
        "iva_included": True,
        "response_rating": 2.5,
        "transparency_rating": 2.5,
        "has_api": False,
        "mobile_friendly": True,
        "why_trust": "Plataforma online. Menor trayectoria.",
        "typical_fees": "10% comision + IVA.",
    },
    "delafuente": {
        "name": "De la Fuente",
        "full_name": "De la Fuente Subastas",
        "type": "private",
        "website": "https://www.delafuentesubastas.com.ar",
        "is_government": False,
        "years_operating": 15,
        "has_physical_location": True,
        "requires_registration": True,
        "buyer_commission_pct": 10.0,
        "platform_fee_pct": 0.0,
        "iva_included": True,
        "response_rating": 3.5,
        "transparency_rating": 3.5,
        "has_api": False,
        "mobile_friendly": True,
        "why_trust": "Casa de remates establecida.",
        "typical_fees": "10% comision + IVA.",
    },
}


def calculate_quality_scores(listings: list[dict]) -> dict:
    """Calculate quality scores from listing data.

    Returns dict with:
        - image_score: % of listings with images
        - description_score: % with meaningful descriptions
        - price_score: % with prices > 0
        - date_score: % with end dates
        - location_score: % with location data
        - overall: weighted average
    """
    if not listings:
        return {
            "image_score": 0,
            "description_score": 0,
            "price_score": 0,
            "date_score": 0,
            "location_score": 0,
            "overall": 0,
        }

    total = len(listings)

    # Count listings meeting each criterion
    with_images = sum(1 for l in listings if l.get("images") and len(l["images"]) > 0)
    with_desc = sum(1 for l in listings if l.get("description") and len(l["description"]) > 20)
    with_price = sum(1 for l in listings if l.get("base_price", 0) > 0)
    with_date = sum(1 for l in listings if l.get("ends_at"))
    with_location = sum(1 for l in listings if (
        l.get("location", {}).get("province") or l.get("location", {}).get("city")
    ))

    # Calculate percentages (0-100)
    image_score = round((with_images / total) * 100)
    desc_score = round((with_desc / total) * 100)
    price_score = round((with_price / total) * 100)
    date_score = round((with_date / total) * 100)
    loc_score = round((with_location / total) * 100)

    # Weighted overall score
    # Images most important (30%), then price (25%), desc (20%), date (15%), location (10%)
    overall = round(
        image_score * 0.30 +
        price_score * 0.25 +
        desc_score * 0.20 +
        date_score * 0.15 +
        loc_score * 0.10
    )

    return {
        "image_score": image_score,
        "description_score": desc_score,
        "price_score": price_score,
        "date_score": date_score,
        "location_score": loc_score,
        "overall": overall,
    }


def calculate_trust_score(source_id: str, quality_scores: dict) -> int:
    """Calculate overall trust score (0-100) for a source.

    Based on:
    - Is government/judicial (high weight)
    - Years operating
    - Quality scores
    - Manual ratings
    - Has physical location
    """
    meta = SOURCE_METADATA.get(source_id, {})

    score = 0

    # Government/judicial sources get major boost (35 points)
    if meta.get("is_government"):
        score += 35

    # Source type - judicial gets extra (15 points)
    if meta.get("type") == "judicial":
        score += 15

    # Years operating (up to 15 points)
    years = meta.get("years_operating", 0)
    score += min(years, 15)

    # Quality score contribution (up to 20 points)
    quality = quality_scores.get("overall", 0)
    score += round(quality * 0.20)

    # Manual ratings (up to 10 points)
    transparency = meta.get("transparency_rating", 3) or 3
    response = meta.get("response_rating", 3) or 3
    avg_rating = (transparency + response) / 2
    score += round(avg_rating * 2)  # 5 rating = 10 points

    # Has physical location (5 points)
    if meta.get("has_physical_location"):
        score += 5

    return min(100, score)


def get_category_breakdown(listings: list[dict]) -> dict:
    """Get breakdown of listings by category."""
    categories = {}
    for listing in listings:
        cat = listing.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1
    return categories


def analyze_source(source_id: str, listings: list[dict]) -> SourceMetrics:
    """Analyze a single source and return metrics."""
    meta = SOURCE_METADATA.get(source_id, {})

    # Filter to active listings (with end date in future or no date)
    now = datetime.now(timezone.utc)
    active_listings = []
    for l in listings:
        ends_at = l.get("ends_at")
        if ends_at:
            try:
                end_date = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=timezone.utc)
                if end_date > now:
                    active_listings.append(l)
            except (ValueError, TypeError):
                active_listings.append(l)  # Keep if can't parse
        else:
            active_listings.append(l)  # Keep if no end date

    # Count lots
    with_lots = sum(1 for l in listings if l.get("lots"))
    total_lots = sum(len(l.get("lots", [])) for l in listings)

    # Calculate quality scores
    quality = calculate_quality_scores(listings)

    # Calculate trust score
    trust = calculate_trust_score(source_id, quality)

    # Category breakdown
    categories = get_category_breakdown(listings)

    # Build metrics
    metrics = SourceMetrics(
        source_id=source_id,
        source_name=meta.get("name", source_id.title()),
        source_type=meta.get("type", "private"),
        total_listings=len(listings),
        active_listings=len(active_listings),
        with_lots=with_lots,
        total_lots=total_lots,
        quality_score=quality["overall"],
        image_score=quality["image_score"],
        description_score=quality["description_score"],
        price_score=quality["price_score"],
        date_score=quality["date_score"],
        location_score=quality["location_score"],
        categories=categories,
        buyer_commission_pct=meta.get("buyer_commission_pct", 10.0),
        platform_fee_pct=meta.get("platform_fee_pct", 0.0),
        iva_included=meta.get("iva_included", True),
        typical_total_fees=meta.get("typical_fees", "10% + IVA"),
        is_government=meta.get("is_government", False),
        years_operating=meta.get("years_operating", 0),
        has_physical_location=meta.get("has_physical_location", False),
        requires_registration=meta.get("requires_registration", True),
        response_rating=meta.get("response_rating"),
        transparency_rating=meta.get("transparency_rating"),
        website_url=meta.get("website", ""),
        has_api=meta.get("has_api", False),
        mobile_friendly=meta.get("mobile_friendly", True),
        trust_score=trust,
    )

    return metrics


def analyze_all_sources(data_dir: Path = Path("data/raw")) -> dict:
    """Analyze all sources and return comprehensive stats.

    Returns:
        Dict with:
        - sources: dict of source_id -> SourceMetrics
        - summary: overall statistics
        - generated_at: timestamp
    """
    sources = {}
    all_listings = []

    # Load all source data
    for json_file in data_dir.glob("*.json"):
        if json_file.name == ".gitkeep":
            continue

        source_id = json_file.stem
        try:
            with open(json_file, encoding="utf-8") as f:
                listings = json.load(f)
                if isinstance(listings, list):
                    # Analyze this source
                    metrics = analyze_source(source_id, listings)
                    sources[source_id] = metrics.to_dict()
                    all_listings.extend(listings)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read {json_file}: {e}")

    # Sort sources by trust score
    sorted_sources = sorted(
        sources.items(),
        key=lambda x: (x[1]["trust_score"], x[1]["quality_score"]),
        reverse=True
    )

    # Build summary
    total_listings = sum(s["total_listings"] for s in sources.values())
    total_active = sum(s["active_listings"] for s in sources.values())
    judicial_count = sum(1 for s in sources.values() if s["source_type"] == "judicial")
    private_count = sum(1 for s in sources.values() if s["source_type"] == "private")

    # Average quality across sources
    avg_quality = round(
        sum(s["quality_score"] for s in sources.values()) / len(sources)
    ) if sources else 0

    # Top sources by trust
    top_by_trust = [s[0] for s in sorted_sources[:5]]

    summary = {
        "total_sources": len(sources),
        "judicial_sources": judicial_count,
        "private_sources": private_count,
        "total_listings": total_listings,
        "active_listings": total_active,
        "average_quality_score": avg_quality,
        "top_trusted_sources": top_by_trust,
    }

    return {
        "sources": dict(sorted_sources),
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_why_judicial_content() -> dict:
    """Return content for 'Why Judicial?' explainer section."""
    return {
        "title": "Por que elegir subastas judiciales?",
        "subtitle": "Las subastas judiciales ofrecen ventajas unicas para compradores serios",
        "advantages": [
            {
                "icon": "shield",
                "title": "Seguridad Juridica",
                "description": "Supervisadas por el Poder Judicial. El proceso es transparente y tiene respaldo legal completo.",
            },
            {
                "icon": "percent",
                "title": "Menores Comisiones",
                "description": "Tipicamente 3% vs 10-15% en casas privadas. Ahorra miles de dolares en cada compra.",
            },
            {
                "icon": "document",
                "title": "Titulos Claros",
                "description": "Los bienes se venden con orden judicial. Sin sorpresas de gravamenes o deudas ocultas.",
            },
            {
                "icon": "balance",
                "title": "Precios Justos",
                "description": "Tasaciones oficiales por peritos judiciales. Bases reales, no infladas.",
            },
            {
                "icon": "clock",
                "title": "Proceso Transparente",
                "description": "Fechas y condiciones publicadas con anticipacion. Sin cambios de ultimo momento.",
            },
        ],
        "comparison_table": {
            "headers": ["Caracteristica", "Judicial", "Privada"],
            "rows": [
                ["Comision tipica", "3%", "10-15%"],
                ["Respaldo legal", "Poder Judicial", "Empresa privada"],
                ["Tasacion", "Perito judicial", "Tasador interno"],
                ["Transparencia", "Total (expediente publico)", "Variable"],
                ["IVA", "No aplica (particular)", "21% adicional"],
            ],
        },
    }


def get_source_badge_info(source_id: str) -> dict:
    """Get badge/display info for a source."""
    meta = SOURCE_METADATA.get(source_id, {})

    # Determine badge type
    if meta.get("type") == "judicial":
        badge_type = "judicial"
        badge_color = "emerald"
        badge_text = "Judicial"
    elif meta.get("is_government"):
        badge_type = "government"
        badge_color = "blue"
        badge_text = "Estatal"
    else:
        badge_type = "private"
        badge_color = "amber"
        badge_text = "Privada"

    return {
        "source_id": source_id,
        "name": meta.get("name", source_id.title()),
        "badge_type": badge_type,
        "badge_color": badge_color,
        "badge_text": badge_text,
        "trust_level": "high" if meta.get("type") == "judicial" else "medium",
        "why_trust": meta.get("why_trust", ""),
        "typical_fees": meta.get("typical_fees", ""),
    }
