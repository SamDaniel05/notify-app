"""Send transactional email via Resend API or Django SMTP."""
from __future__ import annotations

import hashlib
import logging
import os
import random
import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


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
    """True if Resend or SMTP is configured for real delivery."""
    if os.environ.get("RESEND_API_KEY", "").strip():
        return True
    if os.environ.get("EMAIL_HOST", "").strip() and os.environ.get("EMAIL_HOST_USER", "").strip():
        return True
    return False


def expose_dev_codes() -> bool:
    """Only when explicitly enabled. Never on normal production deploy."""
    return os.environ.get("EMAIL_DEV_EXPOSE", "0") == "1"


def _send_resend(to: str, subject: str, text: str) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if not api_key:
        return False
    from_addr = os.environ.get("EMAIL_FROM", "Notify <onboarding@resend.dev>")
    try:
        res = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"from": from_addr, "to": [to], "subject": subject, "text": text},
            timeout=20,
        )
        if res.status_code >= 400:
            logger.error("Resend error %s: %s", res.status_code, res.text[:300])
            return False
        return True
    except requests.RequestException as e:
        logger.exception("Resend failed: %s", e)
        return False


def _send_django(to: str, subject: str, text: str) -> bool:
    if not os.environ.get("EMAIL_HOST", "").strip():
        return False
    try:
        n = send_mail(
            subject,
            text,
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@notify.app"),
            [to],
            fail_silently=False,
        )
        return n > 0
    except Exception as e:
        logger.exception("Django email failed: %s", e)
        return False


def send_email(to: str, subject: str, text: str) -> bool:
    if _send_resend(to, subject, text):
        return True
    return _send_django(to, subject, text)
