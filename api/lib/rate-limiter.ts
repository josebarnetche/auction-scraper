/**
 * Rate Limiter for Subasto API
 *
 * Implements tiered rate limiting based on user type:
 * - Free tier: 100 requests/day
 * - Paid (credits): 1000 requests/hour
 * - Premium subscribers (Pro/Enterprise): Unlimited
 *
 * Uses Upstash Redis for distributed rate limiting in production.
 * Falls back to in-memory storage for development/MVP.
 */

import { SubscriptionTier } from "./config.js";

// ============================================================================
// CONFIGURATION
// ============================================================================

export interface RateLimitConfig {
  windowMs: number;       // Time window in milliseconds
  maxRequests: number;    // Max requests per window (-1 = unlimited)
  keyPrefix: string;      // Redis key prefix
}

export const RATE_LIMIT_TIERS: Record<string, RateLimitConfig> = {
  free: {
    windowMs: 24 * 60 * 60 * 1000, // 24 hours
    maxRequests: 100,
    keyPrefix: "rl:free:",
  },
  paid: {
    windowMs: 60 * 60 * 1000, // 1 hour
    maxRequests: 1000,
    keyPrefix: "rl:paid:",
  },
  premium: {
    windowMs: 60 * 60 * 1000, // 1 hour (for tracking, not limiting)
    maxRequests: -1, // Unlimited
    keyPrefix: "rl:premium:",
  },
};

// Endpoint-specific overrides (optional stricter limits for expensive endpoints)
export const ENDPOINT_LIMITS: Record<string, Partial<RateLimitConfig>> = {
  "/api/v1/auctions": {
    // Full data dump - slightly stricter for free tier
    maxRequests: 50, // Override for free tier only
  },
};

// ============================================================================
// TYPES
// ============================================================================

export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  limit: number;
  resetAt: number;        // Unix timestamp (seconds)
  retryAfter?: number;    // Seconds until next request allowed
  tier: string;
}

export interface RateLimitIdentifier {
  ip: string;
  wallet?: string;
  subscriptionTier?: SubscriptionTier;
  hasCredits?: boolean;
}

// ============================================================================
// REDIS CLIENT (Upstash)
// ============================================================================

interface RedisClient {
  get(key: string): Promise<string | null>;
  set(key: string, value: string, options?: { ex?: number }): Promise<void>;
  incr(key: string): Promise<number>;
  expire(key: string, seconds: number): Promise<void>;
  ttl(key: string): Promise<number>;
}

// In-memory fallback for development
class InMemoryRedis implements RedisClient {
  private store = new Map<string, { value: string; expiresAt: number }>();

  private cleanup(): void {
    const now = Date.now();
    for (const [key, entry] of this.store.entries()) {
      if (entry.expiresAt > 0 && entry.expiresAt < now) {
        this.store.delete(key);
      }
    }
  }

  async get(key: string): Promise<string | null> {
    this.cleanup();
    const entry = this.store.get(key);
    if (!entry) return null;
    if (entry.expiresAt > 0 && entry.expiresAt < Date.now()) {
      this.store.delete(key);
      return null;
    }
    return entry.value;
  }

  async set(key: string, value: string, options?: { ex?: number }): Promise<void> {
    const expiresAt = options?.ex ? Date.now() + options.ex * 1000 : 0;
    this.store.set(key, { value, expiresAt });
  }

  async incr(key: string): Promise<number> {
    const current = await this.get(key);
    const newValue = current ? parseInt(current, 10) + 1 : 1;
    const entry = this.store.get(key);
    const expiresAt = entry?.expiresAt || 0;
    this.store.set(key, { value: String(newValue), expiresAt });
    return newValue;
  }

  async expire(key: string, seconds: number): Promise<void> {
    const entry = this.store.get(key);
    if (entry) {
      entry.expiresAt = Date.now() + seconds * 1000;
    }
  }

  async ttl(key: string): Promise<number> {
    const entry = this.store.get(key);
    if (!entry || entry.expiresAt === 0) return -1;
    const remaining = Math.ceil((entry.expiresAt - Date.now()) / 1000);
    return remaining > 0 ? remaining : -2;
  }
}

// Upstash Redis client
class UpstashRedis implements RedisClient {
  private url: string;
  private token: string;

  constructor(url: string, token: string) {
    this.url = url;
    this.token = token;
  }

