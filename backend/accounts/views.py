from django.contrib.auth.models import User
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .email_utils import expose_dev_codes, generate_otp, send_email
from .models import Profile
from .serializers import (
    EmailOnlySerializer,
    MagicLinkVerifySerializer,
    PasswordResetConfirmSerializer,
    RegisterSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)


def tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def _profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _send_verify_email(user, code: str) -> bool:
    subject = "Notify — your verification code"
    text = (
        f"Your Notify verification code is: {code}\n\n"
        f"It expires in 15 minutes.\n"
        f"If you did not sign up, ignore this email.\n"
    )
    return send_email(user.email, subject, text)


def _send_reset_email(user, code: str) -> bool:
    subject = "Notify — password reset code"
    text = (
        f"Your Notify password reset code is: {code}\n\n"
        f"It expires in 15 minutes.\n"
        f"If you did not request this, ignore this email.\n"
    )
    return send_email(user.email, subject, text)


def _send_magic_email(user, token: str) -> bool:
    subject = "Notify — sign-in link"
    text = (
        f"Use this token to sign in to Notify:\n\n{token}\n\n"
        f"Or enter it on the Magic link screen with your email.\n"
        f"Expires in about 20 minutes.\n"
    )
    return send_email(user.email, subject, text)


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        profile = _profile(user)
        code = generate_otp(6)
        profile.set_email_otp(code)
        sent = _send_verify_email(user, code)
        payload = {
            "detail": "Account created. Enter the 6-digit code sent to your email.",
            "email": user.email,
            "requires_verification": True,
            "email_sent": sent,
        }
        if expose_dev_codes():
            payload["dev_code"] = code
            payload["dev_note"] = "Shown only when email is not fully configured / DEBUG."
        return Response(payload, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = VerifyEmailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        code = ser.validated_data["code"].strip()
        try:
            user = User.objects.get(email__iexact=email)
            profile = _profile(user)
        except User.DoesNotExist:
            return Response({"detail": "Invalid code or email."}, status=400)
        if not profile.check_email_otp(code):
            return Response({"detail": "Invalid or expired code."}, status=400)
        data = tokens_for_user(user)
        data["user"] = UserSerializer(user).data
        data["detail"] = "Email verified."
        return Response(data)


class ResendCodeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = EmailOnlySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        payload = {"detail": "If an account needs verification, a new code was sent."}
        try:
            user = User.objects.get(email__iexact=email)
            profile = _profile(user)
        except User.DoesNotExist:
            return Response(payload)
        if profile.email_verified:
            return Response({"detail": "Email is already verified. You can sign in."})
        code = generate_otp(6)
        profile.set_email_otp(code)
        sent = _send_verify_email(user, code)
        payload["email_sent"] = sent
        if expose_dev_codes():
            payload["dev_code"] = code
        return Response(payload)


class LoginView(APIView):
    """Password login — blocks unverified emails."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get("email") or request.data.get("username") or "").lower().strip()
        password = request.data.get("password") or ""
        if not email or not password:
            return Response({"detail": "Email and password required."}, status=400)
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"detail": "Invalid credentials."}, status=400)
        if not user.check_password(password):
            return Response({"detail": "Invalid credentials."}, status=400)
        profile = _profile(user)
        if not profile.email_verified:
            return Response(
                {
                    "detail": "Email not verified. Enter the code sent to your inbox.",
                    "requires_verification": True,
                    "email": user.email,
                },
                status=403,
            )
        data = tokens_for_user(user)
        data["user"] = UserSerializer(user).data
        return Response(data)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def patch(self, request, *args, **kwargs):
        user = request.user
        profile = _profile(user)
        lang = request.data.get("preferred_language")
        name = request.data.get("display_name")
        if lang in ("en", "ta"):
            profile.preferred_language = lang
        if name is not None:
            profile.display_name = name[:120]
        profile.save()
        return Response(UserSerializer(user).data)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = EmailOnlySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        payload = {"detail": "If an account exists, a reset code was sent."}
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(payload)
        profile = _profile(user)
        code = generate_otp(6)
        profile.set_reset_otp(code)
        sent = _send_reset_email(user, code)
        payload["email_sent"] = sent
        if expose_dev_codes():
            payload["dev_code"] = code
        return Response(payload)


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        code = ser.validated_data["code"].strip()
        new_password = ser.validated_data["new_password"]
        try:
            user = User.objects.get(email__iexact=email)
            profile = _profile(user)
        except User.DoesNotExist:
            return Response({"detail": "Invalid code or email."}, status=400)
        if not profile.check_reset_otp(code):
            return Response({"detail": "Invalid or expired code."}, status=400)
        user.set_password(new_password)
        user.save()
        profile.email_verified = True
        profile.save(update_fields=["email_verified", "updated_at"])
        data = tokens_for_user(user)
        data["user"] = UserSerializer(user).data
        data["detail"] = "Password updated."
        return Response(data)


class MagicLinkRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = EmailOnlySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        payload = {"detail": "If an account exists, a magic link was sent."}
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(payload)
        profile = _profile(user)
        raw = profile.issue_magic_token()
        sent = _send_magic_email(user, raw)
        payload["email_sent"] = sent
        if expose_dev_codes():
            payload["dev_token"] = raw
        return Response(payload)


class MagicLinkVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = MagicLinkVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        token = ser.validated_data["token"]
        try:
            user = User.objects.get(email__iexact=email)
            profile = _profile(user)
        except User.DoesNotExist:
            return Response({"detail": "Invalid or expired link."}, status=400)
        if not profile.verify_magic_token(token):
            return Response({"detail": "Invalid or expired link."}, status=400)
        data = tokens_for_user(user)
        data["user"] = UserSerializer(user).data
        return Response(data)
