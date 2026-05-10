#!/usr/bin/env bash
# MG-301 diagnose: текущая структура apps/menu, MenuItem, MenuGenerator,
# наличие FoodGroup/suitable_for/protein_type/grain_type из MG-101/104.
# Идемпотентно. Только чтение.
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/opt/menugen}"
COMPOSE="${PROJECT_ROOT}/docker-compose.yml"
APPS="${PROJECT_ROOT}/backend/apps"
MENU_APP="${APPS}/menu"
RECIPES_APP="${APPS}/recipes"

echo "=== MG-301 DIAGNOSE === $(date -Is)"
echo

echo "[1/8] Дерево apps/menu:"
if [[ -d "${MENU_APP}" ]]; then
    find "${MENU_APP}" -maxdepth 3 -type f \
        \( -name "*.py" -o -name "*.txt" -o -name "*.md" \) \
        | sort
else
    echo "  ❌ Каталог ${MENU_APP} не найден"
fi
echo

echo "[2/8] models.py — выжимка по MenuItem / Menu:"
if [[ -f "${MENU_APP}/models.py" ]]; then
    grep -nE "^\s*(class |[a-z_]+\s*=\s*models\.)" "${MENU_APP}/models.py" \
        | sed -n '1,200p'
    echo "  ---"
    echo "  marker MG_301_V_models: $(grep -c 'MG_301_V_models' "${MENU_APP}/models.py" || true)"
    echo "  poле component_role найдено: $(grep -c 'component_role' "${MENU_APP}/models.py" || true)"
else
    echo "  ❌ ${MENU_APP}/models.py не найден"
fi
echo

echo "[3/8] generator.py — заголовок и структура:"
GEN_FILE=""
for cand in "${MENU_APP}/generator.py" "${MENU_APP}/services/generator.py" "${MENU_APP}/services.py"; do
    if [[ -f "${cand}" ]]; then GEN_FILE="${cand}"; break; fi
done
if [[ -n "${GEN_FILE}" ]]; then
    echo "  Файл: ${GEN_FILE}"
    echo "  Строк: $(wc -l < "${GEN_FILE}")"
    echo "  ---"
    grep -nE "^\s*(class |def )" "${GEN_FILE}" | head -60
    echo "  ---"
    echo "  marker MG_301_V_generator: $(grep -c 'MG_301_V_generator' "${GEN_FILE}" || true)"
else
    echo "  ⚠️  generator.py не найден ни в одном из ожидаемых мест"
fi
echo

echo "[4/8] Recipe — наличие полей MG-101/104:"
if [[ -f "${RECIPES_APP}/models.py" ]]; then
    for f in food_group suitable_for protein_type grain_type is_fatty_fish is_red_meat; do
        c=$(grep -c "^\s*${f}\s*=" "${RECIPES_APP}/models.py" || true)
        echo "  ${f}: ${c}"
    done
else
    echo "  ❌ ${RECIPES_APP}/models.py не найден"
fi
echo

echo "[5/8] Миграции apps/menu:"
if [[ -d "${MENU_APP}/migrations" ]]; then
    ls -1 "${MENU_APP}/migrations" | grep -E '^[0-9]{4}_' | sort | tail -10
else
    echo "  ❌ ${MENU_APP}/migrations не найден"
fi
echo

echo "[6/8] Тесты apps/menu (что сейчас есть):"
find "${MENU_APP}" -type f -name "test_*.py" -o -name "tests.py" 2>/dev/null | sort
echo

echo "[7/8] Состояние БД (через docker compose):"
if [[ -f "${COMPOSE}" ]] && command -v docker &>/dev/null; then
    docker compose -f "${COMPOSE}" exec -T backend python manage.py showmigrations menu 2>&1 | tail -20 || true
    echo "  ---"
    docker compose -f "${COMPOSE}" exec -T backend python -c "
from apps.menu.models import MenuItem
fields = [f.name for f in MenuItem._meta.get_fields()]
print('MenuItem fields:', fields)
print('has component_role:', 'component_role' in fields)
" 2>&1 | tail -10 || true
else
    echo "  ⚠️  docker compose недоступен или ${COMPOSE} не найден — пропуск"
fi
echo

echo "[8/8] Версии маркеров MG-301 (поиск по backend):"
grep -rE "MG_301_V_[a-z_]+" "${PROJECT_ROOT}/backend" 2>/dev/null \
    | awk -F: '{print $1}' | sort -u || echo "  (маркеров MG-301 нет — задача не начата)"

echo
echo "=== MG-301 DIAGNOSE DONE ==="
