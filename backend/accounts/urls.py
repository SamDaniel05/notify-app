from django.urls import path

from .views import (
    LoginView,
    MagicLinkRequestView,
    MagicLinkVerifyView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    ResendCodeView,
    VerifyEmailView,
)

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("login/", LoginView.as_view()),
    path("verify-email/", VerifyEmailView.as_view()),
    path("resend-code/", ResendCodeView.as_view()),
    path("password-reset/", PasswordResetRequestView.as_view()),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view()),
    path("me/", MeView.as_view()),
    path("magic/", MagicLinkRequestView.as_view()),
    path("magic/verify/", MagicLinkVerifyView.as_view()),
]
