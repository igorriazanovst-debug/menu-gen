# MG_ALLERGEN14: поле аллергенов рецепта (ключи ТР ТС 022/2011).
# Идемпотентно: на некоторых окружениях колонка уже существует (добавлена вне
# миграций), поэтому на уровне БД используем ADD COLUMN IF NOT EXISTS, а на
# уровне состояния Django — обычный AddField.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0016_recipe_plate_component"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="recipe",
                    name="allergens",
                    field=models.JSONField(blank=True, default=list),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE recipes ADD COLUMN IF NOT EXISTS allergens jsonb NOT NULL DEFAULT '[]'::jsonb;",
                    reverse_sql="ALTER TABLE recipes DROP COLUMN IF EXISTS allergens;",
                ),
            ],
        ),
    ]
