"""
MG-104d-7 — диагностика рецептов с физически невозможной плотностью kcal.

Критерий: density = kcal * servings_normalized / dw_calc > 9 ккал/г.
(чистый жир ~9 ккал/г — жёсткая верхняя граница)

Запуск:
  docker compose -f /opt/menugen/docker-compose.yml exec -T backend bash -c \
    'python manage.py shell < /app/scripts/mg_104d7_diag_density.py'

Вывод: /tmp/menugen/mg104d7_density_<timestamp>.tsv
"""
import csv
import os
from datetime import datetime

from apps.recipes.models import Recipe

THRESHOLD = 9.0  # ккал/г, строгий порог
OUT_DIR = "/tmp/menugen"
os.makedirs(OUT_DIR, exist_ok=True)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
out_path = os.path.join(OUT_DIR, f"mg104d7_density_{ts}.tsv")

candidates = []
total_checked = 0
skipped_no_dw = 0

# ограничиваем выборку рецептами с kcal > 0 и большим kcal — там основные кандидаты
qs = Recipe.objects.filter(kcal__gt=0).order_by("-kcal")

for r in qs:
    total_checked += 1
    sn = r.servings_normalized or r.servings or 1
    dw = (r.povar_raw or {}).get("dish_weight_g_calc") or 0
    if not dw or dw <= 0:
        skipped_no_dw += 1
        continue
    density = float(r.kcal) * float(sn) / float(dw)
    if density > THRESHOLD:
        candidates.append({
            "id": r.id,
            "title": (r.title or "")[:80],
            "kcal": r.kcal,
            "servings": r.servings,
            "servings_normalized": sn,
            "dw_calc": dw,
            "density": round(density, 2),
        })

with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["id", "title", "kcal", "servings", "servings_normalized", "dw_calc", "density_kcal_per_g"])
    for c in candidates:
        w.writerow([c["id"], c["title"], c["kcal"], c["servings"], c["servings_normalized"], c["dw_calc"], c["density"]])

print(f"[mg-104d-7 diag] threshold={THRESHOLD} ккал/г")
print(f"[mg-104d-7 diag] всего проверено: {total_checked}")
print(f"[mg-104d-7 diag] пропущено (нет dw_calc): {skipped_no_dw}")
print(f"[mg-104d-7 diag] кандидатов на удаление: {len(candidates)}")
print(f"[mg-104d-7 diag] отчёт: {out_path}")
print()
print("ID-список кандидатов:")
print(sorted([c["id"] for c in candidates]))
print()
print("Топ кандидатов по плотности:")
for c in sorted(candidates, key=lambda x: -x["density"])[:20]:
    print(f"  id={c['id']:>5} dens={c['density']:>7.1f} kcal={c['kcal']:>6} sn={c['servings_normalized']} dw={c['dw_calc']} {c['title']}")
