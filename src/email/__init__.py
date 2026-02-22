"""Email digest system for Subasto.

This module handles:
- Daily digest generation with personalized content
- Email template rendering
- Integration with email service providers (Resend/SendGrid)
"""

from .digest_generator import DigestGenerator, generate_daily_digest
from .sender import EmailSender, send_digest

__all__ = [
    "DigestGenerator",
    "generate_daily_digest",
    "EmailSender",
    "send_digest",
]
