from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AndroidBuild, LegalInfo
from .serializers import AndroidBuildSerializer, LegalInfoSerializer


class LegalInfoView(generics.RetrieveAPIView):
    """GET /api/v1/legal/ — публичные реквизиты + оферта + логотип."""

    permission_classes = [permissions.AllowAny]
    serializer_class = LegalInfoSerializer

    def get_object(self):
        return LegalInfo.load()


class AndroidBuildView(APIView):
    """MG_APKSITE: GET /api/v1/app/android/ — выложенная сборка приложения.

    Без входа: человек приходит на сайт именно за тем, чтобы поставить
    приложение. Пусто (null) — если выкладывать нечего, и тогда сайт про
    скачивание молчит, а не показывает битую ссылку.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        build = AndroidBuild.current()
        if build is None:
            return Response({"build": None})
        return Response({"build": AndroidBuildSerializer(build, context={"request": request}).data})
