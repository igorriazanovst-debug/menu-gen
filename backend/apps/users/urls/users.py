from django.urls import path

from apps.users.views import UserMeView, TargetHistoryView, TargetResetView

urlpatterns = [

    # MG_205UI_V_urls = 1
    path("me/targets/<str:field>/history/", TargetHistoryView.as_view(), name="users-me-target-history"),
    path("me/targets/<str:field>/reset/",   TargetResetView.as_view(),   name="users-me-target-reset"),
    path("me/", UserMeView.as_view(), name="users-me"),
]
