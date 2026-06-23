from django.db import migrations

FREE_PLAN = {
    "name": "Бесплатный",
    "price": 0,
    "period": "month",
    "max_family_members": 1,
    "features": {"menu_generations_per_month": 4},
    "is_active": True,
    "sort_order": 0,
}


def create_free_plan(apps, schema_editor):
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    SubscriptionPlan.objects.update_or_create(code="free", defaults=FREE_PLAN)


def remove_free_plan(apps, schema_editor):
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(code="free").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0002_menugenerationcounter"),
    ]

    operations = [
        migrations.RunPython(create_free_plan, remove_free_plan),
    ]
