#!/bin/bash
# Фикс тестов MG-605.C: учитываем DRF pagination (results)
# Расположение: /opt/menugen/backend/scripts/fix_605c_tests_pagination.sh

set -eu
PROJECT_DIR="${PROJECT_DIR:-/opt/menugen}"
BACKEND_DIR="$PROJECT_DIR/backend"

TESTS="$BACKEND_DIR/apps/diary/tests/test_mg_605c_permissions.py"

python3 <<'PYEOF'
import re
from pathlib import Path

path = Path("/opt/menugen/backend/apps/diary/tests/test_mg_605c_permissions.py")
src = path.read_text()

# 1) Добавляем helper _list() сразу после _auth()
helper = '''

def _list(resp):
    """MG-605.C: учёт DRF pagination — достаём results если есть."""
    data = resp.json()
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data
'''

if "_list(resp)" not in src:
    src = src.replace(
        'def _auth(client, user):\n    client.force_authenticate(user=user)\n    return client\n',
        'def _auth(client, user):\n    client.force_authenticate(user=user)\n    return client\n' + helper,
    )

# 2) Заменяем все resp.json() в list-views на _list(resp)
replacements = [
    ('names = [e["custom_name"] for e in resp.json()]',
     'names = [e["custom_name"] for e in _list(resp)]'),
]
for old, new in replacements:
    src = src.replace(old, new)

path.write_text(src)
print("OK: тесты обновлены")
PYEOF

echo ""
echo "=== Проверка: что получилось ==="
grep -n "_list(resp)\|def _list" "$TESTS"

echo ""
echo "=== Чистка тест-БД ==="
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T db \
    psql -U menugen_user -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='test_menugen' AND pid <> pg_backend_pid();" || true
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T db \
    psql -U menugen_user -d postgres -c "DROP DATABASE IF EXISTS test_menugen;" || true

echo ""
echo "=== Прогон тестов 605.C ==="
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T backend \
    pytest apps/diary/tests/test_mg_605c_permissions.py -v --tb=short

echo ""
echo "=== Полный регресс diary ==="
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T backend \
    pytest apps/diary/ -v --tb=short
