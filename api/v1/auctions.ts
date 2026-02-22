import type { VercelRequest, VercelResponse } from "@vercel/node";
import { readFileSync } from "fs";
import { join } from "path";
import { verifyUSDCPayment } from "../lib/verify-payment.js";
import { PRICES, PAYMENT_WALLET } from "../lib/config.js";

// Simple in-memory cache for used tx hashes (resets on cold start)
// For production, use Vercel KV or similar
const usedTxHashes = new Set<string>();

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    return res.status(200).end();
  }

  const txHash = req.query.tx as string;

  if (!txHash) {
    return res.status(402).json({
      error: "Payment required",
      message: "Include ?tx=YOUR_TX_HASH with USDC payment on Base",
      price: PRICES.auctions,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
      docs: "/api/v1/price",
    });
  }

  // Check if tx already used (anti-replay)
  if (usedTxHashes.has(txHash.toLowerCase())) {
    return res.status(400).json({
      error: "Transaction already used",
      message: "Each transaction can only be used once",
    });
  }

  // Verify payment on-chain
  const verification = await verifyUSDCPayment(txHash, PRICES.auctions);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment verification failed",
      message: verification.error,
      required: PRICES.auctions,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
    });
  }

  // Mark tx as used
  usedTxHashes.add(txHash.toLowerCase());

  // Load and return listings data
  try {
    const listingsPath = join(process.cwd(), "site", "api", "listings.json");
    const listingsData = JSON.parse(readFileSync(listingsPath, "utf-8"));

    return res.status(200).json({
      success: true,
      payment: {
        tx: txHash,
        amount: verification.amount,
        from: verification.from,
      },
      data: listingsData,
    });
  } catch (error) {
    console.error("Error reading listings:", error);
    return res.status(500).json({
      error: "Internal error",
      message: "Failed to load listings data",
    });
  }
}
