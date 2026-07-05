# MG_ALLERGEN14: поле аллергенов рецепта (ключи ТР ТС 022/2011).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0016_recipe_plate_component"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipe",
            name="allergens",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
