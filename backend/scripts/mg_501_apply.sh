#!/usr/bin/env bash
# MG-501 apply: добавление полей Recipe (cooking_method, has_added_sugar, oil_tsp, serving_size_label).
# - модель + миграция (0010)
# - сериализаторы (List/Detail/Write)
# - web/types/index.ts
# - RecipeEditModal.tsx (новая секция в classification)
# - тесты apps/recipes/tests/test_mg_501.py

set -uo pipefail

BACKEND="/opt/menugen/backend"
WEB="/opt/menugen/web/menugen-web"
SRC="$WEB/src"
COMPOSE="/opt/menugen/docker-compose.yml"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP="/tmp/mg_501_backup_${TS}"

MARK_MODEL="# MG_501_V_model"
MARK_SERS="# MG_501_V_serializers"
MARK_TESTS="# MG_501_V_tests"
MARK_TYPES="// MG_501_V_types"
MARK_MODAL="// MG_501_V_modal"

mkdir -p "$BACKUP"
echo "=== MG-501 apply (TS=$TS) ==="
echo "BACKUP: $BACKUP"
echo

# ─────────────────────────────────────────────────────────────────────────────
# 1. backend: backup
# ─────────────────────────────────────────────────────────────────────────────
echo "=== [1/8] Бэкапы ==="
F_MODELS="$BACKEND/apps/recipes/models.py"
F_SERS="$BACKEND/apps/recipes/serializers.py"
F_TYPES="$SRC/types/index.ts"
F_MODAL="$SRC/components/recipes/RecipeEditModal.tsx"

for f in "$F_MODELS" "$F_SERS" "$F_TYPES" "$F_MODAL"; do
  [ -f "$f" ] || { echo "  ❌ НЕТ файла: $f"; exit 1; }
  cp "$f" "$BACKUP/$(basename "$f").bak"
  echo "  ✅ $(basename "$f")"
done
echo

# ─────────────────────────────────────────────────────────────────────────────
# 2. БД-бэкап
# ─────────────────────────────────────────────────────────────────────────────
echo "=== [2/8] DB backup ==="
DB_CONT="$(docker compose -f "$COMPOSE" ps -q db 2>/dev/null | head -1)"
[ -z "$DB_CONT" ] && DB_CONT="$(docker compose -f "$COMPOSE" ps -q postgres 2>/dev/null | head -1)"
if [ -n "$DB_CONT" ]; then
  DB_USER="$(docker exec "$DB_CONT" printenv POSTGRES_USER 2>/dev/null || echo menugen_user)"
  DB_NAME="$(docker exec "$DB_CONT" printenv POSTGRES_DB   2>/dev/null || echo menugen)"
  mkdir -p /opt/menugen/backups
  DBBAK="/opt/menugen/backups/db_mg501_${TS}.sql.gz"
  docker exec "$DB_CONT" pg_dump -U "$DB_USER" -d "$DB_NAME" 2>/dev/null | gzip > "$DBBAK"
  echo "  ✅ $DBBAK ($(du -h "$DBBAK" | cut -f1))"
else
  echo "  ⚠️  DB контейнер не найден — пропуск"
fi
echo

# ─────────────────────────────────────────────────────────────────────────────
# 3. apps/recipes/models.py
# ─────────────────────────────────────────────────────────────────────────────
echo "=== [3/8] models.py — поля + CookingMethod ==="
if grep -q "$MARK_MODEL" "$F_MODELS"; then
  echo "  уже применено — skip"
else
python3 <<PYEOF
import pathlib
p = pathlib.Path("$F_MODELS")
s = p.read_text(encoding="utf-8")

# 3.1 — добавить CookingMethod после GrainType
anchor = '    class GrainType(models.TextChoices):\n        WHOLE   = "whole",   "Цельнозерновые"\n        REFINED = "refined", "Рафинированные"\n'
if anchor not in s:
    raise SystemExit("anchor for GrainType not found")

