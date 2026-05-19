from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fridge", "0002_product_image_url"),
    ]

    operations = [
        # 1) Create the new table first.
        migrations.CreateModel(
            name="ProductCategory",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=64, unique=True)),
                ("name_ru", models.CharField(max_length=128)),
                ("name_en", models.CharField(blank=True, max_length=128)),
                ("icon", models.CharField(blank=True, help_text="Emoji or short symbol", max_length=16)),
                ("color", models.CharField(blank=True, help_text="Hex color, e.g. #FFE082", max_length=16)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "product_categories",
                "ordering": ["sort_order", "name_ru"],
            },
        ),
        migrations.AddIndex(
            model_name="productcategory",
            index=models.Index(fields=["slug"], name="product_cat_slug_801f9e_idx"),
        ),

        # 2) Add new fields to Product BEFORE creating their indexes.
        migrations.AddField(
            model_name="product",
            name="is_seed",
            field=models.BooleanField(
                default=False,
                help_text="True for built-in basic products",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="category_fk",
            field=models.ForeignKey(
                blank=True,
                db_column="category_id",
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="products",
                to="fridge.productcategory",
            ),
        ),

        # 3) Now add indexes on the fields just created.
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["category_fk"], name="products_categor_4083ff_idx"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["is_seed"], name="products_is_seed_00ffd9_idx"),
        ),
    ]
