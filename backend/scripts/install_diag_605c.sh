#!/bin/bash
# Копирует diag_605c.sh из корня проекта в backend/scripts/
# Запуск из /opt/menugen:
#   bash install_diag_605c.sh

set -eu
PROJECT_DIR="${PROJECT_DIR:-/opt/menugen}"
TARGET_DIR="$PROJECT_DIR/backend/scripts"

mkdir -p "$TARGET_DIR"
cp -v "$PROJECT_DIR/diag_605c.sh" "$TARGET_DIR/diag_605c.sh"
chmod +x "$TARGET_DIR/diag_605c.sh"

echo "OK: установлен $TARGET_DIR/diag_605c.sh"
echo "Запуск:"
echo "  bash $TARGET_DIR/diag_605c.sh 2>&1 | tee /tmp/diag_605c.log"
