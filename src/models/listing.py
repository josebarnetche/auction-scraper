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
    source: str  # csjn, scba, cordoba, adrian_mercado, etc.
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
        # General
        "auto", "automotor", "automóvil", "automovil", "vehículo", "vehiculo", "camioneta", "camión", "camion",
        "moto", "motocicleta", "pickup", "sedan", "hatchback", "suv", "4x4", "utilitario",
        "rodado", "patentado", "dominio", "chasis", "carroceria",
        # Car Brands
        "ford", "chevrolet", "toyota", "volkswagen", "vw", "wolkswagen", "renault", "fiat", "peugeot",
        "citroen", "citroën", "mercedes", "benz", "bmw", "audi", "honda", "nissan", "hyundai", "kia",
        "jeep", "dodge", "ram", "mitsubishi", "suzuki", "mazda", "subaru", "chery", "geely", "jac",
        "iveco", "scania", "volvo", "man", "mercedes-benz", "sprinter", "ducato",
        # Motorcycle Brands
        "corven", "motomel", "zanella", "gilera", "bajaj", "kymco", "benelli", "beta", "sym", "mondial",
        "guerrero", "cerro", "jawa", "appia", "keeway", "daelim", "tvs", "hero",
        # Car Models (Renault)
        "kwid", "captur", "clio", "megane", "fluence", "koleos", "stepway", "symbol", "oroch", "alaskan",
        # Car Models (VW)
        "gol", "polo", "vento", "passat", "bora", "suran", "tiguan", "touareg", "saveiro", "taos", "virtus",
        # Car Models (Other)
        "corolla", "hilux", "etios", "yaris", "rav4", "sw4", "fortuner",
        "ranger", "ka", "focus", "fiesta", "ecosport", "territory", "bronco",
        "amarok", "frontier", "s10", "cruze", "onix", "tracker", "spin", "cobalt", "prisma", "montana", "corsa", "classic", "agile", "meriva", "zafira", "vectra", "astra", "celta",
        "duster", "sandero", "logan", "kangoo", "master", "trafic",
        "partner", "berlingo", "boxer", "jumper", "expert",
        "palio", "siena", "uno", "mobi", "argo", "cronos", "strada", "toro", "fiorino",
        "208", "2008", "308", "3008", "408", "5008", "rifter",
        # Motorcycle Models
        "triax", "rouser", "skua", "zr", "rx", "ybr", "fz", "xtz", "mt-", "cg", "cb", "xr", "tornado",
        "wave", "biz", "pcx", "nmax", "tmax", "vespa", "scooter", "cuatriciclo", "atv", "utv",
        # Types
        "colectivo", "omnibus", "minibus", "micro", "remolque", "acoplado", "semirremolque",
        "trailer", "cisterna", "tanque", "furgon", "ambulancia", "grua"
    ]

    real_estate_keywords = [
        # Property types
        "inmueble", "casa", "departamento", "depto", "dpto", "dto", "terreno", "lote",
        "local comercial", "local", "oficina", "galpón", "galpon", "nave industrial",
        "propiedad", "edificio", "cochera", "garage", "estacionamiento", "vivienda",
        "ph", "dúplex", "duplex", "triplex", "monoambiente", "ambiente",
        # Land
        "hectáreas", "hectareas", "ha.", "parcela", "predio", "campo", "chacra",
        "fracción", "fraccion", "quinta", "finca", "rural",
        # Legal/units
        "uf.", "unidad funcional", "m2", "metros cuadrados", "m²",
        "escritura", "titulo", "matricula", "nomenclatura catastral",
        "nuda propiedad", "nuda prop", "derechos hereditarios", "derechos acc", "50% derechos",
        # Location terms
        "barrio", "b°", "bº", "country", "countries", "club de campo",
        # Common real estate location patterns
        "oportunidad b", "en b°", "en bº",
        # Common location names that indicate real estate
        "la granja", "bella vista", "unquillo", "alta gracia", "villa carlos paz", "cosquin",
        "rio ceballos", "salsipuedes", "mendiolaza", "villa allende",
        # Street address patterns (number + neighborhood)
        "villa urquiza", "c.a.b.a", "caba", "capital federal"
    ]

    machinery_keywords = [
        # General
        "maquinaria", "máquina", "maquina", "equipo", "equipamiento",
        "herramienta", "herramientas", "industrial", "fabrica", "planta",
        # Agricultural
        "tractor", "cosechadora", "sembradora", "fumigadora", "pulverizadora",
        "agrícola", "agricola", "implemento", "arado", "rastra", "cultivador",
        # Construction equipment
        "excavadora", "retroexcavadora", "pala mecánica", "bulldozer", "topadora",
        "motoniveladora", "rodillo", "compactador", "hormigonera", "mixer",
        # Industrial
        "generador", "grupo electrógeno", "electrogeno", "compresor", "bomba",
        "soldadora", "torno", "fresadora", "guillotina", "prensa", "cnc",
        "autoelevador", "montacarga", "elevador", "apilador", "transpallet",
        "grúa", "grua", "puente grua", "polipasto",
        # Electronics/IT (industrial)
        "servidor", "rack", "ups", "transformador", "tablero electrico",
        # Food/Restaurant equipment
        "heladera comercial", "freezer", "cocina industrial", "freidora",
        "exhibidora", "vitrina", "mostrador", "balanza industrial",
        # Medical
        "médico", "medico", "quirúrgico", "quirurgico", "dental", "radiología",
        # Other equipment
        "aire acondicionado", "split", "caldera", "calefaccion",
        # More industrial
        "tolva", "tratadora", "limadora", "cortadora", "balancin", "invernader", "cámara de almacenamiento",
        "perfil estructural", "material ferroso"
    ]

    general_goods_keywords = [
        # Furniture
        "escritorio", "silla", "mesa", "mueble", "estante", "ropero", "cama", "sofa", "sofá",
        "sillon", "sillón", "butaca", "fichero", "perchero", "pizarra", "biblioteca",
        "cajonera", "armario", "placard", "modular", "tablon", "tablón", "banco",
        # Clothing & Textiles
        "ropa", "calzado", "zapato", "campera", "pantalon", "pantalón", "remera", "casco",
        "jean", "short", "vestido", "pollera", "buzo", "chomba", "bermuda", "camiseta",
        "toalla", "repasador", "sabana", "sábana", "frazada", "acolchado", "cortina",
        "medias", "boxer", "corpiño", "corpino", "musculosa", "camisa", "sweater",
        "jogging", "joggin", "calza", "leggin", "pijama", "bata", "delantal",
        "prendas", "bikini", "malla", "traje de baño", "guante", "bufanda", "gorro",
        "can-can", "can can", "escolar", "objetos varios",
        # Footwear
        "zapatilla", "bota", "sandalia", "ojota", "pantufla", "mocasin",
        # Small Appliances
        "cocina", "horno", "microondas", "lavarropas", "caloventor", "caloventores", "caloventrores", "estufa", "ventilador",
        "cafetera", "anafe", "calefactor", "tostadora", "licuadora", "batidora", "minipimer",
        "plancha", "aspiradora", "secador", "termo", "pava", "secarropa",
        # Tools (hand/power)
        "amoladora", "taladro", "sierra", "destornillador", "llave", "pinza", "martillo",
        "nivel", "cinta metrica", "escalera",
        # Electronics (consumer)
        "tv", "televisor", "led", "smart tv", "celular", "notebook", "tablet", "telefono",
        "parlante", "proyector", "auricular", "cargador", "control remoto",
        "impresora", "monitor", "teclado", "mouse", "webcam", "router", "modem",
        # Construction Materials
        "puerta", "ventana", "ceramico", "cerámico", "porcelanato", "pastina", "pegamento",
        "pintura", "ladrillo", "laja", "madera", "placa", "durlock", "membrana",
        # Office supplies
        "posnet", "calculadora", "archivador", "carpeta", "resma",
        # Decor & Home
        "cuadro", "espejo", "lampara", "lámpara", "alfombra", "florero", "adorno",
        # Kitchen & Dining
        "vajilla", "plato", "vaso", "taza", "cubierto", "olla", "sarten", "sartén",
        # Baby & Kids
        "bebe", "bebé", "infantil", "juguete", "coche bebe", "cuna", "practicuna"
    ]

    # Check real_estate FIRST (terreno/parcela should be real estate even if "industrial" appears)
    if any(kw in text for kw in real_estate_keywords):
        return "real_estate"
    # Then vehicles (check before machinery to catch motorcycles)
    elif any(kw in text for kw in vehicle_keywords):
        return "vehicles"
    # Then machinery
    elif any(kw in text for kw in machinery_keywords):
        return "machinery"
    # Then general goods
    elif any(kw in text for kw in general_goods_keywords):
        return "general_goods"

    return "other"
