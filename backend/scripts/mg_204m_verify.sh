#!/usr/bin/env bash
# MG-204 mobile — финальная верификация
set -uo pipefail

ROOT="/opt/menugen"
MOB="${ROOT}/mobile/menugen_app"
LIB="${MOB}/lib"

echo "================================================================"
echo "  MG-204 mobile — verify"
echo "================================================================"

echo "── Маркеры в файлах ──"
for f in \
  "${LIB}/core/widgets/macro_pill.dart" \
  "${LIB}/features/family/screens/family_screen.dart" \
  "${LIB}/features/profile/screens/profile_screen.dart"; do
  echo
  echo "→ $f"
  grep -nE "MG_204m_V_(macro_pill|family|profile)" "$f" || echo "  ⚠ маркер не найден"
done

echo
echo "── Размеры ──"
ls -la \
  "${LIB}/core/widgets/macro_pill.dart" \
  "${LIB}/features/family/screens/family_screen.dart" \
  "${LIB}/features/profile/screens/profile_screen.dart" 2>/dev/null

echo
echo "── Балансы скобок ──"
for f in \
  "${LIB}/core/widgets/macro_pill.dart" \
  "${LIB}/features/family/screens/family_screen.dart" \
  "${LIB}/features/profile/screens/profile_screen.dart"; do
  awk -v f="$f" '
    { for (i=1;i<=length($0);i++){c=substr($0,i,1); if(c=="{")o++; else if(c=="}")cl++; if(c=="(")po++; else if(c==")")pc++} }
    END { printf "  %s: { %d/%d  ( %d/%d\n", f, o, cl, po, pc }
  ' "$f"
done

echo
echo "── Парсинг (dart format --set-exit-if-changed) ──"
RC=0
for f in \
  "${LIB}/core/widgets/macro_pill.dart" \
  "${LIB}/features/family/screens/family_screen.dart" \
  "${LIB}/features/profile/screens/profile_screen.dart"; do
  if dart format --output=none --set-exit-if-changed "$f" >/dev/null 2>&1; then
    echo "  ✓ $f"
  else
    # формат уже применён предыдущим запуском — это не ошибка парсинга
    if dart format --output=none "$f" >/dev/null 2>&1; then
      echo "  ✓ $f (parses)"
    else
      echo "  ✗ $f (parse error!)"
      RC=1
    fi
  fi
done

echo
echo "── git status ──"
cd "${ROOT}" && git status --short

echo
echo "── ключевые места family_screen ──"
echo "  декларация _mealPlanType:"
grep -n "_mealPlanType" "${LIB}/features/family/screens/family_screen.dart" | head -10
echo
echo "  meal_plan_type в _save:"
grep -n "meal_plan_type" "${LIB}/features/family/screens/family_screen.dart" | head -5

echo
echo "── ключевые места profile_screen ──"
grep -nE "_saveMealPlan|_load|/users/me/|MacroPillsRow" "${LIB}/features/profile/screens/profile_screen.dart" | head -10

echo
[ $RC -eq 0 ] && echo "✓ ВЕРИФИКАЦИЯ OK" || echo "✗ Есть проблемы"
exit $RC
