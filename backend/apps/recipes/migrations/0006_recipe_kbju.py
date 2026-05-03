from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0005_mg_104c_add_povar_raw"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipe",
            name="kcal",
            field=models.DecimalField(
                max_digits=7, decimal_places=1, null=True, blank=True,
                help_text="Калорийность на 1 порцию, ккал (расчёт MG-104d-4).",
            ),
        ),
        migrations.AddField(
            model_name="recipe",
            name="proteins",
            field=models.DecimalField(
                max_digits=6, decimal_places=1, null=True, blank=True,
                help_text="Белки на 1 порцию, г.",
            ),
        ),
        migrations.AddField(
            model_name="recipe",
            name="fats",
            field=models.DecimalField(
                max_digits=6, decimal_places=1, null=True, blank=True,
                help_text="Жиры на 1 порцию, г.",
            ),
        ),
        migrations.AddField(
            model_name="recipe",
            name="carbs",
            field=models.DecimalField(
                max_digits=6, decimal_places=1, null=True, blank=True,
                help_text="Углеводы на 1 порцию, г.",
            ),
        ),
    ]
