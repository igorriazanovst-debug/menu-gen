#!/usr/bin/env bash
# MG-502 + MG-503 apply: контроль масла ≤5 ч.л./день и исключение has_added_sugar из основных приёмов.
# - generator.py: новые константы, _WeeklyTracker._daily расширяется (oil_tsp, sweet_count),
#   tracker.add() суммирует oil_tsp / инкрементит sweet_count,
#   _pick_for_role: фильтр oil_tsp>0.5 после лимита, фильтр has_added_sugar для основных приёмов,
#   MG-503 для snack: не более SWEET_PER_DAY_LIMIT раз/день,
#   _collect_daily_oil_warnings, _collect_daily_sweet_warnings.
# - tests/test_mg_502_503.py
set -uo pipefail

BACKEND="/opt/menugen/backend"
COMPOSE="/opt/menugen/docker-compose.yml"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP="/tmp/mg_502_503_backup_${TS}"

F_GEN="$BACKEND/apps/menu/generator.py"

MARK="# MG_502_503_V_generator"
MARK_TESTS="# MG_502_503_V_tests"

mkdir -p "$BACKUP"
echo "=== MG-502/503 apply (TS=$TS) ==="
echo "BACKUP: $BACKUP"
echo

# ── 1. backup ────────────────────────────────────────────────────────────────
echo "=== [1/5] Бэкап ==="
cp "$F_GEN" "$BACKUP/generator.py.bak"
echo "  ✅ generator.py"
echo

# ── 2. идемпотентность ──────────────────────────────────────────────────────
if grep -q "$MARK" "$F_GEN"; then
  echo "  уже применено — skip patch, перейдём к тестам"
  PATCH_SKIP=1
else
  PATCH_SKIP=0
fi

# ── 3. patch generator.py ───────────────────────────────────────────────────
if [ "$PATCH_SKIP" = "0" ]; then
echo "=== [2/5] patch generator.py ==="
python3 <<PYEOF
import pathlib, re
p = pathlib.Path("$F_GEN")
s = p.read_text(encoding="utf-8")

# 3.1. Новые константы — после блока MG_303 (MEAL_CAL_WINDOW_TIERS)
anchor = "MEAL_CAL_WINDOW_TIERS = (0.15, 0.30, 0.50)\n"
if anchor not in s:
    raise SystemExit("MEAL_CAL_WINDOW_TIERS anchor not found")

new_consts = '''
# MG_502_503_V_generator: контроль масла и сахара
DAILY_OIL_TSP_LIMIT     = 5.0   # ≤ 5 ч.л. масла в сутки на члена семьи
OIL_TSP_HEAVY_THRESHOLD = 0.5   # рецепт считается «маслянистым» при oil_tsp > 0.5
SWEET_PER_DAY_LIMIT     = 1     # ≤ 1 сладкого перекуса в день
MAIN_MEAL_TYPES         = ("breakfast", "lunch", "dinner")  # сладкое запрещено
'''
s = s.replace(anchor, anchor + new_consts, 1)

# 3.2. _WeeklyTracker._daily — расширить структуру: oil_tsp, sweet_count
old_daily = '        self._daily: Dict[int, Dict[int, Dict[str, int]]] = defaultdict(\n            lambda: defaultdict(lambda: {"plant": 0, "animal": 0, "mixed": 0})\n        )\n'
new_daily = (
    '        # MG_502_503_V_generator: добавлены oil_tsp (float) и sweet_count (int)\n'
    '        self._daily: Dict[int, Dict[int, Dict[str, float]]] = defaultdict(\n'
    '            lambda: defaultdict(lambda: {"plant": 0, "animal": 0, "mixed": 0,\n'
    '                                          "oil_tsp": 0.0, "sweet_count": 0})\n'
    '        )\n'
)
if old_daily not in s:
    raise SystemExit("_daily anchor not found")
s = s.replace(old_daily, new_daily, 1)

