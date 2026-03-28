#!/usr/bin/env python
"""
Скрипт миграции данных из recipes.db (SQLite) в PostgreSQL.

Использование:
    python scripts/migrate_recipes_db.py --db /path/to/recipes.db [--batch 500] [--dry-run]

Переменные окружения (или .env):
    DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
"""

import argparse
import json
import logging
import os
import sqlite3
import sys

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Django setup ──────────────────────────────────────────────────────────────

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.recipes.models import Recipe  # noqa: E402 (after django.setup)

# ── helpers ───────────────────────────────────────────────────────────────────


def _parse_json(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


def _normalize_nutrition(raw: dict) -> dict:
    """Приводит nutrition к единому виду {calories, proteins, fats, carbs}."""
    if not raw:
        return {}
    result = {}
    for key in ("calories", "proteins", "fats", "carbs"):
        entry = raw.get(key)
        if isinstance(entry, dict):
            result[key] = {
                "value": str(entry.get("value", "")),
                "unit": str(entry.get("unit", "")),
            }
    return result


def _row_to_recipe(row: sqlite3.Row) -> dict:
    return {
        "legacy_id": row["id"],
        "title": (row["title"] or row["name"] or "").strip(),
        "cook_time": row["cook_time"] or "",
        "servings": row["servings"] if row["servings"] else None,
        "ingredients": _parse_json(row["ingredients"], []),
        "steps": _parse_json(row["steps"], []),
        "nutrition": _normalize_nutrition(_parse_json(row["nutrition"], {})),
        "categories": _parse_json(row["categories"], []),
        "image_url": row["image_url"] or None,
        "source_url": row["url"] or None,
        "is_custom": False,
        "is_published": True,
    }


# ── main ──────────────────────────────────────────────────────────────────────


def migrate(db_path: str, batch_size: int, dry_run: bool):
    if not os.path.exists(db_path):
        log.error("Файл не найден: %s", db_path)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM recipes WHERE level='details' AND title IS NOT NULL").fetchall()
    conn.close()

    log.info("Найдено записей в SQLite: %d", len(rows))

    if dry_run:
        log.info("[dry-run] Миграция не выполняется.")
        sample = rows[:3]
        for r in sample:
            log.info("  sample: %s", _row_to_recipe(r)["title"])
        return

    # Загружаем уже существующие legacy_id чтобы не дублировать
    existing = set(Recipe.objects.filter(legacy_id__isnull=False).values_list("legacy_id", flat=True))
    log.info("Уже в PostgreSQL: %d", len(existing))

    to_insert = [r for r in rows if r["id"] not in existing]
    log.info("Новых для вставки: %d", len(to_insert))

    created = 0
    errors = 0
    for i in range(0, len(to_insert), batch_size):
        batch = to_insert[i : i + batch_size]
        objects = []
        for row in batch:
            try:
                objects.append(Recipe(**_row_to_recipe(row)))
            except Exception as exc:
                log.warning("Пропуск %s: %s", row["id"], exc)
                errors += 1

        try:
            Recipe.objects.bulk_create(objects, ignore_conflicts=True)
            created += len(objects)
            log.info("Вставлено: %d / %d", created, len(to_insert))
        except Exception as exc:
            log.error("Ошибка batch insert: %s", exc)
            errors += len(objects)

    log.info("Готово. Создано: %d, ошибок: %d", created, errors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate recipes.db to PostgreSQL")
    parser.add_argument("--db", required=True, help="Путь к recipes.db")
    parser.add_argument("--batch", type=int, default=500, help="Размер батча (default: 500)")
    parser.add_argument("--dry-run", action="store_true", help="Только проверка, без записи в БД")
    args = parser.parse_args()

    migrate(db_path=args.db, batch_size=args.batch, dry_run=args.dry_run)
