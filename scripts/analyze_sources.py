#!/usr/bin/env python3
"""Analyze all auction sources and generate statistics.

Generates:
- data/source_stats.json - Cached statistics for API
- site/api/v1/sources.json - Public API endpoint

Usage:
    python scripts/analyze_sources.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.source_analytics import (
    analyze_all_sources,
    get_why_judicial_content,
    get_source_badge_info,
    SOURCE_METADATA,
)


def main():
    """Run source analysis and generate output files."""
    print("=" * 60)
    print("SOURCE ANALYTICS")
    print("=" * 60)

    # Analyze all sources
    data_dir = Path("data/raw")
    results = analyze_all_sources(data_dir)

    # Print summary
    summary = results["summary"]
    print(f"\nSummary:")
    print(f"  Total sources: {summary['total_sources']}")
    print(f"  Judicial: {summary['judicial_sources']}")
    print(f"  Private: {summary['private_sources']}")
    print(f"  Total listings: {summary['total_listings']}")
    print(f"  Active listings: {summary['active_listings']}")
    print(f"  Avg quality score: {summary['average_quality_score']}/100")

    # Print source rankings
    print(f"\nSource Rankings (by Trust Score):")
    print("-" * 60)
    for i, (source_id, metrics) in enumerate(results["sources"].items(), 1):
        source_type = "JUD" if metrics["source_type"] == "judicial" else "PRI"
        print(
            f"  {i:2d}. [{source_type}] {metrics['source_name']:<25} "
            f"Trust: {metrics['trust_score']:3d} | "
            f"Quality: {metrics['quality_score']:3d} | "
            f"Listings: {metrics['total_listings']:4d}"
        )

    # Print quality breakdown for each source
    print(f"\nQuality Breakdown:")
    print("-" * 60)
    print(f"{'Source':<20} {'Imgs':>6} {'Desc':>6} {'Price':>6} {'Date':>6} {'Loc':>6}")
    print("-" * 60)
    for source_id, metrics in results["sources"].items():
        print(
            f"{metrics['source_name']:<20} "
            f"{metrics['image_score']:>5}% "
            f"{metrics['description_score']:>5}% "
            f"{metrics['price_score']:>5}% "
            f"{metrics['date_score']:>5}% "
            f"{metrics['location_score']:>5}%"
        )

    # Print fee comparison
    print(f"\nFee Comparison:")
    print("-" * 60)
    for source_id, metrics in results["sources"].items():
        iva = "incl IVA" if metrics["iva_included"] else "sin IVA"
        print(
            f"  {metrics['source_name']:<25} "
            f"{metrics['buyer_commission_pct']:.1f}% + {metrics['platform_fee_pct']:.1f}% ({iva})"
        )

    # Add badge info for each source
    for source_id in results["sources"]:
        results["sources"][source_id]["badge_info"] = get_source_badge_info(source_id)

    # Add "Why Judicial" content
    results["why_judicial"] = get_why_judicial_content()

    # Add source metadata for frontend
    results["source_metadata"] = {}
    for source_id, meta in SOURCE_METADATA.items():
        results["source_metadata"][source_id] = {
            "name": meta.get("name", source_id.title()),
            "full_name": meta.get("full_name", ""),
            "type": meta.get("type", "private"),
            "website": meta.get("website", ""),
            "why_trust": meta.get("why_trust", ""),
            "typical_fees": meta.get("typical_fees", ""),
        }

    # Save to data directory
    output_path = Path("data/source_stats.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {output_path}")

    # Save to site API directory
    api_dir = Path("site/api/v1")
    api_dir.mkdir(parents=True, exist_ok=True)

    # Create public API response (free endpoint)
    api_response = {
        "status": "success",
        "data": {
            "sources": results["sources"],
            "summary": results["summary"],
            "why_judicial": results["why_judicial"],
        },
        "meta": {
            "generated_at": results["generated_at"],
            "endpoint": "/api/v1/sources",
            "description": "Source analytics and trust scores for all auction houses",
            "free": True,
        },
    }

    api_path = api_dir / "sources.json"
    with open(api_path, "w", encoding="utf-8") as f:
        json.dump(api_response, f, indent=2, ensure_ascii=False)
    print(f"Saved: {api_path}")

    # Update openapi.json to include sources endpoint
    openapi_path = api_dir / "openapi.json"
    if openapi_path.exists():
        try:
            with open(openapi_path, "r", encoding="utf-8") as f:
                openapi = json.load(f)

            # Add sources endpoint if not present
            if "/sources" not in openapi.get("paths", {}):
                openapi["paths"]["/sources"] = {
                    "get": {
                        "summary": "Get source analytics",
                        "description": "Returns trust scores, quality metrics, and fee information for all auction sources. FREE endpoint.",
                        "tags": ["Sources"],
                        "responses": {
                            "200": {
                                "description": "Source analytics data",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "status": {"type": "string"},
                                                "data": {
                                                    "type": "object",
                                                    "properties": {
                                                        "sources": {
                                                            "type": "object",
                                                            "description": "Source metrics keyed by source_id"
                                                        },
                                                        "summary": {
                                                            "type": "object",
                                                            "description": "Overall statistics"
                                                        },
                                                        "why_judicial": {
                                                            "type": "object",
                                                            "description": "Explainer content for judicial auctions"
                                                        }
                                                    }
                                                },
                                                "meta": {"type": "object"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                with open(openapi_path, "w", encoding="utf-8") as f:
                    json.dump(openapi, f, indent=2, ensure_ascii=False)
                print(f"Updated: {openapi_path}")
        except Exception as e:
            print(f"Warning: Could not update openapi.json: {e}")

    print("\nDone!")
    return results


if __name__ == "__main__":
    main()
