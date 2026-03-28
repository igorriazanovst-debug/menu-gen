from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    TokenPairSerializer,
    UserMeSerializer,
    UserMeUpdateSerializer,
)


class RegisterView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=RegisterSerializer, responses={201: TokenPairSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()
            _bootstrap_user(user)
        tokens = TokenPairSerializer.get_tokens(user)
        return Response(tokens, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=LoginSerializer, responses={200: TokenPairSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = TokenPairSerializer.get_tokens(user)
        return Response(tokens)


class LogoutView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "refresh токен обязателен."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response({"detail": "Токен недействителен или уже отозван."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserMeView(generics.RetrieveUpdateAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserMeUpdateSerializer
        return UserMeSerializer

    @extend_schema(responses={200: UserMeSerializer})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=UserMeUpdateSerializer, responses={200: UserMeSerializer})
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(request=UserMeUpdateSerializer, responses={200: UserMeSerializer})
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)


# ── helpers ──────────────────────────────────────────────────────────────────


def _bootstrap_user(user):
    """Создаёт Family + Free подписку при регистрации."""
    from apps.family.models import Family, FamilyMember
    from apps.subscriptions.models import Subscription, SubscriptionPlan
    from django.utils import timezone
    import datetime

    family = Family.objects.create(owner=user, name=f"Семья {user.name}")
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)

    try:
        free_plan = SubscriptionPlan.objects.get(code="free")
        Subscription.objects.create(
            family=family,
            plan=free_plan,
            status=Subscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + datetime.timedelta(days=36500),
            auto_renew=False,
        )
    except SubscriptionPlan.DoesNotExist:
        pass
