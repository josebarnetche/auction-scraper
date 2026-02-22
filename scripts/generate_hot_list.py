"""Generate hot list of urgent/opportunity auctions."""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_listings():
    """Load all listings from API JSON."""
    api_file = Path("site/api/listings.json")
    if not api_file.exists():
        print("No listings.json found")
        return []

    with open(api_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("listings", [])


def is_ending_soon(listing, days=7):
    """Check if auction ends within N days."""
    ends_at = listing.get("ends_at")
    if not ends_at:
        return False

    try:
        # Parse ISO date
        if isinstance(ends_at, str):
            end_date = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
        else:
            return False

        now = datetime.now(timezone.utc)
        delta = end_date - now
        return timedelta(0) < delta < timedelta(days=days)
    except (ValueError, TypeError):
        return False


def days_until(listing):
    """Get days until auction ends."""
    ends_at = listing.get("ends_at")
    if not ends_at:
        return 999

    try:
        if isinstance(ends_at, str):
            end_date = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
        else:
            return 999

        now = datetime.now(timezone.utc)
        delta = end_date - now
        return max(0, delta.days)
    except (ValueError, TypeError):
        return 999


def get_discount(listing):
    """Get discount percentage if available."""
    # Check various locations for discount data
    if listing.get("market_data", {}).get("discount_percent"):
        return listing["market_data"]["discount_percent"]
    if listing.get("extra", {}).get("discount_percent"):
        return listing["extra"]["discount_percent"]
    return 0


def get_usd_price(listing, blue_rate=1430):
    """Convert price to USD."""
    price = listing.get("base_price", 0)
    currency = listing.get("currency", "ARS")

    if currency == "USD":
        return price
    return price / blue_rate


def score_listing(listing):
    """Score listing for hotness (higher = hotter)."""
    score = 0

    # Time urgency (ending soon = hot)
    days = days_until(listing)
    if days <= 2:
        score += 50
    elif days <= 5:
        score += 30
    elif days <= 7:
        score += 15

    # Discount (big discount = hot)
    discount = get_discount(listing)
    if discount >= 50:
        score += 40
    elif discount >= 30:
        score += 25
    elif discount >= 20:
        score += 10

    # Premium listings are hot
    if listing.get("is_premium") or listing.get("extra", {}).get("is_premium"):
        score += 30

    # Has images (more credible)
    if listing.get("images"):
        score += 5

    # Has price
    if listing.get("base_price", 0) > 0:
        score += 5

    # Categories that move fast
    category = listing.get("category", "")
    if category == "vehicles":
        score += 10
    elif category == "machinery":
        score += 5

    return score


def format_price(listing, blue_rate=1430):
    """Format price for display."""
    price = listing.get("base_price", 0)
    currency = listing.get("currency", "ARS")

    if currency == "USD":
        return f"USD ${price:,.0f}"
    else:
        usd = price / blue_rate
        return f"${price:,.0f} ARS (~USD ${usd:,.0f})"


def main():
    print("=" * 80)
    print("AUCTION RADAR - HOT LIST")
    print("=" * 80)
    print()

    listings = load_listings()
    if not listings:
        print("No listings found")
        return

    print(f"Total listings: {len(listings)}")
    print()

    # Score all listings
    scored = []
    for listing in listings:
        score = score_listing(listing)
        if score > 0:  # Only include items with some score
            scored.append((score, listing))

    # Sort by score (highest first)
    scored.sort(key=lambda x: -x[0])

    # Get top hot items
    hot_list = scored[:20]

    print("=" * 80)
    print("TOP 20 HOT AUCTIONS")
    print("(Ending soon + Good discounts + Premium)")
    print("=" * 80)
    print()

    for i, (score, listing) in enumerate(hot_list, 1):
        days = days_until(listing)
        discount = get_discount(listing)

        # Build tags
        tags = []
        if days <= 2:
            tags.append("ENDING SOON!")
        elif days <= 5:
            tags.append(f"{days}d left")

        if discount >= 30:
            tags.append(f"{discount:.0f}% OFF")

        if listing.get("is_premium") or listing.get("extra", {}).get("is_premium"):
            tags.append("PREMIUM")

        premium_type = listing.get("extra", {}).get("premium_type", "")
        if premium_type:
            tags.append(premium_type.upper())

        tag_str = " | ".join(tags) if tags else ""

        print(f"{i:2}. [{score:3}] {listing.get('title', 'N/A')[:60]}")
        print(f"     {format_price(listing)}")
        if tag_str:
            print(f"     {tag_str}")
        print(f"     Source: {listing.get('source')} | {listing.get('category')}")
        print(f"     URL: {listing.get('source_url', 'N/A')}")
        print()

    # Stats
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    ending_soon = sum(1 for _, l in scored if days_until(l) <= 7)
    big_discounts = sum(1 for _, l in scored if get_discount(l) >= 30)
    premium = sum(1 for _, l in scored if l.get("is_premium") or l.get("extra", {}).get("is_premium"))

    print(f"Ending within 7 days: {ending_soon}")
    print(f"30%+ discount: {big_discounts}")
    print(f"Premium listings: {premium}")

    # Save to file
    hot_json = []
    for score, listing in hot_list:
        hot_json.append({
            "id": listing.get("id"),
            "title": listing.get("title"),
            "price": format_price(listing),
            "days_until_end": days_until(listing),
            "discount_percent": get_discount(listing),
            "is_premium": listing.get("is_premium") or listing.get("extra", {}).get("is_premium"),
            "category": listing.get("category"),
            "source": listing.get("source"),
            "source_url": listing.get("source_url"),
            "score": score,
        })

    with open("data/hot_list.json", "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(hot_json),
            "items": hot_json,
        }, f, ensure_ascii=False, indent=2)

    print()
    print("Hot list saved to data/hot_list.json")


if __name__ == "__main__":
    main()
