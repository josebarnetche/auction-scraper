# Subasto Telegram Bot

Telegram bot for browsing and receiving alerts for Argentine auctions.

## Features

- **Search**: Find auctions by keyword, category, or price
- **Categories**: Browse by vehicles, real estate, machinery, etc.
- **Watchlist**: Track auctions you're interested in
- **Alerts**: Daily digest and instant notifications
- **Inline Search**: Quick search from any chat using `@subasto_bot [query]`

## Quick Start

### 1. Create Bot with @BotFather

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow prompts to name your bot
4. Copy the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Configure Environment

```bash
# Set bot token
export TELEGRAM_BOT_TOKEN="your_bot_token_here"

# Optional: webhook URL for production
export TELEGRAM_WEBHOOK_URL="https://your-domain.com"
```

### 3. Install Dependencies

```bash
pip install python-telegram-bot>=20.0
```

### 4. Run the Bot

```bash
# Development (polling mode)
python scripts/run_telegram_bot.py

# Production (webhook mode)
python scripts/run_telegram_bot.py --webhook --url https://your-domain.com
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and menu |
| `/buscar [texto]` | Search auctions |
| `/categoria [tipo]` | Browse by category |
| `/vencer` | Auctions ending in 24h |
| `/oportunidades` | Hot deals with discounts |
| `/watchlist` | Your saved auctions |
| `/watch [id]` | Add to watchlist |
| `/alertas` | Configure notifications |
| `/stats` | Auction statistics |
| `/ayuda` | Help message |

### Search Examples

```
/buscar toyota hilux
/buscar camioneta -p 15000    # Max USD $15,000
/buscar maquinaria cordoba
```

### Category Options

- `vehiculos` - Cars, motorcycles, trucks
- `inmuebles` - Houses, apartments, land
- `maquinaria` - Industrial equipment
- `general` - General goods
- `otros` - Miscellaneous

## Alert System

### Daily Digest

Receive a summary of top opportunities at your preferred time.

1. Open `/alertas`
2. Enable "Resumen diario"
3. Set your preferred hour (Argentina time)
4. Configure category/price/discount filters

### Instant Alerts

Get notified immediately when new auctions match your criteria.

1. Open `/alertas`
2. Enable "Alertas instantaneas"
3. Configure filters for category, max price, min discount

### Watchlist Alerts

Automatically receive warnings when watched auctions are ending soon (within 2 hours).

## Inline Search

Search from any chat without opening the bot:

```
@subasto_bot toyota hilux
@subasto_bot departamento capital
```

Results appear as inline suggestions that can be shared directly.

## Deployment Options

### Option 1: Polling (Development)

Best for development and testing. Bot pulls updates from Telegram servers.

```bash
python scripts/run_telegram_bot.py
```

**Pros:**
- Simple setup
- Works behind NAT/firewall
- No SSL certificate needed

**Cons:**
- Slightly higher latency
- Must keep process running

### Option 2: Webhook (Production)

Best for production. Telegram pushes updates to your server.

```bash
python scripts/run_telegram_bot.py \
    --webhook \
    --url https://subasto.com.ar \
    --port 8443
```

**Requirements:**
- Public HTTPS URL
- Valid SSL certificate (Let's Encrypt works)
- Open port (443, 80, 88, or 8443)

### Option 3: Vercel Deployment

Deploy as serverless function on Vercel.

1. Create `api/telegram/webhook.py`:

```python
from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from telegram import Update
from src.telegram import SubastoBot

bot = SubastoBot(
    token=os.environ["TELEGRAM_BOT_TOKEN"],
    base_path=str(Path(__file__).parent.parent.parent),
)
app = bot.get_application()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        update = Update.de_json(json.loads(post_data), app.bot)

        import asyncio
        asyncio.run(app.process_update(update))

        self.send_response(200)
        self.end_headers()
```

2. Set environment variable in Vercel:
   - `TELEGRAM_BOT_TOKEN`

3. Set webhook URL:
```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://your-vercel-app.vercel.app/api/telegram/webhook"
```

## Architecture

```
src/telegram/
├── __init__.py       # Package exports
├── bot.py            # Main bot class
├── config.py         # Configuration
├── handlers.py       # Command/callback handlers
├── keyboards.py      # Inline keyboard builders
├── data.py           # Data access layer
├── formatters.py     # Message formatters
└── alerts.py         # Alert system

scripts/
└── run_telegram_bot.py   # Entry point
```

## Data Storage

User preferences are stored in JSON files:

```
data/telegram_users/
├── 123456789.json    # User preferences
├── 987654321.json
└── ...
```

Each file contains:
- Watchlist (list of auction IDs)
- Alert settings (digest enabled, hour, filters)
- Category/price/discount filters

## Security Notes

1. **Never commit bot token** - Use environment variables
2. **Webhook validation** - Telegram sends updates only from their IPs
3. **Rate limiting** - Built into python-telegram-bot library
4. **User data** - Stored locally, not synced to cloud

## Troubleshooting

### Bot not responding

1. Check token is correct
2. Verify bot is running (`ps aux | grep telegram`)
3. Check logs for errors

### Webhook not working

1. Verify HTTPS certificate is valid
2. Check URL is accessible from internet
3. Confirm port is open (443, 80, 88, or 8443)
4. Check webhook status:
   ```bash
   curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
   ```

### Missing listings data

1. Run scraper first: `python scripts/run_scraper.py`
2. Verify `site/api/listings.json` exists
3. Check file permissions

## Development

### Run tests

```bash
# TODO: Add tests
pytest tests/telegram/
```

### Add new command

1. Add handler method to `handlers.py`
2. Register in `bot.py` `_setup_handlers()`
3. Add to help message in `formatters.py`

### Add new keyboard

1. Create keyboard function in `keyboards.py`
2. Handle callbacks in `handlers.py` `callback_handler()`

## License

MIT - See LICENSE file
