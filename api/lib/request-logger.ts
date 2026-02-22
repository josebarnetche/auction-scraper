/**
 * Request Logger and Monitoring for Subasto API
 *
 * Tracks all API requests for:
 * - Usage analytics
 * - Abuse detection
 * - Billing verification
 * - Performance monitoring
 *
 * Uses Upstash Redis for distributed logging.
 */

// ============================================================================
// TYPES
// ============================================================================

export interface RequestLog {
  id: string;
  timestamp: number;
  ip: string;
  wallet?: string;
  endpoint: string;
  method: string;
  statusCode: number;
  responseTimeMs: number;
  rateLimitTier: string;
  rateLimitRemaining: number;
  paymentMethod?: "free" | "credits" | "subscription" | "pay-per-use";
  userAgent?: string;
  country?: string;
  error?: string;
}

export interface UsageStats {
  total: number;
  byEndpoint: Record<string, number>;
  byStatusCode: Record<number, number>;
  byTier: Record<string, number>;
  byPaymentMethod: Record<string, number>;
  uniqueIPs: number;
  uniqueWallets: number;
  avgResponseTimeMs: number;
  errorRate: number;
}

export interface DashboardData {
  period: string;
  stats: UsageStats;
  topEndpoints: { endpoint: string; count: number }[];
  topUsers: { identifier: string; count: number }[];
  recentErrors: RequestLog[];
  alerts: { type: string; count: number }[];
}

// ============================================================================
// REDIS CLIENT
// ============================================================================

interface RedisClient {
  get(key: string): Promise<string | null>;
  set(key: string, value: string, options?: { ex?: number }): Promise<void>;
  incr(key: string): Promise<number>;
  incrby(key: string, amount: number): Promise<number>;
  hincrby(key: string, field: string, amount: number): Promise<number>;
  hgetall(key: string): Promise<Record<string, string>>;
  lpush(key: string, value: string): Promise<number>;
  ltrim(key: string, start: number, stop: number): Promise<void>;
  lrange(key: string, start: number, stop: number): Promise<string[]>;
  sadd(key: string, member: string): Promise<number>;
  scard(key: string): Promise<number>;
  expire(key: string, seconds: number): Promise<void>;
}

