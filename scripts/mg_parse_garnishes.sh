#!/usr/bin/env bash
# Запуск парсера гарниров с russianfood.com
# Использование:
#   bash mg_parse_garnishes.sh            # dry-run (показать без сохранения)
#   bash mg_parse_garnishes.sh --apply    # реально сохранить в БД
#   bash mg_parse_garnishes.sh --apply --limit 20  # первые 20

set -euo pipefail

COMPOSE_FILE="/opt/menugen/docker-compose.yml"
CMD="python manage.py parse_russianfood_garnishes"

# передаём все аргументы скрипта в management-команду
EXTRA="${*}"

echo "=== mg_parse_garnishes ==="
echo "Аргументы: ${EXTRA:-<нет, режим dry-run>}"
echo ""

docker compose -f "$COMPOSE_FILE" exec -T backend \
    $CMD $EXTRA 2>&1

echo ""
echo "=== Готово ==="
