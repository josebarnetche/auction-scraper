# Changelog

All notable changes to Argentina Auction Radar are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- COMPR.AR scraper: SSL context bypass for government site

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
  - COMPR.AR (Government)
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
| **1.2.0** | 2026-02-21 | **Real market prices from Autocosmos/ZonaProp, no fake estimates** |
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
