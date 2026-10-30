from django.urls import path

from .views import (
    AlertRuleDetailView,
    AlertRuleListCreateView,
    ChatIntentView,
    NotificationLogListView,
)

urlpatterns = [
    path("", AlertRuleListCreateView.as_view()),
    path("<int:pk>/", AlertRuleDetailView.as_view()),
    path("logs/", NotificationLogListView.as_view()),
    path("chat/", ChatIntentView.as_view()),
]
