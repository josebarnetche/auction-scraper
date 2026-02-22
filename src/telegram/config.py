"""Configuration for Subasto Telegram bot."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BotConfig:
    """Telegram bot configuration."""

    # Bot token from @BotFather
    token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))

    # Webhook settings (for production)
    webhook_url: Optional[str] = field(default_factory=lambda: os.getenv("TELEGRAM_WEBHOOK_URL"))
    webhook_port: int = field(default_factory=lambda: int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8443")))

    # API settings
    api_base_url: str = field(default_factory=lambda: os.getenv("SUBASTO_API_URL", "https://subasto.com.ar"))
    listings_path: str = "site/api/listings.json"
    hot_list_path: str = "data/hot_list.json"

    # Alert settings
    default_digest_hour: int = 9  # 9 AM Argentina time (UTC-3)
    default_timezone: str = "America/Argentina/Buenos_Aires"

    # Rate limiting
    max_results_per_search: int = 10
    max_watchlist_items: int = 50

    # Data directory for user preferences
    user_data_dir: str = "data/telegram_users"

    # Categories
    categories: dict = field(default_factory=lambda: {
        "vehicles": {"emoji": "🚗", "name": "Vehiculos", "name_en": "Vehicles"},
        "real_estate": {"emoji": "🏠", "name": "Inmuebles", "name_en": "Real Estate"},
        "machinery": {"emoji": "⚙️", "name": "Maquinaria", "name_en": "Machinery"},
        "general_goods": {"emoji": "📦", "name": "Bienes Generales", "name_en": "General Goods"},
        "other": {"emoji": "🔷", "name": "Otros", "name_en": "Other"},
    })

    # Sources (judicial first)
    sources: dict = field(default_factory=lambda: {
        "judicial": {
            "csjn": "CSJN (Nacion)",
            "scba": "SCBA (Buenos Aires)",
            "cordoba": "Cordoba",
            "entrerios": "Entre Rios",
        },
        "private": {
            "adrian_mercado": "Adrian Mercado",
            "banco_ciudad": "Banco Ciudad",
            "global_remates": "Global Remates",
            "bidbit": "BidBit",
            "agusti": "Agusti Subastas",
            "manucha": "Manucha",
            "delafuente": "De la Fuente",
            "zarate": "Zarate",
            "sitiodetiendas": "Sitio de Tiendas",
            "rematadores": "Rematadores",
        }
    })

    def validate(self) -> bool:
        """Validate configuration."""
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        return True


# Default configuration instance
config = BotConfig()
