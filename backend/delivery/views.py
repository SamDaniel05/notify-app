import os
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from alerts.models import NotificationLog
from .models import DeliveryChannel
from .serializers import DeliveryChannelSerializer
from .services import send_ntfy, send_telegram

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
        channel = qs.first()
        if not channel:
            return Response({"detail": "No active delivery channel."}, status=400)
        title, body = "Notify · test alert", "Your delivery channel is working."
        if channel.channel_type == DeliveryChannel.CHANNEL_NTFY:
            ok, detail = send_ntfy(channel.config.get("topic", ""), title, body)
        else:
            ok, detail = send_telegram(os.environ.get("TELEGRAM_BOT_TOKEN", ""), str(channel.config.get("chat_id", "")), title, body)
        NotificationLog.objects.create(user=request.user, channel=channel.channel_type, title=title, body=body, success=ok, detail=detail)
        if not ok:
            return Response({"detail": detail}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"detail": "Test notification sent.", "channel": channel.channel_type})
