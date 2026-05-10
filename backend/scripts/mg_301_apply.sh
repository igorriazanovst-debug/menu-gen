#!/usr/bin/env bash
# MG-301 apply: метод тарелки — финализация.
#
# Что делает:
#   1. БД-бэкап (gzip).
#   2. .bak копии трогаемых файлов.
#   3. Пишет apps/menu/exceptions.py (EmptyRolePoolError + сообщения human-readable).
#   4. Патчит apps/menu/generator.py:
#      - бросает EmptyRolePoolError вместо тихого None при пустом пуле;
#      - пишет AuditLog (best-effort).
#   5. Патчит apps/menu/views.py:
#      - ловит EmptyRolePoolError → 400 с понятным сообщением.
#   6. Добавляет тесты apps/menu/tests/test_mg_301.py.
#   7. pytest.
#
# Идемпотентно: маркеры MG_301_V_*; повторный запуск ничего не ломает.

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/opt/menugen}"
COMPOSE="${PROJECT_ROOT}/docker-compose.yml"
BACKEND="${PROJECT_ROOT}/backend"
MENU_APP="${BACKEND}/apps/menu"
BACKUPS="${PROJECT_ROOT}/backups"
TS="$(date +%Y%m%d_%H%M%S)"

MARKER_VERSION="MG_301_V_1"

mkdir -p "${BACKUPS}"

echo "=== MG-301 APPLY === ${TS}"
echo

# ── 1. БД-бэкап ──────────────────────────────────────────────────────────────
echo "[1/7] БД-бэкап → ${BACKUPS}/db_${TS}.sql.gz"
# Тянем креды из самого контейнера db, не хардкодим
DB_USER_REAL="$(docker compose -f "${COMPOSE}" exec -T db sh -c 'printf %s "$POSTGRES_USER"')"
DB_NAME_REAL="$(docker compose -f "${COMPOSE}" exec -T db sh -c 'printf %s "$POSTGRES_DB"')"
echo "  pg_dump as user='${DB_USER_REAL}' db='${DB_NAME_REAL}'"
docker compose -f "${COMPOSE}" exec -T db pg_dump -U "${DB_USER_REAL}" "${DB_NAME_REAL}" \
    | gzip > "${BACKUPS}/db_${TS}.sql.gz"
ls -la "${BACKUPS}/db_${TS}.sql.gz"
echo

# ── 2. .bak копии файлов ─────────────────────────────────────────────────────
echo "[2/7] .bak копии исходников"
for f in "${MENU_APP}/generator.py" "${MENU_APP}/views.py"; do
    if [[ -f "${f}" ]]; then
        cp -n "${f}" "${f}.bak_mg301_${TS}"
        echo "  ✓ $(basename "${f}").bak_mg301_${TS}"
    fi
done
echo

# ── 3. apps/menu/exceptions.py ───────────────────────────────────────────────
echo "[3/7] apps/menu/exceptions.py"
python3 <<'PYEOF'
import os
from pathlib import Path

