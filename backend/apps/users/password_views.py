"""MG_PWDRESET: ручки восстановления пароля.

Две штуки: попросить письмо и задать новый пароль по ссылке из него. Обе
публичные — человек, забывший пароль, войти не может по определению.
"""

from django.conf import settings as dj_settings
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User

from .password_reset import read_token, send_reset_email, send_reset_via_messenger


class PasswordResetRequestView(APIView):
    """POST /auth/password-reset/request/ {email} либо {phone} — ссылка на смену.

    Куда придёт ссылка, определяет не пользователь, а то, чем он подтверждал
    владение: адрес — письмом, номер — сообщением в мессенджер, где он делился
    контактом при регистрации.

    Ответ одинаков независимо от того, нашёлся аккаунт или нет: иначе форма
    превратилась бы в проверку «зарегистрирован ли такой e-mail (или номер)»,
    доступную кому угодно без входа. Ровно как в форме удаления аккаунта. По
    той же причине в ответе не сказано, В КАКОЙ мессенджер ушло сообщение:
    название провайдера — это уже сведения об аккаунте.
    """

    permission_classes = (permissions.AllowAny,)
    # Пустой список намеренно: в приложении может лежать протухший токен, и
    # разбор заголовка Authorization вернул бы 401 вместо формы.
    authentication_classes = ()

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        phone = (request.data.get("phone") or "").strip()

        if phone and not email:
            return self._by_phone(phone)
        return self._by_email(email)

    def _by_email(self, email: str):
        payload = {
            "detail": (
                "Если аккаунт с таким адресом существует, мы отправили письмо со ссылкой "
                "для смены пароля. Ссылка действует 2 часа."
            )
        }
        if email:
            user = User.objects.filter(email__iexact=email).first()
            # has_usable_password: у аккаунтов, заведённых только по телефону,
            # пароль есть всегда, но проверка дешёвая и защищает от рассылки
            # писем на аккаунты, которым сбрасывать нечего.
            if user and user.has_usable_password():
                link = send_reset_email(user)
                if dj_settings.DEBUG:  # dev, где почта не настроена
                    payload["reset_link"] = link
        return Response(payload)

    def _by_phone(self, phone: str):
        from .phone_verify import normalize_phone

        payload = {
            "detail": (
                "Если аккаунт с таким номером существует, мы отправили ссылку для смены пароля "
                "в мессенджер, где вы подтверждали номер. Ссылка действует 2 часа."
            )
        }
        norm = normalize_phone(phone)
        if norm:
            user = User.objects.filter(phone=norm).first()
            if user and user.has_usable_password():
                link = send_reset_via_messenger(user)
                if link and dj_settings.DEBUG:  # dev, где бот может быть выключен
                    payload["reset_link"] = link
        return Response(payload)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    # min_length=5 — ровно как при регистрации (RegisterSerializer). Полный
    # набор AUTH_PASSWORD_VALIDATORS здесь НЕ гоняем сознательно: регистрация
    # его не гоняет тоже, и иначе человек не смог бы задать тот же пароль,
    # который у него уже был принят при заведении аккаунта.
    password = serializers.CharField(min_length=5)
    password2 = serializers.CharField()

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError("Пароли не совпадают.")
        return attrs


class PasswordResetConfirmView(APIView):
    """POST /auth/password-reset/confirm/ {token, password, password2}."""

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: None})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = read_token(serializer.validated_data["token"])
        if user is None:
            return Response(
                {"detail": "Ссылка недействительна или устарела.", "code": "invalid_token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["password"])
        fields = ["password"]

        # MG_EMAILVERIFY: переход по ссылке из письма — то же доказательство
        # владения адресом, что и подтверждение регистрации. Не отмечать было
        # бы издевательством: человек сменил пароль и всё равно упёрся бы в
        # «подтвердите e-mail», причём письмо на подтверждение пришло бы в тот
        # же ящик, куда он только что заходил.
        if user.email and user.email_verified_at is None:
            from django.utils import timezone

            user.email_verified_at = timezone.now()
            fields.append("email_verified_at")

        user.save(update_fields=fields)

        # Токены НЕ выдаём, вход остаётся отдельным действием. Причина не в
        # удобстве, а в MG_ACCDEL: вход — это отмена запланированного удаления
        # аккаунта, и такое решение человек должен принять сам, а не получить
        # побочным эффектом смены пароля.
        return Response({"detail": "Пароль изменён. Теперь войдите с новым паролем."})
