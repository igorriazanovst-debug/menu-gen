#!/usr/bin/env bash
# MG-204 mobile — установка Dart SDK + smoke-проверка парсинга 3 файлов.
# Полный dart analyze невозможен без Flutter SDK, поэтому проверяем
# парсер через `dart format --output=none`.
set -uo pipefail

ROOT="/opt/menugen"
MOB="${ROOT}/mobile/menugen_app"
LIB="${MOB}/lib"
FAMILY_SCREEN="${LIB}/features/family/screens/family_screen.dart"
PROFILE_SCREEN="${LIB}/features/profile/screens/profile_screen.dart"
MACRO_PILL="${LIB}/core/widgets/macro_pill.dart"

echo "================================================================"
echo "  Dart smoke (parse-only)"
echo "================================================================"

# 1) Поставить Dart, если не стоит
if ! command -v dart >/dev/null 2>&1; then
  echo "── установка Dart SDK ──"
  apt-get update -qq
  apt-get install -yq apt-transport-https wget gnupg curl
  curl -fsSL https://dl-ssl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /usr/share/keyrings/dart.gpg
  echo "deb [signed-by=/usr/share/keyrings/dart.gpg arch=amd64] https://storage.googleapis.com/download.dartlang.org/linux/debian stable main" \
    > /etc/apt/sources.list.d/dart_stable.list
  apt-get update -qq
  apt-get install -yq dart
fi

if ! command -v dart >/dev/null 2>&1; then
  echo "!!! не удалось установить dart"
  exit 1
fi
dart --version 2>&1

echo
echo "── dart format --output=none (проверка только парсера) ──"
RC=0
for f in "${MACRO_PILL}" "${FAMILY_SCREEN}" "${PROFILE_SCREEN}"; do
  echo
  echo "→ $f"
  if dart format --output=none "$f" 2>&1; then
    echo "  ✓ парсится"
  else
    echo "  ✗ ошибка парсинга"
    RC=1
  fi
done

if command -v flutter >/dev/null 2>&1; then
  echo
  echo "── flutter analyze (полный) ──"
  cd "${MOB}"
  flutter pub get 2>&1 | tail -5
  flutter analyze 2>&1 | head -80 || true
fi

echo
if [ $RC -eq 0 ]; then
  echo "✓ все 3 файла парсятся корректно"
else
  echo "✗ есть проблемы с парсингом"
fi
exit $RC
