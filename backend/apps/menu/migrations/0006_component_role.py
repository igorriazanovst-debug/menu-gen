# Generated manually for MG-301 — component_role
from django.db import migrations, models


SALAD_CATS = {"салат", "salad", "овощное", "vegetables", "овощи", "клетчатка", "fiber", "зелень"}
SALAD_KW   = ("салат", "salad", "овощной", "зелёный", "греческий", "цезарь")

ALLOWED_ROLES = {"protein", "grain", "vegetable", "fruit", "dairy", "oil"}


def _is_salad(recipe) -> bool:
    cats = {c.lower() for c in (recipe.categories or [])}
    if cats & SALAD_CATS:
        return True
    title = (recipe.title or "").lower()
    return any(kw in title for kw in SALAD_KW)


def _role_for(item):
    if getattr(item, "is_salad", False):
        return "vegetable"
    fg = getattr(item.recipe, "food_group", None) or ""
    if fg in ALLOWED_ROLES:
        return fg
    if _is_salad(item.recipe):
        return "vegetable"
    return "other"


def forwards(apps, schema_editor):
    MenuItem = apps.get_model("menu", "MenuItem")

    # шаг 1: проставить component_role
    for item in MenuItem.objects.select_related("recipe").iterator():
        item.component_role = _role_for(item)
        item.save(update_fields=["component_role"])

    # шаг 2: дедупликация по (menu, member, day_offset, meal_slot, component_role)
    # внутри каждой группы оставляем самую раннюю запись (min id), остальные удаляем
    from collections import defaultdict
    groups = defaultdict(list)
    for item in MenuItem.objects.all().only("id", "menu_id", "member_id", "day_offset", "meal_slot", "component_role"):
        key = (item.menu_id, item.member_id, item.day_offset, item.meal_slot, item.component_role)
        groups[key].append(item.id)

    to_delete = []
    for key, ids in groups.items():
        if len(ids) > 1:
            ids.sort()
            to_delete.extend(ids[1:])

    if to_delete:
        MenuItem.objects.filter(id__in=to_delete).delete()


def backwards(apps, schema_editor):
    MenuItem = apps.get_model("menu", "MenuItem")
    MenuItem.objects.filter(component_role="vegetable").update(is_salad=True)


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0005_menuitem_meal_slot"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="menuitem",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="menuitem",
            name="component_role",
            field=models.CharField(
                choices=[
                    ("protein",   "Белок"),
                    ("grain",     "Крупа/гарнир"),
                    ("vegetable", "Овощи"),
                    ("fruit",     "Фрукт"),
                    ("dairy",     "Молочное"),
                    ("oil",       "Масло"),
                    ("other",     "Прочее"),
                ],
                default="other",
                max_length=20,
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="menuitem",
            name="is_salad",
        ),
        migrations.AlterUniqueTogether(
            name="menuitem",
            unique_together={("menu", "member", "day_offset", "meal_slot", "component_role")},
        ),
    ]
