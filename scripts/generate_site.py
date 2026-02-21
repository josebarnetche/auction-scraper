#!/usr/bin/env python3
"""Generate static site data from scraped auctions."""

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.market.price_reference import get_market_price, calculate_discount, is_opportunity

# Blue dollar rate (approximate - should be fetched dynamically)
BLUE_DOLLAR_RATE = 1250  # ARS per USD


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
    if curated_file.exists():
        try:
            with open(curated_file, encoding="utf-8") as f:
                curated = json.load(f)
                for listing in curated:
                    if listing.get("extra", {}).get("is_premium"):
                        listing["is_premium"] = True
                        premium_listings.append(listing)
                        all_listings.append(listing)
                        source = listing.get("source", "curated")
                        by_source[source] = by_source.get(source, 0) + 1
            print(f"Loaded {len(premium_listings)} curated premium opportunities")
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read curated file: {e}")

    # Calculate quality score for ranking
    def quality_score(listing):
        score = 0

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

    # Sort opportunities: before_march first, then by discount (highest first)
    # Prioritize machinery and premium
    def opportunity_score(opp):
        score = opp["discount"]
        if opp.get("is_premium"):
            score += 200  # Premium opportunities always on top
        if opp["before_march"]:
            score += 100  # Big boost for before March
        if opp["category"] == "machinery":
            score += 50  # Boost machinery
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

    # Write listings.json
    with_market_data = sum(1 for l in all_listings if l.get('market_data'))
    opportunity_count = sum(1 for l in all_listings if l.get('market_data', {}).get('is_opportunity'))
    premium_count = sum(1 for l in all_listings if l.get('is_premium'))

    listings_data = {
        "total_count": len(all_listings),
        "by_source": by_source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "blue_dollar_rate": BLUE_DOLLAR_RATE,
        "with_market_data": with_market_data,
        "opportunity_count": opportunity_count,
        "premium_count": premium_count,
        "top_opportunities": top_opportunities,
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
    print(f"  With images: {with_images}")
    print(f"  With price: {with_price}")

    # Print premium stats
    print(f"  Premium curated: {premium_count}")

    # Print top opportunities
    if top_opportunities:
        print(f"\n  TOP OPPORTUNITIES:")
        for i, opp in enumerate(top_opportunities):
            march_tag = " [BEFORE MARCH]" if opp["before_march"] else ""
            premium_tag = " [PREMIUM]" if opp.get("is_premium") else ""
            print(f"    {i+1}. {opp['discount_percent']:.0f}% off - {opp['title'][:50]}...{march_tag}{premium_tag}")


if __name__ == "__main__":
    generate_site()
