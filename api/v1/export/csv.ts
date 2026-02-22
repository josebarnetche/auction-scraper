/**
 * CSV Export Endpoint
 *
 * Export auction data as CSV file with filtering and field selection.
 * Price: $0.02 USDC on Base network
 *
 * Query Parameters:
 *   - tx: USDC payment transaction hash (required)
 *   - template: Report template (daily_opportunities, closing_soon, best_deals, by_category)
 *   - categories: Comma-separated category filter
 *   - sources: Comma-separated source filter
 *   - min_price, max_price: ARS price range
 *   - min_price_usd, max_price_usd: USD price range
 *   - start_date, end_date: Date range for auction end dates
 *   - min_discount, max_discount: Discount percentage range
 *   - has_market_data: true/false
 *   - is_opportunity: true/false
 *   - provinces: Comma-separated province filter
 *   - fields: Comma-separated field names to include
 *   - exclude_fields: Comma-separated field names to exclude
 *   - column_order: Comma-separated field order
 *   - sort_by: Field to sort by
 *   - sort_order: asc or desc
 *   - limit: Maximum number of records
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { verifyUSDCPayment } from "../../lib/verify-payment.js";
import { PAYMENT_WALLET } from "../../lib/config.js";
import {
  loadListingsData,
  applyFilters,
  applyReportTemplate,
  sortListings,
  flattenListing,
  parseQueryFilters,
  parseQueryOptions,
  getEffectiveFields,
  ReportTemplate,
} from "../../lib/export-utils.js";

// Pricing for CSV export
const CSV_EXPORT_PRICE = 0.02;

// Anti-replay protection
const usedTxHashes = new Set<string>();

function escapeCSV(value: any): string {
  if (value === null || value === undefined) {
    return "";
  }

  const str = String(value);

  // If contains comma, newline, or quote, wrap in quotes
  if (str.includes(",") || str.includes("\n") || str.includes('"')) {
    return `"${str.replace(/"/g, '""')}"`;
  }

  return str;
}

function generateCSV(
  records: Record<string, any>[],
  fields: string[]
): string {
  if (records.length === 0) {
    return fields.join(",") + "\n";
  }

  // Header row
  const lines: string[] = [fields.map(escapeCSV).join(",")];

  // Data rows
  for (const record of records) {
    const row = fields.map((field) => escapeCSV(record[field]));
    lines.push(row.join(","));
  }

  return lines.join("\n");
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    return res.status(200).end();
  }

  const txHash = req.query.tx as string;

  // Payment required check
  if (!txHash) {
    return res.status(402).json({
      error: "Payment required",
      message: "Include ?tx=YOUR_TX_HASH with USDC payment on Base",
      price: CSV_EXPORT_PRICE,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
      docs: "/api/v1/price",
      format: "CSV",
      description: "Export all auction data as CSV file",
      filters_available: [
        "categories",
        "sources",
        "min_price",
        "max_price",
        "min_price_usd",
        "max_price_usd",
        "start_date",
        "end_date",
        "min_discount",
        "max_discount",
        "provinces",
      ],
      templates_available: [
        "daily_opportunities",
        "closing_soon",
        "best_deals",
        "by_category",
      ],
    });
  }

  // Anti-replay check
  if (usedTxHashes.has(txHash.toLowerCase())) {
    return res.status(400).json({
      error: "Transaction already used",
      message: "Each transaction can only be used once",
    });
  }

  // Verify payment
  const verification = await verifyUSDCPayment(txHash, CSV_EXPORT_PRICE);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment verification failed",
      message: verification.error,
      required: CSV_EXPORT_PRICE,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
    });
  }

  // Mark transaction as used
  usedTxHashes.add(txHash.toLowerCase());

  try {
    // Load data
    const data = loadListingsData();
    let listings = data.listings;

    // Parse query parameters
    const filters = parseQueryFilters(req.query);
    const options = parseQueryOptions(req.query);
    const template = req.query.template as ReportTemplate | undefined;

    // Apply report template if specified
    let reportTitle = "Subasto Export";
    let reportDescription = "";

    if (template) {
      const templateResult = applyReportTemplate(listings, template);
      listings = templateResult.listings;
      reportTitle = templateResult.title;
      reportDescription = templateResult.description;
    }

    // Apply filters
    listings = applyFilters(listings, filters);

    // Sort
    if (options.sortBy) {
      listings = sortListings(listings, options.sortBy, options.sortOrder);
    }

    // Limit
    if (options.limit && options.limit > 0) {
      listings = listings.slice(0, options.limit);
    }

    // Get effective fields
    const fields = getEffectiveFields(options);

    // Flatten listings to records
    const records = listings.map((l) => flattenListing(l, fields));

    // Generate CSV
    const csv = generateCSV(records, fields);

    // Generate filename
    const timestamp = new Date().toISOString().split("T")[0];
    const filename = template
      ? `subasto_${template}_${timestamp}.csv`
      : `subasto_export_${timestamp}.csv`;

    // Set headers for file download
    res.setHeader("Content-Type", "text/csv; charset=utf-8");
    res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
    res.setHeader("X-Export-Count", listings.length.toString());
    res.setHeader("X-Report-Title", reportTitle);
    res.setHeader("X-Payment-Tx", txHash);
    res.setHeader("X-Payment-Amount", verification.amount?.toString() || "");

    return res.status(200).send(csv);
  } catch (error) {
    console.error("CSV export error:", error);
    return res.status(500).json({
      error: "Export failed",
      message: "Failed to generate CSV export",
    });
  }
}
