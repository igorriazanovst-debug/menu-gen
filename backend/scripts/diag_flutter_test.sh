#!/usr/bin/env bash
# DIAG: где запускать flutter test
ROOT="${PROJECT_DIR:-/opt/menugen}"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. docker-compose services"
grep -nE "^\s+\w+:|image:|build:" "${ROOT}/docker-compose.yml" 2>/dev/null | head -40
echo "---"
ls "${ROOT}/docker-compose"*.yml 2>/dev/null

hr "2. flutter in PATH anywhere?"
which flutter 2>/dev/null
ls /opt/flutter/bin/flutter /usr/local/flutter/bin/flutter /home/*/flutter/bin/flutter 2>/dev/null
find /opt /usr/local -maxdepth 4 -name "flutter" -type f 2>/dev/null | head -5

hr "3. CI workflow — как там Flutter тесты запускаются"
ls "${ROOT}/.github/workflows/" 2>/dev/null
echo "---"
grep -lE "flutter|dart" "${ROOT}/.github/workflows/"*.yml 2>/dev/null

hr "4. flutter workflow содержимое"
for f in "${ROOT}/.github/workflows/"*.yml; do
  [ -f "$f" ] || continue
  if grep -qE "flutter|mobile" "$f"; then
    echo "--- $f ---"
    cat "$f"
    echo
  fi
done | head -150

hr "5. Dockerfile в mobile/"
ls "${ROOT}/mobile/"Dockerfile* "${ROOT}/mobile/menugen_app/"Dockerfile* 2>/dev/null
echo "---"
find "${ROOT}/mobile" -maxdepth 3 -name "Dockerfile*" 2>/dev/null

echo
echo "=== done ==="
