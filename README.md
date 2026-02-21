# Argentina Auction Radar

**One hub. All auctions. Zero friction.**

Argentina Auction Radar aggregates judicial and private auctions from 11 sources across Argentina into a single, searchable interface. Updated daily. No login required.

[![Daily Scrape](https://github.com/josebarnetche/auction-scraper/actions/workflows/scrape.yml/badge.svg)](https://github.com/josebarnetche/auction-scraper/actions)

| **Version** | **Last Updated** |
|-------------|------------------|
| `v1.0.0` | 2026-02-21 02:22 UTC |

> See [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## Why This Exists

### The Problem

Argentina has **15+ fragmented auction platforms**:
- Each requires separate registration
- Different interfaces, different data formats
- Opportunities disappear within hours
- No unified search capability
- Manual monitoring is inefficient and error-prone

**Time wasted:** 2-3 hours daily checking each source manually.

### The Solution

A **single aggregation layer** that:
- Scrapes 11 sources automatically at 00:00 Argentina time
- Normalizes all data into a consistent format
- Provides unified search, filtering, and calendar views
- Shows total estimated costs (base + commission + fees)
- Displays live countdown timers to auction end
- Runs on zero infrastructure cost (static site + GitHub Actions)

**Time saved:** Check once, see everything.

---

## Live Stats

| Metric | Value |
|--------|-------|
| **Total Sources** | 11 |
| **Active Listings** | 227 |
| **Listings with Dates** | 70 (31%) |
| **Update Frequency** | Daily at 00:00 GMT-3 |
| **Infrastructure Cost** | $0 |

---

## Data Sources

### Judicial Auctions (3)

| Source | Description | Method |
|--------|-------------|--------|
| **CSJN** | Corte Suprema de Justicia de la Nación | HTTP + ID Enumeration |
| **SCBA** | Suprema Corte de Buenos Aires | Playwright (JS) |
| **COMPR.AR** | Government asset disposals | HTTP + SSL bypass |

### Private Auction Houses (8)

| Source | Specialty | Method |
|--------|-----------|--------|
| **Adrián Mercado** | Vehicles, machinery, real estate | HTTP parsing |
| **Banco Ciudad** | Real estate (bank foreclosures) | Playwright (Angular) |
| **Global Remates** | Industrial equipment, machinery | HTTP parsing |
| **BidBit** | Vehicles, general | HTTP parsing |
| **Manucha Subastas** | Vehicles, general (Córdoba) | HTTP parsing |
| **De la Fuente** | Mixed auctions (Córdoba) | HTTP + ID enumeration |
| **Remates Zárate** | Industrial, vehicles (Buenos Aires) | HTTP parsing |
| **Sitio de Tiendas** | Ecommerce businesses | Playwright (JS) |

---

## How It Works

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      GITHUB ACTIONS                              │
│                   (Daily Cron: 00:00 GMT-3)                     │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PYTHON SCRAPERS                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │  HTTP   │  │Playwright│  │  ID     │  │  SSL    │            │
│  │ Parsing │  │(Headless)│  │  Enum   │  │ Bypass  │            │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │
│       └────────────┴────────────┴────────────┘                  │
│                         │                                        │
│                         ▼                                        │
│              ┌──────────────────┐                               │
│              │   NORMALIZER     │                               │
│              │  (Unified JSON)  │                               │
│              └────────┬─────────┘                               │
└───────────────────────┼─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STATIC FILES                                  │
│         site/api/listings.json (270+ auctions)                  │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      VERCEL CDN                                  │
│              (Auto-deploy on git push)                          │
└─────────────────────────────────────────────────────────────────┘
```

### Scraping Methods

#### 1. HTTP + BeautifulSoup (Default)
```python
html = await self.fetch_html(url)
soup = self.parse_html(html)
listings = soup.select(".auction-card")
```
- Simple, fast, low resource usage
- Works for server-rendered HTML
- **Used by:** CSJN, Adrian Mercado, Global Remates, BidBit, Manucha, Zarate

#### 2. Playwright (Headless Browser)
```python
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.goto(url, wait_until="networkidle")
    # JavaScript has now rendered
    cards = await page.query_selector_all(".card")
```
- Full JavaScript execution
- Handles SPAs (Angular, React, Vue)
- **Used by:** SCBA, Banco Ciudad, Sitio de Tiendas

#### 3. ID Enumeration
```python
# When URLs follow /auction/{id} pattern
for auction_id in range(last_known_id - 20, last_known_id + 10):
    listing = await fetch_detail(auction_id)
```
- Discovers unlisted auctions
- Catches new listings before they appear on index pages
- **Used by:** CSJN, De la Fuente

### Data Normalization

Every listing is transformed to:

```json
{
  "id": "csjn:12345",
  "source": "csjn",
  "source_url": "https://subastaselectronicasjudiciales.csjn.gov.ar/Auctions/Details/12345",
  "title": "FORD RANGER XLT 4X4 2019",
  "category": "vehicles",
  "base_price": 25000.00,
  "currency": "USD",
  "status": "published",
  "ends_at": "2024-02-25T15:00:00-03:00",
  "location": {
    "province": "Buenos Aires",
    "city": "La Plata"
  },
  "images": ["https://..."],
  "extra": {
    "commission_pct": 3.0,
    "csjn_fee_pct": 0.25,
    "total_cost_estimate": 25812.50
  }
}
```

---

## Auto-Update System

### Daily Automation

```yaml
# .github/workflows/scrape.yml
on:
  schedule:
    - cron: '0 3 * * *'  # 03:00 UTC = 00:00 Argentina (GMT-3)
```

**Execution flow:**
1. GitHub Actions starts Ubuntu runner
2. Installs Python 3.11 + dependencies
3. Installs Playwright Chromium browser
4. Runs all 11 scrapers concurrently
5. Generates `listings.json`
6. Commits changes to repository
7. Vercel auto-deploys on push

**Cost:** $0 (GitHub Actions free tier: 2,000 minutes/month)

### Manual Trigger

You can also trigger scraping manually:
1. Go to repository → Actions → Daily Auction Scrape
2. Click "Run workflow"

---

## Cost Estimation

Auction base prices don't include fees. We extract and calculate total costs:

| Fee Type | Typical % | Notes |
|----------|-----------|-------|
| Auctioneer Commission | 3-10% | Varies by house |
| CSJN Court Fee | 0.25% | Judicial only (Acordada 10/99) |
| Stamp Tax (Sellado) | 1-2% | Varies by province |
| IVA | 21% | Applied to commission |

**Formula:**
```
Total = Base + (Base × Commission%) + (Base × Court Fee%) + (Base × Stamp Tax%)
      + (Base × Commission% × IVA%)
```

---

## Local Development

### Prerequisites
- Python 3.11+
- Git

### Quick Start

```bash
# Clone repository
git clone https://github.com/josebarnetche/auction-scraper.git
cd auction-scraper

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run all scrapers
python scripts/run_scraper.py

# Preview site locally
python -m http.server 8000 --directory site
# Open http://localhost:8000
```

### Run Specific Sources

```bash
# Single source
python scripts/run_scraper.py --sources csjn

# Multiple sources
python scripts/run_scraper.py --sources csjn banco_ciudad global_remates

# Test mode (first source only)
python scripts/run_scraper.py --test
```

---

## Adding a New Scraper

### 1. Create the scraper file

```python
# src/scrapers/private/new_source.py
from src.scrapers.base import BaseScraper
from src.models.listing import AuctionListing, detect_category

class NewSourceScraper(BaseScraper):
    SOURCE_NAME = "new_source"
    BASE_URL = "https://example.com"
    RATE_LIMIT_SECONDS = 2.0

    async def scrape(self) -> list[AuctionListing]:
        html = await self.fetch_html(f"{self.BASE_URL}/auctions")
        soup = self.parse_html(html)

        listings = []
        for card in soup.select(".auction-card"):
            title = card.select_one("h3").text
            # ... extract other fields
            listings.append(AuctionListing(...))

        return listings
```

### 2. Register in run_scraper.py

```python
from src.scrapers.private.new_source import NewSourceScraper

SCRAPERS = {
    # ... existing scrapers
    "new_source": NewSourceScraper,
}
```

### 3. Test

```bash
python scripts/run_scraper.py --sources new_source
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Scrapers** | Python 3.11, aiohttp, BeautifulSoup4, Playwright |
| **Data** | JSON (static files) |
| **Frontend** | HTML5, Tailwind CSS, Vanilla JavaScript |
| **Hosting** | Vercel (static CDN) |
| **Automation** | GitHub Actions (cron) |
| **Analytics** | Google Analytics 4 |
| **Monetization** | Google AdSense, Solana donations |

---

## Limitations

- **Daily updates only:** Data refreshes at midnight Argentina time
- **Public data only:** No authenticated/private listings
- **Image availability:** Some sources don't provide product photos
- **Price disclosure:** Some auctions hide base price until registration
- **Source stability:** Scrapers may break if source sites change structure

---

## Support the Project

If this tool saves you time, consider supporting development:

**Solana (SOL):**
```
Cjz2ZPXXzThdUJp894BUDVykt1Ap9hXxuBRTcso17By2
```

---

## License

MIT License - See [LICENSE](LICENSE)

---

## Credits

Developed by **[Memola Medios S.A.S.](https://www.memola.com.ar)**

CUIT: 30-71863222-2 | Contact: [agencia@memola.com.ar](mailto:agencia@memola.com.ar)
