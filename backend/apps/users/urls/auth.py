from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.deletion_views import PublicDeletionConfirmView, PublicDeletionRequestView  # MG_ACCDEL
from apps.users.password_views import PasswordResetConfirmView, PasswordResetRequestView  # MG_PWDRESET
from apps.users.phone_views import (  # MG_PHONEVERIFY
    MaxWebhookView,
    PhoneRegisterView,
    PhoneStartView,
    PhoneStatusView,
    TelegramWebhookView,
)
from apps.users.views import LoginView, LogoutView, RegisterView, ResendVerificationView, VerifyEmailView

urlpatterns = [
    path("email/register/", RegisterView.as_view(), name="auth-register"),
    path("email/verify/", VerifyEmailView.as_view(), name="auth-email-verify"),  # MG_EMAILVERIFY
    path("email/resend/", ResendVerificationView.as_view(), name="auth-email-resend"),  # MG_EMAILVERIFY
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    # MG_PWDRESET: забыл пароль. Обе ручки публичные — человек без пароля
    # войти не может, и требовать от него авторизации было бы замкнутым кругом.
    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="auth-password-reset-request",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    # MG_ACCDEL: удаление без входа в приложение — Google Play требует
    # публичный веб-адрес, доступный без авторизации. Подтверждение письмом.
    path(
        "account-deletion/request/",
        PublicDeletionRequestView.as_view(),
        name="auth-account-deletion-request",
    ),
    path(
        "account-deletion/confirm/",
        PublicDeletionConfirmView.as_view(),
        name="auth-account-deletion-confirm",
    ),
    # MG_PHONEVERIFY: регистрация/подтверждение телефона через мессенджер
    path("phone/start/", PhoneStartView.as_view(), name="auth-phone-start"),
    path("phone/status/", PhoneStatusView.as_view(), name="auth-phone-status"),
    path("phone/register/", PhoneRegisterView.as_view(), name="auth-phone-register"),
    path("telegram/webhook/", TelegramWebhookView.as_view(), name="auth-telegram-webhook"),
    path("telegram/webhook/<str:secret>/", TelegramWebhookView.as_view(), name="auth-telegram-webhook-secret"),
    # MG_PHONEVERIFY/max: у Max секрет передаётся сегментом URL (заголовка нет)
    path("max/webhook/", MaxWebhookView.as_view(), name="auth-max-webhook"),
    path("max/webhook/<str:secret>/", MaxWebhookView.as_view(), name="auth-max-webhook-secret"),
]
