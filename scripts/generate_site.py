#!/usr/bin/env python3
"""Generate static site from scraped data."""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def generate_site():
    """Generate the static site from JSON data."""
    site_dir = Path("site")
    api_dir = site_dir / "api"

    # Load opportunities
    opportunities = []
    opp_file = api_dir / "opportunities.json"
    if opp_file.exists():
        with open(opp_file) as f:
            data = json.load(f)
            opportunities = data.get("opportunities", [])

    # Load listings for stats
    listings_file = api_dir / "listings.json"
    listings_data = {}
    if listings_file.exists():
        with open(listings_file) as f:
            listings_data = json.load(f)

    # Calculate stats
    total_listings = listings_data.get("total_count", 0)
    flagged = [o for o in opportunities if o.get("is_flagged")]
    flagged_count = len(flagged)
    sources = list(listings_data.get("by_source", {}).keys())
    sources_count = len(sources)

    avg_discount = 0
    if flagged:
        avg_discount = sum(o["discount_percentage"] for o in flagged) / len(flagged)

    # Sort opportunities by discount
    opportunities.sort(key=lambda x: x.get("discount_percentage", 0), reverse=True)

    # Generate stats JSON for frontend
    stats = {
        "total_listings": total_listings,
        "flagged_count": flagged_count,
        "sources_count": sources_count,
        "avg_discount": round(avg_discount, 1),
        "sources": sources,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }

    stats_path = api_dir / "stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print(f"Generated API files:")
    print(f"  {stats_path}")
    print(f"  Total listings: {total_listings}")
    print(f"  Flagged opportunities: {flagged_count}")
    print(f"  Sources: {sources_count}")

    # Check if index.html already exists with modern design
    index_path = site_dir / "index.html"
    if index_path.exists():
        content = index_path.read_text(encoding="utf-8")
        # If it has the modern design markers, don't overwrite
        if "tailwindcss" in content and "gsap" in content.lower():
            print(f"  Keeping existing modern design at {index_path}")
            return

    # Only generate basic template if no modern design exists
    print(f"  Note: No modern template found, keeping existing index.html")


if __name__ == "__main__":
    generate_site()
