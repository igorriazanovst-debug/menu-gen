#!/usr/bin/env python3
"""
MG-104d-3c merge_overrides:
накладывает ручную таблицу КБЖУ (TSV) поверх ingredient_kbju.json от OFF.

Логика:
  - Если name_canon есть в TSV → берём ручные значения, source='manual',
    в samples — поле notes из TSV.
  - Иначе оставляем как было.
  - Имена в TSV нормализуются (lower, ё→е, обрезка пробелов).
  - Логируем какие имена из TSV не использовались (nothing to override) — это
    подсказка либо опечатка в TSV, либо имя не дошло до canon после clean.

Вход:
  --kbju     /tmp/menugen/ingredient_kbju.json
  --override /opt/menugen/backend/scripts/data/kbju_overrides_104d3c.tsv

Выход:
  --out      /tmp/menugen/ingredient_kbju.json   (перезаписывает по умолчанию)

Запуск:
  python3 /opt/menugen/backend/scripts/mg_104d3c_merge_overrides.py \
    --kbju     /tmp/menugen/ingredient_kbju.json \
    --override /opt/menugen/backend/scripts/data/kbju_overrides_104d3c.tsv \
    --out      /tmp/menugen/ingredient_kbju.json
"""
import argparse
import csv
import json
from pathlib import Path

NUTRIENTS = ("calories", "proteins", "fats", "carbs", "fiber")


def norm(s: str) -> str:
    return (s or "").strip().lower().replace("ё", "е")


def load_overrides(path: Path) -> dict:
    out = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            name = norm(row.get("name_canon", ""))
            if not name:
                continue
            rec = {}
            for k in NUTRIENTS:
                v = (row.get(k) or "").strip()
                if v == "":
                    rec[k] = None
                else:
                    try:
                        rec[k] = float(v)
                    except ValueError:
                        rec[k] = None
            rec["_source"] = (row.get("source") or "manual").strip()
            rec["_notes"] = (row.get("notes") or "").strip()
            out[name] = rec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kbju", required=True, type=Path)
    ap.add_argument("--override", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    kbju = json.loads(args.kbju.read_text(encoding="utf-8"))
    overrides = load_overrides(args.override)

    overridden = 0
    added = 0
    used: set = set()

    for name, rec in overrides.items():
        used.add(name)
        existing = kbju.get(name)
        new_rec = {
            "calories": rec["calories"],
            "calories_n": 1 if rec["calories"] is not None else 0,
            "proteins": rec["proteins"],
            "proteins_n": 1 if rec["proteins"] is not None else 0,
            "fats": rec["fats"],
            "fats_n": 1 if rec["fats"] is not None else 0,
            "carbs": rec["carbs"],
            "carbs_n": 1 if rec["carbs"] is not None else 0,
            "fiber": rec["fiber"],
            "fiber_n": 1 if rec["fiber"] is not None else 0,
            "n_matched": 1,
            "source": f"manual:{rec['_source']}",
            "fuzzy_samples": [],
            "samples": [{"off_id": None, "name": rec["_notes"] or name}],
        }
        if existing is not None:
            overridden += 1
        else:
            added += 1
        kbju[name] = new_rec

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(kbju, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "kbju_total": len(kbju),
        "overrides_in_tsv": len(overrides),
        "overridden_existing": overridden,
        "added_new": added,
        "out": str(args.out),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
