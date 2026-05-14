#!/usr/bin/env bash
# Backend Lint hybrid fix:
#   1) backend/scripts/ → exclude из flake8/black/isort (CI + .flake8)
#   2) black + isort авто-фикс на apps/ + config/
#   3) показывает оставшиеся ручные flake8-нарушения (без правки)
#
# Запуск:
#   bash /opt/menugen/backend/scripts/fix_lint_hybrid.sh

set -uo pipefail
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
cd "$ROOT"

hr() { printf '\n========== %s ==========\n' "$1"; }

# ─── 1. .flake8 — добавить scripts в exclude ────────────────────────────────
hr "1. .flake8"
FLAKE8_CFG="${BACKEND}/.flake8"
cat "$FLAKE8_CFG"
echo "---"

python3 - "$FLAKE8_CFG" <<'PY'
import sys, re
from pathlib import Path
p = Path(sys.argv[1])
src = p.read_text(encoding="utf-8")
# Найти/обновить строку exclude. Если её нет — добавить после max-line-length.
if re.search(r"^exclude\s*=", src, re.M):
    def repl(m):
        line = m.group(0)
        if "scripts" in line:
            return line
        return line.rstrip() + ",scripts\n"
    src = re.sub(r"^exclude\s*=.*\n", repl, src, count=1, flags=re.M)
else:
    src = src.rstrip() + "\nexclude = migrations,scripts\n"
p.write_text(src, encoding="utf-8")
print("after:\n" + p.read_text(encoding="utf-8"))
PY

# ─── 2. ci.yml — добавить scripts в --exclude / --skip ──────────────────────
hr "2. .github/workflows/ci.yml"
CI="${ROOT}/.github/workflows/ci.yml"
python3 - "$CI" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
src = p.read_text(encoding="utf-8")
changes = [
    ("flake8 . --max-line-length=120 --exclude=migrations",
     "flake8 . --max-line-length=120 --exclude=migrations,scripts"),
    ("black --check . --exclude=migrations",
     "black --check . --exclude='/(migrations|scripts)/'"),
    ("isort --check-only . --skip=migrations",
     "isort --check-only . --skip=migrations --skip=scripts"),
]
for old, new in changes:
    if old in src:
        src = src.replace(old, new)
        print(f"  patched: {old!r} -> {new!r}")
    elif new in src:
        print(f"  already: {new!r}")
    else:
        print(f"  NOT FOUND: {old!r}")
p.write_text(src, encoding="utf-8")
PY

# ─── 3. black + isort авто-фикс на apps/ + config/ ──────────────────────────
hr "3. black + isort на apps/ + config/"
docker compose exec -T backend isort apps config --skip=migrations
echo "---"
docker compose exec -T backend black apps config --exclude='/migrations/'

# ─── 4. Финальные проверки ─────────────────────────────────────────────────
hr "4a. flake8 на apps/ + config/ — оставшиеся ручные нарушения"
docker compose exec -T backend \
  flake8 apps config --max-line-length=120 --exclude=migrations 2>&1 | tee /tmp/lint_remaining.log
echo
echo "remaining count: $(wc -l < /tmp/lint_remaining.log)"

hr "4b. black --check"
docker compose exec -T backend black --check apps config --exclude='/migrations/' 2>&1 | tail -5

hr "4c. isort --check"
docker compose exec -T backend isort --check-only apps config --skip=migrations 2>&1 | tail -5

hr "5. flake8 на корне с обновлённым exclude (как делает CI)"
docker compose exec -T backend \
  flake8 . --max-line-length=120 --exclude=migrations,scripts 2>&1 | tail -20

echo
echo "DONE. Если в 4a/5 ещё есть нарушения — это ручные (F401/F841/E501/etc)."
echo "Diff:"
git -C "$ROOT" diff --stat | tail -20
