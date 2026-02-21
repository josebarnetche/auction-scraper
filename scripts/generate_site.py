#!/usr/bin/env python3
"""Generate static site data from scraped auctions.

Generates both auction-level and lot-level views for the site API.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.market.price_reference import get_market_price, calculate_discount, is_opportunity
from src.utils.currency import get_blue_dollar_rate, convert_to_usd
from src.models.listing import detect_category


def fetch_blue_dollar_rate() -> float:
    """Fetch current blue dollar rate from dolarapi.com"""
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
            rate = data.get("venta", 1415)
            print(f"Blue dollar rate from API: ${rate}")
            return float(rate)
    except Exception as e:
        print(f"Warning: Could not fetch blue dollar rate: {e}")
        return 1415.0  # Fallback to current rate


# Blue dollar rate - fetched from dolarapi.com
BLUE_DOLLAR_RATE = fetch_blue_dollar_rate()

# Source ranking: judicial sources first, then quality private sources
JUDICIAL_SOURCES = ["csjn", "scba", "cordoba", "entrerios", "comprar"]
PRIORITY_PRIVATE_SOURCES = ["banco_ciudad", "global_remates", "adrian_mercado"]


def generate_site():
    """Generate the site API files from raw scraped data."""
    data_dir = Path("data/raw")
    curated_dir = Path("data/curated")
    site_dir = Path("site")
    api_dir = site_dir / "api"
    api_dir.mkdir(parents=True, exist_ok=True)

    all_listings = []
    premium_listings = []
    by_source = {}

    # Non-auction titles/patterns to filter out
    skip_patterns = [
        "asegurá tu participación",
        "bienvenido al portal",
        "como participar",
        "cómo participar",
        "tel:+",
        "ramos de pujas",
        "ramer nro",
        "su oferta",
        "ofertar",
        "ver detalles",
        "ver más",
        "ver lotes",
    ]

    # Generic title patterns (low quality listings)
    generic_title_patterns = [
        r'^remate\s*#?\d+$',
        r'^subasta\s*#?\d+$',
        r'^auction\s*#?\d+$',
        r'^lote\s*#?\d+$',
    ]

    # Load all raw JSON files
    for json_file in data_dir.glob("*.json"):
        if json_file.name == ".gitkeep":
            continue
        try:
            with open(json_file, encoding="utf-8") as f:
                listings = json.load(f)
                if isinstance(listings, list):
                    for listing in listings:
                        # Only include listings with valid data
                        if not listing.get("title") or not listing.get("source_url"):
                            continue

                        title = listing.get("title", "")
                        title_lower = title.lower().strip()
                        url_lower = listing.get("source_url", "").lower()

                        # Filter out non-auction entries
                        if any(p in title_lower or p in url_lower for p in skip_patterns):
                            continue

                        # Must have actual auction URL (not tel: or generic pages)
                        source_url = listing.get("source_url", "")
                        if not source_url.startswith("http"):
                            continue

                        # Skip listings pointing to wrong domains
                        if "rural.com.uy" in source_url:
                            continue

                        # Skip very generic titles with no real content
                        is_generic = any(re.match(p, title_lower) for p in generic_title_patterns)
                        if is_generic:
                            continue

                        all_listings.append(listing)
                        source = listing.get("source", "unknown")
                        by_source[source] = by_source.get(source, 0) + 1
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read {json_file}: {e}")

    # Load curated premium opportunities
    curated_file = curated_dir / "premium_opportunities.json"
    coming_soon_count = 0
    if curated_file.exists():
        try:
            with open(curated_file, encoding="utf-8") as f:
                curated = json.load(f)
                for listing in curated:
                    if listing.get("extra", {}).get("is_premium"):
                        has_price = listing.get("base_price", 0) > 0
                        has_images = len(listing.get("images", [])) > 0

                        if has_price and has_images:
                            # Complete premium listing - highlight it
                            listing["is_premium"] = True
                            premium_listings.append(listing)
                        else:
                            # Incomplete premium - mark as coming_soon, hide from main
                            listing["is_premium"] = False
                            listing["coming_soon"] = True
                            listing["visibility"] = "search_only"
                            coming_soon_count += 1

                        all_listings.append(listing)
                        source = listing.get("source", "curated")
                        by_source[source] = by_source.get(source, 0) + 1
            print(f"Loaded {len(premium_listings)} complete premium opportunities")
            if coming_soon_count > 0:
                print(f"  ({coming_soon_count} premium listings marked as coming_soon - missing price/images)")
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read curated file: {e}")

    # Calculate quality score for ranking
    def quality_score(listing):
        score = 0

        # Source ranking: judicial first, then priority private
        source = listing.get("source", "")
        if source in JUDICIAL_SOURCES:
            score += 500  # Judicial sources get major boost
        elif source in PRIORITY_PRIVATE_SOURCES:
            score += 300  # Priority private sources

        # Has images (most important)
        images = listing.get("images", [])
        if images and len(images) > 0:
            score += 100
            # More images = better
            score += min(len(images) * 10, 50)

        # Has price
        if listing.get("base_price", 0) > 0:
            score += 50

        # Has description
        desc = listing.get("description", "")
        if desc and len(desc) > 20:
            score += 20

        # Has end date (time-sensitive = more relevant)
        if listing.get("ends_at"):
            score += 30

        # Has location
        location = listing.get("location", {})
        if location.get("province") or location.get("city"):
            score += 10

        # Title quality (longer, more descriptive = better)
        title = listing.get("title", "")
        if len(title) > 30:
            score += 20
        elif len(title) > 15:
            score += 10

        # Scraped recently
        scraped_at = listing.get("scraped_at", "")
        if scraped_at:
            score += 5

        return score

    # Sort by quality score (highest first), then by scraped_at
    all_listings.sort(key=lambda x: (quality_score(x), x.get("scraped_at", "")), reverse=True)

    # Add visibility field: "main" = shown on homepage, "search_only" = only via search
    # Listings need BOTH price AND image to show on main page
    for listing in all_listings:
        has_price = listing.get("base_price", 0) > 0
        has_images = len(listing.get("images", [])) > 0

        if has_price and has_images:
            listing["visibility"] = "main"
        else:
            listing["visibility"] = "search_only"

        # Quality score for frontend (0-100 scale)
        score = quality_score(listing)
        listing["quality_score"] = min(100, score)  # Cap at 100

        # Source type for filtering (judicial vs private)
        source = listing.get("source", "")
        listing["source_type"] = "judicial" if source in JUDICIAL_SOURCES else "private"

        # Recalculate category using updated detect_category (fixes machinery vs vehicle)
        title = listing.get("title", "")
        description = listing.get("description", "")
        listing["category"] = detect_category(title, description)

        # Filter out logo/junk images (especially from Agusti)
        logo_patterns = ['home_agusti', 'agusti_subastas', 'empresas/', 'logo', 'icon',
                         'avatar', 'social', 'facebook', 'twitter', 'banner']
        images = listing.get("images", [])
        clean_images = [img for img in images
                        if not any(p in img.lower() for p in logo_patterns)]
        listing["images"] = clean_images if clean_images else images[:1]  # Keep first if all filtered

        # Ensure currency is set and add USD equivalent for filtering
        currency = listing.get("currency", "ARS")
        base_price = listing.get("base_price", 0)
        source = listing.get("source", "")

        # Currency correction for Banco Ciudad: they typically price in USD
        # Detect USD prices incorrectly stored as ARS
        # Heuristic: BC real estate > 50,000 is likely USD, not ARS
        if source == "banco_ciudad" and currency == "ARS" and base_price > 50000:
            category = listing.get("category", "")
            # Real estate priced > 50k and machinery > 10k are likely USD
            if category == "real_estate" or (category == "machinery" and base_price > 10000):
                currency = "USD"
                listing["currency"] = "USD"

        if currency == "ARS" and base_price > 0:
            listing["base_price_usd"] = round(base_price / BLUE_DOLLAR_RATE, 2)
        elif currency == "USD":
            listing["base_price_usd"] = base_price
            listing["base_price_ars"] = round(base_price * BLUE_DOLLAR_RATE, 2)
        else:
            listing["base_price_usd"] = 0

    # Calculate market prices and opportunities using keyword matching
    opportunities = []
    march_deadline = datetime(2026, 3, 1, tzinfo=timezone.utc)

    for listing in all_listings:
        title = listing.get("title", "")
        description = listing.get("description", "")
        category = listing.get("category", "")

        # Get market price estimate
        market_data = get_market_price(title, description, category)

        if market_data:
            # Convert listing price to USD
            base_price = listing.get("base_price", 0)
            currency = listing.get("currency", "ARS")

            if base_price > 0:
                if currency == "ARS":
                    price_usd = base_price / BLUE_DOLLAR_RATE
                else:
                    price_usd = base_price

                # Calculate discount
                discount = calculate_discount(price_usd, market_data)

                if discount > 0:
                    market_data["auction_price_usd"] = round(price_usd, 2)
                    market_data["discount_percent"] = discount
                    market_data["is_opportunity"] = discount >= 30

                    listing["market_data"] = market_data

                    # Track opportunities for top selection
                    if discount >= 20:  # Include 20%+ for ranking
                        # Check if before March - use any available date
                        date_str = listing.get("ends_at") or listing.get("starts_at")
                        before_march = False
                        if date_str:
                            try:
                                if isinstance(date_str, str):
                                    # Parse ISO date - handle various formats
                                    date_str_clean = date_str.replace("Z", "+00:00")
                                    if "+" not in date_str_clean and len(date_str_clean) == 19:
                                        date_str_clean += "+00:00"
                                    end_date = datetime.fromisoformat(date_str_clean)
                                else:
                                    end_date = date_str
                                before_march = end_date < march_deadline
                            except Exception as e:
                                # Try simpler parsing
                                try:
                                    if "2026-02" in str(date_str):
                                        before_march = True
                                except:
                                    pass

                        opportunities.append({
                            "listing": listing,
                            "discount": discount,
                            "before_march": before_march,
                            "category": market_data.get("category", "other"),
                            "is_premium": listing.get("is_premium", False),
                        })

    # Add premium curated opportunities (they may not have automatic market data)
    for listing in premium_listings:
        extra = listing.get("extra", {})
        discount_str = extra.get("discount_estimate", "0%")
        # Parse discount estimate (e.g., "45-55%" -> 50)
        try:
            if "-" in discount_str:
                parts = discount_str.replace("%", "").split("-")
                discount = (float(parts[0]) + float(parts[1])) / 2
            else:
                discount = float(discount_str.replace("%", ""))
        except:
            discount = 40  # Default for premium items

        # Check if before March
        date_str = listing.get("ends_at")
        before_march = False
        if date_str:
            try:
                if "2026-02" in str(date_str) or "2026-03-0" in str(date_str):
                    before_march = True
            except:
                pass

        # Only add if not already in opportunities
        listing_id = listing.get("id")
        if not any(o["listing"].get("id") == listing_id for o in opportunities):
            opportunities.append({
                "listing": listing,
                "discount": discount,
                "before_march": before_march,
                "category": listing.get("category", "other"),
                "is_premium": True,
            })

    # Sort opportunities: judicial first, then by discount (highest first)
    # Prioritize judicial sources, machinery and premium
    def opportunity_score(opp):
        score = opp["discount"]
        # Source type: judicial sources get priority
        source = opp["listing"].get("source", "")
        if source in JUDICIAL_SOURCES:
            score += 100  # Judicial sources ranked higher
        elif source in PRIORITY_PRIVATE_SOURCES:
            score += 40  # Priority private sources
        if opp.get("is_premium"):
            score += 50  # Premium is a bonus
        if opp["before_march"]:
            score += 30  # Time urgency bonus
        if opp["category"] == "machinery":
            score += 20  # Category bonus
        return score

    opportunities.sort(key=opportunity_score, reverse=True)

    # Mark top 3 opportunities
    top_opportunity_ids = set()
    for i, opp in enumerate(opportunities[:3]):
        opp["listing"]["is_top_opportunity"] = True
        opp["listing"]["opportunity_rank"] = i + 1
        top_opportunity_ids.add(opp["listing"]["id"])

    # Re-sort all listings: top opportunities first, then by quality
    def final_sort_key(listing):
        if listing.get("is_top_opportunity"):
            # Top opportunities at the very top, ordered by rank
            return (0, listing.get("opportunity_rank", 99), 0)
        else:
            # Then by quality score
            return (1, 0, -quality_score(listing))

    all_listings.sort(key=final_sort_key)

    # Build top opportunities summary (top 5 for premium content)
    top_opportunities = []
    for opp in opportunities[:5]:
        listing = opp["listing"]
        extra = listing.get("extra", {})
        top_opportunities.append({
            "id": listing["id"],
            "title": listing["title"][:100],
            "discount_percent": opp["discount"],
            "before_march": opp["before_march"],
            "category": opp["category"],
            "source": listing["source"],
            "source_url": listing["source_url"],
            "base_price": listing.get("base_price", 0),
            "currency": listing.get("currency", "ARS"),
            "market_typical_usd": listing.get("market_data", {}).get("typical_usd", 0) or extra.get("estimated_value_usd", 0),
            "is_premium": opp.get("is_premium", False),
            "premium_type": extra.get("premium_type", ""),
            "why_premium": extra.get("why_premium", ""),
        })

    # Generate lot-level flat view for browsing
    all_lots = []
    auctions_with_lots = 0

    for listing in all_listings:
        lots_data = listing.get("lots", [])
        if not lots_data:
            continue

        auctions_with_lots += 1
        auction_id = listing.get("id", "")
        auction_title = listing.get("title", "")
        auction_source = listing.get("source", "")
        auction_url = listing.get("source_url", "")

        for lot in lots_data:
            # Calculate discount if we have AI analysis
            discount_percent = None
            if lot.get("ai_market_value_usd") and lot.get("base_price_usd"):
                market_val = lot["ai_market_value_usd"]
                auction_price = lot["base_price_usd"]
                if market_val > 0:
                    discount_percent = round((1 - auction_price / market_val) * 100, 1)

            flat_lot = {
                "lot_id": lot.get("lot_id", ""),
                "lot_number": lot.get("lot_number", 1),
                "auction_id": auction_id,
                "auction_title": auction_title,
                "auction_source": auction_source,
                "auction_url": auction_url,
                "title": lot.get("title", ""),
                "description": lot.get("description", ""),
                "base_price": lot.get("base_price", 0),
                "currency": lot.get("currency", "ARS"),
                "base_price_usd": lot.get("base_price_usd", 0),
                "images": lot.get("images", []),
                # AI analysis fields
                "ai_specs": lot.get("ai_specs"),
                "ai_market_value_usd": lot.get("ai_market_value_usd"),
                "opportunity_score": lot.get("ai_opportunity_score"),
                "discount_percent": discount_percent,
                "ai_analyzed": lot.get("ai_analyzed_at") is not None,
            }
            all_lots.append(flat_lot)

    # Sort lots by opportunity score (highest first), then by discount
    def lot_sort_key(lot):
        score = lot.get("opportunity_score") or 0
        discount = lot.get("discount_percent") or 0
        return (score, discount)

    all_lots.sort(key=lot_sort_key, reverse=True)

    # Top lots (best opportunities)
    top_lots = [
        lot for lot in all_lots
        if (lot.get("opportunity_score") or 0) >= 7
    ][:20]

    # Write listings.json
    with_market_data = sum(1 for l in all_listings if l.get('market_data'))
    opportunity_count = sum(1 for l in all_listings if l.get('market_data', {}).get('is_opportunity'))
    premium_count = sum(1 for l in all_listings if l.get('is_premium'))
    analyzed_lots_count = sum(1 for lot in all_lots if lot.get("ai_analyzed"))

    listings_data = {
        "total_count": len(all_listings),
        "by_source": by_source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "blue_dollar_rate": BLUE_DOLLAR_RATE,
        "with_market_data": with_market_data,
        "opportunity_count": opportunity_count,
        "premium_count": premium_count,
        "top_opportunities": top_opportunities,
        # Lot-level data (new architecture)
        "lot_stats": {
            "total_lots": len(all_lots),
            "auctions_with_lots": auctions_with_lots,
            "analyzed_lots": analyzed_lots_count,
            "top_opportunity_lots": len(top_lots),
        },
        "lots": all_lots,
        "top_lots": top_lots,
        # Hierarchical auction data
        "listings": all_listings,
    }

    listings_path = api_dir / "listings.json"
    with open(listings_path, "w", encoding="utf-8") as f:
        json.dump(listings_data, f, indent=2, ensure_ascii=False)

    print(f"Generated {listings_path}")
    print(f"  Total listings: {len(all_listings)}")
    print(f"  Sources: {list(by_source.keys())}")
    print(f"  With market data: {with_market_data}")
    print(f"  Opportunities (30%+ discount): {opportunity_count}")

    # Print quality breakdown
    with_images = sum(1 for l in all_listings if l.get("images"))
    with_price = sum(1 for l in all_listings if l.get("base_price", 0) > 0)
    main_page = sum(1 for l in all_listings if l.get("visibility") == "main")
    search_only = sum(1 for l in all_listings if l.get("visibility") == "search_only")
    print(f"  With images: {with_images}")
    print(f"  With price: {with_price}")
    print(f"  Main page visibility: {main_page}")
    print(f"  Search only: {search_only}")

    # Print premium stats
    print(f"  Premium curated: {premium_count}")

    # Print lot-level stats
    print(f"\n  LOT-LEVEL DATA:")
    print(f"    Total lots: {len(all_lots)}")
    print(f"    Auctions with lots: {auctions_with_lots}")
    print(f"    AI-analyzed lots: {analyzed_lots_count}")
    print(f"    Top opportunity lots (7+): {len(top_lots)}")

    # Print top lot opportunities
    if top_lots:
        print(f"\n  TOP LOT OPPORTUNITIES:")
        for i, lot in enumerate(top_lots[:5]):
            score = lot.get("opportunity_score", 0)
            discount = lot.get("discount_percent")
            discount_str = f"{discount:.0f}% off" if discount else "N/A"
            print(f"    {i+1}. [{score}/10] {lot['title'][:50]}... ({discount_str})")

    # Print top opportunities
    if top_opportunities:
        print(f"\n  TOP OPPORTUNITIES:")
        for i, opp in enumerate(top_opportunities):
            march_tag = " [BEFORE MARCH]" if opp["before_march"] else ""
            premium_tag = " [PREMIUM]" if opp.get("is_premium") else ""
            print(f"    {i+1}. {opp['discount_percent']:.0f}% off - {opp['title'][:50]}...{march_tag}{premium_tag}")


if __name__ == "__main__":
    generate_site()
