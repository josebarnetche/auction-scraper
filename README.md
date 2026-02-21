# Argentina Auction Scraper

Monitors judicial and private auctions in Argentina, compares prices against market data (MercadoLibre), and identifies opportunities with 30%+ discounts.

## Features

- Scrapes 8 auction sources (judicial and private)
- Compares against MercadoLibre market prices
- Uses blue dollar rates for ARS/USD conversion
- Generates static dashboard with opportunities
- Daily automated scraping via GitHub Actions

## Auction Sources

### Judicial
- **CSJN** - Supreme Court auctions
- **SCBA** - Buenos Aires Province
- **COMPR.AR** - Government assets

### Private
- Adrián Mercado
- Banco Ciudad
- Global Remates
- BidBit
- Manucha Subastas

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Run all scrapers

```bash
python scripts/run_scraper.py --sources all
```

### Run specific sources

```bash
python scripts/run_scraper.py --sources csjn banco_ciudad
```

### Test mode (single source)

```bash
python scripts/run_scraper.py --test
```

### Generate static site

```bash
python scripts/generate_site.py
```

### Test price comparison

```bash
python scripts/test_comparison.py --sample 5
```

### Local preview

```bash
python -m http.server 8000 --directory site
# Open http://localhost:8000
```

## Project Structure

```
auction-scraper/
├── src/
│   ├── scrapers/         # Source scrapers
│   │   ├── base.py       # Abstract base class
│   │   ├── judicial/     # Government auctions
│   │   └── private/      # Private auctioneers
│   ├── market/           # Price comparison
│   │   ├── mercadolibre.py
│   │   ├── currency.py   # Blue dollar rates
│   │   └── matcher.py    # Item matching
│   ├── models/           # Data models
│   ├── processors/       # Analysis
│   └── storage/          # JSON storage
├── site/                 # Static site output
├── scripts/              # CLI tools
└── data/                 # Scraped data
```

## Data Model

```python
@dataclass
class AuctionListing:
    id: str
    source: str           # csjn, scba, adrian_mercado, etc.
    source_url: str
    title: str
    description: str
    category: str         # vehicles, real_estate, machinery, other
    base_price: float
    currency: str         # ARS or USD
    status: str           # published, ongoing, finalized
    starts_at: datetime
    ends_at: datetime
    location: dict
    images: list[str]

@dataclass
class Opportunity:
    listing: AuctionListing
    market_median_usd: float
    discount_percentage: float
    confidence_score: float
    is_flagged: bool      # True if >= 30% discount
```

## Deployment

### GitHub Pages (via Actions)

Push to `main` branch - the workflow will automatically:
1. Run all scrapers
2. Generate the static site
3. Deploy to GitHub Pages

### Manual deployment

```bash
./scripts/publish.sh site/
```

## API Endpoints

The static site generates JSON files:

- `site/api/opportunities.json` - Flagged opportunities
- `site/api/listings.json` - All active auctions

## MercadoLibre Integration

The system uses MercadoLibre for market price comparison. Due to API authentication requirements:

- **Demo Mode (default)**: Uses sample market prices for testing
- **Production Mode**: Set `ML_ACCESS_TOKEN` environment variable

To get an ML access token:
1. Register at https://developers.mercadolibre.com.ar/
2. Create an application
3. Follow OAuth flow to get access token
4. Export: `export ML_ACCESS_TOKEN=your_token_here`

## Notes

- Auction site scrapers may need adjustment as websites change their structure
- Some judicial sites may be temporarily unavailable (HTTP 500)
- Blue dollar rates are fetched from DolarAPI.com with 5-minute caching
- Demo mode generates realistic price estimates based on category and keywords

## License

MIT
