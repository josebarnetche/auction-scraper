/**
 * POST /api/v1/credits/buy
 *
 * Buy credits or activate a subscription with USDC on Base network.
 *
 * Usage:
 *   POST /api/v1/credits/buy
 *   Body: { "tx": "0x...", "type": "credits" | "subscription" }
 *
 * The endpoint automatically detects the package based on the USDC amount sent:
 *
 * CREDIT PACKAGES:
 *   $1  -> 50 credits (Starter)
 *   $5  -> 300 credits (Popular, 20% bonus)
 *   $10 -> 700 credits (Pro, 40% bonus)
 *   $50 -> 4000 credits (Whale, 60% bonus)
 *
 * SUBSCRIPTIONS (monthly):
 *   $5  -> Pro (unlimited requests + webhooks)
 *   $20 -> Enterprise (priority support + custom filters)
 *
 * Credits never expire. Subscriptions last 30 days.
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { verifyUSDCPayment } from "../../lib/verify-payment.js";
import {
  PAYMENT_WALLET,
  CREDIT_PACKAGES,
  SUBSCRIPTION_TIERS,
} from "../../lib/config.js";
import {
  isTxUsed,
  addCredits,
  activateSubscription,
  getBalance,
  calculateCreditsForAmount,
  getSubscriptionForAmount,
} from "../../lib/credit-manager.js";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  // GET request shows available packages
  if (req.method === "GET") {
    return res.status(200).json({
      name: "Buy Credits or Subscription",
      description: "Send USDC to our wallet, then call this endpoint with the tx hash",
      payment: {
        wallet: PAYMENT_WALLET,
        network: "Base (Chain ID: 8453)",
        token: "USDC",
      },
      credit_packages: Object.entries(CREDIT_PACKAGES).map(([id, pkg]) => ({
        id,
        price: `$${pkg.price} USDC`,
        credits: pkg.credits,
        description: pkg.description,
        savings: pkg.savingsPercent > 0 ? `${pkg.savingsPercent}% bonus` : null,
        cost_per_credit: `$${(pkg.price / pkg.credits).toFixed(4)}`,
      })),
      subscriptions: Object.entries(SUBSCRIPTION_TIERS)
        .filter(([_, tier]) => tier.price > 0)
        .map(([id, tier]) => ({
          id,
          name: tier.name,
          price: `$${tier.price}/month USDC`,
          features: tier.features,
        })),
      usage: {
        method: "POST",
        body: {
          tx: "0x... (your USDC payment transaction hash)",
          type: "credits | subscription (optional, auto-detected from amount)",
        },
      },
      example: {
        request: 'POST /api/v1/credits/buy\n{"tx": "0x123...abc"}',
        response: '{"success": true, "credits_added": 300, "balance": {...}}',
      },
    });
  }

  // POST request processes a purchase
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  // Parse body
  let body: { tx?: string; type?: "credits" | "subscription" };
  try {
    body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
  } catch {
    return res.status(400).json({
      error: "Invalid JSON body",
      expected: { tx: "0x...", type: "credits | subscription" },
    });
  }

  const { tx: txHash, type: purchaseType } = body;

  if (!txHash) {
    return res.status(400).json({
      error: "Missing transaction hash",
      message: 'Include "tx" in request body with your USDC payment tx hash',
      example: { tx: "0x123...abc" },
    });
  }

  // Check if tx already used
  if (isTxUsed(txHash)) {
    return res.status(400).json({
      error: "Transaction already used",
      message: "Each transaction can only be used once. Send a new payment for more credits.",
    });
  }

  // Verify the payment on-chain (minimum $1 for any purchase)
  const verification = await verifyUSDCPayment(txHash, 1.0);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment verification failed",
      message: verification.error,
      minimum_amount: "$1 USDC",
      wallet: PAYMENT_WALLET,
    });
  }

  const amountPaid = verification.amount!;
  const fromWallet = verification.from!;

  // Determine what was purchased based on amount
  const subscriptionMatch = getSubscriptionForAmount(amountPaid);
  const creditMatch = calculateCreditsForAmount(amountPaid);

  // If type is specified, respect it; otherwise auto-detect
  let result;

  if (purchaseType === "subscription" && subscriptionMatch) {
    // Activate subscription
    const account = activateSubscription(
      fromWallet,
      txHash,
      subscriptionMatch.tier,
      amountPaid
    );

    result = {
      success: true,
      purchase_type: "subscription",
      subscription: {
        tier: subscriptionMatch.tier,
        name: subscriptionMatch.name,
        price: `$${subscriptionMatch.price} USDC`,
        duration: "30 days",
        activated_at: new Date().toISOString(),
        expires_at: new Date(account.subscriptionExpiresAt!).toISOString(),
      },
      balance: getBalance(fromWallet),
    };
  } else if (subscriptionMatch && !purchaseType) {
    // Exact subscription amount - ask user to clarify
    return res.status(200).json({
      clarification_needed: true,
      message: `$${amountPaid} matches both a subscription and credit package. Please specify type.`,
      options: {
        subscription: {
          tier: subscriptionMatch.tier,
          description: `${subscriptionMatch.name} - 30 days unlimited access`,
          how_to_activate: 'POST with {"tx": "' + txHash + '", "type": "subscription"}',
        },
        credits: {
          amount: creditMatch?.credits || 0,
          description: `${creditMatch?.credits || 0} credits`,
          how_to_activate: 'POST with {"tx": "' + txHash + '", "type": "credits"}',
        },
      },
      tx: txHash,
      amount_paid: amountPaid,
    });
  } else if (creditMatch) {
    // Add credits
    const account = addCredits(
      fromWallet,
      txHash,
      creditMatch.packageId,
      creditMatch.credits,
      amountPaid
    );

    result = {
      success: true,
      purchase_type: "credits",
      credits_purchased: {
        package: creditMatch.packageId,
        amount_paid: `$${amountPaid} USDC`,
        credits_added: creditMatch.credits,
        bonus_credits: creditMatch.bonus,
        effective_rate: `$${creditMatch.effectiveRate.toFixed(4)}/credit`,
      },
      balance: getBalance(fromWallet),
    };
  } else {
    return res.status(400).json({
      error: "Invalid payment amount",
      message: "Amount doesn't match any package. Minimum is $1 USDC.",
      amount_received: `$${amountPaid} USDC`,
      available_packages: Object.entries(CREDIT_PACKAGES).map(([id, pkg]) => ({
        id,
        price: `$${pkg.price}`,
        credits: pkg.credits,
      })),
    });
  }

  return res.status(200).json(result);
}
