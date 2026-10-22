from django.urls import path
from .views import MagicLinkRequestView, MagicLinkVerifyView, MeView, RegisterView
urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("me/", MeView.as_view()),
    path("magic/", MagicLinkRequestView.as_view()),
    path("magic/verify/", MagicLinkVerifyView.as_view()),
]
