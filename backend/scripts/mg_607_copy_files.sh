#!/bin/bash
# /opt/menugen/backend/scripts/mg_607_copy_files.sh
# Копирует скачанные файлы по структуре проекта.
# Кладёт:
#   - mg_607_apply_backend.sh → /opt/menugen/backend/scripts/
#   - test_mg_607_filters.py  → /opt/menugen/backend/apps/menu/tests/
# Источник (где лежат скачанные файлы) — задаётся как аргумент или /root/Downloads
set -euo pipefail

SRC="${1:-/root/Downloads}"
ROOT=/opt/menugen

if [ ! -d "$SRC" ]; then
  echo "ERROR: source dir not found: $SRC"
  exit 1
fi

echo "Copying from: $SRC"

# 1) patch script
if [ -f "$SRC/mg_607_apply_backend.sh" ]; then
  install -m 755 "$SRC/mg_607_apply_backend.sh" "$ROOT/backend/scripts/mg_607_apply_backend.sh"
  echo "  → $ROOT/backend/scripts/mg_607_apply_backend.sh"
else
  echo "  SKIP: $SRC/mg_607_apply_backend.sh not found"
fi

# 2) tests
if [ -f "$SRC/test_mg_607_filters.py" ]; then
  install -m 644 "$SRC/test_mg_607_filters.py" "$ROOT/backend/apps/menu/tests/test_mg_607_filters.py"
  echo "  → $ROOT/backend/apps/menu/tests/test_mg_607_filters.py"
else
  echo "  SKIP: $SRC/test_mg_607_filters.py not found"
fi

echo "Done."
