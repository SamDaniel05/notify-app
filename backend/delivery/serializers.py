from rest_framework import serializers
from .models import DeliveryChannel

class DeliveryChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryChannel
        fields = ("id", "channel_type", "config", "is_active", "label", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")
    def validate(self, attrs):
        channel_type = attrs.get("channel_type") or getattr(self.instance, "channel_type", None)
        config = attrs.get("config", getattr(self.instance, "config", {}) or {})
        if channel_type == DeliveryChannel.CHANNEL_NTFY and not (config.get("topic") or "").strip():
            raise serializers.ValidationError({"config": "ntfy topic is required."})
        if channel_type == DeliveryChannel.CHANNEL_TELEGRAM and not str(config.get("chat_id") or "").strip():
            raise serializers.ValidationError({"config": "Telegram chat_id is required."})
        return attrs
    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
