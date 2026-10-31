import os

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from alerts.models import NotificationLog

from .models import DeliveryChannel
from .serializers import DeliveryChannelSerializer
from .services import send_ntfy, send_telegram, send_webpush


class DeliveryChannelListCreateView(generics.ListCreateAPIView):
    serializer_class = DeliveryChannelSerializer

    def get_queryset(self):
        return DeliveryChannel.objects.filter(user=self.request.user)


class DeliveryChannelDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DeliveryChannelSerializer

    def get_queryset(self):
        return DeliveryChannel.objects.filter(user=self.request.user)


class TestDeliveryView(APIView):
    def post(self, request):
        channel_id = request.data.get("channel_id")
        qs = DeliveryChannel.objects.filter(user=request.user, is_active=True)
        if channel_id:
            qs = qs.filter(pk=channel_id)
        channels = list(qs)
        if not channels:
            return Response({"detail": "No active delivery channel."}, status=400)
        title, body = "Notify · test alert", "Your delivery channel is working."
        results = []
        any_ok = False
        for channel in channels:
            if channel.channel_type == DeliveryChannel.CHANNEL_NTFY:
                ok, detail = send_ntfy(channel.config.get("topic", ""), title, body)
            elif channel.channel_type == DeliveryChannel.CHANNEL_TELEGRAM:
                ok, detail = send_telegram(
                    os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                    str(channel.config.get("chat_id", "")),
                    title,
                    body,
                )
            elif channel.channel_type == DeliveryChannel.CHANNEL_WEBPUSH:
                ok, detail = send_webpush(channel.config, title, body)
            else:
                ok, detail = False, "Unknown channel"
            NotificationLog.objects.create(
                user=request.user,
                channel=channel.channel_type,
                title=title,
                body=body,
                success=ok,
                detail=detail,
            )
            results.append({"channel": channel.channel_type, "ok": ok, "detail": detail})
            if ok:
                any_ok = True
        if not any_ok:
            return Response({"detail": results[0]["detail"], "results": results}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"detail": "Test notification sent.", "results": results})


class VapidPublicKeyView(APIView):
    """Public VAPID key for browser PushManager.subscribe."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        key = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
        if not key:
            return Response({"detail": "Web push not configured. Set VAPID_PUBLIC_KEY on server."}, status=503)
        return Response({"publicKey": key})


class WebPushSubscribeView(APIView):
    """Save browser push subscription as delivery channel webpush."""

    def post(self, request):
        sub = request.data.get("subscription") or request.data
        endpoint = (sub.get("endpoint") or "").strip()
        keys = sub.get("keys") or {}
        if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
            return Response({"detail": "Invalid subscription."}, status=400)
        config = {"endpoint": endpoint, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}}
        ch, _ = DeliveryChannel.objects.update_or_create(
            user=request.user,
            channel_type=DeliveryChannel.CHANNEL_WEBPUSH,
            label="default",
            defaults={"config": config, "is_active": True},
        )
        return Response({"detail": "App notifications enabled.", "id": ch.id})
