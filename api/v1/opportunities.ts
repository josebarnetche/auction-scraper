import type { VercelRequest, VercelResponse } from "@vercel/node";
import { readFileSync } from "fs";
import { join } from "path";
import { verifyUSDCPayment } from "../lib/verify-payment.js";
import { PRICES, PAYMENT_WALLET } from "../lib/config.js";

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
      price: PRICES.opportunities,
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

  const verification = await verifyUSDCPayment(txHash, PRICES.opportunities);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment verification failed",
      message: verification.error,
      required: PRICES.opportunities,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
    });
  }

  usedTxHashes.add(txHash.toLowerCase());

  try {
    const opportunitiesPath = join(process.cwd(), "site", "api", "opportunities.json");
    const data = JSON.parse(readFileSync(opportunitiesPath, "utf-8"));

    // Filter to only high-discount opportunities
    const hotDeals = data.opportunities?.filter(
      (o: any) => o.discount_percent >= 40
    ) || [];

    return res.status(200).json({
      success: true,
      payment: {
        tx: txHash,
        amount: verification.amount,
        from: verification.from,
      },
      data: {
        count: hotDeals.length,
        opportunities: hotDeals,
        generated_at: data.generated_at,
      },
    });
  } catch (error) {
    console.error("Error reading opportunities:", error);
    return res.status(500).json({
      error: "Internal error",
      message: "Failed to load opportunities data",
    });
  }
}
