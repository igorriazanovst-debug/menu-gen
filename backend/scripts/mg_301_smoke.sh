#!/usr/bin/env bash
# MG-301 smoke: реальные API вызовы внутри backend контейнера.
#   1. POST /menu/generate/ → 201, items содержат component_role.
#   2. Проверка набора ролей для lunch/dinner = {protein, grain, vegetable}.
#   3. Проверка хранения component_role в menu_items.
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/opt/menugen}"
COMPOSE="${PROJECT_ROOT}/docker-compose.yml"

echo "=== MG-301 SMOKE === $(date -Is)"
echo

docker compose -f "${COMPOSE}" exec -T backend python <<'PYEOF'
import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from collections import Counter
from rest_framework.test import APIClient
from django.urls import reverse

from apps.users.models import User
from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe

# Берём реального админа или первого пользователя с family
user = User.objects.filter(email="admin@menugen.local").first() or User.objects.first()
print(f"[smoke] user = {user.email if user else None}")

family = Family.objects.filter(owner=user).first()
if not family:
    family = Family.objects.create(owner=user, name="Smoke MG-301")
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    print("[smoke] created family")
else:
    print(f"[smoke] family = {family.id} ({family.name})")

# Проверим, что в БД есть рецепты всех нужных групп
fg_dist = Counter(Recipe.objects.values_list("food_group", flat=True))
print(f"[smoke] food_group distribution: {dict(fg_dist)}")

c = APIClient()
c.force_authenticate(user)

# DRF APIClient по умолчанию шлёт HTTP_HOST=testserver, что не в ALLOWED_HOSTS прод-конфига.
# Используем localhost (всегда в ALLOWED_HOSTS dev/prod).
HOST_KW = {"HTTP_HOST": "localhost"}

# 1) основной: 3 дня, 3 приёма
resp = c.post(
    reverse("menu-generate"),
    {"period_days": 3, "meal_plan_type": "3"},
    format="json",
    **HOST_KW,
)
print(f"[smoke] generate 3d/3meals → status={resp.status_code}")
assert resp.status_code == 201, resp.data
items = resp.data["items"]
print(f"[smoke] items={len(items)}")

# 2) для каждого lunch/dinner ровно роли {protein, grain, vegetable}
by_slot = {}
for it in items:
    key = (it["day_offset"], it["meal_slot"])
    by_slot.setdefault(key, []).append(it["component_role"])

errors = []
for (day, slot), roles in by_slot.items():
    if slot in ("lunch", "dinner"):
        if set(roles) != {"protein", "grain", "vegetable"}:
            errors.append(f"day {day} {slot}: {roles}")
    elif slot == "breakfast":
        if set(roles) != {"grain", "protein", "fruit"}:
            errors.append(f"day {day} {slot}: {roles}")

if errors:
    print("[smoke] ❌ нарушения метода тарелки:")
    for e in errors:
        print("   ", e)
else:
    print("[smoke] ✅ метод тарелки соблюдён для всех приёмов пищи")

# 3) проверка БД
menu_id = resp.data["id"]
db_items = MenuItem.objects.filter(menu_id=menu_id)
db_role_dist = Counter(db_items.values_list("component_role", flat=True))
print(f"[smoke] DB role distribution: {dict(db_role_dist)}")
assert "other" not in db_role_dist, "В БД есть component_role='other' — что-то не так"

# 4) проверим snack-режим
resp5 = c.post(
    reverse("menu-generate"),
    {"period_days": 1, "meal_plan_type": "5"},
    format="json",
    **HOST_KW,
)
print(f"[smoke] generate 1d/5meals → status={resp5.status_code}")
assert resp5.status_code == 201
items5 = resp5.data["items"]
slots5 = Counter([i["meal_slot"] for i in items5])
print(f"[smoke] meal_slots: {dict(slots5)}")
assert slots5["snack1"] == 2, slots5  # fruit + dairy
assert slots5["snack2"] == 2, slots5  # protein + vegetable

# 5) аккуратно почистим smoke-данные
Menu.objects.filter(id__in=[menu_id, resp5.data["id"]]).delete()
print("[smoke] cleanup ok")

print("[smoke] === ALL OK ===")
PYEOF

echo
echo "=== SMOKE DONE ==="
