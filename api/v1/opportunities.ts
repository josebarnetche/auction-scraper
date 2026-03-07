import type { VercelRequest, VercelResponse } from "@vercel/node";
import { verifyUSDCPayment } from "../../src/api-lib/verify-payment.js";
import { PRICES } from "../../src/api-lib/config.js";
import * as fs from "fs";
import * as path from "path";

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
      required_amount: PRICES.opportunities,
      payment_info: "/api/v1/price",
    });
  }

  if (usedTxHashes.has(txHash.toLowerCase())) {
    return res.status(400).json({
      error: "Transaction Already Used",
      message: "Each transaction hash can only be used once",
    });
  }

  const verification = await verifyUSDCPayment(txHash, PRICES.opportunities);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment Verification Failed",
      message: verification.error,
      required_amount: PRICES.opportunities,
    });
  }

  usedTxHashes.add(txHash.toLowerCase());

  try {
    const opportunitiesPath = path.join(process.cwd(), "site", "api", "opportunities.json");
    const hotDealsPath = path.join(process.cwd(), "data", "hot_deals.json");
    
    let opportunities: any[] = [];

    // Try opportunities.json first, then hot_deals.json
    if (fs.existsSync(opportunitiesPath)) {
      const data = JSON.parse(fs.readFileSync(opportunitiesPath, "utf-8"));
      opportunities = data.opportunities || data.deals || data;
    } else if (fs.existsSync(hotDealsPath)) {
      const data = JSON.parse(fs.readFileSync(hotDealsPath, "utf-8"));
      opportunities = data.deals || [];
    }

    // Filter to only 40%+ discount deals
    const hotDeals = opportunities.filter((item: any) => {
      const discount = item.discount_percent || item.discount || 0;
      return discount >= 40;
    });

    return res.status(200).json({
      success: true,
      payment: {
        tx: txHash,
        amount: verification.amount,
        from: verification.from,
      },
      data: {
        total_count: hotDeals.length,
        min_discount: "40%",
        generated_at: new Date().toISOString(),
        opportunities: hotDeals,
      },
    });
  } catch (error) {
    console.error("Error loading opportunities data:", error);
    return res.status(500).json({
      error: "Internal Server Error",
      message: "Failed to load opportunities data",
    });
  }
}
