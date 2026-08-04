# MG_GALLERY: дополнительные фото блюда в карточке рецепта.
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.recipes.models import Recipe, RecipeImage
from apps.users.models import User

# 1x1 GIF — минимальная валидная картинка, чтобы ImageField принял файл.
PIXEL = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def make_recipe(**kwargs) -> Recipe:
    r = Recipe(title=kwargs.pop("title", "Рецепт"), **kwargs)
    r._mg_skip_link_rebuild = True
    r.save()
    return r


def add_photo(recipe, name="a.gif", caption="", sort_order=0) -> RecipeImage:
    return RecipeImage.objects.create(
        recipe=recipe,
        image=SimpleUploadedFile(name, PIXEL, content_type="image/gif"),
        caption=caption,
        sort_order=sort_order,
    )


@pytest.fixture
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    settings.MEDIA_URL = "/media/"
    return tmp_path


@pytest.mark.django_db
class TestModel:
    def test_порядок_задаётся_вручную(self, media):
        recipe = make_recipe()
        add_photo(recipe, "third.gif", sort_order=3)
        add_photo(recipe, "first.gif", sort_order=1)
        add_photo(recipe, "second.gif", sort_order=2)

        assert [p.sort_order for p in recipe.gallery_images.all()] == [1, 2, 3]

    def test_при_равном_порядке_сортировка_стабильна(self, media):
        """Иначе выдача «прыгала» бы между запросами."""
        recipe = make_recipe()
        first = add_photo(recipe, "a.gif")
        second = add_photo(recipe, "b.gif")

        assert list(recipe.gallery_images.values_list("id", flat=True)) == [first.id, second.id]

    def test_удаление_рецепта_уносит_фото(self, media):
        recipe = make_recipe()
        add_photo(recipe)

        recipe.delete()

        assert RecipeImage.objects.count() == 0


@pytest.mark.django_db
class TestApi:
    @pytest.fixture
    def client(self):
        from rest_framework.test import APIClient

        return APIClient()

    def test_галерея_в_карточке_рецепта(self, client, media):
        recipe = make_recipe(image_url="/media/recipes/images/cover.png")
        add_photo(recipe, "side.gif", caption="Вид сбоку", sort_order=1)

        resp = client.get(reverse("recipe-detail", args=[recipe.id]))

        assert resp.status_code == 200
        gallery = resp.data["gallery"]
        assert len(gallery) == 1
        assert gallery[0]["caption"] == "Вид сбоку"
        assert gallery[0]["url"].endswith(".gif")
        # обложка остаётся отдельным полем — это первый слайд галереи
        assert resp.data["image_url"].endswith("cover.png")

    def test_без_фото_галерея_пустая(self, client, media):
        recipe = make_recipe()

        resp = client.get(reverse("recipe-detail", args=[recipe.id]))

        assert resp.data["gallery"] == []

    def test_галерея_видна_без_авторизации(self, client, media):
        """В отличие от «я приготовил», это часть рецепта — видна всем."""
        recipe = make_recipe()
        add_photo(recipe, "public.gif")

        resp = client.get(reverse("recipe-detail", args=[recipe.id]))

        assert len(resp.data["gallery"]) == 1
        assert resp.data["made_photos"] == []

    def test_порядок_сохраняется_в_выдаче(self, client, media):
        recipe = make_recipe()
        add_photo(recipe, "b.gif", caption="второе", sort_order=2)
        add_photo(recipe, "a.gif", caption="первое", sort_order=1)

        resp = client.get(reverse("recipe-detail", args=[recipe.id]))

        assert [p["caption"] for p in resp.data["gallery"]] == ["первое", "второе"]

    def test_абсолютный_url_через_backend_public_url(self, client, media, monkeypatch):
        monkeypatch.setenv("BACKEND_PUBLIC_URL", "https://menugen.ru")
        recipe = make_recipe()
        add_photo(recipe, "x.gif")

        resp = client.get(reverse("recipe-detail", args=[recipe.id]))

        assert resp.data["gallery"][0]["url"].startswith("https://menugen.ru/media/")


@pytest.mark.django_db
class TestAdmin:
    def test_инлайн_подключён_к_рецепту(self):
        from django.contrib import admin as dj_admin

        from apps.recipes.admin import RecipeImageInline

        inlines = dj_admin.site._registry[Recipe].inlines
        assert RecipeImageInline in inlines

    def test_превью_без_файла_не_падает(self):
        from django.contrib import admin as dj_admin

        from apps.recipes.admin import RecipeImageInline

        inline = RecipeImageInline(Recipe, dj_admin.site)
        assert inline.preview(None) == "—"
        assert inline.preview(RecipeImage()) == "—"

    def test_админ_видит_галерею_в_карточке(self, media, client_admin):
        recipe = make_recipe()
        add_photo(recipe, "in_admin.gif")

        resp = client_admin.get(f"/admin/recipes/recipe/{recipe.id}/change/")

        assert resp.status_code == 200
        assert b"gallery_images" in resp.content


@pytest.fixture
def client_admin(db):
    from django.test import Client

    User.objects.create_superuser(email="admin@example.com", password="pass1234", name="Админ")
    c = Client()
    c.login(username="admin@example.com", password="pass1234")
    return c
