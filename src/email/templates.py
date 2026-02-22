"""
Email Templates for Subasto Digest System.

Generates HTML emails with inline CSS for maximum compatibility.
All templates are responsive and work in major email clients.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .digest_generator import DigestContent, DigestItem


# Base styles (inline CSS for email clients)
BASE_STYLES = """
<style>
  body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #030303; color: #ffffff; }
  .container { max-width: 600px; margin: 0 auto; padding: 20px; }
  .header { text-align: center; padding: 30px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }
  .logo { font-size: 28px; font-weight: 700; color: #eab308; text-decoration: none; }
  .hero { padding: 40px 20px; text-align: center; background: linear-gradient(135deg, rgba(234,179,8,0.1) 0%, rgba(234,179,8,0.05) 100%); border-radius: 12px; margin: 20px 0; }
  .hero h1 { margin: 0 0 10px 0; font-size: 24px; color: #fff; }
  .hero p { margin: 0; color: #a1a1aa; }
  .stats { display: flex; justify-content: center; gap: 30px; padding: 20px 0; }
  .stat { text-align: center; }
  .stat-value { font-size: 32px; font-weight: 700; color: #eab308; }
  .stat-label { font-size: 12px; color: #71717a; text-transform: uppercase; letter-spacing: 0.1em; }
  .section { margin: 30px 0; }
  .section-title { font-size: 18px; font-weight: 600; margin-bottom: 15px; color: #fff; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; }
  .card { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.08); }
  .card-row { display: flex; gap: 15px; }
  .card-image { width: 120px; height: 90px; border-radius: 8px; object-fit: cover; background: rgba(255,255,255,0.1); }
  .card-content { flex: 1; }
  .card-title { font-size: 16px; font-weight: 600; color: #fff; margin: 0 0 8px 0; line-height: 1.3; }
  .card-title a { color: #fff; text-decoration: none; }
  .card-title a:hover { color: #eab308; }
  .card-meta { font-size: 13px; color: #71717a; margin-bottom: 8px; }
  .card-price { font-size: 18px; font-weight: 700; color: #22c55e; }
  .card-discount { display: inline-block; background: rgba(34,197,94,0.2); color: #4ade80; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; margin-left: 8px; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
  .badge-vehicles { background: rgba(59,130,246,0.2); color: #60a5fa; }
  .badge-real_estate { background: rgba(236,72,153,0.2); color: #f472b6; }
  .badge-machinery { background: rgba(234,179,8,0.2); color: #fbbf24; }
  .badge-general_goods { background: rgba(34,197,94,0.2); color: #4ade80; }
  .badge-other { background: rgba(156,163,175,0.2); color: #d1d5db; }
  .badge-premium { background: rgba(234,179,8,0.3); color: #eab308; }
  .badge-ending { background: rgba(239,68,68,0.2); color: #f87171; }
  .urgent { border-left: 3px solid #ef4444; }
  .cta-button { display: inline-block; background: #eab308; color: #000; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 20px 0; }
  .cta-button:hover { background: #ca9a06; }
  .footer { text-align: center; padding: 30px 0; border-top: 1px solid rgba(255,255,255,0.1); margin-top: 30px; }
  .footer p { color: #52525b; font-size: 13px; margin: 5px 0; }
  .footer a { color: #a1a1aa; text-decoration: none; }
  .footer a:hover { color: #fff; }
  .tips { background: rgba(59,130,246,0.1); border-radius: 12px; padding: 20px; margin: 20px 0; }
  .tips h3 { color: #60a5fa; margin: 0 0 15px 0; font-size: 16px; }
  .tips ul { margin: 0; padding-left: 20px; color: #a1a1aa; }
  .tips li { margin-bottom: 8px; line-height: 1.5; }
  .ending-banner { background: linear-gradient(135deg, rgba(239,68,68,0.2) 0%, rgba(239,68,68,0.1) 100%); border: 1px solid rgba(239,68,68,0.3); border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0; }
  .ending-banner h2 { color: #f87171; margin: 0 0 10px 0; }
  @media (max-width: 480px) {
    .card-row { flex-direction: column; }
    .card-image { width: 100%; height: 150px; }
    .stats { flex-direction: column; gap: 15px; }
  }
</style>
"""


def _format_price(price: float, currency: str) -> str:
    """Format price for display."""
    if currency == "USD":
        return f"USD ${price:,.0f}"
    return f"${price:,.0f} ARS"


def _get_category_badge(category: str) -> str:
    """Get HTML for category badge."""
    labels = {
        "vehicles": "Vehiculos",
        "real_estate": "Inmuebles",
        "machinery": "Maquinaria",
        "general_goods": "Bienes",
        "other": "Otros",
    }
    label = labels.get(category, category.title())
    return f'<span class="badge badge-{category}">{label}</span>'


def _render_item_card(item: "DigestItem", show_image: bool = True) -> str:
    """Render a single item card."""
    # Image HTML
    image_html = ""
    if show_image and item.image_url:
        image_html = f'<img src="{item.image_url}" class="card-image" alt="{item.title[:30]}">'

    # Badges
    badges = [_get_category_badge(item.category)]
    if item.is_premium:
        badges.append('<span class="badge badge-premium">Premium</span>')
    if item.is_ending_today:
        badges.append('<span class="badge badge-ending">Termina hoy</span>')

    badges_html = " ".join(badges)

    # Discount badge
    discount_html = ""
    if item.discount_percent and item.discount_percent > 0:
        discount_html = f'<span class="card-discount">-{item.discount_percent:.0f}%</span>'

    # Location
    location = item.location or {}
    location_text = location.get("province", "") or location.get("city", "")

    # Meta info
    meta_parts = [item.source.replace("_", " ").title()]
    if location_text:
        meta_parts.append(location_text)
    if item.ends_at_formatted:
        meta_parts.append(f"Cierra: {item.ends_at_formatted}")
    meta_html = " | ".join(meta_parts)

    # Card classes
    card_class = "card"
    if item.is_ending_today:
        card_class += " urgent"

    return f'''
    <div class="{card_class}">
      <div class="card-row">
        {image_html}
        <div class="card-content">
          <div style="margin-bottom: 8px;">{badges_html}</div>
          <h3 class="card-title"><a href="{item.source_url}">{item.title}</a></h3>
          <p class="card-meta">{meta_html}</p>
          <p class="card-price">
            {_format_price(item.base_price, item.currency)}
            {discount_html}
          </p>
        </div>
      </div>
    </div>
    '''


def render_daily_digest(digest: "DigestContent") -> str:
    """Render the daily digest email."""
    # Render item cards
    items_html = ""
    for item in digest.items:
        items_html += _render_item_card(item)

    # Ending today section
    ending_html = ""
    if digest.ending_today_items:
        ending_items = "".join(_render_item_card(i, show_image=False) for i in digest.ending_today_items[:3])
        ending_html = f'''
        <div class="ending-banner">
          <h2>Terminan Hoy</h2>
          <p style="color: #a1a1aa; margin-bottom: 15px;">No te pierdas estas oportunidades</p>
        </div>
        {ending_items}
        '''

    # Unsubscribe URL
    unsub_url = f"https://subasto.com.ar/api/v1/unsubscribe?token={digest.unsubscribe_token}"

    return f'''
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Subasto Digest - Oportunidades de Hoy</title>
  {BASE_STYLES}
</head>
<body>
  <div class="container">
    <div class="header">
      <a href="https://subasto.com.ar" class="logo">SUBASTO</a>
    </div>

    <div class="hero">
      <h1>Tu Digest Diario</h1>
      <p>Las mejores oportunidades de subastas en Argentina</p>
    </div>

    <table class="stats" style="width: 100%; border-collapse: collapse;">
      <tr>
        <td class="stat" style="text-align: center; padding: 10px;">
          <div class="stat-value">{digest.total_listings}</div>
          <div class="stat-label">Subastas Activas</div>
        </td>
        <td class="stat" style="text-align: center; padding: 10px;">
          <div class="stat-value">{digest.opportunities_count}</div>
          <div class="stat-label">Oportunidades</div>
        </td>
        <td class="stat" style="text-align: center; padding: 10px;">
          <div class="stat-value">${digest.blue_dollar_rate:.0f}</div>
          <div class="stat-label">Dolar Blue</div>
        </td>
      </tr>
    </table>

    <div class="section">
      <h2 class="section-title">Top {len(digest.items)} Oportunidades</h2>
      {items_html}
    </div>

    {ending_html}

    <div style="text-align: center; margin: 30px 0;">
      <a href="https://subasto.com.ar" class="cta-button">Ver Todas las Subastas</a>
    </div>

    <div class="footer">
      <p>Recibis este email porque te suscribiste a Subasto.com.ar</p>
      <p>
        <a href="{unsub_url}">Desuscribirme</a> |
        <a href="https://subasto.com.ar">Ver en el sitio</a>
      </p>
      <p style="margin-top: 15px; font-size: 11px;">
        Memola Medios S.A.S. | Argentina
      </p>
    </div>
  </div>
</body>
</html>
'''


def render_ending_today(digest: "DigestContent") -> str:
    """Render the 'ending today' alert email."""
    items_html = ""
    for item in digest.items:
        items_html += _render_item_card(item)

    unsub_url = f"https://subasto.com.ar/api/v1/unsubscribe?token={digest.unsubscribe_token}"

    return f'''
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Terminan Hoy - Subasto</title>
  {BASE_STYLES}
</head>
<body>
  <div class="container">
    <div class="header">
      <a href="https://subasto.com.ar" class="logo">SUBASTO</a>
    </div>

    <div class="ending-banner">
      <h2>&#128680; Terminan Hoy</h2>
      <p style="color: #a1a1aa;">{len(digest.items)} subastas cierran en las proximas horas</p>
    </div>

    <div class="section">
      {items_html}
    </div>

    <div style="text-align: center; margin: 30px 0;">
      <a href="https://subasto.com.ar" class="cta-button">Ver Todas las Subastas</a>
    </div>

    <div class="footer">
      <p><a href="{unsub_url}">Desuscribirme</a></p>
    </div>
  </div>
</body>
</html>
'''


def render_category_digest(digest: "DigestContent", category_name: str) -> str:
    """Render a category-specific digest email."""
    items_html = ""
    for item in digest.items:
        items_html += _render_item_card(item)

    unsub_url = f"https://subasto.com.ar/api/v1/unsubscribe?token={digest.unsubscribe_token}"

    return f'''
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{category_name} - Subasto Digest</title>
  {BASE_STYLES}
</head>
<body>
  <div class="container">
    <div class="header">
      <a href="https://subasto.com.ar" class="logo">SUBASTO</a>
    </div>

    <div class="hero">
      <h1>Subastas de {category_name}</h1>
      <p>Las mejores oportunidades en tu categoria favorita</p>
    </div>

    <div class="section">
      <h2 class="section-title">Top {len(digest.items)} en {category_name}</h2>
      {items_html}
    </div>

    <div style="text-align: center; margin: 30px 0;">
      <a href="https://subasto.com.ar" class="cta-button">Ver Mas {category_name}</a>
    </div>

    <div class="footer">
      <p><a href="{unsub_url}">Desuscribirme</a></p>
    </div>
  </div>
</body>
</html>
'''


def render_welcome_email(digest: "DigestContent") -> str:
    """Render the welcome email with tips."""
    # Sample items
    samples_html = ""
    for item in digest.items:
        samples_html += _render_item_card(item, show_image=False)

    unsub_url = f"https://subasto.com.ar/api/v1/unsubscribe?token={digest.unsubscribe_token}"

    return f'''
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bienvenido a Subasto</title>
  {BASE_STYLES}
</head>
<body>
  <div class="container">
    <div class="header">
      <a href="https://subasto.com.ar" class="logo">SUBASTO</a>
    </div>

    <div class="hero">
      <h1>&#127881; Bienvenido a Subasto</h1>
      <p>Tu puerta a las mejores subastas de Argentina</p>
    </div>

    <div class="tips">
      <h3>&#128161; Tips para Empezar</h3>
      <ul>
        <li><strong>Busca descuentos del 40%+</strong> - Son las mejores oportunidades</li>
        <li><strong>Revisa las subastas judiciales</strong> - CSJN, SCBA y Cordoba tienen excelentes precios</li>
        <li><strong>Presta atencion a "Termina Hoy"</strong> - Las ultimas horas son criticas</li>
        <li><strong>Verifica siempre los requisitos</strong> - Cada fuente tiene reglas diferentes</li>
        <li><strong>Usa el dolar blue</strong> - Los precios en ARS se convierten a ~${digest.blue_dollar_rate:.0f}</li>
      </ul>
    </div>

    <table class="stats" style="width: 100%; border-collapse: collapse;">
      <tr>
        <td class="stat" style="text-align: center; padding: 10px;">
          <div class="stat-value">{digest.total_listings}+</div>
          <div class="stat-label">Subastas Activas</div>
        </td>
        <td class="stat" style="text-align: center; padding: 10px;">
          <div class="stat-value">{digest.opportunities_count}</div>
          <div class="stat-label">Oportunidades</div>
        </td>
        <td class="stat" style="text-align: center; padding: 10px;">
          <div class="stat-value">14</div>
          <div class="stat-label">Fuentes</div>
        </td>
      </tr>
    </table>

    <div class="section">
      <h2 class="section-title">&#127775; Oportunidades Destacadas</h2>
      <p style="color: #a1a1aa; margin-bottom: 20px;">Un preview de lo que te espera</p>
      {samples_html}
    </div>

    <div style="text-align: center; margin: 30px 0;">
      <a href="https://subasto.com.ar" class="cta-button">Explorar Subastas</a>
    </div>

    <div class="section" style="background: rgba(255,255,255,0.03); padding: 20px; border-radius: 12px;">
      <h3 style="color: #eab308; margin-top: 0;">&#128231; Tu Digest Diario</h3>
      <p style="color: #a1a1aa;">
        Cada dia a las 8:00 AM (Argentina) recibiras un email con las mejores oportunidades.
        Podes personalizar tus preferencias en cualquier momento.
      </p>
    </div>

    <div class="footer">
      <p>Gracias por unirte a Subasto</p>
      <p><a href="{unsub_url}">Desuscribirme</a></p>
    </div>
  </div>
</body>
</html>
'''


def render_confirmation_email(confirm_url: str) -> str:
    """Render the double opt-in confirmation email."""
    return f'''
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Confirma tu Suscripcion - Subasto</title>
  {BASE_STYLES}
</head>
<body>
  <div class="container">
    <div class="header">
      <a href="https://subasto.com.ar" class="logo">SUBASTO</a>
    </div>

    <div class="hero">
      <h1>Confirma tu Suscripcion</h1>
      <p>Un paso mas para recibir las mejores oportunidades</p>
    </div>

    <div style="text-align: center; padding: 30px 0;">
      <p style="color: #a1a1aa; margin-bottom: 30px;">
        Haz click en el boton para confirmar tu email y empezar a recibir el digest diario de Subasto.
      </p>
      <a href="{confirm_url}" class="cta-button">Confirmar Suscripcion</a>
    </div>

    <div style="text-align: center; color: #52525b; font-size: 13px; padding: 20px;">
      <p>Si no solicitaste esta suscripcion, podes ignorar este email.</p>
      <p>Este link expira en 24 horas.</p>
    </div>

    <div class="footer">
      <p>Subasto.com.ar | Memola Medios S.A.S.</p>
    </div>
  </div>
</body>
</html>
'''
