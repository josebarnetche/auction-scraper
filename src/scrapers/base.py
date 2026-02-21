"""Abstract base scraper class."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup

from src.models.listing import AuctionListing

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for auction scrapers."""

    SOURCE_NAME: str = ""
    BASE_URL: str = ""
    RATE_LIMIT_SECONDS: float = 1.0

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self._owns_session = session is None
        self._last_request_time = 0

    async def __aenter__(self):
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._owns_session and self._session:
            await self._session.close()

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self.RATE_LIMIT_SECONDS:
            await asyncio.sleep(self.RATE_LIMIT_SECONDS - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL."""
        await self._rate_limit()
        try:
            async with self._session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                logger.warning(f"HTTP {response.status} for {url}")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"Request failed for {url}: {e}")
            return None

    async def fetch_json(self, url: str) -> Optional[dict]:
        """Fetch JSON content from URL."""
        await self._rate_limit()
        try:
            async with self._session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                logger.warning(f"HTTP {response.status} for {url}")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"Request failed for {url}: {e}")
            return None

    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML into BeautifulSoup object."""
        return BeautifulSoup(html, "lxml")

    @abstractmethod
    async def scrape(self) -> list[AuctionListing]:
        """Scrape all listings from the source.

        Returns:
            List of AuctionListing objects
        """
        pass

    @abstractmethod
    def parse_listing(self, element) -> Optional[AuctionListing]:
        """Parse a single listing element.

        Args:
            element: HTML element containing listing data

        Returns:
            AuctionListing if successful, None otherwise
        """
        pass

    def generate_id(self, *parts) -> str:
        """Generate unique ID from parts."""
        return f"{self.SOURCE_NAME}:{':'.join(str(p) for p in parts)}"
