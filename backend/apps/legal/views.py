from rest_framework import generics, permissions

from .models import LegalInfo
from .serializers import LegalInfoSerializer


class LegalInfoView(generics.RetrieveAPIView):
    """GET /api/v1/legal/ — публичные реквизиты + оферта + логотип."""

    permission_classes = [permissions.AllowAny]
    serializer_class = LegalInfoSerializer

    def get_object(self):
        return LegalInfo.load()
