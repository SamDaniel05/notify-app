import os

from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .checker import run_checks
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

        return Response(extract_intents(message), status=status.HTTP_200_OK)


class RunChecksView(APIView):
    """Cron/webhook: GET/POST with header X-Cron-Secret or ?secret=
    Set CRON_SECRET on Render. Call every 15–30 min from a free cron (cron-job.org).
    """

    permission_classes = [AllowAny]

    def _authorized(self, request) -> bool:
        expected = (os.environ.get("CRON_SECRET") or "").strip()
        if not expected:
            return False
        got = (request.headers.get("X-Cron-Secret") or request.query_params.get("secret") or "").strip()
        return got == expected

    def get(self, request):
        return self._run(request)

    def post(self, request):
        return self._run(request)

    def _run(self, request):
        if not self._authorized(request):
            return Response({"detail": "Unauthorized. Set CRON_SECRET and pass it."}, status=401)
        result = run_checks()
        return Response({"detail": "ok", **result})
