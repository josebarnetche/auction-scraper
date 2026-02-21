#!/usr/bin/env python3
"""Update premium opportunities with real data from scraped listings."""

import json
from pathlib import Path
from datetime import datetime, timezone


def load_all_scraped():
    """Load all scraped listings into a single list."""
    raw_dir = Path("data/raw")
    all_listings = []

    for json_file in raw_dir.glob("*.json"):
        try:
            with open(json_file, encoding="utf-8") as f:
                listings = json.load(f)
                if isinstance(listings, list):
                    for l in listings:
                        l["_source_file"] = json_file.stem
                    all_listings.extend(listings)
        except Exception as e:
            print(f"Warning: Could not load {json_file}: {e}")

    return all_listings


def find_match(scraped, keywords, require_images=True, source_filter=None):
    """Find a scraped listing matching any of the keywords."""
    for listing in scraped:
        # Filter by source if specified
        if source_filter and listing.get("_source_file") != source_filter:
            continue

        title = listing.get("title", "").lower()
        desc = listing.get("description", "").lower()
        url = listing.get("source_url", "").lower()

        for kw in keywords:
            if kw in title or kw in desc or kw in url:
                if require_images:
                    images = listing.get("images", [])
                    # Filter out logo/placeholder images
                    real_images = [img for img in images if not any(x in img.lower() for x in ['logo', 'home_', 'placeholder', 'icon'])]
                    if real_images and len(real_images) > 0:
                        listing["images"] = real_images  # Replace with filtered
                        return listing
                else:
                    return listing
    return None


def main():
    print("Loading scraped data...")
    scraped = load_all_scraped()
    print(f"Loaded {len(scraped)} scraped listings")

    # Load premium opportunities
    curated_path = Path("data/curated/premium_opportunities.json")
    with open(curated_path, encoding="utf-8") as f:
        premium = json.load(f)

    print(f"\nUpdating {len(premium)} premium opportunities...\n")

    # Define matching rules for each premium listing
    matching_rules = {
        "curated:mecalux_robot_warehouse": {
            "keywords": ["mecalux", "almacenamiento logistico", "robot"],
            "update_url": True,
        },
        "curated:sacde_fleet_crane": {
            "keywords": ["sacde", "terex rt555"],
            "update_url": True,
        },
        "curated:techint_cat_d8t": {
            "keywords": ["tecsesi", "techint"],
            "update_url": True,
        },
        "curated:xcmg_70t_crane": {
            "keywords": ["xcmg", "70 ton", "grua 70", "constructora y vial"],
            "update_url": True,
        },
        "curated:scania_20ton_press": {
            "keywords": ["scania argentina", "prensa de 20 toneladas"],
            "update_url": True,
            "source_filter": "global_remates",  # Only match from Global Remates
        },
        "curated:cordoba_road_fleet": {
            "keywords": ["empresa vial", "vial cordoba", "constructora y vial", "camiones con batea"],
            "update_url": True,
        },
        "curated:telecom_70_vehicles": {
            "keywords": ["flota de vehiculos", "importante flota", "hyundai"],
            "update_url": True,
        },
    }

    updated_count = 0

    for listing in premium:
        listing_id = listing["id"]
        print(f"Processing: {listing_id}")

        # Check if we have matching rules
        if listing_id in matching_rules:
            rules = matching_rules[listing_id]
            source_filter = rules.get("source_filter")
            match = find_match(scraped, rules["keywords"], source_filter=source_filter)

            if match:
                # Update with real data
                images = match.get("images", [])
                if images:
                    listing["images"] = images[:5]  # Max 5 images
                    print(f"  + Found {len(images)} images")

                price = match.get("base_price", 0)
                if price > 0:
                    listing["base_price"] = price
                    listing["currency"] = match.get("currency", "ARS")
                    print(f"  + Found price: {price}")

                if rules.get("update_url") and match.get("source_url"):
                    listing["source_url"] = match["source_url"]
                    print(f"  + Updated URL")

                # Update scraped_at
                listing["scraped_at"] = datetime.now(timezone.utc).isoformat()
                updated_count += 1
            else:
                print(f"  - No match found")
        else:
            # Check if listing already has images from a previous run
            if listing.get("images"):
                print(f"  - Already has {len(listing['images'])} images")
            else:
                print(f"  - No matching rules defined")

    # For listings with images but no price, use estimated value from extra
    # This allows them to appear in the opportunities grid
    print("\nAdding estimated prices for listings with images...")
    for listing in premium:
        if listing.get("images") and listing.get("base_price", 0) == 0:
            extra = listing.get("extra", {})
            estimated_usd = extra.get("estimated_value_usd", 0)
            if estimated_usd > 0:
                # Use a conservative auction base price (30-50% of estimated value)
                # This represents a typical auction starting price
                base_price_usd = int(estimated_usd * 0.35)
                listing["base_price"] = base_price_usd
                listing["currency"] = "USD"
                print(f"  + {listing['id']}: set price to ${base_price_usd:,} USD")
                updated_count += 1

    # Save updated premium file
    with open(curated_path, "w", encoding="utf-8") as f:
        json.dump(premium, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"Updated {updated_count} premium listings with real data")

    # Summary
    with_images = sum(1 for l in premium if l.get("images"))
    with_price = sum(1 for l in premium if l.get("base_price", 0) > 0)
    print(f"Total with images: {with_images}/16")
    print(f"Total with price: {with_price}/16")


if __name__ == "__main__":
    main()
