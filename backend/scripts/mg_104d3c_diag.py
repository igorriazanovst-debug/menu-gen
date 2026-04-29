#!/usr/bin/env python3
"""
MG-104d-3c diag: TOP unmatched + TOP low_n,
взвешенные по частоте использования name_canon в рецептах.

Вход:
  --stats     /tmp/menugen/mg104d3c_canon_stats.tsv  (name_canon\tcount)
  --unmatched /tmp/menugen/mg104d3c_unmatched.tsv
  --kbju      /tmp/menugen/ingredient_kbju.json

Выход (stdout + файлы):
  /tmp/menugen/mg104d3c_diag_unmatched.tsv
  /tmp/menugen/mg104d3c_diag_lown.tsv

Запуск:
  python3 /opt/menugen/backend/scripts/mg_104d3c_diag.py \
    --stats /tmp/menugen/mg104d3c_canon_stats.tsv \
    --unmatched /tmp/menugen/mg104d3c_unmatched.tsv \
    --kbju /tmp/menugen/ingredient_kbju.json \
    --top 100
"""
import argparse
import json
from pathlib import Path


def load_counts(path: Path) -> dict:
    counts = {}
    with path.open("r", encoding="utf-8") as f:
        next(f, None)  # header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                try:
                    counts[parts[0]] = int(parts[1])
                except ValueError:
                    pass
    return counts


def load_unmatched(path: Path) -> list:
    out = []
    with path.open("r", encoding="utf-8") as f:
        next(f, None)
        for line in f:
            s = line.strip()
            if s:
                out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True, type=Path)
    ap.add_argument("--unmatched", required=True, type=Path)
    ap.add_argument("--kbju", required=True, type=Path)
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--min-products", type=int, default=3)
    ap.add_argument("--out-dir", type=Path, default=Path("/tmp/menugen"))
    args = ap.parse_args()

    counts = load_counts(args.stats)
    unmatched = load_unmatched(args.unmatched)
    kbju = json.loads(args.kbju.read_text(encoding="utf-8"))

    total_uses = sum(counts.values())

    # --- UNMATCHED ---
    un_rows = sorted(
        ((n, counts.get(n, 0)) for n in unmatched),
        key=lambda x: -x[1],
    )
    un_uses = sum(c for _, c in un_rows)
    out_un = args.out_dir / "mg104d3c_diag_unmatched.tsv"
    with out_un.open("w", encoding="utf-8") as f:
        f.write("name_canon\tcount\n")
        for n, c in un_rows:
            f.write(f"{n}\t{c}\n")

    # --- LOW_N (matched, но < min_products продуктов с ккал) ---
    low_rows = []
    for name, rec in kbju.items():
        n_kcal = rec.get("calories_n") or 0
        if n_kcal < args.min_products:
            low_rows.append((name, counts.get(name, 0), rec.get("source"), n_kcal))
    low_rows.sort(key=lambda x: -x[1])
    low_uses = sum(r[1] for r in low_rows)
    out_low = args.out_dir / "mg104d3c_diag_lown.tsv"
    with out_low.open("w", encoding="utf-8") as f:
        f.write("name_canon\tcount\tsource\tcalories_n\n")
        for n, c, src, nk in low_rows:
            f.write(f"{n}\t{c}\t{src}\t{nk}\n")

    # --- print summary ---
    print("=== ИТОГ ===")
    print(f"всего употреблений name_canon в рецептах: {total_uses}")
    print(f"unmatched: {len(un_rows)} имён, {un_uses} употреблений ({un_uses/total_uses*100:.1f}%)")
    print(f"low_n   : {len(low_rows)} имён, {low_uses} употреблений ({low_uses/total_uses*100:.1f}%)")
    print()
    print(f"=== TOP-{args.top} UNMATCHED (по частоте) ===")
    for n, c in un_rows[: args.top]:
        print(f"{c:>5}  {n}")
    print()
    print(f"=== TOP-{args.top} LOW_N (по частоте) ===")
    for n, c, src, nk in low_rows[: args.top]:
        print(f"{c:>5}  [{src:<9} n={nk}]  {n}")
    print()
    print(f"файлы: {out_un}")
    print(f"       {out_low}")


if __name__ == "__main__":
    main()
