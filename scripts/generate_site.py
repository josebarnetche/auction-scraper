#!/usr/bin/env python3
"""Generate static site data from scraped auctions."""

import json
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
        "subasta judicial #",
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

                        # Filter out non-auction entries
                        title_lower = listing.get("title", "").lower()
                        url_lower = listing.get("source_url", "").lower()
                        if any(p in title_lower or p in url_lower for p in skip_patterns):
                            continue

                        # Must have actual auction URL (not tel: or generic pages)
                        source_url = listing.get("source_url", "")
                        if not source_url.startswith("http"):
                            continue

                        all_listings.append(listing)
                        source = listing.get("source", "unknown")
                        by_source[source] = by_source.get(source, 0) + 1
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read {json_file}: {e}")

    # Sort by scraped_at (most recent first)
    all_listings.sort(key=lambda x: x.get("scraped_at", ""), reverse=True)

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


if __name__ == "__main__":
    generate_site()