# 3.3. tracker.add(): добавить oil_tsp и sweet_count
old_add_tail = '        ptype = getattr(recipe, "protein_type", None)\n        if ptype in ("plant", "animal", "mixed"):\n            d[ptype] += 1\n'
new_add_tail = (
    '        ptype = getattr(recipe, "protein_type", None)\n'
    '        if ptype in ("plant", "animal", "mixed"):\n'
    '            d[ptype] += 1\n'
    '\n'
    '        # MG_502_503_V_generator: oil_tsp и sweet_count\n'
    '        oil = getattr(recipe, "oil_tsp", None)\n'
    '        if oil is not None:\n'
    '            try:\n'
    '                d["oil_tsp"] = float(d.get("oil_tsp", 0.0)) + float(oil)\n'
    '            except (TypeError, ValueError):\n'
    '                pass\n'
    '        if getattr(recipe, "has_added_sugar", False):\n'
    '            d["sweet_count"] = int(d.get("sweet_count", 0)) + 1\n'
)
if old_add_tail not in s:
    raise SystemExit("tracker.add tail anchor not found")
s = s.replace(old_add_tail, new_add_tail, 1)

# 3.4. _pick_for_role: добавить новый блок ПЕРЕД "Бонус по холодильнику".
# Найдём текст: "        # Бонус по холодильнику"
fridge_anchor = "        # Бонус по холодильнику\n"
if fridge_anchor not in s:
    raise SystemExit("fridge bonus anchor not found")

mg_block = '''        # MG_502_503_V_generator: контроль масла (≤5 ч.л./день)
        day_t = self.tracker.get_day(member_id, day_offset)
        if float(day_t.get("oil_tsp", 0.0)) > DAILY_OIL_TSP_LIMIT:
            light = [
                r for r in candidates
                if (getattr(r, "oil_tsp", None) or 0) <= OIL_TSP_HEAVY_THRESHOLD
            ]
            if light:
                candidates = light
            # если все кандидаты — «маслянистые», оставляем как есть, warning соберём после факта

        # MG_502_503_V_generator: исключение сахара
        # 1) основные приёмы: has_added_sugar=True вообще запрещено
        if meal_type in MAIN_MEAL_TYPES:
            no_sugar = [r for r in candidates if not getattr(r, "has_added_sugar", False)]
            if no_sugar:
                candidates = no_sugar
            # если все candidates сладкие (маловероятно для основных) — fallback random,
            # warning будет в _collect_daily_sweet_warnings
        # 2) snack: ≤ SWEET_PER_DAY_LIMIT сладких в день
        elif meal_type == "snack":
            if int(day_t.get("sweet_count", 0)) >= SWEET_PER_DAY_LIMIT:
                no_sugar = [r for r in candidates if not getattr(r, "has_added_sugar", False)]
                if no_sugar:
                    candidates = no_sugar

'''
s = s.replace(fridge_anchor, mg_block + fridge_anchor, 1)

# 3.5. Добавить вызовы новых сборщиков warnings.
# Anchor: после _collect_meal_calorie_warnings и self.last_warnings = warnings
old_collect = (
    "        # MG_303_V_generator: warnings по отклонению ккал приёма от target\n"
    "        warnings.extend(self._collect_meal_calorie_warnings())\n"
    "\n"
    "        self.last_warnings = warnings\n"
)
new_collect = (
    "        # MG_303_V_generator: warnings по отклонению ккал приёма от target\n"
    "        warnings.extend(self._collect_meal_calorie_warnings())\n"
    "\n"
    "        # MG_502_503_V_generator: warnings по маслу и сладкому\n"
    "        warnings.extend(self._collect_daily_oil_warnings())\n"
    "        warnings.extend(self._collect_daily_sweet_warnings())\n"
    "\n"
    "        self.last_warnings = warnings\n"
)
if old_collect not in s:
    raise SystemExit("collect anchor not found")
s = s.replace(old_collect, new_collect, 1)

# 3.6. Добавить новые методы _collect_daily_oil_warnings, _collect_daily_sweet_warnings
# в конец класса MenuGenerator. Anchor: метод _collect_meal_calorie_warnings.
# Найдём его сигнатуру и пройдём до конца — добавим методы сразу после него.
m = re.search(r"    def _collect_meal_calorie_warnings\(self\) -> list:\n", s)
if not m:
    raise SystemExit("_collect_meal_calorie_warnings anchor not found")

