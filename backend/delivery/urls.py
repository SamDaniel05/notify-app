from django.urls import path

from .views import (
    DeliveryChannelDetailView,
    DeliveryChannelListCreateView,
    TestDeliveryView,
    VapidPublicKeyView,
    WebPushSubscribeView,
)

urlpatterns = [
    path("", DeliveryChannelListCreateView.as_view()),
    path("<int:pk>/", DeliveryChannelDetailView.as_view()),
    path("test/", TestDeliveryView.as_view()),
    path("vapid-public-key/", VapidPublicKeyView.as_view()),
    path("webpush/subscribe/", WebPushSubscribeView.as_view()),
]
