import type { VercelRequest, VercelResponse } from "@vercel/node";
import { verifyUSDCPayment } from "../../src/api-lib/verify-payment.js";
import { PRICES } from "../../src/api-lib/config.js";
import * as fs from "fs";
import * as path from "path";

// Used tx hashes (in-memory for now, should use KV store in production)
const usedTxHashes = new Set<string>();

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  
  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  const txHash = req.query.tx as string;

  if (!txHash) {
    return res.status(402).json({
      error: "Payment Required",
      message: "Include ?tx=YOUR_TX_HASH after sending USDC payment",
      required_amount: PRICES.auctions,
      payment_info: "/api/v1/price",
    });
  }

  // Check for replay
  if (usedTxHashes.has(txHash.toLowerCase())) {
    return res.status(400).json({
      error: "Transaction Already Used",
      message: "Each transaction hash can only be used once",
    });
  }

  // Verify payment
  const verification = await verifyUSDCPayment(txHash, PRICES.auctions);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment Verification Failed",
      message: verification.error,
      required_amount: PRICES.auctions,
    });
  }

  // Mark tx as used
  usedTxHashes.add(txHash.toLowerCase());

  // Load auction data
  try {
    const listingsPath = path.join(process.cwd(), "site", "api", "listings.json");
    const statsPath = path.join(process.cwd(), "site", "api", "stats.json");
    
    let listings: any[] = [];
    let stats: any = {};

    if (fs.existsSync(listingsPath)) {
      const data = JSON.parse(fs.readFileSync(listingsPath, "utf-8"));
      listings = data.listings || data;
    }

    if (fs.existsSync(statsPath)) {
      stats = JSON.parse(fs.readFileSync(statsPath, "utf-8"));
    }

    // Group by source
    const bySource: Record<string, number> = {};
    for (const listing of listings) {
      const source = listing.source || "unknown";
      bySource[source] = (bySource[source] || 0) + 1;
    }

    return res.status(200).json({
      success: true,
      payment: {
        tx: txHash,
        amount: verification.amount,
        from: verification.from,
      },
      data: {
        total_count: listings.length,
        by_source: bySource,
        generated_at: new Date().toISOString(),
        listings: listings,
      },
    });
  } catch (error) {
    console.error("Error loading auction data:", error);
    return res.status(500).json({
      error: "Internal Server Error",
      message: "Failed to load auction data",
    });
  }
}
