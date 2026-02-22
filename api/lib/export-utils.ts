/**
 * Shared utilities for bulk data export endpoints
 */

import { readFileSync } from "fs";
import { join } from "path";

// ============================================================================
// Types
// ============================================================================

export interface Listing {
  id: string;
  source: string;
  source_url: string;
  title: string;
  description: string;
  category: string;
  base_price: number;
  currency: string;
  status: string;
  starts_at: string;
  ends_at: string;
  location: {
    province: string;
    city: string;
  };
  images: string[];
  scraped_at: string;
  base_price_usd: number;
  market_data?: {
    source: string;
    keyword_match: string;
    min_usd: number;
    max_usd: number;
    typical_usd: number;
    category: string;
    auction_price_usd: number;
    discount_percent: number;
    is_opportunity: boolean;
  };
  is_top_opportunity?: boolean;
  opportunity_rank?: number;
  source_type: string;
  quality_score: number;
}

export interface ListingsData {
  total_count: number;
  by_source: Record<string, number>;
  generated_at: string;
  blue_dollar_rate: number;
  with_market_data: number;
  opportunity_count: number;
  premium_count: number;
  top_opportunities: any[];
  lots: any[];
  listings: Listing[];
}

export interface ExportFilters {
  categories?: string[];
  sources?: string[];
  minPrice?: number;
  maxPrice?: number;
  minPriceUsd?: number;
  maxPriceUsd?: number;
  startDate?: string;
  endDate?: string;
  minDiscount?: number;
  maxDiscount?: number;
  hasMarketData?: boolean;
  isOpportunity?: boolean;
  provinces?: string[];
}

export interface ExportOptions {
  fields?: string[];
  columnOrder?: string[];
  excludeFields?: string[];
  sortBy?: string;
  sortOrder?: "asc" | "desc";
  limit?: number;
}

export type ReportTemplate =
  | "daily_opportunities"
  | "closing_soon"
  | "best_deals"
  | "by_category";

// ============================================================================
// Data Loading
// ============================================================================

export function loadListingsData(): ListingsData {
  const listingsPath = join(process.cwd(), "site", "api", "listings.json");
  return JSON.parse(readFileSync(listingsPath, "utf-8"));
}

// ============================================================================
// Filtering
// ============================================================================

export function applyFilters(listings: Listing[], filters: ExportFilters): Listing[] {
  return listings.filter((listing) => {
    // Category filter
    if (filters.categories && filters.categories.length > 0) {
      if (!filters.categories.includes(listing.category)) return false;
    }

    // Source filter
    if (filters.sources && filters.sources.length > 0) {
      if (!filters.sources.includes(listing.source)) return false;
    }

    // Price range filter (ARS)
    if (filters.minPrice !== undefined && listing.base_price < filters.minPrice) {
      return false;
    }
    if (filters.maxPrice !== undefined && listing.base_price > filters.maxPrice) {
      return false;
    }

    // Price range filter (USD)
    if (filters.minPriceUsd !== undefined && listing.base_price_usd < filters.minPriceUsd) {
      return false;
    }
    if (filters.maxPriceUsd !== undefined && listing.base_price_usd > filters.maxPriceUsd) {
      return false;
    }

    // Date range filter
    if (filters.startDate) {
      const startDate = new Date(filters.startDate);
      const endsAt = new Date(listing.ends_at);
      if (endsAt < startDate) return false;
    }
    if (filters.endDate) {
      const endDate = new Date(filters.endDate);
      const endsAt = new Date(listing.ends_at);
      if (endsAt > endDate) return false;
    }

    // Discount filter
    if (listing.market_data) {
      if (filters.minDiscount !== undefined &&
          listing.market_data.discount_percent < filters.minDiscount) {
        return false;
      }
      if (filters.maxDiscount !== undefined &&
          listing.market_data.discount_percent > filters.maxDiscount) {
        return false;
      }
    } else if (filters.minDiscount !== undefined || filters.maxDiscount !== undefined) {
      // If discount filter is set but no market data, exclude
      if (filters.hasMarketData) return false;
    }

    // Market data filter
    if (filters.hasMarketData === true && !listing.market_data) {
      return false;
    }
    if (filters.hasMarketData === false && listing.market_data) {
      return false;
    }

    // Opportunity filter
    if (filters.isOpportunity === true && !listing.is_top_opportunity) {
      return false;
    }

    // Province filter
    if (filters.provinces && filters.provinces.length > 0) {
      if (!filters.provinces.includes(listing.location.province)) return false;
    }

    return true;
  });
}

