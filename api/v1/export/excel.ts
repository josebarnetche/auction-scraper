/**
 * Excel Export Endpoint
 *
 * Export auction data as XLSX file with filtering and field selection.
 * Price: $0.03 USDC on Base network
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
 *   - include_summary: true/false - Include summary sheet
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
  Listing,
} from "../../lib/export-utils.js";

// Pricing for Excel export
const EXCEL_EXPORT_PRICE = 0.03;

// Anti-replay protection
const usedTxHashes = new Set<string>();

// Simple XLSX generation using Office Open XML format
// This creates a minimal but valid XLSX file without external dependencies

function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function columnLetter(col: number): string {
  let result = "";
  while (col >= 0) {
    result = String.fromCharCode((col % 26) + 65) + result;
    col = Math.floor(col / 26) - 1;
  }
  return result;
}

function generateSheetXml(
  records: Record<string, any>[],
  fields: string[],
  sheetName: string = "Data"
): string {
  const rows: string[] = [];

  // Header row
  const headerCells = fields.map((field, idx) => {
    const col = columnLetter(idx);
    return `<c r="${col}1" t="inlineStr"><is><t>${escapeXml(field)}</t></is></c>`;
  });
  rows.push(`<row r="1">${headerCells.join("")}</row>`);

  // Data rows
  records.forEach((record, rowIdx) => {
    const rowNum = rowIdx + 2;
    const cells = fields.map((field, colIdx) => {
      const col = columnLetter(colIdx);
      const value = record[field];

      if (value === null || value === undefined || value === "") {
        return `<c r="${col}${rowNum}" t="inlineStr"><is><t></t></is></c>`;
      }

      // Check if numeric
      if (typeof value === "number" && !isNaN(value)) {
        return `<c r="${col}${rowNum}"><v>${value}</v></c>`;
      }

      // Check if boolean
      if (typeof value === "boolean") {
        return `<c r="${col}${rowNum}" t="b"><v>${value ? 1 : 0}</v></c>`;
      }

      // String value
      return `<c r="${col}${rowNum}" t="inlineStr"><is><t>${escapeXml(String(value))}</t></is></c>`;
    });
    rows.push(`<row r="${rowNum}">${cells.join("")}</row>`);
  });

  const lastCol = columnLetter(fields.length - 1);
  const lastRow = records.length + 1;

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews>
    <sheetView tabSelected="1" workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
    </sheetView>
  </sheetViews>
  <sheetData>
    ${rows.join("\n    ")}
  </sheetData>
  <autoFilter ref="A1:${lastCol}${lastRow}"/>
</worksheet>`;
}

function generateSummarySheetXml(
  data: {
    total_count: number;
    by_source: Record<string, number>;
    generated_at: string;
    blue_dollar_rate: number;
    filteredCount: number;
    reportTitle: string;
    reportDescription: string;
  }
): string {
  const rows: string[] = [];
  let rowNum = 1;

  // Title
  rows.push(`<row r="${rowNum}"><c r="A${rowNum}" t="inlineStr"><is><t>${escapeXml(data.reportTitle)}</t></is></c></row>`);
  rowNum++;
  rows.push(`<row r="${rowNum}"><c r="A${rowNum}" t="inlineStr"><is><t>${escapeXml(data.reportDescription)}</t></is></c></row>`);
  rowNum += 2;

  // Summary stats
  rows.push(`<row r="${rowNum}"><c r="A${rowNum}" t="inlineStr"><is><t>Summary</t></is></c></row>`);
  rowNum++;
  rows.push(`<row r="${rowNum}"><c r="A${rowNum}" t="inlineStr"><is><t>Total Listings:</t></is></c><c r="B${rowNum}"><v>${data.total_count}</v></c></row>`);
  rowNum++;
  rows.push(`<row r="${rowNum}"><c r="A${rowNum}" t="inlineStr"><is><t>Exported Records:</t></is></c><c r="B${rowNum}"><v>${data.filteredCount}</v></c></row>`);
  rowNum++;
  rows.push(`<row r="${rowNum}"><c r="A${rowNum}" t="inlineStr"><is><t>Blue Dollar Rate:</t></is></c><c r="B${rowNum}"><v>${data.blue_dollar_rate}</v></c></row>`);
  rowNum++;
  rows.push(`<row r="${rowNum}"><c r="A${rowNum}" t="inlineStr"><is><t>Generated At:</t></is></c><c r="B${rowNum}" t="inlineStr"><is><t>${escapeXml(data.generated_at)}</t></is></c></row>`);
  rowNum += 2;

  // By source breakdown
  rows.push(`<row r="${rowNum}"><c r="A${rowNum}" t="inlineStr"><is><t>Listings by Source</t></is></c></row>`);
  rowNum++;
  rows.push(`<row r="${rowNum}"><c r="A${rowNum}" t="inlineStr"><is><t>Source</t></is></c><c r="B${rowNum}" t="inlineStr"><is><t>Count</t></is></c></row>`);
  rowNum++;

  for (const [source, count] of Object.entries(data.by_source).sort((a, b) => b[1] - a[1])) {
    rows.push(`<row r="${rowNum}"><c r="A${rowNum}" t="inlineStr"><is><t>${escapeXml(source)}</t></is></c><c r="B${rowNum}"><v>${count}</v></c></row>`);
    rowNum++;
  }

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    ${rows.join("\n    ")}
  </sheetData>
</worksheet>`;
}

// ZIP file creation utilities (minimal implementation)
function crc32(data: Buffer): number {
  let crc = 0xffffffff;
  const table = new Uint32Array(256);

  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let j = 0; j < 8; j++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[i] = c;
  }

  for (let i = 0; i < data.length; i++) {
    crc = table[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
  }

  return (crc ^ 0xffffffff) >>> 0;
}

interface ZipEntry {
  name: string;
  content: Buffer;
}

function createZip(entries: ZipEntry[]): Buffer {
  const localHeaders: Buffer[] = [];
  const centralHeaders: Buffer[] = [];
  let offset = 0;

  for (const entry of entries) {
    const nameBuffer = Buffer.from(entry.name, "utf8");
    const content = entry.content;
    const crc = crc32(content);

    // Local file header
    const localHeader = Buffer.alloc(30 + nameBuffer.length);
    localHeader.writeUInt32LE(0x04034b50, 0); // Local header signature
    localHeader.writeUInt16LE(20, 4); // Version needed
    localHeader.writeUInt16LE(0, 6); // Flags
    localHeader.writeUInt16LE(0, 8); // Compression (none)
    localHeader.writeUInt16LE(0, 10); // Mod time
    localHeader.writeUInt16LE(0, 12); // Mod date
    localHeader.writeUInt32LE(crc, 14); // CRC32
    localHeader.writeUInt32LE(content.length, 18); // Compressed size
    localHeader.writeUInt32LE(content.length, 22); // Uncompressed size
    localHeader.writeUInt16LE(nameBuffer.length, 26); // File name length
    localHeader.writeUInt16LE(0, 28); // Extra field length
    nameBuffer.copy(localHeader, 30);

    localHeaders.push(localHeader);
    localHeaders.push(content);

    // Central directory header
    const centralHeader = Buffer.alloc(46 + nameBuffer.length);
    centralHeader.writeUInt32LE(0x02014b50, 0); // Central header signature
    centralHeader.writeUInt16LE(20, 4); // Version made by
    centralHeader.writeUInt16LE(20, 6); // Version needed
    centralHeader.writeUInt16LE(0, 8); // Flags
    centralHeader.writeUInt16LE(0, 10); // Compression
    centralHeader.writeUInt16LE(0, 12); // Mod time
    centralHeader.writeUInt16LE(0, 14); // Mod date
    centralHeader.writeUInt32LE(crc, 16); // CRC32
    centralHeader.writeUInt32LE(content.length, 20); // Compressed size
    centralHeader.writeUInt32LE(content.length, 24); // Uncompressed size
    centralHeader.writeUInt16LE(nameBuffer.length, 28); // File name length
    centralHeader.writeUInt16LE(0, 30); // Extra field length
    centralHeader.writeUInt16LE(0, 32); // Comment length
    centralHeader.writeUInt16LE(0, 34); // Disk start
    centralHeader.writeUInt16LE(0, 36); // Internal attrs
    centralHeader.writeUInt32LE(0, 38); // External attrs
    centralHeader.writeUInt32LE(offset, 42); // Offset to local header
    nameBuffer.copy(centralHeader, 46);

    centralHeaders.push(centralHeader);
    offset += localHeader.length + content.length;
  }

  const centralDirOffset = offset;
  const centralDirSize = centralHeaders.reduce((sum, h) => sum + h.length, 0);

  // End of central directory
  const endRecord = Buffer.alloc(22);
  endRecord.writeUInt32LE(0x06054b50, 0); // End signature
  endRecord.writeUInt16LE(0, 4); // Disk number
  endRecord.writeUInt16LE(0, 6); // Central dir disk
  endRecord.writeUInt16LE(entries.length, 8); // Entries on disk
  endRecord.writeUInt16LE(entries.length, 10); // Total entries
  endRecord.writeUInt32LE(centralDirSize, 12); // Central dir size
  endRecord.writeUInt32LE(centralDirOffset, 16); // Central dir offset
  endRecord.writeUInt16LE(0, 20); // Comment length

  return Buffer.concat([...localHeaders, ...centralHeaders, endRecord]);
}

function generateXlsx(
  records: Record<string, any>[],
  fields: string[],
  summaryData?: {
    total_count: number;
    by_source: Record<string, number>;
    generated_at: string;
    blue_dollar_rate: number;
    filteredCount: number;
    reportTitle: string;
    reportDescription: string;
  }
): Buffer {
  const includeSummary = !!summaryData;

  // Content Types
  const contentTypes = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  ${includeSummary ? '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' : ""}
</Types>`;

  // Relationships
  const rels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`;

  // Workbook relationships
  const workbookRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  ${includeSummary ? '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>' : ""}
</Relationships>`;

  // Workbook
  const workbook = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Auctions" sheetId="1" r:id="rId1"/>
    ${includeSummary ? '<sheet name="Summary" sheetId="2" r:id="rId2"/>' : ""}
  </sheets>
</workbook>`;

  // Data sheet
  const sheet1 = generateSheetXml(records, fields, "Auctions");

  // Build ZIP entries
  const entries: ZipEntry[] = [
    { name: "[Content_Types].xml", content: Buffer.from(contentTypes, "utf8") },
    { name: "_rels/.rels", content: Buffer.from(rels, "utf8") },
    { name: "xl/_rels/workbook.xml.rels", content: Buffer.from(workbookRels, "utf8") },
    { name: "xl/workbook.xml", content: Buffer.from(workbook, "utf8") },
    { name: "xl/worksheets/sheet1.xml", content: Buffer.from(sheet1, "utf8") },
  ];

  // Summary sheet
  if (includeSummary && summaryData) {
    const sheet2 = generateSummarySheetXml(summaryData);
    entries.push({ name: "xl/worksheets/sheet2.xml", content: Buffer.from(sheet2, "utf8") });
  }

  return createZip(entries);
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
      price: EXCEL_EXPORT_PRICE,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
      docs: "/api/v1/price",
      format: "XLSX",
      description: "Export auction data as Excel file with summary sheet",
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
      extra_options: ["include_summary"],
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
  const verification = await verifyUSDCPayment(txHash, EXCEL_EXPORT_PRICE);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment verification failed",
      message: verification.error,
      required: EXCEL_EXPORT_PRICE,
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
    const includeSummary = req.query.include_summary !== "false";

    // Apply report template if specified
    let reportTitle = "Subasto Export";
    let reportDescription = `Generated at ${new Date().toISOString()}`;

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

    // Generate XLSX
    const summaryData = includeSummary
      ? {
          total_count: data.total_count,
          by_source: data.by_source,
          generated_at: data.generated_at,
          blue_dollar_rate: data.blue_dollar_rate,
          filteredCount: listings.length,
          reportTitle,
          reportDescription,
        }
      : undefined;

    const xlsx = generateXlsx(records, fields, summaryData);

    // Generate filename
    const timestamp = new Date().toISOString().split("T")[0];
    const filename = template
      ? `subasto_${template}_${timestamp}.xlsx`
      : `subasto_export_${timestamp}.xlsx`;

    // Set headers for file download
    res.setHeader(
      "Content-Type",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    );
    res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
    res.setHeader("X-Export-Count", listings.length.toString());
    res.setHeader("X-Report-Title", reportTitle);
    res.setHeader("X-Payment-Tx", txHash);
    res.setHeader("X-Payment-Amount", verification.amount?.toString() || "");

    return res.status(200).send(xlsx);
  } catch (error) {
    console.error("Excel export error:", error);
    return res.status(500).json({
      error: "Export failed",
      message: "Failed to generate Excel export",
    });
  }
}
