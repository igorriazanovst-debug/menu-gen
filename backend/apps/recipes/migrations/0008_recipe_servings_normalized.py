from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0007_alter_recipe_kcal"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipe",
            name="servings_normalized",
            field=models.PositiveSmallIntegerField(
                null=True,
                blank=True,
                help_text="Нормализованное число порций (MG-104d-5). Считается из dish_weight_g/kcal.",
            ),
        ),
    ]
