import os
import uuid
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10 MB
MAX_VIDEO_SIZE = 200 * 1024 * 1024  # 200 MB


class RecipeMediaUploadView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request={"multipart/form-data": {"type": "object", "properties": {
            "file": {"type": "string", "format": "binary"},
            "media_type": {"type": "string", "enum": ["image", "video"]},
        }}},
        responses={200: {"type": "object", "properties": {"url": {"type": "string"}}}},
    )
    def post(self, request):
        file = request.FILES.get("file")
        media_type = request.data.get("media_type", "image")

        if not file:
            return Response({"detail": "Файл не передан."}, status=status.HTTP_400_BAD_REQUEST)

        content_type = file.content_type or ""

        if media_type == "image":
            if content_type not in ALLOWED_IMAGE_TYPES:
                return Response({"detail": "Допустимы только JPEG, PNG, WebP, GIF."}, status=400)
            if file.size > MAX_IMAGE_SIZE:
                return Response({"detail": "Изображение не должно превышать 10 МБ."}, status=400)
            folder = "recipes/images"
        else:
            if content_type not in ALLOWED_VIDEO_TYPES:
                return Response({"detail": "Допустимы только MP4, WebM, MOV."}, status=400)
            if file.size > MAX_VIDEO_SIZE:
                return Response({"detail": "Видео не должно превышать 200 МБ."}, status=400)
            folder = "recipes/videos"

        ext = os.path.splitext(file.name)[1].lower()
        filename = f"{folder}/{uuid.uuid4().hex}{ext}"
        saved_path = default_storage.save(filename, ContentFile(file.read()))
        url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)
        return Response({"url": url})