# Найдём окончание метода: следующий "    def " ИЛИ конец класса (другой class на 0-м уровне)
start = m.start()
nxt = re.search(r"\n    def [a-z_]", s[m.end():])
if nxt:
    end = m.end() + nxt.start()
else:
    # ищем top-level class или EOF
    cls = re.search(r"\nclass [A-Z]", s[m.end():])
    end = m.end() + (cls.start() if cls else len(s) - m.end())

new_methods = '''
    # ── MG-502/503: oil & sugar warnings ──────────────────────────────────────
    def _collect_daily_oil_warnings(self) -> list:
        """MG_502_503_V_generator: warning oil_overlimit если суммарно за день >5 ч.л."""
        out: list = []
        days = sorted(self.tracker._daily.keys())
        for day in days:
            if day >= self.period_days:
                continue
            for member in self.members:
                d = self.tracker._daily[day].get(member.id)
                if not d:
                    continue
                actual = float(d.get("oil_tsp", 0.0))
                if actual > DAILY_OIL_TSP_LIMIT:
                    out.append({
                        "code":         "oil_overlimit",
                        "member_id":    member.id,
                        "member_name":  self._member_display_name(member),
                        "day_offset":   day,
                        "actual_tsp":   round(actual, 1),
                        "limit_tsp":    DAILY_OIL_TSP_LIMIT,
                        "delta_tsp":    round(actual - DAILY_OIL_TSP_LIMIT, 1),
                    })
        return out

    def _collect_daily_sweet_warnings(self) -> list:
        """MG_502_503_V_generator: warning sweet_overlimit если за день >SWEET_PER_DAY_LIMIT сладких."""
        out: list = []
        days = sorted(self.tracker._daily.keys())
        for day in days:
            if day >= self.period_days:
                continue
            for member in self.members:
                d = self.tracker._daily[day].get(member.id)
                if not d:
                    continue
                cnt = int(d.get("sweet_count", 0))
                if cnt > SWEET_PER_DAY_LIMIT:
                    out.append({
                        "code":         "sweet_overlimit",
                        "member_id":    member.id,
                        "member_name":  self._member_display_name(member),
                        "day_offset":   day,
                        "sweet_count":  cnt,
                        "limit":        SWEET_PER_DAY_LIMIT,
                    })
        return out

'''

s = s[:end] + new_methods + s[end:]

p.write_text(s, encoding="utf-8")
print("  ✅ generator.py пропатчен")
PYEOF
echo
echo "  проверка маркеров:"
grep -nE "MG_502_503_V_generator|DAILY_OIL_TSP_LIMIT|SWEET_PER_DAY_LIMIT|MAIN_MEAL_TYPES|_collect_daily_oil_warnings|_collect_daily_sweet_warnings" \
  "$F_GEN" | sed 's/^/    /'
fi
echo

