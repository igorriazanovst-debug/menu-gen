# MG_RA002_cuisine_admin
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0012_rb001_recipe_schema"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cuisine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="Название")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
            ],
            options={
                "verbose_name": "Кухня / страна",
                "verbose_name_plural": "Кухни / страны",
                "db_table": "recipe_cuisines",
                "ordering": ["sort_order", "name"],
            },
        ),
    ]
