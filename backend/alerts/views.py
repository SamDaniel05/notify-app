import os
from datetime import date, timedelta

from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .checker import run_checks
from .intent import extract_intents, parse_control_command
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


def _match_reminder(user, query: str):
    qs = AlertRule.objects.filter(user=user, alert_type=AlertRule.TYPE_REMINDER, is_active=True)
    q = (query or "").lower()
    # Prefer keyword overlap with title/message
    tokens = [t for t in re_split_tokens(q) if len(t) > 2]
    best = None
    best_score = 0
    for rule in qs:
        blob = f"{rule.title} {(rule.params or {}).get('message', '')}".lower()
        score = sum(1 for t in tokens if t in blob)
        if score > best_score:
            best_score = score
            best = rule
    if best:
        return best
    return qs.order_by("-updated_at").first()


def re_split_tokens(s: str):
    import re

    return re.findall(r"[a-z0-9]+", s.lower())


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
                    "speak": True,
                }
            )

        # Snooze / done on existing reminders
        ctrl = parse_control_command(message)
        result = extract_intents(message)
        if result.get("control") or (
            ctrl and not result.get("proposals") and (result.get("control") or ctrl)
        ):
            ctrl = result.get("control") or ctrl
            if ctrl:
                rule = _match_reminder(request.user, ctrl.get("query") or message)
                if not rule:
                    return Response(
                        {
                            "reply": "I couldn’t find an active reminder to update. Create one first, e.g. “Remind me to clean AC every 15 days”.",
                            "proposals": [],
                            "speak": True,
                        }
                    )
                params = dict(rule.params or {})
                today = date.today()
                if ctrl["action"] == "snooze":
                    days = int(ctrl.get("days") or 1)
                    new_due = today + timedelta(days=days)
                    params["mode"] = params.get("mode") or "interval"
                    if params.get("mode") != "interval":
                        # convert daily_window mid-flight: still shift start
                        params["start_date"] = new_due.isoformat()
                    params["next_due"] = new_due.isoformat()
                    rule.params = params
                    rule.save(update_fields=["params", "updated_at"])
                    interval = params.get("interval_days")
                    extra = f" After that, the every-{interval}-day cycle continues from that day." if interval else ""
                    return Response(
                        {
                            "reply": f"Okay — “{rule.title}” snoozed. Next reminder: {new_due.isoformat()}.{extra}",
                            "proposals": [],
                            "speak": True,
                            "updated": AlertRuleSerializer(rule).data,
                        }
                    )
                if ctrl["action"] == "done":
                    interval = int(params.get("interval_days") or 0)
                    if interval:
                        new_due = today + timedelta(days=interval)
                        params["next_due"] = new_due.isoformat()
                        params["last_completed"] = today.isoformat()
                        params["mode"] = "interval"
                        rule.params = params
                        rule.save(update_fields=["params", "updated_at"])
                        return Response(
                            {
                                "reply": f"Marked done. Next “{rule.title}” in {interval} days ({new_due.isoformat()}).",
                                "proposals": [],
                                "speak": True,
                                "updated": AlertRuleSerializer(rule).data,
                            }
                        )
                    return Response(
                        {
                            "reply": f"Noted. “{rule.title}” is still on its daily window schedule.",
                            "proposals": [],
                            "speak": True,
                        }
                    )

        return Response(result, status=status.HTTP_200_OK)


class RunChecksView(APIView):
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
