from django.urls import path

from apps.users.views import UserMeView

urlpatterns = [
    path("me/", UserMeView.as_view(), name="users-me"),
]
