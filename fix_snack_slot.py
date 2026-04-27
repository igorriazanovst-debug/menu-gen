#!/usr/bin/env python3
"""
Фикс бага: 5 приёмов пищи не генерируются из-за IntegrityError.
Причина: snack1 и snack2 оба пишутся как meal_type="snack", нарушая unique_together.
Решение: добавить поле meal_slot, перенести unique_together на него.

Запускать из корня проекта: python fix_snack_slot.py
"""
import pathlib, sys, textwrap

ROOT = pathlib.Path(__file__).parent
BACKEND = ROOT / "backend"

def write(path, text):
    path.write_text(text, encoding="utf-8")
    print(f"✓ {path}")

# ── 1. models.py — добавить meal_slot ────────────────────────────────────────
models_path = BACKEND / "apps" / "menu" / "models.py"
src = models_path.read_text(encoding="utf-8")

OLD_ITEM = '''class MenuItem(models.Model):
    class MealType(models.TextChoices):
        BREAKFAST = "breakfast", "Завтрак"
        LUNCH = "lunch", "Обед"
        DINNER = "dinner", "Ужин"
        SNACK = "snack", "Перекус"

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="items")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    member = models.ForeignKey(FamilyMember, on_delete=models.CASCADE, null=True, blank=True)
    meal_type = models.CharField(max_length=20, choices=MealType.choices)
    day_offset = models.PositiveSmallIntegerField()
    quantity = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    is_salad = models.BooleanField(default=False)

    class Meta:
        db_table = "menu_items"
        unique_together = [("menu", "member", "day_offset", "meal_type", "is_salad")]'''

NEW_ITEM = '''class MenuItem(models.Model):
    class MealType(models.TextChoices):
        BREAKFAST = "breakfast", "Завтрак"
        LUNCH = "lunch", "Обед"
        DINNER = "dinner", "Ужин"
        SNACK = "snack", "Перекус"

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="items")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    member = models.ForeignKey(FamilyMember, on_delete=models.CASCADE, null=True, blank=True)
    meal_type = models.CharField(max_length=20, choices=MealType.choices)
    # meal_slot хранит точный слот: breakfast/lunch/dinner/snack1/snack2
    # нужен для различения двух перекусов при 5-разовом питании
    meal_slot = models.CharField(max_length=20, default="")
    day_offset = models.PositiveSmallIntegerField()
    quantity = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    is_salad = models.BooleanField(default=False)

    class Meta:
        db_table = "menu_items"
        unique_together = [("menu", "member", "day_offset", "meal_slot", "is_salad")]'''

if OLD_ITEM in src:
    write(models_path, src.replace(OLD_ITEM, NEW_ITEM))
else:
    print("WARN: models.py — паттерн не найден, проверь вручную")

# ── 2. views.py — сохранять meal_slot в bulk_create ──────────────────────────
views_path = BACKEND / "apps" / "menu" / "views.py"
src = views_path.read_text(encoding="utf-8")

OLD_BULK = '''            MenuItem.objects.bulk_create([
                MenuItem(
                    menu=menu,
                    recipe=item["recipe"],
                    member=item["member"],
                    meal_type=item["meal_type"],
                    day_offset=item["day_offset"],
                    is_salad=item.get("is_salad", False),
                )
                for item in generated
            ])'''

NEW_BULK = '''            MenuItem.objects.bulk_create([
                MenuItem(
                    menu=menu,
                    recipe=item["recipe"],
                    member=item["member"],
                    meal_type=item["meal_type"],
                    meal_slot=item.get("meal_slot", item["meal_type"]),
                    day_offset=item["day_offset"],
                    is_salad=item.get("is_salad", False),
                )
                for item in generated
            ])'''

if OLD_BULK in src:
    write(views_path, src.replace(OLD_BULK, NEW_BULK))
else:
    print("WARN: views.py — паттерн bulk_create не найден, проверь вручную")

# ── 3. generator.py — добавить meal_slot в возвращаемые dict ─────────────────
gen_path = BACKEND / "apps" / "menu" / "generator.py"
src = gen_path.read_text(encoding="utf-8")

OLD_MAIN = '''                    if recipe:
                        used_per_member[member.id].add(recipe.id)
                        items.append({
                            "member": member,
                            "meal_type": db_meal_type,
                            "meal_slot": meal_slot,
                            "day_offset": day,
                            "recipe": recipe,
                            "is_salad": False,
                        })

                    # салат / клетчатка
                    salad = self._pick_salad(
                        pool=salad_pool,
                        used=used_per_member[member.id],
                        hard_exclude=hard_exclude,
                    )
                    if salad:
                        used_per_member[member.id].add(salad.id)
                        items.append({
                            "member": member,
                            "meal_type": db_meal_type,
                            "meal_slot": meal_slot,
                            "day_offset": day,
                            "recipe": salad,
                            "is_salad": True,
                        })'''

# Проверяем, есть ли уже meal_slot в generator.py
if '"meal_slot": meal_slot' in src:
    print("✓ generator.py — meal_slot уже присутствует")
else:
    # Патчим старую версию без meal_slot
    OLD_GEN = '''                    if recipe:
                        used_per_member[member.id].add(recipe.id)
                        items.append({
                            "member": member,
                            "meal_type": db_meal_type,
                            "day_offset": day,
                            "recipe": recipe,
                            "is_salad": False,
                        })

                    # салат / клетчатка
                    salad = self._pick_salad(
                        pool=salad_pool,
                        used=used_per_member[member.id],
                        hard_exclude=hard_exclude,
                    )
                    if salad:
                        used_per_member[member.id].add(salad.id)
                        items.append({
                            "member": member,
                            "meal_type": db_meal_type,
                            "day_offset": day,
                            "recipe": salad,
                            "is_salad": True,
                        })'''
    if OLD_GEN in src:
        write(gen_path, src.replace(OLD_GEN, OLD_MAIN))
    else:
        print("WARN: generator.py — паттерн не найден, проверь вручную")

# ── 4. Миграция ───────────────────────────────────────────────────────────────
migrations_dir = BACKEND / "apps" / "menu" / "migrations"
migration_path = migrations_dir / "0005_menuitem_meal_slot.py"

migration_content = textwrap.dedent('''\
    # Generated manually — fix snack1/snack2 unique_together bug
    from django.db import migrations, models


    class Migration(migrations.Migration):

        dependencies = [
            ("menu", "0004_alter_menuitem_unique_together_menuitem_is_salad_and_more"),
        ]

        operations = [
            # Сначала сбрасываем старый unique_together
            migrations.AlterUniqueTogether(
                name="menuitem",
                unique_together=set(),
            ),
            # Добавляем поле meal_slot
            migrations.AddField(
                model_name="menuitem",
                name="meal_slot",
                field=models.CharField(default="", max_length=20),
            ),
            # Новый unique_together включает meal_slot вместо meal_type
            migrations.AlterUniqueTogether(
                name="menuitem",
                unique_together={("menu", "member", "day_offset", "meal_slot", "is_salad")},
            ),
        ]
''')

write(migration_path, migration_content)

print("\n✅ Готово. Следующие шаги на сервере:")
print("   docker compose exec backend python manage.py migrate")
print("   docker compose down && docker compose up -d")
