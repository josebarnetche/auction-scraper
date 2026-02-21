#!/usr/bin/env python3
"""Generate static site data from scraped auctions."""

import json
import re
from pathlib import Path
from datetime import datetime, timezone


def generate_site():
    """Generate the site API files from raw scraped data."""
    data_dir = Path("data/raw")
    site_dir = Path("site")
    api_dir = site_dir / "api"
    api_dir.mkdir(parents=True, exist_ok=True)

    all_listings = []
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

    # Write listings.json
    listings_data = {
        "total_count": len(all_listings),
        "by_source": by_source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "listings": all_listings,
    }

    listings_path = api_dir / "listings.json"
    with open(listings_path, "w", encoding="utf-8") as f:
        json.dump(listings_data, f, indent=2, ensure_ascii=False)

    print(f"Generated {listings_path}")
    print(f"  Total listings: {len(all_listings)}")
    print(f"  Sources: {list(by_source.keys())}")

    # Print quality breakdown
    with_images = sum(1 for l in all_listings if l.get("images"))
    with_price = sum(1 for l in all_listings if l.get("base_price", 0) > 0)
    print(f"  With images: {with_images}")
    print(f"  With price: {with_price}")


if __name__ == "__main__":
    generate_site()
