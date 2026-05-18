#!/bin/bash
# /opt/menugen/backend/scripts/mg_607_apply_web.sh
# MG-607 web: api/menu.ts + новый GenerateMenuForm + переключение MenuPage.tsx на него.
# ПРЕДВАРИТЕЛЬНО положи в /opt/menugen/backend/scripts/ файлы:
#   - menu.ts                 (заменит web/menugen-web/src/api/menu.ts)
#   - GenerateMenuForm.tsx    (новый, в web/menugen-web/src/components/menu/)
set -euo pipefail

ROOT=/opt/menugen
WEB=$ROOT/web/menugen-web
SCRIPTS=$ROOT/backend/scripts
TS=$(date +%Y%m%d_%H%M%S)
BAK=$ROOT/backups/mg_607_web_$TS
mkdir -p "$BAK"

# ─── Бэкап ─────────────────────────────────────────────────────────────
echo "═══ Backup ═══"
cp "$WEB/src/api/menu.ts"               "$BAK/menu.ts.bak"
cp "$WEB/src/pages/Menu/MenuPage.tsx"   "$BAK/MenuPage.tsx.bak"
echo "Saved to $BAK"

# ─── 1) api/menu.ts ────────────────────────────────────────────────────
if [ ! -f "$SCRIPTS/menu.ts" ]; then
  echo "ERROR: $SCRIPTS/menu.ts not found"
  exit 1
fi
cp "$SCRIPTS/menu.ts" "$WEB/src/api/menu.ts"
echo "[api/menu.ts] replaced"

# ─── 2) Новый компонент ────────────────────────────────────────────────
if [ ! -f "$SCRIPTS/GenerateMenuForm.tsx" ]; then
  echo "ERROR: $SCRIPTS/GenerateMenuForm.tsx not found"
  exit 1
fi
mkdir -p "$WEB/src/components/menu"
cp "$SCRIPTS/GenerateMenuForm.tsx" "$WEB/src/components/menu/GenerateMenuForm.tsx"
echo "[components/menu/GenerateMenuForm.tsx] created"

# ─── 3) MenuPage.tsx — переключить на GenerateMenuForm ─────────────────
python3 - <<'PYEOF'
from pathlib import Path
import re

p = Path("/opt/menugen/web/menugen-web/src/pages/Menu/MenuPage.tsx")
src = p.read_text(encoding="utf-8")

if "MG_607_V_menupage" in src:
    print("[MenuPage.tsx] already patched (marker found) — skipped")
    raise SystemExit(0)

# (a) Добавить import GenerateMenuForm после import DayNutritionSummary
import_anchor = "import { DayNutritionSummary } from '../../components/menu/DayNutritionSummary';\n"
import_new = (
    "import { DayNutritionSummary } from '../../components/menu/DayNutritionSummary';\n"
    "// MG_607_V_menupage\n"
    "import { GenerateMenuForm } from '../../components/menu/GenerateMenuForm';\n"
)
if import_anchor not in src:
    raise SystemExit("FAIL: import anchor (DayNutritionSummary) not found")
src = src.replace(import_anchor, import_new)

# (b) Заменить блок старой формы на использование GenerateMenuForm.
# Старый блок начинается с {showGenerateForm && (
#   <Card className="p-4">
#     ...
#   </Card>
# )}
# Заменяем регэкспом по multiline.
old_form_re = re.compile(
    r"\{showGenerateForm && \(\s*\n\s*<Card className=\"p-4\">.*?</Card>\s*\n\s*\)\}",
    re.DOTALL,
)
m = old_form_re.search(src)
if not m:
    raise SystemExit("FAIL: showGenerateForm block not found by regex")

new_form_block = (
    "{showGenerateForm && (\n"
    "          <GenerateMenuForm\n"
    "            initialMealPlan={mealPlanType}\n"
    "            userAllergies={user?.allergies ?? []}\n"
    "            userDisliked={user?.disliked_products ?? []}\n"
    "            userProfile={user?.profile}\n"
    "            onCancel={() => setShowGenerateForm(false)}\n"
    "            onCreated={(m) => {\n"
    "              setActiveMenu(m);\n"
    "              setShowGenerateForm(false);\n"
    "              load();\n"
    "            }}\n"
    "          />\n"
    "        )}"
)
src = old_form_re.sub(new_form_block, src, count=1)

# (c) Убрать неиспользуемый handleGenerate (старый), чтобы линтер не ругался
old_handle_re = re.compile(
    r"\n  const handleGenerate = async \(\) => \{.*?\n  \};\n",
    re.DOTALL,
)
src = old_handle_re.sub("\n  // MG_607_V_menupage: handleGenerate перенесён в GenerateMenuForm\n", src, count=1)

p.write_text(src, encoding="utf-8")
print("[MenuPage.tsx] patched")
PYEOF

# ─── 4) Build + deploy ─────────────────────────────────────────────────
echo
echo "═══ Building web ═══"
cd "$WEB"
CI=false npm run build 2>&1 | tail -20

echo
echo "═══ Deploying web ═══"
rm -rf "$ROOT/web-dist"
cp -a "$WEB/build/." "$ROOT/web-dist/"
echo "Deployed to /opt/menugen/web-dist"

echo
echo "═══ Done ═══"
ls -la "$ROOT/web-dist/" | head -5
