#!/usr/bin/env bash
# MG-202 fix-signals: восстановить корректный signals.py
# (откат signals.py из бэкапа + аккуратное отключение вызова fill_profile_targets).
# nutrition.py и models.py — НЕ трогаем (там всё ок).

set -euo pipefail

ROOT=/opt/menugen
SIGNALS="$ROOT/backend/apps/users/signals.py"
BAK_DIR="$ROOT/backups"

# Найти последний бэкап signals.py от MG-202
BAK=$(ls -t "$BAK_DIR"/signals.py.bak_mg202_* 2>/dev/null | head -1 || true)
if [ -z "$BAK" ]; then
  echo "ERROR: backup signals.py.bak_mg202_* not found in $BAK_DIR"
  exit 1
fi

echo "=========================================="
echo "MG-202 fix-signals"
echo "  backup found: $BAK"
echo "=========================================="

# 1) восстановить из бэкапа
cp "$BAK" "$SIGNALS"
echo "[1] restored from backup"

# 2) аккуратно закомментировать строку fill_profile_targets(instance, ...)
python3 <<PYEOF
from pathlib import Path
p = Path("$SIGNALS")
src = p.read_text(encoding="utf-8")
out_lines = []
patched = False
for line in src.splitlines(keepends=True):
    stripped = line.lstrip()
    if stripped.startswith("fill_profile_targets("):
        indent = line[: len(line) - len(stripped)]
        out_lines.append(f"{indent}# MG-202: handled in Profile.save() now\n")
        out_lines.append(f"{indent}# {stripped}")
        patched = True
    else:
        out_lines.append(line)
p.write_text("".join(out_lines), encoding="utf-8")
print("  patched:", patched)
PYEOF

echo
echo "--- [signals.py after fix] ---"
cat -n "$SIGNALS"

# 3) sanity: попробовать импортировать в Django
echo
echo "--- [3] django import check ---"
docker compose -f "$ROOT/docker-compose.yml" exec -T backend bash -c \
  'python -c "import django; django.setup()" 2>&1 || python manage.py check' \
  || true

# 4) recalc pid=1 force=True
echo
echo "--- [4] recalc pid=1 (force=True) ---"
docker compose -f "$ROOT/docker-compose.yml" exec -T backend bash -c 'python manage.py shell' <<'PYEOF'
from apps.users.models import Profile
from apps.users.nutrition import fill_profile_targets, MG_202_V

print('MG_202_V =', MG_202_V)
p = Profile.objects.get(pk=1)
print('BEFORE:', dict(
    cal=p.calorie_target, P=p.protein_target_g, F=p.fat_target_g,
    C=p.carb_target_g, Fb=p.fiber_target_g))

changed = fill_profile_targets(p, force=True)
p.save()
p.refresh_from_db()

print('AFTER :', dict(
    cal=p.calorie_target, P=p.protein_target_g, F=p.fat_target_g,
    C=p.carb_target_g, Fb=p.fiber_target_g))
print('changed=', changed)
PYEOF

echo
echo "DONE."
