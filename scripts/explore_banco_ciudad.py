#!/usr/bin/env python3
"""API discovery script for Banco Ciudad auction site.

This script uses Playwright to intercept XHR/Fetch requests and discover
the REST API structure for lot-level data.
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def explore_api():
    """Intercept and log all API calls from Banco Ciudad site."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: Playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    api_calls = []
    lot_data_samples = []

    print("=" * 70)
    print("Banco Ciudad API Discovery")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()

        # Intercept all network requests
        async def handle_request(request):
            url = request.url
            if "subastas_rest" in url or "api" in url.lower():
                api_calls.append({
                    "method": request.method,
                    "url": url,
                    "resource_type": request.resource_type,
                })

        async def handle_response(response):
            url = response.url
            if "subastas_rest" in url:
                try:
                    if response.status == 200:
                        content_type = response.headers.get("content-type", "")
                        if "json" in content_type:
                            body = await response.json()
                            api_calls.append({
                                "method": response.request.method,
                                "url": url,
                                "status": response.status,
                                "response_sample": body if isinstance(body, dict) else body[:3] if isinstance(body, list) else str(body)[:500],
                            })
                except Exception as e:
                    pass

        page.on("request", handle_request)
        page.on("response", handle_response)

        # Visit main page
        print("\n[1] Loading main page...")
        await page.goto("https://subastas.bancociudad.com.ar", wait_until="networkidle", timeout=60000)
        await asyncio.sleep(5)

        print(f"    Found {len(api_calls)} API calls so far")

        # Get auction IDs from the page
        auction_links = await page.query_selector_all('a[href*="/subasta/"]')
        auction_ids = set()

        for link in auction_links:
            href = await link.get_attribute("href")
            if href:
                match = re.search(r'/subasta/(\d+)', href)
                if match:
                    auction_ids.add(match.group(1))

        print(f"\n[2] Found {len(auction_ids)} unique auction IDs")
        print(f"    Sample IDs: {list(auction_ids)[:5]}")

        # Test specific endpoints
        if auction_ids:
            test_id = list(auction_ids)[0]
            print(f"\n[3] Testing API endpoints with auction ID: {test_id}")

            # Test endpoints to discover
            test_endpoints = [
                f"/subastas_rest/subastas",
                f"/subastas_rest/subastas/{test_id}",
                f"/subastas_rest/subastas/{test_id}/lotes",
                f"/subastas_rest/lotes/{test_id}",
                f"/subastas_rest/subastas/detalle/{test_id}",
            ]

            for endpoint in test_endpoints:
                url = f"https://subastas.bancociudad.com.ar{endpoint}"
                print(f"\n    Testing: {endpoint}")
                try:
                    response = await page.request.get(url)
                    status = response.status
                    print(f"    Status: {status}")

                    if status == 200:
                        try:
                            data = await response.json()
                            if isinstance(data, list):
                                print(f"    Response: Array with {len(data)} items")
                                if data:
                                    print(f"    First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'not a dict'}")
                                    if "lote" in str(data[0]).lower() or endpoint.endswith("/lotes"):
                                        lot_data_samples.append({
                                            "endpoint": endpoint,
                                            "sample": data[0] if len(data) > 0 else None
                                        })
                            elif isinstance(data, dict):
                                print(f"    Response keys: {list(data.keys())}")
                                # Check for lots inside the response
                                for key in data.keys():
                                    if "lote" in key.lower():
                                        print(f"    Found lot field: {key}")
                                        if isinstance(data[key], list) and data[key]:
                                            lot_data_samples.append({
                                                "endpoint": endpoint,
                                                "field": key,
                                                "sample": data[key][0]
                                            })
                        except Exception as e:
                            text = await response.text()
                            print(f"    Response (text): {text[:200]}...")
                except Exception as e:
                    print(f"    Error: {e}")

            # Visit a detail page to see lot structure
            print(f"\n[4] Loading auction detail page: {test_id}")
            detail_url = f"https://subastas.bancociudad.com.ar/subasta/{test_id}"

            api_calls_before = len(api_calls)
            await page.goto(detail_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(5)

            print(f"    New API calls from detail page: {len(api_calls) - api_calls_before}")

            # Try to find lot elements on the page
            page_content = await page.content()

            # Look for lot-related patterns
            lot_patterns = [
                r'lote[s]?\s*[#:\d]',
                r'rubro[s]?',
                r'item[s]?\s*[#:\d]',
            ]

            print("\n[5] Searching for lot patterns in page content...")
            for pattern in lot_patterns:
                matches = re.findall(pattern, page_content, re.I)
                if matches:
                    print(f"    Found '{pattern}': {len(matches)} matches")

            # Extract lot containers from HTML structure
            lot_containers = await page.query_selector_all('[class*="lote"], [class*="item"], [class*="rubro"]')
            print(f"    Lot-like containers found: {len(lot_containers)}")

            # Try to extract lot data from page text
            page_text = await page.evaluate("document.body.innerText")

            # Look for price/lot patterns
            lot_price_pattern = r'(?:Lote|Item|Rubro)\s*(?:#|N[°º])?\s*(\d+)[^$]*?\$\s*([\d.,]+)'
            lot_prices = re.findall(lot_price_pattern, page_text, re.I)
            if lot_prices:
                print(f"\n    Found {len(lot_prices)} lot prices in page text:")
                for lot_num, price in lot_prices[:5]:
                    print(f"      Lot #{lot_num}: ${price}")

        await browser.close()

    # Summary
    print("\n" + "=" * 70)
    print("API DISCOVERY SUMMARY")
    print("=" * 70)

    print(f"\nTotal API calls intercepted: {len(api_calls)}")

    # Deduplicate and show unique endpoints
    unique_urls = set()
    for call in api_calls:
        url = call.get("url", "")
        # Normalize URL by removing specific IDs
        normalized = re.sub(r'/\d+', '/{id}', url)
        unique_urls.add(normalized)

    print(f"\nUnique API patterns found:")
    for url in sorted(unique_urls):
        if "subastas_rest" in url:
            print(f"  - {url}")

    if lot_data_samples:
        print(f"\nLot data structure samples:")
        for sample in lot_data_samples:
            print(f"\n  Endpoint: {sample.get('endpoint')}")
            if sample.get('field'):
                print(f"  Field: {sample.get('field')}")
            print(f"  Sample: {json.dumps(sample.get('sample'), indent=4, ensure_ascii=False)[:1000]}")

    # Save results
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    results = {
        "discovered_at": datetime.now().isoformat(),
        "api_calls": api_calls,
        "unique_patterns": list(unique_urls),
        "lot_samples": lot_data_samples,
    }

    output_file = output_dir / "banco_ciudad_api_discovery.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(explore_api())
