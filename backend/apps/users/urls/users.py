from django.urls import path

from apps.users.deletion_views import AccountDeleteView  # MG_ACCDEL
from apps.users.views import (
    AllergenListView,
    CalculatorApplyView,
    CalculatorPreviewView,
    SetEmailView,
    TargetHistoryView,
    TargetResetView,
    UserMeView,
)

urlpatterns = [
    # MG_ALLERGEN14: справочник аллергенов для профиля
    path("allergens/", AllergenListView.as_view(), name="users-allergens"),
    # MG_205UI_V_urls = 1
    path("me/targets/<str:field>/history/", TargetHistoryView.as_view(), name="users-me-target-history"),
    path("me/targets/<str:field>/reset/", TargetResetView.as_view(), name="users-me-target-reset"),
    # MG_206_V_urls = 1
    path("me/calculator/preview/", CalculatorPreviewView.as_view(), name="users-me-calc-preview"),
    path("me/calculator/apply/", CalculatorApplyView.as_view(), name="users-me-calc-apply"),
    # MG_EMAILVERIFY: добавить/сменить e-mail в профиле (с подтверждением)
    path("me/email/", SetEmailView.as_view(), name="users-me-set-email"),
    # MG_ACCDEL: удаление аккаунта из приложения (GET — что будет удалено).
    # Раньше «me/» — иначе путь съел бы префикс: RetrieveUpdateAPIView на
    # "me/" ничего не ловит лишнего, но порядок здесь и так значим.
    path("me/delete/", AccountDeleteView.as_view(), name="users-me-delete"),
    path("me/", UserMeView.as_view(), name="users-me"),
]