cooking_choices = '''
    class CookingMethod(models.TextChoices):  $MARK_MODEL
        BOILED     = "boiled",     "Варёное"
        BAKED      = "baked",      "Запечённое"
        FRIED      = "fried",      "Жареное"
        GRILLED    = "grilled",    "Гриль"
        RAW        = "raw",        "Сырое"
        STEWED     = "stewed",     "Тушёное"
        STEAMED    = "steamed",    "На пару"
'''
s = s.replace(anchor, anchor + cooking_choices, 1)

# 3.2 — добавить 4 поля сразу после carbs
carbs_line = "    carbs    = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, help_text='Углеводы на 1 порцию, г.')\n"
if carbs_line not in s:
    raise SystemExit("anchor for carbs field not found")

new_fields = '''    cooking_method      = models.CharField(  $MARK_MODEL
        max_length=16, choices=CookingMethod.choices, null=True, blank=True,
        help_text='Метод приготовления (MG-501).',
    )
    has_added_sugar     = models.BooleanField(default=False, help_text='Содержит добавленный сахар (MG-501).')
    oil_tsp             = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text='Расход масла в чайных ложках (MG-501).',
    )
    serving_size_label  = models.CharField(
        max_length=64, null=True, blank=True,
        help_text='Подпись размера порции, напр. "1 тарелка / 200 г" (MG-501).',
    )
'''
s = s.replace(carbs_line, carbs_line + new_fields, 1)

# 3.3 — добавить индекс на cooking_method
idx_anchor = '            models.Index(fields=["is_red_meat"]),\n'
if idx_anchor not in s:
    raise SystemExit("anchor for is_red_meat index not found")
idx_new = '            models.Index(fields=["cooking_method"]),  $MARK_MODEL\n            models.Index(fields=["has_added_sugar"]),\n'
s = s.replace(idx_anchor, idx_anchor + idx_new, 1)

p.write_text(s, encoding="utf-8")
print("  ✅ patched")
PYEOF
fi

echo
echo "  проверка:"
grep -nE "MG_501_V_model|cooking_method|has_added_sugar|oil_tsp|serving_size_label|class CookingMethod" \
  "$F_MODELS" | sed 's/^/    /'
echo

# ─────────────────────────────────────────────────────────────────────────────
# 4. apps/recipes/serializers.py
# ─────────────────────────────────────────────────────────────────────────────
echo "=== [4/8] serializers.py — добавить MG501_FIELDS + валидация ==="
if grep -q "$MARK_SERS" "$F_SERS"; then
  echo "  уже применено — skip"
else
python3 <<PYEOF
import pathlib
p = pathlib.Path("$F_SERS")
s = p.read_text(encoding="utf-8")

# 4.1 — после CLASSIFICATION_FIELDS добавить MG501_FIELDS
anchor = '''CLASSIFICATION_FIELDS = (
    "food_group",
    "suitable_for",
    "protein_type",
    "grain_type",
    "is_fatty_fish",
    "is_red_meat",
)
'''
if anchor not in s:
    raise SystemExit("anchor for CLASSIFICATION_FIELDS not found")

mg501_const = '''
MG501_FIELDS = (  $MARK_SERS
    "cooking_method",
    "has_added_sugar",
    "oil_tsp",
    "serving_size_label",
)
'''
s = s.replace(anchor, anchor + mg501_const, 1)

# 4.2 — все три сериализатора уже используют "+ CLASSIFICATION_FIELDS" — нужно расширить до "+ CLASSIFICATION_FIELDS + MG501_FIELDS"
old = ") + CLASSIFICATION_FIELDS"
new = ") + CLASSIFICATION_FIELDS + MG501_FIELDS"
cnt = s.count(old)
if cnt < 3:
    raise SystemExit(f"expected 3 occurrences of '+ CLASSIFICATION_FIELDS', got {cnt}")
s = s.replace(old, new)

p.write_text(s, encoding="utf-8")
print(f"  ✅ patched (расширил {cnt} сериализатора)")
PYEOF
fi

echo
echo "  проверка:"
grep -nE "MG_501_V_serializers|MG501_FIELDS|cooking_method|has_added_sugar|oil_tsp|serving_size_label" \
  "$F_SERS" | sed 's/^/    /'
