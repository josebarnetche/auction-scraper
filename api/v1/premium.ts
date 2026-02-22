import type { VercelRequest, VercelResponse } from "@vercel/node";
import { readFileSync } from "fs";
import { join } from "path";
import { verifyUSDCPayment } from "../../src/api-lib/verify-payment.js";
import { PRICES, PAYMENT_WALLET } from "../../src/api-lib/config.js";

const usedTxHashes = new Set<string>();

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Access-Control-Allow-Origin", "*");

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
      price: PRICES.premium,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
      docs: "/api/v1/price",
    });
  }

  if (usedTxHashes.has(txHash.toLowerCase())) {
    return res.status(400).json({
      error: "Transaction already used",
      message: "Each transaction can only be used once",
    });
  }

  const verification = await verifyUSDCPayment(txHash, PRICES.premium);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment verification failed",
      message: verification.error,
      required: PRICES.premium,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
    });
  }

  usedTxHashes.add(txHash.toLowerCase());

  try {
    const listingsPath = join(process.cwd(), "site", "api", "listings.json");
    const data = JSON.parse(readFileSync(listingsPath, "utf-8"));

    // Get premium picks (is_premium flag or highest discounts)
    const premiumPicks = data.top_opportunities?.filter(
      (o: any) => o.is_premium || o.discount_percent >= 50
    ) || [];

    return res.status(200).json({
      success: true,
      payment: {
        tx: txHash,
        amount: verification.amount,
        from: verification.from,
      },
      data: {
        count: premiumPicks.length,
        premium_picks: premiumPicks,
        blue_dollar_rate: data.blue_dollar_rate,
        generated_at: data.generated_at,
      },
    });
  } catch (error) {
    console.error("Error reading premium data:", error);
    return res.status(500).json({
      error: "Internal error",
      message: "Failed to load premium data",
    });
  }
}
