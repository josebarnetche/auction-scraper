/**
 * GET /api/v1/webhooks/status
 *
 * Check the status of a webhook subscription.
 * No payment required - just provide your subscription ID.
 *
 * Query parameters:
 *   - id: Your subscription ID (wh_xxx)
 *
 * Response includes:
 *   - Subscription status (active/expired/not found)
 *   - Expiration date
 *   - Filter configuration
 *   - Notification statistics
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import {
  getSubscription,
  getActiveSubscriptions,
  updateSubscription,
  VALID_CATEGORIES,
} from "../../lib/webhook-store.js";
import { PAYMENT_WALLET } from "../../lib/config.js";

// Renewal price
const WEBHOOK_RENEWAL_PRICE = 0.10;

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "GET") {
    return res.status(405).json({
      error: "Method not allowed",
      message: "Use GET to check subscription status",
    });
  }

  const subscriptionId = req.query.id as string;

  // If no ID provided, show general info
  if (!subscriptionId) {
    const activeCount = getActiveSubscriptions().length;

    return res.status(200).json({
      message: "Webhook Status API",
      description: "Check the status of your webhook subscription",
      usage: {
        endpoint: "GET /api/v1/webhooks/status?id=YOUR_SUBSCRIPTION_ID",
        example: "GET /api/v1/webhooks/status?id=wh_abc123_xyz",
      },
      system_status: {
        active_subscriptions: activeCount,
        scrape_schedule: "Daily at 00:00 Argentina time (UTC-3)",
        next_scrape: getNextScrapeTime(),
      },
      pricing: {
        registration: "$0.10 USDC for 30 days",
        renewal: "$0.10 USDC for another 30 days",
        wallet: PAYMENT_WALLET,
        register_endpoint: "POST /api/v1/webhooks/register",
      },
      available_categories: VALID_CATEGORIES,
    });
  }

  // Look up the subscription
  const subscription = getSubscription(subscriptionId);

  if (!subscription) {
    return res.status(404).json({
      error: "Subscription not found",
      message: `No subscription found with ID: ${subscriptionId}`,
      hint: "Check that you're using the correct subscription ID (starts with 'wh_')",
    });
  }

  // Check if expired
  const now = new Date();
  const expiresAt = new Date(subscription.expires_at);
  const isExpired = expiresAt < now;
  const daysRemaining = Math.max(0, Math.ceil((expiresAt.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)));

  // Calculate time since last notification
  let lastNotificationAgo = null;
  if (subscription.last_notified_at) {
    const lastNotified = new Date(subscription.last_notified_at);
    const hoursAgo = Math.round((now.getTime() - lastNotified.getTime()) / (1000 * 60 * 60));
    lastNotificationAgo = hoursAgo < 24 ? `${hoursAgo} hours ago` : `${Math.round(hoursAgo / 24)} days ago`;
  }

  // Build response
  const response: any = {
    subscription: {
      id: subscription.id,
      status: isExpired ? "expired" : (subscription.is_active ? "active" : "inactive"),
      webhook_url: maskUrl(subscription.webhook_url),  // Partially masked for privacy
      filters: subscription.filters,
      created_at: subscription.created_at,
      expires_at: subscription.expires_at,
      days_remaining: daysRemaining,
    },
    statistics: {
      total_notifications_sent: subscription.notification_count,
      last_notification: subscription.last_notified_at || null,
      last_notification_ago: lastNotificationAgo,
    },
    payer: {
      address: maskAddress(subscription.payer_address),
      payment_tx: subscription.payment_tx,
    },
  };

  // Add expiration warning or renewal info
  if (isExpired) {
    response.renewal = {
      message: "Your subscription has expired. Renew to continue receiving notifications.",
      price: WEBHOOK_RENEWAL_PRICE,
      currency: "USDC",
      wallet: PAYMENT_WALLET,
      endpoint: "POST /api/v1/webhooks/register",
      note: "Register a new subscription with the same webhook_url to renew",
    };
  } else if (daysRemaining <= 7) {
    response.warning = {
      message: `Your subscription expires in ${daysRemaining} day(s). Consider renewing soon.`,
      renewal_price: WEBHOOK_RENEWAL_PRICE,
    };
  }

  return res.status(200).json(response);
}

/**
 * Get the next scheduled scrape time
 */
function getNextScrapeTime(): string {
  const now = new Date();

  // Argentina is UTC-3
  const argentinaOffset = -3 * 60; // minutes
  const argentinaTime = new Date(now.getTime() + (argentinaOffset + now.getTimezoneOffset()) * 60000);

  // Next midnight Argentina time
  const nextMidnight = new Date(argentinaTime);
  nextMidnight.setHours(24, 0, 0, 0);

  // If it's already past midnight, use today's midnight (which means scrape just happened)
  if (argentinaTime.getHours() === 0 && argentinaTime.getMinutes() < 30) {
    nextMidnight.setDate(nextMidnight.getDate() - 1);
  }

  // Convert back to UTC
  const nextScrapeUtc = new Date(nextMidnight.getTime() - (argentinaOffset + now.getTimezoneOffset()) * 60000);

  return nextScrapeUtc.toISOString();
}

/**
 * Mask a URL for privacy (show domain only)
 */
function maskUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const pathParts = parsed.pathname.split('/').filter(p => p);
    const maskedPath = pathParts.length > 0 ? `/${pathParts[0]}/...` : '/';
    return `${parsed.protocol}//${parsed.hostname}${maskedPath}`;
  } catch {
    return "***";
  }
}

/**
 * Mask an Ethereum address for privacy
 */
function maskAddress(address: string): string {
  if (!address || address.length < 10) return "***";
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}
