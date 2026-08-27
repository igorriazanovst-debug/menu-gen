"""MG_PLANFORM: возможности тарифа правятся галочками, а не JSON руками.

Раньше `features` показывался в админке текстовой областью с JSON. Поле
обязательное, поэтому пустая или кривая строка валила сохранение всей формы —
включая цену, которую в этот момент и правили («Please correct the error
below» под полем Features).

Проверяем: форма разбирает JSON на галочки, собирает обратно и не теряет то,
чего в галочках нет.
"""

from decimal import Decimal

import pytest

from apps.subscriptions.admin import SubscriptionPlanForm
from apps.subscriptions.models import SubscriptionPlan


def plan(**kwargs):
    """Тариф с заданными features.

    update_or_create, а не create: тариф `free` заводит миграция, и на нём
    create упал бы на уникальном коде.
    """
    data = {
        "name": "Премиум",
        "price": Decimal("500.00"),
        "period": SubscriptionPlan.Period.MONTH,
        "max_family_members": 6,
        "features": {},
    }
    data.update(kwargs)
    code = data.pop("code", "premium")
    obj, _ = SubscriptionPlan.objects.update_or_create(code=code, defaults=data)
    return obj


def form_data(**overrides):
    """Поля модели, которые форма требует; features среди них нет."""
    data = {
        "code": "premium",
        "name": "Премиум",
        "price": "500.00",
        "period": SubscriptionPlan.Period.MONTH,
        "max_family_members": "6",
        "sort_order": "0",
        "is_active": "on",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestInitial:
    def test_галочки_расставлены_по_текущему_json(self):
        p = plan(features={"country": True, "fridge": True})

        f = SubscriptionPlanForm(instance=p)

        assert set(f.fields["feature_flags"].initial) == {"country", "fridge"}

    def test_лимит_подставляется_числом(self):
        p = plan(code="free", features={"menu_generations_per_month": 4})

        f = SubscriptionPlanForm(instance=p)

        assert f.fields["menu_generations_per_month"].initial == 4

    def test_выключенная_возможность_не_отмечена(self):
        """False в JSON — это «выключено», а не «есть ключ, значит галочка»."""
        p = plan(features={"country": True, "fridge": False})

        f = SubscriptionPlanForm(instance=p)

        assert set(f.fields["feature_flags"].initial) == {"country"}


@pytest.mark.django_db
class TestSave:
    def test_форма_валидна_без_поля_features(self):
        """Та самая регрессия: JSON больше не спрашивают, значит и не ломает."""
        p = plan()

        f = SubscriptionPlanForm(data=form_data(price="500.00"), instance=p)

        assert f.is_valid(), f.errors
        assert f.save().price == Decimal("500.00")

    def test_галочки_собираются_в_json(self):
        p = plan()

        f = SubscriptionPlanForm(
            data=form_data(feature_flags=["country", "calories", "fridge", "allergies_family"]),
            instance=p,
        )
        assert f.is_valid(), f.errors
        f.save()

        p.refresh_from_db()
        assert p.features == {"country": True, "calories": True, "fridge": True, "allergies_family": True}

    def test_снятая_галочка_убирает_ключ(self):
        p = plan(features={"country": True, "fridge": True})

        f = SubscriptionPlanForm(data=form_data(feature_flags=["country"]), instance=p)
        assert f.is_valid(), f.errors
        f.save()

        p.refresh_from_db()
        assert p.features == {"country": True}

    def test_незнакомые_ключи_сохраняются(self):
        """Форма показывает не всё, что бывает в features, — стирать нельзя."""
        p = plan(features={"country": True, "horeca_seats": 40})

        f = SubscriptionPlanForm(data=form_data(feature_flags=["country"]), instance=p)
        assert f.is_valid(), f.errors
        f.save()

        p.refresh_from_db()
        assert p.features == {"country": True, "horeca_seats": 40}

    def test_лимит_записывается_числом(self):
        p = plan(code="free", features={})

        f = SubscriptionPlanForm(data=form_data(code="free", menu_generations_per_month="4"), instance=p)
        assert f.is_valid(), f.errors
        f.save()

        p.refresh_from_db()
        assert p.features == {"menu_generations_per_month": 4}

    def test_пустой_лимит_убирает_ключ(self):
        """Пусто — значит «без ограничения», а не ноль генераций."""
        p = plan(code="free", features={"menu_generations_per_month": 4})

        f = SubscriptionPlanForm(data=form_data(code="free", menu_generations_per_month=""), instance=p)
        assert f.is_valid(), f.errors
        f.save()

        p.refresh_from_db()
        assert "menu_generations_per_month" not in p.features

    def test_отрицательный_лимит_отклоняется(self):
        p = plan(code="free")

        f = SubscriptionPlanForm(data=form_data(code="free", menu_generations_per_month="-1"), instance=p)

        assert not f.is_valid()
        assert "menu_generations_per_month" in f.errors
