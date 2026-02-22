#!/usr/bin/env python3
"""Generate analytics data from scraped auctions.

Pre-computes market statistics, trends, and insights for the analytics dashboard.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_listings_data() -> Dict[str, Any]:
    """Load the main listings.json data."""
    listings_path = Path("site/api/listings.json")
    if not listings_path.exists():
        print("Error: listings.json not found. Run generate_site.py first.")
        return {}

    with open(listings_path, encoding="utf-8") as f:
        return json.load(f)


def calculate_category_stats(listings: List[Dict]) -> Dict[str, Any]:
    """Calculate statistics by category."""
    by_category = defaultdict(lambda: {
        "count": 0,
        "total_value_usd": 0,
        "with_price": 0,
        "with_images": 0,
        "opportunities": 0,
        "avg_discount": 0,
        "discount_sum": 0
    })

    for listing in listings:
        category = listing.get("category", "other")
        stats = by_category[category]
        stats["count"] += 1

        price_usd = listing.get("base_price_usd", 0)
        if price_usd > 0:
            stats["total_value_usd"] += price_usd
            stats["with_price"] += 1

        if listing.get("images"):
            stats["with_images"] += 1

        market_data = listing.get("market_data", {})
        if market_data.get("is_opportunity"):
            stats["opportunities"] += 1
            discount = market_data.get("discount_percent", 0)
            stats["discount_sum"] += discount

    # Calculate averages
    result = {}
    for category, stats in by_category.items():
        avg_price = stats["total_value_usd"] / stats["with_price"] if stats["with_price"] > 0 else 0
        avg_discount = stats["discount_sum"] / stats["opportunities"] if stats["opportunities"] > 0 else 0

        result[category] = {
            "count": stats["count"],
            "total_value_usd": round(stats["total_value_usd"], 2),
            "avg_price_usd": round(avg_price, 2),
            "with_price": stats["with_price"],
            "with_images": stats["with_images"],
            "opportunities": stats["opportunities"],
            "avg_discount_percent": round(avg_discount, 1)
        }

    return result


def calculate_source_stats(listings: List[Dict]) -> Dict[str, Any]:
    """Calculate statistics by source."""
    by_source = defaultdict(lambda: {
        "count": 0,
        "total_value_usd": 0,
        "with_price": 0,
        "opportunities": 0,
        "source_type": "private"
    })

    judicial_sources = ["csjn", "scba", "cordoba", "entrerios"]

    for listing in listings:
        source = listing.get("source", "unknown")
        stats = by_source[source]
        stats["count"] += 1
        stats["source_type"] = "judicial" if source in judicial_sources else "private"

        price_usd = listing.get("base_price_usd", 0)
        if price_usd > 0:
            stats["total_value_usd"] += price_usd
            stats["with_price"] += 1

        market_data = listing.get("market_data", {})
        if market_data.get("is_opportunity"):
            stats["opportunities"] += 1

    # Sort by count descending
    result = dict(sorted(by_source.items(), key=lambda x: x[1]["count"], reverse=True))

    # Round values
    for source, stats in result.items():
        stats["total_value_usd"] = round(stats["total_value_usd"], 2)

    return result


def calculate_closing_this_week(listings: List[Dict]) -> List[Dict]:
    """Get auctions closing in the next 7 days."""
    now = datetime.now(timezone.utc)
    week_ahead = now + timedelta(days=7)

    closing_soon = []

    for listing in listings:
        ends_at = listing.get("ends_at")
        if not ends_at:
            continue

        try:
            if isinstance(ends_at, str):
                end_date = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
            else:
                continue

            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            if now <= end_date <= week_ahead:
                days_left = (end_date - now).days
                hours_left = (end_date - now).seconds // 3600

                closing_soon.append({
                    "id": listing.get("id"),
                    "title": listing.get("title", "")[:80],
                    "category": listing.get("category", "other"),
                    "source": listing.get("source", "unknown"),
                    "source_url": listing.get("source_url", ""),
                    "base_price_usd": listing.get("base_price_usd", 0),
                    "ends_at": ends_at,
                    "days_left": days_left,
                    "hours_left": hours_left if days_left == 0 else 0,
                    "has_opportunity": listing.get("market_data", {}).get("is_opportunity", False),
                    "discount_percent": listing.get("market_data", {}).get("discount_percent", 0)
                })
        except (ValueError, TypeError):
            continue

    # Sort by closing date
    closing_soon.sort(key=lambda x: x["ends_at"])

    return closing_soon[:20]  # Top 20


def calculate_best_deals(listings: List[Dict]) -> List[Dict]:
    """Get the best deals ranked by discount percentage."""
    deals = []

    for listing in listings:
        market_data = listing.get("market_data", {})
        discount = market_data.get("discount_percent", 0)

        if discount >= 20:  # Minimum 20% discount
            deals.append({
                "id": listing.get("id"),
                "title": listing.get("title", "")[:80],
                "category": listing.get("category", "other"),
                "source": listing.get("source", "unknown"),
                "source_url": listing.get("source_url", ""),
                "base_price_usd": listing.get("base_price_usd", 0),
                "market_price_usd": market_data.get("typical_usd", 0),
                "discount_percent": round(discount, 1),
                "is_premium": listing.get("is_premium", False),
                "images": listing.get("images", [])[:1]
            })

    # Sort by discount descending
    deals.sort(key=lambda x: x["discount_percent"], reverse=True)

    return deals[:15]  # Top 15


def analyze_best_day_for_deals(listings: List[Dict]) -> Dict[str, Any]:
    """Analyze which day of week has the most deals closing."""
    day_counts = defaultdict(lambda: {"total": 0, "opportunities": 0})
    day_names = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    for listing in listings:
        ends_at = listing.get("ends_at")
        if not ends_at:
            continue

        try:
            if isinstance(ends_at, str):
                end_date = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                day_of_week = end_date.weekday()
                day_counts[day_of_week]["total"] += 1

                if listing.get("market_data", {}).get("is_opportunity"):
                    day_counts[day_of_week]["opportunities"] += 1
        except (ValueError, TypeError):
            continue

    # Find best day
    best_day = max(day_counts.items(), key=lambda x: x[1]["opportunities"], default=(0, {"total": 0, "opportunities": 0}))

    result = {
        "by_day": {day_names[i]: day_counts[i] for i in range(7)},
        "best_day": day_names[best_day[0]] if best_day[1]["opportunities"] > 0 else "N/A",
        "best_day_opportunities": best_day[1]["opportunities"],
        "insight": f"Los {day_names[best_day[0]].lower()} tienen mas oportunidades de descuento" if best_day[1]["opportunities"] > 0 else "No hay suficientes datos"
    }

    return result


def analyze_undervalued_category(category_stats: Dict[str, Any]) -> Dict[str, Any]:
    """Determine which category has the most undervalued assets."""
    best_category = None
    best_ratio = 0

    for category, stats in category_stats.items():
        if stats["count"] < 5:  # Minimum sample size
            continue

        # Ratio of opportunities to total listings
        ratio = stats["opportunities"] / stats["count"] if stats["count"] > 0 else 0

        if ratio > best_ratio:
            best_ratio = ratio
            best_category = category

    category_labels = {
        "vehicles": "Vehiculos",
        "real_estate": "Inmuebles",
        "machinery": "Maquinaria",
        "general_goods": "Bienes Generales",
        "other": "Otros"
    }

    if best_category:
        stats = category_stats[best_category]
        return {
            "category": best_category,
            "category_label": category_labels.get(best_category, best_category.title()),
            "opportunity_ratio": round(best_ratio * 100, 1),
            "avg_discount": stats["avg_discount_percent"],
            "total_opportunities": stats["opportunities"],
            "insight": f"{category_labels.get(best_category, best_category.title())} tiene {round(best_ratio * 100, 1)}% de listings con descuento significativo"
        }

    return {
        "category": None,
        "insight": "No hay suficientes datos para determinar la categoria mas subvaluada"
    }


def calculate_trending_items(listings: List[Dict]) -> List[Dict]:
    """Get trending/hot items this week based on various signals."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    trending = []

    for listing in listings:
        score = 0
        signals = []

        # Recently scraped
        scraped_at = listing.get("scraped_at")
        if scraped_at:
            try:
                scraped_date = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
                if scraped_date >= week_ago:
                    score += 20
                    signals.append("nuevo")
            except (ValueError, TypeError):
                pass

        # High quality listing
        quality = listing.get("quality_score", 0)
        if quality >= 80:
            score += 15
            signals.append("alta_calidad")

        # Has discount opportunity
        market_data = listing.get("market_data", {})
        discount = market_data.get("discount_percent", 0)
        if discount >= 40:
            score += 25
            signals.append("gran_descuento")
        elif discount >= 20:
            score += 10
            signals.append("buen_descuento")

        # Premium listing
        if listing.get("is_premium"):
            score += 20
            signals.append("premium")

        # Top opportunity
        if listing.get("is_top_opportunity"):
            score += 30
            signals.append("top_oportunidad")

        # Closing soon (within 5 days)
        ends_at = listing.get("ends_at")
        if ends_at:
            try:
                end_date = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=timezone.utc)
                days_until = (end_date - now).days
                if 0 <= days_until <= 5:
                    score += 15
                    signals.append("cierra_pronto")
            except (ValueError, TypeError):
                pass

        # Judicial source (more trustworthy)
        if listing.get("source_type") == "judicial":
            score += 10
            signals.append("judicial")

        if score >= 30:  # Minimum trending score
            trending.append({
                "id": listing.get("id"),
                "title": listing.get("title", "")[:80],
                "category": listing.get("category", "other"),
                "source": listing.get("source", "unknown"),
                "source_url": listing.get("source_url", ""),
                "base_price_usd": listing.get("base_price_usd", 0),
                "discount_percent": round(discount, 1) if discount > 0 else None,
                "trending_score": score,
                "signals": signals,
                "images": listing.get("images", [])[:1]
            })

    # Sort by trending score
    trending.sort(key=lambda x: x["trending_score"], reverse=True)

    return trending[:10]


