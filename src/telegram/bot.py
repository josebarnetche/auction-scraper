"""Main Telegram bot for Subasto."""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

from .config import BotConfig, config
from .data import DataManager
from .handlers import BotHandlers
from .alerts import AlertManager

logger = logging.getLogger(__name__)


class SubastoBot:
    """Main Telegram bot class for Subasto auction aggregator."""

    def __init__(
        self,
        token: Optional[str] = None,
        base_path: str = ".",
        bot_config: Optional[BotConfig] = None,
    ):
        """Initialize the bot.

        Args:
            token: Telegram bot token. If not provided, uses TELEGRAM_BOT_TOKEN env var.
            base_path: Base path for data files.
            bot_config: Optional custom configuration.
        """
        self.config = bot_config or config
        self.token = token or self.config.token

        if not self.token:
            raise ValueError(
                "Bot token required. Set TELEGRAM_BOT_TOKEN environment variable "
                "or pass token parameter."
            )

        self.base_path = base_path
        self.data_manager = DataManager(base_path)
        self.handlers = BotHandlers(self.data_manager)
        self.alert_manager: Optional[AlertManager] = None
        self.application: Optional[Application] = None

    def _setup_handlers(self, app: Application) -> None:
        """Register all command and callback handlers."""

        # Command handlers
        app.add_handler(CommandHandler("start", self.handlers.start_command))
        app.add_handler(CommandHandler(["help", "ayuda"], self.handlers.help_command))
        app.add_handler(CommandHandler(["search", "buscar"], self.handlers.search_command))
        app.add_handler(CommandHandler(["category", "categoria"], self.handlers.category_command))
        app.add_handler(CommandHandler(["ending", "vencer"], self.handlers.ending_command))
        app.add_handler(CommandHandler(["hot", "oportunidades"], self.handlers.hot_command))
        app.add_handler(CommandHandler("watchlist", self.handlers.watchlist_command))
        app.add_handler(CommandHandler("watch", self.handlers.watch_command))
        app.add_handler(CommandHandler(["alerts", "alertas"], self.handlers.alerts_command))
        app.add_handler(CommandHandler("stats", self.handlers.stats_command))

        # Callback query handler (for inline keyboards)
        app.add_handler(CallbackQueryHandler(self.handlers.callback_handler))

        # Inline query handler (for @bot queries)
        app.add_handler(InlineQueryHandler(self.handlers.inline_query))

        # Text message handler (treat as search)
        app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handlers.text_message,
            )
        )

        logger.info("Bot handlers registered")

    async def _post_init(self, app: Application) -> None:
        """Post-initialization hook."""
        # Initialize alert manager
        self.alert_manager = AlertManager(app.bot, self.data_manager)
        await self.alert_manager.start()
        logger.info("Alert manager started")

    async def _pre_shutdown(self, app: Application) -> None:
        """Pre-shutdown hook."""
        if self.alert_manager:
            await self.alert_manager.stop()
            logger.info("Alert manager stopped")

    def run_polling(self) -> None:
        """Run the bot using long polling (for development)."""
        logger.info("Starting bot in polling mode...")

        self.application = (
            Application.builder()
            .token(self.token)
            .post_init(self._post_init)
            .post_shutdown(self._pre_shutdown)
            .build()
        )

        self._setup_handlers(self.application)

        # Run with polling
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

    def run_webhook(
        self,
        webhook_url: str,
        port: int = 8443,
        listen: str = "0.0.0.0",
        url_path: Optional[str] = None,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
    ) -> None:
        """Run the bot using webhook (for production).

        Args:
            webhook_url: Public URL for webhook (e.g., https://your-domain.com/webhook)
            port: Port to listen on
            listen: IP address to bind to
            url_path: URL path for webhook (defaults to token)
            cert_path: Path to SSL certificate (for self-signed)
            key_path: Path to SSL private key
        """
        logger.info(f"Starting bot in webhook mode on port {port}...")

        self.application = (
            Application.builder()
            .token(self.token)
            .post_init(self._post_init)
            .post_shutdown(self._pre_shutdown)
            .build()
        )

        self._setup_handlers(self.application)

        # Determine URL path
        if url_path is None:
            url_path = self.token

        # Run with webhook
        self.application.run_webhook(
            listen=listen,
            port=port,
            url_path=url_path,
            webhook_url=f"{webhook_url}/{url_path}",
            cert=cert_path,
            key=key_path,
            drop_pending_updates=True,
        )

    def get_application(self) -> Application:
        """Get the application instance for use with ASGI servers.

        Use this method when deploying to Vercel or other serverless platforms.

        Returns:
            Configured Application instance
        """
        if self.application is None:
            self.application = (
                Application.builder()
                .token(self.token)
                .build()
            )
            self._setup_handlers(self.application)

        return self.application


def create_bot(
    token: Optional[str] = None,
    base_path: str = ".",
) -> SubastoBot:
    """Factory function to create a SubastoBot instance.

    Args:
        token: Telegram bot token
        base_path: Base path for data files

    Returns:
        Configured SubastoBot instance
    """
    return SubastoBot(token=token, base_path=base_path)
