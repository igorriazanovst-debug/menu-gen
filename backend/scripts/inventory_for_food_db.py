"""
MG-104d-prep: инвентарь данных для построения справочника.
Запуск: docker compose exec backend python scripts/inventory_for_food_db.py
"""
from __future__ import annotations
import os
import sys
import re

# Гарантируем, что /app есть в PYTHONPATH (manage.py-стиль)
APP_DIR = "/app"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from collections import Counter, defaultdict
from apps.recipes.models import Recipe

OUT_DIR = "/tmp/menugen"
os.makedirs(OUT_DIR, exist_ok=True)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


# ── 1. Уникальные ингредиенты + единицы ────────────────────────────────────

ing_counter: Counter[str] = Counter()
ing_units:  defaultdict[str, Counter[str]] = defaultdict(Counter)
unit_counter: Counter[str] = Counter()
unit_examples: defaultdict[str, list[str]] = defaultdict(list)

total_recipes = 0
for r in Recipe.objects.iterator():
    total_recipes += 1
    for ing in (r.ingredients or []):
        if not isinstance(ing, dict):
            continue
        name = _norm(str(ing.get("name", "")))
        unit = _norm(str(ing.get("unit", "")))
        if not name:
            continue
        ing_counter[name] += 1
        ing_units[name][unit] += 1
        unit_counter[unit] += 1
        if len(unit_examples[unit]) < 3 and name not in unit_examples[unit]:
            unit_examples[unit].append(name)

# 1) ингредиенты
path_ing = os.path.join(OUT_DIR, "ingredients_unique.tsv")
with open(path_ing, "w", encoding="utf-8") as f:
    f.write("count\tname\ttop_units\n")
    for name, cnt in ing_counter.most_common():
        units = ", ".join(f"{u or '(empty)'}×{c}" for u, c in ing_units[name].most_common(3))
        f.write(f"{cnt}\t{name}\t{units}\n")
print(f"[ok] {path_ing}: {len(ing_counter)} уникальных ингредиентов")

# 2) единицы
path_units = os.path.join(OUT_DIR, "units_unique.tsv")
with open(path_units, "w", encoding="utf-8") as f:
    f.write("count\tunit\texamples\n")
    for unit, cnt in unit_counter.most_common():
        ex = ", ".join(unit_examples[unit][:3])
        f.write(f"{cnt}\t{unit or '(empty)'}\t{ex}\n")
print(f"[ok] {path_units}: {len(unit_counter)} уникальных единиц")

# 3) рецепты без nutrition
path_nut = os.path.join(OUT_DIR, "recipes_missing_nutrition.tsv")
seen = set()
with open(path_nut, "w", encoding="utf-8") as f:
    f.write("id\ttitle\tsource_url\n")
    qs = list(Recipe.objects.filter(nutrition={}).values_list("id", "title", "source_url")) + \
         list(Recipe.objects.filter(nutrition__isnull=True).values_list("id", "title", "source_url"))
    for rid, title, url in qs:
        if rid in seen:
            continue
        seen.add(rid)
        f.write(f"{rid}\t{title}\t{url or ''}\n")
print(f"[ok] {path_nut}: {len(seen)} рецептов без nutrition")

# 4) рецепты без servings
path_srv = os.path.join(OUT_DIR, "recipes_missing_servings.tsv")
with open(path_srv, "w", encoding="utf-8") as f:
    f.write("id\ttitle\tsource_url\n")
    cnt = 0
    for rid, title, url in Recipe.objects.filter(servings__isnull=True).values_list("id", "title", "source_url"):
        f.write(f"{rid}\t{title}\t{url or ''}\n")
        cnt += 1
print(f"[ok] {path_srv}: {cnt} рецептов без servings")

print()
print(f"Всего рецептов: {total_recipes}")
print(f"Файлы лежат в {OUT_DIR}/")
