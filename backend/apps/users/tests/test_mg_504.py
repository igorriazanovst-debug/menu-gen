# MG_504_V_tests
"""MG-504: поля Profile для cheat-meal и времени отхода ко сну."""
from datetime import date

import pytest
from django.contrib.auth import get_user_model

from apps.users.models import Profile

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def profile():
    u = User.objects.create(name="MG504", email="mg504@test.local")
    u.set_password("xx")
    u.save()
    return Profile.objects.create(user=u)


def test_profile_has_mg_504_fields(profile):
    assert hasattr(profile, "bedtime_hour")
    assert hasattr(profile, "cheat_meal_interval")
    assert hasattr(profile, "last_cheat_meal_date")


def test_bedtime_hour_default_null(profile):
    assert profile.bedtime_hour is None


def test_cheat_meal_interval_default_10(profile):
    assert profile.cheat_meal_interval == 10


def test_last_cheat_meal_date_default_null(profile):
    assert profile.last_cheat_meal_date is None


def test_set_and_save_bedtime_hour(profile):
    profile.bedtime_hour = 23
    profile.save()
    profile.refresh_from_db()
    assert profile.bedtime_hour == 23


def test_set_cheat_meal_interval(profile):
    profile.cheat_meal_interval = 7
    profile.save()
    profile.refresh_from_db()
    assert profile.cheat_meal_interval == 7


def test_set_last_cheat_meal_date(profile):
    profile.last_cheat_meal_date = date(2026, 5, 1)
    profile.save()
    profile.refresh_from_db()
    assert profile.last_cheat_meal_date == date(2026, 5, 1)