echo

# ─────────────────────────────────────────────────────────────────────────────
# 5. miграция — makemigrations + проверка имени + migrate
# ─────────────────────────────────────────────────────────────────────────────
echo "=== [5/8] makemigrations + migrate ==="
WEB_CONT="$(docker compose -f "$COMPOSE" ps -q web 2>/dev/null | head -1)"
[ -z "$WEB_CONT" ] && WEB_CONT="$(docker compose -f "$COMPOSE" ps -q backend 2>/dev/null | head -1)"

if [ -z "$WEB_CONT" ]; then
  echo "  ❌ backend контейнер не найден"
  exit 1
fi
echo "  backend контейнер: $WEB_CONT"

# проверка существования 0010
EXISTING_0010="$(ls "$BACKEND/apps/recipes/migrations/" 2>/dev/null | grep -E '^0010' || true)"
if [ -n "$EXISTING_0010" ]; then
  echo "  миграция 0010 уже есть: $EXISTING_0010"
else
  echo "  --- makemigrations recipes --name mg_501_recipe_classification ---"
  docker exec "$WEB_CONT" python manage.py makemigrations recipes --name mg_501_recipe_classification 2>&1 | sed 's/^/    /'
fi

echo
echo "  --- migrate recipes ---"
docker exec "$WEB_CONT" python manage.py migrate recipes 2>&1 | sed 's/^/    /'
echo
echo "  --- showmigrations recipes ---"
docker exec "$WEB_CONT" python manage.py showmigrations recipes 2>&1 | tail -12 | sed 's/^/    /'
echo
echo "  --- проверка колонок в БД ---"
docker exec "$WEB_CONT" python manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    c.execute(\"\"\"
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'recipes'
          AND column_name IN ('cooking_method','has_added_sugar','oil_tsp','serving_size_label')
        ORDER BY column_name
    \"\"\")
    for row in c.fetchall():
        print(f'    {row[0]:24s} {row[1]}')
" 2>&1 | sed 's/^/    /'
echo

# ─────────────────────────────────────────────────────────────────────────────
# 6. types/index.ts
# ─────────────────────────────────────────────────────────────────────────────
echo "=== [6/8] web types/index.ts ==="
if grep -q "$MARK_TYPES" "$F_TYPES"; then
  echo "  уже применено — skip"
else
python3 <<PYEOF
import pathlib
p = pathlib.Path("$F_TYPES")
s = p.read_text(encoding="utf-8")

# 6.1 — добавить CookingMethod после GrainType
anchor = "export type GrainType    = 'whole' | 'refined';\n"
if anchor not in s:
    raise SystemExit("GrainType anchor not found")

cm_block = (
    "export type CookingMethod = "
    "'boiled' | 'baked' | 'fried' | 'grilled' | 'raw' | 'stewed' | 'steamed';  $MARK_TYPES\n"
)
s = s.replace(anchor, anchor + cm_block, 1)

# 6.2 — расширить interface Recipe — добавить 4 поля.
# вставка перед закрывающей }: ищем "is_red_meat?: boolean;" внутри Recipe и добавляем после
red_meat_line = "  is_red_meat?: boolean;\n"
if red_meat_line not in s:
    raise SystemExit("is_red_meat anchor not found")

new_props = (
    "  cooking_method?:     CookingMethod | null;  $MARK_TYPES\n"
    "  has_added_sugar?:    boolean;\n"
    "  oil_tsp?:            string | number | null;\n"
    "  serving_size_label?: string | null;\n"
)
s = s.replace(red_meat_line, red_meat_line + new_props, 1)

p.write_text(s, encoding="utf-8")
print("  ✅ patched")
PYEOF
fi

echo
echo "  проверка:"
grep -nE "MG_501_V_types|CookingMethod|cooking_method|has_added_sugar|oil_tsp|serving_size_label" \
  "$F_TYPES" | sed 's/^/    /'
echo

# ─────────────────────────────────────────────────────────────────────────────
# 7. RecipeEditModal.tsx
# ─────────────────────────────────────────────────────────────────────────────
echo "=== [7/8] RecipeEditModal.tsx ==="
if grep -q "$MARK_MODAL" "$F_MODAL"; then
  echo "  уже применено — skip"
else
python3 <<PYEOF
import pathlib, re
p = pathlib.Path("$F_MODAL")
s = p.read_text(encoding="utf-8")

# 7.1 — расширить импорт типов: добавить CookingMethod
old_imp = "import type { Recipe, FoodGroup, ProteinType, GrainType, SuitableMeal } from '../../types';"
new_imp = "import type { Recipe, FoodGroup, ProteinType, GrainType, SuitableMeal, CookingMethod } from '../../types';  $MARK_MODAL"
if old_imp in s:
    s = s.replace(old_imp, new_imp, 1)
else:
    raise SystemExit("import anchor not found")

# 7.2 — после GRAIN_TYPE_OPTIONS добавить COOKING_METHOD_OPTIONS
gto_block_end = '''const GRAIN_TYPE_OPTIONS: { value: GrainType; label: string }[] = [
  { value: 'whole',   label: 'Цельнозерновые' },
  { value: 'refined', label: 'Рафинированные' },
];
'''
if gto_block_end not in s:
    raise SystemExit("GRAIN_TYPE_OPTIONS anchor not found")

cm_options = '''
const COOKING_METHOD_OPTIONS: { value: CookingMethod; label: string }[] = [  $MARK_MODAL
  { value: 'boiled',  label: 'Варёное' },
  { value: 'baked',   label: 'Запечённое' },
  { value: 'fried',   label: 'Жареное' },
  { value: 'grilled', label: 'Гриль' },
  { value: 'raw',     label: 'Сырое' },
  { value: 'stewed',  label: 'Тушёное' },
  { value: 'steamed', label: 'На пару' },
];
'''
s = s.replace(gto_block_end, gto_block_end + cm_options, 1)

# 7.3 — useState для 4 новых полей: добавить рядом с isRedMeat
red_meat_state = "  const [isRedMeat,    setIsRedMeat]    = useState<boolean>(recipe.is_red_meat ?? false);\n"
if red_meat_state not in s:
    raise SystemExit("isRedMeat state anchor not found")

new_states = '''  const [cookingMethod,    setCookingMethod]    = useState<CookingMethod | ''>(recipe.cooking_method ?? '');  $MARK_MODAL
  const [hasAddedSugar,    setHasAddedSugar]    = useState<boolean>(recipe.has_added_sugar ?? false);
  const [oilTsp,           setOilTsp]           = useState<string>(recipe.oil_tsp != null ? String(recipe.oil_tsp) : '');
  const [servingSizeLabel, setServingSizeLabel] = useState<string>(recipe.serving_size_label ?? '');
'''
s = s.replace(red_meat_state, red_meat_state + new_states, 1)

# 7.4 — payload: добавить 4 поля рядом с is_red_meat
payload_anchor = '        is_red_meat:   isRedMeat,\n'
if payload_anchor not in s:
    raise SystemExit("payload is_red_meat anchor not found")

payload_new = '''        cooking_method:      cookingMethod || null,  $MARK_MODAL
        has_added_sugar:     hasAddedSugar,
        oil_tsp:             oilTsp.trim() === '' ? null : oilTsp.trim(),
        serving_size_label:  servingSizeLabel.trim() || null,
'''
s = s.replace(payload_anchor, payload_anchor + payload_new, 1)

# 7.5 — найти конец секции classification (после блока с isRedMeat checkbox)
# В файле есть structure:
#         <input type="checkbox" checked={isRedMeat} onChange={e => setIsRedMeat(e.target.checked)} />
#         <span ...>Красное мясо ...</span>
#         </label>
#       </div>
#     </div>
#   )}    <-- закрывает {tab === 'classification' && ( ... )}
#
# Вставим UI новых полей ВНУТРИ блока classification, перед его закрывающим </div>.
# Находим маркер: '              <input type="checkbox" checked={isRedMeat}'
# и идём до второго после него `</div>` (закрывающий wrapper "space-y-2") - вставляем после.

red_meat_input = '<input type="checkbox" checked={isRedMeat} onChange={e => setIsRedMeat(e.target.checked)} />'
idx = s.find(red_meat_input)
if idx < 0:
    raise SystemExit("isRedMeat checkbox anchor not found")

# найдём ближайший '</label>' после red_meat_input, затем '</div>' после него
lbl_end = s.find("</label>", idx)
if lbl_end < 0: raise SystemExit("</label> after isRedMeat not found")
div_end = s.find("</div>", lbl_end)
if div_end < 0: raise SystemExit("</div> after isRedMeat label not found")
insert_pos = div_end + len("</div>")

mg501_ui = '''

              {/* MG-501: метод готовки, сахар, масло, порция */}
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Метод приготовления</label>
                <select value={cookingMethod} onChange={e => setCookingMethod(e.target.value as CookingMethod | '')}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-tomato/40">
                  <option value="">— не указано —</option>
                  {COOKING_METHOD_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              <label className="flex items-center gap-2 px-3 py-2 rounded-xl border border-gray-200 cursor-pointer hover:bg-gray-50">
                <input type="checkbox" checked={hasAddedSugar} onChange={e => setHasAddedSugar(e.target.checked)} />
                <span className="text-sm">Содержит добавленный сахар</span>
              </label>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Масло (ч.л.)</label>
                  <Input type="number" step="0.1" min="0" value={oilTsp}
                    onChange={e => setOilTsp(e.target.value)} placeholder="напр. 1.5" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Размер порции</label>
                  <Input value={servingSizeLabel}
                    onChange={e => setServingSizeLabel(e.target.value)}
                    placeholder='напр. "1 тарелка / 200 г"' />
                </div>
              </div>
'''

s = s[:insert_pos] + mg501_ui + s[insert_pos:]
p.write_text(s, encoding="utf-8")
print("  ✅ patched")
PYEOF
fi

echo
echo "  проверка:"
grep -nE "MG_501_V_modal|COOKING_METHOD_OPTIONS|cookingMethod|hasAddedSugar|oilTsp|servingSizeLabel" \
  "$F_MODAL" | head -15 | sed 's/^/    /'
echo

# ─────────────────────────────────────────────────────────────────────────────
# 8. tsc + тесты
# ─────────────────────────────────────────────────────────────────────────────
echo "=== [8/8] tsc check + pytest ==="

cd "$WEB"
if [ -d node_modules ]; then
  echo "  --- npx tsc --noEmit ---"
  if npx --no-install tsc --noEmit 2>&1 | tee /tmp/mg_501_tsc.log | tail -10 | sed 's/^/    /'; then
    ERRS="$(grep -c 'error TS' /tmp/mg_501_tsc.log || true)"
    if [ "$ERRS" -eq 0 ]; then
      echo "  ✅ tsc: 0 ошибок"
    else
      echo "  ❌ tsc: $ERRS ошибок"
    fi
  fi
else
  echo "  ⚠️  node_modules нет — tsc пропуск"
fi
echo

# ── создаём тесты apps/recipes/tests/test_mg_501.py ────────────────────────
TEST_FILE="$BACKEND/apps/recipes/tests/test_mg_501.py"
echo "  --- pytest test_mg_501.py ---"
mkdir -p "$BACKEND/apps/recipes/tests"
[ -f "$BACKEND/apps/recipes/tests/__init__.py" ] || touch "$BACKEND/apps/recipes/tests/__init__.py"

cat > "$TEST_FILE" <<'PY'
$MARK_TESTS
"""MG-501 tests: новые поля Recipe + сериализаторы."""
import pytest
from decimal import Decimal

from apps.recipes.models import Recipe


@pytest.mark.django_db
class TestMG501Model:
    def test_cooking_method_choices(self):
        assert Recipe.CookingMethod.BOILED   == "boiled"
        assert Recipe.CookingMethod.BAKED    == "baked"
        assert Recipe.CookingMethod.FRIED    == "fried"
        assert Recipe.CookingMethod.GRILLED  == "grilled"
        assert Recipe.CookingMethod.RAW      == "raw"
        assert Recipe.CookingMethod.STEWED   == "stewed"
        assert Recipe.CookingMethod.STEAMED  == "steamed"

    def test_create_with_new_fields(self):
        r = Recipe.objects.create(
            title="Тестовое блюдо",
            cooking_method=Recipe.CookingMethod.BAKED,
            has_added_sugar=False,
            oil_tsp=Decimal("1.5"),
            serving_size_label="1 тарелка / 200 г",
        )
        r.refresh_from_db()
        assert r.cooking_method     == "baked"
        assert r.has_added_sugar    is False
        assert r.oil_tsp            == Decimal("1.5")
        assert r.serving_size_label == "1 тарелка / 200 г"

    def test_defaults(self):
        r = Recipe.objects.create(title="Без классификации")
        r.refresh_from_db()
        assert r.cooking_method     is None
        assert r.has_added_sugar    is False
        assert r.oil_tsp            is None
        assert r.serving_size_label is None


@pytest.mark.django_db
class TestMG501Serializers:
    def test_list_serializer_has_new_fields(self):
        from apps.recipes.serializers import RecipeListSerializer
        r = Recipe.objects.create(
            title="ListTest", cooking_method="grilled",
            has_added_sugar=True, oil_tsp=Decimal("2.0"),
            serving_size_label="1 шт",
        )
        data = RecipeListSerializer(r).data
        for f in ("cooking_method", "has_added_sugar", "oil_tsp", "serving_size_label"):
            assert f in data, f"List serializer должен содержать {f}"
        assert data["cooking_method"] == "grilled"
        assert data["has_added_sugar"] is True
        assert data["serving_size_label"] == "1 шт"

    def test_detail_serializer_has_new_fields(self):
        from apps.recipes.serializers import RecipeDetailSerializer
        r = Recipe.objects.create(title="DetailTest")
        data = RecipeDetailSerializer(r).data
        for f in ("cooking_method", "has_added_sugar", "oil_tsp", "serving_size_label"):
            assert f in data

    def test_write_serializer_creates_with_new_fields(self):
        from apps.recipes.serializers import RecipeWriteSerializer

        class _Req: pass
        req = _Req()
        # минимально: создать пользователя для author
        from apps.users.models import User
        u, _ = User.objects.get_or_create(name="WriteTest", defaults={"email": "wt@dev.local"})
        req.user = u

        ser = RecipeWriteSerializer(
            data={
                "title": "Новое блюдо",
                "ingredients": [{"name": "вода"}],
                "steps":       [{"text": "налить"}],
                "nutrition": {},
                "categories": [],
                "cooking_method":     "stewed",
                "has_added_sugar":    True,
                "oil_tsp":            "0.5",
                "serving_size_label": "стакан",
            },
            context={"request": req},
        )
        assert ser.is_valid(), ser.errors
        obj = ser.save()
        assert obj.cooking_method     == "stewed"
        assert obj.has_added_sugar    is True
        assert obj.oil_tsp            == Decimal("0.5")
        assert obj.serving_size_label == "стакан"
PY

# подменяем плейсхолдер маркера в файле
sed -i "s|^\$MARK_TESTS|$MARK_TESTS|" "$TEST_FILE"

docker exec "$WEB_CONT" pytest apps/recipes/tests/test_mg_501.py -v 2>&1 | tail -30 | sed 's/^/    /'
echo

# ─────────────────────────────────────────────────────────────────────────────
echo "=========================================="
echo "MG-501 APPLY DONE  (TS=$TS)"
echo "=========================================="
echo "Откат:"
echo "  cp $BACKUP/models.py.bak       $F_MODELS"
echo "  cp $BACKUP/serializers.py.bak  $F_SERS"
echo "  cp $BACKUP/index.ts.bak        $F_TYPES"
echo "  cp $BACKUP/RecipeEditModal.tsx.bak $F_MODAL"
echo "  rm -f $BACKEND/apps/recipes/migrations/0010_mg_501_recipe_classification.py"
echo "  docker exec $WEB_CONT python manage.py migrate recipes 0009"
