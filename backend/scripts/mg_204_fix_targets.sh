#!/usr/bin/env bash
set -euo pipefail

WEB="/opt/menugen/web/menugen-web"
SRC="$WEB/src"
MP="$SRC/pages/Menu/MenuPage.tsx"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUPS="/opt/menugen/backups"
cp "$MP" "$BACKUPS/MenuPage.tsx.bak_mg204fix2_${TS}"
echo "backup → $BACKUPS/MenuPage.tsx.bak_mg204fix2_${TS}"

python3 <<'PYEOF'
path = "/opt/menugen/web/menugen-web/src/pages/Menu/MenuPage.tsx"
s = open(path, encoding='utf-8').read()

# 1. Проверим, нет ли уже объявления targets внутри MenuGrid
if "const targets: NutritionTargets | null" in s:
    print("targets уже объявлен — пропускаю вставку")
else:
    anchor = "const MenuGrid: React.FC<MenuGridProps> = ({ menu, onRefresh, onDelete }) => {\n"
    if anchor not in s:
        raise SystemExit("MenuGrid declaration anchor not found")

    inject = (
        "  // MG_204_V_menu_inner\n"
        "  const userProfile = useAppSelector(state => state.auth.user?.profile);\n"
        "  const targets: NutritionTargets | null = (\n"
        "    userProfile && userProfile.calorie_target\n"
        "      ? {\n"
        "          calorie_target:   userProfile.calorie_target,\n"
        "          protein_target_g: String(userProfile.protein_target_g ?? ''),\n"
        "          fat_target_g:     String(userProfile.fat_target_g ?? ''),\n"
        "          carb_target_g:    String(userProfile.carb_target_g ?? ''),\n"
        "          fiber_target_g:   String(userProfile.fiber_target_g ?? ''),\n"
        "        }\n"
        "      : (userProfile?.targets_calculated ?? null)\n"
        "  );\n"
    )
    s = s.replace(anchor, anchor + inject, 1)
    print("Вставил объявление targets в MenuGrid")

open(path, 'w', encoding='utf-8').write(s)
print("Saved")
PYEOF

echo
echo "### tsc проверка ###"
cd "$WEB"
npx tsc --noEmit 2>&1 | tee /tmp/mg_204_tsc.log
RC=${PIPESTATUS[0]}
echo
if [ $RC -eq 0 ]; then
  echo "tsc OK ✅"
else
  echo "tsc returned $RC"
fi
echo
echo "Откат: cp $BACKUPS/MenuPage.tsx.bak_mg204fix2_${TS} $MP"