def calculate_price_comparison(listings: List[Dict]) -> Dict[str, Any]:
    """Compare auction prices vs retail market prices."""
    comparisons = defaultdict(lambda: {
        "auction_total_usd": 0,
        "market_total_usd": 0,
        "count": 0
    })

    for listing in listings:
        market_data = listing.get("market_data", {})
        auction_price = market_data.get("auction_price_usd", 0)
        market_price = market_data.get("typical_usd", 0)

        if auction_price > 0 and market_price > 0:
            category = listing.get("category", "other")
            comparisons[category]["auction_total_usd"] += auction_price
            comparisons[category]["market_total_usd"] += market_price
            comparisons[category]["count"] += 1

    result = {}
    overall_auction = 0
    overall_market = 0
    overall_count = 0

    for category, data in comparisons.items():
        if data["count"] >= 3:  # Minimum sample
            avg_savings = ((data["market_total_usd"] - data["auction_total_usd"]) / data["market_total_usd"]) * 100
            result[category] = {
                "avg_auction_price_usd": round(data["auction_total_usd"] / data["count"], 2),
                "avg_market_price_usd": round(data["market_total_usd"] / data["count"], 2),
                "avg_savings_percent": round(avg_savings, 1),
                "sample_size": data["count"]
            }
            overall_auction += data["auction_total_usd"]
            overall_market += data["market_total_usd"]
            overall_count += data["count"]

    overall_savings = ((overall_market - overall_auction) / overall_market) * 100 if overall_market > 0 else 0

    return {
        "by_category": result,
        "overall": {
            "avg_savings_percent": round(overall_savings, 1),
            "total_samples": overall_count,
            "insight": f"En promedio, los compradores ahorran {round(overall_savings, 1)}% comprando en subastas vs retail"
        }
    }


