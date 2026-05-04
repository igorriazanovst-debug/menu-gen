#!/usr/bin/env bash
# MG-201 STEP 1 — Бэкенд: бэкап + правка models.py + миграция.
#
# Идемпотентность: проверяем, есть ли уже carb_target_g (без s) в models.py.
# Если есть — пропускаем правку.
#
# Откат:
#   1) gunzip -c $BACKUP_DB | docker compose -f /opt/menugen/docker-compose.yml exec -T db \
#        psql -U menugen_user -d menugen
#   2) cp $BACKUP_MODELS /opt/menugen/backend/apps/users/models.py
#   3) удалить созданные миграции (см. вывод этого скрипта)
#
# Запуск: bash /opt/menugen/backend/scripts/mg_201_apply_backend.sh

set -euo pipefail

ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"
MODELS="$ROOT/backend/apps/users/models.py"
MIGR_DIR="$ROOT/backend/apps/users/migrations"
BACKUP_DIR="$ROOT/backups"
TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DB="$BACKUP_DIR/before_mg201_${TS}.sql.gz"
BACKUP_MODELS="$BACKUP_DIR/before_mg201_models_${TS}.py.bak"

mkdir -p "$BACKUP_DIR"

echo "================================================================"
echo "MG-201 STEP 1 — backend rename"
echo "  models.py:        $MODELS"
echo "  backup db -> :    $BACKUP_DB"
echo "  backup models ->: $BACKUP_MODELS"
echo "================================================================"

# 0. Бэкап БД
echo
echo "[0/5] Бэкап БД..."
docker compose -f "$COMPOSE" exec -T db \
  pg_dump -U menugen_user -d menugen --no-owner --no-acl \
  | gzip > "$BACKUP_DB"
echo "      -> $(ls -lh "$BACKUP_DB" | awk '{print $5}')  $BACKUP_DB"

# 0b. Бэкап models.py
cp "$MODELS" "$BACKUP_MODELS"
echo "      -> $BACKUP_MODELS"

# 1. Идемпотентность: уже переименовано?
if grep -qE '^\s*carb_target_g\s*=' "$MODELS" \
   && grep -qE '^\s*meal_plan_type\s*=' "$MODELS" \
   && ! grep -qE '^\s*carbs_target_g\s*=' "$MODELS" \
   && ! grep -qE '^\s*meal_plan\s*=' "$MODELS"; then
  echo
  echo "[1/5] Поля уже переименованы в models.py — пропускаем правку файла."
  ALREADY_RENAMED=1
else
  echo
  echo "[1/5] Правим models.py..."
  ALREADY_RENAMED=0

  # carbs_target_g -> carb_target_g (только в объявлении поля, чтобы не задеть лишнее)
  sed -i 's/^\(\s*\)carbs_target_g\(\s*=\s*models\.\)/\1carb_target_g\2/' "$MODELS"

  # meal_plan -> meal_plan_type (тоже только в объявлении поля)
  sed -i 's/^\(\s*\)meal_plan\(\s*=\s*models\.\)/\1meal_plan_type\2/' "$MODELS"

  # Контроль
  if ! grep -qE '^\s*carb_target_g\s*=\s*models\.' "$MODELS"; then
    echo "      [!] не нашли carb_target_g после правки — откат"
    cp "$BACKUP_MODELS" "$MODELS"
    exit 1
  fi
  if ! grep -qE '^\s*meal_plan_type\s*=\s*models\.' "$MODELS"; then
    echo "      [!] не нашли meal_plan_type после правки — откат"
    cp "$BACKUP_MODELS" "$MODELS"
    exit 1
  fi
  if grep -qE '^\s*carbs_target_g\s*=\s*models\.' "$MODELS"; then
    echo "      [!] carbs_target_g всё ещё объявлен — откат"
    cp "$BACKUP_MODELS" "$MODELS"
    exit 1
  fi
  if grep -qE '^\s*meal_plan\s*=\s*models\.' "$MODELS"; then
    echo "      [!] meal_plan всё ещё объявлен — откат"
    cp "$BACKUP_MODELS" "$MODELS"
    exit 1
  fi
  echo "      OK"
fi

# 2. makemigrations (Django сам распознает RenameField и спросит y/n)
echo
echo "[2/5] makemigrations users (отвечаем 'y' на оба RenameField)..."
# Перечислим миграции ДО
BEFORE=$(ls "$MIGR_DIR" | grep -E '^[0-9]+.*\.py$' | sort)

# `printf 'y\ny\n'` — отвечаем yes/yes на оба RenameField
printf 'y\ny\n' | docker compose -f "$COMPOSE" exec -T backend \
  python manage.py makemigrations users || {
    echo "      [!] makemigrations упал"
    exit 1
}

# 3. Какие миграции добавились
AFTER=$(ls "$MIGR_DIR" | grep -E '^[0-9]+.*\.py$' | sort)
NEW=$(comm -13 <(echo "$BEFORE") <(echo "$AFTER") | sed '/^$/d')

echo
echo "[3/5] Новые миграции:"
if [[ -z "$NEW" ]]; then
  echo "      (нет — Django ничего не сгенерировал. Проверь models.py)"
  if [[ "$ALREADY_RENAMED" -eq 0 ]]; then
    exit 1
  fi
else
  for m in $NEW; do
    echo "      + $m"
  done
fi

# 4. migrate
echo
echo "[4/5] migrate..."
docker compose -f "$COMPOSE" exec -T backend python manage.py migrate users || {
  echo "      [!] migrate упал — откат вручную"
  echo "          gunzip -c $BACKUP_DB | docker compose -f $COMPOSE exec -T db psql -U menugen_user -d menugen"
  echo "          cp $BACKUP_MODELS $MODELS"
  for m in $NEW; do echo "          rm $MIGR_DIR/$m"; done
  exit 1
}

# 5. Sanity-чек — поля в БД
echo
echo "[5/5] Sanity-чек: колонки в profiles..."
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    c.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='profiles' ORDER BY column_name\")
    cols = sorted(r[0] for r in c.fetchall())
must_have = {'carb_target_g', 'meal_plan_type'}
must_not_have = {'carbs_target_g', 'meal_plan'}
present = [c for c in must_have if c in cols]
absent  = [c for c in must_not_have if c in cols]
print('  колонки:', cols)
print('  должны быть:    ', present, ' (ok)' if len(present)==len(must_have) else ' (FAIL)')
print('  должны исчезнуть:', [c for c in must_not_have if c in cols], ' (ok)' if not absent else ' (FAIL)')
from apps.users.models import Profile
print('  записей в profiles:', Profile.objects.count())
for p in Profile.objects.all()[:3]:
    print(f'  pid={p.id} carb_target_g={p.carb_target_g} meal_plan_type={p.meal_plan_type}')
"

echo
echo "================================================================"
echo "MG-201 STEP 1 ГОТОВО."
echo "  Откат БД:    gunzip -c $BACKUP_DB | docker compose -f $COMPOSE exec -T db psql -U menugen_user -d menugen"
echo "  Откат кода:  cp $BACKUP_MODELS $MODELS"
for m in $NEW; do
  echo "               rm $MIGR_DIR/$m"
done
echo "================================================================"
