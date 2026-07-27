from django.urls import path

from .views import LegalInfoView

urlpatterns = [
    path("", LegalInfoView.as_view(), name="legal-info"),
]
