#!/usr/bin/env python3
"""
MG-104d-3c: применить synonyms_patch_104d3c.yaml к synonyms.yaml.
- делает бэкап исходника (.bak.YYYYMMDDHHMMSS)
- мерджит manual_synonyms (новые алиасы добавляются, дубли убираются)
- предупреждает о коллизиях (один и тот же alias уже привязан к другому canon)
- сохраняет порядок ключей через ruamel.yaml (если установлен), иначе PyYAML

Запуск:
  pip3 install --break-system-packages ruamel.yaml || pip3 install ruamel.yaml
  python3 /opt/menugen/backend/scripts/mg_104d3c_apply_aliases.py \
    --base    /opt/menugen/backend/scripts/data/synonyms.yaml \
    --patch   /opt/menugen/backend/scripts/data/synonyms_patch_104d3c.yaml
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

try:
    from ruamel.yaml import YAML
    HAVE_RUAMEL = True
except ImportError:
    HAVE_RUAMEL = False
    import yaml


def load(path: Path):
    if HAVE_RUAMEL:
        y = YAML()
        y.preserve_quotes = True
        y.width = 4096
        with path.open("r", encoding="utf-8") as f:
            return y.load(f), y
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}, None


def dump(data, path: Path, yobj):
    if HAVE_RUAMEL and yobj is not None:
        with path.open("w", encoding="utf-8") as f:
            yobj.dump(data, f)
    else:
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=4096)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--patch", required=True, type=Path)
    args = ap.parse_args()

    base, ybase = load(args.base)
    patch, _ = load(args.patch)

    if "manual_synonyms" not in base or base["manual_synonyms"] is None:
        base["manual_synonyms"] = {}

    base_manual = base["manual_synonyms"]
    patch_manual = (patch or {}).get("manual_synonyms") or {}

    # обратный индекс по ВСЕМ существующим алиасам
    alias_to_canon: dict = {}
    for canon, aliases in (base_manual or {}).items():
        if not aliases:
            continue
        for a in aliases:
            alias_to_canon[a.strip().lower()] = canon

    added = 0
    moved_canon = 0
    collisions = []
    new_canons = 0

    for canon, aliases in patch_manual.items():
        if canon not in base_manual or base_manual[canon] is None:
            base_manual[canon] = []
            new_canons += 1

        existing = list(base_manual[canon] or [])
        existing_norm = {x.strip().lower() for x in existing}

        for a in aliases or []:
            an = a.strip().lower()
            if an in existing_norm:
                continue
            current_owner = alias_to_canon.get(an)
            if current_owner and current_owner != canon:
                collisions.append((a, current_owner, canon))
                continue
            existing.append(a)
            existing_norm.add(an)
            alias_to_canon[an] = canon
            added += 1

        base_manual[canon] = existing

    # бэкап
    ts = time.strftime("%Y%m%d%H%M%S")
    bak = args.base.with_suffix(args.base.suffix + f".bak.{ts}")
    shutil.copy2(args.base, bak)

    dump(base, args.base, ybase)

    print(f"backend yaml lib: {'ruamel.yaml' if HAVE_RUAMEL else 'PyYAML'}")
    print(f"backup:        {bak}")
    print(f"new canons:    {new_canons}")
    print(f"aliases added: {added}")
    if collisions:
        print(f"COLLISIONS ({len(collisions)}) — пропущены, разруливай вручную:")
        for a, owner, attempted in collisions[:50]:
            print(f"  alias={a!r}: уже у {owner!r}, пропущено для {attempted!r}")
    else:
        print("collisions:    0")


if __name__ == "__main__":
    main()
