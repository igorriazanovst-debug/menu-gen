#!/usr/bin/env python3
"""
MG-104d-3c coverage: финальная статистика покрытия КБЖУ.

Считает три категории по употреблениям (по count из mg104d3c_canon_stats.tsv):
  - "manual"        : source начинается с "manual:" (надёжно)
  - "off_strong"    : source in (exact, substring, fuzzy) И calories_n >= min_n
  - "off_weak"      : source in (exact, substring, fuzzy) И calories_n < min_n
  - "no_kbju"       : нет в kbju или calories=null
  - "unmatched"     : из mg104d3c_unmatched.tsv

Запуск:
  python3 /opt/menugen/backend/scripts/mg_104d3c_coverage.py \
    --stats /tmp/menugen/mg104d3c_canon_stats.tsv \
    --kbju  /tmp/menugen/ingredient_kbju.json \
    --unmatched /tmp/menugen/mg104d3c_unmatched.tsv \
    --min-n 3
"""
import argparse
import json
from pathlib import Path


def load_counts(path: Path) -> dict:
    counts = {}
    with path.open("r", encoding="utf-8") as f:
        next(f, None)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                try:
                    counts[parts[0].strip().lower().replace("ё", "е")] = int(parts[1])
                except ValueError:
                    pass
    return counts


def load_unmatched(path: Path) -> set:
    out = set()
    with path.open("r", encoding="utf-8") as f:
        next(f, None)
        for line in f:
            s = line.strip().lower().replace("ё", "е")
            if s:
                out.add(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True, type=Path)
    ap.add_argument("--kbju", required=True, type=Path)
    ap.add_argument("--unmatched", required=True, type=Path)
    ap.add_argument("--min-n", type=int, default=3)
    args = ap.parse_args()

    counts = load_counts(args.stats)
    kbju_raw = json.loads(args.kbju.read_text(encoding="utf-8"))
    kbju = {k.strip().lower().replace("ё", "е"): v for k, v in kbju_raw.items()}
    unmatched = load_unmatched(args.unmatched)

    total_uses = sum(counts.values())
    cat_count = {"manual": 0, "off_strong": 0, "off_weak": 0, "no_kbju": 0, "unmatched": 0}
    cat_uses = {k: 0 for k in cat_count}

    for name, n in counts.items():
        if name in unmatched:
            cat_count["unmatched"] += 1
            cat_uses["unmatched"] += n
            continue
        rec = kbju.get(name)
        if rec is None:
            cat_count["no_kbju"] += 1
            cat_uses["no_kbju"] += n
            continue
        src = rec.get("source") or ""
        kcal = rec.get("calories")
        n_kcal = rec.get("calories_n") or 0
        if src.startswith("manual"):
            cat_count["manual"] += 1
            cat_uses["manual"] += n
        elif kcal is None:
            cat_count["no_kbju"] += 1
            cat_uses["no_kbju"] += n
        elif n_kcal >= args.min_n:
            cat_count["off_strong"] += 1
            cat_uses["off_strong"] += n
        else:
            cat_count["off_weak"] += 1
            cat_uses["off_weak"] += n

    def pct(x, t):
        return f"{x/t*100:.1f}%" if t else "—"

    print(f"=== ПОКРЫТИЕ КБЖУ (по {total_uses} употреблениям, {sum(cat_count.values())} имён) ===")
    print(f"{'category':<14} {'имён':>6} {'упот.':>8} {'%':>7}")
    for k in ("manual", "off_strong", "off_weak", "no_kbju", "unmatched"):
        print(f"{k:<14} {cat_count[k]:>6} {cat_uses[k]:>8} {pct(cat_uses[k], total_uses):>7}")
    print()
    reliable = cat_uses["manual"] + cat_uses["off_strong"]
    print(f"НАДЁЖНОЕ ПОКРЫТИЕ (manual + off_strong): {reliable} употреблений = {pct(reliable, total_uses)}")


if __name__ == "__main__":
    main()
