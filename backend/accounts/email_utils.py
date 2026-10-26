"""Send email via Brevo/Resend HTTP APIs (SMTP blocked on free Render)."""
from __future__ import annotations

import hashlib
import logging
import os
import random
import secrets
from datetime import timedelta

import requests
from django.conf import settings
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
    if os.environ.get("BREVO_API_KEY", "").strip():
        return True
    if os.environ.get("RESEND_API_KEY", "").strip():
        return True
    # SMTP usually blocked on free Render — still detect if set
    if os.environ.get("EMAIL_HOST", "").strip() and os.environ.get("EMAIL_HOST_USER", "").strip():
        return True
    return False


def expose_dev_codes() -> bool:
    return os.environ.get("EMAIL_DEV_EXPOSE", "0") == "1"


def _sender_email() -> str:
    raw = os.environ.get("EMAIL_FROM") or os.environ.get("DEFAULT_FROM_EMAIL") or ""
    # Parse "Name <email@x.com>" or bare email
    if "<" in raw and ">" in raw:
        return raw.split("<")[1].split(">")[0].strip()
    if "@" in raw:
        return raw.strip()
    return os.environ.get("EMAIL_HOST_USER", "noreply@notify.app").strip()


def _sender_name() -> str:
    raw = os.environ.get("EMAIL_FROM") or "Notify"
    if "<" in raw:
        return raw.split("<")[0].strip() or "Notify"
    return "Notify"


def _send_brevo(to: str, subject: str, text: str) -> tuple[bool, str]:
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    if not api_key:
        return False, ""
    sender = _sender_email()
    if not sender or "@" not in sender:
        return False, "Set EMAIL_FROM to a real email (your Brevo login email works for testing)"
    try:
        res = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "sender": {"name": _sender_name(), "email": sender},
                "to": [{"email": to}],
                "subject": subject,
                "textContent": text,
            },
            timeout=15,
        )
        if res.status_code >= 400:
            logger.error("Brevo error %s: %s", res.status_code, res.text[:400])
            return False, f"Brevo {res.status_code}: {res.text[:250]}"
        return True, ""
    except requests.RequestException as e:
        logger.exception("Brevo failed")
        return False, f"Brevo request failed: {e}"


def _send_resend(to: str, subject: str, text: str) -> tuple[bool, str]:
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if not api_key:
        return False, ""
    from_addr = os.environ.get("EMAIL_FROM", "Notify <onboarding@resend.dev>")
    if "gmail.com" in from_addr.lower() and "resend.dev" not in from_addr.lower():
        # Resend rejects arbitrary gmail as from without domain
        from_addr = "Notify <onboarding@resend.dev>"
    try:
        res = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"from": from_addr, "to": [to], "subject": subject, "text": text},
            timeout=12,
        )
        if res.status_code >= 400:
            logger.error("Resend error %s: %s", res.status_code, res.text[:300])
            return False, f"Resend {res.status_code}: {res.text[:200]}"
        return True, ""
    except requests.RequestException as e:
        logger.exception("Resend failed")
        return False, f"Resend request failed: {e}"


def send_email(to: str, subject: str, text: str) -> tuple[bool, str]:
    """Returns (success, error_message). Prefer HTTP APIs — SMTP is blocked on free Render."""
    errors: list[str] = []

    ok, err = _send_brevo(to, subject, text)
    if ok:
        return True, ""
    if err:
        errors.append(err)

    ok, err = _send_resend(to, subject, text)
    if ok:
        return True, ""
    if err:
        errors.append(err)

    # Do not attempt SMTP on Render free — it fails with Network unreachable and wastes time
    if not errors:
        return False, (
            "No HTTP email API configured. Set BREVO_API_KEY on Render "
            "(Gmail SMTP is blocked: Network unreachable)."
        )
    return False, " | ".join(errors)
