#!/usr/bin/env python3
"""Setup Telegram webhook for production deployment.

Usage:
    # Set webhook
    python scripts/setup_telegram_webhook.py --url https://subasto.com.ar/api/telegram/webhook

    # Check webhook status
    python scripts/setup_telegram_webhook.py --status

    # Delete webhook (switch to polling)
    python scripts/setup_telegram_webhook.py --delete

Environment variables:
    TELEGRAM_BOT_TOKEN: Bot token from @BotFather (required)
"""

import argparse
import os
import sys
import httpx


def get_token() -> str:
    """Get bot token from environment."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set")
        sys.exit(1)
    return token


def set_webhook(url: str, token: str) -> None:
    """Set webhook URL."""
    api_url = f"https://api.telegram.org/bot{token}/setWebhook"

    response = httpx.post(api_url, json={
        "url": url,
        "allowed_updates": ["message", "callback_query", "inline_query"],
        "drop_pending_updates": True,
    })

    result = response.json()

    if result.get("ok"):
        print(f"Webhook set successfully!")
        print(f"URL: {url}")
    else:
        print(f"Error setting webhook: {result.get('description')}")
        sys.exit(1)


def get_webhook_info(token: str) -> None:
    """Get current webhook info."""
    api_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"

    response = httpx.get(api_url)
    result = response.json()

    if result.get("ok"):
        info = result.get("result", {})
        print("Webhook Info:")
        print(f"  URL: {info.get('url') or '(not set)'}")
        print(f"  Pending updates: {info.get('pending_update_count', 0)}")

        if info.get("last_error_date"):
            from datetime import datetime
            error_time = datetime.fromtimestamp(info["last_error_date"])
            print(f"  Last error: {error_time}")
            print(f"  Error message: {info.get('last_error_message')}")

        if info.get("ip_address"):
            print(f"  IP Address: {info.get('ip_address')}")

        allowed = info.get("allowed_updates", [])
        if allowed:
            print(f"  Allowed updates: {', '.join(allowed)}")
    else:
        print(f"Error getting webhook info: {result.get('description')}")
        sys.exit(1)


def delete_webhook(token: str) -> None:
    """Delete webhook (switch to polling mode)."""
    api_url = f"https://api.telegram.org/bot{token}/deleteWebhook"

    response = httpx.post(api_url, json={"drop_pending_updates": True})
    result = response.json()

    if result.get("ok"):
        print("Webhook deleted successfully!")
        print("Bot is now in polling mode.")
    else:
        print(f"Error deleting webhook: {result.get('description')}")
        sys.exit(1)


def get_bot_info(token: str) -> None:
    """Get bot information."""
    api_url = f"https://api.telegram.org/bot{token}/getMe"

    response = httpx.get(api_url)
    result = response.json()

    if result.get("ok"):
        bot = result.get("result", {})
        print("Bot Info:")
        print(f"  ID: {bot.get('id')}")
        print(f"  Username: @{bot.get('username')}")
        print(f"  Name: {bot.get('first_name')}")
        print(f"  Can join groups: {bot.get('can_join_groups')}")
        print(f"  Can read messages: {bot.get('can_read_all_group_messages')}")
        print(f"  Inline mode: {bot.get('supports_inline_queries')}")
    else:
        print(f"Error getting bot info: {result.get('description')}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Setup Telegram webhook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--url",
        type=str,
        help="Webhook URL (e.g., https://subasto.com.ar/api/telegram/webhook)"
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current webhook status"
    )

    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete webhook (switch to polling)"
    )

    parser.add_argument(
        "--info",
        action="store_true",
        help="Show bot information"
    )

    args = parser.parse_args()

    token = get_token()

    if args.info:
        get_bot_info(token)
        return

    if args.status:
        get_webhook_info(token)
        return

    if args.delete:
        delete_webhook(token)
        return

    if args.url:
        set_webhook(args.url, token)
        print()
        get_webhook_info(token)
        return

    # No action specified, show help
    parser.print_help()


if __name__ == "__main__":
    main()