// In-memory fallback
class InMemoryStore implements RedisClient {
  private store = new Map<string, { value: any; expiresAt: number }>();
  private lists = new Map<string, string[]>();
  private hashes = new Map<string, Map<string, string>>();
  private sets = new Map<string, Set<string>>();

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
    return entry?.value || null;
  }

  async set(key: string, value: string, options?: { ex?: number }): Promise<void> {
    const expiresAt = options?.ex ? Date.now() + options.ex * 1000 : 0;
    this.store.set(key, { value, expiresAt });
  }

  async incr(key: string): Promise<number> {
    const current = await this.get(key);
    const newValue = current ? parseInt(current, 10) + 1 : 1;
    await this.set(key, String(newValue));
    return newValue;
  }

  async incrby(key: string, amount: number): Promise<number> {
    const current = await this.get(key);
    const newValue = current ? parseInt(current, 10) + amount : amount;
    await this.set(key, String(newValue));
    return newValue;
  }

  async hincrby(key: string, field: string, amount: number): Promise<number> {
    let hash = this.hashes.get(key);
    if (!hash) {
      hash = new Map();
      this.hashes.set(key, hash);
    }
    const current = parseInt(hash.get(field) || "0", 10);
    const newValue = current + amount;
    hash.set(field, String(newValue));
    return newValue;
  }

  async hgetall(key: string): Promise<Record<string, string>> {
    const hash = this.hashes.get(key);
    if (!hash) return {};
    return Object.fromEntries(hash.entries());
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

  async sadd(key: string, member: string): Promise<number> {
    let set = this.sets.get(key);
    if (!set) {
      set = new Set();
      this.sets.set(key, set);
    }
    const sizeBefore = set.size;
    set.add(member);
    return set.size - sizeBefore;
  }

  async scard(key: string): Promise<number> {
    const set = this.sets.get(key);
    return set?.size || 0;
  }

  async expire(key: string, seconds: number): Promise<void> {
    const entry = this.store.get(key);
    if (entry) {
      entry.expiresAt = Date.now() + seconds * 1000;
    }
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

  async incrby(key: string, amount: number): Promise<number> {
    return this.command(["INCRBY", key, String(amount)]);
  }

  async hincrby(key: string, field: string, amount: number): Promise<number> {
    return this.command(["HINCRBY", key, field, String(amount)]);
  }

  async hgetall(key: string): Promise<Record<string, string>> {
    const result = await this.command(["HGETALL", key]);
    if (!result || !Array.isArray(result)) return {};
    const obj: Record<string, string> = {};
    for (let i = 0; i < result.length; i += 2) {
      obj[result[i]] = result[i + 1];
    }
    return obj;
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

  async sadd(key: string, member: string): Promise<number> {
    return this.command(["SADD", key, member]);
  }

  async scard(key: string): Promise<number> {
    return this.command(["SCARD", key]);
  }

  async expire(key: string, seconds: number): Promise<void> {
    await this.command(["EXPIRE", key, String(seconds)]);
  }
}

// ============================================================================
// REQUEST LOGGER CLASS
// ============================================================================

export class RequestLogger {
  private redis: RedisClient;

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
   * Generate a unique request ID
   */
  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Get the current date key (for daily stats)
   */
  private getDateKey(): string {
    return new Date().toISOString().split("T")[0];
  }

  /**
   * Get the current hour key (for hourly stats)
   */
  private getHourKey(): string {
    const now = new Date();
    return `${now.toISOString().split("T")[0]}:${now.getUTCHours().toString().padStart(2, "0")}`;
  }

  /**
   * Log an API request
   */
  async logRequest(log: Omit<RequestLog, "id">): Promise<string> {
    const id = this.generateId();
    const fullLog: RequestLog = { ...log, id };
    const dateKey = this.getDateKey();
    const hourKey = this.getHourKey();

    try {
      // Store the full log (keep last 10000 logs)
      await this.redis.lpush("logs:requests", JSON.stringify(fullLog));
      await this.redis.ltrim("logs:requests", 0, 9999);

      // Update daily counters
      await this.redis.incr(`stats:daily:${dateKey}:total`);
      await this.redis.hincrby(`stats:daily:${dateKey}:endpoints`, log.endpoint, 1);
      await this.redis.hincrby(`stats:daily:${dateKey}:status`, String(log.statusCode), 1);
      await this.redis.hincrby(`stats:daily:${dateKey}:tier`, log.rateLimitTier, 1);

      if (log.paymentMethod) {
        await this.redis.hincrby(`stats:daily:${dateKey}:payment`, log.paymentMethod, 1);
      }

      // Track response time (store sum and count for average)
      await this.redis.incrby(`stats:daily:${dateKey}:responseTimeSum`, log.responseTimeMs);
      await this.redis.incr(`stats:daily:${dateKey}:responseTimeCount`);

      // Track unique IPs and wallets
      await this.redis.sadd(`stats:daily:${dateKey}:ips`, log.ip);
      if (log.wallet) {
        await this.redis.sadd(`stats:daily:${dateKey}:wallets`, log.wallet);
      }

      // Update hourly counters (for real-time monitoring)
      await this.redis.incr(`stats:hourly:${hourKey}:total`);
      await this.redis.expire(`stats:hourly:${hourKey}:total`, 86400); // Keep 24 hours

      // Store errors separately for quick access
      if (log.statusCode >= 400) {
        await this.redis.lpush("logs:errors", JSON.stringify(fullLog));
        await this.redis.ltrim("logs:errors", 0, 999);
      }

      // Set expiry on daily stats (keep 90 days)
      await this.redis.expire(`stats:daily:${dateKey}:total`, 86400 * 90);
      await this.redis.expire(`stats:daily:${dateKey}:endpoints`, 86400 * 90);
      await this.redis.expire(`stats:daily:${dateKey}:status`, 86400 * 90);
      await this.redis.expire(`stats:daily:${dateKey}:tier`, 86400 * 90);
      await this.redis.expire(`stats:daily:${dateKey}:payment`, 86400 * 90);
      await this.redis.expire(`stats:daily:${dateKey}:ips`, 86400 * 90);
      await this.redis.expire(`stats:daily:${dateKey}:wallets`, 86400 * 90);
    } catch (error) {
      console.error("Request logging error:", error);
    }

    return id;
  }

  /**
   * Get usage stats for a date
   */
  async getStats(date?: string): Promise<UsageStats> {
    const dateKey = date || this.getDateKey();

    try {
      const [
        total,
        endpoints,
        status,
        tier,
        payment,
        responseTimeSum,
        responseTimeCount,
        uniqueIPs,
        uniqueWallets,
      ] = await Promise.all([
        this.redis.get(`stats:daily:${dateKey}:total`),
        this.redis.hgetall(`stats:daily:${dateKey}:endpoints`),
        this.redis.hgetall(`stats:daily:${dateKey}:status`),
        this.redis.hgetall(`stats:daily:${dateKey}:tier`),
        this.redis.hgetall(`stats:daily:${dateKey}:payment`),
        this.redis.get(`stats:daily:${dateKey}:responseTimeSum`),
        this.redis.get(`stats:daily:${dateKey}:responseTimeCount`),
        this.redis.scard(`stats:daily:${dateKey}:ips`),
        this.redis.scard(`stats:daily:${dateKey}:wallets`),
      ]);

      const totalCount = parseInt(total || "0", 10);
      const rtSum = parseInt(responseTimeSum || "0", 10);
      const rtCount = parseInt(responseTimeCount || "1", 10);

      // Calculate error rate
      const statusCodes: Record<number, number> = {};
      let errorCount = 0;
      for (const [code, count] of Object.entries(status || {})) {
        const codeNum = parseInt(code, 10);
        const countNum = parseInt(count, 10);
        statusCodes[codeNum] = countNum;
        if (codeNum >= 400) errorCount += countNum;
      }

      return {
        total: totalCount,
        byEndpoint: Object.fromEntries(
          Object.entries(endpoints || {}).map(([k, v]) => [k, parseInt(v, 10)])
        ),
        byStatusCode: statusCodes,
        byTier: Object.fromEntries(
          Object.entries(tier || {}).map(([k, v]) => [k, parseInt(v, 10)])
        ),
        byPaymentMethod: Object.fromEntries(
          Object.entries(payment || {}).map(([k, v]) => [k, parseInt(v, 10)])
        ),
        uniqueIPs,
        uniqueWallets,
        avgResponseTimeMs: Math.round(rtSum / rtCount),
        errorRate: totalCount > 0 ? errorCount / totalCount : 0,
      };
    } catch (error) {
      console.error("Get stats error:", error);
      return {
        total: 0,
        byEndpoint: {},
        byStatusCode: {},
        byTier: {},
        byPaymentMethod: {},
        uniqueIPs: 0,
        uniqueWallets: 0,
        avgResponseTimeMs: 0,
        errorRate: 0,
      };
    }
  }

  /**
   * Get recent requests
   */
  async getRecentRequests(count: number = 100): Promise<RequestLog[]> {
    try {
      const logs = await this.redis.lrange("logs:requests", 0, count - 1);
      return logs.map((l) => JSON.parse(l));
    } catch (error) {
      console.error("Get recent requests error:", error);
      return [];
    }
  }

  /**
   * Get recent errors
   */
  async getRecentErrors(count: number = 50): Promise<RequestLog[]> {
    try {
      const logs = await this.redis.lrange("logs:errors", 0, count - 1);
      return logs.map((l) => JSON.parse(l));
    } catch (error) {
      console.error("Get recent errors error:", error);
      return [];
    }
  }

  /**
   * Get dashboard data
   */
  async getDashboard(date?: string): Promise<DashboardData> {
    const dateKey = date || this.getDateKey();

    try {
      const [stats, recentErrors] = await Promise.all([
        this.getStats(dateKey),
        this.getRecentErrors(10),
      ]);

      // Sort endpoints by count
      const topEndpoints = Object.entries(stats.byEndpoint)
        .map(([endpoint, count]) => ({ endpoint, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 10);

      return {
        period: dateKey,
        stats,
        topEndpoints,
        topUsers: [], // Would need additional tracking
        recentErrors,
        alerts: [], // Would come from abuse prevention
      };
    } catch (error) {
      console.error("Get dashboard error:", error);
      return {
        period: dateKey,
        stats: {
          total: 0,
          byEndpoint: {},
          byStatusCode: {},
          byTier: {},
          byPaymentMethod: {},
          uniqueIPs: 0,
          uniqueWallets: 0,
          avgResponseTimeMs: 0,
          errorRate: 0,
        },
        topEndpoints: [],
        topUsers: [],
        recentErrors: [],
        alerts: [],
      };
    }
  }

  /**
   * Alert if approaching limits
   */
  async checkApproachingLimits(
    ip: string,
    wallet: string | undefined,
    remaining: number,
    limit: number
  ): Promise<void> {
    if (limit <= 0) return; // Unlimited

    const percentUsed = 1 - remaining / limit;

    if (percentUsed >= 0.9) {
      console.warn(`Rate limit warning: ${wallet || ip} at ${Math.round(percentUsed * 100)}% of limit`);
      // Could send webhook/email alert here
    }
  }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

let requestLoggerInstance: RequestLogger | null = null;

export function getRequestLogger(): RequestLogger {
  if (!requestLoggerInstance) {
    requestLoggerInstance = new RequestLogger();
  }
  return requestLoggerInstance;
}
