import type { VercelRequest, VercelResponse } from "@vercel/node";
import { PRICES, PAYMENT_WALLET, USDC_ADDRESS, BASE_CHAIN_ID } from "../lib/config.js";

export default function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Cache-Control", "s-maxage=60, stale-while-revalidate");

  return res.status(200).json({
    name: "Auction Scraper API",
    version: "1.0.0",
    pricing: {
      currency: "USDC",
      network: "Base",
      chain_id: BASE_CHAIN_ID,
      endpoints: {
        "/api/v1/auctions": {
          price: PRICES.auctions,
          description: "All 864+ auction listings from 15 sources",
        },
        "/api/v1/opportunities": {
          price: PRICES.opportunities,
          description: "Hot deals with 40%+ discount vs market price",
        },
        "/api/v1/premium": {
          price: PRICES.premium,
          description: "Curated premium picks with analysis",
        },
      },
    },
    payment: {
      wallet: PAYMENT_WALLET,
      token: USDC_ADDRESS,
      network: "Base Mainnet",
      instructions: [
        "1. Send USDC to the wallet address above on Base network",
        "2. Call the endpoint with ?tx=YOUR_TX_HASH",
        "3. Transaction must be within the last hour",
        "4. Each tx hash can only be used once",
      ],
    },
    example: {
      request: "GET /api/v1/auctions?tx=0x123...abc",
      response: "{ listings: [...], count: 864 }",
    },
  });
}
