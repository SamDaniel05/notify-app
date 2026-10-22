from django.conf import settings
from django.db import models

class AlertRule(models.Model):
    TYPE_WEATHER, TYPE_KEYWORD, TYPE_RSS = "weather", "keyword", "rss"
    TYPE_CHOICES = [(TYPE_WEATHER, "Place weather / rain"), (TYPE_KEYWORD, "Keyword / news"), (TYPE_RSS, "RSS or public page")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alert_rules")
    title = models.CharField(max_length=200)
    alert_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    params = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-created_at"]

class NotificationLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_logs")
    rule = models.ForeignKey(AlertRule, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs")
    channel = models.CharField(max_length=32)
    title = models.CharField(max_length=200)
    body = models.TextField()
    success = models.BooleanField(default=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at"]
