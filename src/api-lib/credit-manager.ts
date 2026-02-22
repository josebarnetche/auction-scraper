/**
 * Credit Manager for Subasto API
 *
 * Manages credit balances and subscriptions for AI agents.
 * Storage: Uses Vercel KV if available, falls back to in-memory for MVP.
 *
 * Credit Value: 1 credit = 1 API call (regardless of endpoint tier)
 * This simplifies agent logic - they don't need to calculate costs per endpoint.
 */

import { CREDIT_PACKAGES, SUBSCRIPTION_TIERS, SubscriptionTier } from "./config.js";

// Types
export interface CreditAccount {
  wallet: string;
  credits: number;
  subscription: SubscriptionTier;
  subscriptionExpiresAt: number | null; // Unix timestamp, null = no active subscription
  totalPurchased: number; // Lifetime credits purchased
  totalUsed: number; // Lifetime credits used
  createdAt: number;
  updatedAt: number;
}

export interface CreditPurchase {
  wallet: string;
  txHash: string;
  packageId: string;
  creditsAdded: number;
  amountPaid: number;
  timestamp: number;
}

export interface SubscriptionPurchase {
  wallet: string;
  txHash: string;
  tier: SubscriptionTier;
  amountPaid: number;
  expiresAt: number;
  timestamp: number;
}

export interface UsageRecord {
  wallet: string;
  endpoint: string;
  creditsUsed: number;
  timestamp: number;
}

// In-memory storage (MVP - replace with Vercel KV for production)
// Structure allows easy migration to KV with same keys
const storage = {
  accounts: new Map<string, CreditAccount>(),
  purchases: new Map<string, CreditPurchase>(), // keyed by txHash
  subscriptions: new Map<string, SubscriptionPurchase>(), // keyed by txHash
  usedTxHashes: new Set<string>(), // Anti-replay protection
  dailyUsage: new Map<string, { date: string; count: number }>(), // wallet -> daily usage for free tier
};

/**
 * Normalize wallet address to lowercase for consistent keys
 */
function normalizeWallet(wallet: string): string {
  return wallet.toLowerCase();
}

/**
 * Get today's date string for daily usage tracking
 */
function getTodayKey(): string {
  return new Date().toISOString().split("T")[0];
}

/**
 * Get or create a credit account for a wallet
 */