target = Path("/opt/menugen/backend/apps/menu/exceptions.py")
content = '''"""
MG-301: исключения генератора меню.

EmptyRolePoolError — поднимается, если для требуемой роли нет ни одного
подходящего рецепта (после применения hard-фильтров аллергий/нелюбимого).

Сообщение составляется на русском, понятным для не-технического пользователя
языком — оно проксируется в API ответ 400.
"""
# MG_301_V_exceptions
from __future__ import annotations
from typing import Optional


# человекочитаемые названия ролей
ROLE_LABELS_RU = {
    "protein":   "белковый компонент (мясо, рыба, бобы, яйца, творог)",
    "grain":     "зерновой/крахмалистый компонент (крупа, гарнир, хлеб)",
    "vegetable": "овощной компонент",
    "fruit":     "фруктовый компонент",
    "dairy":     "молочный компонент",
    "oil":       "масло/жир",
    "other":     "компонент",
}

MEAL_LABELS_RU = {
    "breakfast": "завтрака",
    "lunch":     "обеда",
    "dinner":    "ужина",
    "snack1":    "первого перекуса",
    "snack2":    "второго перекуса",
    "snack":     "перекуса",
}


class MenuGeneratorError(Exception):
    """Базовое исключение генератора меню."""

    code: str = "menu_generator_error"

    def to_response(self) -> dict:
        return {"error": self.code, "message": str(self)}


class EmptyRolePoolError(MenuGeneratorError):
    """
    Не нашлось рецептов нужной роли (food_group) для приёма пищи —
    после применения hard-фильтров (аллергии, нелюбимые продукты).
    """

    code = "empty_role_pool"

    def __init__(
        self,
        role: str,
        meal_slot: str,
        day_offset: int,
        member_name: Optional[str] = None,
        reason_hint: str = "",
    ):
        self.role = role
        self.meal_slot = meal_slot
        self.day_offset = day_offset
        self.member_name = member_name or ""
        self.reason_hint = reason_hint

        role_lbl = ROLE_LABELS_RU.get(role, role)
        meal_lbl = MEAL_LABELS_RU.get(meal_slot, meal_slot)
        day_n = day_offset + 1
        who = f" для {self.member_name}" if self.member_name else ""

        msg = (
            f"Не удалось подобрать {role_lbl}{who} "
            f"для {meal_lbl} (день {day_n}). "
        )
        if reason_hint:
            msg += f"{reason_hint} "
        msg += (
            "Возможные причины: слишком строгие фильтры (страна, время "
            "приготовления), список аллергий или нелюбимых продуктов "
            "исключил все подходящие рецепты, либо в базе пока мало "
            "рецептов этой группы. Попробуйте ослабить фильтры или "
            "уменьшить список исключений."
        )
        super().__init__(msg)

    def to_response(self) -> dict:
        return {
            "error": self.code,
            "message": str(self),
            "details": {
                "role": self.role,
                "meal_slot": self.meal_slot,
                "day_offset": self.day_offset,
                "member_name": self.member_name,
            },
        }
'''

if target.exists():
    cur = target.read_text(encoding="utf-8")
    if "MG_301_V_exceptions" in cur:
        print("  = exceptions.py уже содержит маркер — пропуск")
    else:
        target.write_text(content, encoding="utf-8")
        print("  ✎ exceptions.py перезаписан (нет маркера)")
else:
    target.write_text(content, encoding="utf-8")
    print("  ✓ exceptions.py создан")
PYEOF
echo

# ── 4. Патчим generator.py ───────────────────────────────────────────────────
echo "[4/7] generator.py — _pick_for_role, audit log, маркер"
python3 <<'PYEOF'
import re
from pathlib import Path

p = Path("/opt/menugen/backend/apps/menu/generator.py")
src = p.read_text(encoding="utf-8")

if "MG_301_V_generator" in src:
    print("  = generator.py уже патчен — пропуск")
    raise SystemExit(0)

# 1) импорт исключения и AuditLog
import_block = "from apps.fridge.models import FridgeItem\nfrom apps.recipes.models import Recipe\n"
new_import = (
    "from apps.fridge.models import FridgeItem\n"
    "from apps.recipes.models import Recipe\n"
    "\n"
    "# MG_301_V_generator: жёсткая ошибка при пустом пуле роли + audit\n"
    "from .exceptions import EmptyRolePoolError\n"
    "import logging\n"
    "\n"
    "logger = logging.getLogger(__name__)\n"
)
if import_block not in src:
    raise SystemExit("ERROR: import_block не найден в generator.py")
src = src.replace(import_block, new_import, 1)

