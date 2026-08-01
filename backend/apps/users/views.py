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


class AllergenListView(APIView):
    """GET /users/allergens/ — фиксированный список аллергенов (ТР ТС 022/2011,
    14 позиций) для выбора в профиле. Публичный справочник."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.common.allergens import public_allergens

        return Response(public_allergens())


class RegisterView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=RegisterSerializer, responses={201: None})
    def post(self, request):
        from django.conf import settings as dj_settings

        from .email_verify import send_verification_email

        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()
            _bootstrap_user(user)

        # MG_EMAILVERIFY: e-mail-регистрация требует подтверждения по ссылке.
        # Токены НЕ выдаём — вход только после подтверждения (строгий гейт).
        # Пользователи без e-mail (напр. только телефон) — подтверждать нечего.
        # Если проверка e-mail отключена флагом (почта ещё не настроена) —
        # ведём себя как раньше: подтверждаем сразу и пускаем в аккаунт.
        require_verify = getattr(dj_settings, "EMAIL_VERIFICATION_REQUIRED", True)
        payload = {
            "detail": "Регистрация почти завершена. Подтвердите e-mail по ссылке из письма.",
            "email": user.email,
            "requires_email_verification": bool(user.email) and require_verify,
        }
        if user.email and require_verify:
            link = send_verification_email(user)
            if dj_settings.DEBUG:  # для тестов на dev, когда почта не настроена
                payload["verify_link"] = link
        else:
            # Нет e-mail (телефонная регистрация) — сразу выдаём токены.
            from .email_verify import mark_verified

            mark_verified(user)
            payload = TokenPairSerializer.get_tokens(user)
        return Response(payload, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=LoginSerializer, responses={200: TokenPairSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        # MG_EMAILVERIFY: строгий гейт — не пускаем до подтверждения e-mail.
        # Ресенд НЕ автоматический (только по явному запросу /email/resend/).
        # Гейт отключаем флагом, пока отправка писем не настроена: иначе новый
        # пользователь не получит ссылку и не сможет войти вообще.
        from django.conf import settings as dj_settings

        if getattr(dj_settings, "EMAIL_VERIFICATION_REQUIRED", True) and user.email and not user.is_email_verified:
            return Response(
                {
                    "detail": "Подтвердите e-mail по ссылке из письма.",
                    "code": "email_not_verified",
                    "email": user.email,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        tokens = TokenPairSerializer.get_tokens(user)
        return Response(tokens)


class VerifyEmailView(APIView):
    """POST /auth/email/verify/ {token} — подтверждение e-mail, выдаёт токены (вход)."""

    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=None, responses={200: TokenPairSerializer})
    def post(self, request):
        from apps.users.models import User

        from .email_verify import mark_verified, read_token

        token = request.data.get("token") or request.query_params.get("token")
        user_id = read_token(token or "")
        if not user_id:
            return Response(
                {"detail": "Ссылка недействительна или устарела.", "code": "invalid_token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "Пользователь не найден."}, status=status.HTTP_400_BAD_REQUEST)
        mark_verified(user)
        return Response(TokenPairSerializer.get_tokens(user))


class ResendVerificationView(APIView):
    """POST /auth/email/resend/ {email} — повторная отправка письма (по запросу)."""

    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        from django.conf import settings as dj_settings

        from apps.users.models import User

        from .email_verify import send_verification_email

        email = (request.data.get("email") or "").strip().lower()
        payload = {"detail": "Если аккаунт существует и не подтверждён, письмо отправлено повторно."}
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user and not user.is_email_verified:
                link = send_verification_email(user)
                if dj_settings.DEBUG:
                    payload["verify_link"] = link
        return Response(payload)


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


class SetEmailView(APIView):
    """POST /users/me/email/ {email} — добавить/сменить e-mail в профиле.

    MG_EMAILVERIFY: e-mail сохраняется как НЕподтверждённый (email_verified_at=
    NULL) и отправляется письмо со ссылкой. Подтверждение — тем же механизмом,
    что и при регистрации (POST /auth/email/verify/ по токену из ссылки).
    """

    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        from django.conf import settings as dj_settings

        from apps.users.models import User

        from .email_verify import send_verification_email
        from .serializers import SetEmailSerializer

        ser = SetEmailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].strip().lower()
        user = request.user

        if user.email and user.email.lower() == email and user.is_email_verified:
            return Response({"detail": "Этот e-mail уже подтверждён.", "email": email, "email_verified": True})

        # Занят другим аккаунтом (регистронезависимо)?
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            return Response(
                {"detail": "Этот e-mail уже используется другим аккаунтом.", "code": "email_taken"},
                status=status.HTTP_409_CONFLICT,
            )

        user.email = email
        user.email_verified_at = None
        user.save(update_fields=["email", "email_verified_at"])

        link = send_verification_email(user)
        payload = {
            "detail": "Письмо со ссылкой отправлено. Подтвердите e-mail по ссылке.",
            "email": email,
            "requires_email_verification": True,
        }
        if dj_settings.DEBUG:  # dev без SMTP — отдаём ссылку в ответе
            payload["verify_link"] = link
        return Response(payload)


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


# ─────────────────────────────────────────────────────────────────────────────
# MG_206_V_views = 1
# KBJU calculator: preview (без сохранения) + apply (сохранение в Profile)
# ─────────────────────────────────────────────────────────────────────────────


class CalculatorPreviewView(APIView):
    """POST /users/me/calculator/preview/ — расчёт без сохранения."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        from apps.users.calculator import calculate
        from apps.users.serializers import CalculatorRequestSerializer, CalculatorResultSerializer

        ser = CalculatorRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            result = calculate(ser.validated_data)
        except (ValueError, KeyError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CalculatorResultSerializer(result).data)


