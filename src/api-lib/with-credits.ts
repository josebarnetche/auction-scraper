/**
 * Credit-aware request handler middleware
 *
 * Wraps API handlers to support both:
 * 1. Credit-based access (wallet address in header or query)
 * 2. Legacy per-transaction payments (tx hash in query)
 *
 * Usage:
 *   import { withCredits } from "../lib/with-credits.js";
 *
 *   export default withCredits(async (req, res, payment) => {
 *     // payment contains: { method, wallet, creditsUsed }
 *     return res.json({ data: "..." });
 *   });
 *
 * Client usage:
 *   // With credits (preferred)
 *   GET /api/v1/auctions
 *   Header: X-Wallet: 0x...
 *
 *   // Legacy per-tx payment
 *   GET /api/v1/auctions?tx=0x...
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { verifyUSDCPayment } from "./verify-payment.js";
import { PAYMENT_WALLET, PRICES } from "./config.js";
import {
  canMakeRequest,
  recordUsage,
  isTxUsed,
  markTxUsed,
  getBalance,
} from "./credit-manager.js";

export interface PaymentContext {
  method: "credits" | "subscription" | "free" | "tx";
  wallet: string | null;
  txHash: string | null;
  creditsRemaining: number | null;
}

type HandlerWithPayment = (
  req: VercelRequest,
  res: VercelResponse,
  payment: PaymentContext
) => Promise<VercelResponse | void>;

/**
 * Wrap an API handler with credit/payment verification
 */
export function withCredits(
  handler: HandlerWithPayment,
  options: {
    endpointName: string;
    legacyPrice: number;
  }
) {
  return async (req: VercelRequest, res: VercelResponse) => {
    res.setHeader("Access-Control-Allow-Origin", "*");

    // Handle CORS preflight
    if (req.method === "OPTIONS") {
      res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
      res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-Wallet");
      return res.status(200).end();
    }

    // Get wallet from header or query
    const wallet = (req.headers["x-wallet"] as string) || (req.query.wallet as string);
    const txHash = req.query.tx as string;

    // Priority 1: Credit-based access via wallet
    if (wallet) {
      // Validate wallet format
      if (!/^0x[a-fA-F0-9]{40}$/i.test(wallet)) {
        return res.status(400).json({
          error: "Invalid wallet address",
          message: "X-Wallet header must be a valid Ethereum address",
        });
      }

      const accessCheck = canMakeRequest(wallet, options.endpointName);

      if (!accessCheck.allowed) {
        const balance = getBalance(wallet);
        return res.status(402).json({
          error: "Access denied",
          message: accessCheck.reason,
          balance: {
            credits: balance.credits,
            subscription: balance.subscription.tier,
            free_requests_remaining:
              balance.usage.freeRequestsLimit === -1
                ? "unlimited"
                : Math.max(0, balance.usage.freeRequestsLimit - balance.usage.freeRequestsToday),
          },
          upgrade: {
            buy_credits: "/api/v1/credits/buy",
            check_balance: `/api/v1/credits/balance?wallet=${wallet}`,
          },
        });
      }

      // Record usage AFTER successful response
      const payment: PaymentContext = {
        method: accessCheck.method,
        wallet,
        txHash: null,
        creditsRemaining: accessCheck.creditsRemaining ?? null,
      };

      try {
        const result = await handler(req, res, payment);
        // Record usage only on success
        recordUsage(wallet, options.endpointName, accessCheck.method);
        return result;
      } catch (error) {
        // Don't record usage on error
        throw error;
      }
    }

    // Priority 2: Legacy per-transaction payment
    if (txHash) {
      // Check if tx already used
      if (isTxUsed(txHash)) {
        return res.status(400).json({
          error: "Transaction already used",
          message: "Each transaction can only be used once",
          upgrade: "Consider buying credits for easier access: /api/v1/credits/buy",
        });
      }

      // Verify payment on-chain
      const verification = await verifyUSDCPayment(txHash, options.legacyPrice);

      if (!verification.valid) {
        return res.status(402).json({
          error: "Payment verification failed",
          message: verification.error,
          required: options.legacyPrice,
          currency: "USDC",
          wallet: PAYMENT_WALLET,
          upgrade: "Consider buying credits for bulk discounts: /api/v1/credits/buy",
        });
      }

      // Mark tx as used
      markTxUsed(txHash);

      const payment: PaymentContext = {
        method: "tx",
        wallet: verification.from || null,
        txHash,
        creditsRemaining: null,
      };

      return handler(req, res, payment);
    }

    // No payment method provided
    return res.status(402).json({
      error: "Payment required",
      message: "Provide credits (X-Wallet header) or per-request payment (?tx=...)",
      options: {
        credits: {
          description: "Use pre-purchased credits",
          method: "Set X-Wallet header with your wallet address",
          buy_credits: "/api/v1/credits/buy",
        },
        per_request: {
          description: "Pay per request (legacy)",
          price: options.legacyPrice,
          currency: "USDC",
          wallet: PAYMENT_WALLET,
          method: "Include ?tx=YOUR_TX_HASH",
        },
        free_tier: {
          description: "Free tier: 10 requests/day",
          method: "Set X-Wallet header with any wallet address",
        },
      },
      docs: "/api/v1/price",
    });
  };
}
