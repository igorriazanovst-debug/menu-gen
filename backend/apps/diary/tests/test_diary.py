import datetime
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.diary.models import DiaryEntry, WaterLog
from apps.recipes.models import Recipe
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="diary@example.com", name="Юзер", password="pass1234")
    family = Family.objects.create(owner=user)
    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    recipe = Recipe.objects.create(
        title="Овсянка",
        ingredients=[],
        steps=[],
        nutrition={"calories": {"value": "300", "unit": "ккал"}, "proteins": {"value": "10", "unit": "г"},
                   "fats": {"value": "5", "unit": "г"}, "carbs": {"value": "50", "unit": "г"}},
        is_published=True,
    )
    return user, member, recipe


@pytest.mark.django_db
class TestDiaryCreate:
    def test_add_with_recipe(self, client, setup):
        user, _, recipe = setup
        client.force_authenticate(user)
        resp = client.post(reverse("diary-list"), {
            "date": str(datetime.date.today()),
            "meal_type": "breakfast",
            "recipe": recipe.id,
            "quantity": 1,
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["recipe_title"] == "Овсянка"

    def test_add_custom(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.post(reverse("diary-list"), {
            "date": str(datetime.date.today()),
            "meal_type": "snack",
            "custom_name": "Яблоко",
            "nutrition": {"calories": {"value": "80", "unit": "ккал"}},
            "quantity": 1,
        }, format="json")
        assert resp.status_code == 201

    def test_add_no_recipe_or_name(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.post(reverse("diary-list"), {
            "date": str(datetime.date.today()),
            "meal_type": "lunch",
            "quantity": 1,
        }, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestDiaryList:
    def test_list_by_date(self, client, setup):
        user, member, recipe = setup
        today = datetime.date.today()
        DiaryEntry.objects.create(member=member, date=today, meal_type="breakfast",
                                  recipe=recipe, nutrition={}, quantity=1)
        client.force_authenticate(user)
        resp = client.get(reverse("diary-list"), {"date": str(today)})
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1

    def test_list_empty_date(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.get(reverse("diary-list"), {"date": "2000-01-01"})
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 0


@pytest.mark.django_db
class TestDiaryStats:
    def test_stats(self, client, setup):
        user, member, recipe = setup
        today = datetime.date.today()
        DiaryEntry.objects.create(member=member, date=today, meal_type="breakfast",
                                  recipe=recipe, nutrition=recipe.nutrition, quantity=1)
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(today), "to": str(today)})
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["calories"] == 300.0


@pytest.mark.django_db
class TestWaterLog:
    def test_set_water(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.post(reverse("diary-water"), {
            "date": str(datetime.date.today()), "water_ml": 1500
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["water_ml"] == 1500

    def test_update_water_idempotent(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        today = str(datetime.date.today())
        client.post(reverse("diary-water"), {"date": today, "water_ml": 500}, format="json")
        resp = client.post(reverse("diary-water"), {"date": today, "water_ml": 2000}, format="json")
        assert resp.status_code == 200
        assert resp.data["water_ml"] == 2000
        assert WaterLog.objects.filter(date=today).count() == 1

    def test_get_water(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.get(reverse("diary-water"), {"date": str(datetime.date.today())})
        assert resp.status_code == 200
        assert resp.data["water_ml"] == 0
