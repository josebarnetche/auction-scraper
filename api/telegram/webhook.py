"""Vercel serverless function for Telegram webhook.

Deploy to Vercel and set webhook URL to:
https://your-app.vercel.app/api/telegram/webhook

Set environment variables in Vercel:
- TELEGRAM_BOT_TOKEN: Your bot token from @BotFather
"""

import json
import os
import sys
import logging
import asyncio
from pathlib import Path
from http.server import BaseHTTPRequestHandler

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lazy initialization of bot
_bot = None
_app = None


def get_bot():
    """Lazily initialize bot instance."""
    global _bot, _app

    if _bot is None:
        from telegram import Bot
        from telegram.ext import Application

        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

        # Create minimal application for webhook processing
        _app = Application.builder().token(token).build()

        # Import and setup handlers
        from src.telegram.data import DataManager
        from src.telegram.handlers import BotHandlers

        data_manager = DataManager(str(project_root))
        handlers = BotHandlers(data_manager)

        # Register handlers
        from telegram.ext import (
            CommandHandler,
            CallbackQueryHandler,
            InlineQueryHandler,
            MessageHandler,
            filters,
        )

        _app.add_handler(CommandHandler("start", handlers.start_command))
        _app.add_handler(CommandHandler(["help", "ayuda"], handlers.help_command))
        _app.add_handler(CommandHandler(["search", "buscar"], handlers.search_command))
        _app.add_handler(CommandHandler(["category", "categoria"], handlers.category_command))
        _app.add_handler(CommandHandler(["ending", "vencer"], handlers.ending_command))
        _app.add_handler(CommandHandler(["hot", "oportunidades"], handlers.hot_command))
        _app.add_handler(CommandHandler("watchlist", handlers.watchlist_command))
        _app.add_handler(CommandHandler("watch", handlers.watch_command))
        _app.add_handler(CommandHandler(["alerts", "alertas"], handlers.alerts_command))
        _app.add_handler(CommandHandler("stats", handlers.stats_command))
        _app.add_handler(CallbackQueryHandler(handlers.callback_handler))
        _app.add_handler(InlineQueryHandler(handlers.inline_query))
        _app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.text_message)
        )

        _bot = _app.bot
        logger.info("Bot initialized for webhook")

    return _app


async def process_update(update_data: dict) -> None:
    """Process a single update from Telegram."""
    from telegram import Update

    app = get_bot()
    update = Update.de_json(update_data, app.bot)

    # Initialize app if needed
    if not app._initialized:
        await app.initialize()

    # Process the update
    await app.process_update(update)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for Telegram webhook."""

    def do_POST(self):
        """Handle POST request from Telegram."""
        try:
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            # Parse JSON
            update_data = json.loads(body.decode("utf-8"))
            logger.info(f"Received update: {update_data.get('update_id')}")

            # Process update
            asyncio.run(process_update(update_data))

            # Send success response
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    def do_GET(self):
        """Handle GET request (health check)."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "service": "subasto-telegram-bot",
            "version": "1.0.0",
        }).encode())

    def log_message(self, format, *args):
        """Override to use Python logging."""
        logger.info("%s - %s", self.address_string(), format % args)
