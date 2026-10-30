from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .intent import extract_intents
from .models import AlertRule, NotificationLog
from .serializers import AlertRuleSerializer, NotificationLogSerializer


class AlertRuleListCreateView(generics.ListCreateAPIView):
    serializer_class = AlertRuleSerializer

    def get_queryset(self):
        return AlertRule.objects.filter(user=self.request.user)


class AlertRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AlertRuleSerializer

    def get_queryset(self):
        return AlertRule.objects.filter(user=self.request.user)


class NotificationLogListView(generics.ListAPIView):
    serializer_class = NotificationLogSerializer

    def get_queryset(self):
        return NotificationLog.objects.filter(user=self.request.user)[:50]


class ChatIntentView(APIView):
    """POST {message, confirm?: bool, proposals?: list}
    Without confirm: analyze message and return proposals.
    With confirm + proposals: create alert rules.
    """

    def post(self, request):
        message = (request.data.get("message") or "").strip()
        confirm = bool(request.data.get("confirm"))
        proposals = request.data.get("proposals")

        if confirm:
            if not isinstance(proposals, list) or not proposals:
                return Response({"detail": "No proposals to confirm."}, status=400)
            created = []
            for p in proposals:
                ser = AlertRuleSerializer(
                    data={
                        "title": p.get("title") or "Alert",
                        "alert_type": p.get("alert_type") or "keyword",
                        "params": p.get("params") or {},
                    },
                    context={"request": request},
                )
                ser.is_valid(raise_exception=True)
                rule = ser.save()
                created.append(AlertRuleSerializer(rule).data)
            return Response(
                {
                    "reply": f"Saved {len(created)} watch(es). Open Watches to manage them.",
                    "created": created,
                    "proposals": [],
                }
            )

        result = extract_intents(message)
        return Response(result, status=status.HTTP_200_OK)
