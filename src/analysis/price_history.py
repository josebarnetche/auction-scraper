#!/usr/bin/env python3
"""Price history analysis module for auction trends and insights.

This module provides:
- Average discount by category over time
- Best days/times to find deals
- Price trends for specific item types
- Seasonal patterns analysis
- Individual item price history
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from collections import defaultdict
import statistics

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class PriceHistoryAnalyzer:
    """Analyzes historical price data for auction insights."""

    def __init__(self, history_dir: str = "data/history"):
        self.history_dir = Path(history_dir)
        self.snapshots_dir = self.history_dir / "snapshots"
        self.item_history_dir = self.history_dir / "item_history"
        self._cache = {}

    def load_snapshots(self, days: int = 30) -> list[dict]:
        """Load snapshots from the last N days."""
        cache_key = f"snapshots_{days}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        snapshots = []
        if not self.snapshots_dir.exists():
            return snapshots

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        for json_file in sorted(self.snapshots_dir.glob("*.json"), reverse=True):
            try:
                date_str = json_file.stem  # YYYY-MM-DD
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if file_date >= cutoff:
                    with open(json_file, encoding="utf-8") as f:
                        snapshots.append(json.load(f))
            except (ValueError, json.JSONDecodeError, IOError):
                continue

        self._cache[cache_key] = snapshots
        return snapshots

    def load_price_changes(self) -> list[dict]:
        """Load all recorded price changes."""
        if "price_changes" in self._cache:
            return self._cache["price_changes"]

        changes_path = self.history_dir / "price_changes.json"
        if not changes_path.exists():
            return []

        try:
            with open(changes_path, encoding="utf-8") as f:
                data = json.load(f)
                changes = data.get("changes", []) if isinstance(data, dict) else []
                self._cache["price_changes"] = changes
                return changes
        except (json.JSONDecodeError, IOError):
            return []

    def load_final_prices(self) -> list[dict]:
        """Load all recorded final auction prices."""
        if "final_prices" in self._cache:
            return self._cache["final_prices"]

        finals_path = self.history_dir / "final_prices.json"
        if not finals_path.exists():
            return []

        try:
            with open(finals_path, encoding="utf-8") as f:
                data = json.load(f)
                ended = data.get("ended", []) if isinstance(data, dict) else []
                self._cache["final_prices"] = ended
                return ended
        except (json.JSONDecodeError, IOError):
            return []

    def get_item_history(self, listing_id: str) -> Optional[dict]:
        """Get price history for a specific listing."""
        import hashlib
        safe_id = hashlib.md5(listing_id.encode()).hexdigest()[:16]
        source = listing_id.split(":")[0] if ":" in listing_id else "unknown"

        filepath = self.item_history_dir / f"{source}_{safe_id}.json"
        if not filepath.exists():
            return None

        try:
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    # =========================================================================
    # INSIGHT 1: Average discount by category over time
    # =========================================================================

    def get_discount_by_category(self, days: int = 30) -> dict:
        """Calculate average discount by category over time.

        Returns:
            {
                "vehicles": {"avg_discount": 45.2, "count": 120, "trend": "up"},
                "real_estate": {"avg_discount": 32.1, "count": 85, "trend": "stable"},
                ...
            }
        """
        snapshots = self.load_snapshots(days)
        if not snapshots:
            return {}

        # Collect discounts by category across all snapshots
        category_discounts = defaultdict(list)

        for snapshot in snapshots:
            for listing in snapshot.get("listings", []):
                category = listing.get("category", "other")
                market_data = listing.get("market_data")
                if market_data and market_data.get("discount_percent"):
                    discount = market_data["discount_percent"]
                    category_discounts[category].append({
                        "discount": discount,
                        "date": snapshot.get("date"),
                    })

        # Calculate stats per category
        results = {}
        for category, discounts in category_discounts.items():
            discount_values = [d["discount"] for d in discounts]
            if not discount_values:
                continue

            avg = statistics.mean(discount_values)
            median = statistics.median(discount_values)

            # Calculate trend (compare first half vs second half)
            mid = len(discounts) // 2
            if mid > 0:
                first_half = statistics.mean([d["discount"] for d in discounts[:mid]])
                second_half = statistics.mean([d["discount"] for d in discounts[mid:]])
                trend_diff = second_half - first_half
                if trend_diff > 2:
                    trend = "up"  # Discounts increasing (better deals)
                elif trend_diff < -2:
                    trend = "down"  # Discounts decreasing
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"

            results[category] = {
                "avg_discount": round(avg, 1),
                "median_discount": round(median, 1),
                "min_discount": round(min(discount_values), 1),
                "max_discount": round(max(discount_values), 1),
                "count": len(discount_values),
                "trend": trend,
            }

        return results

    # =========================================================================
    # INSIGHT 2: Best days to find deals
    # =========================================================================

    def get_best_deal_days(self, days: int = 90) -> dict:
        """Analyze which days of the week have the best deals.

        Returns:
            {
                "best_day": "Tuesday",
                "by_day": {
                    "Monday": {"avg_discount": 42.1, "new_listings": 45},
                    "Tuesday": {"avg_discount": 48.3, "new_listings": 62},
                    ...
                }
            }
        """
        snapshots = self.load_snapshots(days)
        if not snapshots:
            return {"best_day": None, "by_day": {}}

        day_stats = defaultdict(lambda: {"discounts": [], "counts": []})
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for snapshot in snapshots:
            date_str = snapshot.get("date")
            if not date_str:
                continue

            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                day_name = day_names[date.weekday()]
            except ValueError:
                continue

            # Collect discounts for this day
            for listing in snapshot.get("listings", []):
                market_data = listing.get("market_data")
                if market_data and market_data.get("discount_percent"):
                    day_stats[day_name]["discounts"].append(market_data["discount_percent"])

            day_stats[day_name]["counts"].append(snapshot.get("total_count", 0))

        # Calculate stats per day
        by_day = {}
        best_day = None
        best_avg = 0

        for day_name in day_names:
            stats = day_stats[day_name]
            if not stats["discounts"]:
                by_day[day_name] = {"avg_discount": 0, "avg_listings": 0, "sample_size": 0}
                continue

            avg_discount = statistics.mean(stats["discounts"])
            avg_listings = statistics.mean(stats["counts"]) if stats["counts"] else 0

            by_day[day_name] = {
                "avg_discount": round(avg_discount, 1),
                "avg_listings": round(avg_listings),
                "sample_size": len(stats["discounts"]),
            }

            if avg_discount > best_avg:
                best_avg = avg_discount
                best_day = day_name

        return {
            "best_day": best_day,
            "best_avg_discount": round(best_avg, 1) if best_day else 0,
            "by_day": by_day,
            "analysis_period_days": days,
        }

    # =========================================================================
    # INSIGHT 3: Price trends for specific item types
    # =========================================================================

    def get_price_trends(self, category: str = None, days: int = 30) -> dict:
        """Get price trends over time, optionally filtered by category.

        Returns:
            {
                "trend_direction": "down",  # prices dropping
                "avg_change_percent": -3.2,
                "daily_data": [
                    {"date": "2026-02-20", "avg_price_usd": 12500, "count": 45},
                    ...
                ]
            }
        """
        snapshots = self.load_snapshots(days)
        if not snapshots:
            return {"trend_direction": "unknown", "daily_data": []}

        daily_data = []

        for snapshot in sorted(snapshots, key=lambda x: x.get("date", "")):
            prices = []
            discounts = []

            for listing in snapshot.get("listings", []):
                if category and listing.get("category") != category:
                    continue

                price_usd = listing.get("price_usd", 0)
                if price_usd > 0:
                    prices.append(price_usd)

                market_data = listing.get("market_data")
                if market_data and market_data.get("discount_percent"):
                    discounts.append(market_data["discount_percent"])

            if prices:
                daily_data.append({
                    "date": snapshot.get("date"),
                    "avg_price_usd": round(statistics.mean(prices), 2),
                    "median_price_usd": round(statistics.median(prices), 2),
                    "count": len(prices),
                    "avg_discount": round(statistics.mean(discounts), 1) if discounts else None,
                })

        # Determine trend
        if len(daily_data) >= 2:
            first_third = daily_data[:len(daily_data)//3] or daily_data[:1]
            last_third = daily_data[-len(daily_data)//3:] or daily_data[-1:]

            avg_first = statistics.mean([d["avg_price_usd"] for d in first_third])
            avg_last = statistics.mean([d["avg_price_usd"] for d in last_third])

            change_pct = ((avg_last - avg_first) / avg_first) * 100 if avg_first > 0 else 0

            if change_pct > 3:
                trend = "up"
            elif change_pct < -3:
                trend = "down"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
            change_pct = 0

        return {
            "category": category or "all",
            "trend_direction": trend,
            "avg_change_percent": round(change_pct, 1),
            "daily_data": daily_data,
            "analysis_period_days": days,
        }

    # =========================================================================
    # INSIGHT 4: Seasonal patterns
    # =========================================================================

    def get_seasonal_patterns(self, days: int = 90) -> dict:
        """Analyze seasonal patterns in auction listings.

        Returns insights like "More vehicles listed in summer months"
        """
        snapshots = self.load_snapshots(days)
        if not snapshots:
            return {"patterns": [], "by_month": {}}

        month_stats = defaultdict(lambda: defaultdict(list))
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        for snapshot in snapshots:
            date_str = snapshot.get("date")
            if not date_str:
                continue

            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                month = month_names[date.month - 1]
            except ValueError:
                continue

            # Count by category for this month
            for listing in snapshot.get("listings", []):
                category = listing.get("category", "other")
                month_stats[month][category].append(1)

        # Calculate averages per month
        by_month = {}
        for month in month_names:
            if month not in month_stats:
                continue

            by_month[month] = {}
            for category, counts in month_stats[month].items():
                by_month[month][category] = round(statistics.mean(counts) * len(counts), 1)

        # Detect patterns
        patterns = []

        # Check for vehicle seasonality (more in summer = Dec-Feb in Argentina)
        summer_months = ["Dec", "Jan", "Feb"]
        winter_months = ["Jun", "Jul", "Aug"]

        summer_vehicles = sum(by_month.get(m, {}).get("vehicles", 0) for m in summer_months if m in by_month)
        winter_vehicles = sum(by_month.get(m, {}).get("vehicles", 0) for m in winter_months if m in by_month)

        if summer_vehicles > 0 and winter_vehicles > 0:
            ratio = summer_vehicles / winter_vehicles
            if ratio > 1.3:
                patterns.append({
                    "type": "seasonal",
                    "category": "vehicles",
                    "finding": "More vehicles listed in summer (Dec-Feb)",
                    "ratio": round(ratio, 2),
                })
            elif ratio < 0.7:
                patterns.append({
                    "type": "seasonal",
                    "category": "vehicles",
                    "finding": "More vehicles listed in winter (Jun-Aug)",
                    "ratio": round(1/ratio, 2),
                })

        return {
            "patterns": patterns,
            "by_month": by_month,
            "analysis_period_days": days,
        }

    # =========================================================================
    # INSIGHT 5: Price change notifications (item seen before)
    # =========================================================================

    def get_price_change_alert(self, listing_id: str) -> Optional[dict]:
        """Check if a listing's price has changed.

        Returns:
            {
                "has_changed": True,
                "previous_price_usd": 15000,
                "current_price_usd": 12000,
                "change_percent": -20.0,
                "message": "Este item costaba $15,000 USD la semana pasada"
            }
        """
        history = self.get_item_history(listing_id)
        if not history:
            return None

        prices = history.get("prices", [])
        if len(prices) < 2:
            return None

        current = prices[-1]
        previous = prices[-2]

        current_price = current.get("price_usd", 0)
        previous_price = previous.get("price_usd", 0)

        if previous_price == 0:
            return None

        change_pct = ((current_price - previous_price) / previous_price) * 100

        if abs(change_pct) < 1:
            return None  # No significant change

        # Calculate days since previous price
        try:
            current_date = datetime.strptime(current["date"], "%Y-%m-%d")
            previous_date = datetime.strptime(previous["date"], "%Y-%m-%d")
            days_ago = (current_date - previous_date).days
        except (ValueError, KeyError):
            days_ago = None

        if days_ago and days_ago <= 7:
            time_desc = "la semana pasada"
        elif days_ago and days_ago <= 30:
            time_desc = f"hace {days_ago} dias"
        else:
            time_desc = "anteriormente"

        if change_pct < 0:
            message = f"Bajo {abs(round(change_pct))}% - costaba ${previous_price:,.0f} USD {time_desc}"
        else:
            message = f"Subio {round(change_pct)}% - costaba ${previous_price:,.0f} USD {time_desc}"

        return {
            "has_changed": True,
            "previous_price_usd": previous_price,
            "current_price_usd": current_price,
            "change_percent": round(change_pct, 1),
            "days_ago": days_ago,
            "message": message,
            "message_short": f"{'Bajo' if change_pct < 0 else 'Subio'} {abs(round(change_pct))}%",
        }

    # =========================================================================
    # COMBINED MARKET TRENDS DASHBOARD
    # =========================================================================

    def get_market_trends_dashboard(self, days: int = 30) -> dict:
        """Generate comprehensive market trends dashboard data.

        Returns all insights combined for frontend display.
        """
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_period_days": days,
            "discount_by_category": self.get_discount_by_category(days),
            "best_deal_days": self.get_best_deal_days(min(days, 90)),
            "price_trends": {
                "all": self.get_price_trends(None, days),
                "vehicles": self.get_price_trends("vehicles", days),
                "real_estate": self.get_price_trends("real_estate", days),
                "machinery": self.get_price_trends("machinery", days),
            },
            "seasonal_patterns": self.get_seasonal_patterns(min(days, 90)),
            "recent_price_drops": self._get_recent_drops(10),
        }

    def _get_recent_drops(self, limit: int = 10) -> list[dict]:
        """Get most recent significant price drops."""
        changes = self.load_price_changes()

        drops = [c for c in changes if c.get("change_percent", 0) < -5]
        drops.sort(key=lambda x: x.get("detected_at", ""), reverse=True)

        return drops[:limit]


def generate_trends_api():
    """Generate market trends JSON for the API."""
    analyzer = PriceHistoryAnalyzer()
    dashboard = analyzer.get_market_trends_dashboard(days=30)

    api_dir = Path("site/api/v1")
    api_dir.mkdir(parents=True, exist_ok=True)

    output_path = api_dir / "trends.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)

    print(f"Generated market trends API: {output_path}")
    return dashboard


if __name__ == "__main__":
    # Run analysis and generate API
    analyzer = PriceHistoryAnalyzer()

    print("=== Market Trends Analysis ===\n")

    # Discount by category
    print("1. Discount by Category:")
    discounts = analyzer.get_discount_by_category(30)
    for cat, data in discounts.items():
        print(f"   {cat}: {data['avg_discount']}% avg ({data['count']} samples, trend: {data['trend']})")

    # Best deal days
    print("\n2. Best Days for Deals:")
    days = analyzer.get_best_deal_days(90)
    print(f"   Best day: {days['best_day']} ({days['best_avg_discount']}% avg discount)")

    # Price trends
    print("\n3. Price Trends (30 days):")
    trends = analyzer.get_price_trends(None, 30)
    print(f"   Direction: {trends['trend_direction']} ({trends['avg_change_percent']}% change)")

    # Seasonal patterns
    print("\n4. Seasonal Patterns:")
    seasonal = analyzer.get_seasonal_patterns(90)
    for pattern in seasonal["patterns"]:
        print(f"   - {pattern['finding']}")

    # Generate API
    print("\n5. Generating API...")
    generate_trends_api()
