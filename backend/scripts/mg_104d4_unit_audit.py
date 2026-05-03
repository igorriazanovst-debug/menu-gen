# -*- coding: utf-8 -*-
"""
MG-104d-4: аудит unit_canon в Recipe.povar_raw.ingredients_norm.

Запуск (в контейнере):
    docker compose exec backend python manage.py shell -c \
      "exec(open('/app/scripts/mg_104d4_unit_audit.py').read())"

На выходе:
    /tmp/menugen/mg104d4_units_global.tsv     — unit_canon, употреблений, имён
    /tmp/menugen/mg104d4_units_per_canon.tsv  — name_canon, unit_canon, count (топ для шт→г)
    /tmp/menugen/mg104d4_pieces_top.tsv       — name_canon с unit_canon в pcs-семействе, отсортировано
"""
import json
import os
from collections import Counter, defaultdict
from django.apps import apps

OUT_DIR = "/tmp/menugen"
os.makedirs(OUT_DIR, exist_ok=True)

Recipe = apps.get_model("recipes", "Recipe")

# Семейство «штучных» единиц — для них критична таблица перевода в граммы
PIECE_UNITS = {
    "шт", "штука", "штук",
    "зубчик", "зубчика",
    "пучок", "пучка",
    "веточка", "веточек",
    "ломтик", "ломтика",
    "долька", "дольки",
    "головка", "головки",
    "стебель", "стебля",
    "лист", "листа", "листьев",
    "пакет", "пакета", "пакетик", "пакетика",
    "банка", "банки",
    "бутылка", "бутылки",
    "упаковка", "упаковки",
    "кочан", "кочана",
    "початок", "початка",
    "стручок", "стручка",
    "щепотка",
    "горсть", "горсти",
}

units_global = Counter()                              # unit_canon -> употреблений
units_canon = defaultdict(Counter)                    # unit_canon -> Counter(name_canon)
canon_units = defaultdict(Counter)                    # name_canon -> Counter(unit_canon)
total_recipes = 0
total_rows = 0

qs = Recipe.objects.exclude(povar_raw__isnull=True).only("id", "povar_raw").iterator()
for r in qs:
    raw = r.povar_raw or {}
    norm = raw.get("ingredients_norm") or []
    total_recipes += 1
    for it in norm:
        if not isinstance(it, dict):
            continue
        if it.get("skip") or it.get("composite"):
            continue
        u = (it.get("unit_canon") or "").strip().lower()
        n = (it.get("name_canon") or "").strip().lower()
        if not n:
            continue
        units_global[u] += 1
        units_canon[u][n] += 1
        canon_units[n][u] += 1
        total_rows += 1

# 1. units_global.tsv
with open(f"{OUT_DIR}/mg104d4_units_global.tsv", "w", encoding="utf-8") as f:
    f.write("unit_canon\tusages\tunique_canon\n")
    for u, cnt in units_global.most_common():
        f.write(f"{u or '∅'}\t{cnt}\t{len(units_canon[u])}\n")

# 2. units_per_canon.tsv (полная разбивка)
with open(f"{OUT_DIR}/mg104d4_units_per_canon.tsv", "w", encoding="utf-8") as f:
    f.write("name_canon\tunit_canon\tcount\n")
    rows = []
    for n, ucnt in canon_units.items():
        for u, c in ucnt.items():
            rows.append((n, u or "∅", c))
    rows.sort(key=lambda x: (-x[2], x[0]))
    for n, u, c in rows:
        f.write(f"{n}\t{u}\t{c}\n")

# 3. pieces_top.tsv — для ручной таблицы шт→г
piece_rows = []  # (name_canon, unit_canon, count)
for u in PIECE_UNITS:
    for n, c in units_canon.get(u, {}).items():
        piece_rows.append((n, u, c))
piece_rows.sort(key=lambda x: -x[2])

with open(f"{OUT_DIR}/mg104d4_pieces_top.tsv", "w", encoding="utf-8") as f:
    f.write("name_canon\tunit_canon\tcount\n")
    for n, u, c in piece_rows:
        f.write(f"{n}\t{u}\t{c}\n")

# Краткий отчёт в stdout
print(f"[mg-104d4 audit] recipes scanned: {total_recipes}")
print(f"[mg-104d4 audit] non-skip rows  : {total_rows}")
print(f"[mg-104d4 audit] distinct units : {len(units_global)}")
print()
print("TOP-25 unit_canon by usages:")
for u, cnt in units_global.most_common(25):
    print(f"  {u or '∅':<15} {cnt:>7}  ({len(units_canon[u])} canon)")
print()
print(f"TOP-30 piece-units (требуется шт→г):")
for n, u, c in piece_rows[:30]:
    print(f"  {c:>5}  {n:<35} [{u}]")
print()
print("Files:")
for fn in ("mg104d4_units_global.tsv", "mg104d4_units_per_canon.tsv", "mg104d4_pieces_top.tsv"):
    p = f"{OUT_DIR}/{fn}"
    if os.path.exists(p):
        print(f"  {p}  ({os.path.getsize(p):,} bytes)")
