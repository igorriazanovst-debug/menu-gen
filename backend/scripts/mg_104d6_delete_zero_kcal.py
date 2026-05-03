"""
MG-104d-6: удаление рецептов с kcal<=0 (7 шт).

Причина: ингредиенты этих рецептов либо все skip:true (декоративные блюда),
либо без quantity, либо с битым name_canon (скобки в имени) — починить
невозможно без ручного восстановления исходников povar.ru.

Связи:
  MenuItem.recipe  on_delete=CASCADE   → MenuItem удалится автоматически
  DiaryEntry.recipe on_delete=SET_NULL → DiaryEntry останется с recipe=NULL

Запуск:
  # dry-run (по умолчанию)
  docker compose -f /opt/menugen/docker-compose.yml exec -T backend bash -c \
    'python manage.py shell < /app/scripts/mg_104d6_delete_zero_kcal.py'

  # реальное удаление
  docker compose -f /opt/menugen/docker-compose.yml exec -T -e MG104D6_APPLY=1 backend bash -c \
    'python manage.py shell < /app/scripts/mg_104d6_delete_zero_kcal.py'

Идемпотентность: повторный запуск ничего не сломает — выберутся уже 0 рецептов.
"""
import os
from django.apps import apps
from django.db import transaction

APPLY = os.environ.get("MG104D6_APPLY", "").lower() in ("1", "true", "yes")

Recipe = apps.get_model("recipes", "Recipe")

qs = Recipe.objects.filter(kcal__lte=0).order_by("id")
ids = list(qs.values_list("id", flat=True))

print(f"[mg-104d-6 delete] APPLY={APPLY}")
print(f"[mg-104d-6 delete] рецептов с kcal<=0: {len(ids)}")
print(f"[mg-104d-6 delete] ids: {ids}")

if not ids:
    print("[mg-104d-6 delete] нечего удалять — выход")
else:
    print("\n--- список к удалению ---")
    for r in qs.only("id", "title", "servings", "kcal"):
        print(f"  id={r.id:>5}  s={r.servings}  kcal={r.kcal}  title={r.title!r}")

    # связанные объекты (для отчёта до удаления)
    print("\n--- связанные объекты ---")
    for model in apps.get_models():
        for f in model._meta.get_fields():
            if (getattr(f, "related_model", None) is Recipe
                    and f.is_relation and not f.auto_created):
                cnt = model.objects.filter(**{f.name + "__in": ids}).count()
                if cnt:
                    od = f.remote_field.on_delete.__name__
                    print(f"  {model._meta.app_label}.{model.__name__}.{f.name}  "
                          f"on_delete={od}  rows={cnt}")

    if APPLY:
        with transaction.atomic():
            deleted, per_model = qs.delete()
        print(f"\n[mg-104d-6 delete] УДАЛЕНО: total={deleted}")
        for m, n in per_model.items():
            print(f"  {m}: {n}")
    else:
        print("\n[mg-104d-6 delete] DRY-RUN: ничего не удалено. "
              "Для реального удаления — MG104D6_APPLY=1")

# контрольная проверка
remaining = Recipe.objects.filter(kcal__lte=0).count()
total = Recipe.objects.count()
print(f"\n[mg-104d-6 delete] после: total recipes={total}, kcal<=0 still={remaining}")
