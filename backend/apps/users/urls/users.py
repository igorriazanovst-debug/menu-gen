from django.urls import path

from apps.users.views import (
    CalculatorApplyView,
    CalculatorPreviewView,
    TargetHistoryView,
    TargetResetView,
    UserMeView,
)

urlpatterns = [
    # MG_205UI_V_urls = 1
    path("me/targets/<str:field>/history/", TargetHistoryView.as_view(), name="users-me-target-history"),
    path("me/targets/<str:field>/reset/", TargetResetView.as_view(), name="users-me-target-reset"),
    # MG_206_V_urls = 1
    path("me/calculator/preview/", CalculatorPreviewView.as_view(), name="users-me-calc-preview"),
    path("me/calculator/apply/",   CalculatorApplyView.as_view(),   name="users-me-calc-apply"),
    path("me/", UserMeView.as_view(), name="users-me"),
]