# 2) В generate(): сделать так, чтобы member_name прокидывался в EmptyRolePoolError
#    Заменим тело внутреннего цикла "for role in roles:"  с тем, чтобы
#    отлавливать EmptyRolePoolError, дополнять member_name и audit-логом.
#    Текущий блок:
#       for role in roles:
#           recipe = self._pick_for_role(...)
#           if not recipe:
#               continue
#           used_per_member[member.id].add(recipe.id)
#           ...
#    Заменяем на: вызываем _pick_for_role_strict, без if-skip.
old_pick_block = (
    "                    for role in roles:\n"
    "                        recipe = self._pick_for_role(\n"
    "                            role=role,\n"
    "                            meal_type=db_meal_type,\n"
    "                            pools=pools,\n"
    "                            used=used_per_member[member.id],\n"
    "                            hard_exclude=hard_exclude,\n"
    "                            fridge_ids=fridge_ids,\n"
    "                            target_cal=per_role_cal,\n"
    "                            member_id=member.id,\n"
    "                            day_offset=day,\n"
    "                        )\n"
    "                        if not recipe:\n"
    "                            continue\n"
    "                        used_per_member[member.id].add(recipe.id)\n"
    "                        self.tracker.add(member.id, day, recipe)\n"
    "                        items.append({\n"
    "                            \"member\":         member,\n"
    "                            \"meal_type\":      db_meal_type,\n"
    "                            \"meal_slot\":      meal_slot,\n"
    "                            \"day_offset\":     day,\n"
    "                            \"recipe\":         recipe,\n"
    "                            \"component_role\": role,\n"
    "                        })\n"
)
new_pick_block = (
    "                    for role in roles:\n"
    "                        recipe = self._pick_for_role(\n"
    "                            role=role,\n"
    "                            meal_type=db_meal_type,\n"
    "                            pools=pools,\n"
    "                            used=used_per_member[member.id],\n"
    "                            hard_exclude=hard_exclude,\n"
    "                            fridge_ids=fridge_ids,\n"
    "                            target_cal=per_role_cal,\n"
    "                            member_id=member.id,\n"
    "                            day_offset=day,\n"
    "                        )\n"
    "                        if recipe is None:\n"
    "                            # MG_301_V_generator: не молча — поднимаем ошибку\n"
    "                            err = EmptyRolePoolError(\n"
    "                                role=role,\n"
    "                                meal_slot=meal_slot,\n"
    "                                day_offset=day,\n"
    "                                member_name=self._member_display_name(member),\n"
    "                            )\n"
    "                            self._audit_empty_pool(err, member)\n"
    "                            logger.warning(\n"
    "                                \"MG-301 empty role pool: role=%s slot=%s day=%s member=%s\",\n"
    "                                role, meal_slot, day, member.id,\n"
    "                            )\n"
    "                            raise err\n"
    "                        used_per_member[member.id].add(recipe.id)\n"
    "                        self.tracker.add(member.id, day, recipe)\n"
    "                        items.append({\n"
    "                            \"member\":         member,\n"
    "                            \"meal_type\":      db_meal_type,\n"
    "                            \"meal_slot\":      meal_slot,\n"
    "                            \"day_offset\":     day,\n"
    "                            \"recipe\":         recipe,\n"
    "                            \"component_role\": role,\n"
    "                        })\n"
)
if old_pick_block not in src:
    # запасной regex-подход
    pat = re.compile(
        r"                    for role in roles:\n"
        r"                        recipe = self\._pick_for_role\([\s\S]+?"
        r"                        items\.append\(\{[\s\S]+?\}\)\n",
        re.MULTILINE,
    )
    if not pat.search(src):
        raise SystemExit("ERROR: не нашёл блок 'for role in roles' для замены")
    src = pat.sub(new_pick_block, src, count=1)
else:
    src = src.replace(old_pick_block, new_pick_block, 1)

