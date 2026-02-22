"""Message formatters for Subasto Telegram bot."""

from datetime import datetime, timezone
from typing import Optional

from .config import config


def format_price(amount: float, currency: str, blue_rate: float = 1430) -> str:
    """Format price with currency."""
    if currency == "ARS":
        usd_equiv = amount / blue_rate
        return f"${amount:,.0f} ARS (~USD ${usd_equiv:,.0f})"
    else:
        return f"USD ${amount:,.0f}"


def format_time_remaining(ends_at: str) -> str:
    """Format time remaining until auction ends."""
    try:
        if isinstance(ends_at, str):
            end_dt = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
        else:
            end_dt = ends_at

        now = datetime.now(timezone.utc)
        delta = end_dt - now

        if delta.total_seconds() < 0:
            return "Finalizada"

        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    except Exception:
        return "N/A"


def format_listing_short(listing: dict, blue_rate: float = 1430) -> str:
    """Format listing for list display (compact)."""
    title = listing.get("title", "Sin titulo")[:40]
    if len(listing.get("title", "")) > 40:
        title += "..."

    price = format_price(
        listing.get("base_price", 0),
        listing.get("currency", "ARS"),
        blue_rate
    )

    # Category emoji
    cat = listing.get("category", "other")
    cat_info = config.categories.get(cat, {"emoji": "🔷"})
    emoji = cat_info["emoji"]

    # Source indicator
    source = listing.get("source", "")
    is_judicial = source in config.sources.get("judicial", {})
    source_badge = "⚖️" if is_judicial else "🏢"

    # Time remaining
    ends_at = listing.get("ends_at")
    time_str = format_time_remaining(ends_at) if ends_at else ""

    lines = [
        f"{emoji} *{title}*",
        f"💰 {price}",
    ]

    if time_str:
        lines.append(f"⏱ {time_str} | {source_badge} {source}")
    else:
        lines.append(f"{source_badge} {source}")

    return "\n".join(lines)


def format_listing_detail(listing: dict, blue_rate: float = 1430) -> str:
    """Format listing for detailed view."""
    title = listing.get("title", "Sin titulo")
    description = listing.get("description", "")[:300]
    if len(listing.get("description", "")) > 300:
        description += "..."

    price = format_price(
        listing.get("base_price", 0),
        listing.get("currency", "ARS"),
        blue_rate
    )

    # Category
    cat = listing.get("category", "other")
    cat_info = config.categories.get(cat, {"emoji": "🔷", "name": "Otro"})

    # Source
    source = listing.get("source", "")
    is_judicial = source in config.sources.get("judicial", {})
    source_type = "Judicial" if is_judicial else "Privada"

    # Location
    location = listing.get("location", {})
    location_str = ""
    if location.get("province"):
        location_str = location.get("province", "")
        if location.get("city"):
            location_str += f", {location['city']}"

    # Time
    ends_at = listing.get("ends_at")
    time_str = format_time_remaining(ends_at) if ends_at else "Sin fecha"

    # Discount
    discount = listing.get("discount_percent")
    discount_str = f"📉 *{discount:.0f}% descuento*\n" if discount else ""

    lines = [
        f"*{title}*",
        "",
        f"💰 *Precio:* {price}",
        discount_str,
        f"📂 *Categoria:* {cat_info['emoji']} {cat_info['name']}",
        f"🏛 *Fuente:* {source} ({source_type})",
    ]

    if location_str:
        lines.append(f"📍 *Ubicacion:* {location_str}")

    lines.append(f"⏱ *Tiempo restante:* {time_str}")

    if description:
        lines.append("")
        lines.append(f"📝 _{description}_")

    return "\n".join(lines)


def format_hot_item(item: dict) -> str:
    """Format hot list item."""
    title = item.get("title", "")[:50]
    if len(item.get("title", "")) > 50:
        title += "..."

    price = item.get("price", "N/A")
    discount = item.get("discount_percent", 0)

    cat = item.get("category", "other")
    cat_info = config.categories.get(cat, {"emoji": "🔷"})

    lines = [
        f"🔥 *{title}*",
        f"💰 {price}",
    ]

    if discount:
        lines.append(f"📉 *{discount:.0f}% descuento*")

    days = item.get("days_until_end", 999)
    if days < 999:
        lines.append(f"⏱ {days} dias")

    return "\n".join(lines)


def format_stats(stats: dict) -> str:
    """Format statistics message."""
    lines = [
        "📊 *Estadisticas de Subasto*",
        "",
        f"📋 *Total subastas:* {stats.get('total_count', 0):,}",
        f"💵 *Dolar Blue:* ${stats.get('blue_dollar_rate', 0):,.0f}",
        f"🔥 *Oportunidades:* {stats.get('opportunity_count', 0)}",
        f"⭐ *Premium:* {stats.get('premium_count', 0)}",
        "",
        "*Por Fuente:*",
    ]

    by_source = stats.get("by_source", {})
    # Sort by count descending
    sorted_sources = sorted(by_source.items(), key=lambda x: x[1], reverse=True)

    for source, count in sorted_sources[:8]:
        is_judicial = source in config.sources.get("judicial", {})
        badge = "⚖️" if is_judicial else "🏢"
        lines.append(f"  {badge} {source}: {count}")

    lines.append("")
    lines.append("*Por Categoria:*")

    by_cat = stats.get("by_category", {})
    for cat, count in by_cat.items():
        cat_info = config.categories.get(cat, {"emoji": "🔷", "name": cat})
        lines.append(f"  {cat_info['emoji']} {cat_info['name']}: {count}")

    # Last update
    generated = stats.get("generated_at", "")
    if generated:
        try:
            dt = datetime.fromisoformat(generated.replace("Z", "+00:00"))
            lines.append("")
            lines.append(f"🕐 Actualizado: {dt.strftime('%d/%m/%Y %H:%M')} UTC")
        except Exception:
            pass

    return "\n".join(lines)


