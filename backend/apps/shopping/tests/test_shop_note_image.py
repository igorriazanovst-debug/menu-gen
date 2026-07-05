"""MG_SHOPNOTE / MG_SHOPIMG: комментарий + изображение товара в списке покупок."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.shopping.models import ShoppingList, ShoppingListItem

User = get_user_model()

# 1x1 PNG.
_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


@pytest.fixture
def setup(db):
    u = User.objects.create_user(email="shop@a.a", password="x", name="S")
    fam = Family.objects.create(owner=u, name="F")
    FamilyMember.objects.create(family=fam, user=u, role=FamilyMember.Role.HEAD)
    sl = ShoppingList.objects.create(family=fam, name="L", created_by=u)
    return u, sl


@pytest.mark.django_db
class TestShopItemNoteImage:
    # pytest-django: MEDIA_ROOT во временную папку (image_b64 пишет файл).
    @pytest.fixture(autouse=True)
    def _tmp_media(self, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)

    def _client(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def test_create_with_note_and_image_url(self, setup):
        u, sl = setup
        c = self._client(u)
        r = c.post(
            reverse("shopping-items", args=[sl.id]),
            {"name": "Молоко", "note": "2.5%", "image_url": "https://x/y.png"},
            format="json",
        )
        assert r.status_code == 201, r.content
        assert r.data["note"] == "2.5%"
        assert r.data["image_url"] == "https://x/y.png"
        # без загруженного файла resolved image = сам url
        assert r.data["image"] == "https://x/y.png"

    def test_create_with_image_b64(self, setup):
        u, sl = setup
        c = self._client(u)
        r = c.post(
            reverse("shopping-items", args=[sl.id]),
            {"name": "Сыр", "image_b64": "data:image/png;base64," + _PNG},
            format="json",
        )
        assert r.status_code == 201, r.content
        item = ShoppingListItem.objects.get(id=r.data["id"])
        assert bool(item.image)  # файл сохранён
        assert r.data["image"]  # resolved url присутствует

    def test_edit_note_and_clear_image(self, setup):
        u, sl = setup
        item = ShoppingListItem.objects.create(shopping_list=sl, name="Хлеб", note="старый")
        c = self._client(u)
        r = c.patch(
            reverse("shopping-item-detail", args=[sl.id, item.id]),
            {"note": "чёрный"},
            format="json",
        )
        assert r.status_code == 200, r.content
        assert r.data["note"] == "чёрный"
        item.refresh_from_db()
        assert item.note == "чёрный"
