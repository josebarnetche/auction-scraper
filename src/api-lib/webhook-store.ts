/**
 * Webhook Subscription Storage and Types
 *
 * For production: Use Vercel KV, Redis, or a database
 * Current implementation: In-memory with JSON file persistence simulation
 */

import { readFileSync, writeFileSync, existsSync } from "fs";
import { join } from "path";

// Webhook subscription categories
export const VALID_CATEGORIES = [
  "vehicles",
  "real_estate",
  "machinery",
  "general_goods",
] as const;

export type WebhookCategory = typeof VALID_CATEGORIES[number];

// Webhook subscription filter
export interface WebhookFilter {
  categories: WebhookCategory[];
  max_price_usd?: number;        // Only notify if auction price <= this
  min_discount_percent?: number; // Only notify if discount >= this (e.g., 50 for 50%+)
}

// Webhook subscription record
export interface WebhookSubscription {
  id: string;                    // Unique subscription ID
  webhook_url: string;           // URL to POST notifications to
  secret: string;                // Secret for HMAC signature verification
  filters: WebhookFilter;
  created_at: string;            // ISO timestamp
  expires_at: string;            // ISO timestamp (30 days from creation)
  payment_tx: string;            // Payment transaction hash
  payer_address: string;         // Who paid for the subscription
  is_active: boolean;
  last_notified_at?: string;     // Last successful notification
  notification_count: number;    // Total notifications sent
}

// Webhook payload sent to subscribers
export interface WebhookPayload {
  event: "new_opportunity" | "price_drop" | "closing_soon";
  timestamp: string;
  subscription_id: string;
  data: {
    listings: OpportunityNotification[];
    total_count: number;
    scrape_run_id: string;
  };
  signature: string;  // HMAC-SHA256 of payload with subscriber's secret
}

// Individual listing in notification
export interface OpportunityNotification {
  id: string;
  title: string;
  category: WebhookCategory | "other";
  source: string;
  source_url: string;
  base_price: number;
  currency: string;
  base_price_usd: number;
  market_price_usd?: number;
  discount_percent?: number;
  closing_at?: string;
  images: string[];
  location: {
    province: string;
    city: string;
  };
  opportunity_score: number;  // 1-100, higher = better deal
  match_reason: string;       // Why this matched the subscription
}

// Path to subscriptions JSON (for persistence between cold starts)
const SUBSCRIPTIONS_PATH = join(process.cwd(), "data", "webhook_subscriptions.json");

// In-memory store (reloaded from file on cold start)
let subscriptions: Map<string, WebhookSubscription> = new Map();
let loaded = false;

/**
 * Load subscriptions from persistent storage
 */
function loadSubscriptions(): void {
  if (loaded) return;

  try {
    if (existsSync(SUBSCRIPTIONS_PATH)) {
      const data = JSON.parse(readFileSync(SUBSCRIPTIONS_PATH, "utf-8"));
      subscriptions = new Map(Object.entries(data));
    }
  } catch (error) {
    console.error("Failed to load webhook subscriptions:", error);
  }
  loaded = true;
}

/**
 * Save subscriptions to persistent storage
 */
function saveSubscriptions(): void {
  try {
    const data = Object.fromEntries(subscriptions);
    writeFileSync(SUBSCRIPTIONS_PATH, JSON.stringify(data, null, 2));
  } catch (error) {
    console.error("Failed to save webhook subscriptions:", error);
  }
}

/**
 * Generate a unique subscription ID
 */
export function generateSubscriptionId(): string {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 10);
  return `wh_${timestamp}_${random}`;
}

/**
 * Generate a secret for webhook signature verification
 */
