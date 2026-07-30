from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

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
