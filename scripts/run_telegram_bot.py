#!/usr/bin/env python3
"""Entry point for running the Subasto Telegram bot.

Usage:
    # Polling mode (development)
    python scripts/run_telegram_bot.py

    # Webhook mode (production)
    python scripts/run_telegram_bot.py --webhook --url https://your-domain.com

    # With custom port
    python scripts/run_telegram_bot.py --webhook --url https://your-domain.com --port 8443

Environment variables:
    TELEGRAM_BOT_TOKEN: Bot token from @BotFather (required)
    TELEGRAM_WEBHOOK_URL: Webhook URL (alternative to --url)
    TELEGRAM_WEBHOOK_PORT: Webhook port (alternative to --port)
"""

import argparse
import logging
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.telegram import SubastoBot


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
        ]
    )

    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(
        description="Run Subasto Telegram Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Development (polling)
    python scripts/run_telegram_bot.py

    # Production (webhook)
    python scripts/run_telegram_bot.py --webhook --url https://subasto.com.ar

    # Custom token
    TELEGRAM_BOT_TOKEN=your_token python scripts/run_telegram_bot.py
        """
    )

    parser.add_argument(
        "--webhook",
        action="store_true",
        help="Use webhook mode instead of polling"
    )

    parser.add_argument(
        "--url",
        type=str,
        default=os.getenv("TELEGRAM_WEBHOOK_URL"),
        help="Webhook URL (e.g., https://your-domain.com)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8443")),
        help="Port for webhook server (default: 8443)"
    )

    parser.add_argument(
        "--cert",
        type=str,
        help="Path to SSL certificate (for self-signed certs)"
    )

    parser.add_argument(
        "--key",
        type=str,
        help="Path to SSL private key"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--token",
        type=str,
        default=os.getenv("TELEGRAM_BOT_TOKEN"),
        help="Bot token (or set TELEGRAM_BOT_TOKEN env var)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Validate token
    if not args.token:
        logger.error(
            "Bot token required. Set TELEGRAM_BOT_TOKEN environment variable "
            "or use --token argument."
        )
        sys.exit(1)

    # Validate webhook URL if using webhook mode
    if args.webhook and not args.url:
        logger.error(
            "Webhook URL required in webhook mode. "
            "Use --url or set TELEGRAM_WEBHOOK_URL environment variable."
        )
        sys.exit(1)

    # Create and run bot
    try:
        bot = SubastoBot(
            token=args.token,
            base_path=str(project_root),
        )

        if args.webhook:
            logger.info(f"Starting webhook mode on port {args.port}")
            logger.info(f"Webhook URL: {args.url}")

            bot.run_webhook(
                webhook_url=args.url,
                port=args.port,
                cert_path=args.cert,
                key_path=args.key,
            )
        else:
            logger.info("Starting polling mode")
            bot.run_polling()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
