#!/usr/bin/env python3
"""Archive daily snapshots of auction data for historical price tracking.

This script should run daily (after the scraper) to:
1. Save a daily snapshot of all current listings
2. Track price changes for ongoing auctions
3. Record final sale prices when auctions end
4. Maintain a price change log for individual items

Data is stored in data/history/:
- snapshots/YYYY-MM-DD.json - Full daily snapshots
- price_changes.json - Log of all price changes
- final_prices.json - Record of auction closing prices
- item_history/{listing_id}.json - Individual item price history
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import hashlib

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.currency import get_blue_dollar_rate


def get_today_date() -> str:
    """Get today's date in Argentina timezone (UTC-3)."""
    utc_now = datetime.now(timezone.utc)
    argentina_tz = timezone(timedelta(hours=-3))
    argentina_now = utc_now.astimezone(argentina_tz)
    return argentina_now.strftime("%Y-%m-%d")


def load_current_listings() -> list[dict]:
    """Load all current listings from data/raw/*.json."""
    data_dir = Path("data/raw")
    all_listings = []

    for json_file in data_dir.glob("*.json"):
        if json_file.name == ".gitkeep":
            continue
        try:
            with open(json_file, encoding="utf-8") as f:
                listings = json.load(f)
                if isinstance(listings, list):
                    all_listings.extend(listings)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read {json_file}: {e}")

    return all_listings


