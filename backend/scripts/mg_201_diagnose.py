# MG-201 diagnose: показать текущую структуру модели Profile
# Запуск:
#   docker compose -f /opt/menugen/docker-compose.yml exec -T backend bash -c \
#     'python manage.py shell < /app/scripts/mg_201_diagnose.py'

from django.apps import apps
from django.db import connection

print("=" * 70)
print("MG-201 DIAGNOSE: Profile model")
print("=" * 70)

# 1. Найти модель Profile (может быть в разных приложениях)
candidates = []
for model in apps.get_models():
    if model.__name__ == "Profile":
        candidates.append(model)

if not candidates:
    print("\n[!] Модель Profile НЕ найдена среди установленных приложений")
    print("    Все модели:")
    for m in sorted(apps.get_models(), key=lambda x: (x._meta.app_label, x.__name__)):
        print(f"      {m._meta.app_label}.{m.__name__}")
else:
    for Profile in candidates:
        meta = Profile._meta
        print(f"\n>>> {meta.app_label}.{Profile.__name__}")
        print(f"    db_table: {meta.db_table}")
        print(f"    модуль:   {Profile.__module__}")

        print(f"\n    Поля модели ({len(meta.get_fields())}):")
        for f in meta.get_fields():
            ftype = type(f).__name__
            extra = []
            if getattr(f, "null", False):
                extra.append("null=True")
            if getattr(f, "blank", False):
                extra.append("blank=True")
            if getattr(f, "choices", None):
                extra.append(f"choices={len(f.choices)}")
            default = getattr(f, "default", None)
            if default is not None and default.__class__.__name__ != "NOT_PROVIDED":
                if callable(default):
                    extra.append(f"default={default.__name__}")
                else:
                    extra.append(f"default={default!r}")
            max_len = getattr(f, "max_length", None)
            if max_len:
                extra.append(f"max_length={max_len}")
            extras = " ".join(extra)
            print(f"      - {f.name:30s} {ftype:30s} {extras}")

        # 2. Колонки в БД
        print(f"\n    Колонки в БД ({meta.db_table}):")
        with connection.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                [meta.db_table],
            )
            rows = cur.fetchall()
        for col, dtype, nullable, default in rows:
            print(f"      {col:30s} {dtype:25s} null={nullable:3s} default={default}")

        # 3. Количество записей
        cnt = Profile.objects.count()
        print(f"\n    Записей в таблице: {cnt}")

        # 4. Примеры значений активности и пола (если есть)
        for fname in ("activity_level", "gender", "goal", "goals"):
            if any(f.name == fname for f in meta.get_fields()):
                print(f"\n    Распределение {fname}:")
                from django.db.models import Count
                qs = (
                    Profile.objects.values(fname)
                    .annotate(n=Count("id"))
                    .order_by("-n")[:20]
                )
                for row in qs:
                    print(f"      {row[fname]!r:40s}  n={row['n']}")

        # 5. Проверить, есть ли уже целевые поля (идемпотентность задачи MG-201)
        target_fields = (
            "protein_target_g",
            "fat_target_g",
            "carb_target_g",
            "meal_plan_type",
        )
        existing = {f.name for f in meta.get_fields()}
        print(f"\n    Целевые поля MG-201:")
        for tf in target_fields:
            mark = "[уже есть]" if tf in existing else "[нужно добавить]"
            print(f"      {tf:25s} {mark}")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
