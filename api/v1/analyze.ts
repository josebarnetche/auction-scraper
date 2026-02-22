import type { VercelRequest, VercelResponse } from "@vercel/node";
import { readFileSync } from "fs";
import { join } from "path";
import { verifyUSDCPayment } from "../lib/verify-payment.js";
import { PRICES, PAYMENT_WALLET } from "../lib/config.js";
import Anthropic from "@anthropic-ai/sdk";

// Rate limiting: track used transaction hashes
const usedTxHashes = new Set<string>();

// Analysis price
const ANALYSIS_PRICE = 0.02; // $0.02 USDC per analysis

// Listing interface
interface Listing {
  id: string;
  title: string;
  description?: string;
  base_price: number;
  currency: string;
  category?: string;
  source?: string;
  source_url?: string;
  location?: { province?: string; city?: string };
  ends_at?: string;
  images?: string[];
}

// Analysis result interface
interface OpportunityAnalysis {
  listing_id: string;
  analyzed_at: string;
  specs: {
    brand: string | null;
    model: string | null;
    year: number | null;
    condition: string;
    condition_notes: string;
    quantity: number;
    key_features: string[];
  };
  market_value: {
    min_usd: number;
    max_usd: number;
    typical_usd: number;
    confidence: number;
    reasoning: string;
    comparable_items: Array<{ description: string; price_usd: number; source: string }>;
  };
  profit_analysis: {
    buy_price_usd: number;
    estimated_resale_usd: number;
    gross_profit_usd: number;
    profit_margin_percent: number;
    estimated_costs_usd: number;
    net_profit_usd: number;
    time_to_sell_days: number;
    liquidity: string;
    reasoning: string;
  };
  risk_assessment: {
    overall_risk: string;
    risk_score: number;
    legal_concerns: string[];
    condition_concerns: string[];
    location_concerns: string[];
    hidden_costs: string[];
    red_flags: string[];
    mitigation_suggestions: string[];
  };
  bid_strategy: {
    max_bid_usd: number;
    opening_bid_usd: number;
    walk_away_price_usd: number;
    timing_recommendation: string;
    competition_level: string;
    reasoning: string;
  };
  opportunity_score: number;
  action_recommendation: "BUY" | "WATCH" | "SKIP";
  one_liner: string;
  detailed_reasoning: string;
}

// Blue dollar rate (should be fetched dynamically in production)
const BLUE_DOLLAR_RATE = 1430.0;

// Analysis prompt
const ANALYSIS_PROMPT = `You are an expert auction analyst for Argentine auctions. Analyze this listing and provide ACTIONABLE INTELLIGENCE.

## Listing Information
Title: {title}
Description: {description}
Base Price: {price} {currency} (~USD ${"{price_usd}"})
Category: {category}
Source: {source}
Location: {location}
Auction End: {end_date}

## Return ONLY valid JSON with this structure:
{
  "specs": {
    "brand": "brand or null",
    "model": "model or null",
    "year": year or null,
    "condition": "new|like_new|good|fair|poor|unknown",
    "condition_notes": "observations",
    "quantity": 1,
    "key_features": ["feature1"]
  },
  "market_value": {
    "min_usd": number,
    "max_usd": number,
    "typical_usd": number,
    "confidence": 0.0-1.0,
    "reasoning": "valuation explanation",
    "comparable_items": [{"description": "item", "price_usd": 0, "source": "where"}]
  },
  "profit_analysis": {
    "buy_price_usd": number,
    "estimated_resale_usd": number,
    "gross_profit_usd": number,
    "profit_margin_percent": number,
    "estimated_costs_usd": number,
    "net_profit_usd": number,
    "time_to_sell_days": number,
    "liquidity": "high|medium|low",
    "reasoning": "profit explanation"
  },
  "risk_assessment": {
    "overall_risk": "low|medium|high",
    "risk_score": 1-10,
    "legal_concerns": [],
    "condition_concerns": [],
    "location_concerns": [],
    "hidden_costs": [],
    "red_flags": [],
    "mitigation_suggestions": []
  },
  "bid_strategy": {
    "max_bid_usd": number,
    "opening_bid_usd": number,
    "walk_away_price_usd": number,
    "timing_recommendation": "early|late|snipe",
    "competition_level": "low|medium|high",
    "reasoning": "strategy explanation"
  },
  "opportunity_score": 1-10,
  "action_recommendation": "BUY|WATCH|SKIP",
  "one_liner": "one sentence summary",
  "detailed_reasoning": "2-3 sentences"
}

## Scoring: 9-10=Exceptional, 7-8=Very Good, 5-6=Good, 3-4=Marginal, 1-2=Skip
## Argentine context: Judicial auctions 40-70% below market, consider 21% IVA, transport costs`;

