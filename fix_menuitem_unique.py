#!/usr/bin/env python3
"""
Патч MenuItem:
1. Добавляет поле is_salad = BooleanField(default=False)
2. Меняет unique_together чтобы включал is_salad
3. Создаёт и применяет миграцию
"""
import pathlib, subprocess, sys

ROOT = pathlib.Path("/opt/menugen/backend")
MODELS = ROOT / "apps/menu/models.py"

src = MODELS.read_text(encoding="utf-8")

# Добавить поле is_salad после поля quantity
OLD_FIELD = '    quantity = models.DecimalField(max_digits=6, decimal_places=2, default=1)\n'
NEW_FIELD = '    quantity = models.DecimalField(max_digits=6, decimal_places=2, default=1)\n    is_salad = models.BooleanField(default=False)\n'

if "is_salad" not in src:
    src = src.replace(OLD_FIELD, NEW_FIELD)
    print("✓ добавлено поле is_salad")
else:
    print("  skip is_salad (уже есть)")

# Поменять unique_together
OLD_UNIQUE = '        unique_together = [("menu", "member", "day_offset", "meal_type")]'
NEW_UNIQUE = '        unique_together = [("menu", "member", "day_offset", "meal_type", "is_salad")]'

if OLD_UNIQUE in src:
    src = src.replace(OLD_UNIQUE, NEW_UNIQUE)
    print("✓ обновлён unique_together")
elif NEW_UNIQUE in src:
    print("  skip unique_together (уже обновлён)")
else:
    print("⚠ не найден unique_together — проверь вручную")

MODELS.write_text(src, encoding="utf-8")

# Создать миграцию и применить
print("\nСоздаю миграцию...")
r = subprocess.run(
    ["docker", "compose", "exec", "backend", "python", "manage.py", "makemigrations", "menu"],
    cwd="/opt/menugen", capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    print(r.stderr)
    sys.exit(1)

print("Применяю миграцию...")
r = subprocess.run(
    ["docker", "compose", "exec", "backend", "python", "manage.py", "migrate"],
    cwd="/opt/menugen", capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    print(r.stderr)
    sys.exit(1)

print("\n✓ Готово")
