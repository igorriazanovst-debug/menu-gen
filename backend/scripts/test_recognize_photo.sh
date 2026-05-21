#!/usr/bin/env bash
# E2E test for POST /api/v1/fridge/recognize-photo/
# Usage: bash test_recognize_photo.sh <email> <password> <image_path> [base_url]
#   base_url default: http://localhost:8000
set -u

EMAIL="${1:-}"
PASSWORD="${2:-}"
IMG="${3:-/tmp/test_product.jpg}"
BASE="${4:-http://localhost:8000}"

if [ -z "$EMAIL" ] || [ -z "$PASSWORD" ]; then
  echo "Usage: bash $0 <email> <password> <image_path> [base_url]"
  exit 1
fi
[ -f "$IMG" ] || { echo "image not found: $IMG"; exit 1; }

API="$BASE/api/v1"

echo "===== [1] login ====="
LOGIN_RESP="$(curl -s -m 30 -X POST "$API/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")"
echo "$LOGIN_RESP" | head -c 300; echo

ACCESS="$(echo "$LOGIN_RESP" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("access") or d.get("token") or d.get("access_token") or "")' 2>/dev/null)"
if [ -z "$ACCESS" ]; then
  echo "ERROR: no access token. Check login endpoint/credentials."
  echo "Tried fields: access / token / access_token"
  exit 1
fi
echo "access token: OK (len=${#ACCESS})"

echo
echo "===== [2] recognize-photo  mode=single (multipart) ====="
curl -s -m 90 -X POST "$API/fridge/recognize-photo/" \
  -H "Authorization: Bearer $ACCESS" \
  -F "image=@$IMG" \
  -F "mode=single" | python3 -m json.tool 2>/dev/null || echo "(non-json response above)"

echo
echo "===== [3] recognize-photo  mode=multi (multipart) ====="
curl -s -m 90 -X POST "$API/fridge/recognize-photo/" \
  -H "Authorization: Bearer $ACCESS" \
  -F "image=@$IMG" \
  -F "mode=multi" | python3 -m json.tool 2>/dev/null || echo "(non-json response above)"

echo
echo "===== DONE ====="
