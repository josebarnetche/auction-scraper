/**
 * POST /api/v1/webhooks/register
 *
 * Register a webhook subscription to receive auction notifications.
 * Costs $0.10 USDC on Base network, valid for 30 days.
 *
 * Request body:
 * {
 *   "webhook_url": "https://your-agent.com/webhook",
 *   "filters": {
 *     "categories": ["vehicles", "machinery"],
 *     "max_price_usd": 10000,
 *     "min_discount_percent": 50
 *   }
 * }
 *
 * Response:
 * {
 *   "success": true,
 *   "subscription": {
 *     "id": "wh_xxx",
 *     "secret": "whsec_xxx",  // Use this to verify webhook signatures
 *     "expires_at": "2024-03-22T...",
 *     ...
 *   }
 * }
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { verifyUSDCPayment } from "../../lib/verify-payment.js";
import { PAYMENT_WALLET } from "../../lib/config.js";
import {
  createSubscription,
  isPaymentTxUsed,
  isValidWebhookUrl,
  validateFilters,
  getSubscriptionByUrl,
  VALID_CATEGORIES,
  type WebhookFilter,
} from "../../lib/webhook-store.js";

// Webhook registration price in USDC
const WEBHOOK_PRICE = 0.10;  // $0.10 for 30 days

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  // Handle preflight
  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  // Only accept POST
  if (req.method !== "POST") {
    return res.status(405).json({
      error: "Method not allowed",
      message: "Use POST to register a webhook",
    });
  }

  // Parse request body
  let body: any;
  try {
    body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
  } catch {
    return res.status(400).json({
      error: "Invalid request body",
      message: "Request body must be valid JSON",
    });
  }

  const { tx, webhook_url, filters } = body;

  // ===== VALIDATION =====

  // Check payment tx hash
  if (!tx) {
    return res.status(402).json({
      error: "Payment required",
      message: "Include 'tx' field with USDC payment transaction hash on Base",
      price: WEBHOOK_PRICE,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
      valid_for: "30 days",
      example: {
        tx: "0x...",
        webhook_url: "https://your-agent.com/webhook",
        filters: {
          categories: ["vehicles", "real_estate"],
          max_price_usd: 10000,
          min_discount_percent: 40,
        },
      },
    });
  }

  // Validate webhook URL
  if (!webhook_url) {
    return res.status(400).json({
      error: "Missing webhook_url",
      message: "Provide 'webhook_url' - the HTTPS URL to receive notifications",
    });
  }

  if (!isValidWebhookUrl(webhook_url)) {
    return res.status(400).json({
      error: "Invalid webhook_url",
      message: "webhook_url must be a valid HTTPS URL (localhost allowed for testing)",
    });
  }

  // Validate filters
  const filterValidation = validateFilters(filters);
  if (!filterValidation.valid) {
    return res.status(400).json({
      error: "Invalid filters",
      message: filterValidation.error,
      valid_categories: VALID_CATEGORIES,
      filter_schema: {
        categories: "string[] (required) - at least one of: vehicles, real_estate, machinery, general_goods",
        max_price_usd: "number (optional) - only notify for items under this USD price",
        min_discount_percent: "number (optional) - only notify for items with at least this % discount",
      },
    });
  }

  // Check if webhook URL already has an active subscription
  const existingSubscription = getSubscriptionByUrl(webhook_url);
  if (existingSubscription) {
    return res.status(409).json({
      error: "Subscription already exists",
      message: "This webhook URL already has an active subscription",
      existing_subscription: {
        id: existingSubscription.id,
        expires_at: existingSubscription.expires_at,
        filters: existingSubscription.filters,
      },
      hint: "Use /api/v1/webhooks/status to check or renew your subscription",
    });
  }

  // Check if payment tx already used
  if (isPaymentTxUsed(tx)) {
    return res.status(400).json({
      error: "Transaction already used",
      message: "This payment transaction has already been used for a webhook registration",
    });
  }

  // ===== VERIFY PAYMENT =====

  const verification = await verifyUSDCPayment(tx, WEBHOOK_PRICE);

  if (!verification.valid) {
    return res.status(402).json({
      error: "Payment verification failed",
      message: verification.error,
      required: WEBHOOK_PRICE,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
    });
  }

  // ===== CREATE SUBSCRIPTION =====

  const subscription = createSubscription(
    webhook_url,
    filters as WebhookFilter,
    tx,
    verification.from!
  );

  // Return success with subscription details
  return res.status(201).json({
    success: true,
    message: "Webhook subscription created successfully",
    subscription: {
      id: subscription.id,
      secret: subscription.secret,  // IMPORTANT: Only shown once!
      webhook_url: subscription.webhook_url,
      filters: subscription.filters,
      created_at: subscription.created_at,
      expires_at: subscription.expires_at,
      is_active: subscription.is_active,
    },
    payment: {
      tx: tx,
      amount: verification.amount,
      from: verification.from,
    },
    important: {
      secret_warning: "Save the 'secret' value - it's only shown once and is needed to verify webhook signatures",
      signature_header: "X-Webhook-Signature",
      signature_algorithm: "HMAC-SHA256 of the raw request body using your secret",
    },
    next_steps: [
      "1. Save your subscription ID and secret securely",
      "2. Implement a POST endpoint at your webhook_url",
      "3. Verify the X-Webhook-Signature header on incoming requests",
      "4. You'll receive notifications after each daily scrape (00:00 Argentina time)",
    ],
  });
}
