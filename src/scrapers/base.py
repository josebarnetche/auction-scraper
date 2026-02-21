"""Abstract base scraper class."""

import asyncio
import logging
import re
import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup

from src.models.listing import AuctionListing
from src.market.price_reference import analyze_listing, detect_premium_opportunity

logger = logging.getLogger(__name__)

# Directory for downloaded documents
DOCUMENTS_DIR = Path("data/documents")
# Directory for extracted text from PDFs
DOCUMENTS_TEXT_DIR = Path("data/documents_text")
# File to track seen auction IDs
SEEN_IDS_DIR = Path("data/seen_ids")


class BaseScraper(ABC):
    """Abstract base class for auction scrapers."""

    SOURCE_NAME: str = ""
    BASE_URL: str = ""
    RATE_LIMIT_SECONDS: float = 1.0

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self._owns_session = session is None
        self._last_request_time = 0
        self._seen_ids: set[str] = set()
        self._load_seen_ids()

    def _load_seen_ids(self):
        """Load previously seen auction IDs from disk."""
        SEEN_IDS_DIR.mkdir(parents=True, exist_ok=True)
        seen_file = SEEN_IDS_DIR / f"{self.SOURCE_NAME}.txt"
        if seen_file.exists():
            with open(seen_file, "r") as f:
                self._seen_ids = set(line.strip() for line in f if line.strip())
            logger.debug(f"Loaded {len(self._seen_ids)} seen IDs for {self.SOURCE_NAME}")

    def _save_seen_ids(self):
        """Save seen auction IDs to disk."""
        SEEN_IDS_DIR.mkdir(parents=True, exist_ok=True)
        seen_file = SEEN_IDS_DIR / f"{self.SOURCE_NAME}.txt"
        with open(seen_file, "w") as f:
            for auction_id in sorted(self._seen_ids):
                f.write(f"{auction_id}\n")
        logger.debug(f"Saved {len(self._seen_ids)} seen IDs for {self.SOURCE_NAME}")

    def is_new_listing(self, auction_id: str) -> bool:
        """Check if this is a new listing we haven't seen before."""
        full_id = self.generate_id(auction_id) if ":" not in auction_id else auction_id
        return full_id not in self._seen_ids

    def mark_as_seen(self, auction_id: str):
        """Mark a listing as seen."""
        full_id = self.generate_id(auction_id) if ":" not in auction_id else auction_id
        self._seen_ids.add(full_id)

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
        # Save seen IDs when scraper exits
        self._save_seen_ids()
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

    async def download_document(self, url: str, auction_id: str, doc_type: str = "document") -> Optional[str]:
        """Download a document (PDF, etc.) and return local path.

        Args:
            url: URL of the document to download
            auction_id: ID of the auction this document belongs to
            doc_type: Type of document (condition_report, terms, spec, etc.)

        Returns:
            Local file path if successful, None otherwise
        """
        await self._rate_limit()
        try:
            # Create documents directory if needed
            doc_dir = DOCUMENTS_DIR / self.SOURCE_NAME
            doc_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename from URL hash and auction ID
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

            # Determine extension from URL or content-type
            ext = ".pdf"
            if url.lower().endswith((".pdf", ".doc", ".docx", ".jpg", ".png")):
                ext = Path(url).suffix.lower()

            filename = f"{auction_id}_{doc_type}_{url_hash}{ext}"
            filepath = doc_dir / filename

            # Skip if already downloaded
            if filepath.exists():
                logger.debug(f"Document already exists: {filepath}")
                return str(filepath)

            async with self._session.get(url) as response:
                if response.status == 200:
                    content = await response.read()

                    # Check content type for extension
                    content_type = response.headers.get("Content-Type", "")
                    if "pdf" in content_type:
                        ext = ".pdf"
                    elif "word" in content_type or "msword" in content_type:
                        ext = ".doc"

                    # Update filename with correct extension
                    if not filename.endswith(ext):
                        filename = f"{auction_id}_{doc_type}_{url_hash}{ext}"
                        filepath = doc_dir / filename

                    with open(filepath, "wb") as f:
                        f.write(content)

                    logger.info(f"Downloaded document: {filepath}")

                    # Extract text from PDF and save as .txt
                    if ext == ".pdf":
                        text_path = self.extract_pdf_text(filepath, auction_id, doc_type)
                        if text_path:
                            logger.info(f"Extracted PDF text to: {text_path}")

                    return str(filepath)
                else:
                    logger.warning(f"HTTP {response.status} downloading {url}")
                    return None

        except Exception as e:
            logger.error(f"Error downloading document {url}: {e}")
            return None

    def extract_pdf_text(self, pdf_path: str, auction_id: str, doc_type: str) -> Optional[str]:
        """Extract text from PDF and save as .txt file.

        Args:
            pdf_path: Path to the PDF file
            auction_id: ID of the auction
            doc_type: Type of document

        Returns:
            Path to the text file if successful, None otherwise
        """
        try:
            # Try to import PyPDF2 or pdfplumber
            text = ""

            try:
                import PyPDF2
                with open(pdf_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text() or ""
                        text += "\n\n"
            except ImportError:
                try:
                    import pdfplumber
                    with pdfplumber.open(pdf_path) as pdf:
                        for page in pdf.pages:
                            text += page.extract_text() or ""
                            text += "\n\n"
                except ImportError:
                    logger.warning("No PDF library available (PyPDF2 or pdfplumber). Skipping text extraction.")
                    return None

            if not text.strip():
                logger.debug(f"No text extracted from {pdf_path}")
                return None

            # Save text to file
            DOCUMENTS_TEXT_DIR.mkdir(parents=True, exist_ok=True)
            text_dir = DOCUMENTS_TEXT_DIR / self.SOURCE_NAME
            text_dir.mkdir(parents=True, exist_ok=True)

            text_filename = f"{auction_id}_{doc_type}.txt"
            text_path = text_dir / text_filename

            with open(text_path, "w", encoding="utf-8") as f:
                f.write(f"Source: {self.SOURCE_NAME}\n")
                f.write(f"Auction ID: {auction_id}\n")
                f.write(f"Document Type: {doc_type}\n")
                f.write(f"Original File: {pdf_path}\n")
                f.write("=" * 80 + "\n\n")
                f.write(text)

            return str(text_path)

        except Exception as e:
            logger.error(f"Error extracting PDF text from {pdf_path}: {e}")
            return None

    def find_document_links(self, soup: BeautifulSoup, base_url: str = "") -> list[dict]:
        """Find document links (PDFs, etc.) in a page.

        Returns:
            List of dicts with keys: url, type, title
        """
        documents = []

        # Common document link patterns
        doc_patterns = [
            (r'\.pdf$', 'pdf'),
            (r'\.docx?$', 'doc'),
            (r'condicion|condition', 'condition_report'),
            (r'informe|report', 'report'),
            (r'terminos|terms|condiciones|conditions', 'terms'),
            (r'especificacion|specification|ficha', 'spec'),
            (r'tasacion|appraisal|valuacion', 'appraisal'),
        ]

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if not href:
                continue

            href_lower = href.lower()
            link_text = link.get_text(strip=True).lower()

            # Check if it's a document
            doc_type = None

            # First check URL extension
            if re.search(r'\.(pdf|docx?|xls|xlsx)(\?|$)', href_lower, re.I):
                doc_type = "document"

            # Then check for specific document types
            for pattern, dtype in doc_patterns:
                if re.search(pattern, href_lower, re.I) or re.search(pattern, link_text, re.I):
                    doc_type = dtype
                    break

            if doc_type:
                # Make URL absolute
                if href.startswith("/"):
                    href = f"{base_url}{href}"
                elif not href.startswith("http"):
                    href = f"{base_url}/{href}"

                documents.append({
                    "url": href,
                    "type": doc_type,
                    "title": link.get_text(strip=True) or doc_type,
                })

        return documents

    def extract_price(self, text: str) -> tuple[float, str]:
        """Extract price and currency from text.

        Returns:
            Tuple of (price, currency)
        """
        currency = "ARS"
        text_upper = text.upper()

        # Detect currency
        if "USD" in text_upper or "U$S" in text_upper or "DOLAR" in text_upper or "DÓLAR" in text_upper:
            currency = "USD"

        # Try different price patterns
        patterns = [
            # $1.234.567,89 or $ 1.234.567,89
            r'\$\s*([\d.,]+)',
            # USD 1,234.56 or U$S 1.234.567
            r'(?:USD|U\$S)\s*([\d.,]+)',
            # Base: 1.234.567
            r'(?:Base|Precio|Price)[:.\s]*([\d.,]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                price_str = match.group(1)
                # Handle Argentine format: 1.234.567,89 -> 1234567.89
                if "," in price_str:
                    price_str = price_str.replace(".", "").replace(",", ".")
                else:
                    price_str = price_str.replace(".", "")

                try:
                    return float(price_str), currency
                except ValueError:
                    continue

        return 0.0, currency

    def extract_dates(self, text: str) -> dict:
        """Extract start and end dates from text.

        Returns:
            Dict with 'starts_at' and 'ends_at' datetime objects or None
        """
        from datetime import datetime

        months = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
            'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
        }

        result = {'starts_at': None, 'ends_at': None}

        # Pattern: "dd de mes de yyyy" or "dd mes yyyy"
        date_pattern = r'(\d{1,2})\s+(?:de\s+)?(\w+)\s+(?:de\s+)?(\d{4})'
        time_pattern = r'(\d{1,2})[:.](\d{2})\s*(?:hs?|horas?)?'

        # Look for start date indicators
        start_match = re.search(r'(?:inicio|abre|comienza|desde)[:\s]*' + date_pattern, text, re.I)
        if start_match:
            month = months.get(start_match.group(2).lower())
            if month:
                try:
                    time_m = re.search(time_pattern, text[start_match.end():start_match.end()+30], re.I)
                    hour, minute = (int(time_m.group(1)), int(time_m.group(2))) if time_m else (0, 0)
                    result['starts_at'] = datetime(int(start_match.group(3)), month, int(start_match.group(1)), hour, minute)
                except ValueError:
                    pass

        # Look for end date indicators
        end_match = re.search(r'(?:cierra|finaliza|hasta|cierre)[:\s]*' + date_pattern, text, re.I)
        if end_match:
            month = months.get(end_match.group(2).lower())
            if month:
                try:
                    time_m = re.search(time_pattern, text[end_match.end():end_match.end()+30], re.I)
                    hour, minute = (int(time_m.group(1)), int(time_m.group(2))) if time_m else (0, 0)
                    result['ends_at'] = datetime(int(end_match.group(3)), month, int(end_match.group(1)), hour, minute)
                except ValueError:
                    pass

        # If no specific indicators, try to find any date
        if not result['ends_at']:
            matches = re.findall(date_pattern, text)
            for match in matches:
                month = months.get(match[1].lower())
                if month:
                    try:
                        result['ends_at'] = datetime(int(match[2]), month, int(match[0]))
                        break
                    except ValueError:
                        continue

        # Also try dd/mm/yyyy format
        if not result['ends_at']:
            match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
            if match:
                try:
                    result['ends_at'] = datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)))
                except ValueError:
                    pass

        return result

    def extract_location(self, text: str) -> dict:
        """Extract location (province, city) from text.

        Returns:
            Dict with 'province' and 'city'
        """
        provinces = {
            'buenos aires': 'Buenos Aires',
            'caba': 'CABA',
            'capital federal': 'CABA',
            'córdoba': 'Córdoba',
            'cordoba': 'Córdoba',
            'santa fe': 'Santa Fe',
            'mendoza': 'Mendoza',
            'tucumán': 'Tucumán',
            'tucuman': 'Tucumán',
            'entre ríos': 'Entre Ríos',
            'entre rios': 'Entre Ríos',
            'salta': 'Salta',
            'misiones': 'Misiones',
            'chaco': 'Chaco',
            'corrientes': 'Corrientes',
            'santiago del estero': 'Santiago del Estero',
            'san juan': 'San Juan',
            'jujuy': 'Jujuy',
            'río negro': 'Río Negro',
            'rio negro': 'Río Negro',
            'neuquén': 'Neuquén',
            'neuquen': 'Neuquén',
            'formosa': 'Formosa',
            'chubut': 'Chubut',
            'san luis': 'San Luis',
            'catamarca': 'Catamarca',
            'la rioja': 'La Rioja',
            'la pampa': 'La Pampa',
            'santa cruz': 'Santa Cruz',
            'tierra del fuego': 'Tierra del Fuego',
        }

        location = {"province": "", "city": ""}
        text_lower = text.lower()

        # Find province
        for key, value in provinces.items():
            if key in text_lower:
                location["province"] = value
                break

        # Try to find city - look for "en [CITY]" pattern
        match = re.search(r'\ben\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)', text)
        if match:
            city = match.group(1).strip()
            if len(city) > 2 and city.lower() not in provinces:
                location["city"] = city

        return location

    def analyze_opportunity(self, listing: AuctionListing, blue_dollar_rate: float = 1250) -> AuctionListing:
        """Analyze listing for investment opportunities.

        Updates the listing's extra field with opportunity analysis including:
        - market_data: reference price data if available
        - discount_percent: how much below market price
        - is_opportunity: True if 30%+ below market
        - premium_info: liquidation/bankruptcy/fleet detection

        Args:
            listing: The listing to analyze
            blue_dollar_rate: Current blue dollar rate for ARS->USD conversion

        Returns:
            Updated listing with opportunity data in extra field
        """
        try:
            analysis = analyze_listing(
                title=listing.title,
                description=listing.description,
                base_price=listing.base_price,
                currency=listing.currency,
                blue_dollar_rate=blue_dollar_rate
            )

            # Update extra field with opportunity data
            extra = listing.extra.copy() if listing.extra else {}

            if analysis.get("market_data"):
                extra["market_data"] = analysis["market_data"]

            if analysis.get("discount_percent"):
                extra["discount_percent"] = analysis["discount_percent"]

            if analysis.get("is_opportunity"):
                extra["is_opportunity"] = True
                extra["opportunity_reason"] = "price_below_market"

            if analysis.get("premium_info"):
                extra["premium_info"] = analysis["premium_info"]
                if analysis["premium_info"].get("is_premium"):
                    extra["is_opportunity"] = True
                    extra["opportunity_reason"] = analysis["premium_info"].get("premium_type", "premium")

            # Create new listing with updated extra (preserving lots)
            return AuctionListing(
                id=listing.id,
                source=listing.source,
                source_url=listing.source_url,
                title=listing.title,
                description=listing.description,
                category=listing.category,
                base_price=listing.base_price,
                currency=listing.currency,
                status=listing.status,
                starts_at=listing.starts_at,
                ends_at=listing.ends_at,
                location=listing.location,
                images=listing.images,
                scraped_at=listing.scraped_at,
                extra=extra,
                lots=listing.lots,
                lot_count=listing.lot_count,
            )

        except Exception as e:
            logger.debug(f"Error analyzing opportunity for {listing.id}: {e}")
            return listing
