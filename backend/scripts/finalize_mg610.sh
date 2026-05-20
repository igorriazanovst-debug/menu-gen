#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/menugen"
MOB="$ROOT/mobile/menugen_app"

echo "===== flutter analyze (fridge feature only) ====="
cd "$MOB"
flutter analyze lib/features/fridge/ 2>&1 | tail -40 || true

echo
echo "===== git add/commit/push ====="
cd "$ROOT"
git add -A
git status --short
git commit -m "MG-610: fridge edit tools — bulk delete expired, history editor, required-field focus

backend:
- FridgeExpiredBulkDeleteView POST /fridge/expired/delete/ (ids|all + drop_history)
- FridgeHistoryEntryView DELETE /fridge/products/history/<name>/ (?drop_fridge)
- module-level timezone import
- tests test_mg_610_edit.py (8) — fridge regress 45/45

web:
- fridgeApi.deleteExpired / deleteHistoryEntry
- FridgePage: expired select-mode (single-select + delete selected/all)
- HistoryEditorModal (remove-from-history / drop-all)
- AddFridgeItemModal: focus+scroll to first missing required field

mobile:
- FridgeBloc: FridgeExpiredBulkDeleted / FridgeHistoryEntryDeleted
- FridgeScreen: expired select-mode + history button
- FridgeHistoryScreen (new)
- AddFridgeItemSheet: focus/highlight first missing required field"
git push origin main
echo
echo "HEAD: $(git rev-parse --short HEAD)"
echo "DONE"