def generate_time_series(listings: List[Dict]) -> Dict[str, Any]:
    """Generate time series data for listings over time."""
    # Group by scraped date
    by_date = defaultdict(lambda: {"count": 0, "categories": defaultdict(int)})

    for listing in listings:
        scraped_at = listing.get("scraped_at")
        if not scraped_at:
            continue

        try:
            scraped_date = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
            date_key = scraped_date.strftime("%Y-%m-%d")
            by_date[date_key]["count"] += 1
            by_date[date_key]["categories"][listing.get("category", "other")] += 1
        except (ValueError, TypeError):
            continue

    # Convert to sorted list
    time_series = []
    for date_key in sorted(by_date.keys())[-30:]:  # Last 30 days
        data = by_date[date_key]
        time_series.append({
            "date": date_key,
            "total": data["count"],
            **{f"cat_{k}": v for k, v in data["categories"].items()}
        })

    return {
        "daily_listings": time_series,
        "period": "30_days"
    }


def generate_analytics():
    """Main function to generate all analytics data."""
    print("Loading listings data...")
    data = load_listings_data()

    if not data:
        print("No data to analyze.")
        return

    listings = data.get("listings", [])
    print(f"Analyzing {len(listings)} listings...")

    # Calculate all statistics
    print("Calculating category statistics...")
    category_stats = calculate_category_stats(listings)

    print("Calculating source statistics...")
    source_stats = calculate_source_stats(listings)

    print("Finding auctions closing this week...")
    closing_soon = calculate_closing_this_week(listings)

    print("Finding best deals...")
    best_deals = calculate_best_deals(listings)

    print("Analyzing best day for deals...")
    best_day_analysis = analyze_best_day_for_deals(listings)

    print("Finding most undervalued category...")
    undervalued_analysis = analyze_undervalued_category(category_stats)

    print("Finding trending items...")
    trending = calculate_trending_items(listings)

    print("Calculating price comparisons...")
    price_comparison = calculate_price_comparison(listings)

    print("Generating time series...")
    time_series = generate_time_series(listings)

    # Build final analytics object
    analytics_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_listings": len(listings),
            "total_sources": len(source_stats),
            "total_categories": len(category_stats),
            "total_value_usd": sum(s["total_value_usd"] for s in category_stats.values()),
            "opportunity_count": sum(s["opportunities"] for s in category_stats.values()),
            "blue_dollar_rate": data.get("blue_dollar_rate", 1430)
        },
        "by_category": category_stats,
        "by_source": source_stats,
        "closing_this_week": closing_soon,
        "best_deals": best_deals,
        "trending": trending,
        "insights": {
            "best_day_for_deals": best_day_analysis,
            "most_undervalued_category": undervalued_analysis,
            "price_comparison": price_comparison
        },
        "time_series": time_series
    }

    # Write analytics.json
    output_path = Path("site/api/analytics.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analytics_data, f, indent=2, ensure_ascii=False)

    print(f"\nGenerated {output_path}")
    print(f"  Total listings: {len(listings)}")
    print(f"  Categories: {list(category_stats.keys())}")
    print(f"  Sources: {len(source_stats)}")
    print(f"  Opportunities: {analytics_data['summary']['opportunity_count']}")
    print(f"  Closing this week: {len(closing_soon)}")
    print(f"  Best deals: {len(best_deals)}")
    print(f"  Trending items: {len(trending)}")

    # Print insights
    print(f"\n  INSIGHTS:")
    print(f"    Best day: {best_day_analysis['best_day']}")
    print(f"    Undervalued category: {undervalued_analysis.get('category_label', 'N/A')}")
    print(f"    Avg savings vs retail: {price_comparison['overall']['avg_savings_percent']}%")


if __name__ == "__main__":
    generate_analytics()
