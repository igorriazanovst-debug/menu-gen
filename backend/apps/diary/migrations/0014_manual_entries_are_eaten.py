"""MG_EATFLAG: у записи, добавленной руками, галочка «съедено» становится настоящей.

Как было. Факт за день считался по правилу «отмечено ИЛИ запись не плановая»:
всё, что человек добавил руками, считалось съеденным независимо от галочки.
Поэтому в интерфейсе у таких записей стояла не галочка, а неподвижный знак ✓ —
переключать было нечего, значение всё равно не менялось.

Со стороны это выглядит поломкой: в одном приёме три одинаковые строки, и снять
галочку можно только с одной (плановой, из меню). Ровно об этом и пришёл вопрос.

Что делаем. Правило факта становится одним для всех: съедено — то, что
отмечено. Чтобы итоги за прошлые дни от этого не поехали, ручным записям,
которые правилом и так считались фактом, проставляется `is_eaten = true`.

Обратная миграция не нужна и не пишется: она стёрла бы отметки, поставленные
людьми после выката, а отличить их от проставленных здесь будет уже нельзя.
"""

from django.db import migrations


def mark_manual_as_eaten(apps, schema_editor):
    DiaryEntry = apps.get_model("diary", "DiaryEntry")
    # Ручная запись = без связи с меню и без явной пометки «план». Именно такие
    # старое правило считало фактом всегда.
    qs = DiaryEntry.objects.filter(is_eaten=False, is_planned=False, planned_menu_item__isnull=True)
    total = DiaryEntry.objects.count()
    changed = qs.update(is_eaten=True)
    print(f"\n  MG_EATFLAG: записей всего {total}, отмечено съеденными {changed}")


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0013_added_by_and_body_measurements"),
    ]

    operations = [
        migrations.RunPython(mark_manual_as_eaten, migrations.RunPython.noop),
    ]
