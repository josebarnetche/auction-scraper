# Subasto

**Buy assets at 30-70% below market. Cents on the dollar.**

Subasto aggregates judicial and private auctions from 14 sources across Argentina. Vehicles, real estate, machinery, industrial equipment - all at liquidation prices. Updated daily. No login required.

**Website:** [subasto.com.ar](https://subasto.com.ar)

## Why Auctions = Free Money

| What You Pay | What It's Worth | Your Profit |
|--------------|-----------------|-------------|
| $15,000 | $35,000 (vehicle) | **+133%** |
| $50,000 | $120,000 (machinery) | **+140%** |
| $80,000 | $200,000 (real estate) | **+150%** |

Judicial auctions force sales. Sellers can't negotiate. Buyers win.

[![Daily Scrape](https://github.com/josebarnetche/auction-scraper/actions/workflows/scrape.yml/badge.svg)](https://github.com/josebarnetche/auction-scraper/actions)

| **Version** | **Last Updated** |
|-------------|------------------|
| `v1.8.0` | 2026-02-22 |

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
- Shows **total estimated costs** (base + commission + IVA 21% + fees)
- Displays live countdown timers to auction end
- Supports **lot-level browsing** within auctions
- Ranks **judicial auctions first** (better deals, more transparency)
- **API for agents** with USDC micropayments on Base network
- Runs on zero infrastructure cost (static site + GitHub Actions)

**Time saved:** Check once, see everything.

---

## Live Stats

| Metric | Value |
|--------|-------|
| **Total Sources** | 14 |
| **Active Listings** | 850+ |
| **Judicial Listings** | 620+ (72%) |
| **Lot-Level Data** | 200+ lots across 18 auctions |
| **Update Frequency** | Daily at 00:00 GMT-3 |
| **Infrastructure Cost** | $0 |

### Categories

| Category | Description | % of Listings |
|----------|-------------|---------------|
| **General Goods** | Furniture, clothing, appliances, electronics, tools | 45% |
| **Real Estate** | Houses, apartments, land, commercial properties | 30% |
| **Vehicles** | Cars, trucks, motorcycles, buses | 15% |
| **Machinery** | Industrial equipment, agricultural, construction | 6% |
| **Other** | Miscellaneous items | 4% |

---

## Features

### NEW in v1.8.0

| Feature | Description |
|---------|-------------|
| **Credit System** | Buy USDC credits on Base, use across all paid features |
| **Telegram Bot** | Alerts, search, daily digest via @SubastoBot |
| **Interactive Map** | Filter auctions by distance with Leaflet/OpenStreetMap |
| **AI Analysis** | Claude Haiku analyzes opportunities for flip potential |
| **Smart Search** | Natural language queries ("cars under 10k in córdoba") |
| **PWA** | Install as app on mobile, works offline |
| **Multi-Language** | Spanish, English, Portuguese |
| **Bulk Export** | Download CSV, Excel, or PDF of listings |
| **Email Digest** | Daily/weekly summaries to your inbox |
| **Investment Calculator** | Calculate ROI before bidding |
| **Educational Guides** | 7 pages on how to win at auctions |

### Currency Selector
Toggle between **ARS** and **USD** display. All prices convert automatically using the live blue dollar rate from [dolarapi.com](https://dolarapi.com).

### Calendar View
See auctions by **closing date**. Only future auctions are shown. Click any date to see what's closing that day with exact closing times.

### Mobile Optimized
- Responsive design for all screen sizes
- Touch-friendly navigation with hamburger menu
- No hover effects causing scroll issues on mobile

### SEO & Social Sharing
- Full Open Graph and Twitter Card support
- Custom favicon and OG image
- Spanish language meta tags for Argentine search engines

### Cost Breakdown
Every listing shows **total estimated cost** including:

| Type | Commission | Fees | IVA |
|------|------------|------|-----|
| **Judicial** | 3% | 0.25% arancel | 21% s/base |
| **Private** | 10% | - | 21% s/base |

Example: $100,000 base price (judicial)
```
Base           $100,000
+ Comisión 3%    $3,000
+ Arancel 0.25%    $250
+ IVA 21%        $21,000
─────────────────────────
Total Est.     $124,250
```

> **Note:** IVA 21% applies to the base price. Real estate may be exempt. Check with auction house for specific tax treatment.

---

## Data Sources

### Judicial Auctions (4) - *Ranked First*

| Source | Description | Method | Status |
|--------|-------------|--------|--------|
| **CSJN** | Corte Suprema de Justicia de la Nación | HTTP + ID Enumeration | ✅ Working |
| **SCBA** | Suprema Corte de Buenos Aires | Playwright (JS) | ✅ Working |
| **Córdoba** | Poder Judicial de Córdoba | REST API | ✅ Working |
| **Entre Ríos** | Poder Judicial de Entre Ríos | Playwright (JS) | ✅ Working |

### Private Auction Houses (10)

| Source | Specialty | Method |
|--------|-----------|--------|
| **Adrián Mercado** | Vehicles, machinery, real estate (lot-level) | HTTP + JSON parsing |
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

## How to Make Money

### Strategy 1: Flip Vehicles
1. Find vehicles 40%+ below market (use our discount filter)
2. Win auction, pay ~$15,000
3. List on MercadoLibre at $25,000
4. Profit: **$10,000** in 2-3 weeks

### Strategy 2: Source Inventory
- Industrial equipment dealers: buy at 30%, sell at 70%
- Auto parts: salvage vehicles for parts resale
- Restaurant equipment: buy liquidated, resell to new businesses

### Strategy 3: Real Estate Arbitrage
- Judicial real estate sells at 50-60% of market
- No negotiation, forced sale
- Rent or flip for 40%+ ROI

### Strategy 4: Export
- Argentine machinery is cheap in USD terms
- Blue dollar rate = extra 20% discount for foreign buyers
- Ship to Paraguay, Chile, Brazil

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

## API for Agents

Programmatic access with USDC micropayments on Base network.

### Endpoints

| Endpoint | Price | Description |
|----------|-------|-------------|
| `GET /api/v1/price` | Free | Pricing info and payment wallet |
| `GET /api/v1/premium?tx=0x...` | $0.01 | Curated premium picks (~12) |
| `GET /api/v1/opportunities?tx=0x...` | $0.02 | Hot deals 40%+ discount (~70) |
| `GET /api/v1/auctions?tx=0x...` | $0.05 | All 864+ listings |
| `GET /api/v1/search?q=...` | 1 credit | Natural language search |
| `GET /api/v1/analyze?id=...` | 2 credits | AI analysis of listing |
| `GET /api/v1/export/csv` | 5 credits | Bulk CSV export |
| `GET /api/v1/nearby?lat=...&lng=...` | Free | Location-based filtering |
| `POST /api/v1/credits/buy` | - | Purchase credit packages |
| `GET /api/v1/credits/balance` | Free | Check credit balance |

### How It Works

```
1. GET /api/v1/price → get payment wallet
2. Send USDC on Base to 0x29E007249b744892a1da17F4289f75cfC871d6Fe
3. GET /api/v1/auctions?tx=YOUR_TX_HASH → receive data
```

- **Network:** Base (Coinbase L2)
- **Token:** USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`)
- **Verification:** On-chain, automatic
- **OpenAPI Spec:** `/api/v1/openapi.json`

---

## Support the Project

If this tool saves you time, consider supporting development:

**Base (USDC):**
```
0x29E007249b744892a1da17F4289f75cfC871d6Fe
```

**Solana (SOL):**
```
Cjz2ZPXXzThdUJp894BUDVykt1Ap9hXxuBRTcso17By2
```

---

## License

MIT License - See [LICENSE](LICENSE)

---

## Credits

Built by **[@josebarnetche](https://x.com/josebarnetche)**

Idea by **[@hernan__cc](https://x.com/hernan__cc)**

---

**[Memola Medios S.A.S.](https://www.memola.com.ar)** | CUIT: 30-71863222-2
