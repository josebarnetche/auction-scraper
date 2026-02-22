#!/usr/bin/env python3
"""Generate historical price tracking API files.

This script generates:
- /api/v1/trends.json - Market trends dashboard
- /api/v1/history.json - API index and summary
- Individual item history files (on-demand)

Run this after archive_daily.py to update the API.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.price_history import PriceHistoryAnalyzer


def generate_history_api():
    """Generate all history API files."""
    print(f"Generating history API at {datetime.now(timezone.utc).isoformat()}")

    analyzer = PriceHistoryAnalyzer()
    api_dir = Path("site/api/v1")
    api_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate market trends dashboard
    print("Generating market trends...")
    try:
        dashboard = analyzer.get_market_trends_dashboard(days=30)
        dashboard["generated_at"] = datetime.now(timezone.utc).isoformat()

        trends_path = api_dir / "trends.json"
        with open(trends_path, "w", encoding="utf-8") as f:
            json.dump(dashboard, f, ensure_ascii=False, indent=2)
        print(f"  Created: {trends_path}")
    except Exception as e:
        print(f"  Error generating trends: {e}")
        dashboard = None

    # 2. Generate extended trends (90 days)
    print("Generating extended trends (90 days)...")
    try:
        dashboard_90 = analyzer.get_market_trends_dashboard(days=90)
        dashboard_90["generated_at"] = datetime.now(timezone.utc).isoformat()

        trends_90_path = api_dir / "trends-90d.json"
        with open(trends_90_path, "w", encoding="utf-8") as f:
            json.dump(dashboard_90, f, ensure_ascii=False, indent=2)
        print(f"  Created: {trends_90_path}")
    except Exception as e:
        print(f"  Error generating 90-day trends: {e}")

    # 3. Load archive stats
    history_dir = Path("data/history")
    archive_stats = {}
    stats_path = history_dir / "archive_stats.json"
    if stats_path.exists():
        try:
            with open(stats_path, encoding="utf-8") as f:
                archive_stats = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    # 4. Load recent price changes for API
    print("Loading recent price changes...")
    price_changes = analyzer.load_price_changes()
    recent_changes = price_changes[:50] if price_changes else []

    # 5. Load recent ended auctions
    print("Loading ended auctions...")
    final_prices = analyzer.load_final_prices()
    recent_ended = final_prices[:50] if final_prices else []

    # 6. Generate history index
    history_index = {
        "info": {
            "description": "Historical price tracking API for Subasto",
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "endpoints": {
            "trends_30d": "/api/v1/trends.json",
            "trends_90d": "/api/v1/trends-90d.json",
            "price_changes": "/api/v1/price-changes.json",
            "ended_auctions": "/api/v1/ended-auctions.json",
        },
        "stats": archive_stats.get("summary", {}),
        "data_available": bool(archive_stats),
        "date_range": archive_stats.get("date_range", {}),
    }

    history_path = api_dir / "history.json"
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history_index, f, ensure_ascii=False, indent=2)
    print(f"  Created: {history_path}")

    # 7. Generate price changes endpoint
    changes_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_count": len(price_changes),
        "recent_changes": recent_changes,
        "summary": {
            "drops": len([c for c in recent_changes if c.get("change_percent", 0) < 0]),
            "increases": len([c for c in recent_changes if c.get("change_percent", 0) > 0]),
        }
    }

    changes_path = api_dir / "price-changes.json"
    with open(changes_path, "w", encoding="utf-8") as f:
        json.dump(changes_data, f, ensure_ascii=False, indent=2)
    print(f"  Created: {changes_path}")

    # 8. Generate ended auctions endpoint
    ended_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_count": len(final_prices),
        "recent_ended": recent_ended,
    }

    ended_path = api_dir / "ended-auctions.json"
    with open(ended_path, "w", encoding="utf-8") as f:
        json.dump(ended_data, f, ensure_ascii=False, indent=2)
    print(f"  Created: {ended_path}")

    print("\nHistory API generation complete!")

    # Print summary
    if dashboard:
        print("\n=== Market Trends Summary ===")
        discounts = dashboard.get("discount_by_category", {})
        for cat, data in discounts.items():
            print(f"  {cat}: {data.get('avg_discount', 0)}% avg discount")

        best_days = dashboard.get("best_deal_days", {})
        if best_days.get("best_day"):
            print(f"\n  Best day for deals: {best_days['best_day']} ({best_days.get('best_avg_discount', 0)}% avg)")


def lookup_item_history(listing_id: str) -> dict | None:
    """Lookup price history for a specific listing ID.

    This function can be called by the API to serve individual item histories.
    """
    analyzer = PriceHistoryAnalyzer()
    history = analyzer.get_item_history(listing_id)

    if not history:
        return None

    # Add price change alert if applicable
    alert = analyzer.get_price_change_alert(listing_id)

    return {
        "listing_id": listing_id,
        "first_seen": history.get("first_seen"),
        "last_seen": history.get("last_seen"),
        "price_history": history.get("prices", []),
        "extra": history.get("extra", {}),
        "price_alert": alert,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate history API files")
    parser.add_argument("--item", help="Lookup history for specific listing ID")

    args = parser.parse_args()

    if args.item:
        history = lookup_item_history(args.item)
        if history:
            print(json.dumps(history, indent=2, ensure_ascii=False))
        else:
            print(f"No history found for: {args.item}")
    else:
        generate_history_api()
