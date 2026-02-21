#!/usr/bin/env python3
"""Fetch real data for premium curated opportunities."""

import json
import re
import time
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def fetch_url(url, timeout=15):
    """Fetch URL and return HTML content."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None


def extract_adrian_mercado_auction(url):
    """Extract data from Adrian Mercado auction page."""
    html = fetch_url(url)
    if not html:
        return None, None

    soup = BeautifulSoup(html, "html.parser")

    # Extract images
    images = []
    for img in soup.select("img.gallery-image, img.swiper-slide img, .auction-gallery img, .carousel img"):
        src = img.get("src") or img.get("data-src")
        if src and "adrianmercado" in src and not "logo" in src.lower():
            if not src.startswith("http"):
                src = "https://www.adrianmercado.com.ar" + src
            images.append(src)

    # Also check for background images
    for div in soup.select("[style*='background-image']"):
        style = div.get("style", "")
        match = re.search(r"url\(['\"]?([^'\"]+)['\"]?\)", style)
        if match:
            src = match.group(1)
            if not src.startswith("http"):
                src = "https://www.adrianmercado.com.ar" + src
            images.append(src)

    # Extract price
    price = 0
    price_elem = soup.select_one(".price, .base-price, .precio-base, [class*='price']")
    if price_elem:
        price_text = price_elem.get_text()
        match = re.search(r"[\d.,]+", price_text.replace(".", "").replace(",", "."))
        if match:
            try:
                price = float(match.group())
            except:
                pass

    return images[:5], price


def extract_scba_auction(auction_id):
    """Extract data from SCBA auction page."""
    url = f"https://subastas.scba.gov.ar/Auctions/Details/{auction_id}"
    html = fetch_url(url)
    if not html:
        return None, None

    soup = BeautifulSoup(html, "html.parser")

    # Extract images
    images = []
    for img in soup.select("img"):
        src = img.get("src") or img.get("data-src")
        if src and ("subastas.scba" in src or "/Auctions/" in src or "/uploads/" in src.lower()):
            if not src.startswith("http"):
                src = "https://subastas.scba.gov.ar" + src
            if "logo" not in src.lower() and "icon" not in src.lower():
                images.append(src)

    # Extract price from page
    price = 0
    for elem in soup.select("td, span, div"):
        text = elem.get_text()
        if "base" in text.lower() and "$" in text:
            match = re.search(r"\$\s*([\d.,]+)", text)
            if match:
                try:
                    price = float(match.group(1).replace(".", "").replace(",", "."))
                except:
                    pass
                break

    return images[:5], price


def extract_monasterio_auction(remate_id):
    """Extract data from Monasterio-Tattersall auction."""
    url = f"https://activos.monasterio-tattersall.com/remate/{remate_id}"
    html = fetch_url(url)
    if not html:
        return None, None

    soup = BeautifulSoup(html, "html.parser")

    # Extract images
    images = []
    for img in soup.select("img"):
        src = img.get("src") or img.get("data-src")
        if src and ("monasterio" in src or "/uploads/" in src or "/images/" in src):
            if not src.startswith("http"):
                src = "https://activos.monasterio-tattersall.com" + src
            if "logo" not in src.lower():
                images.append(src)

    return images[:5], 0


def extract_global_remates():
    """Extract Scania press data from Global Remates."""
    url = "https://www.globalremates.com.ar/"
    html = fetch_url(url)
    if not html:
        return None, None

    soup = BeautifulSoup(html, "html.parser")

    # Look for Scania-related auctions
    images = []
    for card in soup.select(".auction-card, .remate-item, article, .card"):
        text = card.get_text().lower()
        if "scania" in text or "prensa" in text or "press" in text:
            for img in card.select("img"):
                src = img.get("src") or img.get("data-src")
                if src:
                    if not src.startswith("http"):
                        src = "https://www.globalremates.com.ar" + src
                    images.append(src)

    # Also get any prominent images
    for img in soup.select(".hero img, .featured img, .carousel img"):
        src = img.get("src") or img.get("data-src")
        if src:
            if not src.startswith("http"):
                src = "https://www.globalremates.com.ar" + src
            images.append(src)

    return images[:3], 0


def extract_bidbit_listings():
    """Extract fleet auction data from BidBit."""
    url = "https://www.bidbit.ar/"
    html = fetch_url(url)
    if not html:
        return {}, {}

    soup = BeautifulSoup(html, "html.parser")

    telecom_images = []
    pecom_images = []

    for card in soup.select(".auction-card, .listing-card, article, .card, [class*='auction']"):
        text = card.get_text().lower()
        card_images = []
        for img in card.select("img"):
            src = img.get("src") or img.get("data-src")
            if src and "logo" not in src.lower():
                if not src.startswith("http"):
                    src = "https://www.bidbit.ar" + src
                card_images.append(src)

        if "telecom" in text:
            telecom_images.extend(card_images)
        if "pecom" in text or "energia" in text:
            pecom_images.extend(card_images)

    return telecom_images[:3], pecom_images[:3]


def main():
    curated_path = Path("data/curated/premium_opportunities.json")

    with open(curated_path, encoding="utf-8") as f:
        listings = json.load(f)

    updated = 0

    for listing in listings:
        listing_id = listing["id"]
        url = listing["source_url"]
        print(f"\nProcessing: {listing_id}")
        print(f"  URL: {url}")

        images = None
        price = None

        # Route to appropriate extractor
        if "adrianmercado.com.ar/subastas/" in url and "-" in url.split("/")[-1]:
            # Specific auction page
            images, price = extract_adrian_mercado_auction(url)

        elif "subastas.scba.gov.ar/Auctions/Details/" in url:
            auction_id = url.split("/")[-1]
            images, price = extract_scba_auction(auction_id)

        elif "activos.monasterio-tattersall.com/remate/" in url:
            remate_id = url.split("/")[-1]
            images, price = extract_monasterio_auction(remate_id)

        elif "globalremates.com.ar" in url:
            images, price = extract_global_remates()

        # Update listing if we got data
        if images and len(images) > 0:
            listing["images"] = images
            print(f"  Found {len(images)} images")
            updated += 1

        if price and price > 0:
            listing["base_price"] = price
            print(f"  Found price: {price}")

        time.sleep(0.5)  # Be nice to servers

    # Save updated listings
    with open(curated_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2, ensure_ascii=False)

    print(f"\n\nUpdated {updated} listings with images")

    # Show summary
    with_images = sum(1 for l in listings if l.get("images"))
    with_price = sum(1 for l in listings if l.get("base_price", 0) > 0)
    print(f"Total with images: {with_images}/16")
    print(f"Total with price: {with_price}/16")


if __name__ == "__main__":
    main()
