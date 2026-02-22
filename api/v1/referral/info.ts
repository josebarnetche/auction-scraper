/**
 * GET /api/v1/referral/info
 *
 * Get referral program information and check if current user has attribution.
 * Used by frontend to show referral status.
 *
 * Query params:
 * - userId: Optional user ID from localStorage to check attribution
 *
 * Response:
 * {
 *   "program": { ... },
 *   "userStatus": { ... }
 * }
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import {
  getAttribution,
  getProgramStats,
  REFERRAL_CONFIG,
} from "../../lib/referral-tracker.js";

const BASE_URL = "https://subasto.com.ar";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "GET") {
    return res.status(405).json({
      error: "Method not allowed",
    });
  }

  try {
    const userId = req.query.userId as string | undefined;

    // Get program stats
    const stats = getProgramStats();

    // Build response
    const response: Record<string, unknown> = {
      program: {
        name: "Subasto Affiliate Program",
        description: "Earn 10% commission on API payments from users you refer",
        commissionRate: `${REFERRAL_CONFIG.COMMISSION_RATE * 100}%`,
        minPayout: {
          amount: REFERRAL_CONFIG.MIN_PAYOUT,
          formatted: `$${REFERRAL_CONFIG.MIN_PAYOUT} USDC`,
        },
        attributionWindow: `${REFERRAL_CONFIG.ATTRIBUTION_WINDOW_DAYS} days`,
        payoutNetwork: "Base (Coinbase L2)",
        payoutToken: "USDC",
        rules: [
          "One referral credit per wallet address",
          "Attribution expires after 30 days",
          `Payouts over $${REFERRAL_CONFIG.MANUAL_REVIEW_THRESHOLD} require manual review`,
          "Referrer must have active affiliate account",
        ],
        endpoints: {
          register: "/api/v1/referral/register",
          stats: "/api/v1/referral/stats",
          leaderboard: "/api/v1/referral/leaderboard",
        },
      },
      stats: {
        totalAffiliates: stats.totalAffiliates,
        totalReferrals: stats.totalConversions,
        totalPaid: {
          amount: stats.totalCommissionsPaid,
          formatted: `$${stats.totalCommissionsPaid.toFixed(2)} USDC`,
        },
      },
    };

    // Check user's referral status if userId provided
    if (userId) {
      const attribution = getAttribution(userId);

      if (attribution) {
        const daysRemaining = Math.ceil(
          (attribution.expiresAt - Date.now()) / (24 * 60 * 60 * 1000)
        );

        response.userStatus = {
          hasReferral: true,
          referrerCode: attribution.referrerCode,
          attributedAt: new Date(attribution.attributedAt).toISOString(),
          expiresAt: new Date(attribution.expiresAt).toISOString(),
          daysRemaining,
          converted: attribution.converted,
          message: attribution.converted
            ? "You were referred! Your referrer earns 10% of your API payments."
            : `You were referred! If you make API purchases in the next ${daysRemaining} days, your referrer earns 10%.`,
        };
      } else {
        response.userStatus = {
          hasReferral: false,
          message: "No active referral. Share your link to earn commissions!",
        };
      }
    }

    // Add call to action
    response.cta = {
      title: "Become an Affiliate",
      description: "Share Subasto with developers and AI agents. Earn USDC on every API payment.",
      action: {
        method: "POST",
        url: "/api/v1/referral/register",
        body: {
          wallet: "YOUR_WALLET_ADDRESS",
          displayName: "Optional display name",
        },
      },
      referralUrlFormat: `${BASE_URL}?ref=YOUR_CODE`,
    };

    return res.status(200).json(response);
  } catch (error) {
    console.error("Referral info error:", error);
    return res.status(500).json({
      error: "Internal error",
      message: "Failed to get referral info",
    });
  }
}
