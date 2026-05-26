# DIARY_COPY_V3
from django.db import migrations, models


def backfill_is_planned(apps, schema_editor):
    DiaryEntry = apps.get_model("diary", "DiaryEntry")
    DiaryEntry.objects.filter(planned_menu_item__isnull=False).update(is_planned=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0005_planned_menu_item_o2o"),
    ]

    operations = [
        migrations.AddField(
            model_name="diaryentry",
            name="is_planned",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(backfill_is_planned, noop_reverse),
    ]
