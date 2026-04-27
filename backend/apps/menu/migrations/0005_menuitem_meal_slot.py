from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0004_alter_menuitem_unique_together_menuitem_is_salad_and_more"),
    ]

    operations = [
        # 1. Сбрасываем старый unique_together
        migrations.AlterUniqueTogether(
            name="menuitem",
            unique_together=set(),
        ),
        # 2. Добавляем колонку
        migrations.AddField(
            model_name="menuitem",
            name="meal_slot",
            field=models.CharField(default="", max_length=20),
        ),
        # 3. Заполняем данные
        migrations.RunSQL(
            sql="UPDATE menu_items SET meal_slot = meal_type WHERE meal_slot = ''",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 4. Новый unique_together
        migrations.AlterUniqueTogether(
            name="menuitem",
            unique_together={("menu", "member", "day_offset", "meal_slot", "is_salad")},
        ),
    ]
