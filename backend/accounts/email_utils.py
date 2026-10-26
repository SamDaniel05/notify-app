"""Send email via Gmail SMTP or Resend. Fail fast with clear errors."""
from __future__ import annotations

import hashlib
import logging
import os
import random
import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Last send error (for API responses)
LAST_EMAIL_ERROR = ""


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def generate_otp(length: int = 6) -> str:
    upper = 10**length
    return str(random.SystemRandom().randint(0, upper - 1)).zfill(length)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def otp_expiry(minutes: int | None = None):
    minutes = minutes or getattr(settings, "OTP_TTL_MINUTES", 15)
    return timezone.now() + timedelta(minutes=minutes)


def email_configured() -> bool:
    if os.environ.get("EMAIL_HOST", "").strip() and os.environ.get("EMAIL_HOST_USER", "").strip():
        return True
    if os.environ.get("RESEND_API_KEY", "").strip():
        return True
    return False


def expose_dev_codes() -> bool:
    return os.environ.get("EMAIL_DEV_EXPOSE", "0") == "1"


def _send_smtp(to: str, subject: str, text: str) -> bool:
    global LAST_EMAIL_ERROR
    host = os.environ.get("EMAIL_HOST", "").strip()
    user = os.environ.get("EMAIL_HOST_USER", "").strip()
    password = os.environ.get("EMAIL_HOST_PASSWORD", "").strip().replace(" ", "")
    if not host or not user or not password:
        LAST_EMAIL_ERROR = "SMTP not fully configured (HOST/USER/PASSWORD)"
        return False

    port = int(os.environ.get("EMAIL_PORT", "587") or "587")
    use_tls = os.environ.get("EMAIL_USE_TLS", "1") == "1"
    from_addr = os.environ.get("DEFAULT_FROM_EMAIL") or user
    display_from = os.environ.get("EMAIL_FROM") or from_addr

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = display_from
    msg["To"] = to
    msg.set_content(text)

    try:
        if port == 465 or not use_tls:
            with smtplib.SMTP_SSL(host, port or 465, timeout=12) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=12) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(user, password)
                server.send_message(msg)
        LAST_EMAIL_ERROR = ""
        return True
    except smtplib.SMTPAuthenticationError as e:
        LAST_EMAIL_ERROR = f"Gmail auth failed: {e}. Check App Password (16 chars, no spaces)."
        logger.exception("SMTP auth failed")
        return False
    except (smtplib.SMTPException, OSError, TimeoutError) as e:
        LAST_EMAIL_ERROR = f"SMTP error: {type(e).__name__}: {e}"
        logger.exception("SMTP send failed")
        return False


def _send_resend(to: str, subject: str, text: str) -> bool:
    global LAST_EMAIL_ERROR
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if not api_key:
        return False
    from_addr = os.environ.get("EMAIL_FROM", "Notify <onboarding@resend.dev>")
    # If FROM is still a gmail address, Resend will reject — skip
    if "gmail.com" in from_addr.lower():
        return False
    try:
        res = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"from": from_addr, "to": [to], "subject": subject, "text": text},
            timeout=10,
        )
        if res.status_code >= 400:
            LAST_EMAIL_ERROR = f"Resend {res.status_code}: {res.text[:200]}"
            logger.error("Resend error %s: %s", res.status_code, res.text[:300])
            return False
        LAST_EMAIL_ERROR = ""
        return True
    except requests.RequestException as e:
        LAST_EMAIL_ERROR = f"Resend request failed: {e}"
        logger.exception("Resend failed")
        return False


def send_email(to: str, subject: str, text: str) -> bool:
    global LAST_EMAIL_ERROR
    LAST_EMAIL_ERROR = ""
    # Prefer SMTP when configured
    if os.environ.get("EMAIL_HOST", "").strip():
        if _send_smtp(to, subject, text):
            return True
    if _send_resend(to, subject, text):
        return True
    if not LAST_EMAIL_ERROR:
        LAST_EMAIL_ERROR = "No email provider succeeded"
    return False
