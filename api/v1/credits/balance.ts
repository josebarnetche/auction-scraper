/**
 * GET /api/v1/credits/balance
 *
 * Check credit balance and subscription status for a wallet.
 *
 * Usage:
 *   GET /api/v1/credits/balance?wallet=0x...
 *
 * Returns:
 *   - Current credit balance
 *   - Subscription tier and expiration
 *   - Usage statistics
 *   - Available features
 *
 * No authentication required - balance is public info tied to wallet address.
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getBalance, canMakeRequest } from "../../lib/credit-manager.js";
import { CREDIT_PACKAGES, SUBSCRIPTION_TIERS, PAYMENT_WALLET } from "../../lib/config.js";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Cache-Control", "no-cache, no-store, must-revalidate");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const wallet = req.query.wallet as string;

  if (!wallet) {
    return res.status(400).json({
      error: "Missing wallet address",
      message: "Include ?wallet=0x... to check balance",
      example: "/api/v1/credits/balance?wallet=0x29E007249b744892a1da17F4289f75cfC871d6Fe",
    });
  }

  // Validate wallet format
  if (!/^0x[a-fA-F0-9]{40}$/.test(wallet)) {
    return res.status(400).json({
      error: "Invalid wallet address",
      message: "Wallet must be a valid Ethereum address (0x + 40 hex chars)",
    });
  }

  // Get balance info
  const balance = getBalance(wallet);
  const accessCheck = canMakeRequest(wallet, "any");

  // Build response
  return res.status(200).json({
    wallet: balance.wallet,

    // Credit balance
    credits: {
      balance: balance.credits,
      never_expire: true,
      value_in_requests: balance.credits, // 1 credit = 1 request
    },

    // Subscription status
    subscription: {
      tier: balance.subscription.tier,
      name: SUBSCRIPTION_TIERS[balance.subscription.tier].name,
      active: balance.subscription.active,
      expires_at: balance.subscription.expiresAt,
      days_remaining: balance.subscription.daysRemaining,
      features: balance.subscription.features,
    },

    // Current access status
    access: {
      can_make_request: accessCheck.allowed,
      access_method: accessCheck.method,
      reason: accessCheck.reason || null,
    },

    // Usage stats
    usage: {
      lifetime_credits_purchased: balance.usage.totalPurchased,
      lifetime_credits_used: balance.usage.totalUsed,
      free_requests_today: balance.usage.freeRequestsToday,
      free_requests_limit: balance.usage.freeRequestsLimit === -1
        ? "unlimited"
        : balance.usage.freeRequestsLimit,
    },

    // Upgrade options
    upgrade_options: {
      buy_credits: {
        description: "Buy credits for pay-per-use access",
        endpoint: "/api/v1/credits/buy",
        packages: Object.entries(CREDIT_PACKAGES).map(([id, pkg]) => ({
          id,
          price: `$${pkg.price}`,
          credits: pkg.credits,
          savings: pkg.savingsPercent > 0 ? `${pkg.savingsPercent}%` : null,
        })),
      },
      subscribe: balance.subscription.tier === "free" ? {
        description: "Subscribe for unlimited access",
        endpoint: "/api/v1/credits/buy",
        tiers: Object.entries(SUBSCRIPTION_TIERS)
          .filter(([id]) => id !== "free")
          .map(([id, tier]) => ({
            id,
            name: tier.name,
            price: `$${tier.price}/month`,
            features: tier.features,
          })),
      } : null,
    },

    // How to add credits
    payment: {
      wallet: PAYMENT_WALLET,
      network: "Base (Chain ID: 8453)",
      token: "USDC",
      instructions: "Send USDC to the wallet, then POST to /api/v1/credits/buy with your tx hash",
    },
  });
}
