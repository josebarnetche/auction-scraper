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
      required_amount: PRICES.premium,
      payment_info: "/api/v1/price",
    });
  }

  if (usedTxHashes.has(txHash.toLowerCase())) {
    return res.status(400).json({
      error: "Transaction Already Used",
      message: "Each transaction hash can only be used once",
    });
  }

  const verification = await verifyUSDCPayment(txHash, PRICES.premium);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment Verification Failed",
      message: verification.error,
      required_amount: PRICES.premium,
    });
  }

  usedTxHashes.add(txHash.toLowerCase());

  try {
    const hotDealsPath = path.join(process.cwd(), "data", "hot_deals.json");
    const opportunitiesPath = path.join(process.cwd(), "site", "api", "opportunities.json");
    
    let allDeals: any[] = [];

    if (fs.existsSync(hotDealsPath)) {
      const data = JSON.parse(fs.readFileSync(hotDealsPath, "utf-8"));
      allDeals = data.deals || [];
    } else if (fs.existsSync(opportunitiesPath)) {
      const data = JSON.parse(fs.readFileSync(opportunitiesPath, "utf-8"));
      allDeals = data.opportunities || data.deals || data;
    }

    // Get top 12 curated picks (highest score/discount)
    const premiumPicks = allDeals
      .sort((a: any, b: any) => {
        const scoreA = a.score || a.discount_percent || 0;
        const scoreB = b.score || b.discount_percent || 0;
        return scoreB - scoreA;
      })
      .slice(0, 12)
      .map((item: any) => ({
        ...item,
        analysis: {
          recommendation: item.score >= 80 ? "Strong Buy" : item.score >= 60 ? "Buy" : "Consider",
          risk_level: item.category === "vehicles" ? "Medium" : "Low",
          profit_potential: item.profit_potential_usd || null,
        },
      }));

    return res.status(200).json({
      success: true,
      payment: {
        tx: txHash,
        amount: verification.amount,
        from: verification.from,
      },
      data: {
        total_count: premiumPicks.length,
        curated: true,
        generated_at: new Date().toISOString(),
        premium_picks: premiumPicks,
      },
    });
  } catch (error) {
    console.error("Error loading premium data:", error);
    return res.status(500).json({
      error: "Internal Server Error",
      message: "Failed to load premium picks",
    });
  }
}