// ============================================================================
// Report Templates
// ============================================================================

export function applyReportTemplate(
  listings: Listing[],
  template: ReportTemplate
): { listings: Listing[]; title: string; description: string } {
  const now = new Date();

  switch (template) {
    case "daily_opportunities": {
      // New listings added today
      const today = now.toISOString().split("T")[0];
      const filtered = listings.filter((l) => {
        const scrapedDate = l.scraped_at.split("T")[0];
        return scrapedDate === today;
      });
      return {
        listings: filtered,
        title: "Daily Opportunities Report",
        description: `New listings added on ${today}`,
      };
    }

    case "closing_soon": {
      // Auctions ending in next 48 hours
      const in48h = new Date(now.getTime() + 48 * 60 * 60 * 1000);
      const filtered = listings.filter((l) => {
        const endsAt = new Date(l.ends_at);
        return endsAt >= now && endsAt <= in48h;
      });
      // Sort by end date
      filtered.sort((a, b) =>
        new Date(a.ends_at).getTime() - new Date(b.ends_at).getTime()
      );
      return {
        listings: filtered,
        title: "Closing Soon Report",
        description: "Auctions ending in the next 48 hours",
      };
    }

    case "best_deals": {
      // Top 20 by discount percentage
      const withDiscount = listings.filter((l) => l.market_data?.discount_percent);
      withDiscount.sort((a, b) =>
        (b.market_data?.discount_percent || 0) - (a.market_data?.discount_percent || 0)
      );
      return {
        listings: withDiscount.slice(0, 20),
        title: "Best Deals Report",
        description: "Top 20 auctions by discount vs market value",
      };
    }

    case "by_category": {
      // Group by category, sort each group by price
      const byCategory = new Map<string, Listing[]>();
      for (const listing of listings) {
        const cat = listing.category || "other";
        if (!byCategory.has(cat)) {
          byCategory.set(cat, []);
        }
        byCategory.get(cat)!.push(listing);
      }

      // Flatten with category grouping preserved
      const sorted: Listing[] = [];
      const categories = Array.from(byCategory.keys()).sort();
      for (const cat of categories) {
        const catListings = byCategory.get(cat)!;
        catListings.sort((a, b) => a.base_price_usd - b.base_price_usd);
        sorted.push(...catListings);
      }

      return {
        listings: sorted,
        title: "By Category Report",
        description: "All listings grouped by category",
      };
    }

    default:
      return {
        listings,
        title: "Export Report",
        description: "Full data export",
      };
  }
}

// ============================================================================
// Field Selection & Ordering
// ============================================================================

export const DEFAULT_EXPORT_FIELDS = [
  "id",
  "title",
  "category",
  "source",
  "base_price",
  "base_price_usd",
  "currency",
  "discount_percent",
  "ends_at",
  "province",
  "source_url",
];

export const ALL_EXPORT_FIELDS = [
  "id",
  "title",
  "description",
  "category",
  "source",
  "source_type",
  "source_url",
  "base_price",
  "base_price_usd",
  "currency",
  "status",
  "starts_at",
  "ends_at",
  "province",
  "city",
  "discount_percent",
  "market_typical_usd",
  "is_opportunity",
  "opportunity_rank",
  "quality_score",
  "image_url",
  "scraped_at",
];

export function flattenListing(listing: Listing, fields: string[]): Record<string, any> {
  const flat: Record<string, any> = {};

  for (const field of fields) {
    switch (field) {
      case "province":
        flat[field] = listing.location?.province || "";
        break;
      case "city":
        flat[field] = listing.location?.city || "";
        break;
      case "discount_percent":
        flat[field] = listing.market_data?.discount_percent || null;
        break;
      case "market_typical_usd":
        flat[field] = listing.market_data?.typical_usd || null;
        break;
      case "is_opportunity":
        flat[field] = listing.market_data?.is_opportunity || false;
        break;
      case "image_url":
        flat[field] = listing.images?.[0] || "";
        break;
      default:
        flat[field] = (listing as any)[field] ?? "";
    }
  }

  return flat;
}

