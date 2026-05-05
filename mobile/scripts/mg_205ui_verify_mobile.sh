#!/bin/bash
# /opt/menugen/mobile/scripts/mg_205ui_verify_mobile.sh
# Проверка изменённых кусков mobile.
set -uo pipefail
LIB=/opt/menugen/mobile/menugen_app/lib

echo "=== MG-205-UI mobile verify ==="

echo ""
echo "── profile_screen.dart: интеграция (lines 165-185) ──"
sed -n '160,190p' $LIB/features/profile/screens/profile_screen.dart

echo ""
echo "── family_screen.dart: интеграция (lines 495-520) ──"
sed -n '495,525p' $LIB/features/family/screens/family_screen.dart

echo ""
echo "── target_field.dart: первые 60 строк ──"
sed -n '1,60p' $LIB/core/widgets/target_field.dart

echo ""
echo "── ищем flutter в системе ──"
which flutter 2>/dev/null
ls -la /opt/flutter*/bin/flutter 2>/dev/null
ls -la $HOME/flutter/bin/flutter 2>/dev/null
docker compose -f /opt/menugen/docker-compose.yml ps --format '{{.Service}}' 2>/dev/null
echo ""
echo "(если flutter не установлен — нормально: проверим при сборке мобилки)"