export function generateSecret(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let result = 'whsec_';
  for (let i = 0; i < 32; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

/**
 * Create a new webhook subscription
 */
export function createSubscription(
  webhookUrl: string,
  filters: WebhookFilter,
  paymentTx: string,
  payerAddress: string
): WebhookSubscription {
  loadSubscriptions();

  const now = new Date();
  const expiresAt = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000); // 30 days

  const subscription: WebhookSubscription = {
    id: generateSubscriptionId(),
    webhook_url: webhookUrl,
    secret: generateSecret(),
    filters,
    created_at: now.toISOString(),
    expires_at: expiresAt.toISOString(),
    payment_tx: paymentTx,
    payer_address: payerAddress,
    is_active: true,
    notification_count: 0,
  };

  subscriptions.set(subscription.id, subscription);
  saveSubscriptions();

  return subscription;
}

/**
 * Get a subscription by ID
 */
export function getSubscription(id: string): WebhookSubscription | undefined {
  loadSubscriptions();
  return subscriptions.get(id);
}

/**
 * Get subscription by webhook URL (to prevent duplicates)
 */
export function getSubscriptionByUrl(url: string): WebhookSubscription | undefined {
  loadSubscriptions();
  for (const sub of subscriptions.values()) {
    if (sub.webhook_url === url && sub.is_active) {
      return sub;
    }
  }
  return undefined;
}

/**
 * Get all active subscriptions
 */
export function getActiveSubscriptions(): WebhookSubscription[] {
  loadSubscriptions();
  const now = new Date();

  return Array.from(subscriptions.values()).filter(sub => {
    if (!sub.is_active) return false;
    if (new Date(sub.expires_at) < now) {
      // Auto-deactivate expired subscriptions
      sub.is_active = false;
      return false;
    }
    return true;
  });
}

/**
 * Update subscription (e.g., after notification)
 */
export function updateSubscription(
  id: string,
  updates: Partial<WebhookSubscription>
): WebhookSubscription | undefined {
  loadSubscriptions();
  const sub = subscriptions.get(id);
  if (!sub) return undefined;

  Object.assign(sub, updates);
  subscriptions.set(id, sub);
  saveSubscriptions();

  return sub;
}

/**
 * Deactivate a subscription
 */
export function deactivateSubscription(id: string): boolean {
  loadSubscriptions();
  const sub = subscriptions.get(id);
  if (!sub) return false;

  sub.is_active = false;
  saveSubscriptions();
  return true;
}

/**
 * Check if a payment tx has already been used for webhook registration
 */
export function isPaymentTxUsed(txHash: string): boolean {
  loadSubscriptions();
  const normalizedTx = txHash.toLowerCase();

  for (const sub of subscriptions.values()) {
    if (sub.payment_tx.toLowerCase() === normalizedTx) {
      return true;
    }
  }
  return false;
}

/**
 * Validate webhook URL
 */
export function isValidWebhookUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    // Must be HTTPS for security (except localhost for testing)
    if (parsed.protocol !== "https:" && !parsed.hostname.includes("localhost")) {
      return false;
    }
    // Block common reserved/invalid hosts
    const blocked = ["127.0.0.1", "0.0.0.0", "169.254", "10.", "192.168."];
    if (blocked.some(b => parsed.hostname.startsWith(b))) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

/**
 * Validate filters
 */
export function validateFilters(filters: any): { valid: boolean; error?: string } {
  if (!filters || typeof filters !== "object") {
    return { valid: false, error: "filters must be an object" };
  }

  // Categories validation
  if (!filters.categories || !Array.isArray(filters.categories)) {
    return { valid: false, error: "filters.categories must be an array" };
  }

  if (filters.categories.length === 0) {
    return { valid: false, error: "filters.categories must have at least one category" };
  }

  for (const cat of filters.categories) {
    if (!VALID_CATEGORIES.includes(cat)) {
      return {
        valid: false,
        error: `Invalid category: ${cat}. Valid: ${VALID_CATEGORIES.join(", ")}`
      };
    }
  }

  // Price threshold validation
  if (filters.max_price_usd !== undefined) {
    if (typeof filters.max_price_usd !== "number" || filters.max_price_usd <= 0) {
      return { valid: false, error: "max_price_usd must be a positive number" };
    }
    if (filters.max_price_usd > 10_000_000) {
      return { valid: false, error: "max_price_usd cannot exceed 10,000,000" };
    }
  }

  // Discount threshold validation
  if (filters.min_discount_percent !== undefined) {
    if (typeof filters.min_discount_percent !== "number") {
      return { valid: false, error: "min_discount_percent must be a number" };
    }
    if (filters.min_discount_percent < 0 || filters.min_discount_percent > 100) {
      return { valid: false, error: "min_discount_percent must be between 0 and 100" };
    }
  }

  return { valid: true };
}
