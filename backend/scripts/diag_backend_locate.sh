#!/usr/bin/env bash
# Phase 3b: locate real backend app paths, then dump contract.
# Usage: bash /opt/menugen/backend/scripts/diag_backend_locate.sh 2>&1 | tee /tmp/diag_backend_locate.out
set -u

hdr() { echo; echo "================================================================"; echo "  $*"; echo "================================================================"; }

hdr "0. Top of /opt/menugen"
ls -la /opt/menugen | head -40

hdr "1. /opt/menugen/backend layout (depth 3)"
find /opt/menugen/backend -maxdepth 3 -type d 2>/dev/null | sort

hdr "2. manage.py + settings.py locations"
find /opt/menugen -maxdepth 6 -type f \( -name "manage.py" -o -name "settings.py" \) 2>/dev/null | sort

hdr "3. All Django app urls.py files under /opt/menugen"
find /opt/menugen -maxdepth 8 -type f -name "urls.py" 2>/dev/null | sort

hdr "4. All Django models.py files under /opt/menugen"
find /opt/menugen -maxdepth 8 -type f -name "models.py" 2>/dev/null | sort

hdr "5. All views.py under /opt/menugen"
find /opt/menugen -maxdepth 8 -type f -name "views.py" 2>/dev/null | sort

hdr "6. All serializers.py under /opt/menugen"
find /opt/menugen -maxdepth 8 -type f -name "serializers.py" 2>/dev/null | sort

hdr "7. permissions.py files"
find /opt/menugen -maxdepth 8 -type f -name "permissions.py" 2>/dev/null | sort

hdr "8. Grep for class DiaryEntry / DiaryViewSet across whole tree"
grep -rEn "class DiaryEntry\b|class DiaryViewSet\b|class.*Diary.*View|class.*Diary.*Serializer" /opt/menugen --include="*.py" 2>/dev/null | grep -v "__pycache__" | grep -v "/mobile/" | head -40

hdr "9. Grep for IsFamilyPremiumOrReadOnly (from MG-606)"
grep -rEn "IsFamilyPremiumOrReadOnly|has_ever_had_premium|is_premium" /opt/menugen --include="*.py" 2>/dev/null | grep -v "__pycache__" | grep -v "/mobile/" | head -40

hdr "10. Grep for import-from-menu / import_from_menu"
grep -rEn "import.from.menu|import_from_menu|@action" /opt/menugen --include="*.py" 2>/dev/null | grep -v "__pycache__" | grep -v "/mobile/" | grep -iE "diary|import" | head -30

hdr "11. Grep for planned_menu_item / is_eaten"
grep -rEn "planned_menu_item|is_eaten" /opt/menugen --include="*.py" 2>/dev/null | grep -v "__pycache__" | grep -v "/mobile/" | head -30

hdr "DONE"
