#!/usr/bin/env python3
"""
add_changelog.py — append an entry to CHANGELOG.md (Keep a Changelog style).

Idempotent: skips if an entry with the same marker already exists in [Unreleased].
Called by patch scripts after a successful apply.

Usage:
    python3 add_changelog.py \
        --repo /opt/menugen \
        --type Added \
        --marker MG_SHOP001_shopping_list \
        --summary "Shopping list model + API" \
        --files backend/apps/shopping/models.py backend/apps/shopping/views.py

--type: one of Added / Changed / Fixed / Removed / Deprecated / Security
"""
import argparse
import datetime as _dt
import os
import sys

ANCHOR = "<!-- CHANGELOG_AUTO_ANCHOR"
VALID_TYPES = ("Added", "Changed", "Fixed", "Removed", "Deprecated", "Security")


def build_line(entry_type, marker, summary, files):
    today = _dt.date.today().isoformat()
    files_part = ""
    if files:
        files_part = " — files: " + ", ".join(f"`{f}`" for f in files)
    return f"- **{entry_type}** {today} `{marker}` — {summary}{files_part}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, help="Repo root containing CHANGELOG.md")
    p.add_argument("--type", required=True, choices=VALID_TYPES)
    p.add_argument("--marker", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--files", nargs="*", default=[])
    args = p.parse_args()

    path = os.path.join(args.repo, "CHANGELOG.md")
    if not os.path.exists(path):
        sys.exit(f"ERROR: CHANGELOG.md not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if args.marker in content:
        print(f"SKIP: marker {args.marker} already present in CHANGELOG.md")
        return

    if ANCHOR not in content:
        sys.exit(f"ERROR: anchor '{ANCHOR}' not found in CHANGELOG.md")

    line = build_line(args.type, args.marker, args.summary, args.files)
    new_content = content.replace(ANCHOR, line + "\n\n" + ANCHOR, 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"ADDED: {line}")


if __name__ == "__main__":
    main()
