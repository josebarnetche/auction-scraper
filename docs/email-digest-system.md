# Email Digest System for Subasto

This document describes the email digest system implementation for Subasto.com.ar.

## Overview

The email digest system allows users to receive personalized daily emails with the best auction opportunities, without needing to check the website every day.

## Architecture

```
User                API (Vercel)          Storage (KV)         Email (Resend/SendGrid)
  |                      |                     |                        |
  |--[Subscribe]-------->|                     |                        |
  |                      |--[Store pending]--->|                        |
  |                      |--[Send confirm]-----|----------------------->|
  |                      |                     |                        |
  |--[Confirm]---------->|                     |                        |
  |                      |--[Activate]-------->|                        |
  |                      |--[Welcome email]----|----------------------->|
  |                      |                     |                        |
  |                [Daily Job]                 |                        |
  |                      |--[Get active]------>|                        |
  |                      |<-[Subscribers]------|                        |
  |                      |--[Generate digest]--|                        |
  |                      |--[Send emails]------|----------------------->|
  |                      |                     |                        |
  |--[Unsubscribe]------>|                     |                        |
  |                      |--[Mark inactive]--->|                        |
```

## Components

### 1. API Endpoints (TypeScript/Vercel)

#### POST /api/v1/subscribe
- Creates a new subscriber with pending status
- Sends confirmation email (double opt-in)
- Accepts preferences (categories, price range, etc.)

#### GET /api/v1/subscribe?action=confirm&token=...
- Confirms subscription via unique token
- Activates subscriber

#### GET /api/v1/unsubscribe?token=...
- Shows unsubscribe confirmation page
- Supports GDPR data export/deletion

### 2. Storage (Vercel KV / Memory Fallback)

File: `api/lib/subscriber-store.ts`

Subscriber schema:
```typescript
interface Subscriber {
  email: string;
  emailHash: string;           // SHA256 for privacy
  createdAt: string;
  confirmedAt: string | null;
  confirmToken: string;
  unsubscribeToken: string;
  preferences: {
    categories: string[];      // vehicles, real_estate, machinery, general_goods
    provinces: string[];       // Buenos Aires, Cordoba, etc.
    priceMinUsd: number;
    priceMaxUsd: number;
    digestFrequency: "daily" | "weekly" | "realtime";
    endingTodayAlerts: boolean;
    opportunitiesOnly: boolean;
  };
  lastDigestSent: string | null;
  digestCount: number;
  bounceCount: number;
  status: "pending" | "active" | "unsubscribed" | "bounced";
}
```

### 3. Digest Generator (Python)

File: `src/email/digest_generator.py`

Generates personalized content based on:
- Subscriber preferences (categories, price range, location)
- Current listings data
- Market opportunities (discount percentages)
- Auctions ending today

Digest types:
- **Daily digest**: Top 10 opportunities matching preferences
- **Ending today**: Urgent alerts for auctions closing within 24 hours
- **Category digest**: Focused on a single category
- **Welcome email**: Onboarding with tips and samples

### 4. Email Sender (Python)

File: `src/email/sender.py`

Supports multiple providers:
- **Resend** (recommended): Modern email API, great deliverability
- **SendGrid**: Enterprise option
- **SMTP**: Fallback for any SMTP server

Configuration via environment variables:
```bash
EMAIL_PROVIDER=resend    # resend, sendgrid, smtp, dry_run
RESEND_API_KEY=re_...
SENDGRID_API_KEY=SG....
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=user@gmail.com
SMTP_PASS=app_password
```

### 5. Email Templates (Python)

File: `src/email/templates.py`

HTML templates with inline CSS for email client compatibility:
- Responsive design (mobile-friendly)
- Dark theme matching Subasto branding
- Price formatting (ARS/USD)
- Countdown badges for urgent auctions
- Discount badges for opportunities

### 6. Daily Job (GitHub Actions)

File: `.github/workflows/email-digest.yml`

Schedule:
- **Daily digest**: 11:00 UTC (08:00 Argentina)
- **Ending today alerts**: 14:00 UTC (11:00 Argentina)

Manual triggers available with options:
- Test email (send to specific address)
- Dry run (log without sending)
- Digest type selection

## Setup Guide

### 1. Environment Variables

Add to Vercel:
```
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_your_api_key
EMAIL_FROM=noreply@subasto.com.ar
EMAIL_FROM_NAME=Subasto
```

Add to GitHub Secrets:
```
RESEND_API_KEY=re_your_api_key
VERCEL_KV_REST_API_URL=https://your-kv.vercel-storage.com
VERCEL_KV_REST_API_TOKEN=your_token
```

### 2. Vercel KV Setup

1. Go to Vercel Dashboard > Storage > Create KV Database
2. Connect to your project
3. Copy REST API URL and token to secrets

### 3. Resend Setup

1. Sign up at resend.com
2. Verify your domain (subasto.com.ar)
3. Create API key
4. Add to environment variables

### 4. Frontend Integration

Add to `site/index.html` before the footer:
```html
<!-- Include the subscribe section -->
<!-- See site/partials/subscribe-section.html -->
```

## Compliance Features

### Double Opt-In
- Users must confirm email before receiving digests
- Prevents spam complaints and improves deliverability

### Easy Unsubscribe
- One-click unsubscribe in every email
- Unique token per subscriber (no login required)
- Confirmation page

### GDPR Compliance
- Data export: Users can download their data
- Right to deletion: Complete data removal option
- No tracking beyond basic stats
- Privacy-preserving email hashing

## Testing

### Local Testing
```bash
# Dry run (no emails sent)
python scripts/send_daily_digest.py --dry-run

# Send test to specific email
python scripts/send_daily_digest.py --test your@email.com

# Test ending today alerts
python scripts/send_daily_digest.py --ending-today --dry-run
```

### GitHub Actions Manual Trigger
1. Go to Actions > Daily Email Digest
2. Click "Run workflow"
3. Fill in options (test email, dry run, etc.)
4. Click "Run workflow"

## Metrics to Track

- Subscriber count (active, pending, unsubscribed)
- Digest open rate (requires tracking pixel)
- Click-through rate to auctions
- Unsubscribe rate
- Bounce rate

## Future Improvements

1. **Real-time alerts**: WebSocket/push notifications
2. **Weekly digest**: Summary of best opportunities
3. **Saved searches**: Custom alert criteria
4. **Price alerts**: Notify when specific items drop in price
5. **Mobile app**: Push notifications
6. **Telegram/WhatsApp**: Alternative delivery channels
