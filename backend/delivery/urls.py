from django.urls import path
from .views import DeliveryChannelDetailView, DeliveryChannelListCreateView, TestDeliveryView
urlpatterns = [
    path("", DeliveryChannelListCreateView.as_view()),
    path("<int:pk>/", DeliveryChannelDetailView.as_view()),
    path("test/", TestDeliveryView.as_view()),
]
