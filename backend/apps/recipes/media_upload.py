import os
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.authentication import SessionAuthentication  # UPLOAD_MEDIA_AUTH
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication  # UPLOAD_MEDIA_AUTH

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE = 200 * 1024 * 1024  # 200 MB


# MG_ADMINUPLOAD: проверка и сохранение файла — одни на оба входа (API для веба,
# админский для админки). Раньше это жило внутри вьюхи, и второй вход пришлось бы
# писать заново.
def save_media(file, media_type: str = "image"):
    """Сохраняет файл. Возвращает (относительный путь, ошибка). Ошибка — текст."""
    if not file:
        return None, "Файл не передан."

    content_type = file.content_type or ""

    if media_type == "image":
        if content_type not in ALLOWED_IMAGE_TYPES:
            return None, "Допустимы только JPEG, PNG, WebP, GIF."
        if file.size > MAX_IMAGE_SIZE:
            return None, "Изображение не должно превышать 10 МБ."
        folder = "recipes/images"
    else:
        if content_type not in ALLOWED_VIDEO_TYPES:
            return None, "Допустимы только MP4, WebM, MOV."
        if file.size > MAX_VIDEO_SIZE:
            return None, "Видео не должно превышать 200 МБ."
        folder = "recipes/videos"

    ext = os.path.splitext(file.name)[1].lower()
    filename = f"{folder}/{uuid.uuid4().hex}{ext}"
    saved_path = default_storage.save(filename, ContentFile(file.read()))
    return settings.MEDIA_URL + saved_path, None


class RecipeMediaUploadView(APIView):
    parser_classes = [MultiPartParser]
    # UPLOAD_MEDIA_AUTH: JWT for web client, Session for Django admin
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "format": "binary"},
                    "media_type": {"type": "string", "enum": ["image", "video"]},
                },
            }
        },
        responses={200: {"type": "object", "properties": {"url": {"type": "string"}}}},
    )
    def post(self, request):
        path, error = save_media(request.FILES.get("file"), request.data.get("media_type", "image"))
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"url": request.build_absolute_uri(path)})
