from rest_framework import generics
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
