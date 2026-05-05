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
    import datetime

    from django.utils import timezone

    from apps.family.models import Family, FamilyMember
    from apps.subscriptions.models import Subscription, SubscriptionPlan

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



# ─────────────────────────────────────────────────────────────────────────────
# MG_205UI_V_views = 1
# История правок целевых КБЖУ + сброс одного поля к авторасчёту.
# ─────────────────────────────────────────────────────────────────────────────

TARGET_FIELD_CHOICES = (
    "calorie_target",
    "protein_target_g",
    "fat_target_g",
    "carb_target_g",
    "fiber_target_g",
)


def _validate_target_field(field: str):
    if field not in TARGET_FIELD_CHOICES:
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"field": f"Допустимые значения: {list(TARGET_FIELD_CHOICES)}"})


class TargetHistoryView(APIView):
    """GET /users/me/targets/{field}/history/ — история правок одного поля."""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, field: str):
        _validate_target_field(field)
        from apps.users.models import ProfileTargetAudit
        from apps.users.serializers import ProfileTargetAuditSerializer

        profile = getattr(request.user, "profile", None)
        if profile is None:
            return Response([], status=status.HTTP_200_OK)

        qs = (
            ProfileTargetAudit.objects.filter(profile=profile, field=field)
            .select_related("by_user")
            .order_by("-at")[:100]
        )
        return Response(ProfileTargetAuditSerializer(qs, many=True).data)


class TargetResetView(APIView):
    """POST /users/me/targets/{field}/reset/ — пересчитать одно поле и снять lock."""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, field: str):
        _validate_target_field(field)
        from apps.users.audit import record_target_change
        from apps.users.nutrition import calculate_targets

        profile = getattr(request.user, "profile", None)
        if profile is None:
            return Response({"detail": "Профиль не найден."}, status=status.HTTP_404_NOT_FOUND)

        targets = calculate_targets(profile)
        if not targets:
            return Response(
                {"detail": "Недостаточно данных для расчёта (рост/вес/год рождения)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_value = getattr(profile, field, None)
        new_value = targets.get(field)
        setattr(profile, field, new_value)
        profile.save()

        # запись аудита: source='auto', by_user=request.user (инициатор reset)
        record_target_change(
            profile=profile,
            field=field,
            new_value=new_value,
            source="auto",
            by_user=request.user,
            old_value=old_value,
            reason=f"reset to auto by user {request.user.id}",
        )

        # Возвращаем обновлённого юзера (как и UserMeView)
        return Response(UserMeSerializer(request.user).data)
