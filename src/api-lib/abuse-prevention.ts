/**
 * Abuse Prevention System for Subasto API
 *
 * Detects and blocks abusive behavior:
 * - Known bad IP addresses/ranges
 * - Suspicious request patterns
 * - Rapid-fire requests (beyond rate limits)
 * - Invalid/malformed requests
 *
 * Uses Upstash Redis for distributed tracking.
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

// Known malicious IPs and ranges (add as needed)
// Format: exact IP or CIDR notation
export const BLOCKED_IPS: Set<string> = new Set([
  // Add known bad actors here
  // "1.2.3.4",
  // "5.6.7.0/24",
]);

// Known bad User-Agent patterns
export const BLOCKED_USER_AGENTS: RegExp[] = [
  /^$/,                           // Empty user agent
  /curl\/.*libcurl/i,             // Automated curl (allow normal curl)
  /python-requests.*\d+\.\d+\.\d+\.\d+$/i, // Bot-like python requests
  /Go-http-client/i,              // Likely bot
  /^Java\//i,                     // Generic Java client
];

// Suspicious patterns threshold
export const ABUSE_THRESHOLDS = {
  // Rapid requests (faster than human)
  rapidRequestsPerSecond: 10,
  rapidRequestWindow: 5, // seconds

  // Invalid requests (likely probing)
  invalidRequestsThreshold: 20,
  invalidRequestWindow: 300, // 5 minutes

  // Failed auth attempts
  failedAuthThreshold: 10,
  failedAuthWindow: 300, // 5 minutes

  // Block duration when abuse detected
  blockDurationSeconds: 3600, // 1 hour

  // Escalating blocks
  repeatOffenderMultiplier: 2,
  maxBlockDuration: 86400, // 24 hours
};

// ============================================================================
// TYPES
// ============================================================================

export interface AbuseCheckResult {
  allowed: boolean;
  reason?: string;
  blockExpires?: number;
  requiresCaptcha?: boolean;
}

export interface SuspiciousActivity {
  type: "rapid_requests" | "invalid_requests" | "failed_auth" | "pattern_abuse";
  ip: string;
  wallet?: string;
  count: number;
  window: number;
  timestamp: number;
}

export type AlertSeverity = "low" | "medium" | "high" | "critical";

export interface SecurityAlert {
  severity: AlertSeverity;
  type: string;
  message: string;
  ip: string;
  wallet?: string;
  details: Record<string, any>;
  timestamp: number;
}

// ============================================================================
// REDIS CLIENT INTERFACE
// ============================================================================

interface RedisClient {
  get(key: string): Promise<string | null>;
  set(key: string, value: string, options?: { ex?: number }): Promise<void>;
  incr(key: string): Promise<number>;
  expire(key: string, seconds: number): Promise<void>;
  lpush(key: string, value: string): Promise<number>;
  ltrim(key: string, start: number, stop: number): Promise<void>;
  lrange(key: string, start: number, stop: number): Promise<string[]>;
}

// In-memory fallback
class InMemoryStore implements RedisClient {
  private store = new Map<string, { value: string; expiresAt: number }>();
  private lists = new Map<string, string[]>();

  async get(key: string): Promise<string | null> {
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

  async lpush(key: string, value: string): Promise<number> {
    let list = this.lists.get(key) || [];
    list.unshift(value);
    this.lists.set(key, list);
    return list.length;
  }

  async ltrim(key: string, start: number, stop: number): Promise<void> {
    const list = this.lists.get(key);
    if (list) {
      this.lists.set(key, list.slice(start, stop + 1));
    }
  }

  async lrange(key: string, start: number, stop: number): Promise<string[]> {
    const list = this.lists.get(key) || [];
    return list.slice(start, stop === -1 ? undefined : stop + 1);
  }
}

// Upstash Redis client
class UpstashClient implements RedisClient {
  private url: string;
  private token: string;

  constructor(url: string, token: string) {
    this.url = url;
    this.token = token;
  }

  private async command(cmd: string[]): Promise<any> {
    const response = await fetch(this.url, {
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

  async lpush(key: string, value: string): Promise<number> {
    return this.command(["LPUSH", key, value]);
  }

  async ltrim(key: string, start: number, stop: number): Promise<void> {
    await this.command(["LTRIM", key, String(start), String(stop)]);
  }

  async lrange(key: string, start: number, stop: number): Promise<string[]> {
    return this.command(["LRANGE", key, String(start), String(stop)]);
  }
}

// ============================================================================
// ABUSE PREVENTION CLASS
// ============================================================================

export class AbusePrevention {
  private redis: RedisClient;
  private alertHandlers: ((alert: SecurityAlert) => void)[] = [];

  constructor() {
    const redisUrl = process.env.UPSTASH_REDIS_REST_URL;
    const redisToken = process.env.UPSTASH_REDIS_REST_TOKEN;

    if (redisUrl && redisToken) {
      this.redis = new UpstashClient(redisUrl, redisToken);
    } else {
      this.redis = new InMemoryStore();
    }
  }

  /**
   * Register an alert handler
   */
  onAlert(handler: (alert: SecurityAlert) => void): void {
    this.alertHandlers.push(handler);
  }

  /**
   * Send an alert to all handlers
   */
  private async sendAlert(alert: SecurityAlert): Promise<void> {
    // Store alert in Redis
    try {
      await this.redis.lpush("alerts:security", JSON.stringify(alert));
      await this.redis.ltrim("alerts:security", 0, 999); // Keep last 1000 alerts
    } catch (error) {
      console.error("Failed to store alert:", error);
    }

    // Call handlers
    for (const handler of this.alertHandlers) {
      try {
        handler(alert);
      } catch (error) {
        console.error("Alert handler error:", error);
      }
    }

    // Log to console
    console.warn(`[SECURITY ALERT] [${alert.severity.toUpperCase()}] ${alert.type}: ${alert.message}`, {
      ip: alert.ip,
      wallet: alert.wallet,
      details: alert.details,
    });
  }

  /**
   * Check if an IP is in the blocked list
   */
  isIPBlocked(ip: string): boolean {
    // Exact match
    if (BLOCKED_IPS.has(ip)) {
      return true;
    }

    // Check CIDR ranges (simplified - only /24 support for now)
    for (const blocked of BLOCKED_IPS) {
      if (blocked.includes("/24")) {
        const prefix = blocked.split("/")[0].split(".").slice(0, 3).join(".");
        const ipPrefix = ip.split(".").slice(0, 3).join(".");
        if (prefix === ipPrefix) {
          return true;
        }
      }
    }

    return false;
  }

  /**
   * Check if User-Agent is suspicious
   */
  isSuspiciousUserAgent(userAgent: string | undefined): boolean {
    if (!userAgent) return true; // Missing UA is suspicious

    for (const pattern of BLOCKED_USER_AGENTS) {
      if (pattern.test(userAgent)) {
        return true;
      }
    }

    return false;
  }

  /**
   * Check if IP is temporarily blocked due to abuse
   */
  async isTemporarilyBlocked(ip: string): Promise<{ blocked: boolean; expiresAt?: number }> {
    try {
      const blockKey = `block:${ip}`;
      const blockData = await this.redis.get(blockKey);

      if (blockData) {
        const { expiresAt, reason } = JSON.parse(blockData);
        return { blocked: true, expiresAt };
      }
    } catch (error) {
      console.error("Block check error:", error);
    }

    return { blocked: false };
  }

  /**
   * Temporarily block an IP
   */
  async blockIP(ip: string, reason: string, durationSeconds?: number): Promise<void> {
    const duration = durationSeconds || ABUSE_THRESHOLDS.blockDurationSeconds;
    const expiresAt = Date.now() + duration * 1000;

    try {
      const blockKey = `block:${ip}`;

      // Check for repeat offender
      const offenseCountKey = `offenses:${ip}`;
      const offenseCount = await this.redis.incr(offenseCountKey);
      await this.redis.expire(offenseCountKey, 86400 * 7); // Track for 7 days

      // Escalate block duration for repeat offenders
      let finalDuration = duration;
      if (offenseCount > 1) {
        finalDuration = Math.min(
          duration * Math.pow(ABUSE_THRESHOLDS.repeatOffenderMultiplier, offenseCount - 1),
          ABUSE_THRESHOLDS.maxBlockDuration
        );
      }

      await this.redis.set(
        blockKey,
        JSON.stringify({ expiresAt, reason, offenseCount }),
        { ex: finalDuration }
      );

      // Send alert
      await this.sendAlert({
        severity: offenseCount > 2 ? "high" : "medium",
        type: "ip_blocked",
        message: `IP blocked: ${reason}`,
        ip,
        details: {
          duration: finalDuration,
          offenseCount,
        },
        timestamp: Date.now(),
      });
    } catch (error) {
      console.error("Block IP error:", error);
    }
  }

  /**
   * Track rapid requests (potential DDoS or scraping)
   */
  async trackRapidRequests(ip: string): Promise<boolean> {
    const key = `rapid:${ip}`;
    const window = ABUSE_THRESHOLDS.rapidRequestWindow;

    try {
      const count = await this.redis.incr(key);

      if (count === 1) {
        await this.redis.expire(key, window);
      }

      const threshold = ABUSE_THRESHOLDS.rapidRequestsPerSecond * window;

      if (count > threshold) {
        await this.blockIP(ip, "Rapid-fire requests detected (potential DDoS/scraping)");
        return false; // Blocked
      }
    } catch (error) {
      console.error("Track rapid requests error:", error);
    }

    return true; // Allowed
  }

  /**
   * Track invalid requests (potential probing/scanning)
   */
  async trackInvalidRequest(ip: string, reason: string): Promise<boolean> {
    const key = `invalid:${ip}`;

    try {
      const count = await this.redis.incr(key);

      if (count === 1) {
        await this.redis.expire(key, ABUSE_THRESHOLDS.invalidRequestWindow);
      }

      if (count > ABUSE_THRESHOLDS.invalidRequestsThreshold) {
        await this.blockIP(ip, `Too many invalid requests: ${reason}`);
        return false;
      }

      // Alert on suspicious activity
      if (count === Math.floor(ABUSE_THRESHOLDS.invalidRequestsThreshold / 2)) {
        await this.sendAlert({
          severity: "low",
          type: "invalid_requests",
          message: `Multiple invalid requests from IP`,
          ip,
          details: { count, reason },
          timestamp: Date.now(),
        });
      }
    } catch (error) {
      console.error("Track invalid request error:", error);
    }

    return true;
  }

  /**
   * Track failed authentication attempts
   */
  async trackFailedAuth(ip: string, wallet?: string): Promise<boolean> {
    const key = `failedauth:${ip}`;

    try {
      const count = await this.redis.incr(key);

      if (count === 1) {
        await this.redis.expire(key, ABUSE_THRESHOLDS.failedAuthWindow);
      }

      if (count > ABUSE_THRESHOLDS.failedAuthThreshold) {
        await this.blockIP(ip, "Too many failed authentication attempts");

        await this.sendAlert({
          severity: "high",
          type: "brute_force_attempt",
          message: "Possible brute force attack detected",
          ip,
          wallet,
          details: { failedAttempts: count },
          timestamp: Date.now(),
        });

        return false;
      }
    } catch (error) {
      console.error("Track failed auth error:", error);
    }

    return true;
  }

  /**
   * Main abuse check - run this for every request
   */
  async checkRequest(
    ip: string,
    userAgent?: string,
    wallet?: string
  ): Promise<AbuseCheckResult> {
    // 1. Check static IP blocklist
    if (this.isIPBlocked(ip)) {
      return {
        allowed: false,
        reason: "IP address is blocked",
      };
    }

    // 2. Check temporary blocks
    const blockStatus = await this.isTemporarilyBlocked(ip);
    if (blockStatus.blocked) {
      return {
        allowed: false,
        reason: "Temporarily blocked due to suspicious activity",
        blockExpires: blockStatus.expiresAt,
      };
    }

    // 3. Check User-Agent
    if (this.isSuspiciousUserAgent(userAgent)) {
      await this.trackInvalidRequest(ip, "Suspicious User-Agent");
      // Don't block immediately, but track
    }

    // 4. Track rapid requests
    const rapidOk = await this.trackRapidRequests(ip);
    if (!rapidOk) {
      return {
        allowed: false,
        reason: "Rate limit exceeded - too many requests",
      };
    }

    return { allowed: true };
  }

  /**
   * Get recent security alerts
   */
  async getRecentAlerts(count: number = 100): Promise<SecurityAlert[]> {
    try {
      const alerts = await this.redis.lrange("alerts:security", 0, count - 1);
      return alerts.map((a) => JSON.parse(a));
    } catch (error) {
      console.error("Get alerts error:", error);
      return [];
    }
  }

  /**
   * Manually add an IP to the blocklist
   */
  addToBlocklist(ip: string): void {
    BLOCKED_IPS.add(ip);
  }

  /**
   * Remove an IP from the blocklist
   */
  removeFromBlocklist(ip: string): void {
    BLOCKED_IPS.delete(ip);
  }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

let abusePreventionInstance: AbusePrevention | null = null;

export function getAbusePrevention(): AbusePrevention {
  if (!abusePreventionInstance) {
    abusePreventionInstance = new AbusePrevention();
  }
  return abusePreventionInstance;
}