// ============================================================================
// Sorting
// ============================================================================

export function sortListings(
  listings: Listing[],
  sortBy?: string,
  sortOrder: "asc" | "desc" = "desc"
): Listing[] {
  if (!sortBy) return listings;

  const sorted = [...listings];
  sorted.sort((a, b) => {
    let valA: any;
    let valB: any;

    switch (sortBy) {
      case "discount_percent":
        valA = a.market_data?.discount_percent || 0;
        valB = b.market_data?.discount_percent || 0;
        break;
      case "base_price_usd":
        valA = a.base_price_usd;
        valB = b.base_price_usd;
        break;
      case "base_price":
        valA = a.base_price;
        valB = b.base_price;
        break;
      case "ends_at":
        valA = new Date(a.ends_at).getTime();
        valB = new Date(b.ends_at).getTime();
        break;
      case "title":
        valA = a.title.toLowerCase();
        valB = b.title.toLowerCase();
        break;
      default:
        valA = (a as any)[sortBy];
        valB = (b as any)[sortBy];
    }

    if (valA < valB) return sortOrder === "asc" ? -1 : 1;
    if (valA > valB) return sortOrder === "asc" ? 1 : -1;
    return 0;
  });

  return sorted;
}

// ============================================================================
// Query Parameter Parsing
// ============================================================================

export function parseQueryFilters(query: Record<string, any>): ExportFilters {
  const filters: ExportFilters = {};

  if (query.categories) {
    filters.categories = Array.isArray(query.categories)
      ? query.categories
      : query.categories.split(",");
  }

  if (query.sources) {
    filters.sources = Array.isArray(query.sources)
      ? query.sources
      : query.sources.split(",");
  }

  if (query.min_price) filters.minPrice = parseFloat(query.min_price);
  if (query.max_price) filters.maxPrice = parseFloat(query.max_price);
  if (query.min_price_usd) filters.minPriceUsd = parseFloat(query.min_price_usd);
  if (query.max_price_usd) filters.maxPriceUsd = parseFloat(query.max_price_usd);
  if (query.start_date) filters.startDate = query.start_date;
  if (query.end_date) filters.endDate = query.end_date;
  if (query.min_discount) filters.minDiscount = parseFloat(query.min_discount);
  if (query.max_discount) filters.maxDiscount = parseFloat(query.max_discount);
  if (query.has_market_data) filters.hasMarketData = query.has_market_data === "true";
  if (query.is_opportunity) filters.isOpportunity = query.is_opportunity === "true";

  if (query.provinces) {
    filters.provinces = Array.isArray(query.provinces)
      ? query.provinces
      : query.provinces.split(",");
  }

  return filters;
}

export function parseQueryOptions(query: Record<string, any>): ExportOptions {
  const options: ExportOptions = {};

  if (query.fields) {
    options.fields = Array.isArray(query.fields)
      ? query.fields
      : query.fields.split(",");
  }

  if (query.column_order) {
    options.columnOrder = Array.isArray(query.column_order)
      ? query.column_order
      : query.column_order.split(",");
  }

  if (query.exclude_fields) {
    options.excludeFields = Array.isArray(query.exclude_fields)
      ? query.exclude_fields
      : query.exclude_fields.split(",");
  }

  if (query.sort_by) options.sortBy = query.sort_by;
  if (query.sort_order) options.sortOrder = query.sort_order as "asc" | "desc";
  if (query.limit) options.limit = parseInt(query.limit, 10);

  return options;
}

export function getEffectiveFields(options: ExportOptions): string[] {
  let fields = options.fields || [...DEFAULT_EXPORT_FIELDS];

  if (options.excludeFields) {
    fields = fields.filter((f) => !options.excludeFields!.includes(f));
  }

  if (options.columnOrder) {
    // Reorder based on columnOrder, keeping fields not in columnOrder at the end
    const ordered: string[] = [];
    for (const col of options.columnOrder) {
      if (fields.includes(col)) {
        ordered.push(col);
      }
    }
    for (const f of fields) {
      if (!ordered.includes(f)) {
        ordered.push(f);
      }
    }
    fields = ordered;
  }

  return fields;
}
