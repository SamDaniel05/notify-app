import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .email_utils import hash_code


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    preferred_language = models.CharField(
        max_length=8, choices=[("en", "English"), ("ta", "Tamil")], default="en"
    )
    display_name = models.CharField(max_length=120, blank=True)
    email_verified = models.BooleanField(default=False)

    # Signup / email verification OTP
    email_otp_hash = models.CharField(max_length=64, blank=True)
    email_otp_expires = models.DateTimeField(null=True, blank=True)

    # Password reset OTP
    reset_otp_hash = models.CharField(max_length=64, blank=True)
    reset_otp_expires = models.DateTimeField(null=True, blank=True)

    # Magic link token
    magic_token_hash = models.CharField(max_length=64, blank=True)
    magic_token_expires = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile<{self.user.username}>"

    def set_email_otp(self, code: str, minutes: int = 15):
        self.email_otp_hash = hash_code(code)
        self.email_otp_expires = timezone.now() + timedelta(minutes=minutes)
        self.save(update_fields=["email_otp_hash", "email_otp_expires", "updated_at"])

    def check_email_otp(self, code: str) -> bool:
        if not code or not self.email_otp_hash or not self.email_otp_expires:
            return False
        if timezone.now() > self.email_otp_expires:
            return False
        ok = secrets.compare_digest(hash_code(code), self.email_otp_hash)
        if ok:
            self.email_otp_hash = ""
            self.email_otp_expires = None
            self.email_verified = True
            self.save(
                update_fields=[
                    "email_otp_hash",
                    "email_otp_expires",
                    "email_verified",
                    "updated_at",
                ]
            )
        return ok

    def set_reset_otp(self, code: str, minutes: int = 15):
        self.reset_otp_hash = hash_code(code)
        self.reset_otp_expires = timezone.now() + timedelta(minutes=minutes)
        self.save(update_fields=["reset_otp_hash", "reset_otp_expires", "updated_at"])

    def check_reset_otp(self, code: str) -> bool:
        if not code or not self.reset_otp_hash or not self.reset_otp_expires:
            return False
        if timezone.now() > self.reset_otp_expires:
            return False
        ok = secrets.compare_digest(hash_code(code), self.reset_otp_hash)
        if ok:
            self.reset_otp_hash = ""
            self.reset_otp_expires = None
            self.save(update_fields=["reset_otp_hash", "reset_otp_expires", "updated_at"])
        return ok

    def issue_magic_token(self) -> str:
        raw = secrets.token_urlsafe(32)
        self.magic_token_hash = hashlib.sha256(raw.encode()).hexdigest()
        self.magic_token_expires = timezone.now() + timedelta(
            minutes=getattr(settings, "MAGIC_LINK_TTL_MINUTES", 20)
        )
        self.save(update_fields=["magic_token_hash", "magic_token_expires", "updated_at"])
        return raw

    def verify_magic_token(self, raw: str) -> bool:
        if not raw or not self.magic_token_hash or not self.magic_token_expires:
            return False
        if timezone.now() > self.magic_token_expires:
            return False
        digest = hashlib.sha256(raw.encode()).hexdigest()
        ok = secrets.compare_digest(digest, self.magic_token_hash)
        if ok:
            self.magic_token_hash = ""
            self.magic_token_expires = None
            self.email_verified = True
            self.save(
                update_fields=[
                    "magic_token_hash",
                    "magic_token_expires",
                    "email_verified",
                    "updated_at",
                ]
            )
        return ok
