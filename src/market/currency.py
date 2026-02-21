"""Currency conversion using DolarAPI for blue dollar rates."""

import logging
import time
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class CurrencyConverter:
    """Handles ARS/USD conversion using blue dollar rates."""

    DOLAR_API_URL = "https://dolarapi.com/v1/dolares/blue"
    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self):
        self._cached_rate: Optional[float] = None
        self._cache_time: float = 0

    async def get_blue_dollar_rate(self) -> float:
        """Get current blue dollar sell rate (ARS per USD).

        Returns cached value if available and fresh.
        """
        now = time.time()
        if self._cached_rate and (now - self._cache_time) < self.CACHE_TTL_SECONDS:
            return self._cached_rate

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(self.DOLAR_API_URL)
                if response.status_code == 200:
                    data = response.json()
                    # Use "venta" (sell) rate
                    self._cached_rate = float(data.get("venta", 1000))
                    self._cache_time = now
                    logger.info(f"Updated blue dollar rate: {self._cached_rate}")
                    return self._cached_rate
        except Exception as e:
            logger.error(f"Failed to fetch dollar rate: {e}")

        # Fallback to cached or default
        if self._cached_rate:
            return self._cached_rate

        # Hardcoded fallback (should be updated periodically)
        return 1200.0

    async def ars_to_usd(self, amount: float) -> float:
        """Convert ARS to USD."""
        rate = await self.get_blue_dollar_rate()
        return amount / rate

    async def usd_to_ars(self, amount: float) -> float:
        """Convert USD to ARS."""
        rate = await self.get_blue_dollar_rate()
        return amount * rate

    async def normalize_to_usd(self, amount: float, currency: str) -> float:
        """Normalize any amount to USD."""
        if currency.upper() == "USD":
            return amount
        elif currency.upper() == "ARS":
            return await self.ars_to_usd(amount)
        else:
            logger.warning(f"Unknown currency: {currency}, treating as ARS")
            return await self.ars_to_usd(amount)


# Global instance
converter = CurrencyConverter()
