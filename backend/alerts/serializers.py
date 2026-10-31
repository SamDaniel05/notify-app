from rest_framework import serializers

from .models import AlertRule, NotificationLog


class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = (
            "id",
            "title",
            "alert_type",
            "params",
            "is_active",
            "last_checked_at",
            "last_triggered_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "last_checked_at", "last_triggered_at", "created_at", "updated_at")

    def validate(self, attrs):
        alert_type = attrs.get("alert_type") or getattr(self.instance, "alert_type", None)
        params = attrs.get("params", getattr(self.instance, "params", {}) or {})
        if alert_type == AlertRule.TYPE_WEATHER and not params.get("place_name") and not (
            params.get("lat") and params.get("lng")
        ):
            raise serializers.ValidationError({"params": "Provide place_name or lat/lng."})
        if alert_type == AlertRule.TYPE_KEYWORD and not (params.get("query") or "").strip():
            raise serializers.ValidationError({"params": "Provide a keyword query."})
        if alert_type == AlertRule.TYPE_RSS and not (params.get("feed_url") or params.get("page_url")):
            raise serializers.ValidationError({"params": "Provide feed_url or page_url."})
        if alert_type == AlertRule.TYPE_REMINDER:
            msg = (params.get("message") or params.get("task") or "").strip()
            if not msg:
                raise serializers.ValidationError({"params": "Provide reminder message/task."})
            days = int(params.get("days") or 0)
            if days < 1:
                days = 14
                params["days"] = days
            if not params.get("time_local"):
                params["time_local"] = "20:00"
            attrs["params"] = params
        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = ("id", "rule", "channel", "title", "body", "success", "detail", "created_at")
