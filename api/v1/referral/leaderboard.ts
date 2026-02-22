/**
 * GET /api/v1/referral/leaderboard
 *
 * Get the top affiliates leaderboard.
 * Public endpoint - shows anonymized stats.
 *
 * Query params:
 * - limit: Number of results (default 10, max 50)
 *
 * Response:
 * {
 *   "success": true,
 *   "leaderboard": [
 *     { "rank": 1, "displayName": "CryptoKing", "conversions": 50, "earnings": 125.50 },
 *     ...
 *   ],
 *   "programStats": { ... }
 * }
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import {
  getLeaderboard,
  getProgramStats,
  REFERRAL_CONFIG,
} from "../../lib/referral-tracker.js";

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
      message: "Use GET to view the leaderboard",
    });
  }

  try {
    // Parse limit
    let limit = parseInt(req.query.limit as string) || 10;
    limit = Math.min(Math.max(limit, 1), 50); // Clamp between 1-50

    // Get leaderboard
    const leaderboard = getLeaderboard(limit);

    // Get overall program stats
    const programStats = getProgramStats();

    return res.status(200).json({
      success: true,
      leaderboard: leaderboard.map(entry => ({
        rank: entry.rank,
        displayName: entry.displayName,
        conversions: entry.conversions,
        earnings: {
          amount: entry.earnings,
          formatted: `$${entry.earnings.toFixed(2)}`,
        },
      })),
      programStats: {
        totalAffiliates: programStats.totalAffiliates,
        totalReferrals: programStats.totalConversions,
        totalCommissionsPaid: {
          amount: programStats.totalCommissionsPaid,
          formatted: `$${programStats.totalCommissionsPaid.toFixed(2)} USDC`,
        },
        averageConversionRate: `${programStats.averageConversionRate.toFixed(1)}%`,
      },
      program: {
        commissionRate: `${REFERRAL_CONFIG.COMMISSION_RATE * 100}%`,
        minPayout: `$${REFERRAL_CONFIG.MIN_PAYOUT} USDC`,
        attributionWindow: `${REFERRAL_CONFIG.ATTRIBUTION_WINDOW_DAYS} days`,
        joinUrl: "/api/v1/referral/register",
      },
    });
  } catch (error) {
    console.error("Leaderboard error:", error);
    return res.status(500).json({
      error: "Internal error",
      message: "Failed to load leaderboard",
    });
  }
}