# 3) Добавляем helper-методы _member_display_name и _audit_empty_pool в конец класса
helpers = '''
    # ── MG-301: helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _member_display_name(member) -> str:
        """Имя члена семьи для понятного сообщения об ошибке."""
        try:
            user = member.user
            name = (getattr(user, "name", "") or "").strip()
            if name:
                return name
            email = (getattr(user, "email", "") or "").strip()
            if email:
                return email.split("@", 1)[0]
        except Exception:
            pass
        return ""

    def _audit_empty_pool(self, err, member) -> None:
        """Best-effort запись в общий AuditLog. Не должна падать сама по себе."""
        try:
            from apps.sync.models import AuditLog
            AuditLog.objects.create(
                user=getattr(member, "user", None),
                action="menu.generate.empty_role_pool",
                entity_type="menu_generation",
                entity_id=f"family:{self.family.id}",
                old_values=None,
                new_values={
                    "role":        err.role,
                    "meal_slot":   err.meal_slot,
                    "day_offset":  err.day_offset,
                    "member_id":   getattr(member, "id", None),
                    "member_name": err.member_name,
                    "plan_code":   self.plan_code,
                    "filters":     self.filters,
                    "period_days": self.period_days,
                    "message":     str(err),
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("MG-301: audit log write failed (non-fatal)")
'''

# Вставляем перед последним методом _fridge_score (он точно последний по диагностике)
marker_before = "    def _fridge_score(self, recipe: Recipe, fridge_ids: set) -> int:"
if marker_before not in src:
    raise SystemExit("ERROR: не нашёл _fridge_score для вставки helpers перед ним")

# Найдём конец файла: helpers вставим после _fridge_score
# Простой путь: src + helpers, т.к. _fridge_score — последний метод файла.
src = src.rstrip() + "\n" + helpers + "\n"

p.write_text(src, encoding="utf-8")
print("  ✓ generator.py пропатчен (импорт + raise + helpers)")
PYEOF
echo

# ── 5. Патчим views.py ───────────────────────────────────────────────────────
echo "[5/7] views.py — обработка EmptyRolePoolError → 400"
python3 <<'PYEOF'
from pathlib import Path

p = Path("/opt/menugen/backend/apps/menu/views.py")
src = p.read_text(encoding="utf-8")

if "MG_301_V_views" in src:
    print("  = views.py уже патчен — пропуск")
    raise SystemExit(0)

# 1) импорт MenuGeneratorError
imp_anchor = "from .generator import MenuGenerator"
if imp_anchor in src:
    src = src.replace(
        imp_anchor,
        "from .generator import MenuGenerator\n"
        "from .exceptions import MenuGeneratorError  # MG_301_V_views",
        1,
    )
else:
    # запасной вариант — найти любой импорт из .generator
    import re
    pat = re.compile(r"from \.generator import [^\n]+\n")
    m = pat.search(src)
    if not m:
        raise SystemExit("ERROR: не найден импорт из .generator")
    src = src[:m.end()] + "from .exceptions import MenuGeneratorError  # MG_301_V_views\n" + src[m.end():]

# 2) обернуть generator.generate() в try/except MenuGeneratorError
old = "        generated = generator.generate()\n"
new = (
    "        try:\n"
    "            generated = generator.generate()\n"
    "        except MenuGeneratorError as exc:  # MG_301_V_views\n"
    "            return Response(exc.to_response(), status=status.HTTP_400_BAD_REQUEST)\n"
)
if old not in src:
    raise SystemExit("ERROR: не нашёл строку 'generated = generator.generate()'")
src = src.replace(old, new, 1)

p.write_text(src, encoding="utf-8")
print("  ✓ views.py пропатчен")
PYEOF
echo

# ── 6. Тесты ─────────────────────────────────────────────────────────────────
echo "[6/7] apps/menu/tests/test_mg_301.py"
python3 <<'PYEOF'
from pathlib import Path

