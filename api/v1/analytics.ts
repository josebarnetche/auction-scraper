import type { VercelRequest, VercelResponse } from "@vercel/node";
import { readFileSync, existsSync } from "fs";
import { join } from "path";

/**
 * Public analytics endpoint - no authentication required.
 * Returns aggregated market statistics and insights.
 */
export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS headers for public access
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  // Only allow GET requests
  if (req.method !== "GET") {
    return res.status(405).json({
      error: "Method not allowed",
      message: "Only GET requests are supported",
    });
  }

  try {
    // Try to load pre-computed analytics
    const analyticsPath = join(process.cwd(), "site", "api", "analytics.json");

    if (!existsSync(analyticsPath)) {
      // If analytics.json doesn't exist, compute basic stats from listings
      const listingsPath = join(process.cwd(), "site", "api", "listings.json");

      if (!existsSync(listingsPath)) {
        return res.status(503).json({
          error: "Data not available",
          message: "Analytics data is being generated. Please try again later.",
        });
      }

      const listingsData = JSON.parse(readFileSync(listingsPath, "utf-8"));

      // Return basic stats computed on-the-fly
      const basicAnalytics = computeBasicAnalytics(listingsData);

      return res.status(200).json({
        success: true,
        computed: "on-the-fly",
        generated_at: new Date().toISOString(),
        data: basicAnalytics,
      });
    }

    // Return pre-computed analytics
    const analyticsData = JSON.parse(readFileSync(analyticsPath, "utf-8"));

    // Add cache headers (1 hour)
    res.setHeader("Cache-Control", "public, max-age=3600, stale-while-revalidate=7200");

    return res.status(200).json({
      success: true,
      computed: "pre-computed",
      data: analyticsData,
    });
  } catch (error) {
    console.error("Error loading analytics:", error);
    return res.status(500).json({
      error: "Internal error",
      message: "Failed to load analytics data",
    });
  }
}

interface ListingsData {
  total_count: number;
  by_source: Record<string, number>;
  blue_dollar_rate: number;
  with_market_data: number;
  opportunity_count: number;
  premium_count: number;
  top_opportunities: Array<{
    id: string;
    title: string;
    discount_percent: number;
    category: string;
    source: string;
  }>;
  listings: Array<{
    id: string;
    title: string;
    category: string;
    source: string;
    base_price_usd: number;
    market_data?: {
      discount_percent?: number;
      is_opportunity?: boolean;
      typical_usd?: number;
    };
    ends_at?: string;
  }>;
}

interface BasicAnalytics {
  summary: {
    total_listings: number;
    total_sources: number;
    opportunity_count: number;
    blue_dollar_rate: number;
  };
  by_category: Record<string, { count: number; total_value_usd: number }>;
  by_source: Record<string, number>;
  top_opportunities: Array<{
    id: string;
    title: string;
    discount_percent: number;
    category: string;
    source: string;
  }>;
}

function computeBasicAnalytics(data: ListingsData): BasicAnalytics {
  const listings = data.listings || [];

  // Category stats
  const byCategory: Record<string, { count: number; total_value_usd: number }> = {};

  for (const listing of listings) {
    const category = listing.category || "other";
    if (!byCategory[category]) {
      byCategory[category] = { count: 0, total_value_usd: 0 };
    }
    byCategory[category].count += 1;
    byCategory[category].total_value_usd += listing.base_price_usd || 0;
  }

  // Round totals
  for (const cat of Object.keys(byCategory)) {
    byCategory[cat].total_value_usd = Math.round(byCategory[cat].total_value_usd * 100) / 100;
  }

  return {
    summary: {
      total_listings: data.total_count,
      total_sources: Object.keys(data.by_source).length,
      opportunity_count: data.opportunity_count,
      blue_dollar_rate: data.blue_dollar_rate,
    },
    by_category: byCategory,
    by_source: data.by_source,
    top_opportunities: data.top_opportunities?.slice(0, 5) || [],
  };
}
