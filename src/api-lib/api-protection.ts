/**
 * API Protection Middleware for Subasto API
 *
 * Combines rate limiting, abuse prevention, and request logging
 * into a single easy-to-use middleware function.
 *
 * Usage in API handlers:
 *
 * import { protectEndpoint, ProtectionResult } from "../lib/api-protection.js";
 *
 * export default async function handler(req, res) {
 *   const protection = await protectEndpoint(req, res, {
 *     endpoint: "/api/v1/auctions",
 *     wallet: req.query.wallet as string,
 *     subscriptionTier: account?.subscription,
 *     hasCredits: account?.credits > 0,
 *   });
 *
 *   if (!protection.allowed) {
 *     return; // Response already sent
 *   }
 *
 *   // ... handle request
 *
 *   // Log successful response
 *   await protection.logSuccess(200);
 * }
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import {
  getRateLimiter,
  getRateLimitHeaders,
  getClientIP,
  RateLimitIdentifier,
  RateLimitResult,
} from "./rate-limiter.js";
import { getAbusePrevention, AbuseCheckResult } from "./abuse-prevention.js";
import { getRequestLogger, RequestLog } from "./request-logger.js";
import { SubscriptionTier } from "./config.js";

// ============================================================================
// TYPES
// ============================================================================

export interface ProtectionOptions {
  endpoint: string;
  wallet?: string;
  subscriptionTier?: SubscriptionTier;
  hasCredits?: boolean;
  paymentMethod?: "free" | "credits" | "subscription" | "pay-per-use";
}

export interface ProtectionResult {
  allowed: boolean;
  rateLimitResult?: RateLimitResult;
  abuseCheckResult?: AbuseCheckResult;
  ip: string;
  startTime: number;
  logSuccess: (statusCode: number, error?: string) => Promise<void>;
  logError: (statusCode: number, error: string) => Promise<void>;
}

// ============================================================================
// MAIN PROTECTION FUNCTION
// ============================================================================

/**
 * Protect an API endpoint with rate limiting, abuse prevention, and logging.
 *
 * Returns a ProtectionResult that indicates if the request should proceed.
 * If not allowed, the response is already sent with appropriate headers.
 *
 * @param req - Vercel request object
 * @param res - Vercel response object
 * @param options - Protection options
 * @returns ProtectionResult
 */
