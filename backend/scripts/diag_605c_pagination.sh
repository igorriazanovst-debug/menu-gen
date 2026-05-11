#!/bin/bash
# Диагностика формата JSON-ответа /api/v1/diary/ — есть ли пагинация
# Расположение: /opt/menugen/backend/scripts/diag_605c_pagination.sh

set -u
PROJECT_DIR="${PROJECT_DIR:-/opt/menugen}"

echo "=== 1) DEFAULT_PAGINATION_CLASS в settings ==="
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T backend bash -lc "
grep -rnE 'DEFAULT_PAGINATION_CLASS|PAGE_SIZE|pagination_class' config/ apps/diary/ --include='*.py' | head -30
"

echo ""
echo "=== 2) Запуск REPL-теста: смотрим, что отдаёт /diary/ ==="
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T backend python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.conf import settings
print('REST_FRAMEWORK:', settings.REST_FRAMEWORK)
"