// Find listing by ID
function findListing(listingId: string): Listing | null {
  try {
    // Try listings.json first
    const listingsPath = join(process.cwd(), "site", "api", "listings.json");
    const data = JSON.parse(readFileSync(listingsPath, "utf-8"));

    // Check top_opportunities
    const topOpp = data.top_opportunities?.find((l: any) => l.id === listingId);
    if (topOpp) {
      return {
        id: topOpp.id,
        title: topOpp.title,
        description: topOpp.description || "",
        base_price: topOpp.base_price,
        currency: topOpp.currency,
        category: topOpp.category,
        source: topOpp.source,
        source_url: topOpp.source_url,
        images: topOpp.images || [],
      };
    }

    // Check lots
    const lot = data.lots?.find((l: any) => l.lot_id === listingId);
    if (lot) {
      return {
        id: lot.lot_id,
        title: lot.title,
        description: lot.description || "",
        base_price: lot.base_price,
        currency: lot.currency,
        category: "lot",
        source: lot.auction_source,
        source_url: lot.auction_url,
        images: lot.images || [],
      };
    }

    // Try hot_list.json
    const hotListPath = join(process.cwd(), "data", "hot_list.json");
    const hotData = JSON.parse(readFileSync(hotListPath, "utf-8"));
    const hotItem = hotData.items?.find((i: any) => i.id === listingId);
    if (hotItem) {
      return {
        id: hotItem.id,
        title: hotItem.title,
        description: "",
        base_price: 0, // Would need to parse from price string
        currency: "ARS",
        category: hotItem.category,
        source: hotItem.source,
        source_url: hotItem.source_url,
      };
    }

    return null;
  } catch (error) {
    console.error("Error finding listing:", error);
    return null;
  }
}

