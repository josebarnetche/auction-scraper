/**
 * CAPTCHA Verification for Suspicious Requests
 *
 * Integrates with hCaptcha or Cloudflare Turnstile for human verification.
 * Used when abuse prevention detects suspicious patterns.
 *
 * Environment variables:
 * - CAPTCHA_PROVIDER: "hcaptcha" | "turnstile" | "none"
 * - HCAPTCHA_SECRET: hCaptcha secret key
 * - TURNSTILE_SECRET: Cloudflare Turnstile secret key
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

export type CaptchaProvider = "hcaptcha" | "turnstile" | "none";

const PROVIDER = (process.env.CAPTCHA_PROVIDER || "none") as CaptchaProvider;
const HCAPTCHA_SECRET = process.env.HCAPTCHA_SECRET;
const TURNSTILE_SECRET = process.env.TURNSTILE_SECRET;

const HCAPTCHA_VERIFY_URL = "https://hcaptcha.com/siteverify";
const TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

// ============================================================================
// TYPES
// ============================================================================

export interface CaptchaResult {
  success: boolean;
  error?: string;
  score?: number; // 0-1, where 1 is definitely human
}

export interface CaptchaChallenge {
  required: boolean;
  provider: CaptchaProvider;
  siteKey?: string;
  message?: string;
}

// ============================================================================
// VERIFICATION
// ============================================================================

/**
 * Verify a CAPTCHA token
 */
export async function verifyCaptcha(
  token: string,
  ip?: string
): Promise<CaptchaResult> {
  if (PROVIDER === "none") {
    // CAPTCHA disabled - always pass
    return { success: true };
  }

  if (!token) {
    return { success: false, error: "CAPTCHA token required" };
  }

  try {
    if (PROVIDER === "hcaptcha") {
      return await verifyHCaptcha(token, ip);
    } else if (PROVIDER === "turnstile") {
      return await verifyTurnstile(token, ip);
    }

    return { success: false, error: "Unknown CAPTCHA provider" };
  } catch (error) {
    console.error("CAPTCHA verification error:", error);
    // Fail open on error - don't block legitimate users
    return { success: true, error: "Verification failed, allowing request" };
  }
}

/**
 * Verify hCaptcha token
 */
async function verifyHCaptcha(token: string, ip?: string): Promise<CaptchaResult> {
  if (!HCAPTCHA_SECRET) {
    console.warn("hCaptcha secret not configured");
    return { success: true };
  }

  const body = new URLSearchParams({
    secret: HCAPTCHA_SECRET,
    response: token,
  });

  if (ip) {
    body.append("remoteip", ip);
  }

  const response = await fetch(HCAPTCHA_VERIFY_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  const data = await response.json();

  if (data.success) {
    return { success: true, score: data.score };
  }

  return {
    success: false,
    error: data["error-codes"]?.join(", ") || "Verification failed",
  };
}

/**
 * Verify Cloudflare Turnstile token
 */
async function verifyTurnstile(token: string, ip?: string): Promise<CaptchaResult> {
  if (!TURNSTILE_SECRET) {
    console.warn("Turnstile secret not configured");
    return { success: true };
  }

  const body: Record<string, string> = {
    secret: TURNSTILE_SECRET,
    response: token,
  };

  if (ip) {
    body.remoteip = ip;
  }

  const response = await fetch(TURNSTILE_VERIFY_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await response.json();

  if (data.success) {
    return { success: true };
  }

  return {
    success: false,
    error: data["error-codes"]?.join(", ") || "Verification failed",
  };
}

// ============================================================================
// CHALLENGE GENERATION
// ============================================================================

/**
 * Generate a CAPTCHA challenge response for suspicious requests
 */
export function generateCaptchaChallenge(): CaptchaChallenge {
  if (PROVIDER === "none") {
    return { required: false, provider: "none" };
  }

  const siteKey =
    PROVIDER === "hcaptcha"
      ? process.env.HCAPTCHA_SITE_KEY
      : process.env.TURNSTILE_SITE_KEY;

  return {
    required: true,
    provider: PROVIDER,
    siteKey,
    message:
      "Please complete the CAPTCHA challenge to continue. " +
      "Add the token to your request as ?captcha=TOKEN",
  };
}

/**
 * Check if CAPTCHA is enabled
 */
export function isCaptchaEnabled(): boolean {
  return PROVIDER !== "none";
}

/**
 * Middleware helper to check CAPTCHA if required
 */
export async function checkCaptchaIfRequired(
  requiresCaptcha: boolean,
  token: string | undefined,
  ip: string
): Promise<{ pass: boolean; challenge?: CaptchaChallenge; error?: string }> {
  if (!requiresCaptcha || !isCaptchaEnabled()) {
    return { pass: true };
  }

  if (!token) {
    return {
      pass: false,
      challenge: generateCaptchaChallenge(),
    };
  }

  const result = await verifyCaptcha(token, ip);

  if (!result.success) {
    return {
      pass: false,
      error: result.error,
      challenge: generateCaptchaChallenge(),
    };
  }

  return { pass: true };
}
