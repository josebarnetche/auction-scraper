/**
 * POST /api/v1/referral/track
 *
 * Track a referral click when someone visits with ?ref=CODE
 * Called by the frontend referral.js script.
 *
 * Request body:
 * {
 *   "code": "ABC123",      // Referral code from URL
 *   "userId": "uuid-...",  // User's localStorage ID
 *   "page": "/",           // Optional: page URL
 *   "userAgent": "..."     // Optional: for analytics
 * }
 *
 * Response:
 * {
 *   "success": true,
 *   "attributed": true,
 *   "referrer": "MyBrand",
 *   "expiresIn": "30 days"
 * }
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import {
  recordReferralClick,
  getAffiliateByCode,
  REFERRAL_CONFIG,
} from "../../lib/referral-tracker.js";

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
      message: "Use POST to track referral clicks",
    });
  }

  try {
    const { code, userId, page, userAgent } = req.body || {};

    // Validate required fields
    if (!code || typeof code !== "string") {
      return res.status(400).json({
        error: "Missing referral code",
        success: false,
      });
    }

    if (!userId || typeof userId !== "string") {
      return res.status(400).json({
        error: "Missing user ID",
        success: false,
      });
    }

    // Validate code exists
    const affiliate = getAffiliateByCode(code);
    if (!affiliate) {
      return res.status(200).json({
        success: false,
        error: "Invalid referral code",
        attributed: false,
      });
    }

    // Get IP from headers (for analytics, not shown publicly)
    const ip = (req.headers["x-forwarded-for"] as string)?.split(",")[0] ||
               req.headers["x-real-ip"] as string ||
               undefined;

    // Record the click
    const result = recordReferralClick(code, userId, {
      ip,
      userAgent,
      page,
    });

    if (!result.success) {
      return res.status(200).json({
        success: false,
        error: result.error,
        attributed: false,
      });
    }

    return res.status(200).json({
      success: true,
      attributed: true,
      referrer: affiliate.displayName || `${affiliate.wallet.slice(0, 6)}...`,
      expiresIn: `${REFERRAL_CONFIG.ATTRIBUTION_WINDOW_DAYS} days`,
      message: "Referral tracked! If you make API purchases, your referrer earns 10%.",
    });
  } catch (error) {
    console.error("Referral tracking error:", error);
    return res.status(500).json({
      error: "Internal error",
      success: false,
    });
  }
}
