# Environment Variables for Rate Limiting & Abuse Prevention

## Required for Production

### Upstash Redis (Rate Limiting & Monitoring)
```
UPSTASH_REDIS_REST_URL=https://your-redis.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-token-here
```

Get these from [Upstash Console](https://console.upstash.com/). Free tier includes 10,000 commands/day.

### Stats API Protection
```
STATS_API_KEY=your-secure-random-key
```

Generate with: `openssl rand -hex 32`

## Optional

### CAPTCHA (for suspicious requests)
```
# Provider: "hcaptcha" | "turnstile" | "none"
CAPTCHA_PROVIDER=none

# hCaptcha
HCAPTCHA_SITE_KEY=your-site-key
HCAPTCHA_SECRET=your-secret-key

# Cloudflare Turnstile
TURNSTILE_SITE_KEY=your-site-key
TURNSTILE_SECRET=your-secret-key
```

### Existing Variables
```
PAYMENT_WALLET=0x... (your USDC receiving wallet)
```

## Rate Limit Tiers

| Tier | Limit | Window |
|------|-------|--------|
| Free | 100 requests | 24 hours |
| Paid (credits) | 1000 requests | 1 hour |
| Premium (Pro/Enterprise) | Unlimited | - |

## API Headers

All responses include rate limit headers:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in window
- `X-RateLimit-Reset`: Unix timestamp when limit resets
- `X-RateLimit-Tier`: Current tier (free/paid/premium)
- `Retry-After`: Seconds until next request allowed (when rate limited)

## Monitoring Endpoint

```
GET /api/v1/stats
Authorization: Bearer YOUR_STATS_API_KEY

# Options
?dashboard=true   # Full dashboard data
?alerts=true      # Security alerts
?errors=true      # Recent errors
?requests=true    # Recent requests
?date=2024-01-15  # Stats for specific date
```
