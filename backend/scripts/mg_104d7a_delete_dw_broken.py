"""
MG-104d-7a — удаление рецептов с битым dish_weight_g_calc.

Критерии (одновременно):
  - density = kcal * servings_normalized / dw_calc > 9 ккал/г
  - dw_calc < 50 г (нереалистично малая порция)

Это однозначно нечинибельные рецепты: либо dw_calc битый (доли грамма),
либо kcal битый при заведомо малой порции. Пересчёт через ингредиенты
тут не поможет — цена починки несоразмерна.

Рецепты с dw_calc >= 50 — отдельная задача (MG-104d-7b), там пересчитываем
КБЖУ через ингредиенты, не удаляем огулом.

DRY-RUN по умолчанию.
Реальное удаление: переменная окружения MG104D7A_APPLY=1.

Запуск (dry-run):
  docker compose -f /opt/menugen/docker-compose.yml exec -T backend bash -c \
    'python manage.py shell < /app/scripts/mg_104d7a_delete_dw_broken.py'

Запуск (apply):
  docker compose -f /opt/menugen/docker-compose.yml exec -T -e MG104D7A_APPLY=1 backend bash -c \
    'python manage.py shell < /app/scripts/mg_104d7a_delete_dw_broken.py'

Идемпотентен.

Каскад:
  - MenuItem.recipe = CASCADE -> чистится автоматически
  - DiaryEntry.recipe = SET_NULL -> recipe станет NULL
"""
import os
from django.db import transaction

from apps.recipes.models import Recipe

DENSITY_THRESHOLD = 9.0   # ккал/г, физический предел (~жир)
DW_THRESHOLD = 50.0       # г, минимальная правдоподобная порция
APPLY = os.environ.get("MG104D7A_APPLY") == "1"


def find_candidates():
    cands = []
    for r in Recipe.objects.filter(kcal__gt=0).only(
        "id", "title", "kcal", "servings", "servings_normalized", "povar_raw"
    ):
        sn = r.servings_normalized or r.servings or 1
        dw = (r.povar_raw or {}).get("dish_weight_g_calc") or 0
        if not dw or dw <= 0:
            continue
        if dw >= DW_THRESHOLD:
            continue
        density = float(r.kcal) * float(sn) / float(dw)
        if density > DENSITY_THRESHOLD:
            cands.append((r.id, r.title, r.kcal, sn, dw, round(density, 2)))
    return cands


cands = find_candidates()

print(f"[mg-104d-7a delete] APPLY={APPLY}")
print(f"[mg-104d-7a delete] критерии: density>{DENSITY_THRESHOLD} И dw_calc<{DW_THRESHOLD}")
print(f"[mg-104d-7a delete] кандидатов: {len(cands)}")

if not cands:
    print("[mg-104d-7a delete] нечего удалять. Выход.")
else:
    for rid, title, kcal, sn, dw, dens in sorted(cands, key=lambda x: -x[5]):
        print(f"  id={rid:>5} dens={dens:>9.1f} kcal={kcal:>6} sn={sn} dw={dw} {(title or '')[:70]}")

    ids = [c[0] for c in cands]

    if not APPLY:
        print()
        print("[mg-104d-7a delete] DRY-RUN. Для реального удаления: MG104D7A_APPLY=1")
    else:
        print()
        print("[mg-104d-7a delete] УДАЛЯЮ...")
        with transaction.atomic():
            qs = Recipe.objects.filter(id__in=ids)
            res = qs.delete()
        print(f"[mg-104d-7a delete] УДАЛЕНО: total={res[0]}")
        for model_label, n in res[1].items():
            print(f"  {model_label}: {n}")

# финальная сводка
print()
print(f"[mg-104d-7a delete] после: total recipes={Recipe.objects.count()}")
remaining = find_candidates()
print(f"[mg-104d-7a delete] кандидатов (dw<{DW_THRESHOLD} И density>{DENSITY_THRESHOLD}) still: {len(remaining)}")
