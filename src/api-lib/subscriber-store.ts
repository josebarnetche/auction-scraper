/**
 * Subscriber Storage Module
 *
 * Manages email subscribers using Vercel KV (Redis) or JSON fallback.
 * Supports preferences, confirmation tokens, and unsubscribe tokens.
 */

import { createHash, randomBytes } from "crypto";

// Types
export interface SubscriberPreferences {
  categories: string[];        // vehicles, real_estate, machinery, general_goods, other
  provinces: string[];         // Buenos Aires, Cordoba, etc.
  priceMinUsd: number;         // Minimum price filter
  priceMaxUsd: number;         // Maximum price filter (0 = no max)
  digestFrequency: "daily" | "weekly" | "realtime";
  endingTodayAlerts: boolean;  // Get alerts for auctions ending today
  opportunitiesOnly: boolean;  // Only send opportunities (30%+ discount)
}

export interface Subscriber {
  email: string;
  emailHash: string;           // SHA256 hash for privacy
  createdAt: string;           // ISO date
  confirmedAt: string | null;  // ISO date when confirmed (null = pending)
  confirmToken: string;        // Token for double opt-in
  unsubscribeToken: string;    // Unique token for unsubscribe link
  preferences: SubscriberPreferences;
  lastDigestSent: string | null;  // ISO date
  digestCount: number;         // Total digests sent
  bounceCount: number;         // Email bounce tracking
  status: "pending" | "active" | "unsubscribed" | "bounced";
}

// Default preferences
const DEFAULT_PREFERENCES: SubscriberPreferences = {
  categories: ["vehicles", "real_estate", "machinery", "general_goods", "other"],
  provinces: [],  // Empty = all provinces
  priceMinUsd: 0,
  priceMaxUsd: 0,  // 0 = no maximum
  digestFrequency: "daily",
  endingTodayAlerts: true,
  opportunitiesOnly: false,
};

// Generate secure tokens
function generateToken(): string {
  return randomBytes(32).toString("hex");
}

function hashEmail(email: string): string {
  return createHash("sha256").update(email.toLowerCase().trim()).digest("hex");
}

// In-memory store (fallback when KV not available)
// In production, use Vercel KV
const memoryStore: Map<string, Subscriber> = new Map();

// Try to use Vercel KV if available
let kvAvailable = false;
let kv: any = null;

async function initKV() {
  try {
    // Dynamic import for Vercel KV
    const kvModule = await import("@vercel/kv");
    kv = kvModule.kv;
    kvAvailable = true;
    console.log("Vercel KV initialized");
  } catch (e) {
    console.log("Vercel KV not available, using memory store");
    kvAvailable = false;
  }
}

// Initialize on first import
initKV();

// Storage keys
const SUBSCRIBER_KEY_PREFIX = "subscriber:";
const EMAIL_INDEX_KEY = "subscribers:emails";

/**
 * Create a new subscriber (pending confirmation)
 */
export async function createSubscriber(
  email: string,
  preferences: Partial<SubscriberPreferences> = {}
): Promise<{ subscriber: Subscriber; isNew: boolean }> {
  const normalizedEmail = email.toLowerCase().trim();
  const emailHash = hashEmail(normalizedEmail);

  // Check if already exists
  const existing = await getSubscriberByEmail(normalizedEmail);
  if (existing) {
    // If unsubscribed, allow re-subscribe
    if (existing.status === "unsubscribed") {
      existing.status = "pending";
      existing.confirmToken = generateToken();
      existing.preferences = { ...DEFAULT_PREFERENCES, ...preferences };
      await saveSubscriber(existing);
      return { subscriber: existing, isNew: false };
    }
    return { subscriber: existing, isNew: false };
  }

  const subscriber: Subscriber = {
    email: normalizedEmail,
    emailHash,
    createdAt: new Date().toISOString(),
    confirmedAt: null,
    confirmToken: generateToken(),
    unsubscribeToken: generateToken(),
    preferences: { ...DEFAULT_PREFERENCES, ...preferences },
    lastDigestSent: null,
    digestCount: 0,
    bounceCount: 0,
    status: "pending",
  };

  await saveSubscriber(subscriber);
  return { subscriber, isNew: true };
}

/**
 * Confirm a subscriber (double opt-in)
 */
export async function confirmSubscriber(confirmToken: string): Promise<Subscriber | null> {
  const subscriber = await getSubscriberByConfirmToken(confirmToken);
  if (!subscriber) return null;

  if (subscriber.status === "pending") {
    subscriber.status = "active";
    subscriber.confirmedAt = new Date().toISOString();
    await saveSubscriber(subscriber);
  }

  return subscriber;
}

/**
 * Unsubscribe using token
 */
export async function unsubscribeByToken(unsubscribeToken: string): Promise<Subscriber | null> {
  const subscriber = await getSubscriberByUnsubscribeToken(unsubscribeToken);
  if (!subscriber) return null;

  subscriber.status = "unsubscribed";
  await saveSubscriber(subscriber);
  return subscriber;
}

