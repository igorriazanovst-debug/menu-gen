from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.views import LoginView, LogoutView, RegisterView, ResendVerificationView, VerifyEmailView

urlpatterns = [
    path("email/register/", RegisterView.as_view(), name="auth-register"),
    path("email/verify/", VerifyEmailView.as_view(), name="auth-email-verify"),  # MG_EMAILVERIFY
    path("email/resend/", ResendVerificationView.as_view(), name="auth-email-resend"),  # MG_EMAILVERIFY
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
]