class CalculatorApplyView(APIView):
    """POST /users/me/calculator/apply/ — расчёт + сохранение в Profile + аудит.
    Сохраняет в Profile как сами параметры (height/weight/birth_year/...),
    так и целевые КБЖУ. Аудит пишется с source='user'.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        from apps.users.audit import record_target_change
        from apps.users.calculator import calculate
        from apps.users.models import Profile, ProfileTargetAudit
        from apps.users.serializers import CalculatorRequestSerializer

        ser = CalculatorRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            result = calculate(ser.validated_data)
        except (ValueError, KeyError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        profile, _ = Profile.objects.get_or_create(user=request.user)

        # 1) Сохранить input-параметры (если переданы)
        params_fields = ("height_cm", "weight_kg", "birth_year", "gender", "activity_level", "goal")
        for f in params_fields:
            v = ser.validated_data.get(f)
            if v not in (None, ""):
                setattr(profile, f, v)

        # 2) Сохранить целевые КБЖУ + аудит с source='user'
        target_field_map = {
            "calorie_target": result["calorie_target"],
            "protein_target_g": result["protein_target_g"],
            "fat_target_g": result["fat_target_g"],
            "carb_target_g": result["carb_target_g"],
            "fiber_target_g": result["fiber_target_g"],
        }
        old_values = {f: getattr(profile, f, None) for f in target_field_map}
        for f, new_v in target_field_map.items():
            setattr(profile, f, new_v)
        profile.save()

        # Записать аудит для каждого изменённого поля
        sys_code = ser.validated_data.get("system")
        diet_code = ser.validated_data.get("diet")
        reason = f"calculator: system={sys_code}, diet={diet_code or '-'}"
        for f, new_v in target_field_map.items():
            record_target_change(
                profile=profile,
                field=f,
                new_value=new_v,
                source=ProfileTargetAudit.Source.USER,
                by_user=request.user,
                old_value=old_values.get(f),
                reason=reason,
            )

        return Response(UserMeSerializer(request.user).data)
