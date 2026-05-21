#!/usr/bin/env bash
set -euo pipefail
REPO="igorriazanovst-debug/menu-gen"
ROOT="/opt/menugen"

echo "===== latest Flutter CI run ====="
gh run list --repo "$REPO" --branch main --workflow flutter_ci.yml --limit 3

RUN_ID="$(gh run list --repo "$REPO" --branch main --workflow flutter_ci.yml --limit 1 --json databaseId,status,conclusion --jq '.[0].databaseId')"
echo "RUN_ID=$RUN_ID"

echo
echo "===== watch ====="
gh run watch --repo "$REPO" "$RUN_ID" --exit-status

echo
echo "===== download APK ====="
rm -rf /tmp/apk_dl
gh run download "$RUN_ID" --repo "$REPO" --pattern 'menugen-debug-apk-*' --dir /tmp/apk_dl
APK="$(find /tmp/apk_dl -name 'menugen-debug-*.apk' | head -1)"
echo "APK=$APK"
mkdir -p "$ROOT/web-dist/apk"
cp "$APK" "$ROOT/web-dist/apk/menugen-debug.apk"
ls -lh "$ROOT/web-dist/apk/menugen-debug.apk"
echo "DONE → http://31.192.110.121:8081/apk/menugen-debug.apk"
