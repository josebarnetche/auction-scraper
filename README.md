# Subasto

**One hub. All auctions. Zero friction.**

Subasto aggregates judicial and private auctions from 15+ sources across Argentina into a single, searchable interface. Updated daily. No login required.

**Website:** [subasto.com.ar](https://subasto.com.ar) *(nameservers pending)*

[![Daily Scrape](https://github.com/josebarnetche/auction-scraper/actions/workflows/scrape.yml/badge.svg)](https://github.com/josebarnetche/auction-scraper/actions)

| **Version** | **Last Updated** |
|-------------|------------------|
| `v1.4.0` | 2026-02-21 |

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
- Scrapes 15+ sources automatically at 00:00 Argentina time
- Normalizes all data into a consistent format
- Provides unified search, filtering, and calendar views
- Shows total estimated costs (base + commission + fees)
- Displays live countdown timers to auction end
- Supports **lot-level browsing** within auctions
- Ranks **judicial auctions first** (better deals, more transparency)
- Runs on zero infrastructure cost (static site + GitHub Actions)

**Time saved:** Check once, see everything.

---

## Live Stats

| Metric | Value |
|--------|-------|
| **Total Sources** | 15 |
| **Active Listings** | 873 |
| **Judicial Listings** | 621 (71%) |
| **Lot-Level Data** | 31 lots across 8 auctions |
| **Update Frequency** | Daily at 00:00 GMT-3 |
| **Infrastructure Cost** | $0 |

---

## Data Sources

### Judicial Auctions (5) - *Ranked First*

| Source | Description | Method | Status |
|--------|-------------|--------|--------|
| **CSJN** | Corte Suprema de Justicia de la Nación | HTTP + ID Enumeration | ✅ Working |
| **SCBA** | Suprema Corte de Buenos Aires | Playwright (JS) | ✅ Working |
| **Córdoba** | Poder Judicial de Córdoba | REST API | ✅ Working |
| **Entre Ríos** | Poder Judicial de Entre Ríos | Playwright (JS) | ✅ Working |
| **COMPR.AR** | Government asset disposals | HTTP + SSL bypass | ⚠️ Needs Help |

> **Help Wanted: COMPR.AR Scraper**
>
> The COMPR.AR government auction platform uses ASP.NET session tracking that breaks our current scraper.
> If you have experience with ASP.NET cookie handling or Playwright session management, we'd love your help!
> Please open an issue or PR at [github.com/josebarnetche/auction-scraper](https://github.com/josebarnetche/auction-scraper/issues)

### Private Auction Houses (10)

| Source | Specialty | Method |
|--------|-----------|--------|
| **Adrián Mercado** | Vehicles, machinery, real estate | HTTP parsing |
| **Banco Ciudad** | Real estate, equipment (lot-level) | Playwright + API |
| **Global Remates** | Industrial equipment, machinery | HTTP parsing |
| **BidBit** | Vehicles, general | HTTP parsing |
| **Agusti Subastas** | Vehicles, machinery | HTTP parsing |
| **Manucha Subastas** | Vehicles, general (Córdoba) | HTTP parsing |
| **De la Fuente** | Mixed auctions (Córdoba) | HTTP + ID enumeration |
| **Remates Zárate** | Industrial, vehicles (Buenos Aires) | HTTP parsing |
| **Sitio de Tiendas** | Ecommerce businesses | Playwright (JS) |
| **Rematadores** | General auctions | HTTP parsing |

---

## New: Lot-Level Architecture

Subasto now supports **individual lot browsing** within auctions:

```
BEFORE (Auction-Level):
┌─────────────────────────────────────┐
│ banco_ciudad:3812                   │
│ "Equipamiento Cabinas Peaje"        │
│ USD 42,920,000 (sum of all lots)    │
└─────────────────────────────────────┘

AFTER (Lot-Level):
┌─────────────────────────────────────┐
│ Auction: banco_ciudad:3812          │
│ "Equipamiento Cabinas Peaje"        │
├─────────────────────────────────────┤
│ LOT 1: 100 Computadoras Advantech   │
│        ARS $42,920,000 (~USD $30k)  │
├─────────────────────────────────────┤
│ LOT 2: 18 Elementos Provisionales   │
│        ARS $5,328,000 (~USD $3.7k)  │
├─────────────────────────────────────┤
│ LOT 3: 65 Cámaras Axis/Red          │
│        ARS $2,020,200 (~USD $1.4k)  │
└─────────────────────────────────────┘
```

### API Structure

```json
{
  "blue_dollar_rate": 1430,
  "lot_stats": {
    "total_lots": 31,
    "auctions_with_lots": 8,
    "analyzed_lots": 0
  },
  "lots": [
    {
      "lot_id": "bc:3812:1",
      "auction_id": "banco_ciudad:3812",
      "title": "100 Computadoras Industriales",
      "base_price": 42920000,
      "currency": "ARS",
      "base_price_usd": 30014,
      "opportunity_score": null
    }
  ],
  "listings": [...]
}
```

---

## Currency Support

All listings include both ARS and USD prices for easy comparison:

| Field | Description |
|-------|-------------|
| `currency` | Original currency (ARS or USD) |
| `base_price` | Price in original currency |
| `base_price_usd` | Converted to USD at current blue dollar rate |
| `blue_dollar_rate` | Live rate from dolarapi.com |

---

## Premium Curated Opportunities

Beyond automated scraping, we manually research **high-value opportunities**:

| Category | What We Look For |
|----------|-----------------|
| **Factory Liquidations** | Complete plant closures with industrial equipment |
| **Heavy Equipment** | Cranes, bulldozers, excavators at 40%+ discount |
| **Automation Systems** | Warehouse robots, CNC machines, production lines |
| **Fleet Liquidations** | Corporate vehicle renewals (50+ units) |
| **Bankruptcies** | Court-ordered sales with forced pricing |

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

# Run specific sources (judicial first)
python scripts/run_scraper.py --sources csjn scba cordoba

# Preview site locally
python -m http.server 8000 --directory site
# Open http://localhost:8000
```

### AI Analysis (Optional)

Analyze lots with Claude for opportunity scoring:

```bash
# Dry run - see what would be analyzed
python scripts/analyze_lots.py --dry-run

# Run analysis (requires ANTHROPIC_API_KEY)
python scripts/analyze_lots.py --max-lots 50
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Scrapers** | Python 3.11, aiohttp, BeautifulSoup4, Playwright |
| **AI Analysis** | Claude Haiku (optional) |
| **Data** | JSON (static files) |
| **Frontend** | HTML5, Tailwind CSS, Vanilla JavaScript |
| **Hosting** | Vercel (static CDN) |
| **Domain** | subasto.com.ar |
| **Automation** | GitHub Actions (cron) |

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
