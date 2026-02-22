/**
 * POST /api/v1/referral/register
 *
 * Register as an affiliate to get a referral code.
 * Requires wallet address for payout.
 *
 * Request body:
 * {
 *   "wallet": "0x...",           // Required: wallet address for payouts
 *   "displayName": "MyBrand"     // Optional: display name for leaderboard
 * }
 *
 * Response:
 * {
 *   "success": true,
 *   "affiliate": {
 *     "wallet": "0x...",
 *     "referralCode": "ABC123",
 *     "referralUrl": "https://subasto.com.ar?ref=ABC123",
 *     "displayName": "MyBrand",
 *     "commissionRate": "10%",
 *     "minPayout": 1.00
 *   }
 * }
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import {
  registerAffiliate,
  getAffiliate,
  REFERRAL_CONFIG,
} from "../../lib/referral-tracker.js";

const BASE_URL = "https://subasto.com.ar";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({
      error: "Method not allowed",
      message: "Use POST to register as an affiliate",
    });
  }

  try {
    const { wallet, displayName } = req.body || {};

    // Validate wallet address
    if (!wallet || typeof wallet !== "string") {
      return res.status(400).json({
        error: "Missing wallet address",
        message: "Provide a wallet address to receive commission payouts",
      });
    }

    // Basic wallet format validation (Ethereum-style)
    if (!/^0x[a-fA-F0-9]{40}$/.test(wallet)) {
      return res.status(400).json({
        error: "Invalid wallet address",
        message: "Wallet must be a valid Ethereum address (0x...)",
      });
    }

    // Validate display name if provided
    if (displayName && typeof displayName === "string") {
      if (displayName.length > 30) {
        return res.status(400).json({
          error: "Display name too long",
          message: "Display name must be 30 characters or less",
        });
      }
    }

    // Check if already registered
    const existing = getAffiliate(wallet);
    if (existing) {
      return res.status(200).json({
        success: true,
        message: "Already registered",
        affiliate: {
          wallet: existing.wallet,
          referralCode: existing.referralCode,
          referralUrl: `${BASE_URL}?ref=${existing.referralCode}`,
          displayName: existing.displayName || null,
          commissionRate: `${REFERRAL_CONFIG.COMMISSION_RATE * 100}%`,
          minPayout: REFERRAL_CONFIG.MIN_PAYOUT,
          createdAt: new Date(existing.createdAt).toISOString(),
        },
      });
    }

    // Register new affiliate
    const result = registerAffiliate(wallet, displayName);

    if (!result.success || !result.affiliate) {
      return res.status(500).json({
        error: "Registration failed",
        message: result.error || "Unable to create affiliate account",
      });
    }

    const affiliate = result.affiliate;

    return res.status(201).json({
      success: true,
      message: "Welcome to the Subasto affiliate program!",
      affiliate: {
        wallet: affiliate.wallet,
        referralCode: affiliate.referralCode,
        referralUrl: `${BASE_URL}?ref=${affiliate.referralCode}`,
        displayName: affiliate.displayName || null,
        commissionRate: `${REFERRAL_CONFIG.COMMISSION_RATE * 100}%`,
        minPayout: REFERRAL_CONFIG.MIN_PAYOUT,
        createdAt: new Date(affiliate.createdAt).toISOString(),
      },
      howItWorks: {
        step1: "Share your referral link with others",
        step2: "When they make API payments, you earn 10% commission",
        step3: `Request payout when you reach $${REFERRAL_CONFIG.MIN_PAYOUT} USDC`,
        step4: "Receive USDC directly to your wallet on Base network",
      },
      terms: {
        attributionWindow: `${REFERRAL_CONFIG.ATTRIBUTION_WINDOW_DAYS} days`,
        oneReferralPerWallet: true,
        manualReviewThreshold: `$${REFERRAL_CONFIG.MANUAL_REVIEW_THRESHOLD} USDC`,
      },
    });
  } catch (error) {
    console.error("Affiliate registration error:", error);
    return res.status(500).json({
      error: "Internal error",
      message: "Failed to process registration",
    });
  }
}
