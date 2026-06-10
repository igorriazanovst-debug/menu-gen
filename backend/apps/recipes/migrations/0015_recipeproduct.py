# MG_RECIPELINK — RecipeProduct through-table (recipe <-> rubricator product).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0014_recipe_import_session"),
        ("fridge", "0007_product_last_price_product_last_price_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecipeProduct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name_raw", models.CharField(max_length=255)),
                ("name_canonical", models.CharField(blank=True, max_length=255)),
                ("category_slug", models.CharField(blank=True, max_length=64)),
                ("quantity", models.CharField(blank=True, max_length=64)),
                ("unit", models.CharField(blank=True, max_length=50)),
                ("grams", models.FloatField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="product_links",
                        to="recipes.recipe",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recipe_links",
                        to="fridge.product",
                    ),
                ),
                (
                    "category_fk",
                    models.ForeignKey(
                        blank=True,
                        db_column="category_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recipe_links",
                        to="fridge.productcategory",
                    ),
                ),
            ],
            options={
                "db_table": "recipe_products",
            },
        ),
        migrations.AddIndex(
            model_name="recipeproduct",
            index=models.Index(fields=["recipe"], name="recipe_prod_recipe_idx"),
        ),
        migrations.AddIndex(
            model_name="recipeproduct",
            index=models.Index(fields=["product"], name="recipe_prod_product_idx"),
        ),
        migrations.AddIndex(
            model_name="recipeproduct",
            index=models.Index(fields=["category_slug"], name="recipe_prod_catslug_idx"),
        ),
    ]