export async function protectEndpoint(
  req: VercelRequest,
  res: VercelResponse,
  options: ProtectionOptions
): Promise<ProtectionResult> {
  const startTime = Date.now();
  const ip = getClientIP(req);
  const userAgent = req.headers["user-agent"] as string | undefined;
  const rateLimiter = getRateLimiter();
  const abusePrevention = getAbusePrevention();
  const requestLogger = getRequestLogger();

  // Helper to create log function
  const createLogFunction = (
    rateLimitResult?: RateLimitResult
  ) => async (statusCode: number, error?: string): Promise<void> => {
    const responseTimeMs = Date.now() - startTime;

    await requestLogger.logRequest({
      timestamp: startTime,
      ip,
      wallet: options.wallet,
      endpoint: options.endpoint,
      method: req.method || "GET",
      statusCode,
      responseTimeMs,
      rateLimitTier: rateLimitResult?.tier || "unknown",
      rateLimitRemaining: rateLimitResult?.remaining || 0,
      paymentMethod: options.paymentMethod,
      userAgent,
      error,
    });

    // Check if approaching limits
    if (rateLimitResult && options.wallet) {
      await requestLogger.checkApproachingLimits(
        ip,
        options.wallet,
        rateLimitResult.remaining,
        rateLimitResult.limit
      );
    }
  };

  // 1. Abuse Prevention Check
  const abuseCheck = await abusePrevention.checkRequest(ip, userAgent, options.wallet);

  if (!abuseCheck.allowed) {
    // Set rate limit headers even for blocked requests
    res.setHeader("X-Blocked-Reason", abuseCheck.reason || "Abuse detected");

    if (abuseCheck.blockExpires) {
      const retryAfter = Math.ceil((abuseCheck.blockExpires - Date.now()) / 1000);
      res.setHeader("Retry-After", String(retryAfter));
    }

    res.status(403).json({
      error: "Forbidden",
      message: abuseCheck.reason || "Request blocked due to suspicious activity",
      blocked_until: abuseCheck.blockExpires
        ? new Date(abuseCheck.blockExpires).toISOString()
        : undefined,
    });

    // Log the blocked request
    const logFn = createLogFunction();
    await logFn(403, abuseCheck.reason);

    return {
      allowed: false,
      abuseCheckResult: abuseCheck,
      ip,
      startTime,
      logSuccess: async () => {},
      logError: async () => {},
    };
  }

  // 2. Rate Limit Check
  const identifier: RateLimitIdentifier = {
    ip,
    wallet: options.wallet,
    subscriptionTier: options.subscriptionTier,
    hasCredits: options.hasCredits,
  };

  const rateLimitCheck = await rateLimiter.checkLimit(identifier, options.endpoint);

  // Set rate limit headers for all requests
  const rateLimitHeaders = getRateLimitHeaders(rateLimitCheck);
  for (const [key, value] of Object.entries(rateLimitHeaders)) {
    res.setHeader(key, value);
  }

  if (!rateLimitCheck.allowed) {
    res.status(429).json({
      error: "Too Many Requests",
      message: "Rate limit exceeded",
      tier: rateLimitCheck.tier,
      limit: rateLimitCheck.limit,
      reset_at: new Date(rateLimitCheck.resetAt * 1000).toISOString(),
      retry_after: rateLimitCheck.retryAfter,
      upgrade_info: rateLimitCheck.tier === "free" ? {
        message: "Upgrade to Pro for unlimited requests",
        pricing_url: "/api/v1/price",
      } : undefined,
    });

    // Track failed auth for abuse detection
    await abusePrevention.trackFailedAuth(ip, options.wallet);

    // Log the rate-limited request
    const logFn = createLogFunction(rateLimitCheck);
    await logFn(429, "Rate limit exceeded");

    return {
      allowed: false,
      rateLimitResult: rateLimitCheck,
      abuseCheckResult: abuseCheck,
      ip,
      startTime,
      logSuccess: async () => {},
      logError: async () => {},
    };
  }

  // 3. Consume rate limit token
  const consumeResult = await rateLimiter.consume(identifier, options.endpoint);

  // Update headers with consumed values
  const updatedHeaders = getRateLimitHeaders(consumeResult);
  for (const [key, value] of Object.entries(updatedHeaders)) {
    res.setHeader(key, value);
  }

  // Create log functions
  const logSuccess = createLogFunction(consumeResult);
  const logError = async (statusCode: number, error: string) => {
    const responseTimeMs = Date.now() - startTime;

    // Track invalid requests for abuse detection
    if (statusCode === 400 || statusCode === 401 || statusCode === 402) {
      await abusePrevention.trackInvalidRequest(ip, error);
    }

    await requestLogger.logRequest({
      timestamp: startTime,
      ip,
      wallet: options.wallet,
      endpoint: options.endpoint,
      method: req.method || "GET",
      statusCode,
      responseTimeMs,
      rateLimitTier: consumeResult.tier,
      rateLimitRemaining: consumeResult.remaining,
      paymentMethod: options.paymentMethod,
      userAgent,
      error,
    });
  };

  return {
    allowed: true,
    rateLimitResult: consumeResult,
    abuseCheckResult: abuseCheck,
    ip,
    startTime,
    logSuccess,
    logError,
  };
}

// ============================================================================
// SIMPLIFIED WRAPPERS
// ============================================================================

/**
 * Quick protection check for free tier endpoints
 */
export async function protectFreeTier(
  req: VercelRequest,
  res: VercelResponse,
  endpoint: string
): Promise<ProtectionResult> {
  return protectEndpoint(req, res, {
    endpoint,
    paymentMethod: "free",
  });
}

/**
 * Protection check with wallet identification
 */
export async function protectWithWallet(
  req: VercelRequest,
  res: VercelResponse,
  endpoint: string,
  wallet: string,
  subscriptionTier?: SubscriptionTier,
  hasCredits?: boolean
): Promise<ProtectionResult> {
  return protectEndpoint(req, res, {
    endpoint,
    wallet,
    subscriptionTier,
    hasCredits,
    paymentMethod: subscriptionTier === "pro" || subscriptionTier === "enterprise"
      ? "subscription"
      : hasCredits
        ? "credits"
        : "free",
  });
}
