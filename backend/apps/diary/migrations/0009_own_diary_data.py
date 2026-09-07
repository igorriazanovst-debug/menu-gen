"""MG_OWNDIARY: проставить владельца дневника, воды и веса.

Владелец берётся из членства, которому запись принадлежала раньше: `member` →
`member.user`. На этом шаге ничего не теряется — членство остаётся на месте,
просто рядом появляется человек.

Отдельная забота — задвоенные дни. У воды и веса на день полагается одна запись,
и раньше уникальность считалась по членству: человек, состоящий в двух семьях,
мог иметь две записи на одну дату — по одной за каждым столом. После переноса
уникальность становится «человек + дата», и такие пары надо свести к одной, иначе
0010 не встанет. Правило выбора выписано явно, чтобы результат не зависел от
порядка строк:

* вода — остаётся запись с наибольшим объёмом (при равенстве — с меньшим id);
  складывать нельзя, это один и тот же выпитый день, записанный дважды;
* вес — остаётся самый поздний замер по времени создания (при равенстве — с
  большим id): это последнее, что человек про себя знал.

Что удалено — печатается в вывод миграции: на проде такие строки надо увидеть,
а не узнать о них по разнице в отчётах. Замер перед выкаткой (chat-84) показал,
что задвоенных дней нет ни одного, так что печать ожидается пустой.

Шаг необратим в части удалённых дублей: обратная миграция только снимает
владельца, вернуть удалённые строки неоткуда. Поэтому и печать.
"""

from django.db import migrations


def _fill_owner(apps, table, verbose_name, stdout):
    """user_id ← member.user_id одним запросом."""
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {table} AS t
               SET user_id = fm.user_id
              FROM family_members AS fm
             WHERE t.member_id = fm.id
               AND t.user_id IS NULL
            """
        )
        filled = cur.rowcount
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id IS NULL")
        orphans = cur.fetchone()[0]
    stdout(f"  {verbose_name}: владелец проставлен у {filled} строк, без владельца осталось {orphans}")
    return orphans


def _dedupe(apps, model, keep_order, verbose_name, stdout):
    """Свести (user, date) к одной строке. keep_order — чем сортируем «лучшую»."""
    from django.db.models import Count

    dupes = (
        model.objects.exclude(user_id=None)
        .values("user_id", "date")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .order_by("user_id", "date")
    )
    removed = 0
    for row in dupes:
        rows = list(model.objects.filter(user_id=row["user_id"], date=row["date"]).order_by(*keep_order))
        keep, drop = rows[0], rows[1:]
        stdout(f"  {verbose_name}: user {row['user_id']}, {row['date']} — оставлена строка {keep.id}")
        for obj in drop:
            stdout(f"      удалена строка {obj.id} (членство {obj.member_id})")
            obj.delete()
            removed += 1
    if removed == 0:
        stdout(f"  {verbose_name}: задвоенных дней нет")
    return removed


def forwards(apps, schema_editor):
    def stdout(line):
        print(line)

    print("[MG_OWNDIARY] переношу дневник, воду и вес на человека")

    orphans = 0
    orphans += _fill_owner(apps, "diary_entries", "дневник", stdout)
    orphans += _fill_owner(apps, "water_logs", "вода", stdout)
    orphans += _fill_owner(apps, "weight_logs", "вес", stdout)

    WaterLog = apps.get_model("diary", "WaterLog")
    WeightLog = apps.get_model("diary", "WeightLog")
    # Вода: больший объём важнее; при равенстве берём запись постарше.
    _dedupe(apps, WaterLog, ("-water_ml", "id"), "вода", stdout)
    # Вес: последнее известное значение; при равенстве времени — запись помоложе.
    _dedupe(apps, WeightLog, ("-created_at", "-id"), "вес", stdout)

    if orphans:
        # Строк без членства до этой миграции быть не могло: поле было
        # обязательным. Если такие есть — база не та, что мы чиним, и следующая
        # миграция всё равно упадёт на NOT NULL. Падаем здесь, с понятным текстом.
        raise RuntimeError(
            f"[MG_OWNDIARY] {orphans} строк остались без владельца — у них нет членства. "
            "Разберитесь с ними до 0010: она делает поле обязательным."
        )


def backwards(apps, schema_editor):
    """Снять владельца. Удалённые дубли не возвращаются — см. шапку файла."""
    for model_name in ("DiaryEntry", "WaterLog", "WeightLog"):
        apps.get_model("diary", model_name).objects.update(user=None)


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0008_own_diary_schema"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
