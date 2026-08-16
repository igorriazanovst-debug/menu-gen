"""MG_PAYPERIOD: периоды покупки премиума — месяц и год.

Цены здесь стартовые: они правятся в админке без выкладки, поэтому существующие
значения миграция не трогает (update_or_create только создаёт недостающее).

Тариф остаётся один (`premium`): премиум по всему коду определяется точным
сравнением `plan.code == "premium"`, и отдельный план `premium_year` его просто
не включил бы.
"""

from decimal import Decimal

from django.db import migrations

PREMIUM_CODE = "premium"

OFFERS = [
    {
        "code": "premium_month",
        "title": "Месяц",
        "months": 1,
        "price": Decimal("299.00"),
        "sort_order": 10,
    },
    {
        "code": "premium_year",
        "title": "Год",
        "months": 12,
        "price": Decimal("2990.00"),
        "sort_order": 20,
    },
]


def create_offers(apps, schema_editor):
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    PlanOffer = apps.get_model("subscriptions", "PlanOffer")

    plan = SubscriptionPlan.objects.filter(code=PREMIUM_CODE).first()
    if plan is None:
        # Тариф заводится в админке. Создавать его здесь нельзя: на чистой базе
        # (тесты, CI) он появился бы до фикстур, и каждая из 30+ проверок,
        # создающих `premium` руками, падала бы на уникальном индексе.
        # Без тарифа периодов просто нет — это видно сразу, в админке лечится.
        return

    for offer in OFFERS:
        PlanOffer.objects.get_or_create(
            code=offer["code"],
            defaults={**offer, "plan_id": plan.id, "is_active": True},
        )


def drop_offers(apps, schema_editor):
    PlanOffer = apps.get_model("subscriptions", "PlanOffer")
    PlanOffer.objects.filter(code__in=[o["code"] for o in OFFERS]).delete()


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0007_planoffer")]

    operations = [migrations.RunPython(create_offers, drop_offers)]