// Analyze listing with Claude
async function analyzeWithClaude(listing: Listing): Promise<OpportunityAnalysis | null> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error("ANTHROPIC_API_KEY not configured");
  }

  const client = new Anthropic({ apiKey });

  // Calculate USD price
  const priceUsd =
    listing.currency === "USD"
      ? listing.base_price
      : listing.base_price / BLUE_DOLLAR_RATE;

  // Build prompt
  const location = listing.location
    ? `${listing.location.city || ""}, ${listing.location.province || ""}`
    : "Not specified";

  const prompt = ANALYSIS_PROMPT
    .replace("{title}", listing.title)
    .replace("{description}", listing.description || "(no description)")
    .replace("{price}", listing.base_price.toLocaleString())
    .replace("{currency}", listing.currency)
    .replace("{price_usd}", priceUsd.toFixed(2))
    .replace("{category}", listing.category || "other")
    .replace("{source}", listing.source || "unknown")
    .replace("{location}", location)
    .replace("{end_date}", listing.ends_at || "Not specified");

  // Build content with images if available
  const content: Anthropic.MessageParam["content"] = [];

  // Add up to 2 images for visual analysis
  if (listing.images && listing.images.length > 0) {
    for (const imgUrl of listing.images.slice(0, 2)) {
      try {
        const response = await fetch(imgUrl);
        if (response.ok) {
          const buffer = await response.arrayBuffer();
          const base64 = Buffer.from(buffer).toString("base64");
          const contentType = response.headers.get("content-type") || "image/jpeg";

          if (contentType.includes("image")) {
            content.push({
              type: "image",
              source: {
                type: "base64",
                media_type: contentType as "image/jpeg" | "image/png" | "image/gif" | "image/webp",
                data: base64,
              },
            });
          }
        }
      } catch (e) {
        // Skip failed images
      }
    }
  }

  content.push({ type: "text", text: prompt });

  try {
    const response = await client.messages.create({
      model: "claude-3-5-haiku-20241022",
      max_tokens: 2000,
      messages: [{ role: "user", content }],
    });

    // Extract response text
    const textBlock = response.content.find((b) => b.type === "text");
    if (!textBlock || textBlock.type !== "text") {
      return null;
    }

    let text = textBlock.text.trim();

    // Handle markdown code blocks
    if (text.startsWith("```")) {
      text = text.split("```")[1];
      if (text.startsWith("json")) {
        text = text.substring(4);
      }
      text = text.trim();
    }

    const result = JSON.parse(text);

    return {
      listing_id: listing.id,
      analyzed_at: new Date().toISOString(),
      ...result,
    };
  } catch (error) {
    console.error("Claude analysis error:", error);
    return null;
  }
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS
  res.setHeader("Access-Control-Allow-Origin", "*");

  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    return res.status(200).end();
  }

  // Get listing ID
  const listingId = (req.query.id as string) || (req.body?.id as string);

  if (!listingId) {
    return res.status(400).json({
      error: "Missing listing ID",
      message: "Provide ?id=LISTING_ID or {\"id\": \"LISTING_ID\"} in body",
      example: "/api/v1/analyze?id=cordoba:26092&tx=0x...",
    });
  }

  // Verify payment
  const txHash = (req.query.tx as string) || (req.body?.tx as string);

  if (!txHash) {
    return res.status(402).json({
      error: "Payment required",
      message: "AI analysis costs $0.02 USDC per listing",
      price: ANALYSIS_PRICE,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
      instructions: {
        step1: `Send $${ANALYSIS_PRICE} USDC to ${PAYMENT_WALLET} on Base network`,
        step2: "Include the transaction hash as ?tx=0x...",
        step3: "Analysis will be returned immediately",
      },
    });
  }

  // Check for replay
  if (usedTxHashes.has(txHash.toLowerCase())) {
    return res.status(400).json({
      error: "Transaction already used",
      message: "Each transaction can only be used for one analysis",
    });
  }

  // Verify USDC payment
  const verification = await verifyUSDCPayment(txHash, ANALYSIS_PRICE);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment verification failed",
      message: verification.error,
      required: ANALYSIS_PRICE,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
    });
  }

  // Mark tx as used
  usedTxHashes.add(txHash.toLowerCase());

  // Find the listing
  const listing = findListing(listingId);

  if (!listing) {
    return res.status(404).json({
      error: "Listing not found",
      message: `No listing found with ID: ${listingId}`,
      suggestion: "Check the listing ID in /api/v1/auctions or site/api/listings.json",
    });
  }

  // Perform AI analysis
  try {
    const analysis = await analyzeWithClaude(listing);

    if (!analysis) {
      return res.status(500).json({
        error: "Analysis failed",
        message: "AI analysis could not be completed. Payment has been accepted.",
        listing_id: listingId,
      });
    }

    return res.status(200).json({
      success: true,
      payment: {
        tx: txHash,
        amount: verification.amount,
        from: verification.from,
      },
      analysis: {
        ...analysis,
        source_url: listing.source_url,
      },
    });
  } catch (error) {
    console.error("Analysis error:", error);
    return res.status(500).json({
      error: "Internal error",
      message: error instanceof Error ? error.message : "Unknown error occurred",
    });
  }
}
