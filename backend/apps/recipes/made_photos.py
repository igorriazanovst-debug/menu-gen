"""MG_MADEPHOTO: сохранение/выдача фото приготовленного блюда.

Фото приходит как `image_b64` (data-URL или голый base64) — единый путь для
веба (файл/буфер/камера) и мобилки (камера/галерея). Декодируем и кладём в
`RecipeMadePhoto.image`. URL отдаём абсолютным (BACKEND_PUBLIC_URL или
request.build_absolute_uri).
"""

import base64
import os
import uuid

from django.core.files.base import ContentFile

from .models import RecipeMadePhoto

_IMG_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def create_made_photo_from_b64(user, recipe, b64):
    """Создать RecipeMadePhoto из base64. Возвращает объект или None при ошибке."""
    s = (b64 or "").strip()
    if not s:
        return None
    ext = "png"
    if s.lower().startswith("data:") and "," in s:
        head, s = s.split(",", 1)
        mime = head[5:].split(";", 1)[0].strip().lower()
        ext = _IMG_EXT.get(mime, "png")
    try:
        raw = base64.b64decode(s, validate=False)
    except Exception:
        return None
    if not raw:
        return None
    photo = RecipeMadePhoto(user=user, recipe=recipe)
    photo.image.save(f"made_{uuid.uuid4().hex[:12]}.{ext}", ContentFile(raw), save=True)
    return photo


def resolve_made_photo_url(photo, request=None):
    """Абсолютный URL файла фото."""
    if not photo.image:
        return None
    url = photo.image.url
    public = (os.environ.get("BACKEND_PUBLIC_URL") or "").rstrip("/")
    if public and url.startswith("/"):
        return public + url
    if request is not None:
        return request.build_absolute_uri(url)
    return url
