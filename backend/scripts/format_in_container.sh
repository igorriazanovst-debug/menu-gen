#!/usr/bin/env bash
# Format the 5 feature files with black/isort INSIDE the backend container
# (matches CI), then commit on the host.
set -euo pipefail
ROOT="/opt/menugen"
DC="docker compose -f $ROOT/docker-compose.yml"

# paths inside container (workdir /app == backend/)
CFILES="apps/common/ai_provider.py apps/common/vision.py apps/fridge/serializers.py apps/fridge/views.py config/settings.py"

echo "===== ensure black/isort in container ====="
$DC exec -T backend sh -c '
  python -c "import black" 2>/dev/null && echo "  black present" || pip install -q black==24.3.0
  python -c "import isort" 2>/dev/null && echo "  isort present" || pip install -q isort==5.13.2
'

echo
echo "===== black + isort (line-length 120) inside container ====="
$DC exec -T backend sh -c "python -m black --line-length 120 $CFILES && python -m isort --profile black --line-length 120 $CFILES"

echo
echo "===== black --check (must be clean) ====="
$DC exec -T backend sh -c "python -m black --check --line-length 120 $CFILES" && echo "  black: clean"

echo
echo "===== django check ====="
$DC exec -T backend python manage.py check

echo
echo "===== stage + commit on host ====="
cd "$ROOT"
HFILES="backend/apps/common/ai_provider.py backend/apps/common/vision.py backend/apps/fridge/serializers.py backend/apps/fridge/views.py backend/config/settings.py"
git add $HFILES
git status --short --untracked-files=no
git commit -m "style(fridge): apply black/isort (line-length 120) to vision feature files"
git push origin main
