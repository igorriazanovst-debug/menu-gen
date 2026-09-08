"""MG_MEALSLOT: у записи дневника появился точный слот приёма.

Старым записям слот проставляется по роду еды: завтрак/обед/ужин — сами собой,
перекус — первым. Какой перекус был на самом деле, не знает никто: до сегодня
это нигде не хранилось. Первый — единственная догадка, которую человек увидит в
дневнике и при желании поправит, а второй перекус начнёт заполняться с этого дня.

Записям, пришедшим из меню, слот берётся из самой позиции меню: там он
хранится с самого начала (`MenuItem.meal_slot`), просто дневник его до сих пор
не забирал. Так что план дня разложится по перекусам правильно, включая уже
заполненные дни.
"""

from django.db import migrations, models


def fill_slots(apps, schema_editor):
    from django.db import connection

    with connection.cursor() as cur:
        # Из меню — точный слот, он там есть.
        cur.execute(
            """
            UPDATE diary_entries AS d
               SET meal_slot = mi.meal_slot
              FROM menu_items AS mi
             WHERE d.planned_menu_item_id = mi.id
               AND d.meal_slot = ''
               AND mi.meal_slot <> ''
            """
        )
        from_menu = cur.rowcount
        # Остальным — по роду еды.
        cur.execute(
            """
            UPDATE diary_entries
               SET meal_slot = CASE meal_type
                                   WHEN 'snack' THEN 'snack1'
                                   ELSE meal_type
                               END
             WHERE meal_slot = ''
            """
        )
        by_type = cur.rowcount
        cur.execute("SELECT COUNT(*) FROM diary_entries WHERE meal_slot = ''")
        left = cur.fetchone()[0]

    print(f"[MG_MEALSLOT] слот из меню: {from_menu}, по роду еды: {by_type}, без слота осталось: {left}")


def clear_slots(apps, schema_editor):
    apps.get_model("diary", "DiaryEntry").objects.update(meal_slot="")


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0010_own_diary_finish"),
    ]

    operations = [
        migrations.AddField(
            model_name="diaryentry",
            name="meal_slot",
            field=models.CharField(
                blank=True,
                choices=[
                    ("breakfast", "Завтрак"),
                    ("lunch", "Обед"),
                    ("dinner", "Ужин"),
                    ("snack1", "Перекус 1"),
                    ("snack2", "Перекус 2"),
                ],
                default="",
                max_length=20,
            ),
        ),
        migrations.RunPython(fill_slots, clear_slots),
    ]
