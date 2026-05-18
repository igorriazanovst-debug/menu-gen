#!/usr/bin/env bash
set -u
BACKEND="/opt/menugen/backend"
echo "### settings layout"
find "$BACKEND" -maxdepth 4 -name "settings*" 2>/dev/null
echo
echo "### settings.py if single file"
find "$BACKEND" -maxdepth 4 -name "settings.py" 2>/dev/null
echo
echo "### manage.py DJANGO_SETTINGS_MODULE pointer"
grep -rn "DJANGO_SETTINGS_MODULE" "$BACKEND/manage.py" "$BACKEND/menugen/" 2>/dev/null | head -10
echo
echo "### content of menugen/ root"
ls -la "$BACKEND/menugen/" 2>/dev/null
