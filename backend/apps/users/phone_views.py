"""MG_PHONEVERIFY: эндпоинты подтверждения телефона и регистрации по нему.

Флоу:
  1. POST /auth/phone/start/    {phone, provider}  → {token, deep_link, bot_username}
  2. (пользователь подтверждает номер в боте — webhook/polling)
  3. GET  /auth/phone/status/?token=…             → {status}
  4. POST /auth/phone/register/ {token, name, password, password2} → JWT
"""

import logging

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import phone_verify as pv_mod
from .models import PhoneVerification
from .serializers import PhoneRegisterSerializer, PhoneStartSerializer, TokenPairSerializer

log = logging.getLogger(__name__)


class PhoneStartView(APIView):
    """POST /auth/phone/start/ — создаёт заявку и отдаёт deep-link на бота."""

    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=PhoneStartSerializer, responses={201: None})
    def post(self, request):
        from .messengers import get_provider

        ser = PhoneStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        phone = ser.validated_data["phone"]
        provider_name = ser.validated_data["provider"]

        if pv_mod.phone_taken(phone):
            return Response(
                {"detail": "Аккаунт с таким телефоном уже существует. Войдите по паролю.", "code": "phone_taken"},
                status=status.HTTP_409_CONFLICT,
            )

        provider = get_provider(provider_name)
        if not provider.enabled:
            return Response(
                {"detail": "Подтверждение через этот мессенджер пока недоступно.", "code": "provider_unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        pv = pv_mod.create_verification(phone, provider_name)
        return Response(
            {
                "token": pv.token,
                "provider": provider_name,
                "deep_link": provider.build_deep_link(pv.token),
                "bot_username": provider.bot_username(),
                "expires_at": pv.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )


class PhoneStatusView(APIView):
    """GET /auth/phone/status/?token=… — опрос статуса подтверждения."""

    permission_classes = (permissions.AllowAny,)

    @extend_schema(responses={200: None})
    def get(self, request):
        token = request.query_params.get("token") or ""
        pv = pv_mod.get_active(token)
        if pv is None:
            return Response(
                {"detail": "Заявка не найдена.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        payload = {"status": pv.status}
        # Подсказки для UI при неуспешной сверке.
        if pv.status == PhoneVerification.Status.MISMATCH:
            payload["messenger_phone"] = pv.messenger_phone
        return Response(payload)


class PhoneRegisterView(APIView):
    """POST /auth/phone/register/ — завершает регистрацию после подтверждения."""

    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=PhoneRegisterSerializer, responses={201: TokenPairSerializer})
    def post(self, request):
        from apps.users.views import _bootstrap_user  # переиспользуем bootstrap

        ser = PhoneRegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        token = ser.validated_data["token"]

        pv = pv_mod.get_active(token)
        if pv is None:
            return Response(
                {"detail": "Заявка не найдена.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if pv.status != PhoneVerification.Status.VERIFIED:
            return Response(
                {"detail": "Номер ещё не подтверждён.", "code": "not_verified", "status": pv.status},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if pv_mod.phone_taken(pv.phone):
            return Response(
                {"detail": "Аккаунт с таким телефоном уже существует.", "code": "phone_taken"},
                status=status.HTTP_409_CONFLICT,
            )

        from .models import Profile, User

        with transaction.atomic():
            user = User(name=ser.validated_data["name"], phone=pv.phone)
            user.set_password(ser.validated_data["password"])
            user.save()
            Profile.objects.create(user=user)
            _bootstrap_user(user)
            pv.status = PhoneVerification.Status.CONSUMED
            pv.save(update_fields=["status"])

        return Response(TokenPairSerializer.get_tokens(user), status=status.HTTP_201_CREATED)


class TelegramWebhookView(APIView):
    """POST /auth/telegram/webhook/ — приём апдейтов Telegram (прод).

    Защита: секретный сегмент в URL (settings.TELEGRAM_WEBHOOK_SECRET) —
    Telegram шлёт заголовок X-Telegram-Bot-Api-Secret-Token, сверяем.
    """

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    @extend_schema(request=None, responses={200: None})
    def post(self, request, secret: str = ""):
        from django.conf import settings

        from .messengers import get_provider
        from .messengers.handler import handle_update

        expected = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "") or ""
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if expected and not (secret == expected or header == expected):
            return Response(status=status.HTTP_403_FORBIDDEN)

        handle_update(get_provider("telegram"), request.data or {})
        return Response({"ok": True})