def load_previous_snapshot(days_back: int = 1) -> Optional[dict]:
    """Load a previous day's snapshot."""
    history_dir = Path("data/history/snapshots")

    utc_now = datetime.now(timezone.utc)
    argentina_tz = timezone(timedelta(hours=-3))

    for i in range(days_back, days_back + 7):  # Look back up to 7 days
        target_date = (utc_now.astimezone(argentina_tz) - timedelta(days=i)).strftime("%Y-%m-%d")
        snapshot_path = history_dir / f"{target_date}.json"
        if snapshot_path.exists():
            try:
                with open(snapshot_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                continue

    return None


def load_json_file(path: Path) -> dict | list:
    """Load a JSON file, returning empty dict/list if not exists."""
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_json_file(path: Path, data: dict | list):
    """Save data to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_price_usd(listing: dict, blue_rate: float) -> float:
    """Convert listing price to USD for comparison."""
    base_price = listing.get("base_price", 0)
    currency = listing.get("currency", "ARS")

    if currency == "USD":
        return float(base_price)
    elif currency == "ARS" and base_price > 0:
        return round(base_price / blue_rate, 2)
    return 0.0


def create_listing_summary(listing: dict, blue_rate: float) -> dict:
    """Create a compact summary of a listing for storage."""
    return {
        "id": listing.get("id"),
        "title": listing.get("title", "")[:100],
        "category": listing.get("category", "other"),
        "source": listing.get("source", "unknown"),
        "base_price": listing.get("base_price", 0),
        "currency": listing.get("currency", "ARS"),
        "price_usd": normalize_price_usd(listing, blue_rate),
        "ends_at": listing.get("ends_at"),
        "status": listing.get("status", "unknown"),
        "market_data": listing.get("market_data"),
    }


def detect_price_changes(current: list[dict], previous: dict, blue_rate: float) -> list[dict]:
    """Detect price changes between current and previous snapshot."""
    changes = []

    if not previous:
        return changes

    prev_listings = {l["id"]: l for l in previous.get("listings", [])}

    for listing in current:
        listing_id = listing.get("id")
        if not listing_id:
            continue

        prev = prev_listings.get(listing_id)
        if not prev:
            continue  # New listing, not a price change

        current_price_usd = normalize_price_usd(listing, blue_rate)
        prev_price_usd = prev.get("price_usd", 0)

        if current_price_usd > 0 and prev_price_usd > 0:
            change_pct = ((current_price_usd - prev_price_usd) / prev_price_usd) * 100

            # Only record significant changes (>= 1%)
            if abs(change_pct) >= 1:
                changes.append({
                    "listing_id": listing_id,
                    "title": listing.get("title", "")[:80],
                    "category": listing.get("category"),
                    "source": listing.get("source"),
                    "old_price_usd": prev_price_usd,
                    "new_price_usd": current_price_usd,
                    "change_percent": round(change_pct, 1),
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "date": get_today_date(),
                })

    return changes


def detect_ended_auctions(current: list[dict], previous: dict) -> list[dict]:
    """Detect auctions that ended (present yesterday, not today)."""
    ended = []

    if not previous:
        return ended

    current_ids = {l.get("id") for l in current if l.get("id")}

    for prev_listing in previous.get("listings", []):
        listing_id = prev_listing.get("id")
        if listing_id and listing_id not in current_ids:
            # Check if it had an end date that passed
            ends_at = prev_listing.get("ends_at")
            ended.append({
                "listing_id": listing_id,
                "title": prev_listing.get("title", "")[:80],
                "category": prev_listing.get("category"),
                "source": prev_listing.get("source"),
                "final_price_usd": prev_listing.get("price_usd", 0),
                "final_price": prev_listing.get("base_price", 0),
                "final_currency": prev_listing.get("currency", "ARS"),
                "ended_at": ends_at or get_today_date(),
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "market_data": prev_listing.get("market_data"),
            })

    return ended


def update_item_history(listing_id: str, price_usd: float, date: str, extra: dict = None):
    """Update individual item price history."""
    history_dir = Path("data/history/item_history")
    history_dir.mkdir(parents=True, exist_ok=True)

    # Create safe filename from listing_id
    safe_id = hashlib.md5(listing_id.encode()).hexdigest()[:16]
    source = listing_id.split(":")[0] if ":" in listing_id else "unknown"
    filepath = history_dir / f"{source}_{safe_id}.json"

    history = load_json_file(filepath)
    if not history:
        history = {
            "listing_id": listing_id,
            "first_seen": date,
            "prices": [],
            "extra": extra or {}
        }

    # Add price point if different from last
    prices = history.get("prices", [])
    if not prices or prices[-1].get("price_usd") != price_usd:
        prices.append({
            "date": date,
            "price_usd": price_usd,
        })
        history["prices"] = prices[-90:]  # Keep last 90 days

    history["last_seen"] = date
    save_json_file(filepath, history)


def archive_daily():
    """Main archiving function - run daily after scraper."""
    print(f"Starting daily archive at {datetime.now(timezone.utc).isoformat()}")

    # Get blue dollar rate
    try:
        blue_rate = get_blue_dollar_rate()
    except:
        blue_rate = 1430.0  # Fallback

    print(f"Using blue dollar rate: {blue_rate}")

    # Load current listings
    current_listings = load_current_listings()
    print(f"Loaded {len(current_listings)} current listings")

    if not current_listings:
        print("No listings found, skipping archive")
        return

    today = get_today_date()
    history_dir = Path("data/history")

    # 1. Save daily snapshot
    snapshots_dir = history_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "blue_dollar_rate": blue_rate,
        "total_count": len(current_listings),
        "listings": [create_listing_summary(l, blue_rate) for l in current_listings],
        "by_category": {},
        "by_source": {},
    }

    # Count by category and source
    for listing in current_listings:
        cat = listing.get("category", "other")
        src = listing.get("source", "unknown")
        snapshot["by_category"][cat] = snapshot["by_category"].get(cat, 0) + 1
        snapshot["by_source"][src] = snapshot["by_source"].get(src, 0) + 1

    snapshot_path = snapshots_dir / f"{today}.json"
    save_json_file(snapshot_path, snapshot)
    print(f"Saved daily snapshot: {snapshot_path}")

    # 2. Load previous snapshot for comparison
    previous = load_previous_snapshot()

    # 3. Detect price changes
    price_changes_path = history_dir / "price_changes.json"
    all_changes = load_json_file(price_changes_path)
    if not isinstance(all_changes, dict):
        all_changes = {"changes": [], "last_updated": None}

    new_changes = detect_price_changes(current_listings, previous, blue_rate)
    if new_changes:
        all_changes["changes"] = new_changes + all_changes.get("changes", [])
        all_changes["changes"] = all_changes["changes"][:1000]  # Keep last 1000
        all_changes["last_updated"] = datetime.now(timezone.utc).isoformat()
        save_json_file(price_changes_path, all_changes)
        print(f"Recorded {len(new_changes)} price changes")

    # 4. Detect ended auctions
    final_prices_path = history_dir / "final_prices.json"
    all_finals = load_json_file(final_prices_path)
    if not isinstance(all_finals, dict):
        all_finals = {"ended": [], "last_updated": None}

    ended = detect_ended_auctions(current_listings, previous)
    if ended:
        all_finals["ended"] = ended + all_finals.get("ended", [])
        all_finals["ended"] = all_finals["ended"][:2000]  # Keep last 2000
        all_finals["last_updated"] = datetime.now(timezone.utc).isoformat()
        save_json_file(final_prices_path, all_finals)
        print(f"Recorded {len(ended)} ended auctions")

    # 5. Update individual item histories
    for listing in current_listings:
        listing_id = listing.get("id")
        if listing_id:
            price_usd = normalize_price_usd(listing, blue_rate)
            if price_usd > 0:
                update_item_history(
                    listing_id,
                    price_usd,
                    today,
                    extra={
                        "title": listing.get("title", "")[:100],
                        "category": listing.get("category"),
                        "source": listing.get("source"),
                    }
                )

    print(f"Updated item histories for {len(current_listings)} listings")

    # 6. Generate summary stats
    stats = generate_archive_stats(history_dir)
    stats_path = history_dir / "archive_stats.json"
    save_json_file(stats_path, stats)
    print(f"Archive complete. Stats: {stats['summary']}")

    return stats


def generate_archive_stats(history_dir: Path) -> dict:
    """Generate summary statistics from archived data."""
    snapshots_dir = history_dir / "snapshots"

    # Count snapshots
    snapshot_files = list(snapshots_dir.glob("*.json")) if snapshots_dir.exists() else []

    # Load price changes
    price_changes = load_json_file(history_dir / "price_changes.json")
    changes_list = price_changes.get("changes", []) if isinstance(price_changes, dict) else []

    # Load final prices
    final_prices = load_json_file(history_dir / "final_prices.json")
    ended_list = final_prices.get("ended", []) if isinstance(final_prices, dict) else []

    # Calculate stats
    price_drops = [c for c in changes_list if c.get("change_percent", 0) < 0]
    price_increases = [c for c in changes_list if c.get("change_percent", 0) > 0]

    avg_drop = sum(c.get("change_percent", 0) for c in price_drops) / len(price_drops) if price_drops else 0
    avg_increase = sum(c.get("change_percent", 0) for c in price_increases) / len(price_increases) if price_increases else 0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_snapshots": len(snapshot_files),
            "total_price_changes": len(changes_list),
            "total_ended_auctions": len(ended_list),
        },
        "price_changes": {
            "total": len(changes_list),
            "drops": len(price_drops),
            "increases": len(price_increases),
            "avg_drop_percent": round(avg_drop, 1),
            "avg_increase_percent": round(avg_increase, 1),
        },
        "ended_auctions": {
            "total": len(ended_list),
            "by_category": _count_by_field(ended_list, "category"),
            "by_source": _count_by_field(ended_list, "source"),
        },
        "date_range": {
            "first": snapshot_files[0].stem if snapshot_files else None,
            "last": snapshot_files[-1].stem if snapshot_files else None,
        }
    }


def _count_by_field(items: list[dict], field: str) -> dict:
    """Count items by a given field."""
    counts = {}
    for item in items:
        value = item.get(field, "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


if __name__ == "__main__":
    archive_daily()
