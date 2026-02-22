"""Inline keyboards for Subasto Telegram bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional

from .config import config


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard with primary actions."""
    keyboard = [
        [
            InlineKeyboardButton("🔍 Buscar", callback_data="menu:search"),
            InlineKeyboardButton("📂 Categorias", callback_data="menu:categories"),
        ],
        [
            InlineKeyboardButton("⏰ Por vencer", callback_data="menu:ending"),
            InlineKeyboardButton("🔥 Oportunidades", callback_data="menu:hot"),
        ],
        [
            InlineKeyboardButton("⭐ Mi Watchlist", callback_data="menu:watchlist"),
            InlineKeyboardButton("🔔 Alertas", callback_data="menu:alerts"),
        ],
        [
            InlineKeyboardButton("📊 Estadisticas", callback_data="menu:stats"),
            InlineKeyboardButton("❓ Ayuda", callback_data="menu:help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def categories_keyboard() -> InlineKeyboardMarkup:
    """Category selection keyboard."""
    keyboard = []
    row = []

    for cat_id, cat_info in config.categories.items():
        btn = InlineKeyboardButton(
            f"{cat_info['emoji']} {cat_info['name']}",
            callback_data=f"cat:{cat_id}"
        )
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # Back button
    keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu:main")])

    return InlineKeyboardMarkup(keyboard)


def sources_keyboard(source_type: str = "all") -> InlineKeyboardMarkup:
    """Source selection keyboard."""
    keyboard = []

    if source_type in ("all", "judicial"):
        keyboard.append([InlineKeyboardButton("⚖️ JUDICIALES", callback_data="noop")])
        for source_id, source_name in config.sources["judicial"].items():
            keyboard.append([
                InlineKeyboardButton(f"  {source_name}", callback_data=f"source:{source_id}")
            ])

    if source_type in ("all", "private"):
        keyboard.append([InlineKeyboardButton("🏢 PRIVADAS", callback_data="noop")])
        row = []
        for source_id, source_name in config.sources["private"].items():
            btn = InlineKeyboardButton(source_name[:12], callback_data=f"source:{source_id}")
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

    keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu:main")])

    return InlineKeyboardMarkup(keyboard)


def listing_keyboard(listing_id: str, source_url: str, in_watchlist: bool = False) -> InlineKeyboardMarkup:
    """Keyboard for a single listing."""
    watchlist_btn = (
        InlineKeyboardButton("❌ Quitar de Watchlist", callback_data=f"unwatch:{listing_id}")
        if in_watchlist
        else InlineKeyboardButton("⭐ Agregar a Watchlist", callback_data=f"watch:{listing_id}")
    )

    keyboard = [
        [
            InlineKeyboardButton("🔗 Ver subasta", url=source_url),
        ],
        [
            watchlist_btn,
            InlineKeyboardButton("📤 Compartir", callback_data=f"share:{listing_id}"),
        ],
        [
            InlineKeyboardButton("◀️ Volver", callback_data="menu:main"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str,
    context_data: str = ""
) -> InlineKeyboardMarkup:
    """Pagination keyboard for listing results."""
    keyboard = []
    nav_row = []

    # Previous button
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            "◀️ Anterior",
            callback_data=f"page:{prefix}:{current_page - 1}:{context_data}"
        ))

    # Page indicator
    nav_row.append(InlineKeyboardButton(
        f"{current_page}/{total_pages}",
        callback_data="noop"
    ))

    # Next button
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            "Siguiente ▶️",
            callback_data=f"page:{prefix}:{current_page + 1}:{context_data}"
        ))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("◀️ Volver al menu", callback_data="menu:main")])

    return InlineKeyboardMarkup(keyboard)


def alert_settings_keyboard(
    has_daily_digest: bool = False,
    has_instant_alerts: bool = False,
    digest_hour: int = 9
) -> InlineKeyboardMarkup:
    """Alert settings keyboard."""
    digest_status = "✅" if has_daily_digest else "❌"
    instant_status = "✅" if has_instant_alerts else "❌"

    keyboard = [
        [InlineKeyboardButton(
            f"{digest_status} Resumen diario ({digest_hour}:00)",
            callback_data="alert:toggle_digest"
        )],
        [InlineKeyboardButton(
            f"{instant_status} Alertas instantaneas",
            callback_data="alert:toggle_instant"
        )],
        [InlineKeyboardButton(
            "⏰ Cambiar hora del resumen",
            callback_data="alert:change_hour"
        )],
        [InlineKeyboardButton(
            "🎯 Configurar filtros",
            callback_data="alert:filters"
        )],
        [InlineKeyboardButton("◀️ Volver", callback_data="menu:main")],
    ]

    return InlineKeyboardMarkup(keyboard)


