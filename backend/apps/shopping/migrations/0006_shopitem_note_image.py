# MG_SHOPNOTE / MG_SHOPIMG: комментарий + изображение товара.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shopping", "0005_shoppinglistaccess_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="shoppinglistitem",
            name="note",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="shoppinglistitem",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="shopping_items/"),
        ),
        migrations.AddField(
            model_name="shoppinglistitem",
            name="image_url",
            field=models.URLField(blank=True, default="", max_length=1024),
        ),
    ]
