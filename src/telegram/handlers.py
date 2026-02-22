"""Command and callback handlers for Subasto Telegram bot."""

import logging
import re
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from uuid import uuid4

from .config import config
from .data import DataManager
from .keyboards import (
    main_menu_keyboard,
    categories_keyboard,
    sources_keyboard,
    listing_keyboard,
    pagination_keyboard,
    alert_settings_keyboard,
    alert_filters_keyboard,
    hour_selection_keyboard,
    watchlist_keyboard,
    confirm_keyboard,
    price_filter_keyboard,
    discount_filter_keyboard,
)
from .formatters import (
    format_listing_short,
    format_listing_detail,
    format_hot_item,
    format_stats,
    format_welcome,
    format_help,
    format_watchlist_item,
    format_share_message,
)

logger = logging.getLogger(__name__)


class BotHandlers:
    """Handles all bot commands and callbacks."""

    def __init__(self, data_manager: DataManager):
        self.data = data_manager

    def _get_blue_rate(self) -> float:
        """Get current blue dollar rate."""
        stats = self.data.get_stats()
        return stats.get("blue_dollar_rate", 1430)

    # Command handlers

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) started bot")

        # Initialize user preferences
        prefs = self.data.get_user_preferences(user.id)
        prefs.username = user.username
        self.data.save_user_preferences(prefs)

        await update.message.reply_text(
            format_welcome(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help or /ayuda command."""
        await update.message.reply_text(
            format_help(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /search or /buscar command."""
        query = " ".join(context.args) if context.args else ""

        # Parse price filter: -p 10000 or -precio 10000
        max_price = None
        price_match = re.search(r'-p(?:recio)?\s*(\d+)', query)
        if price_match:
            max_price = int(price_match.group(1))
            query = re.sub(r'-p(?:recio)?\s*\d+', '', query).strip()

        if not query and not max_price:
            await update.message.reply_text(
                "🔍 *Buscar subastas*\n\n"
                "Uso: `/buscar [texto]`\n"
                "Ejemplo: `/buscar toyota hilux`\n\n"
                "Filtros:\n"
                "• `-p 10000` - Precio max USD\n"
                "Ejemplo: `/buscar camioneta -p 15000`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        results = self.data.search_listings(
            query=query,
            max_price_usd=max_price,
            limit=config.max_results_per_search
        )

        if not results:
            await update.message.reply_text(
                f"No se encontraron resultados para '{query}'"
                + (f" (max USD ${max_price:,})" if max_price else ""),
                reply_markup=main_menu_keyboard(),
            )
            return

        blue_rate = self._get_blue_rate()
        message_lines = [f"🔍 *Resultados para '{query}'*"]
        if max_price:
            message_lines.append(f"💰 Max: USD ${max_price:,}")
        message_lines.append(f"📋 {len(results)} encontrados\n")

        for listing in results[:5]:
            message_lines.append(format_listing_short(listing, blue_rate))
            message_lines.append("")

        if len(results) > 5:
            message_lines.append(f"... y {len(results) - 5} mas")

        # Store search context for pagination
        context.user_data["last_search"] = {
            "query": query,
            "max_price": max_price,
            "page": 1,
        }

        await update.message.reply_text(
            "\n".join(message_lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=pagination_keyboard(1, (len(results) + 4) // 5, "search", query),
        )

    async def category_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /category or /categoria command."""
        cat_arg = context.args[0].lower() if context.args else None

        # Map Spanish names to category IDs
        cat_map = {
            "vehiculos": "vehicles",
            "vehicles": "vehicles",
            "inmuebles": "real_estate",
            "real_estate": "real_estate",
            "maquinaria": "machinery",
            "machinery": "machinery",
            "general": "general_goods",
            "general_goods": "general_goods",
            "otros": "other",
            "other": "other",
        }

        if not cat_arg or cat_arg not in cat_map:
            await update.message.reply_text(
                "📂 *Selecciona una categoria:*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=categories_keyboard(),
            )
            return

        category = cat_map[cat_arg]
        await self._show_category(update, context, category)

    async def _show_category(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str
    ) -> None:
        """Show listings for a category."""
        results = self.data.get_listings_by_category(category, limit=10)

        cat_info = config.categories.get(category, {"emoji": "🔷", "name": category})
        blue_rate = self._get_blue_rate()

        if not results:
            message = update.message or update.callback_query.message
            await message.reply_text(
                f"No hay subastas en {cat_info['emoji']} {cat_info['name']}",
                reply_markup=main_menu_keyboard(),
            )
            return

        message_lines = [
            f"{cat_info['emoji']} *{cat_info['name']}*",
            f"📋 {len(results)} subastas\n",
        ]

        for listing in results[:5]:
            message_lines.append(format_listing_short(listing, blue_rate))
            message_lines.append("")

        message = update.message or update.callback_query.message
        await message.reply_text(
            "\n".join(message_lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=pagination_keyboard(1, (len(results) + 4) // 5, "cat", category),
        )

    async def ending_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ending or /vencer command."""
        hours = 24
        if context.args:
            try:
                hours = int(context.args[0])
            except ValueError:
                pass

        results = self.data.get_ending_soon(hours=hours, limit=10)
        blue_rate = self._get_blue_rate()

        if not results:
            await update.message.reply_text(
                f"No hay subastas terminando en las proximas {hours} horas",
                reply_markup=main_menu_keyboard(),
            )
            return

        message_lines = [
            f"⏰ *Subastas terminando en {hours}h*",
            f"📋 {len(results)} encontradas\n",
        ]

        for listing in results[:5]:
            message_lines.append(format_listing_short(listing, blue_rate))
            message_lines.append("")

        await update.message.reply_text(
            "\n".join(message_lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )

    async def hot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /hot or /oportunidades command."""
        items = self.data.get_hot_list(limit=10)

        if not items:
            await update.message.reply_text(
                "No hay oportunidades destacadas en este momento",
                reply_markup=main_menu_keyboard(),
            )
            return

        message_lines = [
            "🔥 *Top Oportunidades*",
            "Descuentos del 40% al 90%+ vs mercado\n",
        ]

        for item in items[:5]:
            message_lines.append(format_hot_item(item))
            message_lines.append("")

        await update.message.reply_text(
            "\n".join(message_lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )

    async def watchlist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /watchlist command."""
        user_id = update.effective_user.id
        items = self.data.get_watchlist(user_id)

        if not items:
            await update.message.reply_text(
                "⭐ *Tu Watchlist esta vacia*\n\n"
                "Agrega subastas para seguirlas y recibir alertas cuando esten por vencer.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )
            return

        blue_rate = self._get_blue_rate()
        message_lines = [
            f"⭐ *Tu Watchlist* ({len(items)} items)\n",
        ]

        for item in items[:5]:
            message_lines.append(format_watchlist_item(item, blue_rate))
            message_lines.append("")

        await update.message.reply_text(
            "\n".join(message_lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=watchlist_keyboard(items),
        )

    async def watch_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /watch [id] command."""
        if not context.args:
            await update.message.reply_text(
                "Uso: `/watch [id_subasta]`\n"
                "Ejemplo: `/watch cordoba:25577`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        listing_id = context.args[0]
        user_id = update.effective_user.id

        listing = self.data.get_listing_by_id(listing_id)
        if not listing:
            await update.message.reply_text(
                f"No se encontro la subasta con ID: {listing_id}",
                reply_markup=main_menu_keyboard(),
            )
            return

        if self.data.add_to_watchlist(user_id, listing_id):
            await update.message.reply_text(
                f"✅ Agregado a tu watchlist:\n*{listing.get('title', '')}*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )
        else:
            if self.data.is_in_watchlist(user_id, listing_id):
                await update.message.reply_text(
                    "Ya esta en tu watchlist",
                    reply_markup=main_menu_keyboard(),
                )
            else:
                await update.message.reply_text(
                    f"Tu watchlist esta llena (max {config.max_watchlist_items} items)",
                    reply_markup=main_menu_keyboard(),
                )

    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /alerts or /alertas command."""
        user_id = update.effective_user.id
        prefs = self.data.get_user_preferences(user_id)

        await update.message.reply_text(
            "🔔 *Configuracion de Alertas*\n\n"
            "Configura como queres recibir notificaciones de nuevas subastas.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=alert_settings_keyboard(
                has_daily_digest=prefs.daily_digest_enabled,
                has_instant_alerts=prefs.instant_alerts_enabled,
                digest_hour=prefs.daily_digest_hour,
            ),
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command."""
        stats = self.data.get_stats()

        await update.message.reply_text(
            format_stats(stats),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )

    # Callback query handlers

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all callback queries."""
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = update.effective_user.id

        logger.debug(f"Callback from {user_id}: {data}")

        # Menu navigation
        if data == "menu:main":
            await query.edit_message_text(
                format_welcome(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )

        elif data == "menu:search":
            await query.edit_message_text(
                "🔍 *Buscar subastas*\n\n"
                "Envia un mensaje con tu busqueda o usa:\n"
                "`/buscar [texto]`\n\n"
                "Filtros:\n"
                "• `-p 10000` - Precio max USD",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )

        elif data == "menu:categories":
            await query.edit_message_text(
                "📂 *Selecciona una categoria:*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=categories_keyboard(),
            )

        elif data == "menu:ending":
            results = self.data.get_ending_soon(hours=24, limit=10)
            blue_rate = self._get_blue_rate()

            if not results:
                await query.edit_message_text(
                    "No hay subastas terminando en las proximas 24 horas",
                    reply_markup=main_menu_keyboard(),
                )
                return

            message_lines = [
                "⏰ *Subastas terminando en 24h*\n",
            ]
            for listing in results[:5]:
                message_lines.append(format_listing_short(listing, blue_rate))
                message_lines.append("")

            await query.edit_message_text(
                "\n".join(message_lines),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )

        elif data == "menu:hot":
            items = self.data.get_hot_list(limit=10)

            if not items:
                await query.edit_message_text(
                    "No hay oportunidades destacadas",
                    reply_markup=main_menu_keyboard(),
                )
                return

            message_lines = ["🔥 *Top Oportunidades*\n"]
            for item in items[:5]:
                message_lines.append(format_hot_item(item))
                message_lines.append("")

            await query.edit_message_text(
                "\n".join(message_lines),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )

        elif data == "menu:watchlist":
            items = self.data.get_watchlist(user_id)
            blue_rate = self._get_blue_rate()

            if not items:
                await query.edit_message_text(
                    "⭐ *Tu Watchlist esta vacia*\n\n"
                    "Agrega subastas para seguirlas.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_menu_keyboard(),
                )
                return

            message_lines = [f"⭐ *Tu Watchlist* ({len(items)} items)\n"]
            for item in items[:5]:
                message_lines.append(format_watchlist_item(item, blue_rate))
                message_lines.append("")

            await query.edit_message_text(
                "\n".join(message_lines),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=watchlist_keyboard(items),
            )

        elif data == "menu:alerts":
            prefs = self.data.get_user_preferences(user_id)
            await query.edit_message_text(
                "🔔 *Configuracion de Alertas*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=alert_settings_keyboard(
                    has_daily_digest=prefs.daily_digest_enabled,
                    has_instant_alerts=prefs.instant_alerts_enabled,
                    digest_hour=prefs.daily_digest_hour,
                ),
            )

        elif data == "menu:stats":
            stats = self.data.get_stats()
            await query.edit_message_text(
                format_stats(stats),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )

        elif data == "menu:help":
            await query.edit_message_text(
                format_help(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )

        # Category selection
        elif data.startswith("cat:"):
            category = data.split(":")[1]
            results = self.data.get_listings_by_category(category, limit=10)
            cat_info = config.categories.get(category, {"emoji": "🔷", "name": category})
            blue_rate = self._get_blue_rate()

            if not results:
                await query.edit_message_text(
                    f"No hay subastas en {cat_info['emoji']} {cat_info['name']}",
                    reply_markup=categories_keyboard(),
                )
                return

            message_lines = [
                f"{cat_info['emoji']} *{cat_info['name']}*",
                f"📋 {len(results)} subastas\n",
            ]
            for listing in results[:5]:
                message_lines.append(format_listing_short(listing, blue_rate))
                message_lines.append("")

            await query.edit_message_text(
                "\n".join(message_lines),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=pagination_keyboard(1, (len(results) + 4) // 5, "cat", category),
            )

        # Watch/unwatch
        elif data.startswith("watch:"):
            listing_id = data.split(":", 1)[1]
            listing = self.data.get_listing_by_id(listing_id)

            if listing and self.data.add_to_watchlist(user_id, listing_id):
                await query.edit_message_text(
                    f"✅ Agregado a tu watchlist:\n*{listing.get('title', '')}*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=listing_keyboard(
                        listing_id, listing.get("source_url", ""), in_watchlist=True
                    ),
                )

        elif data.startswith("unwatch:"):
            listing_id = data.split(":", 1)[1]
            self.data.remove_from_watchlist(user_id, listing_id)
            listing = self.data.get_listing_by_id(listing_id)

            if listing:
                await query.edit_message_text(
                    f"❌ Quitado de tu watchlist:\n*{listing.get('title', '')}*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=listing_keyboard(
                        listing_id, listing.get("source_url", ""), in_watchlist=False
                    ),
                )

        # Alert settings
        elif data == "alert:toggle_digest":
            prefs = self.data.get_user_preferences(user_id)
            prefs.daily_digest_enabled = not prefs.daily_digest_enabled
            self.data.save_user_preferences(prefs)

            status = "activado" if prefs.daily_digest_enabled else "desactivado"
            await query.answer(f"Resumen diario {status}")
            await query.edit_message_reply_markup(
                reply_markup=alert_settings_keyboard(
                    has_daily_digest=prefs.daily_digest_enabled,
                    has_instant_alerts=prefs.instant_alerts_enabled,
                    digest_hour=prefs.daily_digest_hour,
                ),
            )

        elif data == "alert:toggle_instant":
            prefs = self.data.get_user_preferences(user_id)
            prefs.instant_alerts_enabled = not prefs.instant_alerts_enabled
            self.data.save_user_preferences(prefs)

            status = "activadas" if prefs.instant_alerts_enabled else "desactivadas"
            await query.answer(f"Alertas instantaneas {status}")
            await query.edit_message_reply_markup(
                reply_markup=alert_settings_keyboard(
                    has_daily_digest=prefs.daily_digest_enabled,
                    has_instant_alerts=prefs.instant_alerts_enabled,
                    digest_hour=prefs.daily_digest_hour,
                ),
            )

        elif data == "alert:change_hour":
            await query.edit_message_text(
                "⏰ *Selecciona la hora del resumen diario*\n"
                "(Hora Argentina UTC-3)",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=hour_selection_keyboard(),
            )

        elif data.startswith("hour:"):
            hour = int(data.split(":")[1])
            prefs = self.data.get_user_preferences(user_id)
            prefs.daily_digest_hour = hour
            self.data.save_user_preferences(prefs)

            await query.answer(f"Resumen configurado para las {hour}:00")
            await query.edit_message_text(
                "🔔 *Configuracion de Alertas*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=alert_settings_keyboard(
                    has_daily_digest=prefs.daily_digest_enabled,
                    has_instant_alerts=prefs.instant_alerts_enabled,
                    digest_hour=prefs.daily_digest_hour,
                ),
            )

        elif data == "alert:filters":
            prefs = self.data.get_user_preferences(user_id)
            await query.edit_message_text(
                "🎯 *Filtros de Alertas*\n\n"
                "Configura que tipo de subastas queres recibir.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=alert_filters_keyboard(
                    selected_categories=prefs.alert_categories,
                    min_discount=prefs.alert_min_discount,
                    max_price_usd=prefs.alert_max_price_usd,
                ),
            )

        elif data.startswith("filter:cat:"):
            category = data.split(":")[2]
            prefs = self.data.get_user_preferences(user_id)

            if category in prefs.alert_categories:
                prefs.alert_categories.remove(category)
            else:
                prefs.alert_categories.append(category)

            self.data.save_user_preferences(prefs)

            await query.edit_message_reply_markup(
                reply_markup=alert_filters_keyboard(
                    selected_categories=prefs.alert_categories,
                    min_discount=prefs.alert_min_discount,
                    max_price_usd=prefs.alert_max_price_usd,
                ),
            )

        elif data == "filter:price":
            await query.edit_message_text(
                "💰 *Selecciona precio maximo (USD)*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=price_filter_keyboard(),
            )

        elif data.startswith("price:"):
            price = int(data.split(":")[1])
            prefs = self.data.get_user_preferences(user_id)
            prefs.alert_max_price_usd = price if price > 0 else None
            self.data.save_user_preferences(prefs)

            await query.answer(f"Precio max: ${price:,}" if price else "Sin limite")
            await query.edit_message_text(
                "🎯 *Filtros de Alertas*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=alert_filters_keyboard(
                    selected_categories=prefs.alert_categories,
                    min_discount=prefs.alert_min_discount,
                    max_price_usd=prefs.alert_max_price_usd,
                ),
            )

        elif data == "filter:discount":
            await query.edit_message_text(
                "📉 *Selecciona descuento minimo*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=discount_filter_keyboard(),
            )

        elif data.startswith("discount:"):
            discount = int(data.split(":")[1])
            prefs = self.data.get_user_preferences(user_id)
            prefs.alert_min_discount = discount if discount > 0 else None
            self.data.save_user_preferences(prefs)

            await query.answer(f"Descuento min: {discount}%+" if discount else "Sin minimo")
            await query.edit_message_text(
                "🎯 *Filtros de Alertas*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=alert_filters_keyboard(
                    selected_categories=prefs.alert_categories,
                    min_discount=prefs.alert_min_discount,
                    max_price_usd=prefs.alert_max_price_usd,
                ),
            )

        elif data == "filter:save":
            await query.answer("Filtros guardados!")
            prefs = self.data.get_user_preferences(user_id)
            await query.edit_message_text(
                "🔔 *Configuracion de Alertas*\n\n✅ Filtros guardados",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=alert_settings_keyboard(
                    has_daily_digest=prefs.daily_digest_enabled,
                    has_instant_alerts=prefs.instant_alerts_enabled,
                    digest_hour=prefs.daily_digest_hour,
                ),
            )

        # Watchlist clear
        elif data == "wl:clear":
            await query.edit_message_text(
                "⚠️ *Confirmar*\n\n¿Limpiar toda tu watchlist?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=confirm_keyboard("wl_clear"),
            )

        elif data == "confirm:wl_clear:":
            count = self.data.clear_watchlist(user_id)
            await query.edit_message_text(
                f"✅ Watchlist limpiada ({count} items eliminados)",
                reply_markup=main_menu_keyboard(),
            )

        elif data == "cancel":
            await query.edit_message_text(
                "❌ Accion cancelada",
                reply_markup=main_menu_keyboard(),
            )

        # Share
        elif data.startswith("share:"):
            listing_id = data.split(":", 1)[1]
            listing = self.data.get_listing_by_id(listing_id)

            if listing:
                blue_rate = self._get_blue_rate()
                share_text = format_share_message(listing, blue_rate)
                await query.message.reply_text(
                    share_text,
                    parse_mode=ParseMode.MARKDOWN,
                )

        # Watchlist item detail
        elif data.startswith("wl_item:"):
            listing_id = data.split(":", 1)[1]
            listing = self.data.get_listing_by_id(listing_id)

            if listing:
                blue_rate = self._get_blue_rate()
                await query.edit_message_text(
                    format_listing_detail(listing, blue_rate),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=listing_keyboard(
                        listing_id,
                        listing.get("source_url", ""),
                        in_watchlist=True,
                    ),
                )

        # No-op for headers
        elif data == "noop":
            pass

    # Inline query handler

    async def inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline queries for quick search."""
        query = update.inline_query.query

        if len(query) < 2:
            return

        results = self.data.search_listings(query=query, limit=5)
        blue_rate = self._get_blue_rate()

        inline_results = []

        for listing in results:
            title = listing.get("title", "Sin titulo")[:50]
            price = listing.get("base_price", 0)
            currency = listing.get("currency", "ARS")

            if currency == "ARS":
                price_str = f"${price:,.0f} ARS"
            else:
                price_str = f"USD ${price:,.0f}"

            description = f"{price_str} | {listing.get('source', '')}"

            # Full message content
            message_content = format_listing_detail(listing, blue_rate)

            inline_results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=title,
                    description=description,
                    input_message_content=InputTextMessageContent(
                        message_content,
                        parse_mode=ParseMode.MARKDOWN,
                    ),
                )
            )

        await update.inline_query.answer(inline_results, cache_time=60)

    # Message handler for text searches

    async def text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle plain text messages as searches."""
        text = update.message.text.strip()

        # Ignore if starts with /
        if text.startswith("/"):
            return

        # Treat as search query
        if len(text) >= 2:
            context.args = text.split()
            await self.search_command(update, context)