def alert_filters_keyboard(
    selected_categories: list[str],
    min_discount: Optional[int] = None,
    max_price_usd: Optional[int] = None
) -> InlineKeyboardMarkup:
    """Alert filter configuration keyboard."""
    keyboard = []

    # Category toggles
    keyboard.append([InlineKeyboardButton("📂 Categorias:", callback_data="noop")])
    row = []
    for cat_id, cat_info in config.categories.items():
        status = "✅" if cat_id in selected_categories else "⬜"
        btn = InlineKeyboardButton(
            f"{status} {cat_info['emoji']}",
            callback_data=f"filter:cat:{cat_id}"
        )
        row.append(btn)
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Price filter
    price_text = f"${max_price_usd:,} USD" if max_price_usd else "Sin limite"
    keyboard.append([InlineKeyboardButton(
        f"💰 Precio max: {price_text}",
        callback_data="filter:price"
    )])

    # Discount filter
    discount_text = f"{min_discount}%+" if min_discount else "Sin minimo"
    keyboard.append([InlineKeyboardButton(
        f"📉 Descuento min: {discount_text}",
        callback_data="filter:discount"
    )])

    keyboard.append([InlineKeyboardButton("💾 Guardar", callback_data="filter:save")])
    keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu:alerts")])

    return InlineKeyboardMarkup(keyboard)


def hour_selection_keyboard() -> InlineKeyboardMarkup:
    """Hour selection for daily digest."""
    keyboard = []
    row = []

    for hour in range(6, 22):  # 6 AM to 9 PM
        btn = InlineKeyboardButton(f"{hour}:00", callback_data=f"hour:{hour}")
        row.append(btn)
        if len(row) == 4:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("◀️ Cancelar", callback_data="menu:alerts")])

    return InlineKeyboardMarkup(keyboard)


def watchlist_keyboard(items: list[dict], page: int = 1, per_page: int = 5) -> InlineKeyboardMarkup:
    """Watchlist display with item selection."""
    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]
    total_pages = (len(items) + per_page - 1) // per_page

    keyboard = []

    for item in page_items:
        # Truncate title to fit
        title = item.get("title", "")[:30]
        if len(item.get("title", "")) > 30:
            title += "..."

        keyboard.append([InlineKeyboardButton(
            f"🔹 {title}",
            callback_data=f"wl_item:{item['id']}"
        )])

    # Pagination
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"wl_page:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"wl_page:{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton("🗑️ Limpiar todo", callback_data="wl:clear"),
        InlineKeyboardButton("◀️ Menu", callback_data="menu:main"),
    ])

    return InlineKeyboardMarkup(keyboard)


def confirm_keyboard(action: str, item_id: str = "") -> InlineKeyboardMarkup:
    """Confirmation keyboard for destructive actions."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Si, confirmar", callback_data=f"confirm:{action}:{item_id}"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def price_filter_keyboard() -> InlineKeyboardMarkup:
    """Quick price filter selection."""
    keyboard = [
        [
            InlineKeyboardButton("$1,000", callback_data="price:1000"),
            InlineKeyboardButton("$5,000", callback_data="price:5000"),
            InlineKeyboardButton("$10,000", callback_data="price:10000"),
        ],
        [
            InlineKeyboardButton("$25,000", callback_data="price:25000"),
            InlineKeyboardButton("$50,000", callback_data="price:50000"),
            InlineKeyboardButton("$100,000", callback_data="price:100000"),
        ],
        [
            InlineKeyboardButton("Sin limite", callback_data="price:0"),
        ],
        [InlineKeyboardButton("◀️ Volver", callback_data="menu:alerts")],
    ]
    return InlineKeyboardMarkup(keyboard)


def discount_filter_keyboard() -> InlineKeyboardMarkup:
    """Quick discount filter selection."""
    keyboard = [
        [
            InlineKeyboardButton("20%+", callback_data="discount:20"),
            InlineKeyboardButton("30%+", callback_data="discount:30"),
            InlineKeyboardButton("40%+", callback_data="discount:40"),
        ],
        [
            InlineKeyboardButton("50%+", callback_data="discount:50"),
            InlineKeyboardButton("60%+", callback_data="discount:60"),
            InlineKeyboardButton("70%+", callback_data="discount:70"),
        ],
        [
            InlineKeyboardButton("Sin minimo", callback_data="discount:0"),
        ],
        [InlineKeyboardButton("◀️ Volver", callback_data="menu:alerts")],
    ]
    return InlineKeyboardMarkup(keyboard)
