/**
 * GET /api/v1/referral/stats
 *
 * Get affiliate stats and earnings.
 *
 * Query params:
 * - wallet: Affiliate wallet address (required)
 *
 * Response:
 * {
 *   "success": true,
 *   "affiliate": { ... },
 *   "stats": { ... },
 *   "recentCommissions": [ ... ],
 *   "pendingPayouts": [ ... ]
 * }
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import {
  getAffiliateStats,
  requestPayout,
  REFERRAL_CONFIG,
} from "../../lib/referral-tracker.js";

const BASE_URL = "https://subasto.com.ar";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  // POST = Request payout
  if (req.method === "POST") {
    return handlePayoutRequest(req, res);
  }

  // GET = View stats
  if (req.method !== "GET") {
    return res.status(405).json({
      error: "Method not allowed",
      message: "Use GET to view stats, POST to request payout",
    });
  }

  try {
    const wallet = req.query.wallet as string;

    if (!wallet) {
      return res.status(400).json({
        error: "Missing wallet",
        message: "Provide ?wallet=0x... to view your affiliate stats",
      });
    }

    const stats = getAffiliateStats(wallet);

    if (!stats.affiliate) {
      return res.status(404).json({
        error: "Affiliate not found",
        message: "This wallet is not registered as an affiliate. POST to /api/v1/referral/register to join.",
      });
    }

    const affiliate = stats.affiliate;

    return res.status(200).json({
      success: true,
      affiliate: {
        wallet: affiliate.wallet,
        referralCode: affiliate.referralCode,
        referralUrl: `${BASE_URL}?ref=${affiliate.referralCode}`,
        displayName: affiliate.displayName || null,
        status: affiliate.status,
        createdAt: new Date(affiliate.createdAt).toISOString(),
      },
      stats: {
        totalClicks: affiliate.totalClicks,
        totalConversions: affiliate.totalConversions,
        conversionRate: `${stats.conversionRate.toFixed(1)}%`,
        totalEarnings: {
          amount: affiliate.totalEarnings,
          formatted: `$${affiliate.totalEarnings.toFixed(2)} USDC`,
        },
        pendingPayout: {
          amount: affiliate.pendingPayout,
          formatted: `$${affiliate.pendingPayout.toFixed(2)} USDC`,
          canWithdraw: affiliate.pendingPayout >= REFERRAL_CONFIG.MIN_PAYOUT,
          minPayout: REFERRAL_CONFIG.MIN_PAYOUT,
        },
        paidOut: {
          amount: affiliate.paidOut,
          formatted: `$${affiliate.paidOut.toFixed(2)} USDC`,
        },
      },
      recentCommissions: stats.recentCommissions.map(c => ({
        id: c.id,
        paymentAmount: c.paymentAmount,
        commissionAmount: c.commissionAmount,
        status: c.status,
        timestamp: new Date(c.timestamp).toISOString(),
        refereeWallet: `${c.refereeWallet.slice(0, 6)}...${c.refereeWallet.slice(-4)}`,
      })),
      pendingPayouts: stats.pendingPayouts.map(p => ({
        id: p.id,
        amount: p.amount,
        status: p.status,
        requestedAt: new Date(p.requestedAt).toISOString(),
        txHash: p.txHash || null,
      })),
      actions: {
        requestPayout: {
          method: "POST",
          url: "/api/v1/referral/stats",
          body: { wallet: affiliate.wallet, action: "payout" },
          available: affiliate.pendingPayout >= REFERRAL_CONFIG.MIN_PAYOUT,
        },
      },
    });
  } catch (error) {
    console.error("Affiliate stats error:", error);
    return res.status(500).json({
      error: "Internal error",
      message: "Failed to retrieve stats",
    });
  }
}

async function handlePayoutRequest(req: VercelRequest, res: VercelResponse) {
  try {
    const { wallet, action } = req.body || {};

    if (action !== "payout") {
      return res.status(400).json({
        error: "Invalid action",
        message: "Use action: 'payout' to request a payout",
      });
    }

    if (!wallet) {
      return res.status(400).json({
        error: "Missing wallet",
        message: "Provide your affiliate wallet address",
      });
    }

    const result = requestPayout(wallet);

    if (!result.success) {
      return res.status(400).json({
        error: "Payout request failed",
        message: result.error,
      });
    }

    return res.status(200).json({
      success: true,
      message: "Payout request submitted!",
      payout: {
        id: result.payout!.id,
        amount: result.payout!.amount,
        formatted: `$${result.payout!.amount.toFixed(2)} USDC`,
        status: result.payout!.status,
        requestedAt: new Date(result.payout!.requestedAt).toISOString(),
        estimatedProcessing: result.payout!.status === "processing" ? "24-48 hours" : "Under review",
      },
      note: "Payouts are processed manually and sent to your wallet on Base network.",
    });
  } catch (error) {
    console.error("Payout request error:", error);
    return res.status(500).json({
      error: "Internal error",
      message: "Failed to process payout request",
    });
  }
}