target = Path("/opt/menugen/backend/apps/menu/tests/test_mg_301.py")
content = '''"""
MG-301: тесты метода тарелки.
- основной приём = grain + protein + vegetable (3 компонента)
- перекус = 1 компонент
- сохраняется component_role в БД
- при пустом пуле роли API возвращает 400 + читаемое сообщение
- AuditLog содержит запись "menu.generate.empty_role_pool"
"""
# MG_301_V_tests
import datetime

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.models import MenuItem
from apps.recipes.models import Recipe
from apps.sync.models import AuditLog
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


def _mk_recipe(title, food_group, suitable_for=None, **extra):
    return Recipe.objects.create(
        title=title,
        ingredients=[{"name": "ингр", "quantity": "100", "unit": "г"}],
        steps=[{"text": "Шаг 1"}],
        nutrition={"calories": {"value": "300", "unit": "ккал"}},
        categories=[],
        is_published=True,
        food_group=food_group,
        suitable_for=suitable_for or ["breakfast", "lunch", "dinner", "snack"],
        **extra,
    )


@pytest.fixture
def setup_full(db):
    """Все 4 роли есть: protein/grain/vegetable/fruit/dairy."""
    user = User.objects.create_user(email="mg301@example.com", name="Тестер301", password="pass1234")
    family = Family.objects.create(owner=user, name="Семья 301")
    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    for i in range(5):
        _mk_recipe(f"Курица {i}",   "protein")
        _mk_recipe(f"Гречка {i}",   "grain")
        _mk_recipe(f"Салат {i}",    "vegetable")
        _mk_recipe(f"Яблоко {i}",   "fruit")
        _mk_recipe(f"Йогурт {i}",   "dairy")
    return user, family, member


@pytest.mark.django_db
class TestPlateMethodComponents:
    def test_main_meal_has_three_components(self, client, setup_full):
        user, _, _ = setup_full
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "start_date": str(datetime.date.today())},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        items = resp.data["items"]
        # за день: 3 приёма (breakfast/lunch/dinner) × 3 компонента = 9
        # breakfast=grain+protein+fruit, lunch/dinner=protein+grain+vegetable
        lunch_items = [i for i in items if i["meal_slot"] == "lunch"]
        roles = {i["component_role"] for i in lunch_items}
        assert roles == {"protein", "grain", "vegetable"}, f"lunch roles: {roles}"
        dinner_items = [i for i in items if i["meal_slot"] == "dinner"]
        roles = {i["component_role"] for i in dinner_items}
        assert roles == {"protein", "grain", "vegetable"}, f"dinner roles: {roles}"

    def test_breakfast_has_three_components(self, client, setup_full):
        user, _, _ = setup_full
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "start_date": str(datetime.date.today())},
            format="json",
        )
        assert resp.status_code == 201
        breakfast = [i for i in resp.data["items"] if i["meal_slot"] == "breakfast"]
        roles = {i["component_role"] for i in breakfast}
        assert roles == {"grain", "protein", "fruit"}, f"breakfast roles: {roles}"

    def test_snack_5_meal_plan(self, client, setup_full):
        user, _, _ = setup_full
        client.force_authenticate(user)
        resp = client.post(
            reverse("menu-generate"),
            {"period_days": 1, "meal_plan_type": "5", "start_date": str(datetime.date.today())},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        items = resp.data["items"]
        snack1 = [i for i in items if i["meal_slot"] == "snack1"]
        snack2 = [i for i in items if i["meal_slot"] == "snack2"]
        # snack1 = fruit + dairy (2), snack2 = protein + vegetable (2)
        assert {i["component_role"] for i in snack1} == {"fruit", "dairy"}
        assert {i["component_role"] for i in snack2} == {"protein", "vegetable"}

    def test_component_role_stored_in_db(self, client, setup_full):
        user, family, _ = setup_full
        client.force_authenticate(user)
        client.post(
            reverse("menu-generate"),
            {"period_days": 1},
            format="json",
        )
        items = MenuItem.objects.filter(menu__family=family)
        # все роли в наборе
        roles = set(items.values_list("component_role", flat=True))
        assert "protein" in roles
        assert "grain" in roles
        assert "vegetable" in roles or "fruit" in roles
        # ни одной "other" (т.к. пулы полные)
        assert "other" not in roles, f"unexpected 'other' in roles: {roles}"


@pytest.mark.django_db
class TestEmptyRolePool:
    def test_no_vegetable_recipes_returns_400(self, client, db):
        """Если нет рецептов с food_group=vegetable — 400 с понятным сообщением."""
        user = User.objects.create_user(email="empty@example.com", name="Пустой", password="pass1234")
        family = Family.objects.create(owner=user, name="Без овощей")
        FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
        # есть protein, grain, fruit — но НЕТ vegetable
        for i in range(3):
            _mk_recipe(f"Курица {i}", "protein")
            _mk_recipe(f"Гречка {i}", "grain")
            _mk_recipe(f"Яблоко {i}", "fruit")
            _mk_recipe(f"Йогурт {i}", "dairy")

        client.force_authenticate(user)
        resp = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        assert resp.status_code == 400
        body = resp.data
        assert body["error"] == "empty_role_pool"
        # сообщение по-русски, понятное
        assert "Не удалось подобрать" in body["message"]
        assert body["details"]["role"] == "vegetable"

    def test_empty_pool_writes_audit_log(self, client, db):
        user = User.objects.create_user(email="audit@example.com", name="Аудит", password="pass1234")
        family = Family.objects.create(owner=user, name="Аудит-семья")
        FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
        for i in range(3):
            _mk_recipe(f"Курица {i}", "protein")
            _mk_recipe(f"Гречка {i}", "grain")
            _mk_recipe(f"Яблоко {i}", "fruit")

        before = AuditLog.objects.filter(action="menu.generate.empty_role_pool").count()
        client.force_authenticate(user)
        client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        after = AuditLog.objects.filter(action="menu.generate.empty_role_pool").count()
        assert after == before + 1

    def test_no_menu_saved_on_error(self, client, db):
        """При ошибке меню не должно появиться в БД."""
        from apps.menu.models import Menu
        user = User.objects.create_user(email="rollback@example.com", name="Ролл", password="pass1234")
        family = Family.objects.create(owner=user, name="Ролл-семья")
        FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
        for i in range(3):
            _mk_recipe(f"Курица {i}", "protein")
            _mk_recipe(f"Гречка {i}", "grain")
            _mk_recipe(f"Яблоко {i}", "fruit")

        before = Menu.objects.filter(family=family).count()
        client.force_authenticate(user)
        resp = client.post(reverse("menu-generate"), {"period_days": 1}, format="json")
        assert resp.status_code == 400
        after = Menu.objects.filter(family=family).count()
        assert after == before
'''

