import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("recipes", "0018_recipe_media_charfield"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecipeMadePhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="recipe_made/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="made_photos",
                        to="recipes.recipe",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recipe_made_photos",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "recipe_made_photos",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="recipemadephoto",
            index=models.Index(fields=["user", "recipe"], name="recipe_made_user_id_e91883_idx"),
        ),
        migrations.AddIndex(
            model_name="recipemadephoto",
            index=models.Index(fields=["recipe"], name="recipe_made_recipe__8ba9ff_idx"),
        ),
    ]
