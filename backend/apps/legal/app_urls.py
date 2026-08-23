"""MG_APKSITE: /api/v1/app/ — про приложение, а не про юридическую информацию.

Живёт в том же приложении Django: заводить отдельное ради одной модели и
одной ручки дороже, чем держать их рядом с прочей публичной информацией сайта.
"""

from django.urls import path

from .views import AndroidBuildView

urlpatterns = [
    path("android/", AndroidBuildView.as_view(), name="android-build"),
]