def format_watchlist_item(listing: dict, blue_rate: float = 1430) -> str:
    """Format watchlist item with ending soon warning."""
    base = format_listing_short(listing, blue_rate)

    # Check if ending soon (< 24h)
    ends_at = listing.get("ends_at")
    if ends_at:
        try:
            if isinstance(ends_at, str):
                end_dt = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
            else:
                end_dt = ends_at

            now = datetime.now(timezone.utc)
            delta = end_dt - now

            if 0 < delta.total_seconds() < 86400:  # Less than 24h
                return f"⚠️ *POR VENCER*\n{base}"
        except Exception:
            pass

    return base


def format_welcome() -> str:
    """Format welcome message."""
    return """🎯 *Bienvenido a Subasto Bot*

Encontra las mejores oportunidades en subastas judiciales y privadas de Argentina.

*850+ subastas* de *14 fuentes* actualizadas diariamente.

*Comandos disponibles:*
/buscar `[texto]` - Buscar subastas
/categoria `[tipo]` - Ver por categoria
/vencer - Subastas por terminar (24h)
/oportunidades - Ofertas con descuento
/watchlist - Tu lista de seguimiento
/alertas - Configurar notificaciones
/stats - Ver estadisticas
/ayuda - Ver ayuda completa

*Tip:* Las subastas judiciales ⚖️ suelen tener mejores precios que las privadas 🏢

🔗 Web: subasto.com.ar"""


def format_help() -> str:
    """Format help message."""
    return """❓ *Ayuda de Subasto Bot*

*Busqueda:*
• `/buscar toyota` - Buscar "toyota"
• `/buscar -p 10000` - Buscar hasta USD 10,000
• `/categoria vehiculos` - Solo vehiculos

*Categorias disponibles:*
• `vehiculos` - Autos, motos, camiones
• `inmuebles` - Casas, deptos, terrenos
• `maquinaria` - Equipos industriales
• `general` - Bienes diversos
• `otros` - Miscelaneos

*Watchlist:*
• Agrega subastas para seguimiento
• Recibe alertas cuando estan por vencer
• Maximo 50 items

*Alertas:*
• *Resumen diario:* Top oportunidades a tu hora
• *Alertas instantaneas:* Nuevas subastas que coinciden con tus filtros
• Configura categorias, precio max, descuento min

*Fuentes judiciales ⚖️:*
CSJN, SCBA, Cordoba, Entre Rios
(Mejores precios, venta forzada)

*Fuentes privadas 🏢:*
Adrian Mercado, Banco Ciudad, y 8 mas

*Soporte:*
🔗 subasto.com.ar
📧 @josebarnetche en X/Twitter"""


def format_alert_digest(items: list[dict], blue_rate: float = 1430) -> str:
    """Format daily digest alert."""
    lines = [
        "🌅 *Tu resumen diario de Subasto*",
        "",
        f"Hoy tenemos *{len(items)}* oportunidades destacadas:",
        "",
    ]

    for i, item in enumerate(items[:5], 1):
        title = item.get("title", "")[:35]
        if len(item.get("title", "")) > 35:
            title += "..."

        price = item.get("price", "N/A")
        discount = item.get("discount_percent", 0)

        line = f"{i}. *{title}*\n   💰 {price}"
        if discount:
            line += f" | 📉 {discount:.0f}%"

        lines.append(line)
        lines.append("")

    lines.append("👉 Usa /oportunidades para ver todas")
    lines.append("🔗 subasto.com.ar")

    return "\n".join(lines)


def format_ending_soon_alert(items: list[dict], blue_rate: float = 1430) -> str:
    """Format ending soon alert for watchlist items."""
    lines = [
        "⚠️ *Subastas de tu watchlist por vencer!*",
        "",
    ]

    for item in items:
        title = item.get("title", "")[:35]
        if len(item.get("title", "")) > 35:
            title += "..."

        time_remaining = format_time_remaining(item.get("ends_at", ""))
        price = format_price(
            item.get("base_price", 0),
            item.get("currency", "ARS"),
            blue_rate
        )

        lines.append(f"🔔 *{title}*")
        lines.append(f"   ⏱ {time_remaining} | 💰 {price}")
        lines.append("")

    lines.append("No te las pierdas!")

    return "\n".join(lines)


def format_share_message(listing: dict, blue_rate: float = 1430) -> str:
    """Format message for sharing a listing."""
    title = listing.get("title", "Sin titulo")
    price = format_price(
        listing.get("base_price", 0),
        listing.get("currency", "ARS"),
        blue_rate
    )
    url = listing.get("source_url", "")

    discount = listing.get("discount_percent")
    discount_str = f" | {discount:.0f}% descuento" if discount else ""

    return f"""🎯 *{title}*

💰 {price}{discount_str}

🔗 {url}

Encontrado en Subasto - subasto.com.ar"""