  private async command(cmd: string[]): Promise<any> {
    const response = await fetch(`${this.url}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(cmd),
    });

    if (!response.ok) {
      throw new Error(`Upstash error: ${response.status}`);
    }

    const data = await response.json();
    return data.result;
  }

  async get(key: string): Promise<string | null> {
    return this.command(["GET", key]);
  }

  async set(key: string, value: string, options?: { ex?: number }): Promise<void> {
    if (options?.ex) {
      await this.command(["SET", key, value, "EX", String(options.ex)]);
    } else {
      await this.command(["SET", key, value]);
    }
  }

  async incr(key: string): Promise<number> {
    return this.command(["INCR", key]);
  }

  async expire(key: string, seconds: number): Promise<void> {
    await this.command(["EXPIRE", key, String(seconds)]);
  }

  async ttl(key: string): Promise<number> {
    return this.command(["TTL", key]);
  }
}

// ============================================================================
// RATE LIMITER CLASS
// ============================================================================

export class RateLimiter {
  private redis: RedisClient;
  private useRedis: boolean;

  constructor() {
    const redisUrl = process.env.UPSTASH_REDIS_REST_URL;
    const redisToken = process.env.UPSTASH_REDIS_REST_TOKEN;

    if (redisUrl && redisToken) {
      this.redis = new UpstashRedis(redisUrl, redisToken);
      this.useRedis = true;
      console.log("Rate limiter using Upstash Redis");
    } else {
      this.redis = new InMemoryRedis();
      this.useRedis = false;
      console.log("Rate limiter using in-memory storage (development mode)");
    }
  }

  /**
   * Determine the rate limit tier for a user
   */
  private getTier(identifier: RateLimitIdentifier): string {
    // Premium subscribers (Pro/Enterprise) get unlimited
    if (identifier.subscriptionTier === "pro" || identifier.subscriptionTier === "enterprise") {
      return "premium";
    }

    // Users with credits get paid tier limits
    if (identifier.hasCredits) {
      return "paid";
    }

    // Default to free tier
    return "free";
  }

  /**
   * Generate rate limit key for storage
   */
  private getKey(identifier: RateLimitIdentifier, endpoint?: string): string {
    const tier = this.getTier(identifier);
    const config = RATE_LIMIT_TIERS[tier];

    // Use wallet if available, otherwise IP
    const userKey = identifier.wallet || identifier.ip;

    // Include endpoint for endpoint-specific limits
    if (endpoint && ENDPOINT_LIMITS[endpoint]) {
      return `${config.keyPrefix}${endpoint}:${userKey}`;
    }

    return `${config.keyPrefix}${userKey}`;
  }

  /**
   * Check rate limit for a request
   */
  async checkLimit(
    identifier: RateLimitIdentifier,
    endpoint?: string
  ): Promise<RateLimitResult> {
    const tier = this.getTier(identifier);
    const config = RATE_LIMIT_TIERS[tier];

    // Unlimited tier - always allow
    if (config.maxRequests === -1) {
      return {
        allowed: true,
        remaining: -1,
        limit: -1,
        resetAt: 0,
        tier,
      };
    }

    // Get effective limit (endpoint override or default)
    let maxRequests = config.maxRequests;
    if (endpoint && ENDPOINT_LIMITS[endpoint]?.maxRequests && tier === "free") {
      maxRequests = ENDPOINT_LIMITS[endpoint].maxRequests!;
    }

    const key = this.getKey(identifier, endpoint);
    const windowSeconds = Math.ceil(config.windowMs / 1000);

    try {
      // Get current count
      const currentStr = await this.redis.get(key);
      const current = currentStr ? parseInt(currentStr, 10) : 0;

      // Get TTL for reset time
      let ttl = await this.redis.ttl(key);
      if (ttl < 0) {
        ttl = windowSeconds;
      }

      const resetAt = Math.ceil(Date.now() / 1000) + ttl;
      const remaining = Math.max(0, maxRequests - current);

      if (current >= maxRequests) {
        return {
          allowed: false,
          remaining: 0,
          limit: maxRequests,
          resetAt,
          retryAfter: ttl,
          tier,
        };
      }

      return {
        allowed: true,
        remaining: remaining - 1, // Will be decremented on consume
        limit: maxRequests,
        resetAt,
        tier,
      };
    } catch (error) {
      console.error("Rate limit check error:", error);
      // Fail open - allow request but log error
      return {
        allowed: true,
        remaining: maxRequests,
        limit: maxRequests,
        resetAt: Math.ceil(Date.now() / 1000) + windowSeconds,
        tier,
      };
    }
  }

  /**
   * Consume a rate limit token (call after request is processed)
   */
  async consume(
    identifier: RateLimitIdentifier,
    endpoint?: string
  ): Promise<RateLimitResult> {
    const tier = this.getTier(identifier);
    const config = RATE_LIMIT_TIERS[tier];

    // Unlimited tier - just track for monitoring
    if (config.maxRequests === -1) {
      const key = this.getKey(identifier, endpoint);
      try {
        await this.redis.incr(key);
        await this.redis.expire(key, Math.ceil(config.windowMs / 1000));
      } catch (error) {
        console.error("Rate limit tracking error:", error);
      }
      return {
        allowed: true,
        remaining: -1,
        limit: -1,
        resetAt: 0,
        tier,
      };
    }

    const key = this.getKey(identifier, endpoint);
    const windowSeconds = Math.ceil(config.windowMs / 1000);

    // Get effective limit
    let maxRequests = config.maxRequests;
    if (endpoint && ENDPOINT_LIMITS[endpoint]?.maxRequests && tier === "free") {
      maxRequests = ENDPOINT_LIMITS[endpoint].maxRequests!;
    }

    try {
      // Increment counter
      const count = await this.redis.incr(key);

      // Set expiry on first request
      if (count === 1) {
        await this.redis.expire(key, windowSeconds);
      }

      const ttl = await this.redis.ttl(key);
      const resetAt = Math.ceil(Date.now() / 1000) + (ttl > 0 ? ttl : windowSeconds);
      const remaining = Math.max(0, maxRequests - count);

      return {
        allowed: count <= maxRequests,
        remaining,
        limit: maxRequests,
        resetAt,
        retryAfter: count > maxRequests ? (ttl > 0 ? ttl : windowSeconds) : undefined,
        tier,
      };
    } catch (error) {
      console.error("Rate limit consume error:", error);
      // Fail open
      return {
        allowed: true,
        remaining: maxRequests - 1,
        limit: maxRequests,
        resetAt: Math.ceil(Date.now() / 1000) + windowSeconds,
        tier,
      };
    }
  }

  /**
   * Get current usage stats for a user
   */
  async getUsage(identifier: RateLimitIdentifier): Promise<{
    tier: string;
    used: number;
    limit: number;
    resetAt: number;
  }> {
    const tier = this.getTier(identifier);
    const config = RATE_LIMIT_TIERS[tier];
    const key = this.getKey(identifier);

    try {
      const currentStr = await this.redis.get(key);
      const current = currentStr ? parseInt(currentStr, 10) : 0;
      const ttl = await this.redis.ttl(key);
      const resetAt = ttl > 0 ? Math.ceil(Date.now() / 1000) + ttl : 0;

      return {
        tier,
        used: current,
        limit: config.maxRequests,
        resetAt,
      };
    } catch (error) {
      console.error("Rate limit usage error:", error);
      return {
        tier,
        used: 0,
        limit: config.maxRequests,
        resetAt: 0,
      };
    }
  }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

let rateLimiterInstance: RateLimiter | null = null;

export function getRateLimiter(): RateLimiter {
  if (!rateLimiterInstance) {
    rateLimiterInstance = new RateLimiter();
  }
  return rateLimiterInstance;
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Extract rate limit headers from result
 */
export function getRateLimitHeaders(result: RateLimitResult): Record<string, string> {
  const headers: Record<string, string> = {
    "X-RateLimit-Limit": String(result.limit),
    "X-RateLimit-Remaining": String(result.remaining),
    "X-RateLimit-Reset": String(result.resetAt),
    "X-RateLimit-Tier": result.tier,
  };

  if (result.retryAfter) {
    headers["Retry-After"] = String(result.retryAfter);
  }

  return headers;
}

/**
 * Extract client IP from request
 */
export function getClientIP(req: { headers: Record<string, string | string[] | undefined> }): string {
  // Vercel provides the real IP in x-forwarded-for
  const forwarded = req.headers["x-forwarded-for"];
  if (forwarded) {
    const ips = Array.isArray(forwarded) ? forwarded[0] : forwarded;
    return ips.split(",")[0].trim();
  }

  // Fallback headers
  const realIP = req.headers["x-real-ip"];
  if (realIP) {
    return Array.isArray(realIP) ? realIP[0] : realIP;
  }

  // Default fallback
  return "unknown";
}
