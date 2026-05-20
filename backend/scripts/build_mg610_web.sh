#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/menugen"
WEB="$ROOT/web/menugen-web"

cd "$WEB"
echo "===== TypeScript check ====="
npx tsc --noEmit 2>&1 | head -40 || true

echo
echo "===== Build ====="
CI=false npm run build 2>&1 | tail -25

echo
echo "===== Deploy to web-dist (preserve apk/) ====="
mkdir -p "$ROOT/web-dist/apk"
# move apk aside, clean, restore
TMP_APK="$(mktemp -d)"
if [ -d "$ROOT/web-dist/apk" ]; then cp -a "$ROOT/web-dist/apk/." "$TMP_APK/" 2>/dev/null || true; fi
rm -rf "$ROOT/web-dist"
mkdir -p "$ROOT/web-dist"
cp -a build/. "$ROOT/web-dist/"
mkdir -p "$ROOT/web-dist/apk"
cp -a "$TMP_APK/." "$ROOT/web-dist/apk/" 2>/dev/null || true
rm -rf "$TMP_APK"

echo
echo "===== Verify markers in bundle ====="
grep -rl "expired/delete" "$ROOT/web-dist/static/js/" | head -1 && echo "  expired/delete present" || echo "  WARN: expired/delete not found"
grep -rl "products/history" "$ROOT/web-dist/static/js/" | head -1 && echo "  history endpoint present" || echo "  WARN: history endpoint not found"
ls -lh "$ROOT/web-dist/apk/" 2>/dev/null || true
echo "DONE"
