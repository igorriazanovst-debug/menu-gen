#!/bin/bash
# /opt/menugen/backend/scripts/mg_607_apply_backend.sh
# MG-607: expand GenerateMenuSerializer (+ countries[], exclude_allergens[], exclude_disliked[])
# + generator changes (countries filter + per-request hard_exclude override)
# + переносит test_mg_607_filters.py из scripts/ в apps/menu/tests/ если нужно
set -euo pipefail

ROOT=/opt/menugen
BACKEND=$ROOT/backend
TS=$(date +%Y%m%d_%H%M%S)
BAK=$ROOT/backups/mg_607_$TS
mkdir -p "$BAK"

echo "═══ Backup ═══"
cp "$BACKEND/apps/menu/serializers.py" "$BAK/serializers.py.bak"
cp "$BACKEND/apps/menu/views.py"       "$BAK/views.py.bak"
cp "$BACKEND/apps/menu/generator.py"   "$BAK/generator.py.bak"
echo "Saved to $BAK"

echo "═══ Move test file if needed ═══"
if [ -f "$BACKEND/scripts/test_mg_607_filters.py" ]; then
  mv "$BACKEND/scripts/test_mg_607_filters.py" "$BACKEND/apps/menu/tests/test_mg_607_filters.py"
  echo "Moved test_mg_607_filters.py to apps/menu/tests/"
fi

# ─────────────────────────────────────────────────────────────────────────
# 1) serializers.py — добавить новые поля в GenerateMenuSerializer
# ─────────────────────────────────────────────────────────────────────────
python3 - <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/menu/serializers.py")
src = p.read_text(encoding="utf-8")

# Ищем существующую строку mode = ... и вставляем 3 новых поля ПОСЛЕ неё
needle = '    mode = serializers.ChoiceField(choices=["per_member", "family"], default="family", required=False)\n'
if needle not in src:
    raise SystemExit("FAIL: anchor (mode field) not found in serializers.py")

addition = (
    '    # MG_607_V_serializers: мульти-выбор стран + per-request override allergens/disliked\n'
    '    countries = serializers.ListField(\n'
    '        child=serializers.CharField(allow_blank=False),\n'
    '        required=False, allow_empty=True,\n'
    '    )\n'
    '    exclude_allergens = serializers.ListField(\n'
    '        child=serializers.CharField(allow_blank=False),\n'
    '        required=False, allow_empty=True,\n'
    '    )\n'
    '    exclude_disliked = serializers.ListField(\n'
    '        child=serializers.CharField(allow_blank=False),\n'
    '        required=False, allow_empty=True,\n'
    '    )\n'
)
if "MG_607_V_serializers" in src:
    print("[serializers.py] already patched (MG_607_V_serializers marker found) — skipped")
else:
    src = src.replace(needle, needle + addition)
    p.write_text(src, encoding="utf-8")
    print("[serializers.py] patched")
PYEOF

# ─────────────────────────────────────────────────────────────────────────
# 2) views.py — пробрасывать новые поля в filters
# ─────────────────────────────────────────────────────────────────────────
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/menu/views.py")
src = p.read_text(encoding="utf-8")

# Найти блок где собираются filters и mode-проброс
anchor = '        # MG_605A_V_views: проброс mode (per_member | family)\n        filters["mode"] = data.get("mode", "family")\n'
if anchor not in src:
    raise SystemExit("FAIL: anchor (MG_605A mode passthrough) not found in views.py")

addition = (
    '        # MG_607_V_views: countries (мульти), exclude_allergens, exclude_disliked\n'
    '        if data.get("countries"):\n'
    '            filters["countries"] = list(data["countries"])\n'
    '        if "exclude_allergens" in data:\n'
    '            filters["exclude_allergens"] = list(data.get("exclude_allergens") or [])\n'
    '        if "exclude_disliked" in data:\n'
    '            filters["exclude_disliked"] = list(data.get("exclude_disliked") or [])\n'
)
if "MG_607_V_views" in src:
    print("[views.py] already patched (MG_607_V_views marker found) — skipped")
else:
    src = src.replace(anchor, anchor + addition)
    p.write_text(src, encoding="utf-8")
    print("[views.py] patched")
PYEOF

# ─────────────────────────────────────────────────────────────────────────
# 3) generator.py — countries в pool + per-request override hard_exclude
# ─────────────────────────────────────────────────────────────────────────
python3 - <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/menu/generator.py")
src = p.read_text(encoding="utf-8")

