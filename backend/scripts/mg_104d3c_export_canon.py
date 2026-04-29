"""
MG-104d-3c export: уникальные name_canon из Recipe.povar_raw.ingredients_norm
Запуск в контейнере:
  docker compose exec backend python manage.py shell -c \
    "exec(open('/app/scripts/mg_104d3c_export_canon.py').read())"
Выход: /tmp/menugen/mg104d3c_canon.txt (по одному name_canon на строку)
"""
import json
import os
from collections import Counter

from django.apps import apps  # noqa: E402

Recipe = apps.get_model("recipes", "Recipe")

OUT_DIR = "/tmp/menugen"
OUT_FILE = os.path.join(OUT_DIR, "mg104d3c_canon.txt")
STATS_FILE = os.path.join(OUT_DIR, "mg104d3c_canon_stats.tsv")

os.makedirs(OUT_DIR, exist_ok=True)

counter: Counter = Counter()
total_recipes = 0
total_items = 0
skipped_skip = 0
skipped_composite = 0
skipped_no_canon = 0

qs = Recipe.objects.exclude(povar_raw__isnull=True).only("id", "povar_raw").iterator()
for r in qs:
    total_recipes += 1
    raw = r.povar_raw or {}
    items = raw.get("ingredients_norm") or []
    for it in items:
        total_items += 1
        if it.get("skip"):
            skipped_skip += 1
            continue
        if it.get("composite"):
            skipped_composite += 1
            continue
        nc = (it.get("name_canon") or "").strip().lower()
        if not nc:
            skipped_no_canon += 1
            continue
        counter[nc] += 1

with open(OUT_FILE, "w", encoding="utf-8") as f:
    for name in sorted(counter.keys()):
        f.write(name + "\n")

with open(STATS_FILE, "w", encoding="utf-8") as f:
    f.write("name_canon\tcount\n")
    for name, n in counter.most_common():
        f.write(f"{name}\t{n}\n")

print(json.dumps({
    "recipes_processed": total_recipes,
    "items_total": total_items,
    "skipped_skip": skipped_skip,
    "skipped_composite": skipped_composite,
    "skipped_no_canon": skipped_no_canon,
    "unique_name_canon": len(counter),
    "out_file": OUT_FILE,
    "stats_file": STATS_FILE,
}, ensure_ascii=False, indent=2))
