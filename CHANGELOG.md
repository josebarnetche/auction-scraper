# Changelog

All notable changes to **Subasto** (formerly Argentina Auction Radar) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Website:** [subasto.com.ar](https://subasto.com.ar)

---

## [1.6.1] - 2026-02-21

### Added
- **SEO & Agent Discovery**
  - `robots.txt` with AI crawler hints
  - `sitemap.xml` for search engines
  - `.well-known/ai-plugin.json` for ChatGPT/Claude plugin discovery
  - Schema.org structured data (WebApplication)
  - Enhanced meta tags with agent-friendly keywords
  - OpenAPI spec updated with marketing descriptions

- **Marketing Content**
  - "How to Make Money" section in README
  - Value proposition: "30-70% below market"
  - Profit examples and strategies
  - IVA clarification note

### Changed
- Updated keywords: "cents on dollar", "cheap assets", "liquidation sales"
- OpenAPI descriptions focus on ROI and profit potential
- README header emphasizes value proposition

---

## [1.6.0] - 2026-02-21

### Added
- **Pay-Per-Request API for AI Agents** - Programmatic access with USDC micropayments on Base network
  - `/api/v1/price` - Free endpoint showing pricing and payment instructions
  - `/api/v1/premium` - Curated premium picks (~12) - **$0.01 USDC**
  - `/api/v1/opportunities` - Hot deals 40%+ discount (~70) - **$0.02 USDC**
  - `/api/v1/auctions` - All 864+ listings - **$0.05 USDC**
  - On-chain payment verification via Base RPC
  - Anti-replay protection (tx hashes can only be used once)
  - OpenAPI 3.1 spec at `/api/v1/openapi.json` for agent discovery

- **API Section on Homepage** - Interactive documentation at `/#api`
  - Pricing cards for all endpoints
  - Step-by-step payment flow
  - Technical details (network, token, wallet)
  - Example response preview

- **IVA & Fees on Auction Prices** - Total cost now includes all fees
  - IVA 21% calculated on commission
  - Judicial: Base + 3% comisión + 0.25% arancel + IVA
  - Private: Base + 10% comisión + IVA
  - Breakdown shown in listing cards

### Technical
- Vercel serverless functions in TypeScript
- Payment verification using viem library
- Volume-based pricing (smaller datasets cost less)
- USDC contract: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` (Base)
- Payment wallet: `0x29E007249b744892a1da17F4289f75cfC871d6Fe`

---

## [1.5.1] - 2026-02-21

### Added
- **Adrián Mercado Lot Extraction** - Individual lots now extracted from multi-lot auctions
  - Parses embedded JSON data from auction pages
  - Extracts lot title, description, price, and images
  - Converts ARS prices to USD using blue dollar rate
  - 171 new lots extracted across 10 auctions

### Changed
- **Domain Live** - subasto.com.ar nameservers configured and active
- Total lots: 31 → 202 (+550%)
- Auctions with lots: 8 → 18

---

## [1.5.0] - 2026-02-21

### Added
- **SEO & Social Media Optimization**
  - Open Graph meta tags for Facebook/LinkedIn sharing
  - Twitter Card meta tags for Twitter sharing
  - Meta description with Spanish keywords
  - Canonical URL, robots directive, Spanish language (`lang="es"`)

- **Favicon & Branding**
  - SVG favicon with compass/radar design
  - PNG favicons (32x32, 16x16, 180x180 apple-touch-icon)
  - OG image (1200x630) for social sharing
  - Theme color (#eab308 yellow)

- **Currency Selector in Header**
  - ARS/USD toggle moved from floating button to navigation bar
  - Price range slider updates to show ARS values when selected
  - All prices dynamically convert based on blue dollar rate

- **Mobile Navigation**
  - Hamburger menu for mobile devices
  - Slide-down navigation menu
  - Menu closes when link is clicked

### Changed
- **Calendar Shows Closing Dates**
  - Auctions grouped by `ends_at` (closing date) instead of start date
  - Past dates filtered out (only future auctions shown)
  - Time display shows "Cierra: HH:MM" (Closes at)

- **Ended Auctions Filtered**
  - Server-side: `generate_site.py` skips auctions where `ends_at < now`
  - Client-side: JavaScript also filters expired auctions on load
  - Listings reduced from 873 to 864

- **Judicial Source Priority in Opportunities**
  - Judicial sources get +100 points in opportunity ranking
  - Priority private sources get +40 points
  - Same discount = judicial ranks higher

### Fixed
- **Mobile Performance**
  - Disabled hover scale/zoom effects on touch devices
  - Uses `@media (hover: hover)` for desktop-only effects
  - Eliminates scroll lag and jank on mobile

- **Torno Automático Pricing**
  - Added specific lathe types with accurate prices:
    - `torno automatico`: $1,500-6,000 (typical $3,500)
    - `torno revolver`: $2,000-8,000 (typical $4,000)
    - `torno paralelo`: $3,000-15,000 (typical $6,000)
    - `torno cnc`: $15,000-80,000 (typical $35,000)
  - Generic `torno` reduced to $3,000-40,000 (typical $8,000)

- **GMT-3 Time Display**
  - Restored missing `gmt3-time` element in header
  - Fixed JavaScript error from null element reference

---

## [1.4.1] - 2026-02-21

### Fixed
- **Category Detection Order** - Real estate keywords now checked before machinery
  - "TERRENO EN SECTOR INDUSTRIAL" now correctly categorized as `real_estate`
  - "GRUPO ELECTROGENO HONDA" correctly categorized as `machinery`
  - Removed generic "industrial" keyword to avoid false positives

- **Banco Ciudad Currency** - USD prices no longer misdetected as ARS
  - Scraper now detects `U$S` price format before checking payment terms
  - Site generation adds heuristic for real estate listings > $50k USD

- **Agusti Logo Images** - Filtered out branding images
  - `home_agusti_subastas_X.png` and `Empresas/` logos now excluded
  - Product images from `imagenes.agustisubastas.com.ar/dtsImages/Lotes/` shown instead

- **Market Price Accuracy** - More realistic pricing for specific equipment
  - Small presses (20-ton): $3,000-8,000 typical instead of $15,000
  - Portable Honda generators: $800-1,200 typical instead of $20,000
  - Added specific entries for `prensa 20 ton`, `prensa de temple`, `prensa hidraulica`

---

## [1.4.0] - 2026-02-21

### Rebranding
- **New Name:** Subasto (formerly Argentina Auction Radar)
- **New Domain:** subasto.com.ar

### Added
- **Lot-Level Data Architecture** - Browse individual lots within auctions
  - New `LotItem` dataclass with full lot details
  - Banco Ciudad scraper extracts 31 lots across 8 auctions
  - Flat `lots[]` array in API for easy browsing
  - `lot_stats` metadata in listings.json

- **AI Analysis Pipeline** (optional, requires Anthropic API key)
  - `scripts/analyze_lots.py` - Batch analyze lots with Claude Haiku
  - `src/analysis/lot_analyzer.py` - Extract specs, market value, opportunity score
  - `src/analysis/lot_filter.py` - Filter lots worth analyzing (price range, category)

- **Currency Utilities**
  - `src/utils/currency.py` - Blue dollar rate fetching from dolarapi.com
  - `base_price_usd` field on all listings for USD comparison
  - `base_price_ars` field on USD listings for ARS display

- **Source Ranking**
  - Judicial sources (CSJN, SCBA, Córdoba, Entre Ríos) ranked first (+500 points)
  - Priority private sources (Banco Ciudad, Global Remates, Adrian Mercado) ranked second (+300 points)
  - `source_type` field: "judicial" or "private" for frontend filtering

- **New Scrapers**
  - Córdoba Judicial (508 listings via REST API)
  - Entre Ríos Judicial (13 listings)
  - Agusti Subastas (106 listings with 43 opportunities)

### Changed
- Total listings: 227 → 873 (+285%)
- Judicial listings now represent 71% of total (621/873)
- Banco Ciudad scraper enhanced with lot-level extraction

### Technical
- New files:
  - `scripts/explore_banco_ciudad.py` - API discovery for BC endpoints
  - `scripts/analyze_lots.py` - Batch AI analysis runner
  - `src/analysis/__init__.py`, `lot_filter.py`, `lot_analyzer.py`
  - `src/utils/__init__.py`, `currency.py`
- Modified `src/scrapers/base.py` to preserve lots in `analyze_opportunity()`
- Modified `scripts/generate_site.py` for dual-view output (auctions + lots)

---

## [1.3.0] - 2026-02-21

### Added
- **Curated Premium Opportunities** - Hand-researched high-value deals beyond automated scraping
- New `data/curated/premium_opportunities.json` for manually researched opportunities
- Premium opportunity detection using parallel AI agent research
- Premium listings get +200 priority score, always appear in top 5
- New fields: `is_premium`, `premium_type`, `why_premium`, `estimated_value_usd`
- Top opportunities expanded from 3 to 5 to showcase premium content

### How Premium Research Works
1. **Parallel AI Agents** - Multiple specialized agents search simultaneously:
   - Industrial machinery auctions (CNC, presses, forklifts)
   - Company liquidations and bankruptcies
   - Agricultural equipment deals
   - Vehicle fleet renewals
   - Premium real estate opportunities
2. **Web Research** - Agents search news, auction houses, government bulletins
3. **Market Analysis** - Cross-reference auction prices with market values
4. **Curation** - Best opportunities compiled into `premium_opportunities.json`

### Premium Categories
| Type | Description |
|------|-------------|
| `factory_liquidation` | Complete factory closures with equipment |
| `heavy_equipment` | Cranes, bulldozers, excavators |
| `automation` | Robots, warehouse systems, CNC |
| `fleet_liquidation` | Corporate vehicle fleet renewals |
| `bankruptcy` | Court-ordered asset sales |
| `corporate_fleet` | Telecom, energy company vehicles |
| `real_estate_deal` | Properties 40%+ below market |
| `brand_acquisition` | Business brands + equipment |
| `government_surplus` | Provincial/municipal equipment |

### Technical
- Premium opportunities loaded from `data/curated/` directory
- Discount estimates parsed from ranges (e.g., "45-55%" → 50%)
- Before-March detection for time-sensitive deals
- Premium count tracked in `listings.json` metadata

---

## [1.2.0] - 2026-02-21

### Changed
- **Market prices now use real data** - No more fake multipliers
- Market prices scraped from Autocosmos (vehicles) and ZonaProp (real estate)
- Discount/market value only shown when real comparable data exists
- If no market data found, comparison section is hidden (not fake estimates)

### Added
- `src/market/autocosmos.py` - Vehicle price scraper
- `src/market/zonaprop.py` - Real estate price scraper
- `src/market/price_manager.py` - Manages price fetching and caching
- `data/market_prices.json` - Cached market prices

### Fixed
- Removed hardcoded `MARKET_MULTIPLIERS` that showed unrealistic discounts
- Frontend now checks for `auction.market_data` before showing comparisons
- "Best Deals" section only shows items with real market data

### Technical
- Market price fetching runs during daily scrape at 00:00 GMT-3
- Best-effort fetching - scraper continues if external sites unavailable
- Price confidence scoring based on sample size and variance

---

## [1.1.0] - 2026-02-21

### Added
- **UnicornStudio animated background** - Beautiful flowing yellow/gold glowing light effect
- **Lenis smooth scroll** - Professional smooth scrolling for anchor navigation
- **ads.txt** - Google AdSense publisher verification file

### Changed
- Background uses UnicornStudio aura effect with `saturate-200 hue-rotate-180`
- Warm yellow glow with gradient mask overlay
- Improved scroll behavior with GSAP ScrollTrigger integration

### Fixed
- SCBA dates now use "Inicio de inscripción" (registration start) instead of end date
- SCBA date extraction now fetches detail pages for 100% date coverage (90/90 listings)
- Dates include time component (e.g., "2026-02-03T09:00:00")

### Technical
- UnicornStudio project: `FixNvEwvWwbu3QX9qC3F`
- Smooth anchor link scrolling with 80px navbar offset
- Opacity-70 with subtle gradient overlay for readability

---

## [1.0.0] - 2026-02-21

### Added
- Date extraction for Global Remates (85% coverage)
- Date extraction for Adrian Mercado (28% coverage)
- Date extraction for SCBA scraper
- Calendar now displays 70+ auctions with dates across 21 unique dates

### Fixed
- Global Remates titles no longer show "Su Oferta" button text
- Title cleaning removes dates, "Incremento", and noise patterns
- Calendar uses both `ends_at` and `starts_at` fields

---

## [0.12.0] - 2026-02-21

### Fixed
- Global Remates scraper title extraction (skip button text)
- Calendar date display to use `starts_at` as fallback

---

## [0.11.0] - 2026-02-21

### Added
- Video background from Pixabay (city/buildings theme)

### Fixed
- Banco Ciudad scraper improved title parsing
- Remove "Previous", "Next", date patterns from titles

---

## [0.10.0] - 2026-02-21

### Added
- Interactive calendar with month/year navigation
- Clickable dates showing auction counts
- Selected date detail panel with auction list
- Spanish localization for calendar

---

## [0.9.0] - 2026-02-21

### Added
- Quality-based ranking system for auctions
- Auctions with images ranked higher (+100 points)
- Price presence adds +50 points
- End date adds +30 points
- Description quality scoring

### Fixed
- De la Fuente scraper cleaned (removed rural.com.uy junk data)
- Filter generic "Remate #XXX" titles

---

## [0.8.0] - 2026-02-21

### Changed
- Corporate footer branding: Memola Medios S.A.S.
- Professional CUIT display format

---

## [0.7.0] - 2026-02-21

### Changed
- Complete README rewrite with technical documentation
- System architecture diagram
- Scraping methods documentation
- Local development guide

### Added
- MIT License file

### Fixed
- CSJN image extraction (skip ribbon.png, prioritize AuctionImages)

---

## [0.6.0] - 2026-02-21

### Fixed
- SCBA scraper: Playwright for JS rendering (90 listings)
- Banco Ciudad scraper: Playwright for Angular (46 listings)
- Global Remates scraper: Correct URL patterns (33 listings)

### Changed
- Total listings increased from 121 to 270

---

## [0.5.0] - 2026-02-20

### Added
- Google Analytics 4 integration (gtag.js)
- Google AdSense script

---

## [0.4.0] - 2026-02-20

### Added
- GitHub Actions workflow for daily scraping (00:00 GMT-3)
- Sitio de Tiendas scraper (ecommerce businesses)
- Solana donation wallet address

### Changed
- Automated daily updates via cron job

---

## [0.3.0] - 2026-02-20

### Added
- Cost breakdown with commission estimates
- Live countdown timers to auction end
- Total cost calculation (base + fees)

### Fixed
- Image extraction prioritizes product photos
- Skip logo/icon/avatar images

---

## [0.2.0] - 2026-02-20

### Added
- Search functionality (title, description)
- Category filters (vehicles, real estate, machinery)
- Source filters
- Calendar view of auction dates
- Price comparison indicators

---

## [0.1.0] - 2026-02-20

### Added
- GMT-3 timezone display
- Manual update button
- Scrollable listing sections
- Simplified live auction feed

### Changed
- Vercel deployment configuration

---

## [0.0.0] - 2026-02-20

### Added
- Initial project structure
- Base scraper class with async HTTP client
- AuctionListing data model
- Scrapers for 7 sources:
  - CSJN (Corte Suprema)
  - SCBA (Buenos Aires Province)
  - Adrian Mercado
  - Banco Ciudad
  - Global Remates
  - BidBit
- JSON storage system
- Static site generator
- Basic HTML dashboard with Tailwind CSS

---

## Version History Summary

| Version | Date | Highlights |
|---------|------|------------|
| **1.6.1** | 2026-02-21 | **SEO audit, agent discovery, marketing content, profit strategies** |
| **1.6.0** | 2026-02-21 | USDC API for agents, IVA/fees on prices, API docs on homepage |
| **1.5.1** | 2026-02-21 | Adrián Mercado lot extraction (171 lots), domain live at subasto.com.ar |
| **1.5.0** | 2026-02-21 | SEO/social meta tags, currency selector in header, mobile optimization, calendar shows closing dates |
| 1.4.1 | 2026-02-21 | Category detection fixes, market price accuracy, Agusti logo filtering |
| **1.4.0** | 2026-02-21 | **Rebrand to Subasto, lot-level architecture, 873 listings, AI analysis pipeline** |
| 1.3.0 | 2026-02-21 | Curated premium opportunities via AI agent research |
| 1.2.0 | 2026-02-21 | Real market prices from Autocosmos/ZonaProp, no fake estimates |
| 1.1.0 | 2026-02-21 | UnicornStudio animated background, smooth scroll, SCBA 100% dates |
| 1.0.0 | 2026-02-21 | Stable release, date extraction, 227 listings |
| 0.12.0 | 2026-02-21 | Fix Global Remates titles |
| 0.11.0 | 2026-02-21 | Video background |
| 0.10.0 | 2026-02-21 | Interactive calendar |
| 0.9.0 | 2026-02-21 | Quality ranking |
| 0.8.0 | 2026-02-21 | Corporate branding |
| 0.7.0 | 2026-02-21 | Documentation |
| 0.6.0 | 2026-02-21 | Fix scrapers (270 listings) |
| 0.5.0 | 2026-02-20 | Analytics |
| 0.4.0 | 2026-02-20 | GitHub Actions |
| 0.3.0 | 2026-02-20 | Cost breakdown |
| 0.2.0 | 2026-02-20 | Search & filters |
| 0.1.0 | 2026-02-20 | Vercel deploy |
| 0.0.0 | 2026-02-20 | Initial commit |
