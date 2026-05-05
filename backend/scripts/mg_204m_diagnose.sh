#!/usr/bin/env bash
# MG-204 mobile — разведка Flutter-проекта
# Использование: bash /opt/menugen/backend/scripts/mg_204m_diagnose.sh
set -u

ROOT="/opt/menugen"
MOB="${ROOT}/mobile/menugen_app"

echo "================================================================"
echo "  MG-204 mobile — DIAGNOSE"
echo "================================================================"

echo
echo "### 1. Существование Flutter-проекта"
ls -la "${ROOT}/mobile" 2>/dev/null || echo "  /opt/menugen/mobile НЕТ"
echo
if [ ! -d "${MOB}" ]; then
  echo "!!! ${MOB} не существует — на этом всё."
  exit 0
fi

echo "### 2. Структура lib/ (2 уровня)"
find "${MOB}/lib" -maxdepth 3 -type d 2>/dev/null | sort
echo
echo "### 2.1 Файлы в lib/ (2 уровня)"
find "${MOB}/lib" -maxdepth 3 -type f -name "*.dart" 2>/dev/null | sort

echo
echo "### 3. pubspec.yaml — зависимости"
if [ -f "${MOB}/pubspec.yaml" ]; then
  awk '/^dependencies:/,/^dev_dependencies:/' "${MOB}/pubspec.yaml"
else
  echo "  pubspec.yaml НЕТ"
fi

echo
echo "### 4. Версия Flutter / Dart (если установлены)"
which flutter 2>/dev/null && flutter --version 2>/dev/null | head -3 || echo "  flutter не в PATH"

echo
echo "### 5. Поиск state-management библиотек"
grep -E "flutter_bloc|provider|riverpod|get_it|getx|mobx|redux" "${MOB}/pubspec.yaml" 2>/dev/null || echo "  не найдено"

echo
echo "### 6. HTTP-клиент"
grep -E "dio|http:|chopper|retrofit" "${MOB}/pubspec.yaml" 2>/dev/null || echo "  не найдено"

echo
echo "### 7. Хранилище JWT / токенов"
grep -rE "flutter_secure_storage|shared_preferences|hive" "${MOB}/pubspec.yaml" 2>/dev/null || echo "  не найдено"
echo "  --- упоминания access_token / jwt в коде (первые 20):"
grep -rEn "access_token|refresh_token|Bearer|JWT|secureStorage|SecureStorage" "${MOB}/lib" 2>/dev/null | head -20 || echo "    нет"

echo
echo "### 8. Базовый URL API (где задан?)"
grep -rEn "baseUrl|BASE_URL|apiUrl|API_URL|31\.192\.110\.121|/api/v1" "${MOB}/lib" 2>/dev/null | head -20 || echo "  нет упоминаний"

echo
echo "### 9. Профиль пользователя (модель / экран)"
echo "--- модели Profile/User:"
find "${MOB}/lib" -type f -name "*.dart" \( -iname "*profile*" -o -iname "*user*" \) 2>/dev/null | head -30
echo "--- упоминания calorie_target / meal_plan_type:"
grep -rEn "calorie_target|protein_target|fat_target|carb_target|fiber_target|meal_plan_type" "${MOB}/lib" 2>/dev/null | head -30 || echo "  нет упоминаний"

echo
echo "### 10. Экран семьи"
find "${MOB}/lib" -type f -name "*.dart" -iname "*famil*" 2>/dev/null
echo
echo "--- содержимое каталога features/family (если есть):"
find "${MOB}/lib/features/family" -maxdepth 4 -type f -name "*.dart" 2>/dev/null || echo "  каталога features/family нет"

echo
echo "### 11. Маршруты / навигация"
grep -rEn "GoRouter|MaterialApp|onGenerateRoute|routes:" "${MOB}/lib" 2>/dev/null | head -20

echo
echo "### 12. Точка входа main.dart (head)"
[ -f "${MOB}/lib/main.dart" ] && head -60 "${MOB}/lib/main.dart" || echo "  main.dart нет"

echo
echo "### 13. .env / config-файлы"
ls -la "${MOB}/.env"* 2>/dev/null
find "${MOB}" -maxdepth 2 -type f \( -name "*.env" -o -name "config*.dart" -o -name "constants*.dart" -o -name "env*.dart" \) 2>/dev/null

echo
echo "### 14. git status в /opt/menugen"
cd "${ROOT}" && git status --short 2>/dev/null | head -40 || echo "  не git"

echo
echo "### 15. Размер проекта"
du -sh "${MOB}" 2>/dev/null
echo "  файлов .dart:"
find "${MOB}/lib" -type f -name "*.dart" 2>/dev/null | wc -l

echo
echo "================================================================"
echo "  DIAGNOSE DONE"
echo "================================================================"