if target.exists():
    cur = target.read_text(encoding="utf-8")
    if "MG_301_V_tests" in cur:
        print("  = test_mg_301.py уже содержит маркер — пропуск")
    else:
        target.write_text(content, encoding="utf-8")
        print("  ✎ test_mg_301.py перезаписан")
else:
    target.write_text(content, encoding="utf-8")
    print("  ✓ test_mg_301.py создан")
PYEOF
echo

# ── 7. pytest ────────────────────────────────────────────────────────────────
echo "[7/7] pytest apps/menu"
docker compose -f "${COMPOSE}" exec -T backend pytest apps/menu/ -v --tb=short 2>&1 | tail -80
echo

echo "=== MG-301 APPLY DONE === ${TS}"
echo
echo "Откат:"
echo "  DB_USER_REAL=\$(docker compose -f ${COMPOSE} exec -T db sh -c 'printf %s \"\$POSTGRES_USER\"')"
echo "  DB_NAME_REAL=\$(docker compose -f ${COMPOSE} exec -T db sh -c 'printf %s \"\$POSTGRES_DB\"')"
echo "  zcat ${BACKUPS}/db_${TS}.sql.gz | docker compose -f ${COMPOSE} exec -T db psql -U \"\${DB_USER_REAL}\" \"\${DB_NAME_REAL}\""
echo "  cp ${MENU_APP}/generator.py.bak_mg301_${TS} ${MENU_APP}/generator.py"
echo "  cp ${MENU_APP}/views.py.bak_mg301_${TS}     ${MENU_APP}/views.py"
echo "  rm ${MENU_APP}/exceptions.py ${MENU_APP}/tests/test_mg_301.py"
