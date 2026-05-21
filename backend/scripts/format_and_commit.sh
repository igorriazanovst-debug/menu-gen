#!/usr/bin/env bash
# Run black 24.3.0 + isort 5.13.2 (line-length 120, like CI) on the 5 feature
# files, then commit. Uses a throwaway venv so the host stays clean.
set -euo pipefail
cd /opt/menugen

FILES=(
  backend/apps/common/ai_provider.py
  backend/apps/common/vision.py
  backend/apps/fridge/serializers.py
  backend/apps/fridge/views.py
  backend/config/settings.py
)

echo "===== setup tooling (venv) ====="
VENV="/tmp/fmt_venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" -q install --upgrade pip
"$VENV/bin/pip" -q install black==24.3.0 isort==5.13.2

echo
echo "===== black + isort (line-length 120) ====="
"$VENV/bin/black" --line-length 120 "${FILES[@]}"
"$VENV/bin/isort" --profile black --line-length 120 "${FILES[@]}"

echo
echo "===== black --check (must be clean) ====="
"$VENV/bin/black" --check --line-length 120 "${FILES[@]}"
echo "  black: clean"

echo
echo "===== django check ====="
docker compose -f /opt/menugen/docker-compose.yml exec -T backend python manage.py check

echo
echo "===== stage + commit ====="
git add "${FILES[@]}"
git status --short --untracked-files=no
git commit -m "style(fridge): apply black/isort (line-length 120) to vision feature files"
git push origin main