# ── (a) _build_recipe_pool: после строки 'country = self.filters.get("country")'
#       заменить блок country-фильтра на countries-aware
old_country_block = (
    '        country = self.filters.get("country")\n'
    '        if country and self.features.get("country"):\n'
    '            qs = qs.filter(country__iexact=country)\n'
)
new_country_block = (
    '        # MG_607_V_generator: countries (list) имеет приоритет над country (str)\n'
    '        countries = self.filters.get("countries")\n'
    '        country = self.filters.get("country")\n'
    '        if self.features.get("country"):\n'
    '            if countries:\n'
    '                qs = qs.filter(country__in=list(countries))\n'
    '            elif country:\n'
    '                qs = qs.filter(country__iexact=country)\n'
)
if "MG_607_V_generator" in src:
    print("[generator.py] already patched (MG_607_V_generator marker found) — skipped (a/b)")
else:
    if old_country_block not in src:
        raise SystemExit("FAIL: anchor (_build_recipe_pool country block) not found in generator.py")
    src = src.replace(old_country_block, new_country_block)

    # ── (b) _get_hard_exclude — override через filters
    old_hard = (
        '    def _get_hard_exclude(self, member) -> set:\n'
        '        exclude = set()\n'
        '        user = member.user\n'
        '        if isinstance(user.allergies, list):\n'
        '            exclude.update(a.lower() for a in user.allergies)\n'
        '        if self.features.get("disliked") and isinstance(user.disliked_products, list):\n'
        '            exclude.update(d.lower() for d in user.disliked_products)\n'
        '        if self.features.get("allergies_family"):\n'
        '            for m in self.members:\n'
        '                if isinstance(m.user.allergies, list):\n'
        '                    exclude.update(a.lower() for a in m.user.allergies)\n'
        '        return exclude\n'
    )
    new_hard = (
        '    def _get_hard_exclude(self, member) -> set:\n'
        '        # MG_607_V_generator: per-request override через filters.exclude_allergens / exclude_disliked\n'
        '        override_a = self.filters.get("exclude_allergens")\n'
        '        override_d = self.filters.get("exclude_disliked")\n'
        '        exclude = set()\n'
        '        user = member.user\n'
        '        if override_a is not None:\n'
        '            exclude.update(a.lower() for a in override_a if isinstance(a, str))\n'
        '        elif isinstance(user.allergies, list):\n'
        '            exclude.update(a.lower() for a in user.allergies)\n'
        '        if override_d is not None:\n'
        '            if self.features.get("disliked"):\n'
        '                exclude.update(d.lower() for d in override_d if isinstance(d, str))\n'
        '        elif self.features.get("disliked") and isinstance(user.disliked_products, list):\n'
        '            exclude.update(d.lower() for d in user.disliked_products)\n'
        '        if override_a is None and self.features.get("allergies_family"):\n'
        '            for m in self.members:\n'
        '                if isinstance(m.user.allergies, list):\n'
        '                    exclude.update(a.lower() for a in m.user.allergies)\n'
        '        return exclude\n'
    )
    if old_hard not in src:
        raise SystemExit("FAIL: anchor (_get_hard_exclude block) not found in generator.py")
    src = src.replace(old_hard, new_hard)

    # ── (c) _family_virtual_member — тот же override
    old_virt = (
        '    def _family_virtual_member(self) -> dict:\n'
        '        exclude = set()\n'
        '        cals = []\n'
        '        for m in self.members:\n'
        '            user = m.user\n'
        '            if isinstance(user.allergies, list):\n'
        '                exclude.update(a.lower() for a in user.allergies)\n'
        '            if self.features.get("disliked") and isinstance(user.disliked_products, list):\n'
        '                exclude.update(d.lower() for d in user.disliked_products)\n'
    )
    new_virt = (
        '    def _family_virtual_member(self) -> dict:\n'
        '        # MG_607_V_generator: per-request override\n'
        '        override_a = self.filters.get("exclude_allergens")\n'
        '        override_d = self.filters.get("exclude_disliked")\n'
        '        exclude = set()\n'
        '        cals = []\n'
        '        if override_a is not None:\n'
        '            exclude.update(a.lower() for a in override_a if isinstance(a, str))\n'
        '        if override_d is not None and self.features.get("disliked"):\n'
        '            exclude.update(d.lower() for d in override_d if isinstance(d, str))\n'
        '        for m in self.members:\n'
        '            user = m.user\n'
        '            if override_a is None and isinstance(user.allergies, list):\n'
        '                exclude.update(a.lower() for a in user.allergies)\n'
        '            if override_d is None and self.features.get("disliked") and isinstance(user.disliked_products, list):\n'
        '                exclude.update(d.lower() for d in user.disliked_products)\n'
    )
    if old_virt not in src:
        raise SystemExit("FAIL: anchor (_family_virtual_member start) not found in generator.py")
    src = src.replace(old_virt, new_virt)

    p.write_text(src, encoding="utf-8")
    print("[generator.py] patched (a/b/c)")
PYEOF

echo
echo "═══ Done. Restart backend ═══"
cd "$ROOT" && docker compose restart backend && sleep 3 && docker compose logs --tail 15 backend
