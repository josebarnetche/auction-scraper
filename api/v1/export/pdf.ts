/**
 * PDF Report Export Endpoint
 *
 * Generate professional PDF reports with auction data.
 * Price: $0.05 USDC on Base network
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
 *   - limit: Maximum number of records
 *   - include_images: true/false (default: false for performance)
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { verifyUSDCPayment } from "../../lib/verify-payment.js";
import { PAYMENT_WALLET } from "../../lib/config.js";
import {
  loadListingsData,
  applyFilters,
  applyReportTemplate,
  sortListings,
  parseQueryFilters,
  parseQueryOptions,
  ReportTemplate,
  Listing,
} from "../../lib/export-utils.js";

// Pricing for PDF export
const PDF_EXPORT_PRICE = 0.05;

// Anti-replay protection
const usedTxHashes = new Set<string>();

// ============================================================================
// PDF Generation (minimal implementation)
// ============================================================================

class PDFGenerator {
  private objects: string[] = [];
  private objectCount = 0;
  private pages: number[] = [];
  private currentPage = "";
  private yPosition = 800;
  private pageWidth = 612;
  private pageHeight = 792;
  private margin = 50;
  private contentWidth = this.pageWidth - 2 * this.margin;

  constructor() {
    // Initialize with catalog and pages objects (will be added at the end)
  }

  private addObject(content: string): number {
    this.objectCount++;
    this.objects.push(content);
    return this.objectCount;
  }

  private escapeText(text: string): string {
    return text
      .replace(/\\/g, "\\\\")
      .replace(/\(/g, "\\(")
      .replace(/\)/g, "\\)")
      .replace(/[^\x20-\x7E]/g, "?"); // Replace non-ASCII with ?
  }

  private truncateText(text: string, maxChars: number): string {
    if (text.length <= maxChars) return text;
    return text.substring(0, maxChars - 3) + "...";
  }

  private startNewPage(): void {
    if (this.currentPage) {
      const streamContent = this.currentPage;
      const streamId = this.addObject(
        `<< /Length ${streamContent.length} >>\nstream\n${streamContent}endstream`
      );
      const pageId = this.addObject(
        `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${this.pageWidth} ${this.pageHeight}] /Contents ${streamId} 0 R /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>`
      );
      this.pages.push(pageId);
    }

    this.currentPage = "";
    this.yPosition = this.pageHeight - this.margin;
  }

  private addText(
    text: string,
    x: number,
    y: number,
    fontSize: number = 10,
    fontId: string = "F1"
  ): void {
    this.currentPage += `BT /${fontId} ${fontSize} Tf ${x} ${y} Td (${this.escapeText(text)}) Tj ET\n`;
  }

  private addLine(x1: number, y1: number, x2: number, y2: number): void {
    this.currentPage += `0.7 G ${x1} ${y1} m ${x2} ${y2} l S\n`;
  }

  private addRect(x: number, y: number, w: number, h: number, fill: boolean = false): void {
    if (fill) {
      this.currentPage += `0.95 g ${x} ${y} ${w} ${h} re f\n`;
    } else {
      this.currentPage += `0.5 G ${x} ${y} ${w} ${h} re S\n`;
    }
  }

  private checkPageBreak(neededHeight: number): void {
    if (this.yPosition - neededHeight < this.margin + 50) {
      this.startNewPage();
    }
  }

  public generate(
    listings: Listing[],
    metadata: {
      title: string;
      description: string;
      totalCount: number;
      filteredCount: number;
      blueDollarRate: number;
      generatedAt: string;
      bySource: Record<string, number>;
      template?: string;
    }
  ): Buffer {
    // Start first page
    this.startNewPage();

    // Header
    this.addText("SUBASTO", this.margin, this.yPosition, 24, "F2");
    this.yPosition -= 20;
    this.addText("Argentine Auction Intelligence", this.margin, this.yPosition, 10, "F1");
    this.yPosition -= 30;

    // Report Title
    this.addText(metadata.title, this.margin, this.yPosition, 16, "F2");
    this.yPosition -= 18;
    this.addText(metadata.description, this.margin, this.yPosition, 10, "F1");
    this.yPosition -= 25;

    // Divider
    this.addLine(this.margin, this.yPosition, this.pageWidth - this.margin, this.yPosition);
    this.yPosition -= 20;

    // Summary Box
    this.addRect(this.margin, this.yPosition - 80, this.contentWidth, 80, true);
    this.addRect(this.margin, this.yPosition - 80, this.contentWidth, 80, false);

    const boxLeft = this.margin + 10;
    const boxTop = this.yPosition - 10;

    this.addText("REPORT SUMMARY", boxLeft, boxTop, 11, "F2");
    this.addText(
      `Total Listings: ${metadata.filteredCount} of ${metadata.totalCount}`,
      boxLeft,
      boxTop - 18,
      9,
      "F1"
    );
    this.addText(
      `Blue Dollar Rate: ARS ${metadata.blueDollarRate.toLocaleString()}`,
      boxLeft,
      boxTop - 32,
      9,
      "F1"
    );
    this.addText(
      `Generated: ${new Date(metadata.generatedAt).toLocaleString("es-AR")}`,
      boxLeft,
      boxTop - 46,
      9,
      "F1"
    );

    // Source breakdown (right side of box)
    const boxRight = this.margin + this.contentWidth / 2;
    this.addText("BY SOURCE:", boxRight, boxTop, 9, "F2");
    let sourceY = boxTop - 14;
    const topSources = Object.entries(metadata.bySource)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4);
    for (const [source, count] of topSources) {
      this.addText(`${source}: ${count}`, boxRight, sourceY, 8, "F1");
      sourceY -= 12;
    }

    this.yPosition -= 100;

    // Listings Section
    this.yPosition -= 15;
    this.addText("AUCTION LISTINGS", this.margin, this.yPosition, 14, "F2");
    this.yPosition -= 20;

    // Table Header
    const colWidths = {
      title: 180,
      category: 70,
      price: 80,
      discount: 60,
      ends: 80,
      source: 70,
    };

    const headerY = this.yPosition;
    this.addRect(this.margin, headerY - 15, this.contentWidth, 18, true);

    let xPos = this.margin + 5;
    this.addText("Title", xPos, headerY - 10, 8, "F2");
    xPos += colWidths.title;
    this.addText("Category", xPos, headerY - 10, 8, "F2");
    xPos += colWidths.category;
    this.addText("Price USD", xPos, headerY - 10, 8, "F2");
    xPos += colWidths.price;
    this.addText("Discount", xPos, headerY - 10, 8, "F2");
    xPos += colWidths.discount;
    this.addText("Ends", xPos, headerY - 10, 8, "F2");
    xPos += colWidths.ends;
    this.addText("Source", xPos, headerY - 10, 8, "F2");

    this.yPosition -= 20;

    // Table Rows
    for (let i = 0; i < listings.length; i++) {
      this.checkPageBreak(25);

      const listing = listings[i];
      const rowY = this.yPosition;

      // Alternating row background
      if (i % 2 === 0) {
        this.addRect(this.margin, rowY - 12, this.contentWidth, 15, true);
      }

      xPos = this.margin + 5;

      // Title (truncated)
      this.addText(this.truncateText(listing.title, 35), xPos, rowY - 8, 8, "F1");
      xPos += colWidths.title;

      // Category
      this.addText(listing.category || "-", xPos, rowY - 8, 8, "F1");
      xPos += colWidths.category;

      // Price USD
      this.addText(
        `$${listing.base_price_usd?.toLocaleString("en-US", { maximumFractionDigits: 0 }) || "-"}`,
        xPos,
        rowY - 8,
        8,
        "F1"
      );
      xPos += colWidths.price;

      // Discount
      const discount = listing.market_data?.discount_percent;
      this.addText(discount ? `${discount.toFixed(1)}%` : "-", xPos, rowY - 8, 8, "F1");
      xPos += colWidths.discount;

      // Ends date
      const endsDate = new Date(listing.ends_at);
      this.addText(
        endsDate.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" }),
        xPos,
        rowY - 8,
        8,
        "F1"
      );
      xPos += colWidths.ends;

      // Source
      this.addText(this.truncateText(listing.source, 12), xPos, rowY - 8, 8, "F1");

      this.yPosition -= 15;
    }

    // Footer on last page
    this.yPosition = this.margin + 30;
    this.addLine(this.margin, this.yPosition, this.pageWidth - this.margin, this.yPosition);
    this.yPosition -= 15;
    this.addText(
      "subasto.com.ar - Argentine Auction Intelligence",
      this.margin,
      this.yPosition,
      8,
      "F1"
    );
    this.addText(
      `Page ${this.pages.length + 1}`,
      this.pageWidth - this.margin - 40,
      this.yPosition,
      8,
      "F1"
    );

    // Finalize last page
    this.startNewPage();

    // Build PDF structure
    return this.buildPDF();
  }

  private buildPDF(): Buffer {
    const offsets: number[] = [];
    let content = "%PDF-1.4\n%\xE2\xE3\xCF\xD3\n";

    // Object 1: Catalog
    offsets.push(content.length);
    content += "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n";

    // Object 2: Pages
    offsets.push(content.length);
    const pageRefs = this.pages.map((id) => `${id} 0 R`).join(" ");
    content += `2 0 obj\n<< /Type /Pages /Kids [${pageRefs}] /Count ${this.pages.length} >>\nendobj\n`;

    // Object 3: Helvetica font
    offsets.push(content.length);
    content += "3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n";

    // Object 4: Helvetica Bold font
    offsets.push(content.length);
    content += "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n";

    // Add all other objects
    for (let i = 0; i < this.objects.length; i++) {
      offsets.push(content.length);
      content += `${i + 5} 0 obj\n${this.objects[i]}\nendobj\n`;
    }

    // Cross-reference table
    const xrefOffset = content.length;
    content += "xref\n";
    content += `0 ${offsets.length + 1}\n`;
    content += "0000000000 65535 f \n";
    for (const offset of offsets) {
      content += offset.toString().padStart(10, "0") + " 00000 n \n";
    }

    // Trailer
    content += "trailer\n";
    content += `<< /Size ${offsets.length + 1} /Root 1 0 R >>\n`;
    content += "startxref\n";
    content += `${xrefOffset}\n`;
    content += "%%EOF";

    return Buffer.from(content, "binary");
  }
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
      price: PDF_EXPORT_PRICE,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
      docs: "/api/v1/price",
      format: "PDF",
      description: "Generate professional PDF report with auction data",
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
      notes: [
        "PDF reports are limited to 100 listings per page for readability",
        "Use templates for pre-formatted professional reports",
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
  const verification = await verifyUSDCPayment(txHash, PDF_EXPORT_PRICE);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment verification failed",
      message: verification.error,
      required: PDF_EXPORT_PRICE,
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
    let reportTitle = "Auction Report";
    let reportDescription = `Complete listing export - ${new Date().toLocaleDateString("es-AR")}`;

    if (template) {
      const templateResult = applyReportTemplate(listings, template);
      listings = templateResult.listings;
      reportTitle = templateResult.title;
      reportDescription = templateResult.description;
    }

    // Apply filters
    listings = applyFilters(listings, filters);

    // Sort (default by discount for PDF reports)
    const sortBy = options.sortBy || "discount_percent";
    const sortOrder = options.sortOrder || "desc";
    listings = sortListings(listings, sortBy, sortOrder);

    // Limit (default 100 for PDF readability)
    const limit = options.limit || 100;
    listings = listings.slice(0, limit);

    // Generate PDF
    const generator = new PDFGenerator();
    const pdf = generator.generate(listings, {
      title: reportTitle,
      description: reportDescription,
      totalCount: data.total_count,
      filteredCount: listings.length,
      blueDollarRate: data.blue_dollar_rate,
      generatedAt: data.generated_at,
      bySource: data.by_source,
      template,
    });

    // Generate filename
    const timestamp = new Date().toISOString().split("T")[0];
    const filename = template
      ? `subasto_${template}_${timestamp}.pdf`
      : `subasto_report_${timestamp}.pdf`;

    // Set headers for file download
    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
    res.setHeader("X-Export-Count", listings.length.toString());
    res.setHeader("X-Report-Title", reportTitle);
    res.setHeader("X-Payment-Tx", txHash);
    res.setHeader("X-Payment-Amount", verification.amount?.toString() || "");

    return res.status(200).send(pdf);
  } catch (error) {
    console.error("PDF export error:", error);
    return res.status(500).json({
      error: "Export failed",
      message: "Failed to generate PDF report",
    });
  }
}
