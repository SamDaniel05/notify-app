from django.contrib.auth.models import User
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Profile
from .serializers import MagicLinkRequestSerializer, MagicLinkVerifySerializer, RegisterSerializer, UserSerializer

def tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}

class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = tokens_for_user(user)
        data["user"] = UserSerializer(user).data
        return Response(data, status=status.HTTP_201_CREATED)

class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    def get_object(self):
        return self.request.user
    def patch(self, request, *args, **kwargs):
        user = request.user
        profile, _ = Profile.objects.get_or_create(user=user)
        lang = request.data.get("preferred_language")
        name = request.data.get("display_name")
        if lang in ("en", "ta"):
            profile.preferred_language = lang
        if name is not None:
            profile.display_name = name[:120]
        profile.save()
        return Response(UserSerializer(user).data)

class MagicLinkRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        ser = MagicLinkRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"detail": "If an account exists, a magic link was issued.", "dev_token": None})
        profile, _ = Profile.objects.get_or_create(user=user)
        raw = profile.issue_magic_token()
        payload = {"detail": "If an account exists, a magic link was issued."}
        from django.conf import settings
        if settings.DEBUG:
            payload["dev_token"] = raw
            payload["dev_note"] = "DEBUG only"
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
            profile = user.profile
        except (User.DoesNotExist, Profile.DoesNotExist):
            return Response({"detail": "Invalid or expired link."}, status=400)
        if not profile.verify_magic_token(token):
            return Response({"detail": "Invalid or expired link."}, status=400)
        data = tokens_for_user(user)
        data["user"] = UserSerializer(user).data
        return Response(data)
