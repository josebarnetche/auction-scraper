"""Auction listing data model."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import json


def _utcnow():
    return datetime.now(timezone.utc)


@dataclass
class LotItem:
    """Represents a single lot within an auction."""

    lot_id: str
    lot_number: int  # Position in auction (1, 2, 3...)
    title: str
    description: str
    base_price: float
    currency: str  # Original currency (ARS/USD)
    base_price_usd: float = 0.0  # Converted at scrape time
    deposit_required: float = 0.0
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    images: list[str] = field(default_factory=list)

    # AI-generated fields (nullable until analyzed)
    ai_specs: Optional[dict] = None  # {brand, model, quantity, condition}
    ai_market_value_usd: Optional[float] = None
    ai_opportunity_score: Optional[int] = None  # 1-10
    ai_analyzed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime fields to ISO format strings
        for key in ["starts_at", "ends_at", "ai_analyzed_at"]:
            if data.get(key) is not None:
                data[key] = data[key].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LotItem":
        """Create instance from dictionary."""
        # Convert ISO strings back to datetime
        for key in ["starts_at", "ends_at", "ai_analyzed_at"]:
            if data.get(key) and isinstance(data[key], str):
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)


@dataclass
class AuctionListing:
    """Represents a single auction listing."""

    id: str
    source: str  # csjn, scba, comprar, adrian_mercado, etc.
    source_url: str
    title: str
    description: str
    category: str  # vehicles, real_estate, machinery, other
    base_price: float
    currency: str  # ARS or USD
    status: str  # published, ongoing, finalized
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    location: dict = field(default_factory=lambda: {"province": "", "city": ""})
    images: list[str] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=_utcnow)
    extra: dict = field(default_factory=dict)

    # Lot-level data (new architecture)
    lots: list[LotItem] = field(default_factory=list)
    lot_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime fields to ISO format strings
        for key in ["starts_at", "ends_at", "scraped_at"]:
            if data[key] is not None:
                data[key] = data[key].isoformat()
        # Convert lots to dicts with proper datetime handling
        if data.get("lots"):
            data["lots"] = [
                {
                    **lot,
                    "starts_at": lot["starts_at"].isoformat() if lot.get("starts_at") else None,
                    "ends_at": lot["ends_at"].isoformat() if lot.get("ends_at") else None,
                    "ai_analyzed_at": lot["ai_analyzed_at"].isoformat() if lot.get("ai_analyzed_at") else None,
                }
                for lot in data["lots"]
            ]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AuctionListing":
        """Create instance from dictionary."""
        # Convert ISO strings back to datetime
        for key in ["starts_at", "ends_at", "scraped_at"]:
            if data.get(key) and isinstance(data[key], str):
                data[key] = datetime.fromisoformat(data[key])
        # Convert lots back to LotItem objects
        if data.get("lots"):
            data["lots"] = [LotItem.from_dict(lot) for lot in data["lots"]]
        return cls(**data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def detect_category(title: str, description: str = "") -> str:
    """Detect auction category from title and description."""
    text = f"{title} {description}".lower()

    vehicle_keywords = [
        "auto", "automóvil", "vehículo", "vehiculo", "camioneta", "camión",
        "moto", "motocicleta", "pickup", "sedan", "ford", "chevrolet",
        "toyota", "volkswagen", "renault", "fiat", "peugeot", "citroen",
        "mercedes", "bmw", "audi", "honda", "nissan", "rodado"
    ]

    real_estate_keywords = [
        "inmueble", "casa", "departamento", "terreno", "local comercial",
        "oficina comercial", "galpón", "galpon", "propiedad", "edificio",
        "cochera", "ph", "dúplex", "duplex", "monoambiente", "hectáreas",
        "parcela", "predio", "uf.", "unidad funcional", "dto.",
        "lote de terreno", "loteo", "m2 cubiertos", "metros cuadrados"
    ]

    machinery_keywords = [
        "maquinaria", "máquina", "maquina", "tractor", "cosechadora",
        "herramienta", "equipo industrial", "maquina industrial", "agrícola", "agricola",
        "generador", "grupo electrogeno", "electrógeno", "compresor",
        "soldadora", "torno", "fresadora", "guillotina", "autoelevador",
        "excavadora", "retroexcavadora", "grúa", "grua", "montacarga"
    ]

    # Check real_estate FIRST (terreno/parcela should be real estate even if "industrial" appears)
    # Then machinery (before vehicles to avoid brand conflicts like "honda")
    if any(kw in text for kw in real_estate_keywords):
        return "real_estate"
    elif any(kw in text for kw in machinery_keywords):
        return "machinery"
    elif any(kw in text for kw in vehicle_keywords):
        return "vehicles"

    return "other"