export function getAccount(wallet: string): CreditAccount {
  const key = normalizeWallet(wallet);
  let account = storage.accounts.get(key);

  if (!account) {
    account = {
      wallet: key,
      credits: 0,
      subscription: "free",
      subscriptionExpiresAt: null,
      totalPurchased: 0,
      totalUsed: 0,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    storage.accounts.set(key, account);
  }

  // Check if subscription has expired
  if (account.subscription !== "free" && account.subscriptionExpiresAt) {
    if (Date.now() > account.subscriptionExpiresAt) {
      account.subscription = "free";
      account.subscriptionExpiresAt = null;
      account.updatedAt = Date.now();
    }
  }

  return account;
}

/**
 * Check if a transaction hash has already been used
 */
export function isTxUsed(txHash: string): boolean {
  return storage.usedTxHashes.has(txHash.toLowerCase());
}

/**
 * Mark a transaction hash as used
 */
export function markTxUsed(txHash: string): void {
  storage.usedTxHashes.add(txHash.toLowerCase());
}

/**
 * Add credits to a wallet account
 */
export function addCredits(
  wallet: string,
  txHash: string,
  packageId: string,
  creditsToAdd: number,
  amountPaid: number
): CreditAccount {
  const account = getAccount(wallet);

  // Record the purchase
  const purchase: CreditPurchase = {
    wallet: normalizeWallet(wallet),
    txHash: txHash.toLowerCase(),
    packageId,
    creditsAdded: creditsToAdd,
    amountPaid,
    timestamp: Date.now(),
  };
  storage.purchases.set(txHash.toLowerCase(), purchase);

  // Update account
  account.credits += creditsToAdd;
  account.totalPurchased += creditsToAdd;
  account.updatedAt = Date.now();

  // Mark tx as used
  markTxUsed(txHash);

  return account;
}

/**
 * Activate a subscription for a wallet
 */
export function activateSubscription(
  wallet: string,
  txHash: string,
  tier: SubscriptionTier,
  amountPaid: number
): CreditAccount {
  const account = getAccount(wallet);
  const tierConfig = SUBSCRIPTION_TIERS[tier];

  // Calculate expiration (1 month from now)
  const durationMs = tierConfig.durationDays * 24 * 60 * 60 * 1000;
  const expiresAt = Date.now() + durationMs;

  // Record the subscription
  const subscription: SubscriptionPurchase = {
    wallet: normalizeWallet(wallet),
    txHash: txHash.toLowerCase(),
    tier,
    amountPaid,
    expiresAt,
    timestamp: Date.now(),
  };
  storage.subscriptions.set(txHash.toLowerCase(), subscription);

  // Update account
  account.subscription = tier;
  account.subscriptionExpiresAt = expiresAt;
  account.updatedAt = Date.now();

  // Mark tx as used
  markTxUsed(txHash);

  return account;
}

/**
 * Check if a wallet can make an API request
 * Returns: { allowed: boolean, reason?: string, creditsRequired?: number }
 */
export function canMakeRequest(
  wallet: string,
  endpoint: string
): { allowed: boolean; reason?: string; method: "credits" | "subscription" | "free"; creditsRemaining?: number } {
  const account = getAccount(wallet);
  const tierConfig = SUBSCRIPTION_TIERS[account.subscription];

  // Check subscription limits
  if (account.subscription === "free") {
    // Check daily usage for free tier
    const todayKey = getTodayKey();
    const usage = storage.dailyUsage.get(normalizeWallet(wallet));

    if (usage && usage.date === todayKey) {
      if (usage.count >= tierConfig.requestsPerDay) {
        // Free limit reached - need credits or subscription
        if (account.credits > 0) {
          return { allowed: true, method: "credits", creditsRemaining: account.credits };
        }
        return {
          allowed: false,
          reason: `Free tier limit reached (${tierConfig.requestsPerDay}/day). Buy credits or upgrade to Pro.`,
          method: "free",
        };
      }
    }

    return { allowed: true, method: "free", creditsRemaining: account.credits };
  }

  // Pro and Enterprise have unlimited requests
  if (tierConfig.requestsPerDay === -1) {
    return { allowed: true, method: "subscription", creditsRemaining: account.credits };
  }

  // Fallback to credits if somehow subscription doesn't cover
  if (account.credits > 0) {
    return { allowed: true, method: "credits", creditsRemaining: account.credits };
  }

  return {
    allowed: false,
    reason: "No credits or active subscription",
    method: "credits",
  };
}

/**
 * Deduct a credit or record free usage
 * Call this AFTER successfully serving a request
 */
export function recordUsage(
  wallet: string,
  endpoint: string,
  method: "credits" | "subscription" | "free"
): void {
  const account = getAccount(wallet);

  if (method === "credits") {
    if (account.credits > 0) {
      account.credits -= 1;
      account.totalUsed += 1;
      account.updatedAt = Date.now();
    }
  } else if (method === "free") {
    // Track daily usage for free tier
    const todayKey = getTodayKey();
    const key = normalizeWallet(wallet);
    const usage = storage.dailyUsage.get(key);

    if (usage && usage.date === todayKey) {
      usage.count += 1;
    } else {
      storage.dailyUsage.set(key, { date: todayKey, count: 1 });
    }
  }
  // Subscription usage doesn't need tracking (unlimited)
}

/**
 * Get credit balance summary for a wallet
 */
export function getBalance(wallet: string): {
  wallet: string;
  credits: number;
  subscription: {
    tier: SubscriptionTier;
    active: boolean;
    expiresAt: string | null;
    daysRemaining: number | null;
    features: string[];
  };
  usage: {
    totalPurchased: number;
    totalUsed: number;
    freeRequestsToday: number;
    freeRequestsLimit: number;
  };
} {
  const account = getAccount(wallet);
  const tierConfig = SUBSCRIPTION_TIERS[account.subscription];

  // Get today's free usage
  const todayKey = getTodayKey();
  const dailyUsage = storage.dailyUsage.get(normalizeWallet(wallet));
  const freeRequestsToday = (dailyUsage?.date === todayKey) ? dailyUsage.count : 0;

  // Calculate days remaining
  let daysRemaining: number | null = null;
  if (account.subscriptionExpiresAt) {
    const msRemaining = account.subscriptionExpiresAt - Date.now();
    daysRemaining = Math.max(0, Math.ceil(msRemaining / (24 * 60 * 60 * 1000)));
  }

  return {
    wallet: account.wallet,
    credits: account.credits,
    subscription: {
      tier: account.subscription,
      active: account.subscription !== "free",
      expiresAt: account.subscriptionExpiresAt
        ? new Date(account.subscriptionExpiresAt).toISOString()
        : null,
      daysRemaining,
      features: tierConfig.features,
    },
    usage: {
      totalPurchased: account.totalPurchased,
      totalUsed: account.totalUsed,
      freeRequestsToday,
      freeRequestsLimit: tierConfig.requestsPerDay === -1 ? -1 : tierConfig.requestsPerDay,
    },
  };
}

/**
 * Calculate credits for a given USDC amount based on packages
 * Returns the best matching package
 */
export function calculateCreditsForAmount(amountUSDC: number): {
  packageId: string;
  credits: number;
  bonus: number;
  effectiveRate: number;
} | null {
  // Find the exact or best matching package
  for (const [id, pkg] of Object.entries(CREDIT_PACKAGES)) {
    if (Math.abs(amountUSDC - pkg.price) < 0.001) {
      const bonus = pkg.credits - Math.floor(pkg.price / 0.02 * 1); // Base rate: $0.02 = 1 credit
      const effectiveRate = pkg.price / pkg.credits;
      return { packageId: id, credits: pkg.credits, bonus: Math.max(0, bonus), effectiveRate };
    }
  }

  // No exact match - calculate at base rate (no bonus)
  // Base rate: $0.02 per credit (50 credits per dollar)
  const baseCredits = Math.floor(amountUSDC * 50);
  if (baseCredits > 0) {
    return {
      packageId: "custom",
      credits: baseCredits,
      bonus: 0,
      effectiveRate: 0.02,
    };
  }

  return null;
}

/**
 * Check if amount matches a subscription tier
 */
export function getSubscriptionForAmount(amountUSDC: number): {
  tier: SubscriptionTier;
  name: string;
  price: number;
} | null {
  for (const [tier, config] of Object.entries(SUBSCRIPTION_TIERS)) {
    if (config.price > 0 && Math.abs(amountUSDC - config.price) < 0.001) {
      return {
        tier: tier as SubscriptionTier,
        name: config.name,
        price: config.price,
      };
    }
  }
  return null;
}