/**
 * Update subscriber preferences
 */
export async function updatePreferences(
  email: string,
  preferences: Partial<SubscriberPreferences>
): Promise<Subscriber | null> {
  const subscriber = await getSubscriberByEmail(email);
  if (!subscriber || subscriber.status !== "active") return null;

  subscriber.preferences = { ...subscriber.preferences, ...preferences };
  await saveSubscriber(subscriber);
  return subscriber;
}

/**
 * Get all active subscribers for digest
 */
export async function getActiveSubscribers(
  frequency: "daily" | "weekly" | "realtime" = "daily"
): Promise<Subscriber[]> {
  const allSubscribers = await getAllSubscribers();
  return allSubscribers.filter(
    (s) => s.status === "active" && s.preferences.digestFrequency === frequency
  );
}

/**
 * Mark digest as sent
 */
export async function markDigestSent(email: string): Promise<void> {
  const subscriber = await getSubscriberByEmail(email);
  if (subscriber) {
    subscriber.lastDigestSent = new Date().toISOString();
    subscriber.digestCount += 1;
    await saveSubscriber(subscriber);
  }
}

/**
 * Record email bounce
 */
export async function recordBounce(email: string): Promise<void> {
  const subscriber = await getSubscriberByEmail(email);
  if (subscriber) {
    subscriber.bounceCount += 1;
    if (subscriber.bounceCount >= 3) {
      subscriber.status = "bounced";
    }
    await saveSubscriber(subscriber);
  }
}

// ============================================================================
// Storage implementation (KV or memory fallback)
// ============================================================================

async function saveSubscriber(subscriber: Subscriber): Promise<void> {
  const key = SUBSCRIBER_KEY_PREFIX + subscriber.emailHash;

  if (kvAvailable && kv) {
    await kv.set(key, JSON.stringify(subscriber));
    // Also add to email index for listing
    await kv.sadd(EMAIL_INDEX_KEY, subscriber.emailHash);
  } else {
    memoryStore.set(subscriber.emailHash, subscriber);
  }
}

async function getSubscriberByEmail(email: string): Promise<Subscriber | null> {
  const emailHash = hashEmail(email.toLowerCase().trim());
  const key = SUBSCRIBER_KEY_PREFIX + emailHash;

  if (kvAvailable && kv) {
    const data = await kv.get(key);
    return data ? JSON.parse(data as string) : null;
  } else {
    return memoryStore.get(emailHash) || null;
  }
}

async function getSubscriberByConfirmToken(token: string): Promise<Subscriber | null> {
  const all = await getAllSubscribers();
  return all.find((s) => s.confirmToken === token) || null;
}

async function getSubscriberByUnsubscribeToken(token: string): Promise<Subscriber | null> {
  const all = await getAllSubscribers();
  return all.find((s) => s.unsubscribeToken === token) || null;
}

async function getAllSubscribers(): Promise<Subscriber[]> {
  if (kvAvailable && kv) {
    const emailHashes = await kv.smembers(EMAIL_INDEX_KEY);
    if (!emailHashes || emailHashes.length === 0) return [];

    const subscribers: Subscriber[] = [];
    for (const hash of emailHashes) {
      const key = SUBSCRIBER_KEY_PREFIX + hash;
      const data = await kv.get(key);
      if (data) {
        subscribers.push(JSON.parse(data as string));
      }
    }
    return subscribers;
  } else {
    return Array.from(memoryStore.values());
  }
}

/**
 * Export subscribers for backup/migration (GDPR compliance)
 */
export async function exportSubscriberData(email: string): Promise<Subscriber | null> {
  return getSubscriberByEmail(email);
}

/**
 * Delete subscriber data (GDPR right to be forgotten)
 */
export async function deleteSubscriberData(email: string): Promise<boolean> {
  const subscriber = await getSubscriberByEmail(email);
  if (!subscriber) return false;

  const key = SUBSCRIBER_KEY_PREFIX + subscriber.emailHash;

  if (kvAvailable && kv) {
    await kv.del(key);
    await kv.srem(EMAIL_INDEX_KEY, subscriber.emailHash);
  } else {
    memoryStore.delete(subscriber.emailHash);
  }

  return true;
}

/**
 * Get subscriber stats
 */
export async function getSubscriberStats(): Promise<{
  total: number;
  active: number;
  pending: number;
  unsubscribed: number;
  bounced: number;
}> {
  const all = await getAllSubscribers();
  return {
    total: all.length,
    active: all.filter((s) => s.status === "active").length,
    pending: all.filter((s) => s.status === "pending").length,
    unsubscribed: all.filter((s) => s.status === "unsubscribed").length,
    bounced: all.filter((s) => s.status === "bounced").length,
  };
}
