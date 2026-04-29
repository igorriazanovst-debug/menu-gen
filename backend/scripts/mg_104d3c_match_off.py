#!/usr/bin/env python3
"""
MG-104d-3c: матчер ингредиентов (name_canon) в OpenFoodFacts RU.
Стратегия: exact -> substring -> fuzzy(rapidfuzz token_set_ratio>=85).
Агрегация: медиана. min-products — порог для метки low_n (запись пишем в любом случае).

Формат входного индекса (off_ru_index.json):
  { "norm_name": [ {off_id, name, calories, proteins, fats, carbs, fiber}, ... ] }

Запуск на хосте:
  python3 /opt/menugen/backend/scripts/mg_104d3c_match_off.py \
    --canon /tmp/menugen/mg104d3c_canon.txt \
    --off-dir /opt/menugen/data/off_dump \
    --out /tmp/menugen/ingredient_kbju.json \
    --unmatched /tmp/menugen/mg104d3c_unmatched.tsv
"""
import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

try:
    from rapidfuzz import process, fuzz
except ImportError:
    sys.stderr.write("ERROR: pip install rapidfuzz\n")
    sys.exit(1)


NUTRIENTS = ("calories", "proteins", "fats", "carbs", "fiber")

WS_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^\w\s\-]", re.UNICODE)


def norm(s: str) -> str:
    if not s:
        return ""
    s = s.lower().strip().replace("ё", "е")
    s = PUNCT_RE.sub(" ", s)
    s = WS_RE.sub(" ", s).strip()
    return s


def get_value(prod: dict, kind: str):
    v = prod.get(kind)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f < 0 or f > 10000:
        return None
    return f


def aggregate(products: list) -> dict:
    out: dict = {}
    for kind in NUTRIENTS:
        vals = [get_value(p, kind) for p in products]
        vals = [v for v in vals if v is not None]
        out[kind] = round(statistics.median(vals), 2) if vals else None
        out[f"{kind}_n"] = len(vals)
    return out


def load_index(off_dir: Path) -> dict:
    p = off_dir / "off_ru_index.json"
    if not p.exists():
        sys.exit(f"ERROR: missing {p}")
    t0 = time.time()
    with p.open("r", encoding="utf-8") as f:
        idx = json.load(f)
    n_prod = sum(len(v) for v in idx.values())
    sys.stderr.write(f"[off] {len(idx)} keys / {n_prod} products in {time.time()-t0:.1f}s\n")
    return idx


def match_substring(name_n: str, idx: dict, max_keys: int = 50) -> list:
    if len(name_n) < 3:
        return []
    out: list = []
    seen = set()
    hit_keys = 0
    for key, prods in idx.items():
        if name_n in key or key in name_n:
            hit_keys += 1
            for p in prods:
                k = p.get("off_id")
                if k in seen:
                    continue
                seen.add(k)
                out.append(p)
            if hit_keys >= max_keys:
                break
    return out


def match_fuzzy(name_n: str, idx_keys: list, idx: dict,
                threshold: int, top_k: int = 5):
    matches = process.extract(name_n, idx_keys, scorer=fuzz.token_set_ratio,
                              limit=top_k, score_cutoff=threshold)
    out: list = []
    seen = set()
    samples = []
    for key, score, _ in matches:
        samples.append({"key": key, "score": int(score)})
        for p in idx[key]:
            k = p.get("off_id")
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
    return out, samples


def product_sample(p: dict) -> dict:
    return {"off_id": p.get("off_id"), "name": p.get("name")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canon", required=True, type=Path)
    ap.add_argument("--off-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--unmatched", required=True, type=Path)
    ap.add_argument("--fuzzy-threshold", type=int, default=85)
    ap.add_argument("--min-products", type=int, default=3)
    ap.add_argument("--samples", type=int, default=5)
    args = ap.parse_args()

    canon_list = [ln.strip() for ln in args.canon.read_text(encoding="utf-8").splitlines() if ln.strip()]
    sys.stderr.write(f"[in] {len(canon_list)} unique name_canon\n")

    idx = load_index(args.off_dir)
    idx_keys = list(idx.keys())

    out_data: dict = {}
    unmatched_rows: list = []
    stats = {"exact": 0, "substring": 0, "fuzzy": 0, "low_n": 0, "unmatched": 0}

    t0 = time.time()
    for i, name in enumerate(canon_list, 1):
        if i % 200 == 0:
            sys.stderr.write(f"[..] {i}/{len(canon_list)} ({time.time()-t0:.0f}s)\n")
        name_n = norm(name)

        source = None
        prods: list = []
        fuzzy_samples: list = []

        if name_n in idx:
            prods = list(idx[name_n])
            source = "exact"
        else:
            prods = match_substring(name_n, idx)
            if prods:
                source = "substring"
            else:
                prods, fuzzy_samples = match_fuzzy(name_n, idx_keys, idx, args.fuzzy_threshold)
                if prods:
                    source = "fuzzy"

        if not prods:
            stats["unmatched"] += 1
            unmatched_rows.append(name)
            continue

        agg = aggregate(prods)
        if (agg.get("calories_n") or 0) < args.min_products:
            stats["low_n"] += 1

        stats[source] += 1
        out_data[name] = {
            **agg,
            "n_matched": len(prods),
            "source": source,
            "fuzzy_samples": fuzzy_samples if source == "fuzzy" else [],
            "samples": [product_sample(p) for p in prods[: args.samples]],
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")

    args.unmatched.parent.mkdir(parents=True, exist_ok=True)
    with args.unmatched.open("w", encoding="utf-8") as f:
        f.write("name_canon\n")
        for name in unmatched_rows:
            f.write(name + "\n")

    sys.stderr.write(json.dumps({
        "total": len(canon_list),
        **stats,
        "out": str(args.out),
        "unmatched_file": str(args.unmatched),
        "elapsed_sec": round(time.time() - t0, 1),
    }, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
