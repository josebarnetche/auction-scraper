"""Currency conversion utilities."""

import json
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

# Cache for blue dollar rate
_cached_rate: Optional[float] = None


def get_blue_dollar_rate(use_cache: bool = True) -> float:
    """Fetch current blue dollar rate from dolarapi.com.

    Args:
        use_cache: If True, return cached rate if available

    Returns:
        Blue dollar selling rate (venta)
    """
    global _cached_rate

    if use_cache and _cached_rate is not None:
        return _cached_rate

    try:
        url = "https://dolarapi.com/v1/dolares/blue"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AuctionRadar/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            # Use 'venta' (selling rate) for conversion
            rate = float(data.get("venta", 1415))
            logger.debug(f"Blue dollar rate from API: ${rate}")
            _cached_rate = rate
            return rate
    except Exception as e:
        logger.warning(f"Could not fetch blue dollar rate: {e}")
        # Fallback to reasonable default
        return 1415.0


def convert_to_usd(amount: float, currency: str, rate: Optional[float] = None) -> float:
    """Convert amount to USD.

    Args:
        amount: The amount to convert
        currency: Original currency (ARS or USD)
        rate: Blue dollar rate (if None, fetches current rate)

    Returns:
        Amount in USD
    """
    if currency == "USD":
        return amount

    if rate is None:
        rate = get_blue_dollar_rate()

    if rate <= 0:
        logger.warning("Invalid blue dollar rate, returning 0")
        return 0.0

    return amount / rate


def convert_to_ars(amount: float, currency: str, rate: Optional[float] = None) -> float:
    """Convert amount to ARS.

    Args:
        amount: The amount to convert
        currency: Original currency (ARS or USD)
        rate: Blue dollar rate (if None, fetches current rate)

    Returns:
        Amount in ARS
    """
    if currency == "ARS":
        return amount

    if rate is None:
        rate = get_blue_dollar_rate()

    return amount * rate


def format_price(amount: float, currency: str) -> str:
    """Format price for display.

    Args:
        amount: The amount to format
        currency: Currency (ARS or USD)

    Returns:
        Formatted price string
    """
    if currency == "USD":
        return f"USD ${amount:,.2f}"
    else:
        # Argentine format: 1.234.567,89
        formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"${formatted}"
