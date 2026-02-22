"""
Email Sender Module for Subasto.

Supports multiple email service providers:
- Resend (recommended for serverless)
- SendGrid
- SMTP fallback

Uses environment variables for configuration:
- EMAIL_PROVIDER: resend | sendgrid | smtp
- RESEND_API_KEY: Resend API key
- SENDGRID_API_KEY: SendGrid API key
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS: SMTP settings
"""

import os
import json
import urllib.request
import urllib.error
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from .digest_generator import DigestGenerator, SubscriberPreferences
from .templates import render_confirmation_email, render_welcome_email


@dataclass
class EmailResult:
    """Result of sending an email."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailSender:
    """Sends emails via configured provider."""

    # Sender configuration
    FROM_EMAIL = os.getenv("EMAIL_FROM", "noreply@subasto.com.ar")
    FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Subasto")
    REPLY_TO = os.getenv("EMAIL_REPLY_TO", "hola@subasto.com.ar")

    def __init__(self):
        """Initialize with provider from environment."""
        self.provider = os.getenv("EMAIL_PROVIDER", "resend").lower()

        # Provider configs
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.smtp_config = {
            "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "user": os.getenv("SMTP_USER", ""),
            "password": os.getenv("SMTP_PASS", ""),
        }

    def send(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> EmailResult:
        """Send an email using the configured provider."""
        if self.provider == "resend":
            return self._send_resend(to_email, subject, html_content, text_content)
        elif self.provider == "sendgrid":
            return self._send_sendgrid(to_email, subject, html_content, text_content)
        elif self.provider == "smtp":
            return self._send_smtp(to_email, subject, html_content, text_content)
        else:
            # Dry run / logging mode
            return self._send_dry_run(to_email, subject, html_content)

    def _send_resend(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> EmailResult:
        """Send via Resend API."""
        if not self.resend_api_key:
            return EmailResult(success=False, error="RESEND_API_KEY not configured")

        try:
            url = "https://api.resend.com/emails"
            payload = {
                "from": f"{self.FROM_NAME} <{self.FROM_EMAIL}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
                "reply_to": self.REPLY_TO,
            }
            if text_content:
                payload["text"] = text_content

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Bearer {self.resend_api_key}",
                    "Content-Type": "application/json",
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                return EmailResult(
                    success=True,
                    message_id=result.get("id")
                )

        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            return EmailResult(success=False, error=f"Resend error: {error_body}")
        except Exception as e:
            return EmailResult(success=False, error=str(e))

    def _send_sendgrid(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> EmailResult:
        """Send via SendGrid API."""
        if not self.sendgrid_api_key:
            return EmailResult(success=False, error="SENDGRID_API_KEY not configured")

        try:
            url = "https://api.sendgrid.com/v3/mail/send"
            payload = {
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": self.FROM_EMAIL, "name": self.FROM_NAME},
                "reply_to": {"email": self.REPLY_TO},
                "subject": subject,
                "content": [{"type": "text/html", "value": html_content}],
            }
            if text_content:
                payload["content"].insert(0, {"type": "text/plain", "value": text_content})

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Bearer {self.sendgrid_api_key}",
                    "Content-Type": "application/json",
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                # SendGrid returns 202 with empty body on success
                return EmailResult(success=True)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            return EmailResult(success=False, error=f"SendGrid error: {error_body}")
        except Exception as e:
            return EmailResult(success=False, error=str(e))

    def _send_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> EmailResult:
        """Send via SMTP."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.FROM_NAME} <{self.FROM_EMAIL}>"
            msg["To"] = to_email
            msg["Reply-To"] = self.REPLY_TO

            # Attach text and HTML parts
            if text_content:
                msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            # Connect and send
            with smtplib.SMTP(self.smtp_config["host"], self.smtp_config["port"]) as server:
                server.starttls()
                if self.smtp_config["user"]:
                    server.login(self.smtp_config["user"], self.smtp_config["password"])
                server.sendmail(self.FROM_EMAIL, [to_email], msg.as_string())

            return EmailResult(success=True)

        except Exception as e:
            return EmailResult(success=False, error=str(e))

    def _send_dry_run(
        self,
        to_email: str,
        subject: str,
        html_content: str
    ) -> EmailResult:
        """Dry run mode - just log the email."""
        print(f"\n{'='*60}")
        print(f"[DRY RUN] Email to: {to_email}")
        print(f"Subject: {subject}")
        print(f"Content length: {len(html_content)} chars")
        print(f"{'='*60}\n")
        return EmailResult(success=True, message_id="dry_run")


def send_confirmation_email(
    to_email: str,
    confirm_url: str
) -> EmailResult:
    """Send double opt-in confirmation email."""
    sender = EmailSender()
    html = render_confirmation_email(confirm_url)
    return sender.send(
        to_email,
        "Confirma tu suscripcion a Subasto",
        html
    )


def send_welcome_email(
    to_email: str,
    unsubscribe_token: str,
    listings_path: Optional[Path] = None
) -> EmailResult:
    """Send welcome email after confirmation."""
    sender = EmailSender()
    generator = DigestGenerator(listings_path)
    digest = generator.generate_welcome_email(to_email, unsubscribe_token)
    html = render_welcome_email(digest)
    return sender.send(
        to_email,
        "Bienvenido a Subasto - Guia de Inicio",
        html
    )


def send_digest(
    to_email: str,
    unsubscribe_token: str,
    preferences: Optional[dict] = None,
    listings_path: Optional[Path] = None
) -> EmailResult:
    """Send daily digest email."""
    from .digest_generator import generate_daily_digest

    subject, html = generate_daily_digest(
        to_email,
        unsubscribe_token,
        preferences,
        listings_path
    )

    sender = EmailSender()
    return sender.send(to_email, subject, html)


def send_ending_today_alert(
    to_email: str,
    unsubscribe_token: str,
    preferences: Optional[dict] = None,
    listings_path: Optional[Path] = None
) -> Optional[EmailResult]:
    """Send 'ending today' alert if there are items."""
    from .templates import render_ending_today

    generator = DigestGenerator(listings_path)

    # Convert dict to preferences
    prefs = None
    if preferences:
        prefs = SubscriberPreferences(
            categories=preferences.get("categories", []),
            provinces=preferences.get("provinces", []),
            price_min_usd=preferences.get("priceMinUsd", 0),
            price_max_usd=preferences.get("priceMaxUsd", 0),
        )

    digest = generator.generate_ending_today_alert(to_email, unsubscribe_token, prefs)

    if not digest:
        return None  # Nothing ending today for this subscriber

    html = render_ending_today(digest)
    sender = EmailSender()
    return sender.send(
        to_email,
        f"&#128680; {len(digest.items)} subastas terminan hoy - Subasto",
        html
    )
