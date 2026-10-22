from django.conf import settings
from django.db import models

class DeliveryChannel(models.Model):
    CHANNEL_NTFY, CHANNEL_TELEGRAM = "ntfy", "telegram"
    CHANNEL_CHOICES = [(CHANNEL_NTFY, "ntfy"), (CHANNEL_TELEGRAM, "Telegram")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="delivery_channels")
    channel_type = models.CharField(max_length=32, choices=CHANNEL_CHOICES)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    label = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ("user", "channel_type", "label")
        ordering = ["channel_type"]