# ── 4. tests ────────────────────────────────────────────────────────────────
echo "=== [3/5] tests/test_mg_502_503.py ==="
TEST_FILE="$BACKEND/apps/menu/tests/test_mg_502_503.py"
cat > "$TEST_FILE" <<'PY'
# MG_502_503_V_tests
"""MG-502 (контроль масла) + MG-503 (исключение сахара) — тесты."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from apps.menu import generator as gen_module
from apps.menu.generator import (
    MenuGenerator,
    DAILY_OIL_TSP_LIMIT,
    OIL_TSP_HEAVY_THRESHOLD,
    SWEET_PER_DAY_LIMIT,
    MAIN_MEAL_TYPES,
)


def _R(rid=1, oil_tsp=None, has_added_sugar=False, food_group="grain", protein_type=None,
       is_red_meat=False, is_fatty_fish=False, suitable_for=None):
    """Билдер мок-рецепта."""
    r = MagicMock()
    r.id = rid
    r.oil_tsp = Decimal(str(oil_tsp)) if oil_tsp is not None else None
    r.has_added_sugar = has_added_sugar
    r.food_group = food_group
    r.protein_type = protein_type
    r.is_red_meat = is_red_meat
    r.is_fatty_fish = is_fatty_fish
    r.suitable_for = suitable_for or []
    r.nutrition = {}
    r.cook_time = "30 минут"
    r.title = f"recipe_{rid}"
    return r


class _Member:
    def __init__(self, mid=1):
        self.id = mid
        class _U:
            allergies = []
            disliked_products = []
            name = ""
            email = ""
            class profile:
                calorie_target = None
        self.user = _U()


def _make_gen(period=3):
    class _Fam:
        id = 1
    return MenuGenerator(
        family=_Fam(),
        members=[_Member()],
        period_days=period,
        start_date=date(2026, 1, 5),
        plan_code="free",
        filters={},
    )


# ───── tracker.add: oil_tsp / sweet_count ─────────────────────────────────────

def test_tracker_oil_tsp_accumulates_per_day():
    g = _make_gen()
    r1 = _R(rid=1, oil_tsp=1.0)
    r2 = _R(rid=2, oil_tsp=2.5)
    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        g.tracker.add(1, 0, r1)
        g.tracker.add(1, 0, r2)
        g.tracker.add(1, 1, r1)
    assert g.tracker.get_day(1, 0)["oil_tsp"] == pytest.approx(3.5)
    assert g.tracker.get_day(1, 1)["oil_tsp"] == pytest.approx(1.0)
    assert g.tracker.get_day(1, 2)["oil_tsp"] == pytest.approx(0.0)


def test_tracker_oil_tsp_none_means_zero():
    g = _make_gen()
    r = _R(rid=1, oil_tsp=None)
    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        g.tracker.add(1, 0, r)
    assert g.tracker.get_day(1, 0)["oil_tsp"] == pytest.approx(0.0)


def test_tracker_sweet_count_increments():
    g = _make_gen()
    sweet = _R(rid=1, has_added_sugar=True)
    plain = _R(rid=2, has_added_sugar=False)
    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        g.tracker.add(1, 0, sweet)
        g.tracker.add(1, 0, plain)
        g.tracker.add(1, 0, sweet)
    assert g.tracker.get_day(1, 0)["sweet_count"] == 2


# ───── _pick_for_role: MG-502 фильтрация по маслу ─────────────────────────────

def test_pick_oil_filter_when_over_limit():
    """Когда daily oil > 5 ч.л. — режем кандидатов с oil_tsp > 0.5."""
    g = _make_gen()
    g.tracker.get_day(1, 0)["oil_tsp"] = DAILY_OIL_TSP_LIMIT + 1.0  # уже превышен

    heavy = _R(rid=10, oil_tsp=2.0, food_group="grain")  # маслянистый
    light = _R(rid=11, oil_tsp=0.3, food_group="grain")  # лёгкий
    nones = _R(rid=12, oil_tsp=None, food_group="grain") # NULL → 0 → лёгкий

    pools = {"grain": [heavy, light, nones], "protein": [], "vegetable": [],
             "fruit": [], "dairy": [], "oil": [], "other": []}

    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="grain", meal_type="breakfast", pools=pools,
                used=set(), hard_exclude=set(), fridge_ids=set(),
                target_cal=None, member_id=1, day_offset=0,
            )
    assert picked.id in (11, 12), f"должен выбрать light/none, выбран id={picked.id}"


def test_pick_oil_no_filter_under_limit():
    """Под лимитом — фильтр не применяется."""
    g = _make_gen()
    g.tracker.get_day(1, 0)["oil_tsp"] = 2.0  # под лимитом

    heavy = _R(rid=10, oil_tsp=3.0, food_group="grain")
    pools = {"grain": [heavy], "protein": [], "vegetable": [],
             "fruit": [], "dairy": [], "oil": [], "other": []}

    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="grain", meal_type="breakfast", pools=pools,
                used=set(), hard_exclude=set(), fridge_ids=set(),
                target_cal=None, member_id=1, day_offset=0,
            )
    assert picked.id == 10  # heavy не отрезан


def test_pick_oil_fallback_when_only_heavy_available():
    """Превышен, но в пуле только маслянистые → fallback на текущих candidates."""
    g = _make_gen()
    g.tracker.get_day(1, 0)["oil_tsp"] = DAILY_OIL_TSP_LIMIT + 5.0

    heavy = _R(rid=10, oil_tsp=3.0, food_group="grain")
    pools = {"grain": [heavy], "protein": [], "vegetable": [],
             "fruit": [], "dairy": [], "oil": [], "other": []}

    with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="grain", meal_type="breakfast", pools=pools,
                used=set(), hard_exclude=set(), fridge_ids=set(),
                target_cal=None, member_id=1, day_offset=0,
            )
    assert picked is not None and picked.id == 10


# ───── _pick_for_role: MG-503 исключение сахара ───────────────────────────────

def test_pick_no_sugar_in_main_meals():
    """Для основных приёмов has_added_sugar=True должен быть отрезан."""
    g = _make_gen()

    sweet = _R(rid=20, has_added_sugar=True, food_group="grain")
    plain = _R(rid=21, has_added_sugar=False, food_group="grain")
    pools = {"grain": [sweet, plain], "protein": [], "vegetable": [],
             "fruit": [], "dairy": [], "oil": [], "other": []}

    for mt in MAIN_MEAL_TYPES:
        with patch.object(gen_module, "recipe_portion_grams", return_value=200.0):
            with patch("random.choice", side_effect=lambda c: c[0]):
                picked = g._pick_for_role(
                    role="grain", meal_type=mt, pools=pools,
                    used=set(), hard_exclude=set(), fridge_ids=set(),
                    target_cal=None, member_id=1, day_offset=0,
                )
        assert picked.id == 21, f"в {mt} не должно выбираться сладкое (выбран id={picked.id})"


def test_pick_sugar_allowed_in_snack_first_time():
    """Snack: первый раз сладкое разрешено."""
    g = _make_gen()
    sweet = _R(rid=30, has_added_sugar=True, food_group="fruit")
    pools = {"fruit": [sweet], "grain": [], "protein": [], "vegetable": [],
             "dairy": [], "oil": [], "other": []}

    with patch.object(gen_module, "recipe_portion_grams", return_value=100.0):
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="fruit", meal_type="snack", pools=pools,
                used=set(), hard_exclude=set(), fridge_ids=set(),
                target_cal=None, member_id=1, day_offset=0,
            )
    assert picked.id == 30


def test_pick_sugar_blocked_in_snack_after_limit():
    """Snack: ≥ SWEET_PER_DAY_LIMIT — режем сладкое."""
    g = _make_gen()
    g.tracker.get_day(1, 0)["sweet_count"] = SWEET_PER_DAY_LIMIT  # уже достигнуто

    sweet = _R(rid=30, has_added_sugar=True, food_group="fruit")
    plain = _R(rid=31, has_added_sugar=False, food_group="fruit")
    pools = {"fruit": [sweet, plain], "grain": [], "protein": [], "vegetable": [],
             "dairy": [], "oil": [], "other": []}

    with patch.object(gen_module, "recipe_portion_grams", return_value=100.0):
        with patch("random.choice", side_effect=lambda c: c[0]):
            picked = g._pick_for_role(
                role="fruit", meal_type="snack", pools=pools,
                used=set(), hard_exclude=set(), fridge_ids=set(),
                target_cal=None, member_id=1, day_offset=0,
            )
    assert picked.id == 31  # plain выбран, sweet отрезан


# ───── warnings collectors ───────────────────────────────────────────────────

def test_collect_oil_warnings_above_limit():
    g = _make_gen(period=3)
    mid = g.members[0].id
    g.tracker.get_day(mid, 0)["oil_tsp"] = DAILY_OIL_TSP_LIMIT + 2.0
    g.tracker.get_day(mid, 1)["oil_tsp"] = DAILY_OIL_TSP_LIMIT  # ровно лимит — НЕ warning
    g.tracker.get_day(mid, 2)["oil_tsp"] = 1.0

    out = g._collect_daily_oil_warnings()
    days = sorted(w["day_offset"] for w in out if w["code"] == "oil_overlimit")
    assert days == [0]
    w = next(x for x in out if x["day_offset"] == 0)
    assert w["actual_tsp"] == DAILY_OIL_TSP_LIMIT + 2.0
    assert w["delta_tsp"] == 2.0
    assert w["limit_tsp"] == DAILY_OIL_TSP_LIMIT


def test_collect_oil_warnings_silent_under_limit():
    g = _make_gen(period=3)
    mid = g.members[0].id
    g.tracker.get_day(mid, 0)["oil_tsp"] = 2.0
    g.tracker.get_day(mid, 1)["oil_tsp"] = 4.5
    out = g._collect_daily_oil_warnings()
    assert out == []


def test_collect_sweet_warnings_above_limit():
    g = _make_gen(period=3)
    mid = g.members[0].id
    g.tracker.get_day(mid, 0)["sweet_count"] = SWEET_PER_DAY_LIMIT + 1   # warning
    g.tracker.get_day(mid, 1)["sweet_count"] = SWEET_PER_DAY_LIMIT       # на грани — НЕ warning
    g.tracker.get_day(mid, 2)["sweet_count"] = 0
    out = g._collect_daily_sweet_warnings()
    days = sorted(w["day_offset"] for w in out if w["code"] == "sweet_overlimit")
    assert days == [0]


def test_collect_sweet_warnings_silent_under_limit():
    g = _make_gen(period=3)
    mid = g.members[0].id
    g.tracker.get_day(mid, 0)["sweet_count"] = 0
    g.tracker.get_day(mid, 1)["sweet_count"] = SWEET_PER_DAY_LIMIT
    out = g._collect_daily_sweet_warnings()
    assert out == []
PY

echo "  ✅ $TEST_FILE создан"
echo

# ── 4. pytest ───────────────────────────────────────────────────────────────
echo "=== [4/5] pytest apps/menu/tests/test_mg_502_503.py + регрессия ==="
WEB_CONT="$(docker compose -f "$COMPOSE" ps -q web 2>/dev/null | head -1)"
[ -z "$WEB_CONT" ] && WEB_CONT="$(docker compose -f "$COMPOSE" ps -q backend 2>/dev/null | head -1)"

if [ -n "$WEB_CONT" ]; then
  echo "  --- new tests ---"
  docker exec "$WEB_CONT" pytest apps/menu/tests/test_mg_502_503.py -v 2>&1 \
    | tail -30 | sed 's/^/    /'
  echo
  echo "  --- регрессия: все apps/menu/ ---"
  docker exec "$WEB_CONT" pytest apps/menu/ -v 2>&1 | tail -25 | sed 's/^/    /'
else
  echo "  ❌ контейнер не найден"
fi
echo

# ── 5. e2e smoke ────────────────────────────────────────────────────────────
echo "=== [5/5] e2e smoke: POST /api/v1/menu/generate/ ==="
docker exec "$WEB_CONT" python manage.py shell -c "
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.menu.models import Menu, MenuItem
from collections import Counter

U = get_user_model()
admin = U.objects.filter(email='admin@dev.local').first()
if not admin:
    print('NO admin@dev.local'); raise SystemExit
client = APIClient()
client.force_authenticate(user=admin)
resp = client.post(
    '/api/v1/menu/generate/',
    {'period_days': 3, 'start_date': '2026-05-09'},
    format='json', HTTP_HOST='localhost'
)
print(f'status: {resp.status_code}')
data = resp.data if hasattr(resp, 'data') else {}
warns = data.get('warnings', []) if isinstance(data, dict) else []
items = data.get('items', []) if isinstance(data, dict) else []
print(f'items total: {len(items)}')
print(f'warnings count: {len(warns)}')
codes = Counter(w.get('code') for w in warns)
print(f'warnings codes: {dict(codes)}')
oil_w = [w for w in warns if w.get('code') == 'oil_overlimit']
sweet_w = [w for w in warns if w.get('code') == 'sweet_overlimit']
print(f'oil_overlimit:   {len(oil_w)}')
print(f'sweet_overlimit: {len(sweet_w)}')
if oil_w[:1]:   print(f'  пример: {oil_w[0]}')
if sweet_w[:1]: print(f'  пример: {sweet_w[0]}')
" 2>&1 | sed 's/^/    /'
echo

echo "=========================================="
echo "MG-502/503 APPLY DONE  (TS=$TS)"
echo "=========================================="
echo "Откат:"
echo "  cp $BACKUP/generator.py.bak $F_GEN"
echo "  rm -f $TEST_FILE"
