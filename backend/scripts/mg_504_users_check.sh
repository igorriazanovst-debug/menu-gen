#!/usr/bin/env bash
# MG-504 финальная проверка users/serializers.py + полный список изменений
set -eu

ROOT="/opt/menugen"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

echo "=== users/serializers.py: контекст ProfileSerializer ==="
grep -n "class ProfileSerializer\|MG501_FIELDS\|MG504_FIELDS\|fields = " \
  "$ROOT/backend/apps/users/serializers.py" | head -20
echo

echo "=== Полный ProfileSerializer (контекст 100-145) ==="
sed -n '100,145p' "$ROOT/backend/apps/users/serializers.py" | cat -n
echo

echo "=== Python syntax check ==="
$COMPOSE exec -T backend python -c \
  "import ast; ast.parse(open('apps/users/serializers.py').read()); print('  users/serializers OK')"
$COMPOSE exec -T backend python -c \
  "import ast; ast.parse(open('apps/users/models.py').read()); print('  users/models OK')"
$COMPOSE exec -T backend python -c \
  "import ast; ast.parse(open('apps/family/serializers.py').read()); print('  family/serializers OK')"
echo

echo "=== Импорт-тест (есть ли circular issues) ==="
$COMPOSE exec -T backend python -c \
  "from apps.users.serializers import ProfileSerializer; print('  users.ProfileSerializer:', ProfileSerializer.Meta.fields)"
$COMPOSE exec -T backend python -c \
  "from apps.family.serializers import ProfileSerializer; print('  family.ProfileSerializer fields:', list(ProfileSerializer().fields.keys()))"

echo
echo "=== DONE ==="
